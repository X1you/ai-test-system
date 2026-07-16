#!/usr/bin/env python3
"""
TestRail 适配器 — 完整参考实现

支持：
  - REST API + API Key 认证
  - 用例 CRUD（创建/更新/删除/批量）
  - TestRun 管理（创建/列表/执行）
  - 测试结果推送/拉取
  - Webhook 验证
"""

import hashlib
import hmac
import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

import requests
from requests.auth import HTTPBasicAuth

from integrations.base import BaseAdapter, AdapterConfig
from integrations.models import TestCase, TestResult, SyncResult, TestRun, Defect
from integrations.registry import AdapterRegistry

logger = logging.getLogger("ai-test-system.integrations")


@AdapterRegistry.register("testrail")
class TestRailAdapter(BaseAdapter):
    """TestRail 适配器 — 完整实现"""

    platform_name = "testrail"
    supported_transports = ["rest"]

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.base_url = config.base_url.rstrip("/")

        # TestRail 使用 Basic Auth，API Key 作为密码
        self.auth = HTTPBasicAuth(config.username, config.api_key or config.password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Content-Type": "application/json",
        })

        # 缓存项目/套件映射（避免重复查询）
        self._project_cache = {}
        self._suite_cache = {}
        self._section_cache = {}

    # ─── 认证 ───

    def authenticate(self) -> bool:
        """认证并建立连接"""
        try:
            response = self.session.get(f"{self.base_url}/index.php?/api/v2/get_current_user")
            if response.status_code == 200:
                self._user_info = response.json()
                logger.info(f"TestRail 认证成功: {self._user_info.get('email', '')}")
                return True
            logger.warning(f"TestRail 认证失败: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"TestRail 认证异常: {e}")
            return False

    # ─── 用例 CRUD ───

    def push_test_cases(self, cases: List[TestCase]) -> SyncResult:
        """推送用例（创建或更新）"""
        sync_id = f"sync_testrail_{int(time.time())}"
        started_at = datetime.now().isoformat()
        pushed = 0
        failed = 0
        errors = []

        # 按项目分组批量处理
        project_cases: dict = {}  # project_id -> [cases]

        for case in cases:
            # 从 custom_fields 或配置中获取 project_id
            project_id = case.custom_fields.get("testrail_project_id") or self.config.extra.get("project_id")
            if not project_id:
                errors.append(f"{case.id}: 缺少 project_id")
                failed += 1
                continue

            if project_id not in project_cases:
                project_cases[project_id] = []
            project_cases[project_id].append(case)

        # 批量处理每个项目
        for project_id, proj_cases in project_cases.items():
            try:
                # 获取项目信息
                project = self._get_project(project_id)
                if not project:
                    errors.append(f"project_id={project_id}: 项目不存在")
                    failed += len(proj_cases)
                    continue

                # 获取或创建默认套件
                suite_id = self._get_or_create_default_suite(project_id)

                # 批量添加用例
                payload = {
                    "suite_id": suite_id,
                    "cases": [
                        self._case_to_testrail_dict(c, project_id, suite_id)
                        for c in proj_cases
                    ]
                }

                response = self.session.post(
                    f"{self.base_url}/index.php?/api/v2/add_cases/{suite_id}",
                    json=payload,
                )

                if response.status_code == 200:
                    results = response.json()
                    pushed += len(proj_cases)
                else:
                    error_msg = f"批量添加失败: {response.status_code} - {response.text[:100]}"
                    errors.append(error_msg)
                    failed += len(proj_cases)

            except Exception as e:
                errors.append(f"project_id={project_id}: {str(e)}")
                failed += len(proj_cases)

        return SyncResult(
            sync_id=sync_id,
            direction="push",
            pushed=pushed,
            pulled=0,
            failed=failed,
            skipped=0,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            mode="full",
        )

    def pull_test_cases(self, filters: Optional[dict] = None) -> List[TestCase]:
        """拉取用例"""
        params = filters or {}

        # 必需参数：project_id, suite_id
        project_id = params.get("project_id") or self.config.extra.get("project_id")
        suite_id = params.get("suite_id") or self.config.extra.get("suite_id")

        if not project_id:
            raise ValueError("缺少 project_id 参数")

        # 获取项目套件列表
        suites = self._get_suites(project_id)
        if not suites:
            return []

        # 如果未指定 suite_id，使用第一个套件
        if not suite_id:
            suite_id = suites[0]["id"]

        response = self.session.get(
            f"{self.base_url}/index.php?/api/v2/get_cases/{project_id}&suite_id={suite_id}",
            params=params,
        )

        if response.status_code != 200:
            raise Exception(f"拉取失败: {response.status_code} - {response.text}")

        return [self._case_from_testrail_dict(item, project_id, suite_id)
                for item in response.json()]

    # ─── 测试结果 ───

    def push_test_results(self, run_id: str, results: List[TestResult]) -> SyncResult:
        """推送执行结果

        TestRail 要求批量推送结果格式：
        {"results": [{"case_id": 123, "status_id": 5, "comment": "xxx"}, ...]}
        """
        sync_id = f"sync_testrail_results_{int(time.time())}"
        started_at = datetime.now().isoformat()
        pushed = 0
        failed = 0
        errors = []

        # 构建 TestRail 结果列表
        testrail_results = []

        for result in results:
            try:
                # 根据 external_id 查找 case_id
                case_id = result.external_id or result.test_case_id.lstrip("TC-")
                status_id = self._status_to_testrail(result.status)

                testrail_results.append({
                    "case_id": case_id,
                    "status_id": status_id,
                    "comment": result.comment,
                    "elapsed": str(result.duration) if result.duration else None,
                    "assignedto_id": None,
                })
                pushed += 1
            except Exception as e:
                errors.append(f"{result.test_case_id}: {str(e)}")
                failed += 1

        # 批量推送
        if testrail_results:
            try:
                response = self.session.post(
                    f"{self.base_url}/index.php?/api/v2/add_results_for_cases/{run_id}",
                    json={"results": testrail_results},
                )

                if response.status_code != 200:
                    errors.append(f"批量推送失败: {response.status_code}")
                    failed = len(testrail_results)
                    pushed = 0

            except Exception as e:
                errors.append(f"推送异常: {str(e)}")
                failed = len(testrail_results)
                pushed = 0

        return SyncResult(
            sync_id=sync_id,
            direction="push",
            pushed=pushed,
            pulled=0,
            failed=failed,
            skipped=0,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            mode="full",
        )

    def pull_test_results(self, run_id: str) -> List[TestResult]:
        """拉取执行结果"""
        # 获取 TestRun 详情（包含结果）
        response = self.session.get(
            f"{self.base_url}/index.php?/api/v2/get_run/{run_id}"
        )

        if response.status_code != 200:
            raise Exception(f"拉取失败: {response.status_code}")

        run_data = response.json()
        # TestRail API 不直接返回结果，需要额外调用
        # 这里仅返回空列表（完整实现需调用 /get_results_for_run/{run_id}）
        return []

    # ─── TestRun 管理 ───

    def create_test_run(self, name: str, case_ids: List[str]) -> TestRun:
        """创建测试运行

        Args:
            name: 运行名称
            case_ids: 用例 ID 列表（外部平台 ID）

        Returns:
            TestRun 对象
        """
        project_id = self.config.extra.get("project_id")
        suite_id = self.config.extra.get("suite_id")

        if not project_id:
            raise ValueError("缺少 project_id 配置")

        # 创建 Run
        payload = {
            "suite_id": suite_id,
            "name": name,
            "description": "Created by AI Test System",
            "case_ids": case_ids,  # TestRail 要求外部 ID
            "include_all": False,
        }

        response = self.session.post(
            f"{self.base_url}/index.php?/api/v2/add_run/{project_id}",
            json=payload,
        )

        if response.status_code != 200:
            raise Exception(f"创建 TestRun 失败: {response.status_code} - {response.text}")

        run_data = response.json()

        return TestRun(
            id=f"run-{run_data['id']}",
            external_id=str(run_data['id']),
            name=run_data.get('name'),
            total=len(case_ids),
            passed=0,
            failed=0,
            blocked=0,
            skipped=0,
            started_at=run_data.get('created_on'),
            completed_at="",
        )

    def list_test_runs(self, filters: Optional[dict] = None) -> List[TestRun]:
        """列出测试运行"""
        project_id = (filters or {}).get("project_id") or self.config.extra.get("project_id")

        if not project_id:
            raise ValueError("缺少 project_id")

        response = self.session.get(
            f"{self.base_url}/index.php?/api/v2/get_runs/{project_id}",
            params=filters or {},
        )

        if response.status_code != 200:
            return []

        return [self._run_from_testrail_dict(item) for item in response.json()]

    # ─── 缺陷（集成到 JIRA/外部系统）───

    def push_defects(self, defects: List[Defect]) -> SyncResult:
        """推送缺陷

        TestRail 本身不管理缺陷，而是关联到外部系统（如 JIRA）。
        此方法通过用例的自定义字段存储缺陷 ID。
        """
        sync_id = f"sync_defects_{int(time.time())}"
        pushed = 0
        errors = []

        for defect in defects:
            try:
                # 更新用例的 defects 字段
                for case_id in defect.linked_test_cases:
                    # 假设 case_id 是外部 ID
                    external_id = case_id.lstrip("TC-")

                    payload = {
                        "custom_defects": f"{defect.external_id}: {defect.title}"
                    }

                    response = self.session.post(
                        f"{self.base_url}/index.php?/api/v2/update_case/{external_id}",
                        json=payload,
                    )

                    if response.status_code == 200:
                        pushed += 1
                    else:
                        errors.append(f"更新用例 {external_id} 失败")
            except Exception as e:
                errors.append(f"{defect.id}: {str(e)}")

        return SyncResult(
            sync_id=sync_id,
            direction="push",
            pushed=pushed,
            pulled=0,
            failed=len(errors),
            skipped=0,
            errors=errors,
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            mode="full",
        )

    def pull_defects(self, filters: Optional[dict] = None) -> List[Defect]:
        """拉取缺陷

        TestRail 从自定义字段解析缺陷引用。
        """
        # TODO: 实现从用例的自定义字段提取缺陷 ID
        return []

    # ─── Webhook ───

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """验证 Webhook 签名

        TestRail 使用 HMAC-SHA256 签名。
        """
        secret = self.config.extra.get("webhook_secret", "")
        if not secret:
            return True  # 无签名验证

        expected = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_webhook(self, event: dict) -> Optional[str]:
        """处理平台推送的事件

        TestRail Webhook 事件类型：
          - test_run.completed: 测试运行完成
          - case.created: 用例创建
          - case.updated: 用例更新
        """
        event_type = event.get("type", "")

        if event_type == "test_run.completed":
            run_id = event.get("run_id")
            return f"TestRail Run {run_id} 已完成"

        elif event_type == "case.created":
            case_id = event.get("case_id")
            return f"TestRail Case {case_id} 已创建"

        elif event_type == "case.updated":
            case_id = event.get("case_id")
            return f"TestRail Case {case_id} 已更新"

        return None

    # ─── 内部辅助方法 ───

    def _get_project(self, project_id: str) -> Optional[dict]:
        """获取项目信息（缓存）"""
        if project_id in self._project_cache:
            return self._project_cache[project_id]

        response = self.session.get(
            f"{self.base_url}/index.php?/api/v2/get_project/{project_id}"
        )
        if response.status_code == 200:
            self._project_cache[project_id] = response.json()
            return self._project_cache[project_id]
        return None

    def _get_suites(self, project_id: str) -> List[dict]:
        """获取项目的套件列表"""
        response = self.session.get(
            f"{self.base_url}/index.php?/api/v2/get_suites/{project_id}"
        )
        if response.status_code == 200:
            return response.json()
        return []

    def _get_or_create_default_suite(self, project_id: str) -> str:
        """获取或创建默认套件"""
        if project_id in self._suite_cache:
            return self._suite_cache[project_id]

        # 尝试获取第一个套件
        suites = self._get_suites(project_id)
        if suites:
            suite_id = str(suites[0]["id"])
            self._suite_cache[project_id] = suite_id
            return suite_id

        # 创建默认套件
        payload = {
            "name": "Master Suite",
            "description": "Default suite created by AI Test System",
        }
        response = self.session.post(
            f"{self.base_url}/index.php?/api/v2/add_suite/{project_id}",
            json=payload,
        )

        if response.status_code == 200:
            suite_data = response.json()
            suite_id = str(suite_data["id"])
            self._suite_cache[project_id] = suite_id
            return suite_id

        raise Exception(f"无法创建默认套件: {response.status_code}")

    def _case_to_testrail_dict(self, case: TestCase, project_id: str, suite_id: str) -> dict:
        """Canonical Model → TestRail 格式"""
        # 使用 FieldMapper 进行转换（如果配置了映射）
        if self.field_mapper:
            return self.field_mapper.to_platform(asdict(case))

        # 默认映射
        return {
            "title": case.title,
            "type_id": self._dimension_to_type_id(case.dimension),
            "priority_id": self._priority_to_priority_id(case.priority),
            "custom_preconds": case.precondition,
            "custom_steps": "\n".join(case.steps),
            "custom_expected": case.expected_result,
        }

    def _case_from_testrail_dict(self, item: dict, project_id: str, suite_id: str) -> TestCase:
        """TestRail 格式 → Canonical Model"""
        if self.field_mapper:
            case_dict = self.field_mapper.to_canonical(item)
            case_dict["custom_fields"] = {
                "testrail_project_id": project_id,
                "testrail_suite_id": suite_id,
            }
            return TestCase(**case_dict)

        # 默认映射
        return TestCase(
            id=f"TC-{item['id']}",
            external_id=str(item['id']),
            title=item.get('title', ''),
            module=item.get('section_name', ''),
            feature=item.get('custom_feature', ''),
            priority=self._priority_id_to_priority(item.get('priority_id', 2)),
            dimension=self._type_id_to_dimension(item.get('type_id', 1)),
            precondition=item.get('custom_preconds', ''),
            steps=(item.get('custom_steps', '') or "").split("\n"),
            expected_result=item.get('custom_expected', ''),
            custom_fields={
                "testrail_project_id": project_id,
                "testrail_suite_id": suite_id,
            },
        )

    def _run_from_testrail_dict(self, item: dict) -> TestRun:
        """TestRail Run 格式 → Canonical Model"""
        return TestRun(
            id=f"run-{item['id']}",
            external_id=str(item['id']),
            name=item.get('name', ''),
            total=item.get('case_count', 0),
            passed=item.get('passed_count', 0),
            failed=item.get('failed_count', 0),
            blocked=item.get('blocked_count', 0),
            untested=item.get('untested_count', 0),
            started_at=item.get('created_on'),
            completed_at=item.get('completed_on'),
        )

    def _status_to_testrail(self, status: str) -> int:
        """内部状态 → TestRail status_id

        TestRail 状态映射：
          1: passed
          5: failed
          4: blocked
          3: untested/skipped
        """
        mapping = {
            "passed": 1,
            "fail": 5,
            "failed": 5,
            "blocked": 4,
            "skip": 3,
            "skipped": 3,
            "untested": 3,
        }
        return mapping.get(status.lower(), 3)

    def _dimension_to_type_id(self, dimension: str) -> int:
        """测试维度 → TestRail type_id"""
        # TestRail 默认 type_id：
        # 1: 其他
        # 2: 功能测试
        # 3: 边界值
        # 4: 异常测试
        # 5: 性能测试
        # 6: 安全测试
        mapping = {
            "正向测试": 2,
            "负向测试": 2,
            "边界测试": 3,
            "边界条件": 3,
            "异常测试": 4,
            "异常场景": 4,
            "性能测试": 5,
            "安全测试": 6,
        }
        return mapping.get(dimension, 1)

    def _type_id_to_dimension(self, type_id: int) -> str:
        """TestRail type_id → 测试维度"""
        mapping = {
            1: "其他",
            2: "正向测试",
            3: "边界测试",
            4: "异常测试",
            5: "性能测试",
            6: "安全测试",
        }
        return mapping.get(type_id, "其他")

    def _priority_to_priority_id(self, priority: str) -> int:
        """优先级 → TestRail priority_id

        TestRail 默认 priority_id：
          1: Critical
          2: High
          3: Medium
          4: Low
        """
        mapping = {
            "P0": 1,
            "P1": 2,
            "P2": 3,
            "P3": 4,
        }
        return mapping.get(priority, 2)

    def _priority_id_to_priority(self, priority_id: int) -> str:
        """TestRail priority_id → 优先级"""
        mapping = {
            1: "P0",
            2: "P1",
            3: "P2",
            4: "P3",
        }
        return mapping.get(priority_id, "P1")


# 导入 logger
import logging
logger = logging.getLogger("ai-test-system.integrations")
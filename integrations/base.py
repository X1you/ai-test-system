#!/usr/bin/env python3
"""
BaseAdapter — 所有测试管理平台适配器的抽象基类

子类必须实现所有 @abstractmethod 方法。
非抽象方法提供默认实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from integrations.models import TestCase, TestResult, TestRun, Defect, SyncResult


@dataclass
class AdapterConfig:
    """适配器配置"""
    platform: str
    base_url: str = ""
    api_key: str = ""
    username: str = ""                             # Basic Auth / XML-RPC 用户名
    password: str = ""                             # Basic Auth / XML-RPC 密码
    project_id: str = ""                           # 项目 ID
    field_mapping_path: str = ""                   # YAML 映射配置路径
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """适配器抽象基类"""

    platform_name: str = "base"
    supported_transports: List[str] = []           # ["rest", "xmlrpc", "soap"]

    def __init__(self, config: AdapterConfig):
        self.config = config
        self.field_mapper = None                   # 由 SyncEngine 注入

    # ─── 认证 ───

    @abstractmethod
    def authenticate(self) -> bool:
        """认证并建立连接。返回是否成功。"""

    # ─── 测试用例 CRUD ───

    @abstractmethod
    def push_test_cases(self, cases: List[TestCase]) -> SyncResult:
        """推送用例到外部平台（创建或更新）"""

    @abstractmethod
    def pull_test_cases(self, filters: Optional[dict] = None) -> List[TestCase]:
        """从外部平台拉取用例"""

    # ─── 测试结果 ───

    @abstractmethod
    def push_test_results(self, run_id: str,
                          results: List[TestResult]) -> SyncResult:
        """推送执行结果到指定 TestRun"""

    @abstractmethod
    def pull_test_results(self, run_id: str) -> List[TestResult]:
        """从指定 TestRun 拉取执行结果"""

    # ─── TestRun 管理（可选实现）───

    def create_test_run(self, name: str,
                        case_ids: List[str]) -> TestRun:
        raise NotImplementedError(f"{self.platform_name} 不支持创建 TestRun")

    def list_test_runs(self, filters: Optional[dict] = None) -> List[TestRun]:
        raise NotImplementedError(f"{self.platform_name} 不支持列出 TestRun")

    # ─── 缺陷（可选实现）───

    def push_defects(self, defects: List[Defect]) -> SyncResult:
        raise NotImplementedError(f"{self.platform_name} 不支持推送缺陷")

    def pull_defects(self, filters: Optional[dict] = None) -> List[Defect]:
        raise NotImplementedError(f"{self.platform_name} 不支持拉取缺陷")

    # ─── Webhook ───

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """验证 Webhook 签名（子类可覆盖）

        默认实现：无签名验证（返回 True）。
        """
        return True

    def handle_webhook(self, event: dict) -> Optional[str]:
        """处理平台推送的事件

        子类可覆盖以实现事件驱动同步。
        返回值：处理结果消息，或 None 表示未处理。
        """
        return None

    # ─── 健康检查 ───

    def health_check(self) -> bool:
        """连接健康检查"""
        try:
            return self.authenticate()
        except Exception:
            return False

    # ─── 元数据 ───

    def get_platform_info(self) -> dict:
        """平台信息"""
        return {
            "platform": self.platform_name,
            "transports": self.supported_transports,
        }

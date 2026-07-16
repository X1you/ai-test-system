# 集成适配器扩展指南

本文档说明如何为 AI 测试用例生成系统扩展新的测试管理平台集成。

---

## 概述

系统集成层采用**插件化适配器架构**，支持快速添加新的测试管理平台（TestRail、TestLink、JIRA、Zephyr 等）。

核心组件：
```
integrations/
├── base.py              # BaseAdapter 抽象类
├── registry.py          # 适配器注册表
├── models.py            # Canonical Model（内部标准数据模型）
├── field_mapper.py      # 字段映射引擎
├── service.py           # 集成服务（RESTful API + 同步引擎）
└── adapters/
    ├── testrail.py      # TestRail 适配器（示例）
    └── __init__.py
```

---

## 快速开始：添加新平台适配器

### 步骤 1：创建适配器类

在 `integrations/adapters/` 下创建新文件，例如 `myplatform.py`：

```python
#!/usr/bin/env python3
"""
MyPlatform 适配器示例

支持：REST API + OAuth2
"""

import requests
from typing import List, Optional

from integrations.base import BaseAdapter, AdapterConfig
from integrations.models import TestCase, TestResult, SyncResult, TestRun, Defect
from integrations.registry import AdapterRegistry


@AdapterRegistry.register("myplatform")
class MyPlatformAdapter(BaseAdapter):
    """MyPlatform 适配器"""

    platform_name = "myplatform"
    supported_transports = ["rest"]

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ─── 认证 ───

    def authenticate(self) -> bool:
        """认证并建立连接"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/me")
            return response.status_code == 200
        except Exception:
            return False

    # ─── 用例 CRUD ───

    def push_test_cases(self, cases: List[TestCase]) -> SyncResult:
        """推送用例（创建或更新）"""
        sync_id = f"sync_{self.platform_name}_{int(time.time())}"
        started_at = datetime.now().isoformat()
        pushed = 0
        errors = []

        for case in cases:
            try:
                # 检查是否已存在
                existing = self._find_case_by_external_id(case.external_id)
                if existing:
                    # 更新
                    self.session.put(
                        f"{self.base_url}/api/v1/cases/{existing['id']}",
                        json=self._case_to_platform_dict(case),
                    )
                else:
                    # 创建
                    self.session.post(
                        f"{self.base_url}/api/v1/cases",
                        json=self._case_to_platform_dict(case),
                    )
                pushed += 1
            except Exception as e:
                errors.append(f"{case.id}: {str(e)}")

        return SyncResult(
            sync_id=sync_id,
            direction="push",
            pushed=pushed,
            pulled=0,
            failed=len(errors),
            skipped=0,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
            mode="full",
        )

    def pull_test_cases(self, filters: Optional[dict] = None) -> List[TestCase]:
        """拉取用例"""
        params = filters or {}
        response = self.session.get(f"{self.base_url}/api/v1/cases", params=params)
        if response.status_code != 200:
            raise Exception(f"拉取失败: {response.text}")

        return [self._case_from_platform_dict(item) for item in response.json()["data"]]

    # ─── 测试结果 ───

    def push_test_results(self, run_id: str, results: List[TestResult]) -> SyncResult:
        """推送执行结果"""
        sync_id = f"sync_{self.platform_name}_{int(time.time())}"
        pushed = 0
        errors = []

        for result in results:
            try:
                self.session.post(
                    f"{self.base_url}/api/v1/runs/{run_id}/results",
                    json=self._result_to_platform_dict(result),
                )
                pushed += 1
            except Exception as e:
                errors.append(f"{result.test_case_id}: {str(e)}")

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

    def pull_test_results(self, run_id: str) -> List[TestResult]:
        """拉取执行结果"""
        response = self.session.get(f"{self.base_url}/api/v1/runs/{run_id}/results")
        if response.status_code != 200:
            raise Exception(f"拉取失败: {response.text}")

        return [self._result_from_platform_dict(item) for item in response.json()["data"]]

    # ─── TestRun 管理（可选）───

    def create_test_run(self, name: str, case_ids: List[str]) -> TestRun:
        """创建测试运行"""
        # 1. 创建 Run
        response = self.session.post(
            f"{self.base_url}/api/v1/runs",
            json={"name": name, "case_ids": case_ids},
        )
        run_data = response.json()

        return TestRun(
            id=f"run-{run_data['id']}",
            external_id=str(run_data['id']),
            name=run_data['name'],
            total=len(case_ids),
            passed=0,
            failed=0,
            blocked=0,
            skipped=0,
            started_at=datetime.now().isoformat(),
            completed_at="",
        )

    def list_test_runs(self, filters: Optional[dict] = None) -> List[TestRun]:
        """列出测试运行"""
        params = filters or {}
        response = self.session.get(f"{self.base_url}/api/v1/runs", params=params)
        if response.status_code != 200:
            return []

        return [self._run_from_platform_dict(item) for item in response.json()["data"]]

    # ─── 缺陷（可选）───

    def push_defects(self, defects: List[Defect]) -> SyncResult:
        """推送缺陷"""
        # TODO: 实现
        raise NotImplementedError("MyPlatform 不支持推送缺陷")

    def pull_defects(self, filters: Optional[dict] = None) -> List[Defect]:
        """拉取缺陷"""
        # TODO: 实现
        raise NotImplementedError("MyPlatform 不支持拉取缺陷")

    # ─── Webhook ───

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """验证 Webhook 签名"""
        # MyPlatform 使用 HMAC-SHA256 签名
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
        """处理平台推送的事件"""
        event_type = event.get("type")
        if event_type == "test_run.completed":
            # 处理测试运行完成事件
            return f"TestRun {event.get('run_id')} 已完成"
        elif event_type == "defect.created":
            # 处理缺陷创建事件
            return f"Defect {event.get('defect_id')} 已创建"
        return None

    # ─── 内部辅助方法 ───

    def _find_case_by_external_id(self, external_id: str) -> Optional[dict]:
        """根据外部 ID 查找用例"""
        response = self.session.get(
            f"{self.base_url}/api/v1/cases",
            params={"external_id": external_id}
        )
        if response.status_code == 200:
            data = response.json()["data"]
            return data[0] if data else None
        return None

    def _case_to_platform_dict(self, case: TestCase) -> dict:
        """Canonical Model → 平台格式"""
        # 使用 FieldMapper 进行转换（如果配置了映射）
        if self.field_mapper:
            return self.field_mapper.to_platform(asdict(case))

        # 默认映射
        return {
            "title": case.title,
            "section": case.module,
            "feature": case.feature,
            "priority": case.priority,
            "type": case.dimension,
            "preconditions": case.precondition,
            "steps": "\n".join(case.steps),
            "expected_result": case.expected_result,
            "custom_severity": case.custom_fields.get("severity"),
        }

    def _case_from_platform_dict(self, item: dict) -> TestCase:
        """平台格式 → Canonical Model"""
        if self.field_mapper:
            case_dict = self.field_mapper.to_canonical(item)
            return TestCase(**case_dict)

        # 默认映射
        return TestCase(
            id=item.get("id", ""),
            external_id=item.get("external_id", ""),
            title=item.get("title", ""),
            module=item.get("section", ""),
            feature=item.get("feature", ""),
            priority=item.get("priority", ""),
            dimension=item.get("type", ""),
            precondition=item.get("preconditions", ""),
            steps=(item.get("steps", "") or "").split("\n"),
            expected_result=item.get("expected_result", ""),
            custom_fields={
                "severity": item.get("custom_severity"),
            },
        )

    def _result_to_platform_dict(self, result: TestResult) -> dict:
        """Canonical Model → 平台结果格式"""
        return {
            "case_id": result.test_case_id,
            "status": result.status,
            "comment": result.comment,
            "duration": result.duration,
            "executed_by": result.executed_by,
            "executed_at": result.executed_at,
        }

    def _result_from_platform_dict(self, item: dict) -> TestResult:
        """平台结果格式 → Canonical Model"""
        return TestResult(
            test_case_id=item.get("case_id", ""),
            external_id=item.get("id", ""),
            status=item.get("status", ""),
            comment=item.get("comment", ""),
            duration=item.get("duration", 0),
            executed_by=item.get("executed_by", ""),
            executed_at=item.get("executed_at", ""),
        )

    def _run_from_platform_dict(self, item: dict) -> TestRun:
        """平台运行格式 → Canonical Model"""
        return TestRun(
            id=f"run-{item['id']}",
            external_id=str(item['id']),
            name=item.get("name", ""),
            total=item.get("total", 0),
            passed=item.get("passed", 0),
            failed=item.get("failed", 0),
            blocked=item.get("blocked", 0),
            skipped=item.get("skipped", 0),
            started_at=item.get("started_at", ""),
            completed_at=item.get("completed_at", ""),
        )
```

### 步骤 2：创建字段映射配置（可选）

如果平台的字段名称与 Canonical Model 不同，创建 YAML 映射配置：

```yaml
# integrations/mappings/myplatform.yaml
field_mapping:
  title:
    field: name
  module:
    field: section
  feature:
    field: feature
  priority:
    field: severity
    transform: priority_map
  dimension:
    field: type
  steps:
    field: custom_steps
    transform: join
    transform_options:
      separator: "\n"

transforms:
  priority_map:
    P0: 1
    P1: 2
    P2: 3
    P3: 4
```

### 步骤 3：配置环境变量

在 `.env` 或环境变量中配置平台连接信息：

```bash
# MyPlatform 配置
INTEGRATION_MYPLATFORM_BASE_URL=https://myplatform.example.com
INTEGRATION_MYPLATFORM_API_KEY=your_api_key_here
INTEGRATION_MYPLATFORM_FIELD_MAPPING=integrations/mappings/myplatform.yaml
```

### 步骤 4：测试适配器

使用集成服务 API 或测试客户端验证：

```bash
# 列出平台
curl http://localhost:8080/api/v1/integrations/platforms

# 验证配置
curl -X POST http://localhost:8080/api/v1/integrations/validate-config \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "myplatform",
    "base_url": "https://myplatform.example.com",
    "auth_type": "api_key",
    "api_key": "your_api_key_here"
  }'

# 推送用例
curl -X POST http://localhost:8080/api/v1/integrations/test-cases/push \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "myplatform",
    "incremental": false,
    "cases": [
      {
        "id": "TC-001",
        "title": "测试标题",
        "module": "用户模块",
        "feature": "登录",
        "priority": "P0",
        "dimension": "正向测试",
        "steps": ["步骤1", "步骤2"],
        "expected_result": "成功"
      }
    ]
  }'
```

---

## API 端点

### 1. 列出已注册平台

```
GET /api/v1/integrations/platforms
```

响应：
```json
{
  "platforms": ["testrail", "myplatform", "jira"]
}
```

---

### 2. 验证平台配置

```
POST /api/v1/integrations/validate-config
```

请求体：
```json
{
  "platform": "myplatform",
  "base_url": "https://myplatform.example.com",
  "auth_type": "api_key",
  "api_key": "your_api_key_here"
}
```

响应：
```json
{
  "status": "ok",
  "message": "myplatform 连接成功"
}
```

---

### 3. 推送测试用例

```
POST /api/v1/integrations/test-cases/push
```

请求体：
```json
{
  "platform": "myplatform",
  "incremental": false,
  "last_sync": "2026-07-16T00:00:00",
  "cases": [
    {
      "id": "TC-001",
      "title": "测试标题",
      "module": "用户模块",
      "feature": "登录",
      "priority": "P0",
      "dimension": "正向测试",
      "steps": ["步骤1", "步骤2"],
      "expected_result": "成功",
      "custom_fields": {
        "severity": 1
      }
    }
  ]
}
```

响应：
```json
{
  "success_count": 1,
  "success_ids": ["TC-001"],
  "errors": {},
  "log": [
    {
      "sync_id": "sync_123",
      "ts": "2026-07-16T10:00:00",
      "platform": "myplatform",
      "direction": "push",
      "entity_type": "test_case",
      "entity_id": "TC-001",
      "external_id": "EXT-001",
      "action": "create",
      "status": "ok",
      "error": "",
      "detail": ""
    }
  ]
}
```

---

### 4. 拉取测试用例

```
GET /api/v1/integrations/test-cases/pull?platform=myplatform&incremental=false
```

响应：
```json
{
  "success_count": 10,
  "success_ids": ["TC-001", "TC-002"],
  "errors": {},
  "cases": [
    {
      "id": "TC-001",
      "title": "测试标题",
      ...
    }
  ],
  "log": [...]
}
```

---

### 5. 推送测试结果

```
POST /api/v1/integrations/test-results/push?platform=myplatform&run_id=run-123
```

请求体：
```json
{
  "results": [
    {
      "test_case_id": "TC-001",
      "status": "passed",
      "comment": "测试通过",
      "duration": 1.5,
      "executed_by": "user@example.com",
      "executed_at": "2026-07-16T10:00:00"
    }
  ]
}
```

响应：
```json
{
  "success_count": 1,
  "success_ids": ["TC-001"],
  "errors": {},
  "log": [...]
}
```

---

## Canonical Model

所有外部平台数据先转换为内部标准模型（Canonical Model），再进行流转。

```python
@dataclass
class TestCase:
    id: str                                          # 内部唯一 ID
    external_id: str = ""                            # 外部平台 ID
    title: str = ""
    module: str = ""                                 # 模块
    feature: str = ""                                # 功能点
    priority: str = ""                               # P0/P1/P2
    dimension: str = ""                              # 正向/负向/边界/异常/性能/安全
    precondition: str = ""
    steps: List[str] = field(default_factory=list)
    test_data: str = ""
    expected_result: str = ""
    actual_result: str = ""
    status: str = ""                                 # passed/failed/blocked/skipped/pending
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)
```

---

## 同步策略

### 全量同步

- 推送/拉取所有用例
- 适用于首次同步或重建同步

### 增量同步

- 仅同步更新时间 > `last_sync` 的用例
- 需平台支持时间戳过滤

---

## 认证方式

系统支持以下认证方式：

1. **API Key**
   ```bash
   INTEGRATION_MYPLATFORM_API_KEY=your_key
   ```

2. **OAuth2**（GitHub、Google）
   - 配置 `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`
   - 调用 `/api/v1/auth/oauth/authorize` 获取授权 URL
   - 回调后调用 `/api/v1/auth/oauth/callback` 交换令牌

3. **Basic Auth**
   ```bash
   INTEGRATION_MYPLATFORM_USERNAME=user
   INTEGRATION_MYPLATFORM_PASSWORD=pass
   ```

4. **企业 SSO**（SAML/OIDC）
   - 占位实现，需根据企业 SSO 提供商扩展

---

## 测试

```bash
# 运行集成测试
pytest tests/test_integrations_service.py -v
```

---

## 扩展点

### 1. 添加新认证方式

继承 `BaseAdapter` 并覆盖 `authenticate()` 方法：

```python
def authenticate(self) -> bool:
    # 实现 OAuth2/SAML/LDAP 认证
    pass
```

### 2. 自定义 Webhook 处理

覆盖 `handle_webhook()` 方法：

```python
def handle_webhook(self, event: dict) -> Optional[str]:
    event_type = event.get("type")
    if event_type == "custom_event":
        # 处理自定义事件
        return "Event handled"
    return None
```

### 3. 支持额外数据类型

扩展 `models.py` 添加新的数据模型（如 `TestSuite`、`TestEnvironment`）。

---

## 故障排查

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 适配器未注册 | 确保使用 `@AdapterRegistry.register()` 装饰器 |
| 字段映射不生效 | 检查 `field_mapping_path` 是否正确 |
| 认证失败 | 检查 API Key/OAuth2 凭据是否正确 |
| 增量同步无效果 | 确认平台支持时间戳过滤 |

---

## 参考实现

- **TestRail 适配器**: `integrations/adapters/testrail.py`
- **集成服务**: `integrations/service.py`
- **字段映射**: `integrations/field_mapper.py`

---

## 文档更新

添加新平台后，请更新以下文档：
- `README.md`（添加平台列表）
- `docs/requirements.md`（添加平台支持说明）
- `tests/test_integrations_service.py`（添加测试用例）

---

**最后更新**: 2026-07-16
**维护者**: AI Test System Team
"""integrations — 集成适配层

零侵入核心引擎，插件化接入任意测试管理平台。

模块结构：
  - models:        Canonical Model（内部标准数据模型）
  - base:          BaseAdapter 抽象基类 + AdapterConfig
  - registry:      AdapterRegistry 插件注册表
  - field_mapper:  FieldMapper 字段映射引擎
  - bridge:        IntegrationBridge Excel ↔ Canonical 转换
  - service:       IntegrationService 服务层 + RESTful API
  - adapters/:     各平台适配器实现（testrail, ...）
  - mappings/:     YAML 字段映射配置
"""

__all__ = [
    "AdapterConfig",
    "BaseAdapter",
    "TestCase",
    "TestResult",
    "TestRun",
    "Defect",
    "SyncResult",
    "IntegrationBridge",
    "IntegrationService",
    "SyncEngine",
    "AuthManager",
    "AdapterRegistry",
    "FieldMapper",
]

"""端到端 API 测试套件 — 全链路用户旅程。

覆盖：
  - 认证旅程（login → me → 失效 token → 锁定）
  - Provider 生命周期（CRUD + test + set_default + batch + reorder）
  - 健康检查 + 用量统计旅程

特性：
  - 使用 FastAPI TestClient（进程内，快速）
  - backup_config fixture 保护 config.yaml 不被污染
  - LLM 调用全程 mock（不依赖外部服务）
"""

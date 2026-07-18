"""
顶层 pytest 配置。

注册自定义 markers，避免 pytest 警告 "unknown mark"。

marker 约定：
  - @pytest.mark.slow: 真实调用 LLM API / 完整 Pipeline / 大 Vault 遍历的端到端测试。
    执行时间长（单测数秒~分钟级），日常 `pytest` 默认跳过（见 pyproject.toml 的
    `-m "not slow"`），需手动 `pytest -m slow` 触发。
  - @pytest.mark.integration: 需要外部服务（数据库、Web 服务、Obsidian 等）的集成测试。

使用方式：
  - 文件级标记：在测试文件顶部写 `pytestmark = pytest.mark.slow`
  - 类/函数级标记：在 TestClass 或 test_func 上加 `@pytest.mark.slow`
"""

import pytest

# 这些目录下的测试属于端到端套件，整体打 slow 标记
# （真实调用 LLM/Pipeline/Web/KB，执行时间长，日常默认跳过）
_SLOW_DIRS = {
    "tests/ai_agent_suite",      # 完整 Pipeline e2e + Web API e2e
    "tests/integration",          # 外部服务集成测试
}


def pytest_configure(config):
    """注册自定义 markers（消除 pytest "unknown mark" 警告）。"""
    config.addinivalue_line(
        "markers",
        "slow: 真实调用 LLM/完整 Pipeline/大 Vault 的端到端测试，日常默认跳过。"
        "用 `pytest -m slow` 单独触发。",
    )
    config.addinivalue_line(
        "markers",
        "integration: 需要外部服务（DB/Web/Obsidian）的集成测试。",
    )


def pytest_collection_modifyitems(config, items):
    """收集后给 _SLOW_DIRS 下的测试自动打 slow 标记。

    比在每个测试文件写 pytestmark 更集中、更不易遗漏。
    单个测试若想脱离目录默认行为，可显式 @pytest.mark.slow 覆盖。
    """
    for item in items:
        # item.fspath 是测试文件的绝对路径
        fspath = str(item.fspath).replace("\\", "/")
        for slow_dir in _SLOW_DIRS:
            if f"/{slow_dir}/" in fspath:
                item.add_marker(pytest.mark.slow)
                break


@pytest.fixture(scope="function")
def client():
    """创建已自动登录（JWT）的测试客户端"""
    from fastapi.testclient import TestClient

    from web.app import app
    from web.services.user_service import create_admin_if_not_exists

    try:
        create_admin_if_not_exists("testuser", "TestPass123!")
    except Exception:
        pass

    client = TestClient(app)
    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPass123!"},
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token", "")
        client.headers["Authorization"] = f"Bearer {token}"
    return client

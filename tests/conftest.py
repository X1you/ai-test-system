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

# ─── 测试环境 JWT 密钥（必须在 web.app 导入前设置）───
# app.py 在模块导入时通过 _load_dotenv 加载 .env 的 JWT_SECRET，
# 但测试用的 token 必须用固定的测试密钥签名才能通过 verify_token。
# 因此在 conftest 导入阶段（早于任何 web.app 引用）强制覆盖为测试密钥。
# 注意：这是测试环境的唯一例外，生产环境绝不这样做。
import os as _os

_TEST_JWT_SECRET = "test-only-secret-for-pytest-fixture-32chars"
_os.environ["JWT_SECRET"] = _TEST_JWT_SECRET

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
    """创建测试客户端 — 自动注入有效 JWT（现有测试零改动）。

    所有现有测试无需逐个加 token：此 fixture 在 TestClient 上设置默认
    Authorization: Bearer header，让请求自动通过 verify_token。
    token 用测试专用密钥签名，保证通过 verify_token 校验。
    """
    from fastapi.testclient import TestClient

    from web.app import app

    # 测试专用 JWT（用固定 secret 签名，与 verify_token 配合）
    token = _make_test_token()
    tc = TestClient(app)
    tc.headers.update({"Authorization": f"Bearer {token}"})
    return tc


@pytest.fixture(scope="function")
def unauthenticated_client():
    """创建不带认证的测试客户端（用于安全测试：验证 401/403）。

    安全测试（test_security.py）用这个 fixture 访问受保护端点，
    断言返回 401 Unauthorized。
    """
    from fastapi.testclient import TestClient

    from web.app import app

    return TestClient(app)


# ─── 测试用 JWT 生成 ───


def _make_test_token() -> str:
    """签发测试用 JWT（用模块级设置的 _TEST_JWT_SECRET 签名，admin 角色）。

    JWT_SECRET 已在 conftest 导入时设为 _TEST_JWT_SECRET，
    因此 web.middleware.auth.get_jwt_secret() 返回同一密钥。
    """
    from web.middleware.auth import create_token

    return create_token(user_id=0, username="test-admin", role="admin")

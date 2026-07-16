#!/usr/bin/env python3
"""JWT 认证中间件单元测试

验证 web.middleware.auth：
  - create_token() 生成的 Token 为非空字符串
  - Token 解码后的 payload 包含 sub / username / role / exp / iat
"""

import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保可直接 import 项目模块
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_create_token():
    """测试 Token 生成"""
    os.environ["AI_TEST_ENV"] = "test"
    from web.middleware.auth import create_token

    token = create_token(1, "testuser", "admin")
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_token_structure():
    """Token 应包含正确的 payload"""
    os.environ["AI_TEST_ENV"] = "test"
    from jose import jwt

    from web.middleware.auth import ALGORITHM, SECRET_KEY, create_token

    token = create_token(1, "testuser", "admin")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "1"
    assert payload["username"] == "testuser"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload

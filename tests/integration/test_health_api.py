#!/usr/bin/env python3
"""健康检查 API 集成测试

通过 FastAPI TestClient 验证 /health 端点：
  - 返回 200（全部就绪）或 503（部分降级）
  - 响应体包含 version 与 checks 字段
  - checks 中 api 组件状态为 ok
"""

import os
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，确保可直接 import 项目模块
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def client():
    """创建测试客户端"""
    os.environ["AI_TEST_ENV"] = "test"
    from fastapi.testclient import TestClient

    from web.app import app

    return TestClient(app)


def test_health_returns_200(client):
    """健康检查应返回 200 或 503"""
    resp = client.get("/health")
    assert resp.status_code in (200, 503)


def test_health_has_version(client):
    """健康检查应包含版本信息"""
    resp = client.get("/health")
    data = resp.json()
    assert "version" in data
    assert "checks" in data


def test_health_checks_structure(client):
    """健康检查应包含各组件状态"""
    resp = client.get("/health")
    data = resp.json()
    checks = data["checks"]
    assert "api" in checks
    assert checks["api"] == "ok"

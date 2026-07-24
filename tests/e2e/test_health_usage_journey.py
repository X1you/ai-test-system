#!/usr/bin/env python3
"""健康检查 + 用量统计 e2e 旅程。

覆盖：
  - /health/live → 200 alive（不检查依赖）
  - /health/ready → 200 ok 或 503 degraded（含 version + checks）
  - /health → 向后兼容
  - /api/v1/usage/llm → 聚合统计结构
  - /api/v1/usage/reset → 清空并返回快照
  - 健康端点豁免认证
  - 未匹配路由 404
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestHealthJourney:
    """健康检查探针旅程。"""

    def test_liveness_returns_alive(self, unauthenticated_client):
        """/health/live → 200 status=alive。"""
        resp = unauthenticated_client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_readiness_returns_status_and_version(self, unauthenticated_client):
        """/health/ready → 含 status + version + checks。"""
        resp = unauthenticated_client.get("/health/ready")
        # 200（ok）或 503（degraded），都算正常响应
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "version" in data
        assert "checks" in data
        # checks 含 db/llm/kb
        checks = data["checks"]
        assert "db" in checks or "llm" in checks

    def test_health_backward_compatible(self, unauthenticated_client):
        """/health 等价于 /health/ready。"""
        resp = unauthenticated_client.get("/health")
        assert resp.status_code in (200, 503)
        assert "status" in resp.json()

    def test_health_endpoints_no_auth(self, unauthenticated_client):
        """健康端点不要求 JWT。"""
        for path in ["/health/live", "/health/ready"]:
            resp = unauthenticated_client.get(path)
            assert resp.status_code != 401

    def test_readiness_reflects_llm_status(self, unauthenticated_client, seed_providers):
        """readiness 的 checks 应反映 LLM provider 状态。"""
        resp = unauthenticated_client.get("/health/ready")
        data = resp.json()
        # LLM 检查项应存在（配置了 provider 后）
        checks = data.get("checks", {})
        assert "llm" in checks


class TestUsageJourney:
    """LLM 用量统计旅程。"""

    def test_get_llm_usage_structure(self, client):
        """GET /usage/llm 返回聚合统计结构。"""
        resp = client.get("/api/v1/usage/llm")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "started_at" in data
        assert "uptime_seconds" in data
        assert "totals" in data
        assert "providers" in data
        totals = data["totals"]
        for key in ("calls", "success", "errors", "tokens", "success_rate"):
            assert key in totals

    def test_reset_usage_returns_snapshot(self, client):
        """POST /usage/reset 清空并返回清空前快照。"""
        # 先取一次
        before = client.get("/api/v1/usage/llm").json()
        # reset
        resp = client.post("/api/v1/usage/reset")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["ok"] is True
        assert "before" in data
        # reset 后 totals 应归零
        after = client.get("/api/v1/usage/llm").json()
        assert after["totals"]["calls"] == 0
        assert after["totals"]["tokens"] == 0

    def test_usage_requires_auth(self, unauthenticated_client):
        """usage 端点要求认证。"""
        resp = unauthenticated_client.get("/api/v1/usage/llm")
        assert resp.status_code == 401


class TestRoutingBoundary:
    """路由边界与 404。"""

    def test_unknown_api_path_returns_404(self, client):
        """未知 API 路径 → 404 JSON。"""
        resp = client.get("/api/v1/nonexistent-endpoint")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data or "detail" in data

    def test_unknown_root_path_returns_404(self, unauthenticated_client):
        """未知根路径 → 404。"""
        resp = unauthenticated_client.get("/some-random-page")
        assert resp.status_code == 404

    def test_root_returns_system_info(self, unauthenticated_client):
        """根路径 / 返回系统元信息（API 模式）。"""
        resp = unauthenticated_client.get("/")
        # 根路径返回系统信息或 404（取决于前端是否构建），不应是 500
        assert resp.status_code in (200, 404)

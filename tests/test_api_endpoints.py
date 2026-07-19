#!/usr/bin/env python3
"""
其他 API 端点测试 — Config API、Knowledge API、Webhooks

测试范围：
  - Config API：配置查看、API Key 脱敏
  - Knowledge API：状态查询、搜索
  - Webhooks API：平台验证、签名验证
  - 健康检查端点
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("LLM_API_KEY", "«redacted:sk-…»")


class TestHealthEndpoint:
    """健康检查"""

    def test_health_returns_200(self, client):
        """健康检查返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "checks" in data

    def test_health_has_api_check(self, client):
        """健康检查包含 API 状态"""
        resp = client.get("/health")
        data = resp.json()
        assert data["checks"]["api"] == "ok"

    def test_health_has_database_check(self, client):
        """健康检查包含数据库状态"""
        resp = client.get("/health")
        data = resp.json()
        assert "database" in data["checks"]

    def test_health_has_llm_check(self, client):
        """健康检查包含 LLM 状态"""
        resp = client.get("/health")
        data = resp.json()
        assert "llm" in data["checks"]

    def test_health_has_kb_check(self, client):
        """健康检查包含知识库状态"""
        resp = client.get("/health")
        data = resp.json()
        assert "knowledge_base" in data["checks"]

    def test_health_response_format(self, client):
        """健康检查响应格式正确"""
        resp = client.get("/health")
        data = resp.json()
        assert data["version"] == "2.0.0"
        assert data["status"] in ("ok", "degraded")


class TestConfigAPI:
    """配置 API"""

    def test_config_endpoint(self, client):
        """配置端点可访问"""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "knowledge_base" in data
        assert "pipeline" in data
        assert "validation" in data

    def test_api_key_masked(self, client):
        """API Key 被脱敏"""
        resp = client.get("/api/v1/config")
        data = resp.json()
        api_key = data["llm"]["api_key"]
        # 脱敏后包含 "..."
        if api_key != "未配置" and len(api_key) > 8:
            assert "..." in api_key or api_key == "***"

    def test_config_has_validation(self, client):
        """配置包含校验结果"""
        resp = client.get("/api/v1/config")
        data = resp.json()
        assert "validation" in data
        assert "valid" in data["validation"]
        assert "errors" in data["validation"]

    def test_config_has_pipeline_settings(self, client):
        """配置包含 Pipeline 设置"""
        resp = client.get("/api/v1/config")
        data = resp.json()
        pipeline = data["pipeline"]
        assert "default_mode" in pipeline
        assert "default_dimensions" in pipeline
        assert "default_formats" in pipeline
        assert "self_check" in pipeline


class TestKnowledgeAPI:
    """知识库 API"""

    def test_kb_status_endpoint(self, client):
        """知识库状态端点可访问"""
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200
        data = resp.json()
        # 可能返回 enabled 或 source 字段
        assert "enabled" in data or "source" in data or "total" in data

    def test_kb_search_requires_query(self, client):
        """搜索需要查询参数"""
        resp = client.get("/api/v1/knowledge/search")
        # 缺少 q 参数应返回 422（FastAPI 参数校验）
        assert resp.status_code == 422

    def test_kb_search_with_query(self, client):
        """带查询参数的搜索"""
        resp = client.get("/api/v1/knowledge/search?q=用户登录")
        # 可能返回 200（知识库未启用但有正确响应）
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "results" in data

    def test_kb_search_empty_query(self, client):
        """空查询字符串"""
        resp = client.get("/api/v1/knowledge/search?q=")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "query" in data


class TestWebhooksAPI:
    """Webhooks API"""

    def test_webhook_unknown_platform(self, client):
        """未知平台返回 404"""
        resp = client.post("/api/v1/webhooks/unknown_platform")
        assert resp.status_code == 404

    def test_webhook_missing_signature(self, client):
        """缺少签名 — 可能被接受或拒绝"""
        resp = client.post("/api/v1/webhooks/testrail", json={"event": "test"})
        # webhook 端点可能返回 200（接受）、401（签名验证失败）、404（平台未配置）
        assert resp.status_code in (200, 401, 404, 422, 500)

    def test_webhook_no_body(self, client):
        """空请求体"""
        resp = client.post("/api/v1/webhooks/testrail")
        # 缺少 JSON body
        assert resp.status_code in (400, 404, 422)


class TestPageRoutes:
    """页面路由测试（Sprint 6.1: 全部改为 JSON）"""

    def test_index_page(self, client):
        """首页：前端已构建时返回 SPA HTML，未构建时返回 JSON 元信息"""
        resp = client.get("/")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct or "application/json" in ct
        if "application/json" in ct:
            data = resp.json()
            assert "name" in data

    def test_login_page_removed(self, client):
        """登录页已移除（Sprint 6.0 切除 Auth）→ SPA fallback"""
        resp = client.get("/login")
        assert resp.status_code == 200
        # SPA fallback: Vue 构建后返回 text/html，未构建返回 JSON
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct or "application/json" in ct

    def test_knowledge_page_spa_fallback(self, client):
        """知识库页 → SPA fallback"""
        resp = client.get("/knowledge")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct or "application/json" in ct

    def test_pipelines_page_spa_fallback(self, client):
        """Pipeline 列表页 → SPA fallback"""
        resp = client.get("/pipelines")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/html" in ct or "application/json" in ct

    def test_pipeline_page_spa_fallback(self, client):
        """Pipeline 详情页 → SPA fallback"""
        resp = client.get("/pipeline/nonexistent-12345")
        assert resp.status_code == 200

    def test_results_page_spa_fallback(self, client):
        """结果页 → SPA fallback"""
        resp = client.get("/results/nonexistent-12345")
        assert resp.status_code == 200


class TestAPIContentType:
    """API 响应 Content-Type"""

    def test_api_returns_json(self, client):
        """API 端点返回 JSON"""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    def test_page_returns_json_or_spa(self, client):
        """页面返回 JSON（未构建）或 SPA HTML（已构建）"""
        resp = client.get("/")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct or "text/html" in ct


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

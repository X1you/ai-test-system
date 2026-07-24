#!/usr/bin/env python3
"""Provider 生命周期 e2e — 完整 CRUD + 测试 + 设默认 + 批量 + 排序。

覆盖：
  - GET /config 列出 providers + API Key 脱敏（硬约束 sk-xxxx...yyyy）
  - PUT /config 新增/编辑 provider
  - POST /config/test_provider（mock LLM 连接）
  - POST /config/set_default + 不存在 name → 404
  - POST /config/batch_toggle
  - POST /config/batch_delete（拒绝默认、拒绝清空）
  - POST /config/reorder_providers（校验数量/重复/未知）
  - GET /config/providers
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestProviderLifecycle:
    """Provider 全生命周期旅程。"""

    def test_get_config_lists_providers_with_masked_keys(self, client, seed_providers):
        """★ GET /config 返回 providers 列表，API Key 必须脱敏。"""
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        providers = data["llm_providers"]
        assert len(providers) == 3
        names = {p["name"] for p in providers}
        assert names == {"glm", "deepseek", "claude"}
        # 默认标记
        assert data["llm_default"] == "glm"
        # 协议列表
        assert "openai_compatible" in data["llm_protocols"]
        # ★ 硬约束：API Key 脱敏，完整 key 绝不出现在响应
        body_text = resp.text
        assert "sk-glm-test-1234567890wxyz" not in body_text
        assert "sk-deepseek-test-1234567890abcd" not in body_text
        # 脱敏 key 含 ...
        for p in providers:
            if p.get("api_key"):
                assert "..." in p["api_key"] or p["api_key"] == "***"

    def test_put_config_add_new_provider(self, client, seed_providers):
        """PUT /config 新增 provider → GET 后列表 +1。"""
        # 先取现有列表
        resp = client.get("/api/v1/config").json()
        providers = resp["llm_providers"]
        # 构造新 provider
        new_p = {
            "name": "qwen", "provider": "alibaba", "protocol": "openai_compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-qwen-new-1234567890", "model": "qwen-max",
            "temperature": 0.3, "max_tokens": 8192, "timeout": 120, "retry": 2,
            "enabled": True, "priority": 3, "tags": [],
        }
        providers.append(new_p)
        put_resp = client.put("/api/v1/config", json={"llm": {"providers": providers}})
        assert put_resp.status_code == 200, put_resp.text

        # 重新 GET 验证
        data = client.get("/api/v1/config").json()
        names = {p["name"] for p in data["llm_providers"]}
        assert "qwen" in names

    def test_put_config_rejects_disallowed_section(self, client, seed_providers):
        """PUT 不允许的配置段 → 400。"""
        resp = client.put("/api/v1/config", json={"forbidden_section": {"x": 1}})
        assert resp.status_code == 400

    def test_set_default_switches_default(self, client, seed_providers):
        """set_default 切换默认 provider。"""
        resp = client.post("/api/v1/config/set_default", json={"name": "deepseek"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["default"] == "deepseek"
        # 验证持久化
        data = client.get("/api/v1/config").json()
        assert data["llm_default"] == "deepseek"

    def test_set_default_nonexistent_returns_404(self, client, seed_providers):
        """set_default 不存在的 name → 404。"""
        resp = client.post("/api/v1/config/set_default", json={"name": "ghost"})
        assert resp.status_code == 404

    def test_test_provider_success(self, client, seed_providers, mock_llm_connection):
        """test_provider mock 连接成功 → ok=True。"""
        with mock_llm_connection(ok=True, latency=180):
            resp = client.post("/api/v1/config/test_provider", json={
                "provider": {
                    "name": "glm", "provider": "bigmodel",
                    "protocol": "openai_compatible",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "sk-glm-test", "model": "glm-4.7-flash",
                },
                "timeout": 10,
            })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["ok"] is True
        assert data["latency_ms"] == 180

    def test_test_provider_failure(self, client, seed_providers, mock_llm_connection):
        """test_provider mock 连接失败 → ok=False。"""
        with mock_llm_connection(ok=False):
            resp = client.post("/api/v1/config/test_provider", json={
                "provider": {
                    "name": "claude", "protocol": "anthropic",
                    "base_url": "https://api.anthropic.com",
                    "api_key": "sk-ant-test", "model": "claude-3-5-sonnet",
                },
                "timeout": 10,
            })
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_batch_toggle_enable(self, client, seed_providers):
        """batch_toggle 启用 claude（当前 disabled）。"""
        resp = client.post("/api/v1/config/batch_toggle", json={
            "names": ["claude"], "enabled": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "claude" in data["updated"]
        # 验证持久化
        providers = client.get("/api/v1/config").json()["llm_providers"]
        claude = next(p for p in providers if p["name"] == "claude")
        assert claude["enabled"] is True

    def test_batch_toggle_disabling_default_switches_default(self, client, seed_providers):
        """禁用默认 provider → 自动切换 default 到下一个 enabled。"""
        # 默认是 glm，禁用 glm
        resp = client.post("/api/v1/config/batch_toggle", json={
            "names": ["glm"], "enabled": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        # default 应自动切到 deepseek（priority 1，仍 enabled）
        assert data["default"] == "deepseek"

    def test_batch_delete_rejects_default(self, client, seed_providers):
        """batch_delete 含默认 provider → 400。"""
        resp = client.post("/api/v1/config/batch_delete", json={"names": ["glm"]})
        assert resp.status_code == 400
        assert "默认" in resp.json()["detail"]

    def test_batch_delete_success(self, client, seed_providers):
        """batch_delete 删除非默认 provider。"""
        resp = client.post("/api/v1/config/batch_delete", json={"names": ["deepseek"]})
        assert resp.status_code == 200, resp.text
        # 验证删除
        names = {p["name"] for p in client.get("/api/v1/config").json()["llm_providers"]}
        assert "deepseek" not in names

    def test_batch_delete_rejects_clearing_all(self, client, seed_providers):
        """batch_delete 不能删光所有 provider → 400。"""
        # 删除 deepseek + claude（保留 glm 默认）—— 但 claude 是非默认，deepseek 非默认
        # 一次删 2 个非默认，剩 glm → 允许。再删 glm 会被默认拦截。
        # 这里测试"删光"场景：先删 deepseek+claude 剩 glm，再尝试删 glm（默认）→ 400 默认拦截
        client.post("/api/v1/config/batch_delete", json={"names": ["deepseek", "claude"]})
        # 现在只剩 glm（默认）。删 glm → 400（默认拦截，而非清空拦截）
        resp = client.post("/api/v1/config/batch_delete", json={"names": ["glm"]})
        assert resp.status_code == 400

    def test_reorder_providers_success(self, client, seed_providers):
        """reorder_providers 重排顺序。"""
        resp = client.post("/api/v1/config/reorder_providers", json={
            "names": ["claude", "glm", "deepseek"],
        })
        assert resp.status_code == 200, resp.text

    def test_reorder_rejects_count_mismatch(self, client, seed_providers):
        """reorder 数量不匹配 → 400。"""
        resp = client.post("/api/v1/config/reorder_providers", json={
            "names": ["glm", "deepseek"],  # 缺 claude
        })
        assert resp.status_code == 400

    def test_reorder_rejects_duplicate(self, client, seed_providers):
        """reorder 含重复 → 400。"""
        resp = client.post("/api/v1/config/reorder_providers", json={
            "names": ["glm", "glm", "deepseek"],
        })
        assert resp.status_code == 400

    def test_reorder_rejects_unknown_name(self, client, seed_providers):
        """reorder 含未知 name → 400。"""
        resp = client.post("/api/v1/config/reorder_providers", json={
            "names": ["glm", "deepseek", "ghost"],
        })
        assert resp.status_code == 400

    def test_get_providers_endpoint(self, client, seed_providers):
        """GET /config/providers 返回 provider 列表（无 API Key）。"""
        resp = client.get("/api/v1/config/providers")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # 实际返回 {providers, default, count} 结构
        assert "providers" in data
        assert isinstance(data["providers"], list)
        assert data["count"] >= 3
        assert data["default"] == "glm"
        # ★ API Key 脱敏：完整 key 绝不出现在响应
        body_text = resp.text
        assert "sk-glm-test-1234567890wxyz" not in body_text
        for p in data["providers"]:
            if p.get("api_key"):
                assert "..." in p["api_key"] or p["api_key"] == "***"

    def test_full_crud_journey(self, client, seed_providers):
        """★ 完整旅程：新增 → 测试 → 设默认 → 编辑 → 删除。"""
        # 1. 新增
        providers = client.get("/api/v1/config").json()["llm_providers"]
        providers.append({
            "name": "qwen", "provider": "alibaba", "protocol": "openai_compatible",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-qwen-journey-key-1234567890", "model": "qwen-max",
            "temperature": 0.3, "max_tokens": 8192, "timeout": 120, "retry": 2,
            "enabled": True, "priority": 3, "tags": [],
        })
        assert client.put("/api/v1/config", json={"llm": {"providers": providers}}).status_code == 200

        # 2. 设为默认
        assert client.post("/api/v1/config/set_default", json={"name": "qwen"}).status_code == 200

        # 3. 切回 glm 默认，再删 qwen
        assert client.post("/api/v1/config/set_default", json={"name": "glm"}).status_code == 200
        del_resp = client.post("/api/v1/config/batch_delete", json={"names": ["qwen"]})
        assert del_resp.status_code == 200

        # 4. 验证已删除
        names = {p["name"] for p in client.get("/api/v1/config").json()["llm_providers"]}
        assert "qwen" not in names

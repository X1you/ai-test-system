#!/usr/bin/env python3
"""
web/api/webhooks.py 单元测试。

目标：将 webhook 接收端点覆盖率提升到 90%+。
覆盖：全局 HMAC 签名验证（无密钥拒绝/签名错误拒绝/正确签名通过）、
适配器获取（未知平台 404/加载异常 500）、适配器级签名验证失败、
无效 JSON、正常处理成功。
"""

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_WEBHOOK_SECRET = "test-webhook-secret"


def _sign(body: bytes) -> str:
    """用测试密钥计算 HMAC-SHA256 签名。"""
    return hmac.new(
        TEST_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()


# ═══════════════════════════════════════════════════════════════
# _verify_global_signature 纯函数测试
# ═══════════════════════════════════════════════════════════════


class TestVerifyGlobalSignature:
    """测试全局 HMAC 签名验证函数。"""

    def test_no_secret_rejects_all(self):
        """未配置 WEBHOOK_SECRET 时拒绝所有请求（安全默认）。"""
        from web.api.webhooks import _verify_global_signature

        with patch.dict(os.environ, {"WEBHOOK_SECRET": ""}, clear=False):
            # 即使签名正确，无密钥也拒绝
            body = b'{"type": "test"}'
            sig = _sign(body)
            assert _verify_global_signature(body, sig) is False

    def test_wrong_signature_rejected(self):
        """错误签名被拒绝。"""
        from web.api.webhooks import _verify_global_signature

        body = b'{"type": "test"}'
        assert _verify_global_signature(body, "deadbeef" * 8) is False

    def test_correct_signature_accepted(self):
        """正确签名通过验证。"""
        from web.api.webhooks import _verify_global_signature

        body = b'{"type": "test"}'
        assert _verify_global_signature(body, _sign(body)) is True


# ═══════════════════════════════════════════════════════════════
# POST /api/v1/webhooks/{platform} 端点测试
# ═══════════════════════════════════════════════════════════════


class TestReceiveWebhook:
    """测试 webhook 接收端点的完整流程。"""

    def test_webhook_no_secret_returns_401(self, unauthenticated_client):
        """WEBHOOK_SECRET 未配置 → 401（所有 webhook 被拒绝）。"""
        body = b'{"type": "test"}'
        with patch.dict(os.environ, {"WEBHOOK_SECRET": ""}, clear=False):
            resp = unauthenticated_client.post(
                "/api/v1/webhooks/testrail",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 401

    def test_webhook_wrong_signature_returns_401(self, unauthenticated_client):
        """签名错误 → 401。"""
        body = b'{"type": "test"}'
        resp = unauthenticated_client.post(
            "/api/v1/webhooks/testrail",
            content=body,
            headers={"X-Webhook-Signature": "wrong-sig",
                     "Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_webhook_unknown_platform_returns_404(self, unauthenticated_client):
        """签名正确但平台未注册 → 404。"""
        body = b'{"type": "test"}'
        resp = unauthenticated_client.post(
            "/api/v1/webhooks/unknown_platform_xyz",
            content=body,
            headers={"X-Webhook-Signature": _sign(body),
                     "Content-Type": "application/json"},
        )
        assert resp.status_code == 404

    def test_webhook_adapter_load_exception_returns_500(self, unauthenticated_client):
        """适配器加载抛非 ValueError 异常 → 500。"""
        body = b'{"type": "test"}'
        with patch("integrations.registry.AdapterRegistry.get_adapter",
                   side_effect=RuntimeError("init failed")):
            resp = unauthenticated_client.post(
                "/api/v1/webhooks/testrail",
                content=body,
                headers={"X-Webhook-Signature": _sign(body),
                         "Content-Type": "application/json"},
            )
        assert resp.status_code == 500

    def test_webhook_adapter_signature_fail_returns_401(self, unauthenticated_client):
        """适配器级签名验证失败 → 401。"""
        body = b'{"type": "test"}'
        mock_adapter = MagicMock()
        mock_adapter.verify_signature.return_value = False
        with patch("integrations.registry.AdapterRegistry.get_adapter",
                   return_value=mock_adapter):
            resp = unauthenticated_client.post(
                "/api/v1/webhooks/testrail",
                content=body,
                headers={"X-Webhook-Signature": _sign(body),
                         "Content-Type": "application/json"},
            )
        assert resp.status_code == 401

    def test_webhook_invalid_json_returns_400(self, unauthenticated_client):
        """签名通过但 JSON 无效 → 400。"""
        body = b'not-json'
        mock_adapter = MagicMock()
        mock_adapter.verify_signature.return_value = True
        with patch("integrations.registry.AdapterRegistry.get_adapter",
                   return_value=mock_adapter):
            resp = unauthenticated_client.post(
                "/api/v1/webhooks/testrail",
                content=body,
                headers={"X-Webhook-Signature": _sign(body),
                         "Content-Type": "application/json"},
            )
        assert resp.status_code == 400

    def test_webhook_success(self, unauthenticated_client):
        """完整成功流程：签名通过 + 适配器处理 → 200。"""
        event = {"type": "test_run.completed", "run_id": "R123"}
        body = json.dumps(event).encode()
        mock_adapter = MagicMock()
        mock_adapter.verify_signature.return_value = True
        mock_adapter.handle_webhook.return_value = "processed"
        with patch("integrations.registry.AdapterRegistry.get_adapter",
                   return_value=mock_adapter):
            resp = unauthenticated_client.post(
                "/api/v1/webhooks/testrail",
                content=body,
                headers={"X-Webhook-Signature": _sign(body),
                         "Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["result"] == "processed"
        mock_adapter.handle_webhook.assert_called_once_with(event)

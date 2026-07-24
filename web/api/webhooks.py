#!/usr/bin/env python3
"""
Webhook Receiver — 接收外部测试管理平台的事件推送

路由:
  GET  /api/v1/webhooks         — 查看 webhook 状态与已注册平台
  POST /api/v1/webhooks/{platform} — 接收外部平台事件推送

安全：双层签名验证
  1. 全局 HMAC-SHA256 验证（WEBHOOK_SECRET 环境变量，所有 webhook 必须携带）
  2. 适配器级签名验证（各平台自定义，可选）
"""

import hashlib
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from integrations.base import AdapterConfig
from integrations.registry import AdapterRegistry
from web.middleware.auth import verify_token

router = APIRouter(tags=["webhooks"])


def _verify_global_signature(body: bytes, signature: str) -> bool:
    """全局 HMAC-SHA256 签名验证。

    使用 WEBHOOK_SECRET 环境变量作为预共享密钥。
    签名格式：HMAC-SHA256(WEBHOOK_SECRET, body) 的 hex digest。
    未配置 WEBHOOK_SECRET 时拒绝所有 webhook（安全默认）。
    """
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        # 未配置密钥 → 拒绝所有 webhook（安全默认，不静默放行）
        return False
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@router.post("/{platform}")
async def receive_webhook(platform: str, request: Request):
    """接收外部平台推送的事件

    1. 全局 HMAC 签名验证（WEBHOOK_SECRET）
    2. 获取平台对应的适配器
    3. 适配器级签名验证（各平台不同，可选）
    4. 解析事件并处理
    """
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    # 1. 全局 HMAC 签名验证（所有 webhook 必须通过）
    if not _verify_global_signature(body, signature):
        raise HTTPException(401, "Webhook 签名验证失败")

    # 2. 注册表中获取适配器类（不创建实例，用配置兜底）
    try:
        config = AdapterConfig(platform=platform)
        adapter = AdapterRegistry.get_adapter(platform, config)
    except ValueError:
        raise HTTPException(404, f"未知平台: {platform}")
    except Exception as e:
        raise HTTPException(500, f"加载适配器失败: {e}")

    # 3. 适配器级签名验证（如果适配器配置了 api_key）
    if not adapter.verify_signature(body, signature):
        raise HTTPException(401, "签名验证失败")

    # 4. 解析事件（复用已读取的 body，避免重复 await request.json()）
    try:
        import json

        event = json.loads(body)
    except Exception:
        raise HTTPException(400, "无效的 JSON 请求体")

    # 5. 处理事件
    result = adapter.handle_webhook(event)

    return {"status": "ok", "result": result}


@router.get("", dependencies=[Depends(verify_token)])
async def get_webhook_status():
    """查看 webhook 配置状态与已注册平台。

    返回：
      - secret_configured: WEBHOOK_SECRET 是否已配置
      - platforms: 已注册的适配器平台列表
      - webhook_url_template: 外部平台应推送到的 URL 模板
    """
    secret_configured = bool(os.environ.get("WEBHOOK_SECRET", ""))
    try:
        platforms = AdapterRegistry.list_platforms()
    except Exception:
        platforms = []

    return {
        "secret_configured": secret_configured,
        "platforms": platforms,
        "webhook_url_template": "/api/v1/webhooks/{platform}",
    }

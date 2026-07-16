#!/usr/bin/env python3
"""
Webhook Receiver — 接收外部测试管理平台的事件推送

路由: POST /api/webhooks/{platform}
"""

from fastapi import APIRouter, HTTPException, Request

from integrations.base import AdapterConfig
from integrations.registry import AdapterRegistry

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/{platform}")
async def receive_webhook(platform: str, request: Request):
    """接收外部平台推送的事件

    1. 获取平台对应的适配器
    2. 验证签名（各平台不同）
    3. 解析事件并处理
    """
    # 1. 注册表中获取适配器类（不创建实例，用配置兜底）
    try:
        config = AdapterConfig(platform=platform)
        adapter = AdapterRegistry.get_adapter(platform, config)
    except ValueError:
        raise HTTPException(404, f"未知平台: {platform}")
    except Exception as e:
        raise HTTPException(500, f"加载适配器失败: {e}")

    # 2. 验证签名（如果适配器配置了 api_key）
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    if not adapter.verify_signature(body, signature):
        raise HTTPException(401, "签名验证失败")

    # 3. 解析事件
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(400, "无效的 JSON 请求体")

    # 4. 处理事件
    result = adapter.handle_webhook(event)

    return {"status": "ok", "result": result}

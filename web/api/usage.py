#!/usr/bin/env python3
"""
用量统计 API 路由 — LLM 调用仪表盘数据源

Endpoints:
  GET   /usage/llm      — 获取 LLM 调用聚合统计（按 provider 维度）
  POST  /usage/reset    — 清空统计（返回清空前快照，便于审计）

设计：
  - 统计为进程级内存聚合（core.llm_usage.usage_stats 单例）
  - 重启后清空，无持久化（MVP 阶段）
  - 读操作无副作用，可高频访问
"""

from fastapi import APIRouter

from core.llm_usage import usage_stats

router = APIRouter(tags=["usage"])


@router.get("/llm")
async def get_llm_usage():
    """获取 LLM 调用量聚合统计。

    返回结构：
      {
        "started_at": float,         # 统计开始时间（unix timestamp）
        "uptime_seconds": float,     # 已运行时长
        "totals": {
          "calls": int, "success": int, "errors": int,
          "tokens": int, "success_rate": float
        },
        "providers": {
          "<provider_name>": {
            "calls": int, "success": int, "errors": int,
            "tokens": int,
            "latency_ms_avg": float, "latency_ms_max": float,
            "success_rate": float,
            "last_call_at": float, "last_error": str,
            "by_model": { "<model>": {...} }
          }
        }
      }
    """
    return usage_stats.snapshot()


@router.post("/reset")
async def reset_usage():
    """清空所有 LLM 用量统计。

    返回清空前的快照（便于审计/回溯）。
    重置后 started_at 更新为当前时间。
    """
    before = usage_stats.reset()
    return {
        "ok": True,
        "message": "用量统计已清空",
        "before": before,
    }

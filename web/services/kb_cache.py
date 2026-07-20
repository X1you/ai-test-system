"""
知识库缓存服务（Sprint 6.1：统一 DB 数据源）。

历史问题（已修复）：
  原 kb_cache 读 config.yaml（静态），而 /current_config / /update_config 走 DB（动态），
  导致 UI「生效配置」和「知识库统计」两个卡片数据源不一致——用户改了配置后统计卡
  仍指向旧 vault，甚至因 status 返回缺 enabled 字段而误报「知识库未启用」。

修复：status / search 统一走 DynamicKBManager（DB 数据源），与 /current_config 同源。

两层优化：
  1. 复用 DynamicKBManager 单例的 client（DB 热切换后 reload 重建，无需 fork 子进程）
  2. 结果缓存：status 缓存 60s（数据变化不频繁），search 按 query 缓存 30s

缓存失效：
  - import/add 写入操作后自动清空缓存（调用 invalidate_*）
  - /update_config 热切换后调用 invalidate_all()（由路由层负责）

容错：
  - DynamicKBManager 未配置（Dummy 模式）时返回 enabled=False 的降级结果
  - 不影响 Web 服务启动
"""

import threading
import time
from collections import OrderedDict

# 缓存 TTL（秒）
STATUS_TTL = 60      # status 数据变化不频繁
SEARCH_TTL = 30      # search 按 query 缓存

# search 缓存条目上限（防止高频不同 query 导致内存无限增长）
SEARCH_CACHE_MAX = 128

# 缓存存储：(timestamp, data)
_status_cache: tuple[float, dict | None] = (0, None)
_search_cache: OrderedDict[str, tuple[float, list]] = OrderedDict()
_cache_lock = threading.Lock()


def _get_manager():
    """获取 DynamicKBManager 单例（DB 数据源）。

    返回的 manager.get_client() 在 reload() 后会自动替换为新 client。
    """
    from core.kb.dynamic_kb_manager import get_dynamic_kb_manager
    return get_dynamic_kb_manager()


def get_kb_manager():
    """向后兼容入口（原签名保留）。

    返回 DynamicKBManager 底层的 client；未配置时返回 None。
    """
    m = _get_manager()
    if m.is_configured():
        return m.get_client()
    return None


def _status_from_client(client) -> dict:
    """调用 client.status() 并补齐 enabled 字段。

    MCPClient.status() 原始返回不含 enabled，导致前端 v-if="!status.enabled"
    误判为「知识库未启用」。这里统一注入 enabled=True。
    """
    result = client.status()
    if isinstance(result, dict):
        result.setdefault("enabled", True)
    return result


def get_status() -> dict:
    """获取知识库统计（带 60s 缓存，DB 数据源）。

    未配置（Dummy 模式）时返回 enabled=False 的降级结果。
    """
    global _status_cache

    now = time.time()
    with _cache_lock:
        ts, data = _status_cache
        if data is not None and (now - ts) < STATUS_TTL:
            return data

    m = _get_manager()
    if not m.is_configured():
        # DB 无 active 配置 → Dummy 模式
        result = {"enabled": False, "total": 0, "categories": {}, "message": "知识库未配置（Dummy 模式）"}
        with _cache_lock:
            _status_cache = (now, result)
        return result

    client = m.get_client()
    try:
        result = _status_from_client(client)
        with _cache_lock:
            _status_cache = (now, result)
        return result
    except Exception as e:
        return {"enabled": True, "error": str(e)[:200], "total": 0, "categories": {}}


def search(query: str, limit: int = 20) -> list[dict]:
    """搜索知识库（按 query 缓存 30s，DB 数据源）。

    未配置（Dummy 模式）时返回空列表。
    """
    now = time.time()
    cache_key = f"{query}:{limit}"

    with _cache_lock:
        entry = _search_cache.get(cache_key)
        if entry is not None:
            ts, data = entry
            if (now - ts) < SEARCH_TTL:
                _search_cache.move_to_end(cache_key)  # LRU: 标记为最近使用
                return data

    m = _get_manager()
    if not m.is_configured():
        return []

    client = m.get_client()
    try:
        results = client.search(query, limit=limit) or []
        with _cache_lock:
            _search_cache[cache_key] = (now, results)
            _search_cache.move_to_end(cache_key)
            # LRU 淘汰：超出上限移除最旧条目
            while len(_search_cache) > SEARCH_CACHE_MAX:
                _search_cache.popitem(last=False)
        return results
    except Exception:
        return []


# ─── 缓存失效（写入操作 / 热切换后调用）───


def invalidate_status():
    """清除 status 缓存（import/add/update_config 后调用）。"""
    global _status_cache
    with _cache_lock:
        _status_cache = (0, None)


def invalidate_search():
    """清除所有 search 缓存（import/add/update_config 后调用）。"""
    with _cache_lock:
        _search_cache.clear()


def invalidate_all():
    """清除全部缓存（import/add/update_config 后调用）。"""
    invalidate_status()
    invalidate_search()

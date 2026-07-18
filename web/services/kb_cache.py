"""
知识库缓存服务。

解决 P3-C 性能问题：每次 KB API 请求都 subprocess.run fork 子进程跑
kb_manager_mcp.py，Python 冷启动 + Vault 全量遍历 = 6-7 秒。

两层优化：
  1. 模块级单例：复用 KnowledgeBaseManager 实例，避免每次 fork 子进程
  2. 结果缓存：status 缓存 60s（数据变化不频繁），search 按 query 缓存 30s

缓存失效：
  - import/add 写入操作后自动清空缓存（调用 invalidate_*）
  - vault_path 配置变化时单例自动重建

容错：
  - 单例初始化失败（vault 不存在等）返回 None，路由层优雅降级
  - 不影响 Web 服务启动
"""

import threading
import time

from core.config_loader import load_config

# 缓存 TTL（秒）
STATUS_TTL = 60      # status 数据变化不频繁
SEARCH_TTL = 30      # search 按 query 缓存

# 单例 + 缓存（线程安全）
_kb_instance = None
_kb_lock = threading.Lock()
_kb_vault_path = None  # 记录当前单例对应的 vault_path，变化时重建

# 缓存存储：(timestamp, data)
_status_cache: tuple[float, dict | None] = (0, None)
_search_cache: dict[str, tuple[float, list]] = {}
_cache_lock = threading.Lock()


def get_kb_manager():
    """获取 KnowledgeBaseManager 单例（vault_path 变化时自动重建）。

    Returns:
        KnowledgeBaseManager 实例，初始化失败返回 None。
    """
    global _kb_instance, _kb_vault_path

    config = load_config()
    kb_config = config.get("knowledge_base", {})

    if not kb_config.get("enabled", False):
        return None

    vault_path = kb_config.get("vault_path", "")
    if not vault_path:
        return None

    # vault_path 变化或首次调用 → 加锁重建
    if _kb_instance is None or _kb_vault_path != vault_path:
        with _kb_lock:
            # double-check（可能其他线程已经建好了）
            if _kb_instance is None or _kb_vault_path != vault_path:
                try:
                    from core.kb.kb_manager_mcp import KnowledgeBaseManager

                    _kb_instance = KnowledgeBaseManager(vault_path=vault_path)
                    _kb_vault_path = vault_path
                except Exception:
                    # 初始化失败（vault 不存在等），保持 None，下次重试
                    _kb_instance = None

    return _kb_instance


def get_status() -> dict:
    """获取知识库统计（带 60s 缓存）。

    单例不可用时回退到原始的 subprocess 方式（向后兼容）。
    """
    global _status_cache

    now = time.time()
    with _cache_lock:
        ts, data = _status_cache
        if data is not None and (now - ts) < STATUS_TTL:
            return data

    # 缓存未命中或过期 → 实际查询
    mgr = get_kb_manager()
    if mgr is not None:
        try:
            result = mgr.status()
            with _cache_lock:
                _status_cache = (now, result)
            return result
        except Exception as e:
            return {"enabled": True, "error": str(e), "total": 0}

    # 单例不可用 → 回退 subprocess（保留原行为）
    return _status_via_subprocess()


def search(query: str, limit: int = 20) -> list[dict]:
    """搜索知识库（按 query 缓存 30s）。

    单例不可用时回退到原始的 subprocess 方式。
    """
    now = time.time()
    cache_key = f"{query}:{limit}"

    with _cache_lock:
        ts, data = _search_cache.get(cache_key, (0, None))
        if data is not None and (now - ts) < SEARCH_TTL:
            return data

    mgr = get_kb_manager()
    if mgr is not None:
        try:
            results = mgr.search(query, limit=limit)
            with _cache_lock:
                _search_cache[cache_key] = (now, results)
            return results
        except Exception:
            return []

    # 单例不可用 → 回退 subprocess
    return _search_via_subprocess(query, limit)


# ─── 缓存失效（写入操作后调用）───


def invalidate_status():
    """清除 status 缓存（import/add 后调用）。"""
    global _status_cache
    with _cache_lock:
        _status_cache = (0, None)


def invalidate_search():
    """清除所有 search 缓存（import/add 后调用）。"""
    with _cache_lock:
        _search_cache.clear()


def invalidate_all():
    """清除全部缓存（import/add 后调用）。"""
    invalidate_status()
    invalidate_search()


# ─── 向后兼容：subprocess 回退路径 ───


def _status_via_subprocess() -> dict:
    """单例不可用时的 subprocess 回退（保留原有行为）。"""
    import subprocess
    import sys
    from pathlib import Path

    kb_script = Path(__file__).resolve().parents[2] / "core" / "kb" / "kb_manager_mcp.py"
    if not kb_script.exists():
        return {"enabled": True, "error": "知识库脚本不存在", "total": 0}
    try:
        result = subprocess.run(
            [sys.executable, str(kb_script), "status"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
        return {"enabled": True, "error": result.stderr[:200]}
    except Exception as e:
        return {"enabled": True, "error": str(e)}


def _search_via_subprocess(query: str, limit: int = 20) -> list[dict]:
    """单例不可用时的 subprocess 回退。"""
    import subprocess
    import sys
    from pathlib import Path

    kb_script = Path(__file__).resolve().parents[2] / "core" / "kb" / "kb_manager_mcp.py"
    if not kb_script.exists():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(kb_script), "search", query],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)[:limit]
        return []
    except Exception:
        return []

#!/usr/bin/env python3
"""
core/llm_cache.py 单元测试。

LLMCache 是幂等 Prompt 结果缓存层，覆盖以下路径：
  - _make_key: temperature>0 不缓存（返回空 key）
  - get/set 内存缓存命中
  - TTL 过期失效
  - LRU 淘汰（超 maxsize）
  - SQLite 持久化后端
  - clear 清空
  - stats 统计（命中率）

纯内存逻辑 + sqlite（stdlib），无外部依赖，测试用 tmp_path 隔离 db。
"""

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


class TestMakeKey:
    """测试缓存 Key 生成"""

    def test_temp_zero_generates_key(self):
        from core.llm_cache import LLMCache

        cache = LLMCache()
        key = cache._make_key("glm", "sys", "hello", 0)
        assert key  # 非空
        assert len(key) == 64  # sha256 hexdigest

    def test_temp_nonzero_no_cache(self):
        """temperature > 0 返回空 key（非确定性调用不缓存）"""
        from core.llm_cache import LLMCache

        cache = LLMCache()
        assert cache._make_key("glm", "sys", "hello", 0.3) == ""

    def test_different_prompt_different_key(self):
        from core.llm_cache import LLMCache

        cache = LLMCache()
        k1 = cache._make_key("m", "s", "prompt-a", 0)
        k2 = cache._make_key("m", "s", "prompt-b", 0)
        assert k1 != k2

    def test_same_input_same_key(self):
        """相同输入生成相同 key（幂等）"""
        from core.llm_cache import LLMCache

        cache = LLMCache()
        k1 = cache._make_key("m", "s", "p", 0)
        k2 = cache._make_key("m", "s", "p", 0)
        assert k1 == k2


class TestMemCache:
    """测试内存缓存 get/set"""

    def test_set_then_get_hit(self):
        from core.llm_cache import LLMCache

        cache = LLMCache()
        cache.set("m", "s", "hello", "world", 0)
        assert cache.get("m", "s", "hello", 0) == "world"

    def test_get_miss_empty_cache(self):
        from core.llm_cache import LLMCache

        cache = LLMCache()
        assert cache.get("m", "s", "nope", 0) is None

    def test_temp_nonzero_not_cached(self):
        """temperature>0 的 set 不缓存，get 也返回 None"""
        from core.llm_cache import LLMCache

        cache = LLMCache()
        cache.set("m", "s", "hello", "world", 0.5)
        assert cache.get("m", "s", "hello", 0.5) is None

    def test_stats_after_operations(self):
        from core.llm_cache import LLMCache

        cache = LLMCache()
        cache.set("m", "s", "p1", "r1", 0)
        cache.get("m", "s", "p1", 0)  # hit
        cache.get("m", "s", "p2", 0)  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["mem_size"] == 1

    def test_stats_empty_no_division_error(self):
        """无任何操作时 hit_rate=0，不触发除零"""
        from core.llm_cache import LLMCache

        cache = LLMCache()
        stats = cache.stats
        assert stats["hit_rate"] == 0


class TestTTLExpiry:
    """测试 TTL 过期"""

    def test_expired_entry_removed(self, monkeypatch):
        """超过 TTL 的条目被清除（返回 None）"""
        from core.llm_cache import LLMCache

        cache = LLMCache(ttl=100)
        cache.set("m", "s", "p", "r", 0)

        # 模拟时间前进超过 TTL
        t = [time.time()]
        monkeypatch.setattr("core.llm_cache.time.time", lambda: t[0] + 200)
        assert cache.get("m", "s", "p", 0) is None


class TestLRUEviction:
    """测试 LRU 淘汰"""

    def test_evict_oldest_when_full(self, monkeypatch):
        """maxsize 满时淘汰最旧条目"""
        from core.llm_cache import LLMCache

        t = [0.0]
        monkeypatch.setattr("core.llm_cache.time.time", lambda: t[0])

        cache = LLMCache(maxsize=2)
        t[0] = 1.0
        cache.set("m", "s", "p1", "r1", 0)
        t[0] = 2.0
        cache.set("m", "s", "p2", "r2", 0)
        t[0] = 3.0  # set p3 时，p1.time=1.0 最旧 → 被淘汰
        cache.set("m", "s", "p3", "r3", 0)

        assert cache.get("m", "s", "p1", 0) is None  # p1 被淘汰
        assert cache.get("m", "s", "p2", 0) == "r2"
        assert cache.get("m", "s", "p3", 0) == "r3"


class TestSqliteBackend:
    """测试 SQLite 持久化后端"""

    def test_persist_and_retrieve(self, tmp_path):
        """同一 db_path 下 set 后 get 能命中（跨实例也持久）"""
        from core.llm_cache import LLMCache

        db = str(tmp_path / "cache.db")
        cache = LLMCache(db_path=db)
        cache.set("m", "s", "p", "r", 0)

        # 清内存后仍能从 db 读回
        cache._mem_cache.clear()
        assert cache.get("m", "s", "p", 0) == "r"

    def test_clear_empties_both(self, tmp_path):
        """clear 清空内存 + db"""
        from core.llm_cache import LLMCache

        db = str(tmp_path / "cache.db")
        cache = LLMCache(db_path=db)
        cache.set("m", "s", "p", "r", 0)
        cache.clear()
        cache._mem_cache.clear()
        assert cache.get("m", "s", "p", 0) is None

    def test_new_instance_reads_existing_db(self, tmp_path):
        """新实例从已有 db 读取（跨进程持久化验证）"""
        from core.llm_cache import LLMCache

        db = str(tmp_path / "cache.db")
        c1 = LLMCache(db_path=db)
        c1.set("m", "s", "persist", "value", 0)

        c2 = LLMCache(db_path=db)
        assert c2.get("m", "s", "persist", 0) == "value"

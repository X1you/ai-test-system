#!/usr/bin/env python3
"""
LLM 调用缓存层 — 幂等 Prompt 结果缓存

缓存策略：
  - Key = hash(model + system + prompt + temperature)
  - 仅缓存 temperature=0 的确定性调用
  - 默认 TTL 24 小时
  - 支持内存 LRU 和 SQLite 持久化两种后端
"""

import hashlib
import sqlite3
import threading
import time


class LLMCache:
    """LLM 调用结果缓存"""

    def __init__(self, maxsize: int = 256, ttl: int = 86400, db_path: str | None = None):
        """
        Args:
            maxsize: 内存缓存最大条目数
            ttl: 缓存有效期（秒），默认 24 小时
            db_path: SQLite 持久化路径（可选，None 则仅用内存缓存）
        """
        self._maxsize = maxsize
        self._ttl = ttl
        self._db_path = db_path
        self._mem_cache: dict = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        if db_path:
            self._init_db()

    def _init_db(self):
        """初始化 SQLite 缓存表"""
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _make_key(self, model: str, system: str, prompt: str, temperature: float) -> str:
        """生成缓存 Key — 仅 temperature=0 时可缓存"""
        if temperature > 0:
            return ""  # 非确定性调用不缓存
        raw = f"{model}|{system or ''}|{prompt}|{temperature}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, model: str, system: str, prompt: str, temperature: float = 0) -> str | None:
        """查询缓存"""
        key = self._make_key(model, system, prompt, temperature)
        if not key:
            self._misses += 1
            return None

        now = time.time()

        # 先查内存
        with self._lock:
            if key in self._mem_cache:
                entry = self._mem_cache[key]
                if now - entry["time"] < self._ttl:
                    self._hits += 1
                    return entry["response"]
                else:
                    del self._mem_cache[key]

        # 再查 SQLite
        if self._db_path:
            result = self._get_from_db(key, now)
            if result is not None:
                self._hits += 1
                return result

        self._misses += 1
        return None

    def _get_from_db(self, key: str, now: float) -> str | None:
        """从 SQLite 查询"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute(
                "SELECT response, created_at FROM llm_cache WHERE cache_key = ?",
                (key,),
            )
            row = cursor.fetchone()
            conn.close()
            if row and now - row[1] < self._ttl:
                return row[0]
        except Exception:
            pass
        return None

    def set(self, model: str, system: str, prompt: str, response: str, temperature: float = 0):
        """写入缓存"""
        key = self._make_key(model, system, prompt, temperature)
        if not key:
            return

        now = time.time()

        with self._lock:
            # LRU 淘汰
            if len(self._mem_cache) >= self._maxsize:
                oldest = min(self._mem_cache, key=lambda k: self._mem_cache[k]["time"])
                del self._mem_cache[oldest]
            self._mem_cache[key] = {"response": response, "time": now}

        if self._db_path:
            self._set_to_db(key, response, now)

    def _set_to_db(self, key: str, response: str, now: float):
        """写入 SQLite"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache (cache_key, response, created_at) VALUES (?, ?, ?)",
                (key, response, now),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._mem_cache.clear()
        if self._db_path:
            try:
                conn = sqlite3.connect(self._db_path)
                conn.execute("DELETE FROM llm_cache")
                conn.commit()
                conn.close()
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        """缓存统计"""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0,
            "mem_size": len(self._mem_cache),
        }

#!/usr/bin/env python3
"""
DynamicKBManager — 动态知识库管理器（Sprint 6.0）

替代静态 config.yaml 读取，从 SQLite 数据库动态加载知识库配置，
支持运行时热切换 + 冷启动容错。

设计要点：
  1. 启动时从 DB 读取 is_active=True 的 KBConfig 行
  2. 若 DB 中无配置（冷启动），挂载 DummyKBClient 占位，不报错
  3. 用户通过 POST /api/knowledge/update_config 写入新配置后，
     调用 reload() 重建 client
  4. 线程安全：单例 + Lock 保护 reload

不重写老的 kb_manager.py（避免破坏 CLI），作为 Web 层独立模块。
"""

import logging
import threading
from typing import Any

logger = logging.getLogger("ai-test-system")


# ═══════════════════════════════════════════════════════════════
# DummyKBClient — 冷启动占位，零依赖
# ═══════════════════════════════════════════════════════════════

class DummyKBClient:
    """冷启动时的静默占位客户端。

    所有方法返回空结果，不抛异常，仅记录 WARN 级别日志提示用户配置。
    """

    provider_type = "dummy"

    def __init__(self) -> None:
        logger.warning(
            "DynamicKBManager: 未检测到知识库配置（DB 中无 active 记录），"
            "已挂载 DummyKBClient 占位。请通过 POST /api/knowledge/update_config 配置后激活。"
        )

    def status(self) -> dict:
        return {
            "source": "dummy",
            "provider_type": "dummy",
            "message": "知识库未配置，请先添加配置",
            "total": 0,
            "categories": {},
        }

    def search(self, query: str, **kwargs) -> list[dict]:
        return []

    def list_files(self, category: str | None = None) -> list[str]:
        return []

    def read_file(self, filepath: str) -> dict | None:
        return None

    def create_file(self, item: Any) -> bool:
        logger.warning("DummyKBClient: 知识库未配置，create_file 被忽略")
        return False


# ═══════════════════════════════════════════════════════════════
# DynamicKBManager — 单例 + 线程安全 reload
# ═══════════════════════════════════════════════════════════════

class DynamicKBManager:
    """动态知识库管理器。

    生命周期：
      __init__ / get_instance → 从 DB 加载 active 配置 → 构建 client
      reload() → 重新从 DB 加载 → 替换 client（加锁）
    """

    _instance: "DynamicKBManager | None" = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._client: Any = None
        self._config: dict | None = None
        self._reload_lock = threading.Lock()
        self._load_from_db()

    @classmethod
    def get_instance(cls) -> "DynamicKBManager":
        """单例获取（线程安全双重检查）"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ─── DB 配置读取 ───

    def _load_from_db(self) -> dict | None:
        """从 DB 读取 is_active=True 的 KBConfig 行。

        失败（DB 不存在/表不存在/无记录）时返回 None，触发 DummyKBClient。
        """
        try:
            from db.models import KBConfig
            from db.session import session_scope

            with session_scope() as session:
                cfg = (
                    session.query(KBConfig)
                    .filter(KBConfig.is_active == True)  # noqa: E712
                    .order_by(KBConfig.updated_at.desc())
                    .first()
                )
                if cfg is None:
                    self._build_client(None)
                    return None

                config = {
                    "provider_type": cfg.provider_type,
                    "connection_url": cfg.connection_url,
                    "auth_token": cfg.auth_token,
                    "vault_path": cfg.vault_path,
                }
                self._build_client(config)
                return config
        except Exception as e:
            # DB 不存在 / 表不存在 / 任何异常 → Dummy
            logger.info(
                "DynamicKBManager: DB 配置读取失败（%s），降级 DummyKBClient", e
            )
            self._build_client(None)
            return None

    def _build_client(self, config: dict | None) -> None:
        """根据 config 构建对应的 client 实例。

        Args:
            config: None 或 {provider_type, connection_url, auth_token, vault_path}
        """
        if config is None:
            self._client = DummyKBClient()
            self._config = None
            return

        provider = config.get("provider_type", "")
        try:
            if provider == "obsidian_api":
                self._client = self._build_obsidian_client(config)
            elif provider == "mcp_filesystem":
                self._client = self._build_mcp_client(config)
            else:
                logger.warning(
                    "DynamicKBManager: 未知 provider_type=%s，降级 Dummy", provider
                )
                self._client = DummyKBClient()
            self._config = config
        except Exception as e:
            logger.error(
                "DynamicKBManager: 构建 %s client 失败: %s，降级 Dummy", provider, e
            )
            self._client = DummyKBClient()
            self._config = None

    @staticmethod
    def _build_obsidian_client(config: dict) -> Any:
        """构建 Obsidian Local REST API 客户端"""
        from core.kb.mcp_client import MCPClient

        client = MCPClient(
            vault_path=config.get("vault_path") or "",
            use_obsidian_api=True,
            obsidian_api_base=config.get("connection_url") or "",
            obsidian_api_key=config.get("auth_token") or "",
        )
        return client

    @staticmethod
    def _build_mcp_client(config: dict) -> Any:
        """构建本地文件系统 MCP 客户端"""
        from core.kb.mcp_client import MCPClient

        vault = config.get("vault_path") or ""
        if not vault:
            raise ValueError("mcp_filesystem provider 需要 vault_path")
        return MCPClient(vault_path=vault, use_obsidian_api=False)

    # ─── 对外接口 ───

    def get_client(self) -> Any:
        """获取当前 client（线程安全的快照读）"""
        return self._client

    def get_config(self) -> dict | None:
        """获取当前生效的配置（None 表示 Dummy 模式）"""
        return self._config

    def reload(self) -> bool:
        """重新从 DB 加载配置并重建 client（线程安全）。

        Returns:
            True=配置成功加载并构建 client，False=降级 Dummy
        """
        with self._reload_lock:
            config = self._load_from_db()
            return config is not None

    def is_configured(self) -> bool:
        """是否已配置（非 Dummy 模式）"""
        return self._config is not None and not isinstance(
            self._client, DummyKBClient
        )


# ═══════════════════════════════════════════════════════════════
# 便捷入口
# ═══════════════════════════════════════════════════════════════

def get_dynamic_kb_manager() -> DynamicKBManager:
    """获取 DynamicKBManager 单例"""
    return DynamicKBManager.get_instance()

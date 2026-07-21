#!/usr/bin/env python3
"""
多租户支持（Track B）— 租户上下文 + 数据隔离

提供：
  - TenantContext: 租户上下文管理（线程/协程安全）
  - TenantManager: 租户 CRUD + 配额管理
  - tenant_filter: Repository 层自动数据隔离装饰器

数据模型层已在 Pipeline / User 表预留 tenant_id 字段。
本模块实现运行时租户上下文传递和数据自动过滤。
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

# ─── 租户上下文 ───

_tenant_ctx: ContextVar[Optional["TenantContext"]] = ContextVar(
    "_tenant_ctx", default=None
)


@dataclass
class TenantContext:
    """租户上下文 — 携带当前请求的租户信息"""

    tenant_id: str
    tenant_name: str = ""
    quotas: dict = field(default_factory=dict)


def get_current_tenant() -> TenantContext | None:
    """获取当前请求的租户上下文"""
    return _tenant_ctx.get()


def set_tenant_context(ctx: TenantContext | None):
    """设置当前请求的租户上下文"""
    return _tenant_ctx.set(ctx)


def reset_tenant_context(token):
    """重置租户上下文（配合 set_tenant_context 使用）"""
    _tenant_ctx.reset(token)


def require_tenant_id() -> str:
    """获取当前租户 ID，未设置时返回 'default'"""
    ctx = get_current_tenant()
    return ctx.tenant_id if ctx else "default"


# ─── 租户数据模型 ───

@dataclass
class Tenant:
    """租户信息"""
    id: str
    name: str
    status: str = "active"  # active / suspended / deleted
    max_concurrent: int = 3
    max_storage_mb: int = 1024
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    settings: dict = field(default_factory=dict)


class TenantManager:
    """租户管理器 — CRUD + 配额控制"""

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._init_default()

    def _init_default(self):
        """初始化默认租户"""
        default = Tenant(id="default", name="默认租户")
        self._tenants[default.id] = default

    def create_tenant(self, name: str, **kwargs) -> Tenant:
        """创建租户"""
        tenant_id = uuid.uuid4().hex[:12]
        tenant = Tenant(id=tenant_id, name=name, **kwargs)
        self._tenants[tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """查询租户"""
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> list[Tenant]:
        """列出所有租户"""
        return list(self._tenants.values())

    def suspend_tenant(self, tenant_id: str) -> bool:
        """停用租户"""
        tenant = self._tenants.get(tenant_id)
        if tenant:
            tenant.status = "suspended"
            return True
        return False

    def delete_tenant(self, tenant_id: str) -> bool:
        """删除租户（软删除）"""
        tenant = self._tenants.get(tenant_id)
        if tenant and tenant_id != "default":
            tenant.status = "deleted"
            return True
        return False

    def check_concurrency(self, tenant_id: str, current: int) -> bool:
        """检查并发配额"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False
        return current < tenant.max_concurrent

    def resolve_tenant_from_jwt(self, payload: dict) -> str:
        """从 JWT payload 中解析租户 ID"""
        return payload.get("tenant_id", "default")

    def resolve_tenant_from_header(self, headers: dict) -> str:
        """从请求头中解析租户 ID"""
        return headers.get("X-Tenant-ID", "default")


# ─── Repository 层租户过滤 ───

def apply_tenant_filter(query, model_class):
    """为 SQLAlchemy 查询添加租户过滤条件"""
    tenant_id = require_tenant_id()
    if hasattr(model_class, "tenant_id"):
        return query.filter(model_class.tenant_id == tenant_id)
    return query


# ─── 全局单例 ───

_tenant_manager: TenantManager | None = None


def get_tenant_manager() -> TenantManager:
    """获取全局 TenantManager 单例"""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager

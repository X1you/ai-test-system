#!/usr/bin/env python3
"""
用户服务 — 密码哈希校验 + 认证 + 管理员初始化

密码使用 bcrypt（成本因子 12），JWT 由 web.middleware.auth 负责。
"""

import os
import secrets

from db.repository import get_repository
from db.session import session_scope

# bcrypt 成本因子（12 是 2026 年的安全基线，兼顾性能）
_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """明文密码 → bcrypt 哈希（含 salt）。"""
    import bcrypt

    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """校验明文密码是否匹配哈希。

    任何异常（哈希格式错误等）返回 False，绝不抛异常给调用方。
    """
    try:
        import bcrypt

        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def authenticate(username: str, password: str):
    """用户名 + 密码认证，成功返回 User 对象，失败返回 None。"""
    user = get_repository().get_user_by_username(username)
    if not user:
        # 即使用户不存在也执行一次 hashpw，避免时序攻击区分"用户不存在"和"密码错误"
        hash_password(password)
        return None
    if not verify_password(password, user.password_hash):
        return None
    # 更新最后登录时间
    try:
        from datetime import UTC, datetime

        with session_scope() as session:
            from db.models import User

            session.query(User).filter(User.id == user.id).update(
                {"last_login": datetime.now(UTC)}
            )
    except Exception:
        pass  # last_login 更新失败不影响登录
    return user


def generate_api_key() -> str:
    """生成随机 API Key（32 字节 hex）。"""
    return secrets.token_hex(32)


def create_admin_if_not_exists(username: str | None = None, password: str | None = None):
    """启动时确保管理员账户存在（幂等）。

    凭证来源优先级：
      1. 函数参数（测试场景传入）
      2. 环境变量 ADMIN_USERNAME / ADMIN_PASSWORD
      3. 环境变量未设置 → 生成随机密码并打印一次（绝不使用硬编码默认密码）

    生产环境建议通过环境变量注入 ADMIN_PASSWORD，避免随机密码需查日志获取。
    """
    username = username or os.environ.get("ADMIN_USERNAME", "admin")
    password = password or os.environ.get("ADMIN_PASSWORD")

    repo = get_repository()
    if repo.get_user_by_username(username):
        return None

    if not password:
        # 环境变量未配置 → 生成随机密码，打印一次供运维获取
        password = secrets.token_urlsafe(16)
        import logging
        logging.getLogger("web").warning(
            "ADMIN_PASSWORD 未配置，已生成随机管理员密码（请立即登录修改）: %s", password
        )

    return repo.create_user(
        username=username,
        password_hash=hash_password(password),
        role="admin",
        api_key=generate_api_key(),
    )

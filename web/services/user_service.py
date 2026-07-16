#!/usr/bin/env python3
"""
用户服务 — Phase 4

提供密码哈希、用户认证、管理员引导、API Key 生成。
"""

import secrets

import bcrypt

from db.models import User
from db.repository import get_repository
from db.session import session_scope


def hash_password(password: str) -> str:
    """bcrypt 哈希密码，返回 str（可存储）"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希（bcrypt 限制 72 字节，超长时截断）"""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:72], password_hash.encode("utf-8")
        )
    except (ValueError, Exception):
        return False


def authenticate(username: str, password: str) -> User | None:
    """用户名 + 密码认证，成功返回 User，失败返回 None"""
    repo = get_repository()
    user = repo.get_user_by_username(username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    # 更新最后登录时间
    with session_scope() as session:
        db_user = session.query(User).filter(User.id == user.id).first()
        if db_user:
            from datetime import datetime
            db_user.last_login = datetime.utcnow()
    return user


def create_admin_if_not_exists(username: str, password: str) -> bool:
    """首次启动时创建管理员账户

    返回 True 表示新建，False 表示已存在。
    """
    repo = get_repository()
    existing = repo.get_user_by_username(username)
    if existing is not None:
        return False
    password_hash = hash_password(password)
    repo.create_user(
        username=username,
        password_hash=password_hash,
        role="admin",
    )
    return True


def generate_api_key() -> str:
    """生成随机 API Key（32 字符 hex）"""
    return secrets.token_hex(16)

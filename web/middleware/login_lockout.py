#!/usr/bin/env python3
"""
登录失败锁定 — 内存滑动窗口计数器

策略：
  - 按 IP + 用户名 组合跟踪失败次数
  - 连续失败 5 次 → 锁定该 IP 15 分钟
  - 登录成功或锁定过期后自动清除计数
  - 进程重启后计数清零（内存方案，适合单实例部署）

多实例部署时可替换为 Redis 后端实现。
"""

import time
from dataclasses import dataclass, field

# ─── 配置 ───
MAX_FAILURES = 5          # 连续失败次数上限
LOCKOUT_DURATION = 900    # 锁定时长（秒）= 15 分钟


@dataclass
class _LockState:
    """单个 IP 的锁定状态"""
    failures: int = 0
    first_failure_ts: float = 0.0
    locked_until: float = 0.0


# 全局状态：key = "ip:username"
_attempts: dict[str, _LockState] = {}


def _key(ip: str, username: str) -> str:
    return f"{ip}:{username}"


def is_locked(ip: str, username: str) -> bool:
    """检查该 IP+用户名 是否处于锁定状态"""
    state = _attempts.get(_key(ip, username))
    if not state:
        return False
    if state.locked_until > 0 and time.monotonic() < state.locked_until:
        return True
    # 锁定已过期，清除
    if state.locked_until > 0:
        _attempts.pop(_key(ip, username), None)
    return False


def get_lock_remaining(ip: str, username: str) -> int:
    """返回剩余锁定秒数（未锁定返回 0）"""
    state = _attempts.get(_key(ip, username))
    if not state or state.locked_until <= 0:
        return 0
    remaining = int(state.locked_until - time.monotonic())
    return max(remaining, 0)


def record_failure(ip: str, username: str) -> None:
    """记录一次登录失败，达到阈值时自动锁定"""
    k = _key(ip, username)
    now = time.monotonic()
    state = _attempts.get(k)
    if state is None:
        state = _LockState(failures=0, first_failure_ts=now)
        _attempts[k] = state
    # 如果距离首次失败超过 LOCKOUT_DURATION，重置计数（滑动窗口）
    if now - state.first_failure_ts > LOCKOUT_DURATION:
        state.failures = 0
        state.first_failure_ts = now

    state.failures += 1
    if state.failures >= MAX_FAILURES:
        state.locked_until = now + LOCKOUT_DURATION


def record_success(ip: str, username: str) -> None:
    """登录成功，清除失败计数"""
    _attempts.pop(_key(ip, username), None)


def reset_all() -> None:
    """清除所有锁定状态（主要用于测试）"""
    _attempts.clear()

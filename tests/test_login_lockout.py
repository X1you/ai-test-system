#!/usr/bin/env python3
"""
登录失败锁定模块测试
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import time
from unittest.mock import patch

from web.middleware.login_lockout import (
    get_lock_remaining,
    is_locked,
    record_failure,
    record_success,
    reset_all,
    MAX_FAILURES,
    LOCKOUT_DURATION,
)


class TestLoginLockout:
    """登录失败锁定测试"""

    def setup_method(self):
        reset_all()

    def test_not_locked_initially(self):
        """初始状态未锁定"""
        assert not is_locked("1.2.3.4", "admin")

    def test_single_failure_not_locked(self):
        """单次失败不锁定"""
        record_failure("1.2.3.4", "admin")
        assert not is_locked("1.2.3.4", "admin")

    def test_max_failures_triggers_lock(self):
        """达到最大失败次数触发锁定"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin")

    def test_lock_below_threshold(self):
        """阈值以下不锁定"""
        for _ in range(MAX_FAILURES - 1):
            record_failure("1.2.3.4", "admin")
        assert not is_locked("1.2.3.4", "admin")

    def test_success_clears_failures(self):
        """登录成功清除失败计数"""
        for _ in range(MAX_FAILURES - 1):
            record_failure("1.2.3.4", "admin")
        record_success("1.2.3.4", "admin")
        assert not is_locked("1.2.3.4", "admin")
        # 再次失败应从 0 开始计数
        record_failure("1.2.3.4", "admin")
        assert not is_locked("1.2.3.4", "admin")

    def test_different_users_independent(self):
        """不同用户名的失败计数独立"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin")
        assert not is_locked("1.2.3.4", "other_user")

    def test_different_ips_independent(self):
        """不同 IP 的失败计数独立"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin")
        assert not is_locked("5.6.7.8", "admin")

    def test_lock_remaining_returns_seconds(self):
        """锁定剩余时间返回秒数"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        remaining = get_lock_remaining("1.2.3.4", "admin")
        assert remaining > 0
        assert remaining <= LOCKOUT_DURATION

    def test_lock_remaining_zero_when_not_locked(self):
        """未锁定时剩余时间为 0"""
        assert get_lock_remaining("1.2.3.4", "admin") == 0

    def test_lock_expires_after_duration(self):
        """锁定在超时后自动解除"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        assert is_locked("1.2.3.4", "admin")

        # 模拟时间流逝超过锁定时长
        with patch("web.middleware.login_lockout.time.monotonic") as mock_time:
            # 第一次调用：获取当前时间用于 is_locked 检查
            # 设置为锁定结束后
            mock_time.return_value = 999999999  # 远未来
            assert not is_locked("1.2.3.4", "admin")

    def test_reset_all_clears_everything(self):
        """reset_all 清除所有锁定状态"""
        for _ in range(MAX_FAILURES):
            record_failure("1.2.3.4", "admin")
        record_failure("5.6.7.8", "user2")
        reset_all()
        assert not is_locked("1.2.3.4", "admin")
        assert not is_locked("5.6.7.8", "user2")

    def test_sliding_window_reset(self):
        """滑动窗口：超过锁定时长后失败计数重置"""
        record_failure("1.2.3.4", "admin")
        
        # 模拟时间流逝超过 LOCKOUT_DURATION
        with patch("web.middleware.login_lockout.time.monotonic") as mock_time:
            mock_time.return_value = LOCKOUT_DURATION + 10
            record_failure("1.2.3.4", "admin")
            # 应该从 1 重新开始（first_failure_ts 重置后 failures=1）
            assert not is_locked("1.2.3.4", "admin")

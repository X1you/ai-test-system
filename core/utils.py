#!/usr/bin/env python3
"""
通用工具模块

提供跨模块共享的基础工具函数。
"""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(lock_file: str, timeout: int = 10):
    """
    文件锁上下文管理器 — 防止并发写入冲突

    Args:
        lock_file: 锁文件路径
        timeout: 超时时间（秒），默认10秒

    Raises:
        TimeoutError: 获取锁超时
        IOError: 文件操作失败
    """
    lock_path = Path(lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fd = None
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            import time
            waited = 0
            while waited < timeout:
                time.sleep(0.1)
                waited += 0.1
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    continue
            else:
                raise TimeoutError(f"获取文件锁超时 ({timeout}秒)，可能有其他进程正在写入")

        yield

    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                try:
                    os.close(fd)
                except Exception:
                    pass


def safe_join_path(base_dir: str, user_path: str) -> Path:
    """安全路径拼接 — 防止路径穿越攻击

    Args:
        base_dir: 基准目录（受信任）
        user_path: 用户输入的相对路径（不受信任）

    Returns:
        解析后的安全绝对路径

    Raises:
        ValueError: 检测到路径穿越（结果路径不在 base_dir 之下）
    """
    base = Path(base_dir).resolve()
    resolved = (base / user_path).resolve()

    # 确保 resolved 在 base 目录之下（防止路径穿越）
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"路径穿越检测：{user_path} 解析后不在允许的目录范围内")

    return resolved

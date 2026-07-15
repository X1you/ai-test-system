#!/usr/bin/env python3
"""
文件锁工具模块
提供跨平台的文件锁功能，防止并发写入冲突
"""

import os
import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(lock_file: str, timeout: int = 10):
    """
    文件锁上下文管理器

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
        # 打开锁文件
        fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)
        
        # 尝试获取排他锁（非阻塞）
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # 获取锁失败，等待重试
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
        # 释放锁
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
                # 清理锁文件
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
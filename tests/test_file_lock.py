#!/usr/bin/env python3
"""
单元测试 — file_lock（pipeline/scripts/file_lock.py）
覆盖：基本加解锁、重入、并发竞争、超时、异常清理
"""

import pytest
import tempfile
import os
import time
import threading
import sys
from pathlib import Path

# 添加 pipeline scripts 到路径
scripts_dir = Path(__file__).parent.parent / "skills" / "pipeline" / "scripts"
sys.path.insert(0, str(scripts_dir))

from file_lock import file_lock


class TestBasicLock:
    """基本加解锁"""

    def test_acquire_release(self):
        """基本获取和释放"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "test.lock")
            with file_lock(lock_file, timeout=1):
                pass  # 获取后自动释放
            # 锁文件应该被清理
            assert not Path(lock_file).exists()

    def test_consecutive_locks(self):
        """连续加锁不阻塞"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "test.lock")
            with file_lock(lock_file, timeout=1):
                pass
            with file_lock(lock_file, timeout=1):
                pass
            # 两次都应该成功

    def test_lock_creates_parent_dir(self):
        """锁文件自动创建父目录"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "subdir" / "nested" / "test.lock")
            with file_lock(lock_file, timeout=1):
                pass
            assert Path(lock_file).parent.exists()


class TestConcurrentLock:
    """并发锁竞争"""

    def test_concurrent_writes_serialized(self):
        """多个线程并发写入，结果不应丢失"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "concurrent.lock")
            data_file = Path(d) / "data.txt"
            data_file.write_text("0")

            results = []
            barrier = threading.Barrier(5)

            def worker(worker_id):
                barrier.wait()  # 同时开始
                try:
                    with file_lock(lock_file, timeout=5):
                        val = int(data_file.read_text().strip())
                        time.sleep(0.01)  # 模拟写入延迟
                        data_file.write_text(str(val + 1))
                        results.append(f"w{worker_id}:ok")
                except Exception as e:
                    results.append(f"w{worker_id}:fail({e})")

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # 所有 worker 都应成功
            assert len(results) == 5
            assert all("ok" in r for r in results)
            # 最终值应为 5（无竞争条件）
            assert data_file.read_text().strip() == "5"

    def test_two_threads_one_waits(self):
        """两个线程同时竞争，第二个必须等待"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "race.lock")
            execution_order = []

            def worker(name, delay):
                with file_lock(lock_file, timeout=5):
                    execution_order.append(f"{name}:start")
                    time.sleep(delay)
                    execution_order.append(f"{name}:end")

            t1 = threading.Thread(target=worker, args=("A", 0.2))
            t2 = threading.Thread(target=worker, args=("B", 0.1))

            t1.start()
            time.sleep(0.05)  # 确保 A 先拿到锁
            t2.start()
            t1.join()
            t2.join()

            # A 先 start 必然先 end（不会被 B 打断）
            a_start = execution_order.index("A:start")
            a_end = execution_order.index("A:end")
            b_start = execution_order.index("B:start")
            assert a_start < a_end  # A 的 start 在 end 前
            assert a_end < b_start  # A 结束后 B 才开始


class TestLockTimeout:
    """锁超时"""

    def test_timeout_raises(self):
        """锁被占用时，超时应抛出 TimeoutError"""
        import fcntl

        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "blocked.lock")
            lock_path = Path(lock_file)
            lock_path.parent.mkdir(parents=True, exist_ok=True)

            # 预先占用锁
            fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)
            fcntl.flock(fd, fcntl.LOCK_EX)

            try:
                with pytest.raises(TimeoutError):
                    with file_lock(lock_file, timeout=1):
                        pass
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)


class TestLockCleanup:
    """锁文件清理"""

    def test_cleanup_on_success(self):
        """成功获取并释放后，锁文件被清理"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "cleanup.lock")
            with file_lock(lock_file, timeout=1):
                assert Path(lock_file).exists()
            # 退出后应清理
            assert not Path(lock_file).exists()

    def test_cleanup_on_exception(self):
        """即使上下文内抛异常，锁仍应被释放"""
        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "exc.lock")

            with pytest.raises(RuntimeError):
                with file_lock(lock_file, timeout=1):
                    raise RuntimeError("test exception")

            # 异常后锁应被释放（锁文件可能残留但锁已解锁）
            # 关键是后续可以重新获取锁
            with file_lock(lock_file, timeout=1):
                pass  # 能再次获取说明锁已释放


class TestFileIntegrity:
    """文件完整性保护"""

    def test_json_write_integrity(self):
        """并发写入 JSON 不应损坏文件"""
        import json

        with tempfile.TemporaryDirectory() as d:
            lock_file = str(Path(d) / "json.lock")
            state_file = Path(d) / "state.json"
            state_file.write_text("{}")

            def writer(worker_id):
                with file_lock(lock_file, timeout=5):
                    data = json.loads(state_file.read_text())
                    data[f"worker_{worker_id}"] = worker_id
                    state_file.write_text(json.dumps(data))

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            final = json.loads(state_file.read_text())
            assert len(final) == 10
            for i in range(10):
                assert f"worker_{i}" in final


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
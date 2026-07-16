#!/usr/bin/env python3
"""
资源监控器 — 后台线程持续采集 CPU/内存/磁盘/进程指标。

采样间隔内取均值，避免抖动。退出时生成汇总统计（峰值/均值）。
所有数据线程安全地写入内部列表，供报告读取。
"""

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResourceSample:
    """单次资源采样"""
    timestamp: str
    elapsed_sec: float
    cpu_percent: float       # 进程 CPU 占比
    mem_rss_mb: float        # 进程物理内存 (MB)
    mem_percent: float       # 进程内存占比
    disk_mb: float           # 工作目录磁盘占用 (MB)
    thread_count: int        # 活跃线程数
    fd_count: int            # 文件描述符数（macOS/Linux）


@dataclass
class ResourceSummary:
    """资源使用汇总"""
    samples: list = field(default_factory=list)
    peak_cpu: float = 0.0
    peak_mem_mb: float = 0.0
    avg_cpu: float = 0.0
    avg_mem_mb: float = 0.0
    peak_threads: int = 0
    peak_fds: int = 0
    duration_sec: float = 0.0

    def to_dict(self) -> dict:
        return {
            "peak_cpu": round(self.peak_cpu, 1),
            "peak_mem_mb": round(self.peak_mem_mb, 1),
            "avg_cpu": round(self.avg_cpu, 1),
            "avg_mem_mb": round(self.avg_mem_mb, 1),
            "peak_threads": self.peak_threads,
            "peak_fds": self.peak_fds,
            "duration_sec": round(self.duration_sec, 1),
            "sample_count": len(self.samples),
        }


class ResourceMonitor:
    """后台资源监控线程"""

    def __init__(self, interval: float = 5.0, workdir: str = "."):
        self.interval = interval
        self.workdir = os.path.abspath(workdir)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._samples: deque = deque(maxlen=720)  # 最多保留 720 个采样点
        self._start_time: float = 0.0
        self._psutil_proc = None

    def start(self):
        """启动监控线程"""
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ResourceMonitor")
        self._thread.start()

    def stop(self) -> ResourceSummary:
        """停止监控并返回汇总"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 2)
        return self.get_summary()

    def _run(self):
        """监控循环"""
        # 延迟导入 psutil（可选依赖）
        try:
            import psutil
            self._psutil_proc = psutil.Process(os.getpid())
        except ImportError:
            psutil = None
            self._psutil_proc = None

        while not self._stop_event.is_set():
            sample = self._sample(time.time() - self._start_time, psutil)
            with self._lock:
                self._samples.append(sample)
            self._stop_event.wait(self.interval)

    def _sample(self, elapsed: float, psutil_mod=None) -> ResourceSample:
        """采集一次资源数据"""
        cpu_pct = 0.0
        mem_rss = 0.0
        mem_pct = 0.0
        thread_count = threading.active_count()
        fd_count = 0

        if self._psutil_proc and psutil_mod:
            try:
                cpu_pct = self._psutil_proc.cpu_percent(interval=0.5)
                mem_info = self._psutil_proc.memory_info()
                mem_rss = mem_info.rss / (1024 * 1024)
                mem_pct = self._psutil_proc.memory_percent()
                thread_count = self._psutil_proc.num_threads()
                try:
                    fd_count = self._psutil_proc.num_fds()
                except (AttributeError, psutil_mod.AccessDenied):
                    fd_count = 0
            except (psutil_mod.NoSuchProcess, psutil_mod.AccessDenied):
                pass

        # 磁盘占用（工作目录）
        disk_mb = self._dir_size_mb(self.workdir)

        return ResourceSample(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            elapsed_sec=round(elapsed, 1),
            cpu_percent=round(cpu_pct, 1),
            mem_rss_mb=round(mem_rss, 1),
            mem_percent=round(mem_pct, 2),
            disk_mb=round(disk_mb, 1),
            thread_count=thread_count,
            fd_count=fd_count,
        )

    @staticmethod
    def _dir_size_mb(path: str) -> float:
        """计算目录大小（MB）"""
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    try:
                        fp = os.path.join(dirpath, f)
                        if not os.path.islink(fp):
                            total += os.path.getsize(fp)
                    except OSError:
                        pass
        except OSError:
            pass
        return total / (1024 * 1024)

    def get_summary(self) -> ResourceSummary:
        """生成资源使用汇总"""
        with self._lock:
            samples = list(self._samples)

        if not samples:
            return ResourceSummary()

        cpus = [s.cpu_percent for s in samples]
        mems = [s.mem_rss_mb for s in samples]
        threads = [s.thread_count for s in samples]
        fds = [s.fd_count for s in samples]

        return ResourceSummary(
            samples=[{
                "timestamp": s.timestamp,
                "elapsed": s.elapsed_sec,
                "cpu": s.cpu_percent,
                "mem_mb": s.mem_rss_mb,
                "disk_mb": s.disk_mb,
                "threads": s.thread_count,
                "fds": s.fd_count,
            } for s in samples],
            peak_cpu=max(cpus),
            peak_mem_mb=max(mems),
            avg_cpu=sum(cpus) / len(cpus),
            avg_mem_mb=sum(mems) / len(mems),
            peak_threads=max(threads),
            peak_fds=max(fds),
            duration_sec=samples[-1].elapsed_sec if samples else 0.0,
        )

    def current_snapshot(self) -> dict:
        """获取当前资源快照（供实时显示）"""
        with self._lock:
            if not self._samples:
                return {"status": "warming_up"}
            s = self._samples[-1]
            return {
                "elapsed": s.elapsed_sec,
                "cpu": s.cpu_percent,
                "mem_mb": s.mem_rss_mb,
                "disk_mb": s.disk_mb,
                "threads": s.thread_count,
            }

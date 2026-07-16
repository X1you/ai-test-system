#!/usr/bin/env python3
"""
资源监控模块 — 跟踪测试过程中的系统资源使用情况

监控指标：
  - CPU 使用率（总体 + 每核）
  - 内存使用（RSS / VMS / 百分比）
  - 磁盘 I/O（读写字节数）
  - 网络 I/O（收发字节数）
  - 进程信息（线程数、打开文件数）

支持采样间隔配置，提供实时快照和汇总统计。
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class ResourceMonitor:
    """系统资源监控器"""

    def __init__(self, sample_interval: float = 2.0, output_dir: str | None = None):
        """
        Args:
            sample_interval: 采样间隔（秒）
            output_dir: 采样数据输出目录
        """
        self.sample_interval = sample_interval
        self.output_dir = Path(output_dir) if output_dir else Path("./output/monitor")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._running = False
        self._thread: threading.Thread | None = None
        self._samples: list = []
        self._lock = threading.Lock()
        self._start_time: datetime | None = None
        self._process = psutil.Process() if HAS_PSUTIL else None

        # 初始磁盘/网络计数器
        self._initial_disk_io = None
        self._initial_net_io = None

    def start(self):
        """启动监控"""
        if not HAS_PSUTIL:
            print("[Monitor] psutil 未安装，跳过资源监控")
            return

        self._running = True
        self._start_time = datetime.now()

        # 记录初始计数器
        try:
            self._initial_disk_io = psutil.disk_io_counters()
            self._initial_net_io = psutil.net_io_counters()
        except Exception:
            self._initial_disk_io = None
            self._initial_net_io = None

        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        print(f"[Monitor] 资源监控已启动，采样间隔 {self.sample_interval}s")

    def stop(self) -> dict:
        """停止监控并返回汇总统计"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        summary = self._compute_summary()
        self._save_samples()
        print(f"[Monitor] 资源监控已停止，共采集 {len(self._samples)} 个样本")
        return summary

    def _sample_loop(self):
        """后台采样循环"""
        while self._running:
            try:
                sample = self._collect_sample()
                with self._lock:
                    self._samples.append(sample)
            except Exception as e:
                print(f"[Monitor] 采样异常: {e}")
            time.sleep(self.sample_interval)

    def _collect_sample(self) -> dict:
        """采集单个样本"""
        sample = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": (datetime.now() - self._start_time).total_seconds(),
        }

        if not HAS_PSUTIL:
            return sample

        # CPU
        try:
            sample["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            sample["cpu_per_core"] = psutil.cpu_percent(interval=0.1, percpu=True)
        except Exception:
            sample["cpu_percent"] = -1

        # 内存
        try:
            mem = psutil.virtual_memory()
            sample["memory"] = {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "percent": mem.percent,
            }
        except Exception:
            sample["memory"] = {"percent": -1}

        # 进程内存
        if self._process:
            try:
                pmem = self._process.memory_info()
                sample["process_memory"] = {
                    "rss_mb": round(pmem.rss / (1024 ** 2), 2),
                    "vms_mb": round(pmem.vms / (1024 ** 2), 2),
                }
                sample["process_threads"] = self._process.num_threads()
            except Exception:
                pass

        # 磁盘 I/O
        try:
            current_disk = psutil.disk_io_counters()
            if current_disk and self._initial_disk_io:
                sample["disk_io"] = {
                    "read_mb": round(
                        (current_disk.read_bytes - self._initial_disk_io.read_bytes) / (1024 ** 2), 2
                    ),
                    "write_mb": round(
                        (current_disk.write_bytes - self._initial_disk_io.write_bytes) / (1024 ** 2), 2
                    ),
                }
        except Exception:
            pass

        # 网络 I/O
        try:
            current_net = psutil.net_io_counters()
            if current_net and self._initial_net_io:
                sample["net_io"] = {
                    "sent_mb": round(
                        (current_net.bytes_sent - self._initial_net_io.bytes_sent) / (1024 ** 2), 2
                    ),
                    "recv_mb": round(
                        (current_net.bytes_recv - self._initial_net_io.bytes_recv) / (1024 ** 2), 2
                    ),
                }
        except Exception:
            pass

        # 磁盘使用率
        try:
            disk_usage = psutil.disk_usage("/")
            sample["disk_usage"] = {
                "total_gb": round(disk_usage.total / (1024 ** 3), 2),
                "used_gb": round(disk_usage.used / (1024 ** 3), 2),
                "free_gb": round(disk_usage.free / (1024 ** 3), 2),
                "percent": disk_usage.percent,
            }
        except Exception:
            pass

        return sample

    def _compute_summary(self) -> dict:
        """计算汇总统计"""
        with self._lock:
            samples = list(self._samples)

        if not samples:
            return {"samples": 0, "message": "无采样数据"}

        cpu_values = [s.get("cpu_percent", 0) for s in samples if s.get("cpu_percent", -1) >= 0]
        mem_values = [s.get("memory", {}).get("percent", 0) for s in samples
                      if s.get("memory", {}).get("percent", -1) >= 0]
        rss_values = [s.get("process_memory", {}).get("rss_mb", 0) for s in samples
                      if s.get("process_memory")]

        summary = {
            "samples": len(samples),
            "duration_seconds": round(
                (datetime.now() - self._start_time).total_seconds(), 1
            ) if self._start_time else 0,
            "sample_interval": self.sample_interval,
            "cpu": {
                "avg_percent": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
                "max_percent": round(max(cpu_values), 2) if cpu_values else 0,
                "min_percent": round(min(cpu_values), 2) if cpu_values else 0,
            },
            "memory": {
                "avg_percent": round(sum(mem_values) / len(mem_values), 2) if mem_values else 0,
                "max_percent": round(max(mem_values), 2) if mem_values else 0,
            },
            "process": {
                "avg_rss_mb": round(sum(rss_values) / len(rss_values), 2) if rss_values else 0,
                "max_rss_mb": round(max(rss_values), 2) if rss_values else 0,
            },
        }

        # 磁盘 I/O 汇总
        last_sample = samples[-1]
        if "disk_io" in last_sample:
            summary["disk_io"] = last_sample["disk_io"]

        # 网络 I/O 汇总
        if "net_io" in last_sample:
            summary["net_io"] = last_sample["net_io"]

        return summary

    def _save_samples(self):
        """保存采样数据到文件"""
        if not self._samples:
            return

        # 保存完整采样数据
        samples_file = self.output_dir / "resource_samples.json"
        with open(samples_file, "w", encoding="utf-8") as f:
            json.dump(self._samples, f, ensure_ascii=False, indent=2)

        # 保存汇总
        summary = self._compute_summary()
        summary_file = self.output_dir / "resource_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"[Monitor] 采样数据已保存: {samples_file}")
        print(f"[Monitor] 汇总数据已保存: {summary_file}")

    def get_current_snapshot(self) -> dict | None:
        """获取当前快照（不加入采样列表）"""
        return self._collect_sample() if HAS_PSUTIL else None

    def get_sample_count(self) -> int:
        """获取当前采样数"""
        with self._lock:
            return len(self._samples)


# 便捷函数
def create_monitor(sample_interval: float = 2.0, output_dir: str | None = None) -> ResourceMonitor:
    """创建资源监控器"""
    return ResourceMonitor(sample_interval=sample_interval, output_dir=output_dir)

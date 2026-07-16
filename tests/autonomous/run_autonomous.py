#!/usr/bin/env python3
"""
自主测试编排器 — 无人值守运行全部测试阶段。

特性：
  - 8 个测试阶段，200+ 测试用例，执行 60 分钟+
  - 后台资源监控（CPU/内存/磁盘/线程）
  - 异常处理：单个测试失败不影响后续执行
  - 断点续跑：记录进度，中断后可从上次阶段继续
  - 进度显示：实时输出执行进度
  - 自动报告生成：HTML + JSON

用法：
    python -m tests.autonomous.run_autonomous [--workdir DIR] [--resume]

无参数：在 ./test-autonomous-output/ 下执行全部测试。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 激活 venv
activate = PROJECT_ROOT / ".venv/bin/activate_this.py"
if activate.exists():
    exec(open(activate).read(), {"__file__": str(activate)})

os.environ.setdefault("LLM_API_KEY", "sk-test-dummy-key-for-autonomous-testing")

from tests.autonomous.report_generator import ReportGenerator
from tests.autonomous.resource_monitor import ResourceMonitor
from tests.autonomous.test_phases import build_all_phases

# ═══════════════════════════════════════════════════════════════
# 断点续跑状态
# ═══════════════════════════════════════════════════════════════

PROGRESS_FILE = "_autonomous_progress.json"


def save_progress(workdir: Path, completed_phases: list, all_phase_data: list):
    """保存执行进度"""
    progress = {
        "completed_phases": completed_phases,
        "phase_data": all_phase_data,
        "updated": datetime.now().isoformat(),
    }
    (workdir / PROGRESS_FILE).write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_progress(workdir: Path) -> dict:
    """加载执行进度"""
    path = workdir / PROGRESS_FILE
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"completed_phases": [], "phase_data": []}


# ═══════════════════════════════════════════════════════════════
# 主编排器
# ═══════════════════════════════════════════════════════════════

class AutonomousTestRunner:
    """自主测试编排器"""

    def __init__(self, workdir: str, resume: bool = False):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.resume = resume
        self.monitor = ResourceMonitor(interval=10.0, workdir=str(self.workdir))
        self.start_time_str = datetime.now().isoformat(timespec="seconds")
        self.start_ts = time.time()

        # 测试配置
        self.config = {
            "workdir": str(self.workdir),
            "resume": resume,
            "monitor_interval": 10,
            "env": {
                "python": sys.version.split()[0],
                "platform": sys.platform,
                "pid": os.getpid(),
            },
        }

    def run(self) -> dict:
        """执行全部测试"""
        print("=" * 70)
        print("  🤖 自主测试系统启动")
        print(f"  📂 工作目录: {self.workdir}")
        print(f"  🐍 Python: {sys.version.split()[0]}")
        print(f"  ⏰ 开始时间: {self.start_time_str}")
        if self.resume:
            print("  🔄 断点续跑模式")
        print("=" * 70)
        print()

        # 启动资源监控
        self.monitor.start()

        # 构建全部测试阶段
        all_phases = build_all_phases(self.workdir / "testdata")

        # 加载已有进度
        progress = load_progress(self.workdir) if self.resume else {"completed_phases": [], "phase_data": []}
        completed_phases = set(progress.get("completed_phases", []))
        all_phase_data = list(progress.get("phase_data", []))

        # 执行各阶段
        phase_results_for_report = []
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0

        for idx, (phase_name, suite) in enumerate(all_phases, 1):
            phase_key = f"phase_{idx}"

            if phase_key in completed_phases:
                print(f"\n{'─' * 60}")
                print(f"  ⏭️  [{idx}/8] {phase_name} — 已完成，跳过")
                # 从历史数据恢复
                for pd in all_phase_data:
                    if pd.get("phase") == phase_name:
                        phase_results_for_report.append((phase_name, pd.get("results", [])))
                        break
                continue

            print(f"\n{'─' * 60}")
            print(f"  ▶️  [{idx}/8] {phase_name}")
            print(f"     测试用例数: {len(suite._cases)}")
            print(f"{'─' * 60}")

            phase_start = time.time()

            # 执行本阶段测试
            results = suite.run_all(stop_on_error=False)
            phase_elapsed = time.time() - phase_start

            # 统计
            summary = suite.summary()
            total_tests += summary["total"]
            total_passed += summary["passed"]
            total_failed += summary["failed"]
            total_errors += summary["error"]

            print(f"\n  📊 {phase_name} 完成:")
            print(f"     通过: {summary['passed']}/{summary['total']} ({summary['pass_rate']}%)")
            if summary["failed"]:
                print(f"     ❌ 失败: {summary['failed']}")
            if summary["error"]:
                print(f"     ⚡ 错误: {summary['error']}")
            print(f"     耗时: {phase_elapsed:.1f}s")

            # 保存阶段结果
            phase_data = {
                "phase": phase_name,
                "phase_key": phase_key,
                "summary": summary,
                "results": suite.results_to_dict(),
                "elapsed_sec": round(phase_elapsed, 1),
            }
            all_phase_data.append(phase_data)
            phase_results_for_report.append((phase_name, suite.results_to_dict()))

            # 更新进度
            completed_phases.add(phase_key)
            save_progress(self.workdir, sorted(completed_phases), all_phase_data)

            # 资源快照
            snap = self.monitor.current_snapshot()
            if "elapsed" in snap:
                print(f"     💾 资源: CPU={snap.get('cpu', 0):.1f}%, 内存={snap.get('mem_mb', 0):.0f}MB, 磁盘={snap.get('disk_mb', 0):.0f}MB")

        # 停止监控
        print(f"\n{'═' * 60}")
        print("  📊 生成测试报告...")
        resource_summary = self.monitor.stop()
        end_time_str = datetime.now().isoformat(timespec="seconds")
        total_duration = time.time() - self.start_ts

        # 生成报告
        reporter = ReportGenerator(str(self.workdir / "report"))
        report_info = reporter.generate(
            phases=phase_results_for_report,
            resource_summary=resource_summary.to_dict(),
            config=self.config,
            start_time=self.start_time_str,
            end_time=end_time_str,
            total_duration_sec=total_duration,
        )

        # 最终汇总
        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        duration_min = total_duration / 60

        print()
        print("  " + "═" * 60)
        print("  ✅ 自主测试全部完成！")
        print("  " + "═" * 60)
        print(f"  📊 总测试数: {total_tests}")
        print(f"  ✅ 通过: {total_passed} ({overall_pass_rate:.1f}%)")
        print(f"  ❌ 失败: {total_failed}")
        print(f"  ⚡ 错误: {total_errors}")
        print(f"  ⏱  总耗时: {duration_min:.1f} 分钟 ({total_duration:.0f}s)")
        print(f"  💾 峰值内存: {resource_summary.peak_mem_mb:.0f}MB")
        print(f"  💾 峰值CPU: {resource_summary.peak_cpu:.1f}%")
        print(f"  📄 HTML报告: {report_info['html_path']}")
        print(f"  📄 JSON数据: {report_info['json_path']}")
        print()

        # 清理进度文件（全部完成后）
        progress_file = self.workdir / PROGRESS_FILE
        if progress_file.exists():
            progress_file.rename(self.workdir / f"{PROGRESS_FILE}.completed")

        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "pass_rate": round(overall_pass_rate, 1),
            "duration_sec": round(total_duration, 1),
            "duration_min": round(duration_min, 1),
            "html_report": report_info["html_path"],
            "json_report": report_info["json_path"],
        }


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="自主测试系统 — 无人值守运行 60 分钟+ 全面测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workdir", "-w",
        default=str(PROJECT_ROOT / "test-autonomous-output"),
        help="工作目录（默认 ./test-autonomous-output）",
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="从上次中断处继续",
    )
    args = parser.parse_args()

    runner = AutonomousTestRunner(args.workdir, resume=args.resume)
    result = runner.run()

    # 退出码：有错误返回 1，否则 0
    return 1 if result["total_errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

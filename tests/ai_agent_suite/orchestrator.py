#!/usr/bin/env python3
"""
AI Agent 自动化测试编排器

主入口 — 支持无人值守运行 60 分钟以上的全自动化测试。
负责：
  - 环境准备与验证
  - 按顺序执行三个测试模块
  - 异常捕获与恢复（单个测试失败不影响整体流程）
  - 资源监控（后台持续采样）
  - 结果收集与汇总
  - 多格式报告生成

使用方式：
  python -m tests.ai_agent_suite.orchestrator
  python -m tests.ai_agent_suite.orchestrator --output ./my_reports
  python -m tests.ai_agent_suite.orchestrator --modules pipeline,web_api,data
  python -m tests.ai_agent_suite.orchestrator --timeout 120
"""

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 设置测试环境变量
os.environ.setdefault("LLM_API_KEY", os.environ.get("LLM_API_KEY", "sk-test-dummy"))
os.environ.setdefault("AI_TEST_ENV", "development")


class TestOrchestrator:
    """测试编排器 — 主控制器"""

    # 模块定义
    MODULES = {
        "pipeline": {
            "name": "Pipeline 引擎测试",
            "path": "tests/ai_agent_suite/module_pipeline",
            "test_files": ["test_pipeline_e2e.py"],
            "estimated_minutes": 25,
            "description": "Pipeline 完整流程、断点续跑、异常处理、并发执行",
        },
        "web_api": {
            "name": "Web API 与服务层测试",
            "path": "tests/ai_agent_suite/module_web_api",
            "test_files": ["test_api_services.py"],
            "estimated_minutes": 20,
            "description": "REST API 全覆盖、认证授权、SSE、安全防护、并发请求",
        },
        "data": {
            "name": "数据持久化与集成测试",
            "path": "tests/ai_agent_suite/module_data",
            "test_files": ["test_data_integration.py"],
            "estimated_minutes": 20,
            "description": "数据库 CRUD、迁移恢复、知识库、文件生成、外部集成",
        },
    }

    def __init__(
        self,
        output_dir: str = "./output/ai_agent_reports",
        modules: list | None = None,
        timeout_minutes: int = 120,
        verbose: bool = True,
        fail_fast: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.modules_to_run = modules or list(self.MODULES.keys())
        self.timeout_minutes = timeout_minutes
        self.verbose = verbose
        self.fail_fast = fail_fast

        # 验证模块
        for m in self.modules_to_run:
            if m not in self.MODULES:
                raise ValueError(f"未知模块: {m}，可用模块: {list(self.MODULES.keys())}")

        # 运行时状态
        self.start_time: datetime | None = None
        self.results: dict = {
            "summary": {},
            "modules": {},
            "details": [],
            "errors": [],
            "suggestions": [],
        }
        self.resource_summary: dict = {}
        self.monitor = None

    def run(self) -> dict:
        """执行完整测试套件"""
        self._print_header()
        self.start_time = datetime.now()

        # 1. 环境准备
        self._prepare_environment()

        # 2. 启动资源监控
        self._start_monitoring()

        # 3. 执行各模块测试
        total_start = time.time()
        try:
            for module_key in self.modules_to_run:
                if self._is_timeout():
                    self._log("WARNING", "已达到超时限制，停止执行后续模块")
                    break

                self._run_module(module_key)

        except KeyboardInterrupt:
            self._log("WARNING", "用户中断测试执行")
            self.results["suggestions"].append("测试被用户手动中断，部分模块未执行完成")
        except Exception as e:
            self._log("ERROR", f"编排器异常: {e}")
            self.results["errors"].append({
                "module": "orchestrator",
                "test_name": "suite_execution",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            })

        total_elapsed = time.time() - total_start

        # 4. 停止资源监控
        self.resource_summary = self._stop_monitoring()

        # 5. 汇总结果
        self._compute_summary(total_elapsed)

        # 6. 生成报告
        self._generate_reports(total_elapsed)

        # 7. 保存原始结果
        self._save_raw_results()

        self._print_summary()
        return self.results

    def _prepare_environment(self):
        """环境准备与验证"""
        self._log("INFO", "=" * 60)
        self._log("INFO", "阶段 1: 环境准备与验证")
        self._log("INFO", "=" * 60)

        checks = []

        # 检查 Python 版本
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        checks.append(("Python 版本", py_version, sys.version_info >= (3, 11)))

        # 检查项目根目录
        checks.append(("项目根目录", str(PROJECT_ROOT), PROJECT_ROOT.exists()))

        # 检查关键模块
        key_modules = ["core", "web", "db", "scripts"]
        for mod in key_modules:
            mod_path = PROJECT_ROOT / mod
            checks.append((f"模块 {mod}", str(mod_path), mod_path.exists()))

        # 检查 LLM API Key
        llm_key = os.environ.get("LLM_API_KEY", "")
        checks.append(("LLM API Key", "已设置" if llm_key else "未设置", bool(llm_key)))

        # 检查数据库
        try:
            from sqlalchemy import text

            from db.session import get_engine, init_db

            init_db()
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks.append(("数据库", "连接正常", True))
        except Exception as e:
            checks.append(("数据库", f"连接失败: {e}", False))

        # 检查 psutil（资源监控）
        try:
            import psutil
            checks.append(("psutil (资源监控)", "已安装", True))
        except ImportError:
            checks.append(("psutil (资源监控)", "未安装 (监控功能不可用)", False))

        # 打印检查结果
        all_ok = True
        for name, detail, ok in checks:
            status = "OK" if ok else "FAIL"
            self._log("CHECK", f"[{status}] {name}: {detail}")
            if not ok:
                all_ok = False

        if not all_ok:
            self._log("WARNING", "部分环境检查未通过，但测试将继续执行")

        self._log("INFO", "")

    def _start_monitoring(self):
        """启动资源监控"""
        from tests.ai_agent_suite.monitor import create_monitor

        monitor_output = str(self.output_dir / "monitor")
        self.monitor = create_monitor(sample_interval=2.0, output_dir=monitor_output)
        self.monitor.start()

    def _stop_monitoring(self) -> dict:
        """停止资源监控并返回汇总"""
        if self.monitor:
            return self.monitor.stop()
        return {"samples": 0, "message": "监控未启动"}

    def _run_module(self, module_key: str):
        """执行单个模块的测试"""
        mod_info = self.MODULES[module_key]
        module_start = time.time()

        self._log("INFO", "=" * 60)
        self._log("INFO", f"阶段: {mod_info['name']}")
        self._log("INFO", f"描述: {mod_info['description']}")
        self._log("INFO", f"预计耗时: ~{mod_info['estimated_minutes']} 分钟")
        self._log("INFO", "=" * 60)

        module_results = {
            "name": mod_info["name"],
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0},
            "tests": [],
        }

        for test_file in mod_info["test_files"]:
            test_path = PROJECT_ROOT / mod_info["path"] / test_file
            if not test_path.exists():
                self._log("ERROR", f"测试文件不存在: {test_path}")
                module_results["tests"].append({
                    "test_name": test_file,
                    "status": "error",
                    "duration": 0,
                    "note": "测试文件不存在",
                })
                module_results["summary"]["errors"] += 1
                continue

            self._log("INFO", f"执行测试文件: {test_file}")

            try:
                result = self._run_pytest_file(test_path)
                module_results["tests"].extend(result["tests"])
                module_results["summary"]["total"] += result["summary"]["total"]
                module_results["summary"]["passed"] += result["summary"]["passed"]
                module_results["summary"]["failed"] += result["summary"]["failed"]
                module_results["summary"]["skipped"] += result["summary"]["skipped"]
                module_results["summary"]["errors"] += result["summary"]["errors"]

                # 收集错误详情
                for err in result.get("errors", []):
                    self.results["errors"].append(err)

                # 失败时是否快速终止
                if self.fail_fast and result["summary"]["failed"] > 0:
                    self._log("WARNING", "fail_fast 模式，终止后续测试")
                    break

            except Exception as e:
                self._log("ERROR", f"模块 {module_key} 执行异常: {e}")
                module_results["tests"].append({
                    "test_name": test_file,
                    "status": "error",
                    "duration": time.time() - module_start,
                    "note": str(e),
                })
                module_results["summary"]["errors"] += 1
                self.results["errors"].append({
                    "module": module_key,
                    "test_name": test_file,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc(),
                })

        # 计算模块耗时
        module_elapsed = time.time() - module_start
        module_results["summary"]["duration_seconds"] = round(module_elapsed, 1)
        module_results["summary"]["duration_minutes"] = round(module_elapsed / 60, 1)
        total = module_results["summary"]["total"]
        passed = module_results["summary"]["passed"]
        module_results["summary"]["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0

        self.results["modules"][module_key] = module_results

        self._log("INFO", f"模块 {mod_info['name']} 完成: "
                 f"{passed}/{total} 通过, 耗时 {module_elapsed:.1f}s")

    def _run_pytest_file(self, test_path: Path) -> dict:
        """运行单个 pytest 文件并解析结果"""
        result = {
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0},
            "tests": [],
            "errors": [],
        }

        # 构建 pytest 命令
        cmd = [
            sys.executable, "-m", "pytest",
            str(test_path),
            "-v",
            "--tb=short",
            "--no-header",
            "--color=no",
            f"--rootdir={PROJECT_ROOT}",
        ]

        self._log("DEBUG", f"执行命令: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=self.timeout_minutes * 60,
                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            )

            # 解析 pytest 输出
            self._parse_pytest_output(proc.stdout, proc.stderr, result)

            if self.verbose:
                # 打印关键输出
                for line in proc.stdout.split("\n"):
                    if any(kw in line for kw in ["PASSED", "FAILED", "ERROR", "test_"]):
                        if "PASSED" in line or "FAILED" in line or "ERROR" in line:
                            self._log("TEST", line.strip())

            if proc.returncode != 0 and proc.returncode != 1:
                # pytest 返回 1 表示有测试失败，这是正常的
                # 返回其他值表示执行错误
                if proc.returncode > 1:
                    self._log("ERROR", f"pytest 退出码: {proc.returncode}")
                    result["summary"]["errors"] += 1

        except subprocess.TimeoutExpired:
            self._log("ERROR", f"测试超时: {test_path.name}")
            result["summary"]["errors"] += 1
            result["errors"].append({
                "module": test_path.parent.name,
                "test_name": test_path.name,
                "error_type": "TimeoutExpired",
                "error_message": f"测试执行超时 ({self.timeout_minutes} 分钟)",
                "traceback": "",
            })

        except Exception as e:
            self._log("ERROR", f"执行测试异常: {e}")
            result["summary"]["errors"] += 1
            result["errors"].append({
                "module": test_path.parent.name,
                "test_name": test_path.name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            })

        return result

    def _parse_pytest_output(self, stdout: str, stderr: str, result: dict):
        """解析 pytest 输出，提取测试结果"""
        # 统计测试结果
        for line in stdout.split("\n"):
            line = line.strip()
            if "passed" in line and "failed" in line:
                # 解析最后的统计行，如 "10 passed, 2 failed, 1 skipped"
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "passed" in part:
                        try:
                            result["summary"]["passed"] = int(part.split()[0])
                        except ValueError:
                            pass
                    elif "failed" in part:
                        try:
                            result["summary"]["failed"] = int(part.split()[0])
                        except ValueError:
                            pass
                    elif "skipped" in part:
                        try:
                            result["summary"]["skipped"] = int(part.split()[0])
                        except ValueError:
                            pass
                    elif "error" in part.lower():
                        try:
                            result["summary"]["errors"] = int(part.split()[0])
                        except ValueError:
                            pass

            # 解析单个测试行
            if line.startswith("tests/") or "::" in line:
                if "PASSED" in line:
                    test_name = line.split("PASSED")[0].strip().rstrip(".")
                    result["tests"].append({
                        "test_name": test_name,
                        "status": "passed",
                        "duration": 0,
                        "note": "",
                    })
                elif "FAILED" in line:
                    test_name = line.split("FAILED")[0].strip().rstrip(".")
                    result["tests"].append({
                        "test_name": test_name,
                        "status": "failed",
                        "duration": 0,
                        "note": "",
                    })
                elif "SKIPPED" in line:
                    test_name = line.split("SKIPPED")[0].strip().rstrip(".")
                    result["tests"].append({
                        "test_name": test_name,
                        "status": "skipped",
                        "duration": 0,
                        "note": "",
                    })

        # 如果无法解析统计行，用测试列表推算
        if result["summary"]["total"] == 0:
            result["summary"]["total"] = len(result["tests"])
            result["summary"]["passed"] = sum(1 for t in result["tests"] if t["status"] == "passed")
            result["summary"]["failed"] = sum(1 for t in result["tests"] if t["status"] == "failed")
            result["summary"]["skipped"] = sum(1 for t in result["tests"] if t["status"] == "skipped")

        # 捕获 stderr 中的错误
        if stderr.strip():
            result["errors"].append({
                "module": "unknown",
                "test_name": "stderr_output",
                "error_type": "StderrWarning",
                "error_message": stderr[:1000],
                "traceback": "",
            })

    def _compute_summary(self, total_elapsed: float):
        """计算汇总统计"""
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        for mod_key, mod_data in self.results["modules"].items():
            s = mod_data.get("summary", {})
            total += s.get("total", 0)
            passed += s.get("passed", 0)
            failed += s.get("failed", 0)
            skipped += s.get("skipped", 0)
            errors += s.get("errors", 0)

        self.results["summary"] = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "total_duration_seconds": round(total_elapsed, 1),
            "total_duration_minutes": round(total_elapsed / 60, 1),
            "modules_executed": len(self.results["modules"]),
            "start_time": self.start_time.isoformat() if self.start_time else "",
            "end_time": datetime.now().isoformat(),
        }

        # 生成改进建议
        suggestions = []
        if failed > 0:
            suggestions.append(f"有 {failed} 个测试失败，建议检查失败用例详情并修复")
        if errors > 0:
            suggestions.append(f"有 {errors} 个执行错误，建议检查环境配置和依赖")
        if total_elapsed > self.timeout_minutes * 60:
            suggestions.append("测试执行时间超过预期，建议优化耗时较长的测试用例")
        pass_rate = self.results["summary"]["pass_rate"]
        if pass_rate < 90:
            suggestions.append(f"通过率 {pass_rate}% 低于90%，建议重点关注失败用例")
        elif pass_rate >= 95:
            suggestions.append("测试通过率优秀，可考虑将测试套件集成到 CI/CD 流程")

        self.results["suggestions"] = suggestions

    def _generate_reports(self, total_elapsed: float):
        """生成多格式测试报告"""
        from tests.ai_agent_suite.reporter import generate_report

        suite_info = {
            "total_duration": f"{total_elapsed / 60:.1f} 分钟 ({total_elapsed:.1f} 秒)",
            "modules": self.modules_to_run,
            "start_time": self.start_time.isoformat() if self.start_time else "",
            "end_time": datetime.now().isoformat(),
        }

        report_paths = generate_report(
            test_results=self.results,
            resource_summary=self.resource_summary,
            suite_info=suite_info,
            output_dir=str(self.output_dir / "reports"),
        )

        self.results["report_paths"] = report_paths

    def _save_raw_results(self):
        """保存原始结果 JSON"""
        raw_path = self.output_dir / "raw_results.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        self._log("INFO", f"原始结果已保存: {raw_path}")

    def _is_timeout(self) -> bool:
        """检查是否超时"""
        if self.start_time is None:
            return False
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return elapsed > self.timeout_minutes * 60

    def _log(self, level: str, message: str):
        """统一日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "  ",
            "CHECK": "  [CHECK]",
            "TEST": "    ",
            "WARNING": "  [WARN]",
            "ERROR": "  [ERROR]",
            "DEBUG": "  [DEBUG]",
        }.get(level, "  ")

        if level == "DEBUG" and not self.verbose:
            return

        print(f"[{timestamp}]{prefix} {message}")

    def _print_header(self):
        """打印测试套件头部信息"""
        print("\n" + "=" * 70)
        print("  AI Agent 自动化测试套件 v1.0.0")
        print("  项目: AI 测试用例生成系统")
        print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  执行模块: {', '.join(self.modules_to_run)}")
        print(f"  超时限制: {self.timeout_minutes} 分钟")
        print(f"  输出目录: {self.output_dir}")
        print("=" * 70 + "\n")

    def _print_summary(self):
        """打印最终汇总"""
        summary = self.results["summary"]
        print("\n" + "=" * 70)
        print("  测试执行完成")
        print("=" * 70)
        print(f"  总用例数:     {summary['total']}")
        print(f"  通过:         {summary['passed']} ({summary['pass_rate']}%)")
        print(f"  失败:         {summary['failed']}")
        print(f"  跳过:         {summary['skipped']}")
        print(f"  错误:         {summary['errors']}")
        print(f"  总耗时:       {summary['total_duration_minutes']} 分钟")
        print(f"  结束时间:     {summary['end_time']}")
        print("=" * 70)

        # 报告路径
        if "report_paths" in self.results:
            print("\n  报告文件:")
            for fmt, path in self.results["report_paths"].items():
                print(f"    [{fmt.upper()}] {path}")
            print()

        # 退出码
        if summary["failed"] > 0 or summary["errors"] > 0:
            print("  状态: 存在失败或错误，请检查报告详情\n")
        else:
            print("  状态: 全部通过\n")


# ─── CLI 入口 ───


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="AI Agent 自动化测试编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m tests.ai_agent_suite.orchestrator
  python -m tests.ai_agent_suite.orchestrator --output ./my_reports
  python -m tests.ai_agent_suite.orchestrator --modules pipeline,web_api
  python -m tests.ai_agent_suite.orchestrator --timeout 90 --fail-fast
        """,
    )

    parser.add_argument(
        "--output", "-o",
        default="./output/ai_agent_reports",
        help="报告输出目录 (默认: ./output/ai_agent_reports)",
    )
    parser.add_argument(
        "--modules", "-m",
        default="pipeline,web_api,data",
        help="要执行的模块，逗号分隔 (默认: pipeline,web_api,data)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=120,
        help="总超时时间（分钟）(默认: 120)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="首个失败时立即终止",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="减少输出",
    )

    args = parser.parse_args()

    modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    orchestrator = TestOrchestrator(
        output_dir=args.output,
        modules=modules,
        timeout_minutes=args.timeout,
        verbose=not args.quiet,
        fail_fast=args.fail_fast,
    )

    results = orchestrator.run()

    # 返回退出码
    summary = results["summary"]
    if summary["failed"] > 0 or summary["errors"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

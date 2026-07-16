#!/usr/bin/env python3
"""
测试报告生成器 — 多格式测试结果输出

生成格式：
  - HTML：交互式可视化报告（含图表、折叠详情）
  - JSON：结构化数据（适合 AI 智能体解析）
  - Markdown：人类可读的文本报告

支持将测试结果、资源监控数据、异常信息整合为统一报告。
"""

import json
from datetime import datetime
from pathlib import Path


class TestReporter:
    """测试报告生成器"""

    def __init__(self, output_dir: str = "./output/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.generated_at = datetime.now()
        self.timestamp = self.generated_at.strftime("%Y%m%d_%H%M%S")

    def generate_all(self, test_results: dict, resource_summary: dict,
                     suite_info: dict) -> dict:
        """生成所有格式的报告"""
        paths = {}

        # 生成 JSON 报告
        json_path = self._generate_json(test_results, resource_summary, suite_info)
        paths["json"] = json_path

        # 生成 Markdown 报告
        md_path = self._generate_markdown(test_results, resource_summary, suite_info)
        paths["markdown"] = md_path

        # 生成 HTML 报告
        html_path = self._generate_html(test_results, resource_summary, suite_info)
        paths["html"] = html_path

        print(f"\n{'='*60}")
        print("报告已生成:")
        for fmt, path in paths.items():
            print(f"  [{fmt.upper()}] {path}")
        print(f"{'='*60}\n")

        return paths

    def _generate_json(self, test_results: dict, resource_summary: dict,
                       suite_info: dict) -> str:
        """生成 JSON 格式报告"""
        report = {
            "meta": {
                "title": "AI Agent 自动化测试报告",
                "generated_at": self.generated_at.isoformat(),
                "suite_version": "1.0.0",
                "project": "AI 测试用例生成系统",
            },
            "suite_info": suite_info,
            "results": test_results,
            "resource_monitoring": resource_summary,
        }

        path = self.output_dir / f"test_report_{self.timestamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return str(path)

    def _generate_markdown(self, test_results: dict, resource_summary: dict,
                           suite_info: dict) -> str:
        """生成 Markdown 格式报告"""
        summary = test_results.get("summary", {})
        modules = test_results.get("modules", {})
        details = test_results.get("details", [])
        errors = test_results.get("errors", [])
        suggestions = test_results.get("suggestions", [])

        lines = [
            "# AI Agent 自动化测试报告",
            "",
            f"**生成时间**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "**项目**: AI 测试用例生成系统 v2.0.0",
            f"**总执行时间**: {suite_info.get('total_duration', 'N/A')}",
            "",
            "---",
            "",
            "## 1. 执行概览",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总测试用例 | {summary.get('total', 0)} |",
            f"| 通过 | {summary.get('passed', 0)} |",
            f"| 失败 | {summary.get('failed', 0)} |",
            f"| 跳过 | {summary.get('skipped', 0)} |",
            f"| 错误 | {summary.get('errors', 0)} |",
            f"| 通过率 | {summary.get('pass_rate', 0)}% |",
            f"| 总耗时 | {summary.get('total_duration_minutes', 0)} 分钟 |",
            "",
            "---",
            "",
            "## 2. 模块测试结果",
            "",
        ]

        for mod_name, mod_info in modules.items():
            mod_summary = mod_info.get("summary", {})
            lines.extend([
                f"### 2.{list(modules.keys()).index(mod_name) + 1} {mod_name}",
                "",
                f"- 测试数量: {mod_summary.get('total', 0)}",
                f"- 通过: {mod_summary.get('passed', 0)}",
                f"- 失败: {mod_summary.get('failed', 0)}",
                f"- 耗时: {mod_summary.get('duration_minutes', 0)} 分钟",
                "",
            ])

            # 模块内的测试详情
            mod_tests = mod_info.get("tests", [])
            if mod_tests:
                lines.extend([
                    "| 测试名称 | 状态 | 耗时(s) |",
                    "|---------|------|--------|",
                ])
                for t in mod_tests:
                    status_icon = "PASS" if t["status"] == "passed" else "FAIL" if t["status"] == "failed" else "SKIP"
                    lines.append(f"| {t['test_name']} | {status_icon} | {t['duration']} |")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. 资源监控摘要",
            "",
        ])

        cpu = resource_summary.get("cpu", {})
        mem = resource_summary.get("memory", {})
        proc = resource_summary.get("process", {})
        disk_io = resource_summary.get("disk_io", {})
        net_io = resource_summary.get("net_io", {})

        lines.extend([
            f"- 采样次数: {resource_summary.get('samples', 0)}",
            f"- 监控时长: {resource_summary.get('duration_seconds', 0)} 秒",
            "",
            "### CPU",
            f"- 平均使用率: {cpu.get('avg_percent', 'N/A')}%",
            f"- 峰值使用率: {cpu.get('max_percent', 'N/A')}%",
            "",
            "### 内存",
            f"- 系统平均使用率: {mem.get('avg_percent', 'N/A')}%",
            f"- 系统峰值使用率: {mem.get('max_percent', 'N/A')}%",
            f"- 进程平均 RSS: {proc.get('avg_rss_mb', 'N/A')} MB",
            f"- 进程峰值 RSS: {proc.get('max_rss_mb', 'N/A')} MB",
            "",
        ])

        if disk_io:
            lines.extend([
                "### 磁盘 I/O",
                f"- 累计读取: {disk_io.get('read_mb', 'N/A')} MB",
                f"- 累计写入: {disk_io.get('write_mb', 'N/A')} MB",
                "",
            ])

        if net_io:
            lines.extend([
                "### 网络 I/O",
                f"- 累计发送: {net_io.get('sent_mb', 'N/A')} MB",
                f"- 累计接收: {net_io.get('recv_mb', 'N/A')} MB",
                "",
            ])

        # 错误详情
        if errors:
            lines.extend([
                "---",
                "",
                "## 4. 异常与错误详情",
                "",
            ])
            for i, err in enumerate(errors, 1):
                lines.extend([
                    f"### 4.{i} {err.get('test_name', 'Unknown')}",
                    f"- 模块: {err.get('module', 'N/A')}",
                    f"- 错误类型: {err.get('error_type', 'N/A')}",
                    f"- 错误信息: {err.get('error_message', 'N/A')}",
                    "",
                    "```",
                    err.get('traceback', 'N/A'),
                    "```",
                    "",
                ])

        # 建议
        if suggestions:
            lines.extend([
                "---",
                "",
                "## 5. 改进建议",
                "",
            ])
            for s in suggestions:
                lines.append(f"- {s}")

        lines.extend([
            "",
            "---",
            "",
            "*报告由 AI Agent 自动化测试套件自动生成*",
        ])

        path = self.output_dir / f"test_report_{self.timestamp}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return str(path)

    def _generate_html(self, test_results: dict, resource_summary: dict,
                       suite_info: dict) -> str:
        """生成 HTML 格式报告"""
        summary = test_results.get("summary", {})
        modules = test_results.get("modules", {})
        details = test_results.get("details", [])
        errors = test_results.get("errors", [])

        # 通过率颜色
        pass_rate = summary.get("pass_rate", 0)
        if pass_rate >= 90:
            rate_color = "#22c55e"
        elif pass_rate >= 70:
            rate_color = "#f59e0b"
        else:
            rate_color = "#ef4444"

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Agent 自动化测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.6; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 32px; border-radius: 12px; margin-bottom: 24px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header .meta {{ opacity: 0.85; font-size: 14px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .card h2 {{ font-size: 18px; margin-bottom: 16px; color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .stat {{ background: #f1f5f9; border-radius: 8px; padding: 16px; text-align: center; }}
        .stat .value {{ font-size: 28px; font-weight: 700; }}
        .stat .label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .stat.pass .value {{ color: #22c55e; }}
        .stat.fail .value {{ color: #ef4444; }}
        .stat.error .value {{ color: #f59e0b; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
        th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
        .status-pass {{ color: #22c55e; font-weight: 600; }}
        .status-fail {{ color: #ef4444; font-weight: 600; }}
        .status-skip {{ color: #94a3b8; font-weight: 600; }}
        .status-error {{ color: #f59e0b; font-weight: 600; }}
        .progress-bar {{ width: 100%; height: 24px; background: #e2e8f0; border-radius: 12px; overflow: hidden; margin: 12px 0; }}
        .progress-fill {{ height: 100%; background: {rate_color}; border-radius: 12px; transition: width 0.3s; }}
        .error-detail {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin: 8px 0; }}
        .error-detail pre {{ font-size: 12px; overflow-x: auto; white-space: pre-wrap; margin-top: 8px; }}
        .resource-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
        .resource-item {{ background: #f8fafc; border-radius: 8px; padding: 12px; }}
        .resource-item .title {{ font-size: 12px; color: #64748b; margin-bottom: 4px; }}
        .resource-item .value {{ font-size: 18px; font-weight: 600; }}
        .footer {{ text-align: center; color: #94a3b8; font-size: 12px; padding: 24px 0; }}
        .collapsible {{ cursor: pointer; user-select: none; }}
        .collapsible:hover {{ background: #f1f5f9; }}
        .hidden {{ display: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Agent 自动化测试报告</h1>
            <div class="meta">
                生成时间: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')} |
                项目: AI 测试用例生成系统 v2.0.0 |
                总耗时: {suite_info.get('total_duration', 'N/A')}
            </div>
        </div>

        <div class="card">
            <h2>执行概览</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_rate}%"></div>
            </div>
            <div style="text-align: center; font-size: 14px; color: #64748b; margin-bottom: 16px;">
                通过率: <strong style="color: {rate_color}">{pass_rate}%</strong>
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="value">{summary.get('total', 0)}</div>
                    <div class="label">总用例数</div>
                </div>
                <div class="stat pass">
                    <div class="value">{summary.get('passed', 0)}</div>
                    <div class="label">通过</div>
                </div>
                <div class="stat fail">
                    <div class="value">{summary.get('failed', 0)}</div>
                    <div class="label">失败</div>
                </div>
                <div class="stat error">
                    <div class="value">{summary.get('errors', 0)}</div>
                    <div class="label">错误</div>
                </div>
                <div class="stat">
                    <div class="value">{summary.get('skipped', 0)}</div>
                    <div class="label">跳过</div>
                </div>
                <div class="stat">
                    <div class="value">{summary.get('total_duration_minutes', 0)}min</div>
                    <div class="label">总耗时</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>模块测试结果</h2>
"""

        for mod_name, mod_info in modules.items():
            mod_summary = mod_info.get("summary", {})
            mod_pass_rate = mod_summary.get("pass_rate", 0)
            html += f"""
            <h3 style="margin-top: 16px;">{mod_name} ({mod_summary.get('total', 0)} 用例, 通过率 {mod_pass_rate}%)</h3>
            <table>
                <tr><th>测试名称</th><th>状态</th><th>耗时(s)</th><th>备注</th></tr>"""

            for t in mod_info.get("tests", []):
                status_class = f"status-{t['status']}"
                status_text = t["status"].upper()
                note = t.get("note", "")
                html += f"""
                <tr>
                    <td>{t['test_name']}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{t['duration']}</td>
                    <td>{note}</td>
                </tr>"""

            html += "</table>"

        html += """
        </div>

        <div class="card">
            <h2>资源监控摘要</h2>
            <div class="resource-grid">
"""

        cpu = resource_summary.get("cpu", {})
        mem = resource_summary.get("memory", {})
        proc = resource_summary.get("process", {})
        disk_io = resource_summary.get("disk_io", {})
        net_io = resource_summary.get("net_io", {})

        html += f"""
                <div class="resource-item">
                    <div class="title">CPU 平均使用率</div>
                    <div class="value">{cpu.get('avg_percent', 'N/A')}%</div>
                </div>
                <div class="resource-item">
                    <div class="title">CPU 峰值</div>
                    <div class="value">{cpu.get('max_percent', 'N/A')}%</div>
                </div>
                <div class="resource-item">
                    <div class="title">系统内存平均</div>
                    <div class="value">{mem.get('avg_percent', 'N/A')}%</div>
                </div>
                <div class="resource-item">
                    <div class="title">进程 RSS 峰值</div>
                    <div class="value">{proc.get('max_rss_mb', 'N/A')} MB</div>
                </div>
                <div class="resource-item">
                    <div class="title">磁盘写入</div>
                    <div class="value">{disk_io.get('write_mb', 'N/A')} MB</div>
                </div>
                <div class="resource-item">
                    <div class="title">网络接收</div>
                    <div class="value">{net_io.get('recv_mb', 'N/A')} MB</div>
                </div>
                <div class="resource-item">
                    <div class="title">采样次数</div>
                    <div class="value">{resource_summary.get('samples', 0)}</div>
                </div>
                <div class="resource-item">
                    <div class="title">监控时长</div>
                    <div class="value">{resource_summary.get('duration_seconds', 0)}s</div>
                </div>
"""

        html += """
            </div>
        </div>
"""

        # 错误详情
        if errors:
            html += """
        <div class="card">
            <h2>异常与错误详情</h2>
"""
            for i, err in enumerate(errors, 1):
                html += f"""
            <div class="error-detail">
                <strong>#{i} {err.get('test_name', 'Unknown')}</strong>
                <div>模块: {err.get('module', 'N/A')} | 类型: {err.get('error_type', 'N/A')}</div>
                <div>错误: {err.get('error_message', 'N/A')}</div>
                <pre>{err.get('traceback', 'N/A')}</pre>
            </div>"""
            html += """
        </div>"""

        html += f"""
        <div class="footer">
            <p>AI Agent 自动化测试套件 v1.0.0 | 报告生成于 {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""

        path = self.output_dir / f"test_report_{self.timestamp}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return str(path)


def generate_report(test_results: dict, resource_summary: dict,
                    suite_info: dict, output_dir: str = "./output/reports") -> dict:
    """便捷函数：生成测试报告"""
    reporter = TestReporter(output_dir=output_dir)
    return reporter.generate_all(test_results, resource_summary, suite_info)

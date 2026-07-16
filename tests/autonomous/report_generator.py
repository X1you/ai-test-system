#!/usr/bin/env python3
"""
报告生成器 — 生成 HTML 测试报告和 JSON 数据文件。

输出：
  - report.html：可交互的 HTML 报告（含图表）
  - report.json：结构化测试数据
  - resource_chart.json：资源使用时间序列
"""

import json
from pathlib import Path


class ReportGenerator:
    """测试报告生成器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        phases: list[tuple[str, list]],       # [(phase_name, [TestResult.to_dict()])]
        resource_summary: dict,
        config: dict,
        start_time: str,
        end_time: str,
        total_duration_sec: float,
    ):
        """生成完整报告"""
        # 1. 汇总统计
        all_results = []
        phase_stats = []
        for phase_name, results in phases:
            counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "warning": 0}
            phase_duration = 0.0
            for r in results:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
                phase_duration += r["duration_ms"]
                all_results.append(r)

            total = len(results)
            passed = counts["passed"] + counts["warning"]
            pass_rate = (passed / total * 100) if total > 0 else 0

            phase_stats.append({
                "name": phase_name,
                "total": total,
                "passed": passed,
                "failed": counts["failed"],
                "error": counts["error"],
                "skipped": counts["skipped"],
                "warning": counts["warning"],
                "pass_rate": round(pass_rate, 1),
                "duration_ms": round(phase_duration, 0),
            })

        total_tests = len(all_results)
        total_passed = sum(1 for r in all_results if r["status"] in ("passed", "warning"))
        total_failed = sum(1 for r in all_results if r["status"] == "failed")
        total_error = sum(1 for r in all_results if r["status"] == "error")
        overall_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        report_data = {
            "meta": {
                "start_time": start_time,
                "end_time": end_time,
                "duration_sec": round(total_duration_sec, 1),
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_error": total_error,
                "pass_rate": round(overall_rate, 1),
            },
            "phases": phase_stats,
            "results": all_results,
            "resources": resource_summary,
            "config": config,
        }

        # 2. 保存 JSON
        json_path = self.output_dir / "report.json"
        json_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 3. 生成 HTML
        html = self._generate_html(report_data)
        html_path = self.output_dir / "report.html"
        html_path.write_text(html, encoding="utf-8")

        return {
            "json_path": str(json_path),
            "html_path": str(html_path),
            "summary": report_data["meta"],
        }

    def _generate_html(self, data: dict) -> str:
        """生成 HTML 报告"""
        meta = data["meta"]
        phases = data["phases"]
        results = data["results"]
        resources = data.get("resources", {})

        # 资源图表数据
        res_samples = resources.get("samples", [])
        cpu_data = [s["cpu"] for s in res_samples]
        mem_data = [s["mem_mb"] for s in res_samples]
        time_labels = [f"{s['elapsed']:.0f}s" for s in res_samples]

        # 失败/错误用例详情
        failed_results = [r for r in results if r["status"] in ("failed", "error")]

        status_colors = {
            "passed": "#28a745", "warning": "#ffc107", "failed": "#dc3545",
            "error": "#6f42c1", "skipped": "#6c757d",
        }

        phase_rows = ""
        for p in phases:
            rate_color = "#28a745" if p["pass_rate"] >= 95 else ("#ffc107" if p["pass_rate"] >= 80 else "#dc3545")
            phase_rows += f"""
            <tr>
                <td>{p['name']}</td>
                <td>{p['total']}</td>
                <td style="color:#28a745">{p['passed']}</td>
                <td style="color:#dc3545">{p['failed']}</td>
                <td style="color:#6f42c1">{p['error']}</td>
                <td>{p['warning']}</td>
                <td style="color:{rate_color};font-weight:bold">{p['pass_rate']}%</td>
                <td>{p['duration_ms']/1000:.1f}s</td>
            </tr>"""

        failed_rows = ""
        for r in failed_results[:50]:  # 最多显示 50 条
            color = status_colors.get(r["status"], "#666")
            error_text = (r.get("error") or r.get("detail") or "")[:200]
            error_text = error_text.replace("<", "&lt;").replace(">", "&gt;")
            failed_rows += f"""
            <tr>
                <td><span style="color:{color}">●</span> {r['test_id']}</td>
                <td>{r['name']}</td>
                <td>{r['phase']}</td>
                <td style="color:{color}">{r['status']}</td>
                <td>{r['duration_ms']:.0f}ms</td>
                <td style="font-size:12px;color:#666">{error_text}</td>
            </tr>"""

        overall_color = "#28a745" if meta["pass_rate"] >= 95 else ("#ffc107" if meta["pass_rate"] >= 80 else "#dc3545")
        duration_min = meta["duration_sec"] / 60

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>自主测试报告 — {meta['start_time'][:19]}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .meta {{ font-size: 14px; opacity: 0.9; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
        .card .number {{ font-size: 36px; font-weight: bold; margin: 8px 0; }}
        .card .label {{ font-size: 13px; color: #888; text-transform: uppercase; }}
        .section {{ background: white; padding: 24px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; }}
        .section h2 {{ font-size: 20px; margin-bottom: 16px; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .chart-container {{ position: relative; height: 200px; margin: 20px 0; }}
        .progress-bar {{ height: 24px; background: #e9ecef; border-radius: 12px; overflow: hidden; margin: 10px 0; }}
        .progress-fill {{ height: 100%; border-radius: 12px; transition: width 0.5s; }}
        .resource-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
        .resource-item {{ background: #f8f9fa; padding: 12px; border-radius: 8px; }}
        .resource-item .val {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .resource-item .lbl {{ font-size: 12px; color: #888; }}
        .footer {{ text-align: center; padding: 20px; color: #999; font-size: 13px; }}
        canvas {{ max-width: 100%; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🤖 自主测试报告</h1>
        <div class="meta">
            AI 测试用例生成系统 v2.0.0 |
            {meta['start_time'][:19]} → {meta['end_time'][:19]} |
            总耗时 {duration_min:.1f} 分钟
        </div>
    </div>

    <div class="cards">
        <div class="card"><div class="label">总测试数</div><div class="number">{meta['total_tests']}</div></div>
        <div class="card"><div class="label">✅ 通过</div><div class="number" style="color:#28a745">{meta['total_passed']}</div></div>
        <div class="card"><div class="label">❌ 失败</div><div class="number" style="color:#dc3545">{meta['total_failed']}</div></div>
        <div class="card"><div class="label">⚡ 错误</div><div class="number" style="color:#6f42c1">{meta['total_error']}</div></div>
        <div class="card"><div class="label">通过率</div><div class="number" style="color:{overall_color}">{meta['pass_rate']}%</div></div>
    </div>

    <div class="section">
        <h2>📊 各阶段执行结果</h2>
        <table>
            <thead><tr><th>阶段</th><th>总数</th><th>通过</th><th>失败</th><th>错误</th><th>警告</th><th>通过率</th><th>耗时</th></tr></thead>
            <tbody>{phase_rows}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>📈 资源使用</h2>
        <div class="resource-grid">
            <div class="resource-item"><div class="lbl">峰值 CPU</div><div class="val">{resources.get('peak_cpu', 0)}%</div></div>
            <div class="resource-item"><div class="lbl">峰值内存</div><div class="val">{resources.get('peak_mem_mb', 0)} MB</div></div>
            <div class="resource-item"><div class="lbl">平均 CPU</div><div class="val">{resources.get('avg_cpu', 0)}%</div></div>
            <div class="resource-item"><div class="lbl">平均内存</div><div class="val">{resources.get('avg_mem_mb', 0)} MB</div></div>
            <div class="resource-item"><div class="lbl">峰值线程</div><div class="val">{resources.get('peak_threads', 0)}</div></div>
            <div class="resource-item"><div class="lbl">采样点</div><div class="val">{resources.get('sample_count', 0)}</div></div>
        </div>
        <div class="chart-container">
            <canvas id="resourceChart"></canvas>
        </div>
    </div>
"""

        if failed_results:
            html += f"""
    <div class="section">
        <h2>🔍 失败/错误用例详情 ({len(failed_results)} 条)</h2>
        <table>
            <thead><tr><th>ID</th><th>名称</th><th>阶段</th><th>状态</th><th>耗时</th><th>详情</th></tr></thead>
            <tbody>{failed_rows}</tbody>
        </table>
    </div>
"""

        html += """
    <div class="footer">
        本报告由自主测试系统自动生成 | ai-test-system v2.0.0
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
"""
        if cpu_data:
            chart_js = """
    const ctx = document.getElementById('resourceChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: LABELS,
            datasets: [{
                label: 'CPU (%)',
                data: CPU_DATA,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102,126,234,0.1)',
                yAxisID: 'y',
            }, {
                label: '内存 (MB)',
                data: MEM_DATA,
                borderColor: '#764ba2',
                backgroundColor: 'rgba(118,75,162,0.1)',
                yAxisID: 'y1',
            }]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'CPU %' } },
                y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'MB' }, grid: { drawOnChartArea: false } },
            }
        }
    });
"""
            chart_js = chart_js.replace("LABELS", json.dumps(time_labels))
            chart_js = chart_js.replace("CPU_DATA", json.dumps(cpu_data))
            chart_js = chart_js.replace("MEM_DATA", json.dumps(mem_data))
            html += chart_js

        html += """
</script>
</body>
</html>"""
        return html

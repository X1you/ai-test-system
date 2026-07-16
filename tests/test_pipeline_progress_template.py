#!/usr/bin/env python3
"""
pipeline_progress.html 渲染测试
覆盖 5 种状态 × 不同字段组合，验证：
  · 模板不抛异常
  · 关键节点存在
  · 不会因为字段缺失/类型错误导致渲染中断
"""
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path("/Users/x1you/Documents/ai-test-system")
TEMPLATE_DIR = PROJECT_ROOT / "web" / "templates"


def make_progress(status="running", steps=None, logs=None, llm_stats=None,
                  error="", percent=0, pipeline_id="abc12345"):
    if steps is None:
        names = {1: "需求分析", 2: "知识库检索", 3: "测试点梳理", 4: "生成用例",
                 5: "用例评审", 6: "执行测试", 7: "生成报告"}
        steps = []
        for sid in range(1, 8):
            if status == "running" and sid == 3:
                steps.append({"id": sid, "name": names[sid], "status": "running",
                              "detail": "正在生成…"})
            elif sid <= 2 and status in ("running", "paused", "done", "error", "cancelled"):
                steps.append({"id": sid, "name": names[sid], "status": "done",
                              "detail": "已完成"})
            else:
                steps.append({"id": sid, "name": names[sid], "status": "pending",
                              "detail": ""})
    if logs is None and status in ("running", "paused", "done", "error"):
        logs = [
            {"ts": "10:00:01", "level": "STEP",  "msg": "Pipeline 启动"},
            {"ts": "10:00:05", "level": "OK",    "msg": "需求分析完成"},
            {"ts": "10:00:08", "level": "WARN",  "msg": "检测到模糊点"},
            {"ts": "10:00:12", "level": "ERR",   "msg": "知识库连接超时"},
            {"ts": "10:00:15", "level": "HUMAN", "msg": "等待人工确认"},
            {"ts": "10:00:18", "level": "FOO",   "msg": "未知级别应当回退 neutral"},
        ]
    return {
        "pipeline_id": pipeline_id,
        "status": status,
        "percent": percent,
        "completed_steps": [s for s in steps if s["status"] == "done"],
        "steps": steps,
        "logs": logs or [],
        "llm_stats": llm_stats,
        "error": error,
        "started_at": "2026-07-15T10:00:00",
    }


CASES = [
    # (name, progress, must_contain_substrings, must_NOT_contain)
    ("running-with-stats", make_progress(
        status="running", percent=29,
        llm_stats={"call_count": 12, "total_tokens": 12345, "model": "deepseek-v4-flash"},
    ), [
        'role="progressbar"',
        'aria-valuenow="29"',
        'class="badge badge-info"',
        '调用次数',
        '>12<',                # 12 被 stat-value 包住
        '12,345',              # 千分位格式化
        'deepseek-v4-flash',
        'log-level-step',
        'log-level-human',
        'log-level-neutral',
        'role="log"',
        'STICK_TO_BOTTOM_THRESHOLD',
        'requestAnimationFrame',
    ], []),
    ("paused-with-upload", make_progress(
        status="paused", percent=86,
    ), [
        '等待人工执行',
        'id="resume-upload-zone"',
        'hx-post="/api/pipeline/abc12345/resume"',
        "onclick=\"cancelPipeline('abc12345')\"",
        'btn-outline-danger',
        '取消任务',
        '继续执行',
    ], []),
    ("done", make_progress(status="done", percent=100), [
        'Pipeline 执行完成',
        'href="/results/abc12345"',
        'class="badge badge-success"',
        'progress-bar-fill success',
    ], []),
    ("error-traceback", make_progress(
        status="error", percent=43,
        error="Traceback (most recent call last):\n  File 'a.py', line 1\n    raise ValueError('x' * 500)\n" + "long line " * 50,
    ), [
        '执行出错',
        '<pre',
        'white-space:pre-wrap',
        'max-height:240px',
        'progress-bar-fill error',
        '重新启动',
        '任务列表',
    ], []),
    ("error-no-message", make_progress(status="error", percent=10, error=""), [
        '执行出错',
        'details',  # 即使无错误也保留 details 容器
    ], []),
    ("cancelled", make_progress(status="cancelled", percent=29), [
        'Pipeline 已取消',
        '查看产物',
        '返回首页',
    ], []),
    ("no-llm-stats", make_progress(status="running", percent=14,
                                    llm_stats={"call_count": 0, "total_tokens": 0, "model": ""}),
     # call_count==0 时不应展示 LLM 统计
     ['执行中'], ['调用次数']),
    ("missing-llm-stats", make_progress(status="running", percent=14, llm_stats=None),
     ['执行中'], ['调用次数']),
    ("no-logs", make_progress(status="running", percent=0, logs=[]),
     # logs 为空时不应渲染 details.panel
     ['执行中'], ['details class="panel"']),
    ("unknown-status", make_progress(status="initializing", percent=0),
     # 未知 status 应当回退到"等待中"显示
     ['等待中', 'role="progressbar"'], []),
]


def main():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("pipeline_progress.html")
    failures = []
    passes = 0
    for name, progress, must_contain, must_not_contain in CASES:
        case_failures = []
        try:
            html = tpl.render(progress=progress)
        except Exception as e:
            case_failures.append(f"    render error: {e}")
            html = ""
        for s in must_contain:
            if s not in html:
                case_failures.append(f"    missing substring: {s!r}")
        for s in must_not_contain:
            if s in html:
                case_failures.append(f"    unexpected substring: {s!r}")
        if case_failures:
            failures.append(f"  ❌ [{name}]")
            failures.extend(case_failures)
        else:
            passes += 1
            print(f"  ✅ [{name}] passed ({len(html)} bytes)")
    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f)
        sys.exit(1)
    print(f"All {passes}/{len(CASES)} cases passed.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
端到端测试（进程内）：使用 FastAPI TestClient 直接调用应用，
避免单例跨进程问题。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path("/Users/x1you/Documents/ai-test-system")))
os.environ.setdefault("LLM_API_KEY", "sk-test-dummy")

from fastapi.testclient import TestClient

from web.app import app
from web.services.task_manager import get_task_manager

client = TestClient(app)

# ─── Case 1: paused 状态 ───
tm = get_task_manager()
task = tm.create_task(
    config={"llm": {"provider": "deepseek", "api_key": "sk-test", "model": "deepseek-v4-flash"}},
    requirements_path="/tmp/test_requirements.md",
    mode="semi",
    dimensions="basic",
    formats="excel",
)
# 中止后台线程的 mock 启动（不让它真的跑 Pipeline）
# task_manager.create_task 内部会调 start_background, 我们直接覆盖状态
task._thread = None  # 阻止实际跑
task.completed_steps = [1, 2, 3, 4, 5]
task.step_details = {
    1: {"data": {"modules": 3, "features": 8}},
    2: {"data": {"hits": 5}},
    3: {"data": {"count": 24}},
    4: {"data": {"case_count": 24}},
    5: {"data": {"score": 87}},
}
task.logs = [
    {"ts": "10:00:01", "level": "STEP",  "msg": "Pipeline 启动"},
    {"ts": "10:00:08", "level": "OK",    "msg": "需求分析完成"},
    {"ts": "10:00:12", "level": "WARN",  "msg": "检测到模糊点"},
    {"ts": "10:00:18", "level": "HUMAN", "msg": "等待人工确认"},
    {"ts": "10:00:20", "level": "FOO",   "msg": "未知级别测试"},
]
task.llm_stats = {"call_count": 12, "total_tokens": 12345, "model": "deepseek-v4-flash"}
task.status = "paused"

# 请求 1: paused 状态
r = client.get(f"/api/pipeline/{task.pipeline_id}/progress",
               headers={"HX-Request": "true"})
print(f"[paused] HTTP {r.status_code}, {len(r.text)} bytes")
assert r.status_code == 200, r.text

CHECKS_PASS = [
    ('aria-valuenow="71"',          '进度 5/7=71%'),
    ('role="progressbar"',          '进度条 ARIA'),
    ('等待人工执行',                  'paused 文案'),
    ('scope="col"',                 'th 用 scope'),
    ('3 模块 8 功能点',                'step 1 详情'),
    ('命中 5 条',                     'step 2 详情'),
    ('24 个测试点',                   'step 3 详情'),
    ('24 条用例',                     'step 4 详情'),
    ('评分 87/100',                   'step 5 详情'),
    ('role="log"',                   '日志 ARIA'),
    ('log-level-step',               'STEP 级别'),
    ('log-level-human',              'HUMAN 级别'),
    ('log-level-warn',               'WARN 级别'),
    ('log-level-neutral',            'FOO 未知级别 → neutral'),
    ('12,345',                       '千分位'),
    ('deepseek-v4-flash',            '模型名'),
    ('id="resume-upload-zone"',      '上传区 ID'),
    ('aria-label="取消当前 Pipeline"', '取消按钮 aria-label'),
    ('onclick="cancelPipeline',       '取消按钮 onclick'),
    ('hx-post="/api/pipeline/',       'HTMX 提交'),
    ('STICK_TO_BOTTOM_THRESHOLD',     '日志滚动守卫'),
    ('requestAnimationFrame',        '异步滚动'),
    ('initUploadZone',                '复用 app.js 工具'),
]
CHECKS_NEG = [
    ('<pre',                          'paused 状态不应有 <pre> 错误块'),
    ('执行出错',                       'paused 状态不应有错误文案'),
]

fail = []
for sub, desc in CHECKS_PASS:
    if sub in r.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (missing {sub!r})")
        fail.append(desc)
for sub, desc in CHECKS_NEG:
    if sub not in r.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (unexpected {sub!r})")
        fail.append(desc)

# ─── Case 2: error 状态 ───
task.status = "error"
task.error = "Traceback (most recent call last):\n  File 'x.py', line 1\n    raise ValueError('boom')"
r2 = client.get(f"/api/pipeline/{task.pipeline_id}/progress",
                headers={"HX-Request": "true"})
print(f"\n[error] HTTP {r2.status_code}, {len(r2.text)} bytes")
assert r2.status_code == 200

for sub, desc in [
    ('执行出错',                'error 标题'),
    ('progress-bar-fill error', 'error 进度条样式'),
    ('重新启动',                 '重新启动按钮'),
    ('任务列表',                 '任务列表按钮'),
    ('<pre',                    '错误 <pre> 折叠'),
    ('white-space:pre-wrap',    'pre-wrap 排版'),
    ('max-height:240px',        '错误折叠高度限制'),
]:
    if sub in r2.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (missing {sub!r})")
        fail.append(desc)
for sub, desc in [
    ('id="resume-upload-zone"', 'error 状态不应有 resume 上传区'),
    ('aria-label="取消当前 Pipeline"', 'error 状态不应有取消按钮'),
]:
    if sub not in r2.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (unexpected {sub!r})")
        fail.append(desc)

# ─── Case 3: cancelled 状态 ───
task.status = "cancelled"
r3 = client.get(f"/api/pipeline/{task.pipeline_id}/progress",
                headers={"HX-Request": "true"})
print(f"\n[cancelled] HTTP {r3.status_code}, {len(r3.text)} bytes")
assert r3.status_code == 200

for sub, desc in [
    ('Pipeline 已取消',     'cancelled 标题'),
    ('查看产物',             '查看产物按钮'),
    ('progress-bar-fill error', 'cancelled 用 error 样式'),
    ('返回首页',             '返回首页按钮'),
]:
    if sub in r3.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (missing {sub!r})")
        fail.append(desc)
for sub, desc in [
    ('id="resume-upload-zone"', 'cancelled 不应有 resume 上传区'),
    ('aria-label="重新启动"', 'cancelled 不应有"重新启动"按钮'),
    ('aria-label="下载测试用例 Excel"', 'cancelled 不应有下载按钮'),
]:
    if sub not in r3.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (unexpected {sub!r})")
        fail.append(desc)

# ─── Case 4: done 状态 ───
task.status = "done"
task.completed_steps = [1, 2, 3, 4, 5, 6, 7]
r4 = client.get(f"/api/pipeline/{task.pipeline_id}/progress",
                headers={"HX-Request": "true"})
print(f"\n[done] HTTP {r4.status_code}, {len(r4.text)} bytes")
assert r4.status_code == 200

for sub, desc in [
    ('aria-valuenow="100"',         '100%'),
    ('Pipeline 执行完成',            'done 标题'),
    ('progress-bar-fill success',   'done 进度条 success 样式'),
    ('href="/results/',             '查看结果链接'),
]:
    if sub in r4.text:
        print(f"  ✅ {desc}")
    else:
        print(f"  ❌ {desc}  (missing {sub!r})")
        fail.append(desc)

print("\n" + "=" * 60)
if fail:
    print(f"❌ {len(fail)} 个检查未通过:")
    for f in fail:
        print(f"   - {f}")
    sys.exit(1)
print("✅ E2E 端到端测试全部通过（4 种状态 × 关键检查点）")

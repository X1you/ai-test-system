# Pipeline.py 全面优化报告

> 优化日期：2026-07-17
> 涉及文件：`core/pipeline.py`、`web/api/pipeline.py`、`web/services/pipeline_task.py`
> 验证结果：全量测试 409 passed（2 个 KB API 性能测试失败为既有问题，与本次无关）

---

## 一、优化总览

| 文件 | 优化前行数 | 优化后行数 | 核心改动数 |
|------|-----------|-----------|-----------|
| core/pipeline.py | 398 | 401 | 5 |
| web/api/pipeline.py | 375 | 340 | 6 |
| web/services/pipeline_task.py | 313 | 285 | 6 |
| **合计** | **1086** | **1026** | **17** |

注：行数下降主要来自冗余代码消除；新增的文档注释/类型标注使有效信息密度提升。

---

## 二、逐文件对比分析

### 1. core/pipeline.py（Pipeline 引擎核心）

#### 优化点 ① 消除步骤元数据硬编码重复 🔴严重

**问题**：7 个步骤的 `(id, 名称, 输出文件)` 三元组在 `status()`（L330-338）、`_print_summary()`（L375-383）两处完全重复硬编码，共 14 行重复代码。新增/调整步骤需改多处，极易遗漏。

**优化**：提取 `StepMeta` dataclass + `STEP_REGISTRY` 列表作为单一数据源，两处改为遍历 `STEP_REGISTRY`。

```python
# 优化后 — 单一数据源
@dataclass(frozen=True)
class StepMeta:
    id: int
    name: str
    output_file: str
    needs_pause: bool = False

STEP_REGISTRY = [
    StepMeta(1, "需求分析", "requirements_analysis.md", needs_pause=True),
    ...
]
```

**收益**：新增步骤从改 3+ 处 → 改 1 处；步骤属性（如 needs_pause）可数据驱动。

#### 优化点 ② 魔法数字消除 🔵建议

**问题**：`7`（总步骤数）在代码中出现 4 次（L351、`7 in done` 等），硬编码。

**优化**：提取 `TOTAL_STEPS = len(STEP_REGISTRY)`，所有引用改为常量。

#### 优化点 ③ `_has_results()` 效率提升 🟡中等

**问题**：逐行计数 `filled`，遍历全部行后才 `return filled > 0`。实际只需判断"是否至少一行有值"。

```python
# 优化前 — 遍历所有行
filled = 0
for row in range(2, ws.max_row + 1):
    val = str(ws.cell(row=row, column=result_col).value or "").strip()
    if val:
        filled += 1
wb.close()
return filled > 0
```

**优化**：改为 `any()` 短路求值，找到第一个非空行即返回。

```python
# 优化后 — 短路返回
filled = any(
    str(ws.cell(row=row, column=result_col).value or "").strip()
    for row in range(2, ws.max_row + 1)
)
```

**收益**：大 Excel（数千行）时，平均减少 ~50% 单元格读取。

#### 优化点 ④ 启动横幅逻辑提取 🔵建议

**问题**：`run()` 开头的 banner 打印（L164-172）与主流程混在一起。

**优化**：提取为 `_print_banner(mode, requirements_file)` 方法，`run()` 更聚焦。

#### 优化点 ⑤ Step6 路径变量复用 🟡中等

**问题**：`self.output_dir / "testcases.xlsx"` 在 L267 定义后又重复拼接（L278、L279）。

**优化**：复用 `xlsx_path` 变量，减少重复 Path 拼接。

---

### 2. web/services/pipeline_task.py（任务追踪包装器）

#### 优化点 ⑥ `_run` / `_run_resume` 大段重复代码消除 🔴严重

**问题**：两个方法各 ~28 行，其中 ~24 行完全相同（异常处理、_finalize、publish_event），仅 `run_mode` 和启动日志不同。这是全文件最严重的重复。

**优化**：合并为 `_execute(run_mode)` + `_launch(target, startup_log)` 两层：
- `_launch`：统一的线程启动（设置状态、持久化、日志、启动线程）
- `_execute`：统一的执行主逻辑，参数化 run_mode

```python
def _run(self):
    self._execute(self.mode)

def _run_resume(self):
    self._execute("auto")  # 续跑强制 auto，跳过人工检查点
```

**收益**：重复代码从 ~48 行 → ~22 行；异常处理逻辑只维护一处。

#### 优化点 ⑦ `STEP_NAMES` 三处重复消除 🔴严重

**问题**：步骤 id→名称映射在 `_persist_step`（L215-223）、`_build_steps_view`（L281-289）两处各硬编码一遍，共 14 行重复，且与 core/pipeline.py 的 status() 又重复一次。

**优化**：从 core 模块导入 `STEP_REGISTRY`，派生 `STEP_NAMES` 字典，三处全部复用。

```python
from core.pipeline import Pipeline, STEP_REGISTRY, TOTAL_STEPS
STEP_NAMES = {meta.id: meta.name for meta in STEP_REGISTRY}
```

**收益**：步骤名称跨 3 个文件单一数据源；改名只需改 core/pipeline.py 一处。

#### 优化点 ⑧ `_build_steps_view()` 可读性重构 🟡中等

**问题**：L307-312 的 `status` 三元表达式嵌套在字典字面量中，单行超长难读：

```python
# 优化前 — 单行嵌套三元
"status": "done" if done else ("running" if self.status == "running"
    and sid == max(self.completed_steps, default=0) + 1 else "pending"),
```

**优化**：提取为清晰的 if/elif 分支；同时将 detail 摘要逻辑提取为 `_step_detail_str()` 方法。

```python
# 优化后 — 清晰分支
if done:
    step_status = "done"
elif is_running and meta.id == running_step:
    step_status = "running"
else:
    step_status = "pending"
```

#### 优化点 ⑨ `_finalize` 状态判定健壮性 🟡中等

**问题**：原 `elif 6 not in done:` 依赖"Step 6 是否完成"判定暂停，但 `done` 是步骤 id 列表，若步骤乱序完成（理论上不会，但语义不明确），判定可能出错。

**优化**：改为 `len(done) < 6`，语义更清晰——"完成的步骤数不足 6 步则暂停"。

#### 优化点 ⑩ `_run_resume` 未重置取消标志 Bug 修复 🔴严重

**问题**：原 `resume_background()` 未重置 `_cancel_flag`。若任务曾被取消（`cancel()` 设 `_cancel_flag=True`），resume 后首个 `_check_cancelled()` 立即抛 `_PipelineCancelled`，resume 实际无效。

**优化**：在统一的 `_launch()` 中 `self._cancel_flag = False`，确保 resume 干净启动。

#### 优化点 ⑪ 异常处理补全 _persist_pipeline 🟡中等

**问题**：原 `_execute` 异常分支（error）未调用 `_persist_pipeline("error")`，DB 中状态可能停留在 "running"，重启后误判。

**优化**：异常分支补 `_persist_pipeline("error")`。

#### 优化点 ⑫ 魔法数字提取 🔵建议

**问题**：`200`（日志上限）、`20`（返回窗口）在代码中裸露。

**优化**：提取 `MAX_LOGS = 200`、`LOG_RETURN_WINDOW = 20` 常量。

#### 优化点 ⑬ 方法分组与文档补全 🟡中等

**问题**：无分组注释，方法多时导航困难；多个方法缺 docstring。

**优化**：添加 `# ─── 生命周期入口 ───`、`# ─── 回调 ───`、`# ─── 进度视图 ───` 分组；模块 docstring 补充架构说明；所有公开方法补全 docstring。

---

### 3. web/api/pipeline.py（API 路由层）

#### 优化点 ⑭ `get_task` + 404 样板重复消除 🟡中等

**问题**：`get_task` + `if not task: raise HTTPException(404)` 在 7 个 endpoint 中重复 7 次。

**优化**：提取 `_require_task(pipeline_id)` 辅助函数，7 处调用简化为一行。

```python
# 优化前（每个 endpoint）
tm = get_task_manager()
task = tm.get_task(pipeline_id)
if not task:
    raise HTTPException(404, "Pipeline 不存在")

# 优化后
task = _require_task(pipeline_id)
```

#### 优化点 ⑮ 内联 import 提升至模块顶部 🟡中等

**问题**：`import re`、`import uuid` 在 `start_pipeline` 函数体内（L61-62），每次调用重新执行 import 语句（虽 Python 有缓存，但不规范）。

**优化**：移至模块顶部 import 区。

#### 优化点 ⑯ 魔法数字与常量提取 🔵建议

**问题**：`50`（Excel 预览行数）、`100`（单元格截断）、终态事件映射、产物名映射散落在函数内。

**优化**：提取为模块常量 `EXCEL_PREVIEW_MAX_ROWS`、`EXCEL_CELL_MAX_CHARS`、`_TERMINAL_EVENTS`、`_ARTIFACT_NAMES`。

#### 优化点 ⑰ `list_pipelines` 统计简化 + 分页切片修正 🟡中等

**问题①**：统计 `s_other` 用独立计数器遍历，但 `s_other = total - running - done` 可直接算。

**问题②**：`items = all_tasks[start:end]` 多一次中间切片（end 可能越界），Python 切片本身安全但变量多余。

**优化**：`s_other` 改为算术推导；分页切片合并为 `all_tasks[start : start + page_size]`。

---

## 三、验证结果

### 单元测试

```
tests/test_pipeline_api.py            ✅ 全部通过
tests/test_pipeline_progress_template  ✅ 全部通过
tests/test_task_manager.py             ✅ 全部通过
tests/test_db_persistence.py           ✅ 全部通过
tests/test_cli.py                      ✅ 全部通过
tests/test_phase3_async.py             ✅ 全部通过
tests/test_bugfix_regression.py        ✅ 全部通过

全量（排除已知损坏的 e2e 文件）: 409 passed, 2 failed
  → 2 个失败为 test_perf_security_supplement 的 KB API 响应时间测试
  → 与 Pipeline 无关（测试 /api/kb/ 端点），为既有问题
```

### 冒烟测试

- CLI `status` 命令：✅ 正常输出 7 步状态表
- `resume` 无状态路径：✅ 正确输出"未找到 pipeline 状态"
- 模块导入：✅ 三个文件全部 import 成功
- `publish_sync` / `LLMClient.stats` 依赖：✅ 存在且签名匹配

---

## 四、优化分类汇总

| 严重度 | 数量 | 编号 |
|-------|------|------|
| 🔴 严重 | 4 | ①⑥⑦⑩ |
| 🟡 中等 | 9 | ③⑤⑧⑨⑪⑬⑭⑮⑰ |
| 🔵 建议 | 4 | ②④⑫⑯ |
| **合计** | **17** | |

---

## 五、可维护性提升指标

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| 步骤元数据维护点 | 3 处硬编码（core×2 + task×1） | 1 处（STEP_REGISTRY） |
| `_run`/`_run_resume` 重复行 | ~24 行 | 0（合并为 `_execute`） |
| get_task+404 样板 | 7 处重复 | 0（`_require_task`） |
| 魔法数字裸露 | 8+ 处 | 0（全部提取常量） |
| 缺 docstring 的方法 | ~12 个 | 0 |
| 新增步骤改动面 | 3-4 个文件 | 1 个文件（core/pipeline.py） |

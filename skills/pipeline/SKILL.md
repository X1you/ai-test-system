---
name: pipeline
description: 测试用例生成全流程自动串联 — 从需求文档一键跑到测试报告，知识库 RAG 全程增强，含人工检查点
version: 1.1.0
tags: [testing, pipeline, automation]
author: AI Assistant
created_by: agent
---

# 全流程自动串联 Skill

将 6 个环节的 Skill 串联为一键 pipeline：需求文档 → 需求分析 → 知识库检索 → 测试点梳理 → 生成用例 → 用例评审 → 测试报告。全自动执行，在关键节点保留人工确认选项。

## 触发条件

当用户说以下内容时，使用本 Skill：
- "全流程" / "一键生成" / "自动串联"
- "从头跑一遍" / "完整流程"
- "pipeline" / "end to end"
- 带有 "全流程"、"串联"、"一键" 等关键词

## 全流程架构

```
                    ┌──────────────────────┐
                    │   知识库 (RAG)        │
                    │   横切增强全链路       │
                    └──┬───────────────────┘
                       │ search / export
  ┌────────────────────┼──────────────────────────────────────────┐
  │                    ▼                                          │
  │ Step 1  需求文档 (Markdown)                                    │
  │         ↓ AI 执行                                              │
  │ Step 2  需求分析 → requirements_analysis.md + clarification   │
  │         ↓ 🔍 知识库检索：业务规则 + 坑点                       │
  │ Step 3  测试点梳理 → testpoints.md                            │
  │         ↓                                                      │
  │ Step 4  生成测试用例 → testcases.xlsx + testcases.xmind      │
  │         ↓                                                      │
  │ Step 5  用例评审 → test_case_review_report.md                 │
  │         ↓ 🔁 知识库回灌：优质用例 + 规则                       │
  │ Step 6  [人工执行测试，填写执行结果列]                         │
  │         ↓                                                      │
  │ Step 7  生成测试报告 → test_report.md                         │
  │         ↓ 🔁 知识库回灌：失败分析 + 坑点                       │
  └────────────────────────────────────────────────────────────────┘
```

## 执行步骤

### 1. 确认输入

需要用户提供：
- **需求文档路径**（必需）— Markdown 格式
- **项目名称 / 模块名称**（可选）— 用于报告标题和知识库模块标签
- **输出目录**（可选，默认当前目录）
- **执行模式**（见下）

### 2. 选择执行模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **全自动** | 7 步连续执行，不暂停 | 熟悉流程、快速出结果 |
| **半自动**（推荐） | 在关键节点暂停确认 | 首次使用、重要需求 |
| **单步执行** | 每步都暂停确认 | 演示、调试 |

**人工检查点（半自动模式暂停的位置）：**
1. Step 2 后 — 确认需求分析结果、澄清待确认事项
2. Step 3 后 — 确认测试点覆盖是否完整
3. Step 4 后 — 确认用例质量
4. Step 5 后 — 确认评审建议
5. Step 6 — 必须人工执行测试并填写结果

### 3. 自动执行

AI 按顺序调用各 Skill，每步的输出作为下一步的输入：

```
requirements.md
    → [requirement-analysis] → requirements_analysis.md + clarification_needed.md
    → [knowledge-base search] → knowledge-context.md
    → [test-points] → testpoints.md
    → [generate-testcases] → testcases.xlsx
    → [test-case-review] → test_case_review_report.md
    → [knowledge-base ingest] → 回灌优质用例
    → [等待人工执行测试]
    → [generate-report] → test_report.md
    → [knowledge-base ingest] → 回灌坑点
```

### 4. 流程控制

**前 5 步全自动**（Step 1-5）：AI 直接执行，中途根据模式决定是否暂停确认。

**Step 6 人工执行测试**：这是必须的人工环节。AI 会：
- 提示用户打开 `testcases.xlsx` 执行测试
- 在「执行结果」列填写通过/失败/阻塞
- 填完后告知 AI 继续

**Step 7 生成报告**：AI 读取执行完的 Excel，自动生成报告。

### 5. 知识库自动集成

全流程中知识库自动参与：

| 步骤 | 知识库操作 | 说明 |
|------|-----------|------|
| Step 2 后 | `search` 检索 | 按需求关键词检索业务规则和坑点 |
| Step 3 前 | 注入上下文 | 将检索结果作为测试点生成的参考 |
| Step 5 后 | `ingest` 回灌 | 评审通过的优质用例沉淀到知识库 |
| Step 7 后 | `ingest` 回灌 | 失败用例分析作为坑点沉淀 |

### 6. 向用户汇报

每步完成后输出进度条，最终输出汇总：

```markdown
✅ 全流程执行完成！

📊 Pipeline 执行概况：
┌─────────────────────────────────────────────────────┐
│ 步骤                  │ 状态   │ 输出文件           │
├───────────────────────┼────────┼───────────────────┤
│ 1. 需求分析           │ ✅ 完成 │ requirements_...md │
│ 2. 知识库检索         │ ✅ 命中 │ knowledge-context │
│ 3. 测试点梳理         │ ✅ 完成 │ testpoints.md     │
│ 4. 生成用例           │ ✅ 完成 │ testcases.xlsx    │
│ 5. 用例评审           │ ✅ 完成 │ review_report.md  │
│ 6. 执行测试           │ 👤 人工 │ testcases.xlsx    │
│ 7. 测试报告           │ ✅ 完成 │ test_report.md    │
└─────────────────────────────────────────────────────┘

📁 输出目录：/path/to/output/
💡 知识库已更新：+N 条优质用例，+M 条坑点
```

## 输入参数

- **需求文档路径**（必需）
- **项目名称**（可选，用于标题）
- **输出目录**（可选，默认当前目录）
- **执行模式**：全自动 / 半自动 / 单步（默认半自动）
- **测试维度**：基础4维 / 全6维（默认基础4维）
- **输出格式**：Excel / XMind / 两者（默认 Excel）
- **知识库路径**（可选，默认项目内 knowledge-base/）

## Python 脚本说明

### ⚠️ 运行环境

脚本调用各环节的 Python 脚本，需要 Hermes venv Python：

```bash
HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
$HERMES_PYTHON scripts/pipeline.py run requirements.md -o output/
```

### 脚本功能

- 脚本位置：`scripts/pipeline.py`
- 依赖：`openpyxl`（在 Hermes venv 中）
- 功能：
  - 自动执行 Step 1-5 + Step 7（Step 6 需人工）
  - 调用各环节脚本，串联输入输出
  - 自动调用知识库检索和回灌
  - 支持断点续跑（跳过已完成的步骤）
  - 输出执行日志和汇总报告

### 断点续跑

如果 pipeline 中途中断（如人工确认后停止），可以恢复：

```bash
# 查看当前进度
$HERMES_PYTHON scripts/pipeline.py status -o output/

# 从断点继续
$HERMES_PYTHON scripts/pipeline.py resume -o output/
```

## 使用示例

**示例 1：半自动全流程（推荐）**
```
用户：帮我跑一遍这个需求的全流程

AI：
📋 开始执行全流程 Pipeline（半自动模式）

Step 1/7: 需求分析...
✅ 识别到 6 个模块、17 个功能点、60+ 可测项
⏸️  请确认需求分析结果，输入"继续"执行下一步

用户：继续

AI：
Step 2/7: 知识库检索...
✅ 命中 8 条相关知识（3 规则 + 5 坑点）

Step 3/7: 测试点梳理...
✅ 生成 102 个测试点
⏸️  请确认测试点覆盖，输入"继续"执行下一步

...

Step 7/7: 测试报告
✅ 通过率 83.3%，评级「良好」

📊 全流程完成！
```

**示例 2：全自动模式（前 5 步）**
```
用户：全自动跑一遍，到用例生成为止

AI：
📋 开始执行（全自动模式，Step 1-5）

✅ Step 1: 需求分析 → 6 模块 17 功能点
✅ Step 2: 知识库命中 8 条
✅ Step 3: 测试点 102 个
✅ Step 4: 用例 102 条（Excel）
✅ Step 5: 评审完成，评分 78/100

📁 输出目录：output/
⏸️  下一步：请执行测试，填写执行结果后告知我生成报告
```

## 与其他 Skill 的协作

本 Skill 是**编排层**，串联以下 6 个 Skill：

| 步骤 | 调用的 Skill | 输入 | 输出 |
|------|-------------|------|------|
| 1 | requirement-analysis | 需求文档 | requirements_analysis.md |
| 2 | knowledge-base (search) | 关键词 | knowledge-context.md |
| 3 | test-points | requirements_analysis.md | testpoints.md |
| 4 | generate-testcases | testpoints.md | testcases.xlsx |
| 5 | test-case-review | testcases.xlsx | review_report.md |
| 5+ | knowledge-base (ingest) | testcases.xlsx | 知识库更新 |
| 6 | *[人工执行测试]* | testcases.xlsx | testcases.xlsx (已填写结果) |
| 7 | generate-report | testcases.xlsx (已执行) | test_report.md |
| 7+ | knowledge-base (ingest) | test_report.md | 知识库更新 |

## 注意事项

1. **Step 6（人工执行测试）是不可跳过的** — AI 无法代替人工判断
2. 全自动模式仅指 Step 1-5 连续执行，不含 Step 6-7
3. 每步的输出文件保存在同一输出目录，方便管理
4. 知识库操作是可选的 — 如果知识库未初始化，自动跳过 RAG 步骤
5. 如果某步出错，pipeline 会暂停并提示用户
6. 断点续跑时，已完成的步骤会自动跳过（检查输出文件是否存在）

## 更新日志

### v1.1.0 (2026-07-15)
- 🐛 修复脚本路径错误（generate-report 和 knowledge-base 不应在 testing/ 子目录下）
- 🐛 修复知识库脚本调用：优先使用 MCP 层 kb_manager_mcp.py，fallback 到本地 kb_manager.py
- ✅ pipeline Step 4 XMind 生成支持维度过滤参数传递
- ✅ 知识库检索/回灌不再依赖 kb_available（改为检查脚本文件是否存在）

### v1.0.0 (2026-07-14)
- ✅ 初始版本
- ✅ 7 步全流程串联（Step 1-5 + 7 自动，Step 6 人工）
- ✅ 3 种执行模式（全自动/半自动/单步）
- ✅ 知识库自动检索 + 回灌
- ✅ 断点续跑
- ✅ 执行日志和汇总报告

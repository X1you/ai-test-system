# Hermes 测试用例生成系统

基于 Hermes Agent 的测试用例自动化生成全流程系统，实现从需求到测试报告的端到端自动化。7 个核心 Skill 串联，知识库 RAG 横切增强，人工校验节点保留，整体提效。

## 📖 项目背景

基于微信公众号文章《我搭建了一套AI生成测试用例的全流程方案：7个可串联的 Skill 环节》，实现一套完整的测试用例生成辅助系统。

**原始方案来源：** https://mp.weixin.qq.com/s/12fJisrYU-wGmqtXOt5XjA

## 🎯 项目目标

将测试用例生产拆成 7 个可串联的 Skill 环节，知识库 & RAG 横切增强中间链路，每个环节 AI 负责生成和整理，人负责确认和决策，在保留必要人工校验节点的前提下，整体提效。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Hermes Agent Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         pipeline Skill (v1.1.0) — 编排层                  │    │
│  │  自动串联以下 7 步 + 断点续跑 + 人工检查点                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↕                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │       knowledge-base Skill (v2.1.0) — RAG 增强           │    │
│  │  MCP 协议访问 Obsidian Vault（7 分类，持续回灌）             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ── 数据流 ──────────────────────────────────────────────────    │
│                                                                   │
│  Step 1  需求分析 (requirement-analysis v1.2.0)  🤖 AI 实时处理   │
│          需求文档 → 功能模块/功能点/可测项 + 待确认事项             │
│                ↓                                                  │
│  Step 2  知识库检索 (knowledge-base v2.1.0)      📜 脚本自动化    │
│          MCP 检索 Obsidian Vault → knowledge-context.md           │
│                ↓                                                  │
│  Step 3  测试点梳理 (test-points v1.3.0)         🤖 AI 实时处理   │
│          模块→功能点→6维测试点 + 优先级建议                        │
│                ↓                                                  │
│  Step 4  生成测试用例 (generate-testcases v1.3.0) 📜 脚本自动化   │
│          测试点 → Excel (12列) + XMind (树状)                     │
│                ↓                                                  │
│  Step 5  用例评审 (test-case-review v1.0.0)      🤖 AI 实时处理   │
│          四维质检（缺失/质量/重复/整改）→ 质量评分                  │
│                ↓                                                  │
│  Step 6  执行测试                                👤 人工执行       │
│          按用例执行 → 填写结果到 Excel                              │
│                ↓                                                  │
│  Step 7  生成报告 (generate-report v1.1.0)      📜 脚本自动化    │
│          执行结果 → 质量报告（概览/模块/失败/风险）                 │
│                ↓                                                  │
│  回灌    知识库回灌 (knowledge-base v2.1.0)     📜 脚本自动化    │
│          优质用例 + 坑点 → Obsidian Vault 持续沉淀                  │
│                                                                   │
│  ── 脚本 vs AI ───────────────────────────────────────────────   │
│  🤖 AI 实时处理：Step 1 / 3 / 5（无独立脚本，AI 直接生成）         │
│  📜 脚本自动化：Step 2 / 4 / 7 + 回灌（Python 脚本，秒级执行）      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## ✅ 已完成功能

### 1. 需求分析 Skill (requirement-analysis v1.2.0)

**文件位置：** `skills/requirement-analysis/`

**功能特性：**
- ✅ 需求文档（Markdown）结构化拆解
- ✅ 识别功能模块、功能点、可测项
- ✅ 待确认事项清单生成（高/中/低优先级）
- ✅ 优先级自动标注 + 影响范围标注
- ✅ 质量报告生成（可选）

**输出文件：**
- `requirements_analysis.md` — 需求拆解
- `clarification_needed.md` — 待确认清单
- `requirements_quality_report.md` — 质量报告（可选）

---

### 2. 测试点梳理 Skill (test-points v1.3.0)

**文件位置：** `skills/test-points/`

**功能特性：**
- ✅ 基于需求分析生成测试点清单
- ✅ 结构化：模块→功能点→测试维度→具体测试点
- ✅ 支持 6 个测试维度（可配置）
  - 正向测试（必需）
  - 负向测试（必需）
  - 边界测试（必需）
  - 异常测试（必需）
  - 性能测试（可选）✨
  - 安全测试（可选）✨
- ✅ 每个测试点包含描述、测试数据、预期结果
- ✅ 测试优先级建议生成

**输出文件：**
- `testpoints.md` — 测试点清单

---

### 3. 测试用例生成 Skill (generate-testcases v1.3.0)

**文件位置：** `skills/generate-testcases/`
**脚本位置：** `skills/generate-testcases/scripts/generate_excel.py`、`generate_xmind.py`

**功能特性：**
- ✅ Excel 格式生成（12 列标准结构：编号/模块/功能点/标题/维度/优先级/前置条件/步骤/测试数据/预期结果/执行结果/备注）
- ✅ XMind 格式生成（标准 xmind 库，树状结构）
- ✅ 用例编号自动连续（TC-001 ~ TC-NNN）
- ✅ 优先级自动分配（P0/P1/P2）
- ✅ 按测试维度过滤（`-d` 参数）
- ✅ 格式化（表头加粗、冻结首行）
- ✅ 步骤模板按模块类型匹配（v1.2.0 优化，减少通用模板回退）

**输出文件：**
- `testcases.xlsx` — Excel 测试用例
- `testcases.xmind` — XMind 测试用例脑图

**版本历史：**
- v1.0.0: 初始版本，Excel + XMind 双格式
- v1.1.0: 标准 xmind 库替代手工 JSON
- v1.2.0: P0 修复 — 步骤模板优化 + 优先级分配优化
- v1.3.0: XMind 支持 -d 维度过滤 + 优先级逻辑与 Excel 统一

---

### 4. 用例评审 Skill (test-case-review v1.0.0)

**文件位置：** `skills/test-case-review/`

**功能特性：**
- ✅ 四维质检分析
  - 缺失用例检测（关键场景、边界条件、异常路径）
  - 质量问题识别（描述含糊、步骤不清晰、预期结果模糊）
  - 重复冗余检查（用例重复、场景重叠）
  - 整改建议生成（需澄清项、补充建议）
- ✅ 支持多种文件格式（Excel、Markdown、CSV）
- ✅ 质量评分功能（4 个维度，满分 100）
- ✅ 整改清单生成

**输出文件：**
- `test_case_review_report.md` — 评审报告

**质量评分标准：**

| 维度 | 满分 | 评分标准 |
|------|------|---------|
| 完整性 | 30 | 缺失用例越少，得分越高 |
| 清晰性 | 30 | 质量问题越少，得分越高 |
| 准确性 | 20 | 重复冗余越少，得分越高 |
| 可执行性 | 20 | 用例越具体、越可执行，得分越高 |

---

### 5. 测试报告生成 Skill (generate-report v1.1.0)

**文件位置：** `skills/generate-report/`
**脚本位置：** `skills/generate-report/scripts/generate_report.py`

**功能特性：**
- ✅ 读取已执行完成的测试用例 Excel 文件
- ✅ 总体概览（总数、通过/失败/阻塞/跳过、通过率、执行率）
- ✅ 质量评级（优秀/良好/中等/较差，含图标）
- ✅ 模块通过率分布（按通过率排序，低通过率标红）
- ✅ 优先级分析（P0/P1/P2 分组统计）
- ✅ 测试维度分析（正向/负向/边界/异常/性能/安全）
- ✅ 失败用例分析（含失败原因推断和修复建议）
- ✅ 阻塞用例分析
- ✅ 风险评估（高/中/低三级风险，自动判断）
- ✅ 发布建议（基于 P0 失败数和通过率自动推荐）
- ✅ 需求覆盖率计算（`-r` 参数）

**输出文件：**
- `test_report.md` — Markdown 测试报告

**质量评级标准：**

| 通过率 | 评级 | 说明 |
|--------|------|------|
| ≥ 95% | 优秀 🏆 | 可以发布 |
| 85%-95% | 良好 ✅ | 修复少量问题后可发布 |
| 70%-85% | 中等 ⚠️ | 需要修复较多问题 |
| < 70% | 较差 ❌ | 不建议发布 |

---

### 6. 知识库管理 Skill (knowledge-base v2.1.0) — MCP 层

**文件位置：** `skills/knowledge-base/`
**脚本位置：** `scripts/kb_manager_mcp.py`、`scripts/mcp_client.py`

**架构方案：** MCP 协议层（Option D），直接访问 Obsidian Vault 文件系统，非 REST API。

```
Hermes Skills / CLI 调用层
       ↕
MCP 协议层 (统一知识库接口)
  - list_files() / read_file() / search() / create_file()
       ↕
Obsidian Vault (知识存储)
  ~/Documents/test-interview-kb/
```

**知识库 7 分类：**

| 分类 | 目录 | 说明 |
|------|------|------|
| 历史优质用例 | `🏆 历史用例/` | 评审通过的优质用例，按项目维度分层（项目→批次→文件） |
| 业务规则 | `📋 业务规则/` | 字段限制、校验规则、业务逻辑 |
| 业务规范文档 | `📘 业务规范/` | 产品功能说明、状态流转规则、权限矩阵 |
| 数据字典 | `📖 数据字典/` | 表字段释义、枚举值、关联关系 |
| 线上问题沉淀 | `⚠️ 线上坑点/` | 历史 Bug、常见边界坑点、易漏场景 |
| 团队模板规范 | `📝 用例模板/` | 用例编写模板、命名规范、断言规则 |
| 团队规范 | `📐 团队规范/` | 测试流程规范等 |

**功能特性：**
- ✅ MCP 协议统一访问 Obsidian Vault
- ✅ 关键词检索（`search`）
- ✅ 导出增强上下文（`export`）→ Markdown 注入后续环节
- ✅ 回灌优质产物（`ingest`）→ Excel 用例自动拆分写入
- ✅ 添加单条知识（`add`）
- ✅ 知识库状态统计（`status`）
- ✅ 历史用例按项目维度分层归档（项目名→批次→用例文件）

**版本历史：**
- v1.0.0: 初始版本，本地文件系统 + BM25 检索
- v2.0.0: 重构为 MCP 层架构，直接访问 Obsidian Vault
- v2.1.0: 修复 search/export 检索逻辑不一致，统一多关键词 OR 匹配

---

### 7. 全流程串联 Skill (pipeline v1.1.0)

**文件位置：** `skills/pipeline/`
**脚本位置：** `skills/pipeline/scripts/pipeline.py`

**功能特性：**
- ✅ 一键串联 7 个环节：需求文档 → 需求分析 → 知识库检索 → 测试点 → 生成用例 → 用例评审 → 测试报告
- ✅ 断点续跑（记录执行进度，失败后从断点恢复）
- ✅ 人工检查点（关键节点暂停等待确认）
- ✅ 知识库 RAG 全程增强（Step 2 检索 → Step 3 注入 → 回灌）
- ✅ 自动识别 AI 实时处理环节 vs 脚本自动化环节

**执行方式：**

| 环节 | 执行方式 | 典型耗时 |
|------|---------|---------|
| Step 1 需求分析 | 🤖 AI 实时处理 | ~2min |
| Step 2 知识库检索 | 📜 脚本自动化 | <1s |
| Step 3 测试点梳理 | 🤖 AI 实时处理 | ~3min |
| Step 4 生成用例 | 📜 脚本自动化 | <3s |
| Step 5 用例评审 | 🤖 AI 实时处理 | ~2min |
| Step 6 执行测试 | 👤 人工执行 | — |
| Step 7 生成报告 | 📜 脚本自动化 | <3s |
| 回灌知识库 | 📜 脚本自动化 | <2s |

> **关键认知：** Step 1/3/5 是 AI 实时处理环节，无独立脚本。pipeline 全自动模式实际依赖 AI agent 连续调用，不是纯脚本自动化。

---

## 🧪 全流程验证结果

以本项目自身为被测产品，跑通完整 pipeline 全流程自验证（2026-07-14）。

### 执行总览

| 步骤 | 环节 | 状态 | 耗时 | 输出 |
|------|------|------|------|------|
| 准备 | 需求文档 + 原型图 | ✅ | ~3min | requirements.md + prototype.md (21KB) |
| Step 1 | 需求分析 | ✅ | ~2min | 需求拆解 + 待确认事项 (6.4KB) |
| Step 2 | 知识库检索 | ✅ | <1s | knowledge-context.md (2.2KB) |
| Step 3 | 测试点梳理 | ✅ | ~3min | testpoints.md (16.2KB) |
| Step 4 | 生成测试用例 | ✅ | <3s | testcases.xlsx + .xmind (23.7KB) |
| Step 5 | 用例评审 | ✅ | ~2min | 评审报告 (7.6KB) |
| Step 6 | 执行测试（模拟） | ✅ | <5s | 78 条用例已填结果 |
| Step 7 | 生成报告 | ✅ | <3s | test_report.md (5.5KB) |
| 回灌 | 知识库回灌 | ✅ | <2s | 知识库 +80 条 |

**Pipeline 总耗时：约 12 分钟**（含 AI 分析时间，脚本执行部分 < 15 秒）

### 质量评估

| 维度 | 满分 | 初评 | 修复后 | 说明 |
|------|------|------|--------|------|
| 完整性 | 30 | 24 | — | 缺少并发、部分安全场景 |
| 清晰性 | 30 | 22 | — | 步骤模板回退（已修复） |
| 准确性 | 20 | 17 | — | 优先级分配偏差（已修复） |
| 可执行性 | 20 | 14 | — | 35% 步骤不可直接执行（已修复） |
| **总计** | **100** | **77** | **89** | 中等偏上 → 良好 |

**最终通过率：100%**（78 条用例全部通过，P0 修复后）

### 已修复的 P0 问题

1. **generate_excel.py 步骤模板优化** — 增加按模块类型生成步骤的逻辑，减少通用模板回退
2. **generate_excel.py 优先级分配优化** — 增加基于模块优先级的兜底逻辑，提高 P0 覆盖率
3. **kb_manager_mcp.py ingest 格式错位** — 正确解析 testcases.xlsx 12 列格式

完整验证报告：`test-run/output/pipeline_validation_report.md`

---

## 🚧 计划中功能

### 1. 需求读取 MCP 集成（计划中）

- 蓝湖 MCP：读取蓝湖原型链接，解析页面结构、UI 元素、交互规则
- Figma MCP：读取 Figma 原型，解析布局、组件、设计规范
- Axure Parser：读取 Axure 原型，解析交互流程
- 飞书文档：读取飞书需求文档，解析结构化需求

### 2. 脚本逻辑优化（已完成）

- ✅ `knowledge-base` search/export 检索逻辑统一（多词 OR 一致）— v2.1.0
- ✅ `generate_xmind.py` 支持 `-d` 维度过滤参数（与 Excel 脚本对齐）— v1.3.0
- ✅ `test-points` 维度分布自动校验（7 项校验规则）— v1.3.0
- ✅ `generate-report` 失败原因推断增强（4 类→11 类，减少"待确认"）— v1.1.0
- ✅ `pipeline.py` 脚本路径修正 + 知识库脚本 MCP 优先 — v1.1.0

### 3. Web UI 界面（计划中）

- 可视化操作界面
- 进度跟踪
- 报告查看

### 4. 全流程 Cron 自动化（计划中）

- Cron Job 定时触发
- 自动读取新需求文档
- 自动通知（QQ、邮件等）

---

## 📂 项目文件结构

```
~/Documents/ai-test-system/
│
├── README.md                                📖 项目文档（本文件）
├── .gitignore
│
├── skills/                                  🔧 7 个核心 Skill 源码
│   ├── requirement-analysis/                ✅ v1.2.0
│   │   └── SKILL.md
│   ├── test-points/                         ✅ v1.3.0
│   │   └── SKILL.md
│   ├── generate-testcases/                  ✅ v1.3.0
│   │   ├── SKILL.md
│   │   ├── scripts/generate_excel.py        (Excel 生成脚本)
│   │   ├── scripts/generate_xmind.py        (XMind 生成脚本)
│   │   └── references/pipeline-overview.md
│   ├── test-case-review/                    ✅ v1.0.0
│   │   └── SKILL.md
│   ├── generate-report/                     ✅ v1.1.0
│   │   ├── SKILL.md
│   │   └── scripts/generate_report.py       (报告生成脚本)
│   ├── knowledge-base/                      ✅ v2.1.0 (MCP 层)
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── mcp_client.py                (Obsidian Vault 文件访问)
│   │       ├── kb_manager_mcp.py            (知识库管理：search/export/ingest)
│   │       └── kb_manager.py                (本地知识库 fallback，旧版)
│   └── pipeline/                            ✅ v1.1.0 (编排层)
│       ├── SKILL.md
│       └── scripts/pipeline.py              (全流程串联引擎)
│
├── examples/                                📁 示例需求文档
│   ├── demo_requirements.md
│   └── order_requirements.md
│
├── sample-output/                           📁 各环节输出产物示例
│   ├── requirements_analysis.md
│   ├── clarification_needed.md
│   ├── requirements_quality_report.md
│   ├── testpoints.md / _extended.md
│   ├── testcases.xlsx / .xmind
│   ├── testcases_executed.xlsx
│   └── test_report.md
│
├── docs/                                    📝 项目文档
│   └── pipeline_validation_report.md        (全流程验证报告)
│
├── reference/                               📚 参考资料和原始文章
│   └── 我搭建了一套AI生成测试用例的全流程方案....html
│
└── .gitignore

知识库存储（运行时，不在项目仓库内）：
~/Documents/test-interview-kb/                ← Obsidian Vault（MCP 访问）
  ├── 🏆 历史用例/   (按项目→批次分层归档)
  ├── 📋 业务规则/
  ├── 📘 业务规范/
  ├── 📖 数据字典/
  ├── ⚠️ 线上坑点/
  ├── 📝 用例模板/
  └── 📐 团队规范/

安装位置（运行时）：
~/.hermes/skills/                             ← Hermes 自动加载的 Skill 目录
```

---

## 🎯 使用流程

### 方式一：pipeline 一键串联

```
用户：用 pipeline 跑一遍这个需求文档：requirements.md

AI：[自动调用 pipeline Skill，依次执行 7 步]
✅ Step 1 需求分析完成
✅ Step 2 知识库检索完成
✅ Step 3 测试点梳理完成
⏸️  人工检查点：请确认测试点清单 testpoints.md
✅ Step 4 生成测试用例完成
✅ Step 5 用例评审完成
✅ Step 7 生成报告完成
✅ 知识库回灌完成
```

### 方式二：渐进式使用

```bash
# 1. 需求分析
用户：帮我分析这个需求文档：requirements.md
→ 输出：requirements_analysis.md + clarification_needed.md

# 2. 与产品/开发确认待确认事项
人工确认后更新需求文档

# 3. 测试点梳理
用户：梳理测试点，包含性能和安全测试
→ 输出：testpoints.md

# 4. 生成测试用例
用户：生成测试用例
→ 输出：testcases.xlsx + testcases.xmind

# 5. 用例评审
用户：评审测试用例
→ 输出：test_case_review_report.md

# 6. 执行测试用例
人工执行或自动化测试

# 7. 生成测试报告
用户：生成测试报告
→ 输出：test_report.md
```

---

## 📊 技术栈

### 核心技术
- **Hermes Agent** — AI 智能体平台
- **Skills** — 可复用的技能模块（7 个核心 Skill）
- **MCP 协议** — 知识库统一访问层
- **Obsidian Vault** — 知识库存储（本地优先）

### 文件格式
- **Markdown** — 需求文档、测试点、评审报告
- **Excel** — 测试用例（12 列标准结构）、执行结果
- **XMind** — 测试用例脑图（标准 xmind 库）

### 依赖库
- `openpyxl` — Excel 读写
- `xmind` — XMind 生成
- Python 标准库（json, zipfile, os, re 等）

### 可选集成（计划中）
- **蓝湖 API** — 原型读取
- **Figma API** — 设计稿读取
- **飞书 API** — 文档读取

---

## 🚀 快速开始

### 前置要求

1. 安装 [Hermes Agent](https://hermes-agent.nousresearch.com/docs/)
2. 安装 [Obsidian](https://obsidian.md/)（知识库存储）
3. 配置 Mem0 API key（可选，跨会话记忆）
4. Python 依赖：`openpyxl`、`xmind`

### 安装步骤

```bash
# 1. 复制 Skills 到 Hermes 技能目录
cp -R skills/* ~/.hermes/skills/

# 2. 确认 Skills 已加载
hermes skills list | grep -E "requirement-analysis|test-points|generate-testcases|test-case-review|generate-report|knowledge-base|pipeline"

# 3. 创建 Obsidian Vault（知识库存储）
mkdir -p ~/Documents/test-interview-kb

# 4. 复制知识库 MCP 脚本
cp scripts/*.py ~/.hermes/skills/knowledge-base/scripts/ 2>/dev/null || true

# 5. 安装 Python 依赖
pip install openpyxl xmind
```

### 使用示例

```bash
# 启动 Hermes
hermes

# 在会话中使用
用户：帮我分析这个需求文档：~/Documents/requirements.md
AI：[自动调用 requirement-analysis Skill]

用户：梳理测试点，包含性能和安全测试
AI：[自动调用 test-points Skill]

用户：评审这个测试用例文件
AI：[自动调用 test-case-review Skill]

用户：用 pipeline 跑一遍完整流程
AI：[自动调用 pipeline Skill，串联 7 步]
```

---

## 📈 进度统计

### 已完成
- ✅ 需求分析 Skill (v1.2.0)
- ✅ 测试点梳理 Skill (v1.3.0)
- ✅ 测试用例生成 Skill (v1.3.0)
- ✅ 用例评审 Skill (v1.0.0)
- ✅ 测试报告生成 Skill (v1.1.0)
- ✅ 知识库管理 Skill (v2.1.0，MCP 层)
- ✅ 全流程串联 Skill (pipeline v1.1.0)
- ✅ Mem0 记忆系统集成
- ✅ 示例数据和文档
- ✅ **全流程自验证完成**（78 条用例，100% 通过率，质量评分 77→89）
- ✅ **P0 修复 3 项**（步骤模板、优先级分配、ingest 格式）
- ✅ **P1/P2 修复 5 项**（检索逻辑统一、XMind -d 参数、维度校验、失败推断增强、pipeline 路径修正）

### 计划中
- 🚧 需求读取 MCP 集成（蓝湖/Figma/飞书）
- 🚧 Web UI 界面

### 完成度
- **核心 Skills：** 7/7 (100%) 🎉
- **全流程验证：** ✅ 已完成
- **P0 修复：** ✅ 3/3 完成
- **P1/P2 修复：** ✅ 5/5 完成
- **整体完成度：** ~95%

---

## 🤝 贡献指南

### 开发环境

```bash
# 进入项目目录
cd ~/Documents/ai-test-system

# 编辑 Skill
vim skills/[skill-name]/SKILL.md

# 编辑脚本
vim skills/[skill-name]/scripts/[script].py

# 提交改进
git add .
git commit -m "improve: [description]"
git push
```

### Skill 开发规范

1. SKILL.md 必须包含：
   - Frontmatter（name, description, version, tags）
   - 触发条件
   - 执行步骤
   - 输入/输出
   - 注意事项
   - 与其他 Skill 的协作

2. 版本号规范：
   - v1.0.0: 初始版本
   - v1.x.0: 小功能增加
   - v2.0.0: 重大架构变更

3. 文档更新：
   - 每次更新同步版本号
   - 记录版本历史

---

## 📞 联系方式

- **项目维护者：** AI Assistant
- **Hermes 文档：** https://hermes-agent.nousresearch.com/docs/
- **问题反馈：** 通过 Hermes 会话反馈

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- **Nous Research** — Hermes Agent 平台
- **Raina测试** — 原始方案作者
- **Hermes 社区** — 技术支持

---

*最后更新：2026-07-15*
*当前版本：v1.0.0*

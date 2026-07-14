# AI 测试用例生成系统 需求文档（v2.0 — 基于真实功能）

> 版本：v2.0 | 更新日期：2026-07-14
> 说明：本文档描述系统**实际已实现的功能**，作为自验证测试的输入。

## 1. 系统概述

AI 测试用例生成系统是一套基于 AI 技术的自动化测试用例生成工具，通过 7 个可串联的 Skill 环节，实现从需求文档到测试报告的全流程自动化。系统通过 MCP 协议访问 Obsidian Vault 实现知识库 RAG 增强。

**技术栈：** Python 脚本 + Hermes Agent AI Skills + Obsidian Vault（MCP 协议）

## 2. 需求分析模块（requirement-analysis Skill）

### 2.1 需求文档解析

**功能描述：** 读取 Markdown 格式的需求文档，进行结构化拆解。

**输入约束：**
- 文件格式：仅支持 `.md` / `.markdown`
- 文件编码：UTF-8（GBK 等非 UTF-8 编码会报错）
- 文件大小：无硬性限制（建议 ≤ 5MB）

**解析能力：**
- 识别功能模块（`##` 级标题）
- 识别功能点（`###` 级标题）
- 提取每个功能点的可测项
- 识别业务规则（`**业务规则：**` 列表项）

**输出内容：**
- `requirements_analysis.md`：结构化拆解结果（模块 → 功能点 → 可测项）
- `clarification_needed.md`：待确认事项清单，含优先级标注（高/中/低）

**识别规则：**
- 模糊描述识别：检测"一定的""若干""大概"等不具体词汇
- 信息缺失检测：数值、时间、金额等缺失具体数字
- 逻辑矛盾检测：前后描述不一致的地方
- 每个待确认事项必须标注优先级（高/中/低）

### 2.2 执行方式

- **执行方式：** AI 实时处理（无独立脚本，AI 读取文档后直接生成分析结果）
- **前置条件：** 存在合法的 Markdown 需求文档

## 3. 知识库管理模块（kb_manager_mcp.py）

### 3.1 知识库检索

**功能描述：** 通过 MCP 协议直接访问 Obsidian Vault 文件系统，检索业务规则和历史用例。

**CLI 命令：**
```
python kb_manager_mcp.py status                          # 查看知识库概况
python kb_manager_mcp.py search "关键词" [--limit N]      # 搜索知识
python kb_manager_mcp.py export "关键词" [--output file]  # 导出上下文
```

**知识分类（7 类）：**

| 分类 | Obsidian 目录 | 说明 |
|------|-------------|------|
| business-rules | 📋 业务规则 | 字段限制、校验规则 |
| historical-cases | 🏆 历史用例 | 评审通过的优质用例 |
| pitfalls | ⚠️ 线上坑点 | 历史 Bug、易漏场景 |
| templates | 📝 用例模板 | 编写模板、命名规范 |
| data-dictionary | 📖 数据字典 | 表字段、枚举值 |
| business-specs | 📘 业务规范 | 功能说明、状态流转 |
| team-standards | 📐 团队规范 | 断言规则、测试流程 |

**检索逻辑：**
- 全文文本匹配（`query.lower() in content.lower()`）
- 支持按分类过滤（`--category` 参数）
- 返回条数可配置（`--limit`，默认 20）
- 空关键词：返回全部条目（匹配所有文件）

### 3.2 知识回灌

**CLI 命令：**
```
python kb_manager_mcp.py ingest <file.xlsx> --category <category> [--module <module>]
python kb_manager_mcp.py add --title "标题" --content "内容" --category <category>
```

**回灌规则：**
- Excel 格式：自动识别 testcases.xlsx 标准 12 列格式，逐条提取写入
- Markdown 格式：整篇作为一个知识条目写入
- 不支持的格式：提示"不支持的文件格式"
- 每条知识生成 YAML frontmatter（id/category/module/tags/created_at）
- 文件命名：`{日期} {标题}.md`

### 3.3 执行方式

- **执行方式：** 脚本自动化（`kb_manager_mcp.py`）
- **存储后端：** Obsidian Vault 文件系统（`~/Documents/test-interview-kb/`）

## 4. 测试点生成模块（test-points Skill）

### 4.1 测试点自动生成

**功能描述：** 基于需求分析结果，生成结构化的测试点清单。

**输出结构：**
```
## 模块一：{模块名}
### 功能点 1.1：{功能点名}
#### 测试维度：{维度名}
- 测试点 1.1.1：{测试点描述}
  - 测试数据：{具体数据}
  - 预期结果：{预期结果}
```

**生成规则：**
- 每个功能点至少 4 个测试点（覆盖 4 个基础维度）
- 支持的测试维度：正向测试、负向测试、边界测试、异常测试、性能测试、安全测试
- 知识库上下文注入：参考检索到的模板和规范

### 4.2 执行方式

- **执行方式：** AI 实时处理（无独立脚本）
- **前置条件：** 需求分析结果文件存在

## 5. 测试用例生成模块（generate_excel.py + generate_xmind.py）

### 5.1 Excel 用例生成

**CLI 命令：**
```
python generate_excel.py <testpoints.md> [--output file.xlsx] [--dimensions all|basic|positive,negative,...]
```

**参数说明：**
- `input`（位置参数）：测试点 Markdown 文件路径
- `-o/--output`：输出文件路径（默认 testcases.xlsx）
- `-d/--dimensions`：维度过滤，支持 `all`、`basic`（正/负/边界/异常）、或逗号分隔的维度名

**Excel 列结构（12 列）：**

| 列 | 字段 | 说明 |
|----|------|------|
| A | 用例编号 | TC-001 格式，连续编号 |
| B | 所属模块 | 功能模块名称 |
| C | 功能点 | 功能点名称 |
| D | 测试维度 | 正向/负向/边界/异常/性能/安全 |
| E | 用例标题 | 简洁描述 |
| F | 优先级 | P0/P1/P2，带颜色标注 |
| G | 前置条件 | 执行前必要条件 |
| H | 测试步骤 | 编号步骤（基于动作关键词匹配生成） |
| I | 测试数据 | 具体测试数据 |
| J | 预期结果 | 具体预期结果 |
| K | 备注 | 额外说明 |
| L | 执行结果 | 人工/脚本填写 |

**优先级分配规则：**
- P0：核心模块正向测试、关键安全测试、核心模块关键异常/边界
- P1：一般功能正向、负向、边界测试
- P2：非核心性能测试

**步骤生成逻辑：**
- 基于 `ACTION_TEMPLATES` 动作关键词映射表（16 类操作）匹配生成
- 未匹配时利用模块名+功能点+测试数据智能兜底
- 格式：冻结首行、自动筛选、优先级颜色标注

### 5.2 XMind 用例生成

**CLI 命令：**
```
python generate_xmind.py <testpoints.md> [--output file.xmind]
```

**输出结构：** 树状脑图（测试用例 → 模块 → 功能点 → 维度 → 用例节点）

**技术实现：** 纯标准库（zipfile + json），无第三方依赖

### 5.3 执行方式

- **执行方式：** 脚本自动化
- **前置条件：** 测试点 Markdown 文件存在且格式正确

## 6. 用例评审模块（test-case-review Skill）

### 6.1 四维质检

**功能描述：** 对生成的测试用例进行四维质量检查。

**四个维度：**
1. **缺失用例检测**：核心场景、边界条件、异常路径、权限场景
2. **质量问题识别**：描述含糊、步骤不清晰、预期结果模糊
3. **重复冗余检查**：用例相似度 > 80% 视为重复
4. **整改建议生成**：补充、优化、合并建议

**质量评分标准：**

| 维度 | 满分 | 说明 |
|------|------|------|
| 完整性 | 30 | 缺失用例越少分越高 |
| 清晰性 | 30 | 质量问题越少分越高 |
| 准确性 | 20 | 重复冗余越少分越高 |
| 可执行性 | 20 | 用例越具体越可执行分越高 |

**评级：** 90-100 优秀 | 80-89 良好 | 70-79 中等 | 60-69 及格 | <60 不及格

### 6.2 执行方式

- **执行方式：** AI 实时处理（无独立脚本）
- **前置条件：** 测试用例文件存在

## 7. 测试报告模块（generate_report.py）

### 7.1 报告自动生成

**CLI 命令：**
```
python generate_report.py <input.xlsx> [--output report.md] [--requirements analysis.md]
```

**参数说明：**
- `input`（位置参数）：已执行完成的测试用例文件（.xlsx）
- `-o/--output`：输出报告路径（默认 test_report.md）
- `-r/--requirements`：需求分析文件路径（可选，用于需求覆盖率计算）

**报告内容（8 部分）：**
1. 总体概览（总数、通过率、评级）
2. 模块通过率分布
3. 优先级分析（P0/P1/P2 通过率）
4. 测试维度分析
5. 失败用例分析（原因分类）
6. 阻塞用例分析
7. 风险评估（高/中/低）
8. 测试结论与发布建议

**质量评级标准：**
- ≥ 95% → 优秀（可发布）
- 85%-95% → 良好
- 70%-85% → 中等
- < 70% → 较差

### 7.2 执行方式

- **执行方式：** 脚本自动化
- **前置条件：** 测试用例文件存在且已填写执行结果

## 8. Pipeline 全流程模块（pipeline Skill）

### 8.1 全流程串联

**功能描述：** 将 7 个环节自动串联为一键 pipeline。

**执行流程：**
```
Step 1: 需求分析（AI）    → requirements_analysis.md + clarification_needed.md
Step 2: 知识库检索（脚本） → knowledge-context.md
Step 3: 测试点生成（AI）   → testpoints.md
Step 4: 用例生成（脚本）   → testcases.xlsx + testcases.xmind
Step 5: 用例评审（AI）     → test_case_review_report.md
Step 6: 执行测试（人工/脚本）→ testcases.xlsx（填结果）
Step 7: 生成报告（脚本）   → test_report.md
回灌:    知识库回灌（脚本） → Obsidian Vault
```

**执行方式分类：**
- 脚本自动化：Step 2/4/7/回灌（有独立 Python 脚本）
- AI 实时处理：Step 1/3/5（无脚本，AI 直接生成）
- 人工执行：Step 6（填写执行结果）

### 8.2 断点续跑

**功能描述：** 支持从中断处恢复执行。

**规则：**
- 检查输出文件是否存在，自动跳过已完成步骤
- 支持查看当前进度
- 支持从断点继续执行

## 9. 约束与限制

### 9.1 已知限制

1. **需求文档编码**：仅支持 UTF-8，GBK/GB2312 会报错
2. **XMind 参数**：不支持 `-d` 维度过滤参数（与 Excel 脚本不一致）
3. **知识库检索精度**：全文匹配，非语义检索
4. **无 Web UI**：纯 CLI + AI Skill 交互
5. **评审环节**：AI 执行，无脚本化质检

### 9.2 文件格式依赖

- 输入：Markdown（.md）
- 输出：Excel（.xlsx）、XMind（.xmind）、Markdown（.md）
- 知识库：Markdown（Obsidian Vault）

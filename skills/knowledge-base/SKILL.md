---
name: knowledge-base
description: 测试知识库管理（MCP 层）— 通过 MCP 协议访问 Obsidian Vault，检索业务规则/历史用例/线上坑点，回灌优质产物，为生成环节提供 RAG 增强
version: 2.0.0
tags: [testing, knowledge-base, rag, mcp, obsidian]
author: AI Assistant
created_by: agent
---

# 测试知识库 Skill (MCP 层)

基于 MCP 协议的测试知识库系统。通过统一的 MCP 接口访问 Obsidian Vault，在生成测试点、测试用例前检索业务规则、历史优质用例和线上坑点，增强 AI 生成的业务贴合度；在评审通过后，将优质产物回灌知识库，持续沉淀。

## 架构说明

```
┌─────────────────────────────────────────────────┐
│         Hermes Skills / CLI 调用层                 │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│         MCP 协议层 (统一知识库接口)                │
│  - list_files()                                  │
│  - read_file()                                   │
│  - search()                                      │
│  - create_file()                                 │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│       Obsidian Vault (知识存储)                  │
│  ~/Documents/test-interview-kb/                   │
└─────────────────────────────────────────────────┘
```

**优势：**
- ✅ **统一访问层**：所有知识库操作通过 MCP 协议
- ✅ **Obsidian 可视化**：保留 Obsidian 的 wikilinks、图谱、界面
- ✅ **跨工具复用**：MCP 协议可在不同工具中使用
- ✅ **灵活扩展**：可轻松切换底层存储

## 触发条件

当用户说以下内容时，使用本 Skill：
- "搜索知识库" / "检索业务规则" / "查询坑点"
- "回灌知识库" / "沉淀用例" / "保存到知识库"
- "知识库状态" / "知识库概况"
- "导出知识上下文" / "增强上下文"
- 带有 "knowledge-base"、"知识库"、"RAG" 等关键词

## 知识库结构

```
~/Documents/test-interview-kb/
├── 📋 业务规则/              business-rules
│   ├── 产品功能说明.md
│   ├── 状态流转规则.md
│   └── 权限矩阵.md
├── 🏆 历史用例/              historical-cases
│   ├── 订单支付_20260714.md
│   └── 退款流程_20260714.md
├── ⚠️ 线上坑点/              pitfalls
│   ├── 支付回调重复.md
│   └── 库存超卖.md
├── 📝 用例模板/              templates
│   ├── 用例编写规范.md
│   └── 命名规范.md
├── 📖 数据字典/              data-dictionary
│   ├── 订单表字段.md
│   └── 用户表字段.md
├── 📘 业务规范/              business-specs
│   └── 业务规则文档.md
└── 📐 团队规范/              team-standards
    ├── 断言规则.md
    └── 测试流程规范.md
```

### 知识分类

| 分类 | 目录 | 说明 | 示例 |
|------|------|------|------|
| 历史优质用例 | `🏆 历史用例/` | 评审通过的优质用例（Excel/XMind） | "支付回调处理的标准用例步骤" |
| 业务规范文档 | `📘 业务规范/` | 产品功能说明、状态流转规则、权限矩阵 | "订单状态流转图" |
| 数据字典 | `📖 数据字典/` | 表字段释义、枚举值、关联关系 | "订单表 order_status 枚举值" |
| 线上问题沉淀 | `⚠️ 线上坑点/` | 历史Bug、常见边界坑点、易漏场景 | "并发下单库存超卖" |
| 团队模板规范 | `📝 用例模板/` | 用例编写模板、命名规范、断言规则 | "P0 用例的标准步骤写法" |
| 业务规则 | `📋 业务规则/` | 字段限制、校验规则、业务逻辑 | "订单金额最小0.01元" |

## 执行步骤

### 操作 1：检索知识库（search）

在生成测试点、用例前检索相关知识：

```bash
HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
$HERMES_PYTHON scripts/kb_manager_mcp.py search "订单支付"
```

**参数：**
- `query` — 检索关键词（必需）
- `--category` — 限定分类（business-rules/historical-cases/pitfalls/templates/data-dictionary/business-specs/team-standards）
- `--limit` — 返回条数（默认 20）

**输出：** JSON 格式的匹配结果，每条包含分类、来源文件、匹配内容片段。

### 操作 2：导出增强上下文（export）

将检索结果格式化为 Markdown，直接注入后续生成环节：

```bash
$HERMES_PYTHON scripts/kb_manager_mcp.py export "订单支付" --output knowledge-context.md
```

**输出文件格式：**
```markdown
# 知识库增强上下文

> 检索关键词：订单支付 | 命中 8 条相关知识

> 来源: Obsidian Vault (MCP 协议)

## 📋 业务规则（3 条）
### 1. [[📋 业务规则/支付规则.md]]
- 微信支付最低金额：0.01元
- 余额支付需验证支付密码
...

## 🏆 历史优质用例（2 条）
### 1. [[🏆 历史用例/支付回调重复处理.md]]
前置条件：...
...

## ⚠️ 线上坑点（3 条）
### 1. [[⚠️ 线上坑点/支付回调重复.md]]
影响范围：高
...
```

### 操作 3：回灌优质产物（ingest）

将评审通过的优质用例、确认的业务规则、记录的坑点沉淀到知识库：

```bash
# 回灌用例文件
$HERMES_PYTHON scripts/kb_manager_mcp.py ingest testcases.xlsx --category historical-cases --module "订单支付"

# 回灌业务规则（从需求分析提取）
$HERMES_PYTHON scripts/kb_manager_mcp.py ingest requirements_analysis.md --category business-specs

# 回灌评审报告中的坑点
$HERMES_PYTHON scripts/kb_manager_mcp.py ingest test_report.md --category pitfalls
```

### 操作 4：添加单条知识（add）

手动添加单条知识：

```bash
$HERMES_PYTHON scripts/kb_manager_mcp.py add \
  --category pitfalls \
  --title "并发下单库存超卖" \
  --content "高并发场景下，库存扣减未加锁导致超卖。解决方案：Redis 分布式锁 + DB 乐观锁双重校验。" \
  --module "订单创建" \
  --tags "并发,库存,分布式锁" \
  --severity high
```

### 操作 5：知识库概况（status）

```bash
$HERMES_PYTHON scripts/kb_manager_mcp.py status
```

输出各分类的条目数、最近更新时间、总条数。

## 与其他 Skill 的协作

### 检索增强流程（RAG）

```
用户需求 → 知识库检索 → 导出上下文 → 注入生成环节
                                        ↓
                                    test-points（测试点）
                                    generate-testcases（用例）
                                    test-case-review（评审）
                                        ↓
                                    优质产物 → 回灌知识库
```

**集成方式：**
1. **test-points**：生成测试点前，先 `search` 检索业务规则和坑点
2. **generate-testcases**：生成用例前，先 `export` 导出历史优质用例作参考
3. **test-case-review**：评审时，对比历史优质用例标准
4. **generate-report**：报告中可引用坑点作为风险评估依据
5. **评审通过后**：`ingest` 回灌优质用例

## Python 脚本说明

### 运行环境

脚本依赖 `openpyxl`（回灌 Excel 用例时需要），仅在 Hermes venv 中。

```bash
HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
$HERMES_PYTHON scripts/kb_manager_mcp.py <command> [options]
```

### 脚本功能

- 脚本位置：`scripts/kb_manager_mcp.py`
- 依赖：`openpyxl`（可选，仅 Excel 回灌时需要）
- 访问方式：通过 MCP 协议访问 Obsidian Vault
- 存储位置：`~/Documents/test-interview-kb/`

### MCP 客户端说明

- 客户端位置：`scripts/mcp_client.py`
- 统一接口：`list_files()`, `read_file()`, `search()`, `create_file()`
- 支持分类：7 种（business-rules, historical-cases, pitfalls, templates, data-dictionary, business-specs, team-standards）

## 使用示例

**示例 1：生成测试点前检索**
```
用户：帮我梳理订单支付模块的测试点

AI：[先调用 knowledge-base search "订单支付"]
[获得业务规则、历史坑点]
[注入 test-points 生成上下文]
✅ 基于知识库增强，生成了 35 个测试点
💡 知识库命中：3 条业务规则、2 条历史坑点
```

**示例 2：评审通过后回灌**
```
用户：这些用例评审通过了，回灌到知识库

AI：[调用 knowledge-base ingest testcases.xlsx --category historical-cases]
✅ 已回灌 28 条优质用例到知识库
📁 存储位置: 🏆 历史用例/
```

**示例 3：记录线上坑点**
```
用户：记录一个坑点：支付回调重复导致重复扣款

AI：[调用 knowledge-base add --category pitfalls ...]
✅ 已记录到知识库
📁 存储位置: ⚠️ 线上坑点/
```

**示例 4：查看知识库状态**
```
用户：知识库现在有多少条目？

AI：[调用 knowledge-base status]
✅ 当前知识库状态：
   - 历史用例：48 条
   - 业务规则：1 条
   - 线上坑点：4 条
   - 用例模板：0 条
   - 数据字典：0 条
   - 业务规范：0 条
   - 团队规范：0 条
   - 总计：53 条
```

## 注意事项

1. 知识库存储在 **Obsidian Vault** 中，通过 MCP 协议访问
2. 支持 **wikilinks** 连接（[[模块]]）和 **YAML frontmatter** 元数据
3. 检索使用文本匹配 + BM25 排序
4. 回灌的用例会提取关键字段，不会原样复制整个文件
5. 知识库需要定期维护，清理过时内容
6. 支持 **手动在 Obsidian 中编辑**知识内容
7. 所有文件使用 **日期前缀 + 标题** 命名，便于按时间管理

## 更新日志

### v2.0.0 (2026-07-14)
- ✅ 迁移到 MCP 协议层
- ✅ 集成 Obsidian Vault
- ✅ 支持新增分类（数据字典、业务规范、团队规范）
- ✅ 支持 wikilinks 和 YAML frontmatter
- ✅ 统一 MCP 客户端接口

### v1.0.0 (2026-07-14)
- ✅ 初始版本（本地 Markdown + BM25）
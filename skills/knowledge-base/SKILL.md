---
name: knowledge-base
description: 测试知识库管理 — 检索业务规则/历史用例/线上坑点，回灌优质产物，为生成环节提供 RAG 增强
version: 1.0.0
tags: [testing, knowledge-base, rag]
author: AI Assistant
created_by: agent
---

# 测试知识库 Skill

本地优先的测试知识库系统。在生成测试点、测试用例前，检索业务规则、历史优质用例和线上坑点，增强 AI 生成的业务贴合度；在评审通过后，将优质产物回灌知识库，持续沉淀。

## 触发条件

当用户说以下内容时，使用本 Skill：
- "搜索知识库" / "检索业务规则" / "查询坑点"
- "回灌知识库" / "沉淀用例" / "保存到知识库"
- "知识库状态" / "知识库概况"
- "导出知识上下文" / "增强上下文"
- 带有 "knowledge-base"、"知识库"、"RAG" 等关键词

## 知识库结构

```
~/Documents/ai-test-system/knowledge-base/
├── business-rules/          业务规则（字段限制、校验规则、业务逻辑）
│   ├── order-rules.md       订单业务规则
│   ├── payment-rules.md     支付业务规则
│   └── ...
├── historical-cases/        历史优质用例（评审通过的范例）
│   ├── order-cases.md       订单模块优质用例集
│   └── ...
├── pitfalls/                线上坑点（历史 Bug、踩坑记录）
│   ├── order-pitfalls.md    订单模块坑点
│   └── ...
├── templates/               用例模板（标准步骤、预期结果模板）
│   └── case-templates.md    通用用例编写模板
└── index.json               索引文件（自动维护）
```

### 知识分类

| 分类 | 目录 | 说明 | 示例 |
|------|------|------|------|
| 业务规则 | `business-rules/` | 字段限制、校验逻辑、业务流程规则 | "订单金额最小0.01元，最大999999.99元" |
| 历史用例 | `historical-cases/` | 评审通过的优质用例模板 | "支付回调处理的标准用例步骤" |
| 线上坑点 | `pitfalls/` | 历史 Bug、踩坑记录 | "并发下单时库存超卖，需加分布式锁" |
| 用例模板 | `templates/` | 标准用例编写模板和规范 | "异常测试的标准步骤写法" |

## 执行步骤

### 操作 1：检索知识库（search）

在生成测试点、用例前检索相关知识：

```bash
HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
$HERMES_PYTHON scripts/kb_manager.py search "订单支付" --kb-dir <knowledge-base路径>
```

**参数：**
- `query` — 检索关键词（必需）
- `--kb-dir` — 知识库目录（默认项目内 `knowledge-base/`）
- `--category` — 限定分类（business-rules/historical-cases/pitfalls/templates）
- `--limit` — 返回条数（默认 20）

**输出：** JSON 格式的匹配结果，每条包含分类、来源文件、匹配内容片段。

### 操作 2：导出增强上下文（export）

将检索结果格式化为 Markdown，直接注入后续生成环节：

```bash
$HERMES_PYTHON scripts/kb_manager.py export "订单支付" --output knowledge-context.md
```

**输出文件格式：**
```markdown
# 知识库增强上下文

> 检索关键词：订单支付 | 命中 8 条相关知识

## 📋 业务规则（3 条）
### 1. [order-rules.md] 支付方式限制
- 微信支付最低金额：0.01元
- 余额支付需验证支付密码
...

## 🏆 历史优质用例（2 条）
### 1. [order-cases.md] 支付回调重复处理（P0）
前置条件：...

## ⚠️ 线上坑点（3 条）
### 1. [order-pitfalls.md] 支付回调重复导致重复扣款
影响范围：高
...
```

### 操作 3：回灌优质产物（ingest）

将评审通过的优质用例、确认的业务规则、记录的坑点沉淀到知识库：

```bash
# 回灌用例文件
$HERMES_PYTHON scripts/kb_manager.py ingest testcases.xlsx --category historical-cases --module "订单支付"

# 回灌业务规则（从需求分析提取）
$HERMES_PYTHON scripts/kb_manager.py ingest requirements_analysis.md --category business-rules

# 回灌评审报告中的坑点
$HERMES_PYTHON scripts/kb_manager.py ingest test_report.md --category pitfalls
```

### 操作 4：添加单条知识（add）

手动添加单条知识：

```bash
$HERMES_PYTHON scripts/kb_manager.py add \
  --category pitfalls \
  --title "并发下单库存超卖" \
  --content "高并发场景下，库存扣减未加锁导致超卖。解决方案：Redis 分布式锁 + DB 乐观锁双重校验。" \
  --module "订单创建" \
  --severity high
```

### 操作 5：知识库概况（status）

```bash
$HERMES_PYTHON scripts/kb_manager.py status
```

输出各分类的条目数、最近更新时间、索引状态。

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

### ⚠️ 运行环境

脚本依赖 `openpyxl`（回灌 Excel 用例时需要），仅在 Hermes venv 中。纯文本检索不依赖外部库。

```bash
HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
$HERMES_PYTHON scripts/kb_manager.py <command> [options]
```

### 脚本功能

- 脚本位置：`scripts/kb_manager.py`
- 依赖：`openpyxl`（可选，仅 Excel 回灌时需要）
- 检索方式：TF-IDF 关键词匹配 + BM25 排序（纯标准库实现，无外部依赖）
- 索引维护：`index.json` 自动维护，记录每条知识的分类、来源、关键词、更新时间

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
📁 存储位置：knowledge-base/historical-cases/
```

**示例 3：记录线上坑点**
```
用户：记录一个坑点：支付回调重复导致重复扣款

AI：[调用 knowledge-base add --category pitfalls ...]
✅ 已记录到知识库
📁 存储位置：knowledge-base/pitfalls/payment-pitfalls.md
```

## 注意事项

1. 知识库为**本地 Markdown 文件**，不依赖外部 API，完全可控
2. 检索使用 TF-IDF + BM25，对中文友好（基于字符级和词级混合分词）
3. `index.json` 是缓存索引，删除后会自动重建
4. 回灌的用例会提取关键字段（编号、标题、步骤、预期结果），不会原样复制整个文件
5. 知识库需要定期维护，清理过时内容
6. 支持手动编辑 Markdown 文件来管理知识内容

## 更新日志

### v1.0.0 (2026-07-14)
- ✅ 初始版本
- ✅ 本地 Markdown 知识库（business-rules/historical-cases/pitfalls/templates）
- ✅ TF-IDF + BM25 检索引擎（纯标准库）
- ✅ 知识回灌（Excel/Markdown → 知识库）
- ✅ 增强上下文导出（Markdown 格式）
- ✅ 索引自动维护

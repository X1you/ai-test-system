# 测试用例生成全流程 Pipeline

基于微信公众号文章《我搭建了一套AI生成测试用例的全流程方案：7个可串联的 Skill 环节》。
原始方案作者：Raina测试。

## 流程链路

```
需求文档(.md)
    ↓ requirement-analysis (v1.2.0)
需求拆解 + 待确认清单
    ↓ [人工确认待确认事项]
test-points (v1.1.0)
    ↓
测试点清单(.md)
    ↓ generate-testcases (v1.0.0) ← 本 Skill
测试用例(.xlsx / .xmind)
    ↓ test-case-review (v1.0.0)
评审报告 + 整改建议
    ↓ [人工执行测试]
测试报告 (计划中: generate-report)
```

## 各环节输出文件

| 环节 | 输入 | 输出文件 |
|------|------|---------|
| requirement-analysis | requirements.md | requirements_analysis.md, clarification_needed.md, (可选)requirements_quality_report.md |
| test-points | requirements_analysis.md | testpoints.md |
| generate-testcases | testpoints.md | testcases.xlsx, testcases.xmind |
| test-case-review | testcases.xlsx (+ 可选 testpoints.md) | test_case_review_report.md |

## 测试维度体系（6维）

| 维度 | 中文 | 必需 | 过滤关键词 |
|------|------|------|-----------|
| 正向测试 | positive | ✅ | `positive`, `正向` |
| 负向测试 | negative | ✅ | `negative`, `负向` |
| 边界测试 | boundary | ✅ | `boundary`, `边界` |
| 异常测试 | exception | ✅ | `exception`, `异常` |
| 性能测试 | performance | 可选 | `performance`, `性能` |
| 安全测试 | security | 可选 | `security`, `安全` |
| 基础4维 | basic | — | `basic`（=正向+负向+边界+异常） |

## 优先级体系

| 优先级 | 分配规则 |
|--------|---------|
| P0 | 核心流程正向(下单/支付/退款/登录)、资金安全异常(并发/回调)、安全测试(越权/篡改/注入) |
| P1 | 一般功能正向、大部分负向、边界测试 |
| P2 | 性能测试、非核心功能、UI细节 |

## 实测数据（订单管理系统示例）

- 需求文档：82行 → 6模块 17功能点 60+可测项
- 测试点：145个（正向51, 负向30, 边界34, 异常30）
- 生成用例：145条 → Excel 18KB, XMind 9.4KB
- 优先级分布：P0:35, P1:110, P2:0

## 与原始方案的差异

- 原始方案基于 Cursor/Claude 的 `.claude/skills` 机制
- 本实现基于 Hermes Agent 的 `~/.hermes/skills/` 机制
- 原始方案的 Skill 通过知识星球付费获取
- 本实现为完全开源实现，Python 脚本可直接运行
- 原始方案未提及 XMind 文件格式细节（zip+content.json），本实现用纯标准库生成

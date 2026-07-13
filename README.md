# Hermes 测试用例生成系统

基于 Hermes Agent 的测试用例自动化生成全流程系统，实现从需求到测试报告的端到端自动化。

## 📖 项目背景

基于微信公众号文章《我搭建了一套AI生成测试用例的全流程方案：7个可串联的 Skill 环节》，实现一套完整的测试用例生成辅助系统。

**原始方案来源：** https://mp.weixin.qq.com/s/12fJisrYU-wGmqtXOt5XjA

## 🎯 项目目标

将测试用例生产拆成7个可串联的 Skill 环节，知识库 & RAG 横切增强中间链路，每个环节 AI 负责生成和整理，人负责确认和决策，在保留必要人工校验节点的前提下，整体提效。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Agent Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 需求读取 (MCP集成)                                         │
│     ├── 蓝湖 MCP Skill                                         │
│     ├── Figma MCP Skill                                        │
│     ├── Axure Parser                                           │
│     └── 飞书文档                                               │
│           ↓                                                   │
│  2. 需求分析 ✅ 已完成                                          │
│     ├── requirement-analysis Skill (v1.2.0)                    │
│     ├── 功能模块识别                                           │
│     ├── 功能点提取                                             │
│     ├── 待确认事项清单                                         │
│     └── 质量报告生成                                           │
│           ↓                                                   │
│  3. 知识库 & RAG ✅ 已完成                                      │
│     ├── knowledge-base Skill (v1.0.0)                         │
│     ├── BM25 检索引擎（纯标准库）                               │
│     ├── 历史用例检索                                           │
│     ├── 业务规则匹配                                           │
│     └── 线上坑点召回                                           │
│           ↓                                                   │
│  4. 测试点梳理 ✅ 已完成                                        │
│     ├── test-points Skill (v1.1.0)                            │
│     ├── 模块→功能点→测试维度→具体测试点                          │
│     ├── 6个测试维度支持                                        │
│     └── 优先级建议生成                                         │
│           ↓                                                   │
│  5. 生成测试用例 ✅ 已完成                                      │
│     ├── generate-testcases Skill (v1.0.0)                     │
│     ├── Excel 格式                                             │
│     └── XMind 格式                                             │
│           ↓                                                   │
│  6. 用例评审 ✅ 已完成                                          │
│     ├── test-case-review Skill (v1.0.0)                       │
│     ├── 四维质检                                               │
│     │   ├── 缺失用例检测                                       │
│     │   ├── 质量问题识别                                       │
│     │   ├── 重复冗余检查                                       │
│     │   └── 整改建议生成                                       │
│     └── 质量评分                                               │
│           ↓                                                   │
│  7. 生成测试报告 ✅ 已完成                                      │
│     ├── generate-report Skill (v1.0.0)                        │
│     ├── 质量摘要                                               │
│     ├── 失败分析                                               │
│     └── 模块覆盖率                                             │
│           ↓                                                   │
│  8. 知识库回灌 (Mem0)                                          │
│     └── 持续沉淀优质产物                                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## ✅ 已完成功能

### 1. 需求分析 Skill (v1.2.0)

**文件位置：** `~/.hermes/skills/requirement-analysis/`

**功能特性：**
- ✅ 需求文档结构化拆解
- ✅ 识别功能模块、功能点、可测项
- ✅ 生成待确认事项清单
- ✅ 优先级自动标注（高/中/低）
- ✅ 影响范围标注
- ✅ 质量报告生成（可选）

**输出文件：**
1. `requirements_analysis.md` - 需求拆解
2. `clarification_needed.md` - 待确认清单
3. `requirements_quality_report.md` - 质量报告（可选）

**使用示例：**
```
用户：帮我分析这个需求文档：requirements.md

AI：
✅ 需求分析完成！
📊 统计信息：
- 功能模块：6 个
- 功能点：17 个
- 可测项：60+ 个
- 待确认事项：22 个
```

**版本历史：**
- v1.0.0: 初始版本，基础需求分析功能
- v1.1.0: 移除手动脚本，改为 AI 直接调用
- v1.2.0: 添加优先级标注、质量报告、增强识别规则

---

### 2. 测试点梳理 Skill (v1.1.0)

**文件位置：** `~/.hermes/skills/test-points/`

**功能特性：**
- ✅ 基于需求分析生成测试点清单
- ✅ 结构化：模块→功能点→测试维度→具体测试点
- ✅ 支持6个测试维度（可配置）
  - 正向测试（必需）
  - 负向测试（必需）
  - 边界测试（必需）
  - 异常测试（必需）
  - 性能测试（可选）✨
  - 安全测试（可选）✨
- ✅ 每个测试点包含描述、测试数据、预期结果
- ✅ 测试优先级建议生成

**输出文件：**
- `testpoints.md` - 测试点清单

**使用示例：**
```
# 基础测试（4个维度）
用户：梳理测试点，基于 requirements_analysis.md

# 包含性能测试
用户：梳理测试点，包含性能测试

# 包含所有测试维度（6个维度）
用户：梳理测试点，包含性能和安全测试
```

**测试点分布示例（6个维度）：**
| 测试维度 | 数量 | 占比 |
|---------|------|------|
| 正向测试 | 22 个 | 22% |
| 负向测试 | 18 个 | 18% |
| 边界测试 | 14 个 | 14% |
| 异常测试 | 14 个 | 14% |
| 性能测试 | 17 个 | 17% |
| 安全测试 | 17 个 | 17% |

**版本历史：**
- v1.0.0: 初始版本，支持4个测试维度
- v1.1.0: 集成性能和安全测试生成功能，支持参数化配置

---

### 3. 用例评审 Skill (v1.0.0)

**文件位置：** `~/.hermes/skills/test-case-review/`

**功能特性：**
- ✅ 四维质检分析
  - 缺失用例检测（关键场景、边界条件、异常路径）
  - 质量问题识别（描述含糊、步骤不清晰、预期结果模糊）
  - 重复冗余检查（用例重复、场景重叠）
  - 整改建议生成（需澄清项、补充建议）
- ✅ 支持多种文件格式（Excel、Markdown、CSV）
- ✅ 质量评分功能（4个维度，满分100）
- ✅ 整改清单生成
- ✅ 测试点对比（可选）

**输出文件：**
- `test_case_review_report.md` - 评审报告

**使用示例：**
```
# 基本用法
用户：帮我评审测试用例 testcases.xlsx

AI：
✅ 用例评审完成！
📊 评审概况：
- 用例总数：50 个
- 通过质检：35 个
- 需要整改：15 个
- 质量评分：72/100（中等）

🎯 四维质检结果：
- 缺失用例：5 个
- 质量问题：8 个
- 重复冗余：2 对
- 整改建议：10 条
```

**质量评分标准：**
| 维度 | 满分 | 评分标准 |
|------|------|---------|
| 完整性 | 30 | 缺失用例越少，得分越高 |
| 清晰性 | 30 | 质量问题越少，得分越高 |
| 准确性 | 20 | 重复冗余越少，得分越高 |
| 可执行性 | 20 | 用例越具体、越可执行，得分越高 |

**版本历史：**
- v1.0.0: 初始版本，完整四维质检功能

---

### 4. Mem0 记忆系统集成 ✅ 已配置

**配置状态：**
- ✅ Mem0 API key 已配置
- ✅ Provider 设置为 mem0
- ✅ Memory enabled: true
- ✅ User profile enabled: true

**功能：**
- 持久化跨会话记忆
- 知识库增强
- 业务规则匹配
- 历史用例检索

---

### 5. 测试报告生成 Skill (v1.0.0)

**文件位置：** `~/.hermes/skills/testing/generate-report/`

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

**输出文件：** `test_report.md` - Markdown 测试报告

**使用示例：**
```
用户：生成测试报告，基于 testcases.xlsx

AI：
✅ 测试报告生成完成！

📊 总体概览：
- 总用例数：145 个
- 通过：101 个（69.7%）
- 失败：12 个
- 阻塞：18 个
- 跳过：14 个
- 质量评级：较差 ❌

📁 生成的文件：
- test_report.md - 测试报告（8.6 KB）

💡 下一步：
请根据报告中的失败用例分析和风险评估，优先修复高风险问题。
```

**质量评级标准：**
| 通过率 | 评级 | 说明 |
|--------|------|------|
| ≥ 95% | 优秀 🏆 | 可以发布 |
| 85%-95% | 良好 ✅ | 修复少量问题后可发布 |
| 70%-85% | 中等 ⚠️ | 需要修复较多问题 |
| < 70% | 较差 ❌ | 不建议发布 |

**版本历史：**
- v1.0.0: 初始版本，完整报告生成功能

---

## 🚧 计划中功能

### 1. 需求读取 MCP 集成 (计划中)

**功能规划：**
- 蓝湖 MCP：读取蓝湖原型链接，解析页面结构、UI元素、交互规则
- Figma MCP：读取 Figma 原型，解析布局、组件、设计规范
- Axure Parser：读取 Axure 原型，解析交互流程
- 飞书文档：读取飞书需求文档，解析结构化需求

**输出格式：**
- 统一的 Markdown 需求文档
- 作为后续所有环节的输入

---

### 4. 全流程自动化 (计划中)

**功能规划：**
- Cron Job 定时触发
- 自动读取新需求文档
- 自动执行：需求分析 → 测试点梳理 → 生成用例 → 用例评审
- 自动发送通知（QQ、邮件等）
- 知识库自动回灌

**Cron 配置示例：**
```bash
# 每天早上9点检查新需求并生成测试用例
hermes cron create "0 9 * * *" --prompt """
检查工作目录中的新需求文档（requirements/*.md），
依次执行：
1. 需求分析 → 2. 测试点梳理 → 3. 生成用例 → 4. 用例评审
输出文件保存到 outputs/ 目录，并发送通知。
"""
```

---

## 📂 项目文件结构

```
~/Documents/ai-test-system/
│
├── README.md                               📖 项目文档（本文件）
├── .gitignore
│
├── skills/                                 🔧 6 个核心 Skill 源码
│   ├── requirement-analysis/               ✅ v1.2.0
│   │   └── SKILL.md
│   ├── test-points/                        ✅ v1.1.0
│   │   └── SKILL.md
│   ├── generate-testcases/                 ✅ v1.0.0
│   │   ├── SKILL.md
│   │   ├── scripts/generate_excel.py       (Excel 生成脚本)
│   │   ├── scripts/generate_xmind.py       (XMind 生成脚本)
│   │   └── references/pipeline-overview.md
│   ├── test-case-review/                   ✅ v1.0.0
│   │   └── SKILL.md
│   ├── generate-report/                    ✅ v1.0.0
│   │   ├── SKILL.md
│   │   └── scripts/generate_report.py      (报告生成脚本)
│   └── knowledge-base/                     ✅ v1.0.0
│       ├── SKILL.md
│       └── scripts/kb_manager.py           (知识库管理脚本)
│
├── knowledge-base/                         🧠 本地知识库数据
│   ├── business-rules/                     (业务规则)
│   ├── historical-cases/                   (历史优质用例)
│   ├── pitfalls/                           (线上坑点)
│   ├── templates/                          (用例模板)
│   └── index.json                          (自动索引)
│
├── examples/                               📁 示例需求文档
│   ├── demo_requirements.md               (示例需求文档)
│   └── order_requirements.md              (订单系统需求文档)
│
├── sample-output/                          📁 各环节输出产物示例
│   ├── requirements_analysis.md            (需求拆解)
│   ├── clarification_needed.md             (待确认清单)
│   ├── requirements_quality_report.md      (质量报告)
│   ├── testpoints.md                       (测试点清单)
│   ├── testpoints_extended.md              (性能安全测试补充)
│   ├── testcases.xlsx                      (Excel 用例)
│   ├── testcases.xmind                     (XMind 用例)
│   ├── testcases_executed.xlsx             (带执行结果的用例)
│   └── test_report.md                      (测试报告)
│
├── reference/                              📚 参考资料和原始文章
│   └── 我搭建了一套AI生成测试用例的全流程方案....html
│
└── docs/                                   📝 额外文档（预留）

安装位置（运行时）：
~/.hermes/skills/                           ← Hermes 自动加载的 Skill 目录
```

---

## 🎯 使用流程

### 完整流程

```bash
# 1. 需求分析
引用 requirement-analysis Skill
输入：需求文档（requirements.md）
输出：需求拆解 + 待确认清单

# 2. 与产品/开发确认待确认事项
人工确认后更新需求文档

# 3. 测试点梳理
引用 test-points Skill
输入：需求拆解文档（requirements_analysis.md）
输出：测试点清单（testpoints.md）

# 4. 生成测试用例
引用 generate-testcases Skill
输入：测试点清单
输出：Excel/XMind 测试用例

# 5. 用例评审
引用 test-case-review Skill
输入：测试用例文件
输出：评审报告 + 整改建议

# 6. 执行测试用例
人工执行或自动化测试

# 7. 生成测试报告
引用 generate-report Skill
输入：执行结果（Excel）
输出：测试质量报告（Markdown）
```

### 渐进式使用

**阶段1：基础功能（当前可用）**
```
需求分析 → 测试点梳理 → 生成用例 → 用例评审 → 生成报告
```

**阶段2：完整流程（当前可用）**
```
需求文档 → 需求分析 → 测试点梳理 → 生成用例 → 用例评审 → 执行测试 → 生成报告
```

**阶段3：全自动化（计划中）**
```
需求读取(MCP) → 需求分析 → 测试点梳理 → 生成用例 → 用例评审 → 执行测试 → 生成报告 → 知识库回灌
```

---

## 📊 技术栈

### 核心技术
- **Hermes Agent** - AI 智能体平台
- **Mem0** - 外置记忆系统（RAG）
- **Skills** - 可复用的技能模块

### 文件格式
- **Markdown** - 需求文档、测试点、评审报告
- **Excel** - 测试用例、执行结果
- **XMind** - 测试用例脑图（计划中）

### 可选集成（计划中）
- **MCP (Model Context Protocol)** - 需求平台集成
- **蓝湖 API** - 原型读取
- **Figma API** - 设计稿读取
- **飞书 API** - 文档读取

---

## 🚀 快速开始

### 前置要求

1. 安装 Hermes Agent
2. 配置 Mem0 API key
3. 安装必要的 Skills

### 安装 Steps

```bash
# 1. 确认 Mem0 已配置
hermes config get memory.provider

# 2. 复制 Skills 到 Hermes 技能目录
cp -R skills/* ~/.hermes/skills/

# 3. 确认 Skills 已安装
hermes skills list | grep -E "requirement-analysis|test-points|generate-testcases|test-case-review|generate-report"
```

### 使用示例

```bash
# 启动 Hermes
hermes

# 在会话中使用
```

```
用户：帮我分析这个需求文档：~/Documents/requirements.md
AI：[自动调用 requirement-analysis Skill]

用户：梳理测试点，包含性能和安全测试
AI：[自动调用 test-points Skill]

用户：评审这个测试用例文件：testcases.xlsx
AI：[自动调用 test-case-review Skill]
```

---

## 📈 进度统计

### 已完成
- ✅ 需求分析 Skill (v1.2.0)
- ✅ 测试点梳理 Skill (v1.1.0)
- ✅ 测试用例生成 Skill (v1.0.0)
- ✅ 用例评审 Skill (v1.0.0)
- ✅ 测试报告生成 Skill (v1.0.0)
- ✅ 知识库 & RAG Skill (v1.0.0)
- ✅ Mem0 记忆系统集成
- ✅ 示例数据和文档

### 计划中
- 🚧 需求读取 MCP 集成
- 🚧 全流程自动化
- 🚧 Web UI 界面

### 完成度
- **核心 Skills：** 6/6 (100%) 🎉
- **辅助功能：** 2/4 (50%)
- **整体完成度：** ~85%

---

## 🎯 下一步计划

### 短期计划（1-2周）
1. **全流程联调测试**
   - 用真实需求文档跑通完整 pipeline
   - 修复发现的问题
   - 完善各 Skill 之间的数据传递

2. **generate-testcases v1.1 增强**
   - 用例模板自定义
   - 更多业务场景的步骤模板

### 中期计划（1-2月）
3. **需求读取 MCP 集成**
   - 蓝湖 MCP
   - Figma MCP
   - 飞书文档

4. **全流程自动化**
   - Cron Job 配置
   - 自动通知
   - 知识库回灌

### 长期计划（3-6月）
5. **Web UI 界面**
   - 可视化操作界面
   - 进度跟踪
   - 报告查看

6. **性能优化**
   - 大文档处理优化
   - 并发处理
   - 缓存机制

---

## 🤝 贡献指南

### 开发环境

```bash
# 进入技能目录
cd ~/.hermes/skills/[skill-name]

# 编辑 SKILL.md
vim SKILL.md

# 测试技能
hermes -s [skill-name]

# 提交改进
git add .
git commit -m "improve: [description]"
git push
```

### 技能开发规范

1. SKILL.md 必须包含：
   - Frontmatter（name, description, version, tags）
   - 触发条件
   - 执行步骤
   - 输入参数
   - 注意事项
   - 示例对话
   - 与其他 Skill 的协作

2. 版本号规范：
   - v1.0.0: 初始版本
   - v1.1.0: 小功能增加
   - v2.0.0: 重大功能变更

3. 文档更新：
   - 每次更新同步更新版本号
   - 记录更新日志

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

- **Nous Research** - Hermes Agent 平台
- **Raina测试** - 原始方案作者
- **Hermes 社区** - 技术支持

---

*最后更新：2026-07-14*
*当前版本：v0.6.0*
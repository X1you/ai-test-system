# AI 测试用例生成系统 — 需求规格说明书

> **版本**：v2.0.0
> **文档状态**：正式版
> **最后更新**：2026-07-17
> **作者**：AI Test System Team

---

## 目录

1. [项目概述](#1-项目概述)
2. [功能需求](#2-功能需求)
3. [非功能需求](#3-非功能需求)
4. [用户角色与权限](#4-用户角色与权限)
5. [系统架构](#5-系统架构)
6. [数据模型](#6-数据模型)
7. [接口说明](#7-接口说明)
8. [验收标准](#8-验收标准)
9. [附录](#9-附录)

---

## 1. 项目概述

### 1.1 项目背景

在软件测试领域，测试用例的编写是质量保障的核心环节。传统手工编写方式存在以下痛点：

- **效率低下**：从需求文档到测试用例需要大量人工分析和编写时间
- **覆盖不全**：依赖个人经验，容易遗漏边界、异常、安全等测试维度
- **质量波动**：不同测试工程师输出的用例质量参差不齐
- **知识流失**：团队积累的测试经验和线上问题难以系统化复用

AI 测试用例生成系统旨在通过大语言模型（LLM）和知识库增强检索（RAG）技术，实现从需求文档到测试报告的全流程自动化，在保留人工决策权的前提下，将测试用例生产效率提升 3-5 倍。

### 1.2 项目目标

| 目标维度 | 具体指标 | 衡量方式 |
|---------|---------|---------|
| 效率提升 | 测试用例生产时间缩短 60% 以上 | 从需求输入到完整用例输出的端到端耗时 |
| 质量保障 | 用例评审通过率 ≥ 85% | AI 四维质检评分 |
| 覆盖全面 | 6 维度测试覆盖，用例覆盖率达到 90%+ | 测试点维度分布统计 |
| 知识沉淀 | 历史用例和线上问题可检索、可复用 | 知识库命中率和回灌统计 |
| 易用性 | 5 分钟完成安装部署，零学习成本上手 | 新用户从安装到首次产出的时间 |

### 1.3 项目范围

**包含（In Scope）**：

- 基于 Markdown 需求文档的自动化测试用例生成
- 7 步 Pipeline 全流程编排（需求分析 → 知识库检索 → 测试点梳理 → 用例生成 → 评审 → 人工执行 → 报告）
- 知识库 7 分类管理（历史用例、业务规则、业务规范、数据字典、线上坑点、用例模板、团队规范）
- Excel（12 列标准格式）和 XMind（树状脑图）双格式输出
- CLI 命令行 + Web UI 双操作入口
- JWT 用户认证与 API Key 鉴权
- 外部测试管理平台（TestRail、TestLink 等）集成适配
- 断点续跑、人工检查点、三种执行模式

**不包含（Out of Scope）**：

- 自动化测试执行引擎（Step 6 为人工执行，非 UI 自动化）
- 移动端 App
- 多租户 SaaS 化（Track B 规划）
- 图数据库或向量数据库（Track B 规划）
- 自定义 DAG 工作流编排（Track B 规划）

### 1.4 术语定义

| 术语 | 英文 | 说明 |
|------|------|------|
| Pipeline | Pipeline | 7 步全流程自动化编排引擎 |
| 测试维度 | Test Dimension | 正向/负向/边界/异常/性能/安全 6 个测试视角 |
| 知识库 | Knowledge Base | 基于 Obsidian Vault 的本地文件系统知识库 |
| RAG | Retrieval-Augmented Generation | 检索增强生成，通过检索知识库增强 LLM 输出质量 |
| MCP | Model Context Protocol | 模型上下文协议，用于访问 Obsidian Vault 文件系统 |
| Canonical Model | Canonical Model | 内部标准数据模型，所有外部平台数据的统一表示 |
| 断点续跑 | Checkpoint Resume | 执行中断后从上次完成位置恢复继续执行 |
| SSE | Server-Sent Events | 服务器推送事件，用于实时进度推送 |

---

## 2. 功能需求

### 2.1 全流程 Pipeline 编排

#### 2.1.1 7 步流程定义

系统应按照以下 7 个步骤顺序执行全流程：

| 步骤 | 环节名称 | 执行方式 | 输出产物 | 类型 |
|------|---------|---------|---------|------|
| Step 1 | 需求分析 | AI 实时处理 | `requirements_analysis.md` + `clarification_needed.md` | AI 步骤 |
| Step 2 | 知识库检索 | 脚本自动化 | `knowledge-context.md` | 脚本步骤 |
| Step 3 | 测试点梳理 | AI 实时处理 | `testpoints.md` | AI 步骤 |
| Step 4 | 生成测试用例 | 脚本自动化 | `testcases.xlsx` + `testcases.xmind` | 脚本步骤 |
| Step 5 | 用例评审 | AI 实时处理 | `test_case_review_report.md` | AI 步骤 |
| Step 6 | 执行测试 | 人工执行 | 已填写执行结果的 `testcases.xlsx` | 人工步骤 |
| Step 7 | 生成测试报告 | 脚本自动化 | `test_report.md` | 脚本步骤 |

**规则**：

- 步骤必须按顺序执行，不可跳过或打乱
- 前一步骤的输出产物是后一步骤的输入依赖
- Step 2（知识库检索）在知识库未启用时应自动跳过，不阻塞流程
- Step 6（人工执行）检测到 Excel 执行结果列已填写时应自动标记完成

#### 2.1.2 三种执行模式

系统应支持以下三种执行模式：

| 模式 | 标识 | 行为描述 |
|------|------|---------|
| 全自动 | `auto` | AI 步骤连续执行，无人机交互，适合快速产出 |
| 半自动 | `semi`（默认） | 每个 AI 步骤（Step 1/3/5）完成后暂停，等待人工确认后继续 |
| 逐步骤 | `step` | 每步需手动触发，适合精细控制 |

**规则**：

- 半自动模式下，AI 步骤完成且自检通过后暂停，展示结果等待确认
- 逐步骤模式下，每一步完成后都暂停，等待用户手动触发下一步
- 模式切换不影响已完成的步骤，仅在断点恢复时生效

#### 2.1.3 断点续跑

系统应支持断点续跑机制：

- 每个步骤执行完成后，将完成状态写入 `_pipeline_state.json`
- 状态文件包含：启动时间、已完成步骤列表、各步骤结果、执行模式、需求文档路径
- 恢复执行时，跳过已完成且输出文件存在的步骤
- 支持 CLI 和 WebUI 两种恢复方式

#### 2.1.4 人工检查点

系统应在以下节点设置人工检查点：

- Step 1（需求分析）完成后：确认需求拆解和待确认清单
- Step 3（测试点梳理）完成后：确认测试点覆盖和优先级
- Step 5（用例评审）完成后：确认评审结果和整改建议
- Step 6（执行测试）：必须人工填写执行结果后才能继续

**规则**：

- 半自动模式下，检查点暂停等待确认
- 全自动模式下，检查点不暂停，连续执行
- 检查点处提供清晰的结果展示，支持用户判断是否继续

### 2.2 需求分析

#### 2.2.1 输入支持

- 支持 Markdown（`.md`）和纯文本（`.txt`）格式的需求文档
- 支持文件路径和直接文本两种输入方式
- 文件大小限制：最大 10MB
- 支持指定需求文档路径启动全流程

#### 2.2.2 分析输出

要求 LLM 输出以下结构化内容：

- **需求拆解**：按模块 → 功能点 → 可测项三级结构拆解
- **待确认清单**：按优先级（高/中/低）分类的模糊事项
- **影响范围**：标注各模块之间的依赖和影响关系
- 统计信息：模块数、功能点数、待确认事项数

#### 2.2.3 质量自检

- 支持 LLM 对自身输出进行质量评估
- 自检不通过时，自动携带改进意见重跑一次
- 自检标准：结构完整性、逻辑一致性、可测项覆盖率

### 2.3 知识库管理

#### 2.3.1 知识库分类

系统应支持以下 7 个分类的知识库：

| 分类 | 目录 | 说明 |
|------|------|------|
| 历史优质用例 | `历史用例/` | 评审通过的优质用例，按项目/批次三层归档 |
| 业务规则 | `业务规则/` | 字段限制、校验规则、业务逻辑 |
| 业务规范文档 | `业务规范/` | 产品功能说明、状态流转规则、权限矩阵 |
| 数据字典 | `数据字典/` | 表字段释义、枚举值、关联关系 |
| 线上问题沉淀 | `线上坑点/` | 历史 Bug、常见边界坑点、易漏场景 |
| 团队模板规范 | `用例模板/` | 用例编写模板、命名规范、断言规则 |
| 团队规范 | `团队规范/` | 测试流程规范等 |

#### 2.3.2 检索功能

- 关键词检索：根据从需求分析中提取的关键词进行多关键词匹配
- 三层搜索策略：
  - Layer 1：Obsidian Local REST API 搜索（利用 Obsidian 内置索引）
  - Layer 2：标签匹配（YAML frontmatter 中的 tags 字段，命中加权 2.0）
  - Layer 3：全文遍历 + 多关键词 OR 匹配
- 导出增强上下文：按分类分组的 Markdown 格式，注入 Step 3 和 Step 5

#### 2.3.3 回灌功能

- 支持从 Excel 回灌知识，自动识别 12 列标准格式和通用 3 列格式
- 历史用例按 `项目名/批次/TC-xxx.md` 三层归档
- 支持添加单条知识条目
- 回灌内容自动提取关键词标签

#### 2.3.4 知识库状态

- 统计各分类条目数
- 统计标签分布
- 展示知识库总体规模

### 2.4 测试点梳理

#### 2.4.1 测试维度

系统应支持 6 个测试维度：

| 维度 | 类别 | 说明 |
|------|------|------|
| 正向测试 | 必需 | 验证正常业务流程和预期行为 |
| 负向测试 | 必需 | 验证无效输入和异常操作的处理 |
| 边界测试 | 必需 | 验证输入边界值和临界条件 |
| 异常测试 | 必需 | 验证系统异常和错误恢复能力 |
| 性能测试 | 可选 | 验证响应时间和并发处理能力 |
| 安全测试 | 可选 | 验证权限控制、数据保护和注入防护 |

**配置选项**：

- `basic`：仅包含 4 个必需维度（正向/负向/边界/异常）
- `all`：包含全部 6 个维度
- 自定义：通过逗号分隔指定维度，如 `positive,negative,boundary`

#### 2.4.2 测试点结构

每个测试点应包含：

- 所属模块和功能点
- 测试维度
- 测试点描述
- 测试数据
- 预期结果
- 优先级建议（P0/P1/P2）

#### 2.4.3 优先级分配规则

基于多级决策表自动分配优先级：

- **P0（核心）**：核心模块的核心功能正向测试、关键安全测试
- **P1（重要）**：非核心模块的正向测试、核心模块的负向/边界测试
- **P2（一般）**：非核心模块的负向/边界测试、异常测试、性能测试

### 2.5 测试用例生成

#### 2.5.1 Excel 格式

Excel 测试用例应包含以下 12 列标准结构：

| 列名 | 说明 |
|------|------|
| 编号 | TC-001 ~ TC-NNN，自动连续编号 |
| 模块 | 所属功能模块 |
| 功能点 | 所属功能点 |
| 标题 | 用例标题 |
| 测试维度 | 正向/负向/边界/异常/性能/安全 |
| 优先级 | P0/P1/P2 |
| 前置条件 | 执行前需要满足的条件 |
| 测试步骤 | 具体操作步骤 |
| 测试数据 | 输入数据 |
| 预期结果 | 期望的输出结果 |
| 执行结果 | 通过/失败/阻塞/跳过（Step 6 填写） |
| 备注 | 额外说明 |

**格式化要求**：

- 优先级着色：P0 红色、P1 橙色、P2 黄色
- 冻结首行（表头行）
- 启用自动筛选
- 自动调整列宽

#### 2.5.2 XMind 格式

- 树状脑图结构：模块 → 功能点 → 测试维度 → 测试点
- 每个测试点显示优先级标签
- 测试点下包含测试数据和预期结果子节点
- 根节点包含统计信息（总用例数、模块数、优先级分布、维度分布）

#### 2.5.3 步骤模板

系统应内置 16 种动作关键词的步骤模板：

- 登录、注册、上传、创建、编辑、删除、查询
- 评审、回灌、报告、集成、校验、审核、导出、导入、配置

每种动作包含正向和负向两套步骤模板，根据测试维度自动匹配。

#### 2.5.4 生成控制

- 支持按测试维度过滤（`-d` 参数）
- 支持选择输出格式：Excel、XMind、或同时输出
- 如果 Excel 已存在且含执行结果，跳过生成以保护已填写数据

### 2.6 用例评审

#### 2.6.1 四维质检体系

| 维度 | 满分 | 评分标准 |
|------|------|---------|
| 完整性 | 30 | 缺失用例越少，得分越高 |
| 清晰性 | 30 | 质量问题越少，得分越高 |
| 准确性 | 20 | 重复冗余越少，得分越高 |
| 可执行性 | 20 | 用例越具体、越可执行，得分越高 |

#### 2.6.2 评审输出

- 总分和等级（优秀/良好/中等/较差）
- 各维度详细评分
- 缺失用例检测和补充建议
- 质量问题识别和修复建议
- 重复冗余检查
- 整改清单

#### 2.6.3 等级划分

| 分数范围 | 等级 | 说明 |
|---------|------|------|
| >= 90 | 优秀 | 可直接使用 |
| 75 ~ 89 | 良好 | 少量修改后使用 |
| 60 ~ 74 | 中等 | 需要较多修改 |
| < 60 | 较差 | 建议重新生成 |

### 2.7 测试报告生成

#### 2.7.1 报告章节

报告应包含以下 8 个章节：

1. **总体概览**：总数、通过/失败/阻塞/跳过、通过率、执行率
2. **模块通过率分布**：按模块维度统计
3. **优先级分析**：按 P0/P1/P2 统计
4. **测试维度分析**：按测试维度统计
5. **失败用例分析**：含失败原因推断和修复建议
6. **阻塞用例分析**：阻塞原因分析
7. **风险评估**：高/中/低三级，综合风险等级
8. **测试结论与建议**：发布建议

#### 2.7.2 发布建议

| 条件 | 建议 |
|------|------|
| P0 全部通过，通过率 >= 95% | 可以发布 |
| 通过率 85% ~ 95% | 修复少量问题后可发布 |
| 通过率 70% ~ 85% | 需要修复较多问题 |
| 通过率 < 70% 或存在高风险项 | 不建议发布 |

#### 2.7.3 失败原因推断

系统应支持 11 类失败原因推断，结合维度加权分析：

- 功能缺陷、数据问题、环境问题、配置错误
- 兼容性问题、性能问题、安全漏洞、UI 问题
- 接口问题、并发问题、文档问题

### 2.8 外部集成

#### 2.8.1 支持的平台

- TestRail（通过 REST API）
- TestLink（通过 XML-RPC）
- 可扩展架构：通过适配器模式支持更多平台

#### 2.8.2 同步功能

- 推送测试用例到外部平台
- 拉取测试用例从外部平台
- 推送测试结果
- 拉取测试结果和缺陷
- 增量同步（基于 `updated_at` 时间戳）
- 全量同步

#### 2.8.3 冲突解决

双向同步时支持 4 种冲突解决策略：

- `last_write_wins`：最后写入者胜出
- `source_wins`：源端数据优先
- `target_wins`：目标端数据优先
- `manual`：手动解决

#### 2.8.4 Webhook 接收

- 支持接收外部平台事件推送
- 自动验证签名
- 解析事件并触发同步

### 2.9 用户界面

#### 2.9.1 CLI 命令行

提供以下 4 个命令：

| 命令 | 功能 | 示例 |
|------|------|------|
| `run` | 启动全流程 Pipeline | `python cli.py run requirements.md --mode auto` |
| `resume` | 从断点继续执行 | `python cli.py resume -o output/` |
| `status` | 查看 Pipeline 状态 | `python cli.py status -o output/` |
| `config` | 查看当前配置 | `python cli.py config` |

#### 2.9.2 Web UI

提供以下页面：

| 页面 | 路由 | 功能 |
|------|------|------|
| 首页 | `/` | 上传需求文档，启动 Pipeline |
| Pipeline 进度 | `/pipeline/{id}` | 实时查看 7 步进度 |
| 结果预览 | `/results/{id}` | 查看和下载产物 |
| 知识库管理 | `/knowledge` | 搜索和查看知识库状态 |
| Pipeline 列表 | `/pipelines` | 历史任务列表 |
| 登录 | `/login` | 用户登录 |

#### 2.9.3 实时进度推送

- 基于 SSE（Server-Sent Events）实现实时进度更新
- 15 秒心跳保活，防止代理超时断开
- 步骤完成时推送事件，前端自动更新进度条
- 终端事件（done/error/cancelled）后自动关闭流

### 2.10 配置管理

#### 2.10.1 配置来源优先级

系统应按照以下优先级加载配置：

1. 命令行指定的配置文件路径
2. 项目根目录 `config.yaml`
3. 代码内置默认值

#### 2.10.2 环境变量支持

- 配置文件中的 `${VAR_NAME}` 占位符自动替换为环境变量值
- 支持 `${VAR_NAME:-default}` 默认值语法
- 自动加载 `.env` 文件（不覆盖已有环境变量）

#### 2.10.3 配置项清单

| 配置域 | 配置项 | 类型 | 默认值 | 说明 |
|--------|--------|------|--------|------|
| llm | provider | string | deepseek | 模型提供商 |
| llm | api_key | string | - | API Key（支持环境变量引用） |
| llm | base_url | string | https://api.deepseek.com | API 地址 |
| llm | model | string | deepseek-v4-flash | 模型名称 |
| llm | temperature | float | 0.3 | 生成温度（0-1） |
| llm | max_tokens | int | 8192 | 最大输出 Token |
| llm | timeout | int | 120 | 单次请求超时（秒） |
| llm | retry | int | 2 | 失败重试次数 |
| knowledge_base | enabled | bool | true | 是否启用知识库 |
| knowledge_base | vault_path | string | - | Obsidian Vault 路径 |
| pipeline | default_mode | string | semi | 默认执行模式 |
| pipeline | default_dimensions | string | basic | 默认测试维度 |
| pipeline | default_formats | string | excel | 默认输出格式 |
| pipeline | self_check | bool | true | 是否启用 AI 自检 |
| pipeline | max_concurrent | int | 2 | 最大并发任务数 |
| output | dir | string | ./output | 输出目录 |

---

## 3. 非功能需求

### 3.1 性能需求

| 指标 | 要求 | 衡量方式 |
|------|------|---------|
| 需求分析响应时间 | ≤ 2 分钟 | 从提交到输出完成的端到端耗时 |
| 测试点生成响应时间 | ≤ 3 分钟 | 从提交到输出完成的端到端耗时 |
| 用例评审响应时间 | ≤ 2 分钟 | 从提交到输出完成的端到端耗时 |
| 脚本步骤执行时间 | ≤ 3 秒 | 知识库检索、Excel/XMind 生成、报告生成 |
| 知识库检索响应时间 | ≤ 1 秒 | 单次关键词检索 |
| 并发 Pipeline 处理 | ≥ 2 个 | 同时运行的 Pipeline 数量 |
| 文件上传大小 | ≤ 10 MB | 需求文档上传限制 |
| LLM Token 超时 | 120 秒 | 单次 API 请求超时 |

### 3.2 可靠性需求

| 指标 | 要求 |
|------|------|
| 断点恢复 | 任何步骤失败后，可从断点恢复继续执行 |
| LLM 故障转移 | 主 Provider 失败时自动切换到备选 Provider |
| 数据持久化 | Pipeline 元数据写入 SQLite，执行中断不丢失 |
| 文件锁保护 | 并发写入时通过 `fcntl.flock` 文件锁保护，避免冲突 |
| 错误处理 | 所有异常捕获并记录，不导致系统崩溃 |
| 重试机制 | LLM 调用失败自动重试（指数退避，最多 2 次） |

### 3.3 安全性需求

| 类别 | 需求描述 |
|------|---------|
| 认证 | 支持 JWT Token 认证和 API Key 鉴权 |
| 密码安全 | 用户密码使用 bcrypt 哈希存储 |
| API Key 脱敏 | 配置查询时 API Key 自动脱敏（仅显示前 4 位和后 4 位） |
| 速率限制 | Web API 接口支持速率限制 |
| 路径穿越防护 | 文件下载和上传接口校验文件名，防止路径穿越攻击 |
| 安全响应头 | Web 服务添加安全响应头（Content-Security-Policy 等） |
| CORS 配置 | 生产环境可配置 CORS 白名单 |
| 输入校验 | 所有用户输入进行校验，防止注入攻击 |

### 3.4 可维护性需求

| 类别 | 需求描述 |
|------|---------|
| 模块化设计 | 核心引擎、Web UI、数据库、集成适配层相互解耦 |
| 配置外部化 | 所有配置通过 YAML 文件和环境变量管理，不硬编码 |
| 数据库迁移 | 使用 Alembic 管理数据库版本迁移 |
| 日志记录 | 关键操作记录日志，支持结构化日志 |
| 代码规范 | 遵循 PEP 8，使用 ruff 进行代码检查 |
| 类型注解 | 核心模块使用 Python 类型注解 |
| 版本管理 | 遵循语义化版本规范（SemVer），记录 CHANGELOG |

### 3.5 可扩展性需求

| 类别 | 需求描述 |
|------|---------|
| LLM Provider | 支持所有 OpenAI 兼容协议的模型，新增 Provider 仅需配置 |
| 测试平台 | 适配器模式，新增外部平台仅需实现 `BaseAdapter` 接口 |
| 字段映射 | 平台字段映射通过 YAML 配置文件驱动，无需修改代码 |
| 数据库 | SQLAlchemy 抽象层，切换 SQLite 到 PostgreSQL 仅需改连接串 |
| 多租户 | 数据模型已预留 `tenant_id` 字段，支持未来多租户演进 |
| 工作流 | 预留 `workflow_id` 字段，支持未来 DAG 可配置工作流 |
| 部署方式 | 支持 pip 安装、Docker 容器化部署 |

### 3.6 兼容性需求

| 类别 | 需求描述 |
|------|---------|
| 操作系统 | macOS、Linux（Windows 通过 WSL 支持） |
| Python 版本 | ≥ 3.11 |
| LLM Provider | DeepSeek、智谱 GLM、OpenAI、Moonshot、通义千问 |
| 浏览器 | Chrome、Firefox、Safari、Edge 最新两个大版本 |
| 文件格式 | Markdown、Excel（.xlsx）、XMind、CSV |

### 3.7 可用性需求

| 类别 | 需求描述 |
|------|---------|
| 安装部署 | 5 分钟完成安装，3 条命令即可启动 |
| 文档完备 | README、快速开始指南、架构文档、迁移指南 |
| 错误提示 | 清晰的错误信息，包含原因和解决建议 |
| 示例需求 | 提供示例需求文档，方便新用户快速体验 |

---

## 4. 用户角色与权限

### 4.1 角色定义

| 角色 | 权限范围 | 说明 |
|------|---------|------|
| 管理员（admin） | 全部功能 | 系统配置、用户管理、全部 Pipeline 管理 |
| 普通用户（user） | 基本功能 | 创建和管理自己的 Pipeline、查看知识库 |
| API 用户 | 程序化调用 | 通过 API Key 调用 REST API |

### 4.2 权限矩阵

| 功能 | 管理员 | 普通用户 | API 用户 | 未登录 |
|------|--------|---------|---------|--------|
| 创建 Pipeline | ✅ | ✅ | ✅ | ❌ |
| 查看自己的 Pipeline | ✅ | ✅ | ✅ | ❌ |
| 查看所有 Pipeline | ✅ | ❌ | ❌ | ❌ |
| 取消 Pipeline | ✅ | ✅（仅自己的） | ✅（仅自己的） | ❌ |
| 下载产物 | ✅ | ✅ | ✅ | ❌ |
| 查看配置 | ✅ | ✅ | ❌ | ❌ |
| 修改配置 | ✅ | ❌ | ❌ | ❌ |
| 管理知识库 | ✅ | ✅ | ❌ | ❌ |
| 管理用户 | ✅ | ❌ | ❌ | ❌ |
| 查看知识库 | ✅ | ✅ | ❌ | ❌ |

### 4.3 认证方式

| 认证方式 | 适用场景 | 实现方式 |
|---------|---------|---------|
| 用户名密码 | Web UI 登录 | JWT Token（Bearer） |
| API Key | REST API 调用 | Header `X-API-Key` |
| 平台认证 | 外部平台集成 | API Key / Basic Auth / OAuth2 |

---

## 5. 系统架构

### 5.1 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    接入层 (Access Layer)                       │
│                                                              │
│   CLI (click)    │    WebUI (HTMX + Jinja2 + SSE)   │  REST  │
│                  │    + JWT 认证                      │  API  │
├──────────────────────────────────────────────────────────────┤
│                    服务层 (Service Layer)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PipelineService                                        │  │
│  │  TaskBackend (asyncio) + EventBus (pub/sub) + SSE      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LLM Gateway 轻量版                                      │  │
│  │  Provider 路由 │ 故障转移 │ 用量统计                     │  │
│  └────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│                  核心引擎层 (Core Engine)                      │
│                                                              │
│  Pipeline Engine (7 步) │ Steps │ Prompts │ LLM Client       │
├──────────────────────────────────────────────────────────────┤
│               数据与基础设施层 (Data & Infra)                  │
│                                                              │
│  SQLite (元数据) │ 文件存储 (产物) │ Obsidian Vault (知识库)   │
│  集成适配层 (Integration Layer)                               │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 分层说明

#### 5.2.1 接入层

| 组件 | 技术栈 | 职责 |
|------|--------|------|
| CLI | Python argparse | `run` / `resume` / `status` / `config` 四个命令 |
| Web UI | FastAPI + HTMX + Jinja2 + SSE | 浏览器操作界面，实时进度推送 |
| REST API | FastAPI | 程序化调用，支持 API Key 认证 |

#### 5.2.2 服务层

- **PipelineService**：任务生命周期管理，包含 TaskBackend（任务调度）、EventBus（事件分发）、TaskManager（任务管理）
- **LLM Gateway**：多 Provider 路由、自动故障转移、调用统计

#### 5.2.3 核心引擎层

- **Pipeline Engine**：7 步串联编排，断点续跑，三种执行模式
- **Steps**：7 个步骤实现（Step 1-7）
- **Prompts**：AI 提示词模板管理
- **LLM Client**：兼容 OpenAI 协议的 LLM 调用抽象层

#### 5.2.4 数据层

- **SQLite（WAL 模式）**：Pipeline 元数据持久化
- **文件存储**：Pipeline 产物（Excel/XMind/Markdown）
- **Obsidian Vault**：知识库 7 分类文件系统

### 5.3 技术选型

| 层 | 技术 | 选型理由 |
|----|------|---------|
| 语言 | Python 3.11+ | 丰富的 AI/ML 生态，团队熟悉 |
| LLM SDK | openai Python SDK | 兼容所有 OpenAI 协议模型 |
| Web 后端 | FastAPI | 异步高性能，自带 OpenAPI 文档 |
| Web 前端 | HTMX + Jinja2 | 纯 Python 栈，无需 Node.js 构建链 |
| 数据库 | SQLite (WAL) | 零运维，嵌入式，SQLAlchemy 抽象保证可切换 |
| 知识库 | Obsidian Vault + MCP | 本地文件系统，路径可配置 |
| ORM | SQLAlchemy 2.0 | 成熟的 Python ORM |
| 迁移 | Alembic | SQLAlchemy 官方迁移工具 |
| 认证 | python-jose + bcrypt | JWT 标准 + 安全密码哈希 |
| 测试 | pytest | Python 标准测试框架 |

### 5.4 模块依赖关系

```
cli.py
├── core/config_loader.py
│   └── (.env, config.yaml)
└── core/pipeline.py
    ├── core/llm_client.py ─── openai
    ├── core/llm_gateway.py ─── core/llm_client.py
    ├── core/steps/base.py ─── core/llm_client.py
    ├── core/steps/step1_analysis.py ─── core/prompt_loader.py
    ├── core/steps/step2_kb_search.py ─── core/kb/kb_manager_mcp.py ─── core/kb/mcp_client.py
    ├── core/steps/step3_testpoints.py ─── core/prompt_loader.py
    ├── core/steps/step4_generate.py ─── scripts/generate_excel.py + generate_xmind.py
    ├── core/steps/step5_review.py ─── core/prompt_loader.py
    ├── core/steps/step6_human_test.py
    └── core/steps/step7_report.py ─── scripts/generate_report.py

web/app.py
├── web/api/pipeline.py ─── web/services/task_manager.py
│   └── web/services/pipeline_task.py
│       ├── core/pipeline.py
│       ├── db/repository.py ─── db/models.py, db/session.py
│       └── web/services/event_bus.py
├── web/api/knowledge.py ─── core/kb/kb_manager_mcp.py
├── web/api/config.py ─── core/config_loader.py
├── web/api/auth.py ─── web/services/user_service.py
├── web/api/sse.py ─── web/services/event_bus.py
└── web/api/webhooks.py ─── integrations/registry.py
```

---

## 6. 数据模型

### 6.1 数据库表结构

#### 6.1.1 pipelines（Pipeline 实例表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | VARCHAR(32) | PK | Pipeline 唯一标识（UUID 前 8 位） |
| requirements_path | VARCHAR(512) | NOT NULL | 需求文档路径 |
| mode | VARCHAR(16) | DEFAULT 'semi' | 执行模式（auto/semi/step） |
| dimensions | VARCHAR(64) | DEFAULT 'basic' | 测试维度（basic/all/自定义） |
| formats | VARCHAR(64) | DEFAULT 'excel' | 输出格式（excel/xmind/excel,xmind） |
| status | VARCHAR(16) | DEFAULT 'pending' | 状态（pending/running/paused/done/error/cancelled） |
| started_at | DATETIME | NOT NULL | 启动时间 |
| finished_at | DATETIME | NULLABLE | 完成时间 |
| error | TEXT | NULLABLE | 错误信息 |
| output_dir | VARCHAR(512) | DEFAULT '' | 输出目录路径 |
| tenant_id | VARCHAR(32) | NULLABLE, INDEX | 租户 ID（Track B 预留） |
| workflow_id | VARCHAR(64) | NULLABLE | 工作流 ID（Track B 预留） |

#### 6.1.2 pipeline_steps（步骤执行记录表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 自增主键 |
| pipeline_id | VARCHAR(32) | FK → pipelines.id, CASCADE | 所属 Pipeline |
| step_id | INTEGER | NOT NULL | 步骤序号（1-7） |
| name | VARCHAR(64) | NOT NULL | 步骤名称 |
| status | VARCHAR(16) | NOT NULL | 执行状态 |
| detail | TEXT | NULLABLE | 执行详情 |
| started_at | DATETIME | NULLABLE | 开始时间 |
| finished_at | DATETIME | NULLABLE | 完成时间 |
| llm_calls | TEXT | NULLABLE | LLM 调用详情（JSON） |
| retry_count | INTEGER | DEFAULT 0 | 重试次数 |

#### 6.1.3 artifacts（产物元数据表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 自增主键 |
| pipeline_id | VARCHAR(32) | FK → pipelines.id, CASCADE | 所属 Pipeline |
| name | VARCHAR(255) | NOT NULL | 文件名 |
| display_name | VARCHAR(255) | NOT NULL | 显示名称 |
| type | VARCHAR(32) | NOT NULL | 文件类型（md/xlsx/xmind/json） |
| size | BIGINT | DEFAULT 0 | 文件大小（字节） |
| created_at | DATETIME | NOT NULL | 创建时间 |

#### 6.1.4 users（用户表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 自增主键 |
| username | VARCHAR(64) | UNIQUE, INDEX | 用户名 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 密码哈希 |
| role | VARCHAR(32) | DEFAULT 'user' | 角色（admin/user） |
| api_key | VARCHAR(64) | NULLABLE, INDEX | API 密钥 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| last_login | DATETIME | NULLABLE | 最后登录时间 |
| tenant_id | VARCHAR(32) | NULLABLE, INDEX | 租户 ID（Track B 预留） |

### 6.2 实体关系图

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│  User    │       │   Pipeline   │       │ Artifact │
├──────────┤       ├──────────────┤       ├──────────┤
│ id (PK)  │       │ id (PK)      │──┐    │ id (PK)  │
│ username │       │ requirements │  │    │ pipeline │──┐
│ password │       │ mode         │  │    │ name     │  │
│ role     │       │ dimensions   │  │    │ type     │  │
│ api_key  │       │ formats      │  │    │ size     │  │
└──────────┘       │ status       │  │    └──────────┘  │
                   │ started_at   │  │                   │
                   │ finished_at  │  │    ┌──────────────┤
                   │ output_dir   │  │    │PipelineStep  │
                   └──────────────┘  │    ├──────────────┤
                          │          │    │ id (PK)      │
                          │          └────│ pipeline_id  │
                          │               │ step_id      │
                          └───────────────│ name         │
                                          │ status       │
                                          └──────────────┘
```

### 6.3 Canonical Model（内部标准数据模型）

用于外部平台数据统一表示的核心数据类：

| 数据类 | 说明 | 关键字段 |
|--------|------|---------|
| TestCase | 标准测试用例 | id, title, module, priority, dimension, steps, expected_result, status |
| TestResult | 测试执行结果 | test_case_id, status, comment, executed_by, executed_at |
| TestRun | 测试运行 | id, name, total, passed, failed, blocked, skipped |
| Defect | 缺陷信息 | id, title, severity, status, linked_test_cases |
| SyncResult | 同步结果 | sync_id, direction, pushed, pulled, failed, errors |
| SyncLogEntry | 同步日志 | sync_id, platform, direction, entity_type, action, status |

### 6.4 Pipeline 状态机

```
                    ┌─────────┐
                    │ pending │
                    └────┬────┘
                         │ start
                    ┌────▼────┐
               ┌───►│ running │◄───┐
               │    └────┬────┘    │
               │         │         │ resume
               │    ┌────▼────┐    │
               │    │ paused  │────┘
               │    └─────────┘
               │
               │    ┌─────────┐
               ├───►│  done   │
               │    └─────────┘
               │
               │    ┌─────────┐
               ├───►│  error  │
               │    └─────────┘
               │
               │    ┌──────────┐
               └───►│cancelled │
                    └──────────┘
```

---

## 7. 接口说明

### 7.1 REST API

#### 7.1.1 Pipeline 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/pipeline/start` | 上传需求文档并启动 Pipeline | 需要 |
| GET | `/api/pipeline/{id}/progress` | 获取任务进度（JSON/HTMX） | 需要 |
| GET | `/api/pipeline/{id}/status` | 获取详细状态 | 需要 |
| GET | `/api/pipeline/{id}/stream` | SSE 实时进度推送 | 需要 |
| POST | `/api/pipeline/{id}/resume` | 从断点继续（可上传已执行 Excel） | 需要 |
| POST | `/api/pipeline/{id}/cancel` | 取消 Pipeline | 需要 |
| GET | `/api/pipeline/list` | 获取任务列表 | 需要 |
| GET | `/api/pipeline/{id}/artifacts` | 获取产物列表 | 需要 |
| GET | `/api/pipeline/{id}/artifacts/{name}` | 下载产物文件 | 需要 |
| GET | `/api/pipeline/{id}/preview/{name}` | 预览产物（Markdown/Excel） | 需要 |

**启动 Pipeline 请求参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| file | File | 是 | - | 需求文档（.md/.txt） |
| mode | string | 否 | semi | 执行模式（auto/semi/step） |
| dimensions | string | 否 | basic | 测试维度（basic/all/自定义） |
| formats | string | 否 | excel | 输出格式（excel/xmind/excel,xmind） |

**启动 Pipeline 响应**：

```json
{
  "pipeline_id": "a1b2c3d4",
  "redirect": "/pipeline/a1b2c3d4",
  "status": "running"
}
```

**进度查询响应**：

```json
{
  "pipeline_id": "a1b2c3d4",
  "status": "running",
  "mode": "semi",
  "percent": 57,
  "completed_steps": [1, 2, 3, 4],
  "current_step": 5,
  "steps": [
    {"step_id": 1, "name": "需求分析", "status": "done"},
    {"step_id": 2, "name": "知识库检索", "status": "done"},
    {"step_id": 3, "name": "测试点梳理", "status": "done"},
    {"step_id": 4, "name": "生成测试用例", "status": "done"},
    {"step_id": 5, "name": "用例评审", "status": "running"},
    {"step_id": 6, "name": "执行测试", "status": "pending"},
    {"step_id": 7, "name": "生成测试报告", "status": "pending"}
  ],
  "logs": ["..."]
}
```

#### 7.1.2 知识库接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/kb/status` | 知识库统计信息 | 需要 |
| GET | `/api/kb/search?q=keyword` | 搜索知识库 | 需要 |

#### 7.1.3 配置接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/config` | 查看当前配置（API Key 脱敏） | 需要 |

#### 7.1.4 认证接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/auth/login` | 用户名密码登录 | 否 |
| POST | `/api/auth/logout` | 登出 | 否 |
| GET | `/api/auth/me` | 获取当前用户信息 | 需要 |

#### 7.1.5 Webhook 接口

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/webhooks/{platform}` | 接收外部平台事件推送 | 平台签名 |

#### 7.1.6 健康检查

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/health` | 检查数据库、LLM 配置、知识库连通性 | 否 |

### 7.2 CLI 接口

| 命令 | 参数 | 说明 |
|------|------|------|
| `ai-test run <file>` | `--mode`, `-d`, `-f`, `-o` | 启动全流程 |
| `ai-test resume` | `-o` | 从断点继续 |
| `ai-test status` | `-o` | 查看状态 |
| `ai-test config` | - | 查看配置 |

### 7.3 SSE 事件格式

| 事件类型 | 触发时机 | 数据格式 |
|---------|---------|---------|
| `step_started` | 步骤开始执行 | `{"step_id": 1, "name": "需求分析"}` |
| `step_done` | 步骤执行完成 | `{"step_id": 1, "name": "需求分析", "ok": true}` |
| `log` | 日志输出 | `{"level": "OK", "message": "..."}` |
| `done` | Pipeline 完成 | `{"status": "done"}` |
| `error` | Pipeline 出错 | `{"status": "error", "error": "..."}` |
| `cancelled` | Pipeline 取消 | `{"status": "cancelled"}` |
| `ping` | 心跳（15s） | `{}` |

### 7.4 集成适配器接口

每个外部平台适配器必须实现 `BaseAdapter` 抽象基类定义的方法：

| 方法 | 说明 | 必实现 |
|------|------|--------|
| `authenticate()` | 认证连接 | 是 |
| `push_test_cases(cases)` | 推送测试用例 | 是 |
| `pull_test_cases()` | 拉取测试用例 | 是 |
| `push_test_results(results)` | 推送测试结果 | 是 |
| `pull_test_results()` | 拉取测试结果 | 是 |
| `create_test_run(name)` | 创建测试运行 | 否 |
| `list_test_runs()` | 列出测试运行 | 否 |
| `push_defects(defects)` | 推送缺陷 | 否 |
| `pull_defects()` | 拉取缺陷 | 否 |
| `verify_signature(payload)` | 验证 Webhook 签名 | 否 |
| `handle_webhook(event)` | 处理 Webhook 事件 | 否 |

---

## 8. 验收标准

### 8.1 功能验收

#### 8.1.1 Pipeline 核心流程

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-001 | 全自动模式执行 | 提交需求文档后，7 步连续执行，无人工干预，最终输出完整产物 | P0 |
| AC-002 | 半自动模式执行 | 每个 AI 步骤完成后暂停，确认后继续，人工执行步骤正确处理 | P0 |
| AC-003 | 逐步骤模式执行 | 每步需手动触发，可精确控制执行节奏 | P1 |
| AC-004 | 断点续跑 | 任意步骤中断后，resume 命令从断点继续，不重复执行已完成步骤 | P0 |
| AC-005 | 知识库未启用时跳过 | 知识库 disabled 时，Step 2 自动跳过，不阻塞流程 | P1 |

#### 8.1.2 需求分析

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-006 | 结构化拆解 | 输出包含模块→功能点→可测项三级结构 | P0 |
| AC-007 | 待确认清单 | 识别模糊需求，按高/中/低优先级分类 | P0 |
| AC-008 | 质量自检 | 自检不通过时自动重跑，携带改进意见 | P1 |

#### 8.1.3 知识库

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-009 | 关键词检索 | 根据需求分析提取的关键词，检索到相关历史用例和业务规则 | P0 |
| AC-010 | 回灌功能 | 支持从 Excel 回灌优质用例到知识库 | P1 |
| AC-011 | 7 分类管理 | 支持 7 个分类目录的独立检索和管理 | P1 |

#### 8.1.4 测试点与用例

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-012 | 6 维度覆盖 | basic 模式覆盖 4 必需维度，all 模式覆盖全部 6 维度 | P0 |
| AC-013 | Excel 12 列格式 | 生成的 Excel 包含完整的 12 列结构，格式化正确 | P0 |
| AC-014 | XMind 脑图 | 生成的 XMind 为四级树状结构，可正常打开 | P1 |
| AC-015 | 优先级自动分配 | P0/P1/P2 分配合理，核心功能 P0 覆盖率 ≥ 30% | P0 |
| AC-016 | 用例编号连续 | 编号从 TC-001 开始连续递增 | P1 |

#### 8.1.5 用例评审

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-017 | 四维评分 | 输出完整性、清晰性、准确性、可执行性四个维度评分 | P0 |
| AC-018 | 整改清单 | 评审不通过时提供具体的整改建议 | P1 |
| AC-019 | 等级划分 | 分数正确映射到优秀/良好/中等/较差四个等级 | P1 |

#### 8.1.6 测试报告

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-020 | 8 章节结构 | 报告包含全部 8 个章节 | P0 |
| AC-021 | 通过率计算 | 通过率计算正确，发布建议合理 | P0 |
| AC-022 | 失败原因推断 | 失败用例包含原因推断和修复建议 | P1 |

#### 8.1.7 外部集成

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-023 | 适配器注册 | 新适配器通过装饰器注册后自动发现 | P1 |
| AC-024 | 字段映射 | 通过 YAML 配置驱动字段双向映射 | P1 |
| AC-025 | 同步推送 | 支持将用例和结果推送到外部平台 | P2 |

### 8.2 非功能验收

#### 8.2.1 性能

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-026 | 需求分析耗时 | ≤ 2 分钟 | P0 |
| AC-027 | 测试点梳理耗时 | ≤ 3 分钟 | P0 |
| AC-028 | 脚本步骤耗时 | 每步 ≤ 3 秒 | P1 |
| AC-029 | 并发支持 | 同时运行 2 个 Pipeline | P1 |

#### 8.2.2 可靠性

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-030 | LLM 故障转移 | 主 Provider 失败时自动切换到备选 | P1 |
| AC-031 | 断点恢复 | 进程崩溃后重启，断点状态完整保留 | P0 |
| AC-032 | 错误处理 | 异常不导致系统崩溃，有清晰的错误信息 | P0 |

#### 8.2.3 安全性

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-033 | JWT 认证 | 未登录用户无法访问受保护接口 | P0 |
| AC-034 | API Key 脱敏 | 配置查询时 API Key 仅显示前后 4 位 | P1 |
| AC-035 | 路径穿越防护 | 文件下载接口无法通过 `../` 访问系统文件 | P0 |
| AC-036 | 密码安全 | 用户密码使用 bcrypt 哈希存储 | P1 |

#### 8.2.4 兼容性

| 编号 | 验收项 | 验收标准 | 优先级 |
|------|--------|---------|--------|
| AC-037 | Python 3.11+ | 在 Python 3.11 和 3.12 上通过全部测试 | P0 |
| AC-038 | LLM Provider | 至少支持 DeepSeek 和 OpenAI 两个 Provider | P0 |
| AC-039 | Docker 部署 | `docker-compose up` 可正常启动 | P1 |

### 8.3 验收测试数据

| 场景 | 输入 | 期望输出 |
|------|------|---------|
| 全流程基础 | 用户管理系统需求文档 | 7 步全部完成，输出 Excel + 评审 + 报告 |
| 知识库增强 | 订单系统需求 + 已有订单相关历史用例 | 知识库命中 ≥ 3 条，用例质量提升 |
| 断点续跑 | 执行到 Step 3 后中断 | resume 后从 Step 3 继续 |
| 全 6 维 | 带 `-d all` 参数 | 测试点包含性能和安全维度 |
| 双格式 | 带 `-f excel,xmind` 参数 | 同时输出 Excel 和 XMind |

---

## 9. 附录

### 9.1 参考文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 文件功能分析 | `docs/file-analysis.md` | 全部文件的功能和依赖关系分析 |
| 集成扩展指南 | `docs/integration-extension-guide.md` | 集成适配器扩展开发指南 |
| Pipeline 布局设计 | `docs/PIPELINE_LAYOUT_V3.md` | Pipeline 进度页面垂直时间轴设计 |
| 快速开始 | `QUICKSTART.md` | 5 步快速上手指南 |
| 变更日志 | `CHANGELOG.md` | 版本变更历史 |

### 9.2 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0.0 | 2026-07-12 | 初始版本，确定 7 步架构 |
| v1.1.0 | 2026-07-13 | 7 个独立 Skill，Excel + XMind 双格式 |
| v1.2.0 | 2026-07-14 | Pipeline 全流程串联，断点续跑，MCP 知识库 |
| v1.3.0 | 2026-07-15 | 单元测试框架，代码重构，Bug 修复 |
| v2.0.0 | 2026-07-16 | 独立仓库，Web UI，数据库持久化，集成适配层 |

### 9.3 术语对照表

| 中文 | 英文 | 缩写 |
|------|------|------|
| 大语言模型 | Large Language Model | LLM |
| 检索增强生成 | Retrieval-Augmented Generation | RAG |
| 模型上下文协议 | Model Context Protocol | MCP |
| 应用程序接口 | Application Programming Interface | API |
| 命令行界面 | Command Line Interface | CLI |
| 服务器推送事件 | Server-Sent Events | SSE |
| 对象关系映射 | Object-Relational Mapping | ORM |
| 软件即服务 | Software as a Service | SaaS |
| 有向无环图 | Directed Acyclic Graph | DAG |
| 写入时复制 | Write-Ahead Logging | WAL |

---

*本文档为 AI 测试用例生成系统 v2.0.0 的正式需求规格说明书，所有需求项均与当前代码实现保持一致。*
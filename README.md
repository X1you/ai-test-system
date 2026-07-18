# AI 测试用例生成系统

从需求文档到测试报告的全流程自动化系统。基于 AI 串联 7 个核心环节，知识库 RAG 横切增强，人工校验节点保留，实现测试用例生产整体提效。

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    接入层 (Access Layer)                       │
│                                                              │
│   CLI (argparse)  │    WebUI (HTMX + Jinja2 + SSE)   │ REST  │
│                   │    + JWT 认证                      │ API  │
├──────────────────────────────────────────────────────────────┤
│                    服务层 (Service Layer)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PipelineService — TaskManager + EventBus + SSE        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LLM Gateway — 多 Provider 路由 + 故障转移 + 用量统计   │  │
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

## 核心功能

### 全流程 Pipeline

一键串联 7 个环节，从需求文档到测试报告端到端自动化：

| 步骤 | 环节 | 执行方式 | 典型耗时 | 输出产物 |
|------|------|---------|---------|---------|
| Step 1 | 需求分析 | AI 实时处理 | ~2min | 需求拆解 + 待确认清单 |
| Step 2 | 知识库检索 | 脚本自动化 | <1s | 知识增强上下文 |
| Step 3 | 测试点梳理 | AI 实时处理 | ~3min | 6 维测试点清单 |
| Step 4 | 生成测试用例 | 脚本自动化 | <3s | Excel + XMind |
| Step 5 | 用例评审 | AI 实时处理 | ~2min | 四维质检报告 |
| Step 6 | 执行测试 | 人工执行 | — | 已执行结果 |
| Step 7 | 生成报告 | 脚本自动化 | <3s | 质量报告 |
| 回灌 | 知识库回灌 | 脚本自动化 | <2s | 知识库沉淀 |

**关键特性：**

- **断点续跑**：记录执行进度，失败后从断点恢复，无需重头开始
- **人工检查点**：关键节点暂停等待确认，保留人工决策权
- **三种执行模式**：
  - `auto`（全自动）：AI 步骤连续执行，适合快速产出
  - `semi`（半自动，默认）：AI 步骤后暂停，等待人工确认
  - `step`（逐步骤）：每步需手动触发，适合精细控制
- **知识库 RAG 增强**：Step 2 检索知识库 → Step 3 注入上下文 → 回灌沉淀
- **LLM 故障转移**：主 Provider 失败时自动切换到备选 Provider（通过 LLM Gateway）

### 需求分析

- 需求文档（Markdown / 纯文本）结构化拆解，提取功能模块、功能点、可测项
- 待确认事项清单生成（高/中/低三级优先级）
- 影响范围自动标注
- AI 质量自检：自检不通过时自动携带改进意见重跑

### 测试点梳理

- 按模块 → 功能点 → 测试维度 → 具体测试点逐层展开
- 支持 6 个测试维度（可配置）：
  - **必需维度**：正向测试、负向测试、边界测试、异常测试
  - **可选维度**：性能测试、安全测试
- 每个测试点包含描述、测试数据、预期结果
- 测试优先级自动建议（P0/P1/P2）

### 测试用例生成

- **Excel 格式**：12 列标准结构（编号/模块/功能点/标题/维度/优先级/前置条件/步骤/测试数据/预期结果/执行结果/备注）
- **XMind 格式**：树状脑图，使用标准 xmind 库
- 用例编号自动连续（TC-001 ~ TC-NNN）
- 优先级自动分配（P0/P1/P2），核心功能 P0 覆盖率 ≥ 30%
- 按测试维度过滤（`-d` 参数）
- 步骤模板按模块类型自动匹配（内置 15 种动作关键词模板）

### 用例评审

四维质检分析：

| 维度 | 满分 | 评分标准 |
|------|------|---------|
| 完整性 | 30 | 缺失用例越少，得分越高 |
| 清晰性 | 30 | 质量问题越少，得分越高 |
| 准确性 | 20 | 重复冗余越少，得分越高 |
| 可执行性 | 20 | 用例越具体、越可执行，得分越高 |

等级划分：

| 分数范围 | 等级 | 说明 |
|---------|------|------|
| >= 90 | 优秀 | 可直接使用 |
| 75 ~ 89 | 良好 | 少量修改后使用 |
| 60 ~ 74 | 中等 | 需要较多修改 |
| < 60 | 较差 | 建议重新生成 |

- 支持多种文件格式（Excel、Markdown、CSV）
- 整改清单生成

### 测试报告生成

| 通过率 | 评级 | 说明 |
|--------|------|------|
| >= 95% | 优秀 | 可以发布 |
| 85% ~ 95% | 良好 | 修复少量问题后可发布 |
| 70% ~ 85% | 中等 | 需要修复较多问题 |
| < 70% | 较差 | 不建议发布 |

- 8 章节标准结构：总体概览 → 模块分布 → 优先级分析 → 维度分析 → 失败用例分析 → 阻塞用例分析 → 风险评估 → 测试结论与建议
- 失败用例分析含 11 类失败原因推断和修复建议
- 风险评估（高/中/低三级）与发布建议
- 需求覆盖率计算（通过 `generate_report.py` 的 `-r` 参数传入需求分析文件）

### 知识库管理

MCP 协议层直接访问 Obsidian Vault 文件系统，支持 7 分类知识库：

| 分类 | 目录 | 说明 |
|------|------|------|
| 历史优质用例 | 历史用例/ | 评审通过的优质用例，按项目/批次三层归档 |
| 业务规则 | 业务规则/ | 字段限制、校验规则、业务逻辑 |
| 业务规范文档 | 业务规范/ | 产品功能说明、状态流转规则、权限矩阵 |
| 数据字典 | 数据字典/ | 表字段释义、枚举值、关联关系 |
| 线上问题沉淀 | 线上坑点/ | 历史 Bug、常见边界坑点、易漏场景 |
| 团队模板规范 | 用例模板/ | 用例编写模板、命名规范、断言规则 |
| 团队规范 | 团队规范/ | 测试流程规范等 |

三层搜索策略：Obsidian REST API 搜索 → 标签匹配（YAML frontmatter，加权 2.0）→ 全文遍历 + 多关键词 OR 匹配。

**功能：** 关键词检索、导出增强上下文（Markdown 注入后续环节）、回灌优质产物、添加单条知识、知识库状态统计。

### 外部集成

通过适配器模式支持外部测试管理平台集成：

- **TestRail**：通过 REST API 推送/拉取测试用例和结果
- **TestLink**：通过 XML-RPC 推送/拉取（字段映射 YAML 已就绪）
- **可扩展**：实现 `BaseAdapter` 接口即可接入新平台
- 双向同步支持 4 种冲突解决策略（last_write_wins / source_wins / target_wins / manual）
- Webhook 接收器支持外部平台事件推送

## 快速开始

### 环境要求

- Python 3.11+
- 一个 LLM API Key（支持 OpenAI 兼容协议的模型）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-org/ai-test-system.git
cd ai-test-system

# 2. 安装核心 + WebUI + Excel/XMind
pip install -e ".[web,xmind,excel]"

# 或仅安装核心（CLI 模式）
pip install -e .

# 安装全量依赖（WebUI + Excel/XMind + 数据库 + 认证 + 生产加固）
pip install -e ".[all]"
```

### 可选依赖组

| 依赖组 | 安装命令 | 包含内容 |
|--------|---------|---------|
| `web` | `pip install -e ".[web]"` | FastAPI + Uvicorn + Jinja2 + SSE |
| `xmind` | `pip install -e ".[xmind]"` | XMind 脑图输出 |
| `excel` | `pip install -e ".[excel]"` | Excel 读写 |
| `db` | `pip install -e ".[db]"` | SQLAlchemy + Alembic 数据库迁移 |
| `auth` | `pip install -e ".[auth]"` | JWT 认证 + bcrypt 密码哈希 |
| `production` | `pip install -e ".[production]"` | 结构化日志 + 速率限制 |
| `dev` | `pip install -e ".[dev]"` | pytest + ruff + mypy 开发工具链 |
| `all` | `pip install -e ".[all]"` | web + xmind + excel + db + auth + production |
| `dev-all` | `pip install -e ".[dev-all]"` | all + dev |

### 配置说明

```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY=sk-xxx
```

支持所有 OpenAI 兼容协议的模型，在 `config.yaml` 或 `.env` 中配置：

| Provider | 默认 Base URL | 推荐模型 |
|----------|--------------|---------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

`config.yaml` 完整配置项：

```yaml
# LLM 配置
llm:
  provider: deepseek                    # 模型提供商
  api_key: ${LLM_API_KEY}              # API Key（支持环境变量引用）
  base_url: https://api.deepseek.com   # API 地址
  model: deepseek-v4-flash             # 模型名称
  temperature: 0.3                     # 生成温度（0-1），测试用例建议低温
  max_tokens: 8192                     # 最大输出 Token 数
  timeout: 120                         # 单次请求超时（秒）
  retry: 2                             # 失败重试次数

# 知识库配置
knowledge_base:
  enabled: true                        # 是否启用知识库
  vault_path: ~/Documents/test-interview-kb  # Obsidian Vault 路径

# Pipeline 配置
pipeline:
  default_mode: semi                   # 默认执行模式：auto/semi/step
  default_dimensions: basic            # 默认维度：basic/all
  default_formats: excel               # 默认输出格式：excel/xmind
  self_check: true                     # AI 步骤输出质量自检
  max_concurrent: 2                    # 最大并发任务数

# 输出配置
output:
  dir: ./output                        # 输出目录
```

生产环境部署可使用 `config.production.yaml`，额外包含 LLM Gateway 故障转移链、JWT 安全配置、速率限制、CORS 白名单、结构化日志等生产级配置。

### 使用示例

#### CLI 命令行

```bash
# 查看当前配置
python cli.py config
# 或使用注册的命令行入口
ai-test config

# 执行全流程（半自动模式，AI 步骤后有检查点）
python cli.py run examples/demo_requirements.md

# 全自动模式（AI 步骤连续执行）
python cli.py run examples/demo_requirements.md --mode auto

# 全 6 维测试（含性能/安全）
python cli.py run examples/demo_requirements.md -d all

# 同时生成 Excel + XMind
python cli.py run examples/demo_requirements.md -f excel,xmind

# 指定配置文件
python cli.py run examples/demo_requirements.md --config config.production.yaml

# 查看 Pipeline 状态
python cli.py status -o output/

# 从断点继续
python cli.py resume -o output/
```

#### Web UI（浏览器界面）

```bash
# 启动 Web 服务
uvicorn web.app:app --port 8080
# 或
python -m web.app
```

打开浏览器访问 `http://localhost:8080`，即可在可视化界面上：
- 上传需求文档（Markdown / 纯文本格式）
- 选择执行模式、维度、输出格式
- 实时查看 Pipeline 7 步进度（SSE 实时推送）
- 下载生成的测试用例、评审报告等产物
- 查看和搜索知识库
- 管理历史 Pipeline 任务

#### Docker 部署

```bash
# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 输出产物

默认输出到 `./output/` 目录：

```
output/
├── requirements_analysis.md         # 需求拆解
├── clarification_needed.md          # 待确认清单
├── knowledge-context.md             # 知识库增强上下文
├── testpoints.md                    # 测试点清单
├── testcases.xlsx                   # Excel 测试用例
├── testcases.xmind                  # XMind 测试用例脑图
├── test_case_review_report.md       # 用例评审报告
├── test_report.md                   # 测试报告
└── _pipeline_state.json             # 断点状态（断点续跑用）
```

### 知识库初始化

知识库为可选功能，不启用不影响系统运行。如需启用：

```bash
# 1. 创建 Obsidian Vault
mkdir -p ~/Documents/test-interview-kb

# 2. 创建 7 个分类目录
mkdir -p ~/Documents/test-interview-kb/{"历史用例","业务规则","业务规范","数据字典","线上坑点","用例模板","团队规范"}

# 3. 在 config.yaml 中启用知识库
# knowledge_base.enabled: true
# knowledge_base.vault_path: ~/Documents/test-interview-kb
```

> 知识库内容初始为空，可通过 Pipeline 回灌功能逐步积累，也可手动添加历史用例和业务规则文档。

## 项目结构

```
ai-test-system/
├── cli.py                             # CLI 入口（同时注册为 ai-test 命令）
├── pyproject.toml                     # 项目元数据与依赖声明
├── config.yaml                        # 主配置文件
├── config.production.yaml             # 生产环境配置（含故障转移、JWT、限流等）
├── .env.example                       # 环境变量模板
├── alembic.ini                        # 数据库迁移配置
├── Dockerfile                         # 多阶段构建（builder + runtime）
├── docker-compose.yml                 # Docker Compose 一键部署
│
├── core/                              # 核心引擎
│   ├── pipeline.py                    # Pipeline 编排引擎
│   ├── config_loader.py               # 配置加载器（YAML + 环境变量）
│   ├── llm_client.py                  # LLM 统一调用抽象层
│   ├── llm_gateway.py                 # LLM 网关（多 Provider 路由 + 故障转移）
│   ├── prompt_loader.py               # 提示词加载与组装
│   ├── utils.py                       # 通用工具（文件锁等）
│   ├── prompts/                       # AI 提示词模板
│   │   ├── requirement_analysis.md
│   │   ├── test_points.md
│   │   └── case_review.md
│   ├── steps/                         # 7 个步骤实现
│   │   ├── base.py                    # 步骤基类
│   │   ├── step1_analysis.py          # 需求分析
│   │   ├── step2_kb_search.py         # 知识库检索
│   │   ├── step3_testpoints.py        # 测试点梳理
│   │   ├── step4_generate.py          # 生成测试用例
│   │   ├── step5_review.py            # 用例评审
│   │   ├── step6_human_test.py        # 人工执行测试
│   │   └── step7_report.py            # 生成测试报告
│   └── kb/                            # 知识库管理
│       ├── kb_manager.py              # 本地知识库管理
│       ├── kb_manager_mcp.py          # MCP 知识库管理
│       └── mcp_client.py              # MCP 协议客户端
│
├── web/                               # Web UI（FastAPI + HTMX）
│   ├── app.py                         # FastAPI 应用入口
│   ├── api/                           # API 路由
│   │   ├── pipeline.py                # Pipeline 接口
│   │   ├── knowledge.py               # 知识库接口
│   │   ├── config.py                  # 配置接口
│   │   ├── sse.py                     # SSE 实时推送
│   │   ├── webhooks.py                # Webhook 接收器
│   │   └── auth.py                    # 认证接口
│   ├── middleware/                    # 中间件
│   │   ├── auth.py                    # JWT 认证
│   │   ├── logging.py                 # 请求日志
│   │   └── rate_limit.py             # 速率限制
│   ├── services/                      # 业务服务
│   │   ├── pipeline_task.py           # Pipeline 异步任务包装器
│   │   ├── task_manager.py            # 任务管理器
│   │   ├── event_bus.py               # 进程内事件总线
│   │   └── user_service.py            # 用户服务
│   ├── templates/                     # Jinja2 模板
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── pipeline.html
│   │   ├── pipeline_progress.html
│   │   ├── pipelines.html
│   │   ├── results.html
│   │   ├── knowledge.html
│   │   └── login.html
│   └── static/                        # 静态资源
│       ├── app.js
│       └── custom.css
│
├── db/                                # 数据持久化层
│   ├── models.py                      # SQLAlchemy 数据模型
│   ├── repository.py                  # 数据仓库
│   ├── session.py                     # 数据库会话管理
│   └── migrations/                    # Alembic 迁移
│       └── versions/
│
├── integrations/                      # 集成适配层
│   ├── base.py                        # 适配器抽象基类
│   ├── registry.py                    # 适配器注册表
│   ├── auth.py                        # 认证策略链
│   ├── models.py                      # 内部标准数据模型（Canonical Model）
│   ├── field_mapper.py                # 字段映射引擎
│   ├── bridge.py                      # 核心引擎桥接器
│   ├── sync_engine.py                 # 同步引擎
│   ├── adapters/                      # 平台适配器
│   │   └── testrail.py                # TestRail 适配器
│   └── mappings/                      # 字段映射配置
│       ├── testrail_mapping.yaml
│       └── testlink_mapping.yaml
│
├── scripts/                           # 工具脚本
│   ├── common.py                      # 共享解析模块
│   ├── generate_excel.py              # Excel 生成
│   ├── generate_xmind.py              # XMind 生成
│   └── generate_report.py             # 报告生成
│
├── tests/                             # 单元测试（24 个测试文件）
│   ├── test_api_endpoints.py
│   ├── test_auth.py
│   ├── test_boundary.py
│   ├── test_bugfix_regression.py
│   ├── test_cli.py
│   ├── test_common.py
│   ├── test_config_loader.py
│   ├── test_db_persistence.py
│   ├── test_excel_reader.py
│   ├── test_file_lock.py
│   ├── test_integration_bridge.py
│   ├── test_integration_runtime.py
│   ├── test_integrations_service.py
│   ├── test_llm_gateway.py
│   ├── test_perf_security_supplement.py
│   ├── test_performance.py
│   ├── test_phase3_async.py
│   ├── test_pipeline_api.py
│   ├── test_pipeline_progress_e2e.py
│   ├── test_pipeline_progress_template.py
│   ├── test_security.py
│   ├── test_task_manager.py
│   ├── test_xmind.py
│   └── mock_testrail.py
│
├── docs/                              # 项目文档
│   ├── requirements.md                # 需求规格说明书
│   ├── file-analysis.md               # 文件功能分析
│   ├── integration-extension-guide.md # 集成扩展指南
│   ├── phase2-completion-report.md    # Phase 2 完成报告
│   ├── qa-coverage-assessment-r2.md   # QA 覆盖率评估
│   ├── qa-test-report.md              # QA 测试报告
│   ├── optimization-backlog.md        # 优化积压列表
│   └── PIPELINE_LAYOUT_V3.md          # Pipeline 布局设计
│
├── examples/                          # 示例需求文档
│   ├── demo_requirements.md           # 用户管理系统
│   └── order_requirements.md          # 订单系统
│
├── uploads/                           # 上传文件暂存（运行时生成）
├── output/                            # 输出产物（运行时生成）
├── README.md
├── CHANGELOG.md
├── QUICKSTART.md
└── LICENSE
```

## Web API 文档

### Pipeline 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/pipeline/start` | 上传需求文档并启动 Pipeline |
| GET | `/api/pipeline/{id}/progress` | 获取任务进度（JSON / HTMX 片段） |
| GET | `/api/pipeline/{id}/status` | 获取详细状态 |
| GET | `/api/pipeline/{id}/stream` | SSE 实时进度推送 |
| POST | `/api/pipeline/{id}/resume` | 从断点继续（可上传已执行 Excel） |
| POST | `/api/pipeline/{id}/cancel` | 取消 Pipeline |
| GET | `/api/pipeline/list` | 任务列表 |
| GET | `/api/pipeline/{id}/artifacts` | 获取产物列表 |
| GET | `/api/pipeline/{id}/artifacts/{name}` | 下载产物文件 |
| GET | `/api/pipeline/{id}/preview/{name}` | 预览产物（Markdown 渲染 / Excel 表格） |

### 知识库接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb/status` | 知识库统计信息 |
| GET | `/api/kb/search?q=keyword` | 搜索知识库 |

### 配置与认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 查看当前配置（API Key 脱敏） |
| POST | `/api/auth/login` | 用户名密码登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户信息 |
| POST | `/api/webhooks/{platform}` | 接收外部平台事件推送 |

### 系统接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（数据库、LLM 配置、知识库连通性） |

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 语言 | Python 3.11+ | 核心开发语言 |
| LLM SDK | `openai` Python SDK | 兼容 DeepSeek / GLM / OpenAI / Moonshot / 通义千问 |
| LLM 网关 | `LLMGateway` | 多 Provider 路由 + 自动故障转移 |
| Web 后端 | FastAPI | 异步高性能，自带 OpenAPI 文档 |
| Web 前端 | HTMX + Jinja2 模板 | 纯 Python 栈，无需 Node.js |
| 实时推送 | SSE (Server-Sent Events) | 15s 心跳保活，Pipeline 进度实时更新 |
| 知识库 | Obsidian Vault + MCP 协议 | 本地文件系统，路径可配置 |
| 持久化 | SQLAlchemy 2.0 + SQLite (WAL) + Alembic | ORM + 迁移管理 |
| 认证 | python-jose (JWT) + bcrypt | Token 认证 + 安全密码哈希 |
| 集成适配 | 适配器模式 + YAML 字段映射 | 可扩展接入 TestRail、TestLink 等平台 |
| 测试框架 | pytest + pytest-asyncio + pytest-cov | 单元测试 + 覆盖率 |
| 代码质量 | ruff + mypy | 代码检查 + 类型检查 |
| 容器化 | Docker + Docker Compose | 多阶段构建，一键部署 |
| 包管理 | pyproject.toml + pip | Python 标准包管理 |

**核心依赖：** `openpyxl`（Excel）、`xmind`（脑图）、`openai`（LLM）、`PyYAML`（配置）、`fastapi` + `uvicorn` + `jinja2`（WebUI）、`sqlalchemy` + `alembic`（持久化）、`python-jose` + `bcrypt`（认证）

## 常见问题

**Q: 支持哪些 LLM 模型？**

所有兼容 OpenAI API 协议的模型均可，包括 DeepSeek、智谱 GLM、OpenAI、Moonshot、通义千问等。在 `config.yaml` 中配置 `provider`、`base_url`、`model` 即可。生产环境还支持通过 LLM Gateway 配置备选 Provider 实现故障转移。

**Q: 知识库是必需的吗？**

不是。知识库为可选增强功能，不启用不影响系统运行。在 `config.yaml` 中设置 `knowledge_base.enabled: false` 即可关闭。

**Q: 输出文件保存在哪里？**

默认输出到项目根目录下的 `output/` 文件夹，可通过 `-o` 参数或 `config.yaml` 中的 `output.dir` 配置修改。

**Q: 执行中断了怎么办？**

系统支持断点续跑。执行 `python cli.py resume -o output/` 即可从断点继续。断点状态保存在 `output/_pipeline_state.json` 中。

**Q: 如何选择执行模式？**

- `auto`（全自动）：适合快速产出，AI 步骤连续执行
- `semi`（半自动，默认）：AI 步骤后暂停，等待确认后再继续
- `step`（逐步骤）：每步需手动触发，适合精细控制

**Q: 如何部署到生产环境？**

使用 `config.production.yaml` 作为配置模板，或通过 Docker Compose 一键部署：

```bash
cp config.production.yaml config.yaml
# 编辑 config.yaml 填入 JWT_SECRET、LLM_API_KEY 等
docker-compose up -d
```

## 贡献指南

### 开发环境

```bash
# 进入项目目录
cd ai-test-system

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 运行测试 + 覆盖率
pytest tests/ --cov=. --cov-report=term-missing
```

### 代码规范

1. **Python 版本**：3.11+，使用类型注解
2. **代码风格**：遵循 PEP 8，使用 `ruff` 格式化与检查
3. **提交信息**：遵循 Conventional Commits 规范
   - `feat:` 新功能
   - `fix:` 修复
   - `refactor:` 重构
   - `docs:` 文档更新
   - `test:` 测试
   - `chore:` 构建/工具

### 开发流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/your-feature`
3. 提交变更：`git commit -m "feat: add some feature"`
4. 推送到分支：`git push origin feat/your-feature`
5. 提交 Pull Request

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 需求规格说明书 | [docs/requirements.md](docs/requirements.md) | 完整功能需求、非功能需求、验收标准 |
| 文件功能分析 | [docs/file-analysis.md](docs/file-analysis.md) | 全部文件的功能和依赖关系分析 |
| 集成扩展指南 | [docs/integration-extension-guide.md](docs/integration-extension-guide.md) | 外部平台适配器开发指南 |
| QA 覆盖率评估 | [docs/qa-coverage-assessment-r2.md](docs/qa-coverage-assessment-r2.md) | 测试覆盖率评估报告 |
| QA 测试报告 | [docs/qa-test-report.md](docs/qa-test-report.md) | 质量保证测试报告 |
| 优化积压列表 | [docs/optimization-backlog.md](docs/optimization-backlog.md) | 技术优化和债务清理计划 |
| 快速开始指南 | [QUICKSTART.md](QUICKSTART.md) | 5 步快速上手指南 |
| 变更日志 | [CHANGELOG.md](CHANGELOG.md) | 版本变更历史 |

## 许可证

本项目基于 MIT 许可证开源，详见 [LICENSE](LICENSE) 文件。

## 联系方式

- **问题反馈：** [GitHub Issues](https://github.com/your-org/ai-test-system/issues)
- **项目文档：** [docs/](docs/) 目录下包含需求规格说明书、集成扩展指南、QA 报告等文档

---

*最后更新：2026-07-16*
*当前版本：v2.0.0*
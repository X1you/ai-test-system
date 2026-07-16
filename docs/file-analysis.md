# AI 测试用例生成系统 — 文件功能分析文档

> 版本：v2.0.0 | 生成日期：2026-07-16 | 更新日期：2026-07-16

本文档对项目中所有文件的功能、关键实现逻辑、依赖关系和架构角色进行结构化分析，便于项目维护人员和新成员快速理解项目结构。

---

## 项目架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLI (cli.py)                                  │
│                     Web UI (web/)                                 │
│                     ├── Middleware (web/middleware/)               │
│                     ├── Static (web/static/)                      │
│                     └── Templates (web/templates/)                │
├──────────────────────────────────────────────────────────────────┤
│              Pipeline 编排引擎 (core/pipeline.py)                  │
├──────────┬──────────┬──────────┬─────────────────────────────────┤
│ 7 Steps  │ LLM 层   │ KB 层    │ Integrations 层                  │
│ (steps/) │ (llm_*)  │ (kb/)    │ (integrations/ + adapters/)      │
├──────────┴──────────┴──────────┴─────────────────────────────────┤
│              DB 持久化层 (db/ + migrations/)                       │
│              Scripts 脚本层 (scripts/)                             │
│              Examples (examples/)                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 一、顶层文件

### 1.1 cli.py
- **路径**：`/cli.py`
- **功能**：CLI 命令行入口，提供 `run`、`resume`、`status`、`config` 四个子命令
- **关键逻辑**：
  - 通过 `argparse` 解析命令行参数，支持 `--mode`（auto/semi/step）、`-d`（测试维度）、`-f`（输出格式）等选项
  - `cmd_run()`：加载并校验配置 → 创建 `Pipeline` 实例 → 调用 `pipeline.run()` 执行全流程
  - `cmd_resume()`：从断点继续执行
  - `cmd_status()`：查看 Pipeline 执行状态
  - `cmd_config()`：显示当前配置（API Key 脱敏，显示前 8 位和后 4 位）
  - 延迟导入 `LLMClient`/`LLMError`，避免 `config` 命令受 LLM 库初始化影响
- **依赖关系**：
  - 依赖 `core.config_loader`（加载配置、校验）
  - 依赖 `core.pipeline`（Pipeline 引擎）
  - 依赖 `core.llm_client`（延迟导入 LLMError）
- **架构角色**：面向终端用户的命令行操作入口

### 1.2 pyproject.toml
- **路径**：`/pyproject.toml`
- **功能**：Python 项目元数据与依赖声明文件
- **关键逻辑**：
  - 定义项目名 `ai-test-system`，版本 `2.0.0`，Python 版本要求 `>=3.11`
  - 核心依赖：`openai>=1.0`、`pyyaml>=6.0`
  - 可选依赖组：`web`（FastAPI）、`xmind`、`excel`、`db`（SQLAlchemy）、`auth`（JWT）、`production`（structlog+slowapi）、`dev`（pytest+ruff+mypy）
  - 入口点：`ai-test = cli:main`
  - 配置 ruff、mypy、pytest 工具链
  - setuptools 包发现配置：`core*`、`web*`、`scripts*`、`integrations*`、`db*`
- **依赖关系**：被 pip 安装工具读取
- **架构角色**：项目元数据中心

### 1.3 config.yaml
- **路径**：`/config.yaml`
- **功能**：开发环境默认配置文件
- **关键逻辑**：
  - LLM 配置（provider: deepseek, model: deepseek-v4-flash, temperature: 0.3, base_url: https://api.deepseek.com）
  - 知识库配置（enabled: true, vault_path: ~/Documents/test-interview-kb）
  - Pipeline 配置（default_mode: semi, self_check: true, max_concurrent: 2）
  - 输出配置（dir: ./output）
- **依赖关系**：被 `core/config_loader.py` 读取
- **架构角色**：用户可编辑的运行时配置

### 1.4 config.production.yaml
- **路径**：`/config.production.yaml`
- **功能**：生产环境配置模板，相比开发配置增加了：
  - LLM Gateway 备选 Provider（fallback 链，支持故障转移）
  - 服务配置（host/port/workers）
  - 安全配置（JWT secret、rate limit、CORS）
  - 日志配置（level/format）
  - 更多环境变量引用（`${VAR_NAME:-default}` 语法）
- **依赖关系**：被 `core/config_loader.py` 读取
- **架构角色**：生产部署配置模板

### 1.5 .env.example
- **路径**：`/.env.example`
- **功能**：环境变量模板，包含 LLM_API_KEY、Obsidian API Key、TestRail API Key、JWT Secret 等配置项说明
- **依赖关系**：用户复制为 `.env` 后被 `core/config_loader.py` 的 `_load_dotenv()` 加载
- **架构角色**：敏感配置的模板文件

### 1.6 .gitignore
- **路径**：`/.gitignore`
- **功能**：Git 忽略规则，排除 `__pycache__/`、`.venv/`、`output/`、`data/`、`.env`、`_meta.json`、IDE 配置等
- **架构角色**：版本控制配置

### 1.7 Dockerfile
- **路径**：`/Dockerfile`
- **功能**：多阶段 Docker 构建文件
- **关键逻辑**：
  - Builder 阶段：安装 gcc → 复制源码 → 安装 `[web,xmind,excel,db]` 依赖
  - Runtime 阶段：精简镜像，复制依赖和源码，配置环境变量和健康检查
  - 启动命令：`uvicorn web.app:app --host 0.0.0.0 --port 8080`
- **架构角色**：容器化部署

### 1.8 docker-compose.yml
- **路径**：`/docker-compose.yml`
- **功能**：Docker Compose 编排文件，映射端口 8080，挂载 data/output/uploads 目录，设置健康检查
- **架构角色**：一键容器化部署

### 1.9 README.md
- **路径**：`/README.md`
- **功能**：项目主文档，包含核心功能说明、快速开始、配置说明、项目结构、API 文档、技术栈
- **架构角色**：项目入口文档

### 1.10 QUICKSTART.md
- **路径**：`/QUICKSTART.md`
- **功能**：5 步快速开始指南（安装 → 配置 → 执行 → 查看进度 → 输出产物）
- **架构角色**：新用户快速上手文档

### 1.11 CHANGELOG.md
- **路径**：`/CHANGELOG.md`
- **功能**：版本变更历史，遵循 Keep a Changelog 格式，记录 v1.0.0 ~ v1.3.0 的新增、修复和优化
- **架构角色**：版本历史记录

### 1.12 LICENSE
- **路径**：`/LICENSE`
- **功能**：项目开源许可证文件
- **架构角色**：法律声明

### 1.13 alembic.ini
- **路径**：`/alembic.ini`
- **功能**：Alembic 数据库迁移工具配置文件，指定迁移脚本目录（`db/migrations/versions/`）和数据库连接 URL
- **依赖关系**：被 `db/migrations/env.py` 读取
- **架构角色**：数据库版本迁移配置

---

## 二、core/ — 核心引擎层

### 2.1 core/pipeline.py
- **路径**：`/core/pipeline.py`
- **功能**：Pipeline 编排引擎（v2.0），负责串联 7 个步骤的完整执行流程
- **关键逻辑**：
  - `Pipeline` 类包含完整的状态管理（`load_state`/`save_state`/`mark_done`/`is_done`）
  - `run(requirements_file, mode, dimensions, formats)` 方法按顺序执行 7 个步骤，每个步骤执行前检查是否已完成（支持断点续跑）
  - 三种执行模式：
    - `auto`：AI 步骤连续执行，无人机交互
    - `semi`：AI 步骤后暂停，等待确认
    - `step`：每步需手动触发
  - `resume()`：从 `_pipeline_state.json` 恢复状态后继续执行
  - `status()`：显示 7 步的完成状态和输出文件
  - 支持 WebUI 回调钩子（`on_log`、`on_step_done`）
  - `_has_results()`：检查 Excel 执行结果列是否已填写（匹配"执行结果"列名或包含"执行"+"结果"的表头）
- **依赖关系**：
  - 依赖 `core.config_loader`、`core.llm_client`
  - 依赖 `core.steps.base`（StepResult）
  - 依赖 `core.steps.step1_analysis` ~ `step7_report`（7 个步骤类）
- **架构角色**：系统的核心调度中枢，连接所有步骤模块

### 2.2 core/config_loader.py
- **路径**：`/core/config_loader.py`
- **功能**：配置加载器，统一读取 config.yaml + .env 环境变量
- **关键逻辑**：
  - `PROJECT_ROOT`：指向项目根目录（core/ 的上一级）
  - `DEFAULT_CONFIG`：包含 llm、knowledge_base、pipeline、output、integrations 五大配置块
  - `_load_dotenv()`：加载 `.env` 文件到环境变量（不覆盖已有变量）
  - `_expand_vars()`：递归替换 `${VAR_NAME}` 为环境变量值
  - `_deep_merge()`：深度合并两个字典（用户配置覆盖默认配置）
  - `_expand_path()`：展开 `~` 为家目录
  - `load_config()`：按优先级加载（指定路径 > config.yaml > DEFAULT_CONFIG），执行变量插值和路径展开
  - `validate_config()`：校验 LLM API Key、base_url、model 是否配置，返回错误列表
- **依赖关系**：被几乎所有模块依赖（通过 `load_config` 获取配置）
- **架构角色**：全局配置中心

### 2.3 core/llm_client.py
- **路径**：`/core/llm_client.py`
- **功能**：LLM 统一调用抽象层，基于 OpenAI Python SDK 兼容所有 OpenAI 协议模型
- **关键逻辑**：
  - `LLMClient` 类封装 `OpenAI` 客户端，支持 DeepSeek / GLM / OpenAI / Moonshot / 通义千问
  - `chat()`：单轮对话，支持 system prompt
  - `chat_with_retry()`：带重试的对话，支持指数退避
  - `evaluate()`：质量自检（LLM 评估自身输出），返回 `{score, passed, issues, suggestions}`
  - `_parse_json_response()`：容错解析 LLM 的 JSON 输出（去除 markdown 代码块标记）
  - `stats` 属性：调用次数和 Token 用量统计
  - `LLMError`：自定义异常类
- **依赖关系**：依赖 `openai` 库；被 Pipeline、Steps、LLMGateway 依赖
- **架构角色**：LLM 调用的统一抽象层

### 2.4 core/llm_gateway.py
- **路径**：`/core/llm_gateway.py`
- **功能**：LLM 网关（Track A 轻量版），多 Provider 路由 + 故障转移
- **关键逻辑**：
  - `LLMGateway` 类管理一个主 Provider 和多个备选 Provider
  - `chat()`：按顺序尝试 Provider 链（主 → 备选1 → 备选2 → ...），全部失败时抛出异常
  - `_call_provider()`：通过 `asyncio.to_thread` 包装同步 `LLMClient.chat()` 调用
  - 统计信息：total_calls、total_tokens、provider_calls、provider_errors、failovers 计数
  - 备选 Provider 配置错误时跳过（不阻塞启动）
- **依赖关系**：依赖 `core.llm_client`（LLMClient、LLMError）
- **架构角色**：LLM 高可用层，Track B 将扩展缓存、成本核算、Rate Limiting

### 2.5 core/prompt_loader.py
- **路径**：`/core/prompt_loader.py`
- **功能**：提示词加载与组装工具
- **关键逻辑**：
  - `load_prompt(name)`：从 `core/prompts/` 加载 Markdown 模板
  - `render(template, **kwargs)`：替换 `{variable}` 占位符
  - `build_kb_context(kb_text)`：构建知识库上下文注入段落
- **依赖关系**：被 AI 步骤（Step1/3/5）依赖
- **架构角色**：提示词模板管理层

### 2.6 core/utils.py
- **路径**：`/core/utils.py`
- **功能**：通用工具模块
- **关键逻辑**：
  - `file_lock()`：上下文管理器，基于 `fcntl.flock` 的文件锁，防止并发写入冲突，支持非阻塞获取 + 超时重试
- **依赖关系**：无内部依赖
- **架构角色**：跨模块共享的基础工具

---

## 三、core/prompts/ — 提示词模板

### 3.1 core/prompts/requirement_analysis.md
- **路径**：`/core/prompts/requirement_analysis.md`
- **功能**：需求分析提示词模板，指导 LLM 将需求文档拆解为结构化测试分析
- **关键逻辑**：定义输出格式（模块 → 功能点 → 可测项）+ 待确认事项（高/中/低优先级），包含模糊词识别规则
- **依赖关系**：被 `Step1Analysis` 通过 `prompt_loader.load_prompt()` 加载
- **架构角色**：Step 1 的 AI 提示词

### 3.2 core/prompts/test_points.md
- **路径**：`/core/prompts/test_points.md`
- **功能**：测试点梳理提示词模板，指导 LLM 生成结构化测试点清单
- **关键逻辑**：定义 6 维测试（正向/负向/边界/异常/性能/安全），每个测试点包含描述、测试数据、预期结果
- **依赖关系**：被 `Step3Testpoints` 通过 `prompt_loader.load_prompt()` 加载
- **架构角色**：Step 3 的 AI 提示词

### 3.3 core/prompts/case_review.md
- **路径**：`/core/prompts/case_review.md`
- **功能**：用例评审提示词模板
- **关键逻辑**：四维质检（完整性 30 分/清晰性 30 分/准确性 20 分/可执行性 20 分），缺失用例检测、质量问题识别、重复冗余检查、整改清单
- **依赖关系**：被 `Step5Review` 通过 `prompt_loader.load_prompt()` 加载
- **架构角色**：Step 5 的 AI 提示词

---

## 四、core/steps/ — 7 个 Pipeline 步骤

### 4.1 core/steps/base.py
- **路径**：`/core/steps/base.py`
- **功能**：步骤基类，定义所有 Pipeline 步骤的统一接口
- **关键逻辑**：
  - `StepResult` 数据类：`ok`（是否成功）、`data`（结果数据）、`error`（错误信息）、`human`（是否需要人工介入）
  - `BaseStep` 抽象类：`step_id`、`step_name`、`output_file` 子类必须定义
  - `__init__(output_dir, config, llm=None)`：构造函数，output_dir 自动创建目录
  - `_out(filename)`：获取输出目录下的完整路径
  - `_read_output(filename)`/`_write_output(filename, content)`：读写输出文件
  - `log(msg, level)`：带图标的日志输出（INFO/STEP/OK/WARN/ERR/HUMAN/KB）
  - `self_check(content, criteria)`：委托 LLM 进行质量自检（受 `pipeline.self_check` 配置控制，未启用或 LLM 未初始化时跳过）
  - `run(**kwargs)` 抽象方法
- **依赖关系**：依赖 `core.llm_client`（LLMClient）；被所有 7 个步骤子类继承
- **架构角色**：步骤模式的抽象基类

### 4.2 core/steps/step1_analysis.py
- **路径**：`/core/steps/step1_analysis.py`
- **功能**：Step 1 — 需求分析（AI 步骤）
- **关键逻辑**：
  - 支持 `requirements_path`（文件路径）和 `requirements_text`（直接文本）两种输入
  - 通过 `prompt_loader` 加载模板并渲染（注入需求文档 + 知识库上下文）
  - 调用 LLM 分析需求，解析输出（拆分需求拆解 + 待确认清单）
  - `_split_response()`：通过多种分隔符策略拆分 LLM 输出（`====`、`===CLARIFICATION===`、双一级标题）
  - 质量自检：不通过时带着改进意见重跑一次
  - 统计模块数、功能点数、待确认事项数
  - 输出：`requirements_analysis.md` + `clarification_needed.md`
- **依赖关系**：继承 `BaseStep`；依赖 `core.llm_client`、`core.prompt_loader`
- **架构角色**：Pipeline 第一步，AI 驱动的需求结构化分析

### 4.3 core/steps/step2_kb_search.py
- **路径**：`/core/steps/step2_kb_search.py`
- **功能**：Step 2 — 知识库检索（脚本步骤）
- **关键逻辑**：
  - 检查知识库是否启用，未启用直接跳过
  - `_extract_keywords()`：从需求分析中提取模块名和功能点作为关键词
  - 通过 subprocess 调用 `kb_manager_mcp.py export` 命令执行检索
  - 支持超时处理（60s）
  - 统计命中数
  - 输出：`knowledge-context.md`
- **依赖关系**：继承 `BaseStep`；依赖 `core/kb/kb_manager_mcp.py` 脚本
- **架构角色**：RAG 检索步骤，连接知识库与 Pipeline

### 4.4 core/steps/step3_testpoints.py
- **路径**：`/core/steps/step3_testpoints.py`
- **功能**：Step 3 — 测试点梳理（AI 步骤）
- **关键逻辑**：
  - `_build_dimensions_text()`：将维度配置（basic/all/自定义）转为提示词说明文本
  - 通过 `prompt_loader` 加载模板并渲染（注入需求分析 + 知识库上下文 + 维度配置）
  - 调用 LLM 生成测试点清单
  - 质量自检：检查维度覆盖、预期结果明确性、测试数据具体性，不通过则重跑
  - 统计测试点数量
  - 输出：`testpoints.md`
- **依赖关系**：继承 `BaseStep`；依赖 `core.llm_client`、`core.prompt_loader`
- **架构角色**：Pipeline 第三步，AI 驱动的测试点结构化生成

### 4.5 core/steps/step4_generate.py
- **路径**：`/core/steps/step4_generate.py`
- **功能**：Step 4 — 生成测试用例（脚本步骤）
- **关键逻辑**：
  - 检查 `testpoints.md` 是否存在
  - 通过 subprocess 调用 `scripts/generate_excel.py` 生成 Excel
  - 可选通过 `scripts/generate_xmind.py` 生成 XMind
  - 如果 Excel 已存在且含执行结果，跳过生成（保护已填写数据）
  - `_count_cases()`：统计 Excel 行数
  - `_has_results()`：检查执行结果列是否已填写
  - 输出：`testcases.xlsx` + 可选 `testcases.xmind`
- **依赖关系**：继承 `BaseStep`；依赖 `scripts/generate_excel.py`、`scripts/generate_xmind.py`
- **架构角色**：测试用例生成步骤

### 4.6 core/steps/step5_review.py
- **路径**：`/core/steps/step5_review.py`
- **功能**：Step 5 — 用例评审（AI 步骤）
- **关键逻辑**：
  - `_read_testcases_as_text()`：读取 Excel 并转换为 Markdown 表格文本（限制 200 行）
  - 通过 `prompt_loader` 加载模板并渲染（注入测试用例 + 知识库上下文）
  - 调用 LLM 进行四维质检
  - `_extract_score()`：从评审报告中提取总分
  - `_score_to_grade()`：分数转等级（优秀/良好/中等/较差）
  - 输出：`test_case_review_report.md`
- **依赖关系**：继承 `BaseStep`；依赖 `core.llm_client`、`core.prompt_loader`
- **架构角色**：AI 驱动的用例质量评审

### 4.7 core/steps/step6_human_test.py
- **路径**：`/core/steps/step6_human_test.py`
- **功能**：Step 6 — 人工执行测试（人工步骤）
- **关键逻辑**：
  - 不自动执行，只检测 Excel 执行结果列是否已填写
  - `_check_has_results()`：扫描 Excel 的"执行结果"列（精确匹配"执行结果"或模糊匹配同时包含"执行"和"结果"的表头），检查是否有非空值
  - 未检测到结果时返回 `ok=False, human=True`，Pipeline 暂停等待人工执行
  - 提示用户在「执行结果」列填写：通过/失败/阻塞/跳过
- **依赖关系**：继承 `BaseStep`
- **架构角色**：人机交互检查点，保留人工决策权

### 4.8 core/steps/step7_report.py
- **路径**：`/core/steps/step7_report.py`
- **功能**：Step 7 — 生成测试报告（脚本步骤）
- **关键逻辑**：
  - 通过 subprocess 调用 `scripts/generate_report.py` 生成报告
  - 从 stdout 提取通过率信息
  - 输出：`test_report.md`
- **依赖关系**：继承 `BaseStep`；依赖 `scripts/generate_report.py`
- **架构角色**：测试报告生成步骤

---

## 五、core/kb/ — 知识库管理

### 5.1 core/kb/mcp_client.py
- **路径**：`/core/kb/mcp_client.py`
- **功能**：MCP 协议客户端，直接访问 Obsidian Vault 文件系统
- **关键逻辑**：
  - `MCPClient` 类：支持三层搜索策略
    - Layer 1：Obsidian Local REST API 搜索（利用 Obsidian 内置索引）
    - Layer 2：标签匹配（YAML frontmatter 中的 tags 字段，命中加权 2.0）
    - Layer 3：全文遍历 + 多关键词 OR 匹配
  - `_safe_path()`：安全路径校验，防止路径穿越攻击
  - `_parse_yaml_frontmatter()`：解析 YAML frontmatter 元数据
  - `create_file()`：创建知识条目，历史用例按 `项目名/批次/` 三层归档
  - `extract_keywords()`：从标题、模块、内容中自动提取关键词标签（去停用词、3-gram 提取）
  - `ObsidianAPIClient`：可选增强层，通过 REST API 调用 Obsidian 内置搜索
  - 7 分类目录映射：业务规则、历史用例、线上坑点、用例模板、数据字典、业务规范、团队规范
- **依赖关系**：被 `kb_manager_mcp.py` 依赖
- **架构角色**：知识库访问的核心抽象层

### 5.2 core/kb/kb_manager_mcp.py
- **路径**：`/core/kb/kb_manager_mcp.py`
- **功能**：知识库管理器（MCP 层），通过 MCP 协议访问 Obsidian Vault
- **关键逻辑**：
  - `KnowledgeBaseManager` 类封装 `MCPClient`，提供 `search`/`add`/`ingest`/`export`/`status` 操作
  - `ingest()`：支持从 Excel 回灌知识，自动识别 12 列标准格式和通用 3 列格式
  - `export()`：导出增强上下文 Markdown，按分类分组
  - CLI 支持 6 个子命令：search、add、ingest、export、status、tags
  - `tags` 命令：遍历知识库收集所有标签及其出现次数
- **依赖关系**：依赖 `mcp_client.py`（MCPClient、KnowledgeItem、extract_keywords）
- **架构角色**：知识库管理的业务逻辑层

### 5.3 core/kb/kb_manager.py
- **路径**：`/core/kb/kb_manager.py`
- **功能**：知识库管理器（本地 Markdown + Obsidian REST API 双方案）
- **关键逻辑**：
  - `KnowledgeBaseManager` 类：优先使用 Obsidian API，fallback 到本地文件搜索
  - `BM25Engine`：纯标准库实现的 BM25 检索引擎，支持中文（字符级 + 2-gram 分词）
  - `ObsidianClient`：基于 `urllib` 的 Obsidian Local REST API 客户端
  - 支持 search/add/ingest/export/status 五项操作
- **依赖关系**：独立模块，与 `kb_manager_mcp.py` 功能平行但实现方式不同
- **架构角色**：知识库管理的备选方案（本地文件 + BM25）

---

## 六、scripts/ — 脚本层

### 6.1 scripts/common.py
- **路径**：`/scripts/common.py`
- **功能**：`generate_excel.py` 和 `generate_xmind.py` 的共享代码模块
- **关键逻辑**：
  - `TestPointParser`：解析测试点 Markdown 文件，识别模块（`## 模块`）、功能点（`### 功能点`）、测试维度（`#### 测试维度`）、测试点（`- 测试点`）、测试数据、预期结果
  - `assign_priority(tp)`：基于模块、功能点、维度、测试类型的多级决策表分配优先级（P0/P1/P2）
  - `filter_by_dimensions(test_points, dimensions)`：按维度关键词过滤测试点
  - 常量：`CORE_MODULES`、`CORE_FEATURES`、`CORE_ACTION_KW`、`DIMENSION_ALIASES`
- **依赖关系**：被 `generate_excel.py`、`generate_xmind.py` 依赖
- **架构角色**：测试点解析与优先级分配的公共逻辑

### 6.2 scripts/generate_excel.py
- **路径**：`/scripts/generate_excel.py`
- **功能**：生成 Excel 格式测试用例（12 列标准结构）
- **关键逻辑**：
  - `TestCaseGenerator`：
    - 16 种动作关键词 → 步骤模板映射表（登录/注册/上传/创建/编辑/删除/查询/评审/回灌/报告/集成/校验等），每个动作有正向和负向两套步骤模板
    - `__generate_steps(tp)`：根据测试维度生成具体步骤（正向 → 正向模板，负向 → 负向模板，边界/异常/性能/安全各有智能模板）
    - `__generate_precondition(tp)`：根据标题关键词生成前置条件
    - `generate(test_points)`：组装完整测试用例（TC-001 ~ TC-NNN）
  - `ExcelWriter`：写入 Excel 文件，带格式化（优先级着色、冻结首行、自动筛选）
  - `count_stats()`：统计模块数、功能点数、维度分布、优先级分布
- **依赖关系**：依赖 `common.py`（TestPointParser、assign_priority、filter_by_dimensions）；依赖 `openpyxl`
- **架构角色**：Excel 测试用例生成器

### 6.3 scripts/generate_xmind.py
- **路径**：`/scripts/generate_xmind.py`
- **功能**：生成 XMind 格式测试用例脑图
- **关键逻辑**：
  - `XMindGenerator`：使用 `xmind` 库生成标准 `.xmind` 文件
  - 按 模块 → 功能点 → 测试维度 → 测试点 四级树状结构组织
  - 每个测试点显示优先级标签和测试数据/预期结果子节点
  - `_add_stats()`：添加统计信息节点（总用例数、模块数、优先级分布、维度分布）
- **依赖关系**：依赖 `common.py`（TestPointParser、assign_priority、filter_by_dimensions）；依赖 `xmind` 库
- **架构角色**：XMind 脑图生成器

### 6.4 scripts/generate_report.py
- **路径**：`/scripts/generate_report.py`
- **功能**：测试报告生成脚本，读取已执行的 Excel 生成 Markdown 质量报告
- **关键逻辑**：
  - `ExcelReader`：模糊匹配表头（支持中英文别名），归一化执行结果
  - `ReportAnalyzer`：
    - 多维度统计（总计/按模块/按优先级/按维度）
    - 失败原因推断（11 类原因 + 维度加权）
    - 风险评估（高/中/低三级，综合风险等级）
    - 发布建议（基于 P0 失败数、通过率、高风险项）
  - `ReportGenerator`：生成 8 个章节的 Markdown 报告（总体概览/模块通过率/优先级分析/维度分析/失败用例分析/阻塞用例分析/风险评估/测试结论与建议）
  - 失败用例修复建议（13 种原因对应修复建议）
- **依赖关系**：依赖 `openpyxl`
- **架构角色**：测试质量报告生成器

---

## 七、web/ — Web UI 层（FastAPI + HTMX）

### 7.1 web/app.py
- **路径**：`/web/app.py`
- **功能**：FastAPI 应用入口，WebUI 启动文件
- **关键逻辑**：
  - 注册 6 个路由模块（pipeline、knowledge、config、webhooks、auth，sse 条件加载）
  - `SecurityHeadersMiddleware`：添加安全响应头（X-Content-Type-Options、X-Frame-Options、X-XSS-Protection、Referrer-Policy）+ 静态资源缓存策略（CSS/JS 缓存 1 小时，图片/字体缓存 1 天）
  - `LoggingMiddleware`：结构化日志中间件（Phase 6，条件加载），为每个请求生成 trace_id
  - 全局异常处理：未捕获异常返回标准 JSON（error、detail、path）
  - 页面路由：首页（`/`）、Pipeline 进度页（`/pipeline/{id}`）、结果预览页（`/results/{id}`）、知识库管理页（`/knowledge`）、Pipeline 列表页（`/pipelines`）、登录页（`/login`）
  - 健康检查端点（`/health`）：检查 4 项 — api（始终 ok）、database（SQLite 连通性）、llm（配置是否就绪，不实际调用）、knowledge_base（vault 路径是否存在）
  - 应用版本：`2.0.0-alpha`
- **依赖关系**：依赖 `core.config_loader`、`web.api.*`、`web.services.task_manager`、`web.middleware.logging`
- **架构角色**：Web 服务总入口

### 7.2 web/api/pipeline.py
- **路径**：`/web/api/pipeline.py`
- **功能**：Pipeline API 路由
- **关键逻辑**：
  - `POST /api/pipeline/start`：上传需求文件 → 校验格式和大小 → 检查并发限制 → 创建 PipelineTask 并启动
  - `GET /api/pipeline/{id}/progress`：返回进度（JSON 或 HTMX 片段），完成时发送 HX-Trigger 事件
  - `POST /api/pipeline/{id}/resume`：上传已执行 Excel → 后台继续执行
  - `POST /api/pipeline/{id}/cancel`：取消 Pipeline
  - `GET /api/pipeline/{id}/artifacts`：产物列表
  - `GET /api/pipeline/{id}/artifacts/{name}`：下载产物
  - `GET /api/pipeline/{id}/preview/{name}`：预览产物（Markdown 渲染或 Excel 表格前 50 行）
- **依赖关系**：依赖 `core.config_loader`、`web.services.task_manager`
- **架构角色**：Pipeline 操作的 REST API

### 7.3 web/api/knowledge.py
- **路径**：`/web/api/knowledge.py`
- **功能**：知识库 API 路由（前缀 `/api/kb`）
- **关键逻辑**：
  - `GET /api/kb/status`：通过 subprocess 调用 `kb_manager_mcp.py status` 获取知识库统计（总数、分类分布）
  - `GET /api/kb/search`：通过 subprocess 调用 `kb_manager_mcp.py search` 搜索知识库，返回前 20 条结果
  - `POST /api/kb/import`：上传 Excel 文件回灌知识库，通过 `kb_manager_mcp.py ingest` 执行
  - `POST /api/kb/add`：添加单条知识条目（form 表单提交 title、content、category、module、tags、severity）
  - 分类校验：仅允许 7 个有效分类（business-rules、historical-cases、pitfalls 等）
- **依赖关系**：依赖 `core.config_loader`、`core/kb/kb_manager_mcp.py`
- **架构角色**：知识库管理的 REST API

### 7.4 web/api/config.py
- **路径**：`/web/api/config.py`
- **功能**：配置 API 路由
- **关键逻辑**：`GET /api/config` 返回当前配置（LLM/知识库/Pipeline），API Key 脱敏，返回校验结果
- **依赖关系**：依赖 `core.config_loader`
- **架构角色**：配置查询的 REST API

### 7.5 web/api/auth.py
- **路径**：`/web/api/auth.py`
- **功能**：认证 API 路由（Phase 4）
- **关键逻辑**：
  - `POST /api/auth/login`：用户名密码登录，返回 JWT Token
  - `POST /api/auth/logout`：登出（JWT 无状态，客户端清除 Token）
  - `GET /api/auth/me`：获取当前用户信息（需 JWT）
- **依赖关系**：依赖 `db.repository`、`web.middleware.auth`、`web.services.user_service`
- **架构角色**：用户认证的 REST API

### 7.6 web/api/webhooks.py
- **路径**：`/web/api/webhooks.py`
- **功能**：Webhook 接收器，接收外部测试管理平台的事件推送
- **关键逻辑**：`POST /api/webhooks/{platform}` 获取适配器 → 验证签名 → 解析 JSON 事件 → 调用适配器处理
- **依赖关系**：依赖 `integrations.base`、`integrations.registry`
- **架构角色**：外部平台的 Webhook 入口

### 7.7 web/api/sse.py
- **路径**：`/web/api/sse.py`
- **功能**：SSE（Server-Sent Events）实时推送端点（Phase 3）
- **关键逻辑**：
  - `GET /api/pipeline/{pipeline_id}/stream`：基于 EventBus 订阅事件流
  - 15s 心跳保活（ping 事件），防止代理超时断开连接
  - 终止事件（done / error / cancelled）到达后自动关闭流
  - 事件格式：`event: step_done`，`data: {"step_id": 1, "name": "需求分析", ...}`
  - 客户端断开连接时自动取消订阅
- **依赖关系**：依赖 `web.services.event_bus`（get_event_bus）；依赖 `sse_starlette`
- **架构角色**：实时事件推送通道

### 7.8 web/middleware/auth.py
- **路径**：`/web/middleware/auth.py`
- **功能**：JWT 认证中间件（Phase 4）
- **关键逻辑**：
  - `create_token(user_id, username, role)`：生成 JWT Token（HS256 算法，24 小时过期）
  - `require_user()`：FastAPI Depends，验证 JWT 并返回 payload，无效则抛 401
  - `require_admin()`：验证管理员权限，非 admin 抛 403
  - 生产环境校验：`AI_TEST_ENV=production` 时 JWT_SECRET 长度必须 >= 32 字符
  - 模块加载时自动执行 `_validate_secret()` 校验
- **依赖关系**：依赖 `python-jose`（jwt）；被 `web/api/auth.py` 依赖
- **架构角色**：JWT 认证与授权

### 7.9 web/middleware/logging.py
- **路径**：`/web/middleware/logging.py`
- **功能**：结构化日志中间件（Phase 6），基于 structlog 输出 JSON 格式日志，每个请求自动生成唯一 trace_id
- **关键逻辑**：
  - `configure_logging()`：配置 structlog（JSON 渲染器、ISO 时间戳、INFO 级别）
  - `get_logger(name)`：获取结构化日志器
  - `LoggingMiddleware`：记录每个请求的 trace_id、方法、路径、状态码、耗时（ms），将 trace_id 注入 structlog 上下文和响应头 `X-Trace-Id`
- **依赖关系**：依赖 `structlog`；被 `web/app.py` 条件加载
- **架构角色**：请求链路追踪与结构化日志

### 7.10 web/middleware/rate_limit.py
- **路径**：`/web/middleware/rate_limit.py`
- **功能**：速率限制中间件（Phase 6），基于 slowapi 防止 API 滥用
- **关键逻辑**：
  - `limiter`：全局限速器，默认每分钟 60 次请求（按 IP）
  - `get_limiter()`：获取全局限速器实例
- **依赖关系**：依赖 `slowapi`
- **架构角色**：API 访问频率控制

### 7.11 web/services/pipeline_task.py
- **路径**：`/web/services/pipeline_task.py`
- **功能**：Pipeline 任务包装器，增加实时状态追踪
- **关键逻辑**：
  - `PipelineTask` 数据类：包装 core Pipeline，添加状态追踪（status、completed_steps、logs、llm_stats）
  - `start_background()`：后台线程执行 Pipeline
  - `resume_background()`：从断点继续
  - `cancel()`：设置取消标志，协作式取消
  - `_persist_pipeline()`/`_persist_step()`：将状态写入 DB（Phase 2 持久化层）
  - `_publish_event()`：发布事件到 EventBus（Phase 3 SSE 推送）
  - `get_progress()`：构建进度视图（百分比、步骤状态、日志）
  - `_on_log()`：日志回调（限制 200 条）
  - `_on_step_done()`：步骤完成回调，同步到 DB 和 EventBus
- **依赖关系**：依赖 `core.pipeline`、`db.repository`、`web.services.event_bus`
- **架构角色**：WebUI 与 Core Engine 之间的桥梁

### 7.12 web/services/task_manager.py
- **路径**：`/web/services/task_manager.py`
- **功能**：Pipeline 异步任务管理器
- **关键逻辑**：
  - `TaskManager` 类：基于 `ThreadPoolExecutor`（最大 2 并发）
  - `create_task()`：创建 PipelineTask → 内存追踪 → 后台启动
  - `list_tasks()`：合并内存活跃任务 + DB 历史任务（重启后可见）
  - `is_full()`：检查并发上限
  - 全局单例模式
- **依赖关系**：依赖 `web.services.pipeline_task`、`db.repository`
- **架构角色**：异步任务调度中心

### 7.13 web/services/event_bus.py
- **路径**：`/web/services/event_bus.py`
- **功能**：进程内 pub/sub 事件总线（基于 asyncio.Queue）
- **关键逻辑**：
  - `EventBus` 类：支持按 topic（pipeline_id）订阅
  - `subscribe(topic)`：返回 `asyncio.Queue`，消费者从中 get() 事件
  - `publish(topic, event)`：异步发布（队列满时丢弃旧事件）
  - `publish_sync(topic, event)`：线程安全同步发布（供工作线程调用）
  - `unsubscribe()`：取消订阅，无订阅者时清理主题
  - 全局单例模式
- **依赖关系**：被 `pipeline_task.py` 依赖
- **架构角色**：SSE 实时推送的事件源

### 7.14 web/services/user_service.py
- **路径**：`/web/services/user_service.py`
- **功能**：用户服务（Phase 4），提供密码哈希、用户认证、管理员引导、API Key 生成
- **关键逻辑**：
  - `hash_password(password)`：bcrypt 哈希密码，返回可存储的字符串
  - `verify_password(password, password_hash)`：验证密码是否匹配哈希
  - `authenticate(username, password)`：用户名 + 密码认证，成功返回 User 对象并更新最后登录时间，失败返回 None
  - `create_admin_if_not_exists(username, password)`：首次启动时创建管理员账户，返回 True 表示新建，False 表示已存在
  - `generate_api_key()`：生成 32 字符随机 hex API Key
- **依赖关系**：依赖 `bcrypt`、`db.models`（User）、`db.repository`、`db.session`
- **架构角色**：用户认证业务逻辑

### 7.15 web/static/ 与 web/templates/
- **路径**：`/web/static/`、`/web/templates/`
- **功能**：前端静态资源与 HTML 模板
- **包含文件**：
  - `static/app.js`：前端交互逻辑（HTMX 事件处理）
  - `static/custom.css`：自定义样式
  - `templates/base.html`：基础布局模板
  - `templates/index.html`：首页（上传需求 + 启动 Pipeline）
  - `templates/knowledge.html`：知识库管理页
  - `templates/login.html`：登录页
  - `templates/pipeline.html`：Pipeline 详情页
  - `templates/pipeline_progress.html`：Pipeline 进度片段（HTMX 局部刷新）
  - `templates/pipelines.html`：Pipeline 列表页
  - `templates/results.html`：结果预览页
- **架构角色**：前端 UI 层

---

## 八、db/ — 数据持久化层

### 8.1 db/models.py
- **路径**：`/db/models.py`
- **功能**：SQLAlchemy ORM 数据模型定义
- **关键逻辑**：
  - `Pipeline` 表：id、requirements_path、mode、dimensions、formats、status、started_at、finished_at、error、output_dir
  - `PipelineStep` 表：pipeline_id（FK）、step_id、name、status、detail、started_at、finished_at、llm_calls（JSON 格式）、retry_count
  - `Artifact` 表：pipeline_id（FK）、name、display_name、type（md/xlsx/xmind/json）、size、created_at
  - `User` 表：username、password_hash、role、api_key、created_at、last_login
  - 所有表预留 `tenant_id` 字段用于 Track B 多租户演进
  - Pipeline 表额外预留 `workflow_id` 字段（Track B）
  - 关系：Pipeline 1:N PipelineStep（cascade delete-orphan），Pipeline 1:N Artifact（cascade delete-orphan）
- **依赖关系**：依赖 SQLAlchemy；被 `db/repository.py`、`db/session.py` 依赖
- **架构角色**：数据库 Schema 定义

### 8.2 db/session.py
- **路径**：`/db/session.py`
- **功能**：SQLAlchemy Session 管理
- **关键逻辑**：
  - `get_engine()`：创建/获取全局同步 Engine（SQLite + WAL 模式 + 外键约束 + StaticPool）
  - `get_session_factory()`：创建/获取全局 SessionFactory
  - `get_session()`：获取新 Session
  - `init_db()`：创建所有表
  - `session_scope()`：事务作用域上下文管理器（自动 commit/rollback/close）
  - `reset_engine()`：重置引擎缓存（测试用）
  - 支持 `DATABASE_PATH` 环境变量覆盖
- **依赖关系**：依赖 `db.models`（Base）
- **架构角色**：数据库连接管理

### 8.3 db/repository.py
- **路径**：`/db/repository.py`
- **功能**：数据访问层，封装 Pipeline/PipelineStep/Artifact/User 的 CRUD 操作
- **关键逻辑**：
  - `PipelineRepository` 类：
    - `create_pipeline()`/`get_pipeline()`/`list_pipelines()`/`update_pipeline_status()`
    - `record_step()`/`get_steps()`/`get_completed_step_ids()`
    - `record_artifact()`/`get_artifacts()`
    - `get_user_by_username()`/`get_user_by_api_key()`/`create_user()`
  - 所有查询使用 `session_scope()` 自动管理事务
  - 查询结果 `expunge` 后返回，避免 Session 关闭后访问问题
  - 全局单例 `get_repository()`
- **依赖关系**：依赖 `db.models`、`db.session`
- **架构角色**：数据访问层（Repository 模式）

### 8.4 db/migrations/
- **路径**：`/db/migrations/`
- **功能**：Alembic 数据库迁移管理
- **包含文件**：
  - `env.py`：Alembic 环境配置，连接数据库并设置目标元数据
  - `script.py.mako`：迁移脚本模板
  - `versions/24d34db69863_initial_schema.py`：初始 Schema 迁移脚本
- **依赖关系**：依赖 `alembic.ini`、`db/models.py`（Base.metadata）
- **架构角色**：数据库版本迁移

---

## 九、integrations/ — 集成适配层

### 9.1 integrations/models.py
- **路径**：`/integrations/models.py`
- **功能**：内部标准数据模型（Canonical Model）
- **关键逻辑**：定义 6 个数据类：`TestCase`（12 列 + external_id + custom_fields）、`TestResult`、`TestRun`、`Defect`、`SyncResult`、`SyncLogEntry`
- **架构角色**：所有外部平台数据的内部统一表示

### 9.2 integrations/base.py
- **路径**：`/integrations/base.py`
- **功能**：适配器抽象基类
- **关键逻辑**：
  - `AdapterConfig`：适配器配置（platform、base_url、api_key、username、password、project_id、field_mapping_path、extra）
  - `BaseAdapter` 抽象类：定义 `authenticate()`、`push_test_cases()`、`pull_test_cases()`、`push_test_results()`、`pull_test_results()` 等抽象方法
  - 可选实现：`create_test_run()`、`list_test_runs()`、`push_defects()`、`pull_defects()`（默认抛出 NotImplementedError）
  - Webhook 支持：`verify_signature()`（默认返回 True）、`handle_webhook()`（默认返回 None）
  - `health_check()`：调用 `authenticate()` 检查连通性
  - `get_platform_info()`：返回平台名和传输协议
- **架构角色**：平台适配器的统一接口契约

### 9.3 integrations/registry.py
- **路径**：`/integrations/registry.py`
- **功能**：适配器注册表
- **关键逻辑**：
  - `AdapterRegistry` 类：装饰器注册 + 目录自动发现
  - `register(platform)`：类装饰器，将适配器类注册到 `_adapters` 字典
  - `get_adapter(platform, config)`：工厂方法，获取适配器实例
  - `auto_discover(package)`：自动发现 `integrations/adapters/` 下的所有适配器模块
- **架构角色**：适配器插件管理

### 9.4 integrations/auth.py
- **路径**：`/integrations/auth.py`
- **功能**：认证策略链（API Key / Basic Auth / OAuth2）
- **关键逻辑**：
  - `AuthStrategy` 抽象基类
  - `APIKeyAuth`：API Key 认证（TestRail、Zephyr）
  - `BasicAuth`：Basic Auth（TestLink XML-RPC）
  - `OAuth2Auth`：OAuth2 Bearer Token（JIRA/Xray），支持 Token 刷新
  - `create_auth()`：工厂方法
- **架构角色**：外部平台认证策略

### 9.5 integrations/field_mapper.py
- **路径**：`/integrations/field_mapper.py`
- **功能**：字段映射引擎（配置驱动）
- **关键逻辑**：
  - `FieldMapper` 类：基于 YAML 配置的双向字段映射
  - `to_platform()`：内部格式 → 平台格式
  - `to_canonical()`：平台格式 → 内部格式
  - 支持 4 种转换器：`join`（List → 字符串）、`template`、`lookup`（运行时查询）、值映射表
  - `_reverse_transform()`：反向转换
- **依赖关系**：依赖 PyYAML
- **架构角色**：字段映射转换引擎

### 9.6 integrations/bridge.py
- **路径**：`/integrations/bridge.py`
- **功能**：Core Engine 和 Adapter Layer 之间的桥接层
- **关键逻辑**：
  - `IntegrationBridge` 类：
    - `excel_to_testcases(xlsx_path)`：读取 testcases.xlsx → List[TestCase]
    - `excel_to_results(xlsx_path)`：读取执行结果列 → List[TestResult]
    - `testcases_to_excel(cases, output_path)`：反向：Canonical → Excel
- **架构角色**：Core Engine 产出与集成层之间的数据转换

### 9.7 integrations/sync_engine.py
- **路径**：`/integrations/sync_engine.py`
- **功能**：同步引擎，支持增量/全量推送、拉取、双向同步
- **关键逻辑**：
  - `SyncEngine` 类：
    - `sync_push()`：增量推送（基于 `updated_at` 时间戳）
    - `sync_pull()`：全量拉取
    - `sync_bidirectional()`：双向同步 + 冲突检测与解决
    - `_detect_conflicts()`：检测同 ID 两端都有更新的冲突
    - `_resolve_conflict()`：4 种冲突解决策略（last_write_wins / source_wins / target_wins / manual）
    - 状态持久化（`_sync_state.json`）
- **依赖关系**：依赖 `integrations.base`、`integrations.models`
- **架构角色**：与外部平台的数据同步引擎

### 9.8 integrations/adapters/testrail.py
- **路径**：`/integrations/adapters/testrail.py`
- **功能**：TestRail 适配器参考实现，基于 TestRail API v2（REST + Basic Auth）
- **关键逻辑**：
  - `TestRailAdapter` 类（通过 `@AdapterRegistry.register("testrail")` 注册）：
    - `authenticate()`：通过 `get_user/current` 验证连接
    - `push_test_cases()`：逐条推送用例，支持新建（add_case）和更新（update_case），自动创建/查找 Section
    - `pull_test_cases()`：从指定 project 拉取用例，通过 FieldMapper 转换为 Canonical 模型
    - `push_test_results()`：推送执行结果到 TestRun
    - `pull_test_results()`：从 TestRun 拉取执行结果
    - `verify_signature()`：HMAC-SHA256 签名验证
    - 状态映射：passed→1, failed→5, blocked→2, skipped→3, retest→4
- **依赖关系**：继承 `BaseAdapter`；依赖 `integrations.field_mapper`、`integrations.registry`
- **架构角色**：TestRail 平台适配器实现

### 9.9 integrations/mappings/
- **路径**：`/integrations/mappings/`
- **功能**：平台字段映射 YAML 配置文件
- **包含文件**：
  - `testrail_mapping.yaml`：TestRail 字段映射配置
  - `testlink_mapping.yaml`：TestLink 字段映射配置
- **依赖关系**：被 `integrations/field_mapper.py` 读取
- **架构角色**：平台字段映射规则

---

## 十、tests/ — 测试目录

### 10.1 tests/
- **路径**：`/tests/`
- **功能**：单元测试和集成测试
- **包含文件**（共 22 个测试文件）：
  - `test_common.py`：TestPointParser、assign_priority、filter_by_dimensions 的单元测试
  - `test_excel_reader.py`：Excel 读取器测试
  - `test_file_lock.py`：文件锁测试
  - `test_xmind.py`：XMind 生成测试
  - `test_phase3_async.py`：Phase 3 异步功能测试
  - `test_pipeline_progress_e2e.py`：Pipeline 进度端到端测试
  - `test_pipeline_progress_template.py`：Pipeline 进度模板测试
  - `test_db_persistence.py`：数据库持久化测试
  - `test_api_endpoints.py`：API 端点测试
  - `test_auth.py`：认证功能测试
  - `test_cli.py`：CLI 命令行测试
  - `test_config_loader.py`：配置加载器测试
  - `test_integration_bridge.py`：集成桥接层测试
  - `test_llm_gateway.py`：LLM 网关测试
  - `test_performance.py`：性能测试
  - `test_pipeline_api.py`：Pipeline API 测试
  - `test_security.py`：安全测试
  - `test_task_manager.py`：任务管理器测试
  - `test_perf_security_supplement.py`：性能与安全补充测试（KB API 响应时间、CSP/CORS/HSTS 头、HTTP 参数污染、大请求体防护、敏感信息泄露）
  - `test_boundary.py`：边界条件与异常测试（Pipeline 异常处理、TaskManager 并发上限、知识库边界、认证 Token 边界、配置类型边界、数据库连接边界）
  - `mock_testrail.py`：TestRail 模拟
  - `__init__.py`：包初始化文件
- **架构角色**：质量保障

---

## 十一、examples/ — 示例目录

### 11.1 examples/
- **路径**：`/examples/`
- **功能**：示例需求文档，供新用户快速体验
- **包含文件**：
  - `demo_requirements.md`：演示用需求文档
  - `order_requirements.md`：订单系统示例需求文档
- **架构角色**：入门示例与测试数据

---

## 十二、文件依赖关系图

```
cli.py
├── core/config_loader.py
│   └── (.env, config.yaml)
└── core/pipeline.py
    ├── core/llm_client.py ─── openai
    ├── core/llm_gateway.py ─── core/llm_client.py
    ├── core/steps/base.py ─── core/llm_client.py
    ├── core/steps/step1_analysis.py ─── core/prompt_loader.py ─── core/prompts/*.md
    ├── core/steps/step2_kb_search.py ─── core/kb/kb_manager_mcp.py ─── core/kb/mcp_client.py
    ├── core/steps/step3_testpoints.py ─── core/prompt_loader.py
    ├── core/steps/step4_generate.py ─── scripts/generate_excel.py ─── scripts/common.py
    │                                 └── scripts/generate_xmind.py ─── scripts/common.py
    ├── core/steps/step5_review.py ─── core/prompt_loader.py
    ├── core/steps/step6_human_test.py
    └── core/steps/step7_report.py ─── scripts/generate_report.py

web/app.py
├── web/middleware/logging.py ─── structlog
├── web/api/pipeline.py ─── web/services/task_manager.py
│   └── web/services/pipeline_task.py
│       ├── core/pipeline.py
│       ├── db/repository.py ─── db/models.py, db/session.py
│       └── web/services/event_bus.py
├── web/api/knowledge.py ─── core/kb/kb_manager_mcp.py
├── web/api/config.py ─── core/config_loader.py
├── web/api/auth.py ─── web/services/user_service.py, web/middleware/auth.py
├── web/api/sse.py ─── web/services/event_bus.py
└── web/api/webhooks.py ─── integrations/registry.py ─── integrations/base.py

web/middleware/
├── auth.py ─── python-jose
├── logging.py ─── structlog
└── rate_limit.py ─── slowapi

integrations/
├── models.py (独立)
├── base.py ─── models.py
├── registry.py ─── base.py
├── auth.py (独立)
├── field_mapper.py (独立)
├── bridge.py ─── models.py
├── sync_engine.py ─── base.py, models.py
├── adapters/testrail.py ─── base.py, registry.py, field_mapper.py, models.py
└── mappings/
    ├── testrail_mapping.yaml
    └── testlink_mapping.yaml

db/
├── models.py (独立)
├── session.py ─── models.py
├── repository.py ─── models.py, session.py
└── migrations/ ─── alembic.ini, models.py
```

---

*文档由 AI 自动生成并校对，基于项目 v2.0.0 源码分析。*
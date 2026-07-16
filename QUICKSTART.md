# 快速开始

## 1. 安装

```bash
# 进入项目目录
cd ai-test-system

# 安装核心 + WebUI + Excel/XMind
pip install -e ".[web,xmind,excel]"

# 或仅安装核心（CLI 模式）
pip install -e .
```

## 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY=sk-xxx
```

支持 OpenAI 兼容协议的所有模型（DeepSeek / GLM / OpenAI / Moonshot / 通义千问）。

## 3. 执行全流程

### CLI 命令行

```bash
# 查看当前配置
python cli.py config

# 执行全流程（半自动模式，AI 步骤后有检查点）
python cli.py run examples/demo_requirements.md

# 全自动模式（AI 步骤连续执行）
python cli.py run examples/demo_requirements.md --mode auto

# 全 6 维测试（含性能/安全）
python cli.py run examples/demo_requirements.md -d all

# 生成 Excel + XMind
python cli.py run examples/demo_requirements.md -f excel,xmind
```

### Web UI

```bash
# 启动 Web 服务
uvicorn web.app:app --port 8080
# 或
python -m web.app
```

打开浏览器访问 `http://localhost:8080`。

## 4. 查看进度 / 断点续跑

```bash
# 查看当前 Pipeline 状态
python cli.py status -o output/

# 从断点继续（如执行测试后生成报告）
python cli.py resume -o output/
```

## 5. 输出产物

默认输出到 `./output/` 目录：

```
output/
├── requirements_analysis.md         # 需求拆解
├── clarification_needed.md          # 待确认清单
├── knowledge-context.md             # 知识库增强上下文
├── testpoints.md                    # 测试点清单
├── testcases.xlsx                   # Excel 测试用例
├── testcases.xmind                  # XMind 脑图（可选）
├── test_case_review_report.md       # 用例评审报告
├── test_report.md                   # 测试报告（执行后）
└── _pipeline_state.json             # 断点状态
```

## 下一步

- [需求规格说明书](docs/requirements.md)
- [文件功能分析](docs/file-analysis.md)
- [完整文档](README.md)

# AI 测试用例生成系统 — Makefile
# 常用开发命令

PYTHON ?= python

.PHONY: help install dev-install test test-cov test-e2e test-e2e-backend test-e2e-frontend lint format type-check security-audit clean run

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装核心依赖
	$(PYTHON) -m pip install -e .

dev-install: ## 安装开发全量依赖
	$(PYTHON) -m pip install -e ".[dev-all]"

test: ## 运行测试
	$(PYTHON) -m pytest tests/ -q

test-cov: ## 运行测试并生成覆盖率报告
	$(PYTHON) -m pytest tests/ --cov=core --cov=web --cov=db --cov-report=term

test-e2e: test-e2e-backend test-e2e-frontend ## 运行全部 e2e 测试（后端 + 前端）

test-e2e-backend: ## 后端 e2e 测试（auth/config/health/usage 全链路）
	AUTH_ENABLED=true JWT_SECRET="test-only-secret-for-pytest-fixture-32chars" \
	$(PYTHON) -m pytest tests/e2e/ -q --tb=short

test-e2e-frontend: ## 前端 Playwright e2e 测试（chromium + mobile）
	cd webui && npx playwright test --reporter=list

lint: ## 代码规范检查（ruff）
	ruff check core/ db/ web/ tests/

format: ## 自动格式化代码（ruff）
	ruff check core/ db/ web/ tests/ --fix
	ruff format core/ db/ web/ tests/

type-check: ## 类型检查（mypy）
	mypy core/ db/ web/ --ignore-missing-imports

security-audit: ## 依赖安全审计
	pip-audit --strict

clean: ## 清理临时文件
	find . -type d -name __pycache__ -not -path './.git/*' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null
	rm -rf .pytest_cache .coverage
	find output/ -mindepth 1 -maxdepth 1 -not -name '.gitkeep' -exec rm -rf {} + 2>/dev/null
	find uploads/ -type f -not -name '.gitkeep' -delete 2>/dev/null

run: ## 启动开发服务器
	$(PYTHON) -m web.app

db-backup: ## SQLite 数据库备份（保留最近 5 份）
	$(PYTHON) scripts/db_backup.py --keep 5

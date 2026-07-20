# Changelog

本文件记录 AI 测试用例生成系统的版本变更历史。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [2.1.0] — 2026-07-20

### 🐛 修复
- **KB 双数据源不一致**：`/status` `/search` 读 config.yaml 而 `/current_config` 读 DB，导致知识库页面「生效配置」和「统计」两卡片指向不同 vault。统一到 DynamicKBManager（DB 数据源），补齐 `enabled` 字段（MCPClient.status() 原无此字段，前端误报「未启用」）。
- **健康检查 KB 状态读旧 config.yaml**：`/health` 端点的 knowledge_base 检查改走 DB（DynamicKBManager），与 `/knowledge/status` 同源。
- **`/update_config` 500 错误**：`requests` 顶层导入在未安装时崩溃，改为延迟导入。
- **rate limit 测试持续失败**：slowapi 在 production 可选依赖组，dev 环境未安装时优雅跳过。

### ✨ 新增
- **interrupted 任务可恢复（方案 A）**：服务重启后 DB 中 interrupted 的任务可通过「继续执行」按钮恢复。`TaskManager.rebuild_task_from_db()` 从 DB 重建内存 PipelineTask，恢复已完成步骤（断点续跑依据）。
- **服务重启自动恢复（方案 B）**：启动时自动扫描 interrupted 任务，对有已完成步骤 + requirements 文件存在的重建到内存，用户刷新页面即可看到进度并点继续。不引入外部依赖（无 Redis/Celery）。
- **工作区清理脚本** `scripts/clean_workspace.py`：清理 uploads 陈旧文件 + output 空目录（interrupted 任务遗留），默认 dry-run。

### 🔧 优化
- **Sprint 6.2 UI**：Dashboard 健康面板重设计（卡片网格 + 骨架屏 + 手动刷新），主题双态化（light/dark）。
- **测试覆盖**：新增 25 个回归测试（KB 数据源 11 + interrupted-resume 7 + KB cache 16 重写），551 passed / 4 skipped。

---

## [2.0.0] — 2026-07-19

### ✨ Sprint 6.1：前后端彻底分离
- 后端 FastAPI 纯 JSON API，路由统一 `/api/v1/*`
- 前端 Vue 3 SPA（Vite 6 + vue-router），dev 5173 代理→8090
- Auth 切除，知识库动态配置（DynamicKBManager + KBConfig 表 + 热切换）

---

### 🔧 优化
|- **P0.1**: 修复 `generate_report.py` 的 `_fmt_pct` 方法调用错误
  - 统一使用 `self._fmt_percent()` 并添加除零保护
|- **P0.3**: 修复 `mcp_client.py` 的 `list_files` 使用 `glob` 只扫顶层目录的 Bug
  - 历史用例按 `🏆 历史用例/项目名/批次/` 三层存储，`glob("*.md")` 无法发现
  - 改为 `rglob("*.md")`，51 条历史用例从「不可见」恢复为可检索
|- **P0.4**: 修复 `generate_excel.py` 字段名语义错误
  - 字段名 `"预留"` 修正为 `"expected"`
|- **P1.4**: 新增单元测试框架
  - 添加 `pytest` 和 `pytest-cov` 依赖
  - 完成核心模块 `TestPointParser`、`assign_priority`、`filter_by_dimensions` 的测试覆盖（15个测试用例）
|- **P1.5**: 抽取 `generate_excel.py` 和 `generate_xmind.py` 的重复代码为 `common.py` 共享模块
  - `TestPointParser`、`assign_priority`、`filter_by_dimensions`、`CORE_*` 常量统一维护
  - 删减 140 行重复代码，三份独立实现合并为一份
|- **P1.7**: 新增 `requirements.txt` 依赖声明文件
|- **P1.9**: 修复 `pipeline.py` subprocess `-c` 的 f-string 路径注入风险
  - `load_workbook('{xlsx_path}')` → `load_workbook(sys.argv[1])` 安全传参
|- **P2.3**: 移除版本控制中的大 HTML 文件
  - 从 git 中移除 `reference/*.html` (4.3MB)
  - 完善 `.gitignore` 规则
|- **P2.6**: 统一 README 版本号与 CHANGELOG 一致
  - Pipeline: v1.1.0 → v1.3.0
  - Knowledge-base: v2.0.1 → v2.1.0
  - 新增 OPTIMIZATION_STATUS.md 优化完成状态报告
|- **P2.10**: `.gitignore` 新增 `test-run/` 和 `reference/*.html` 规则
|- **P2.11**: 删除 `.DS_Store`
|- **P2.13**: 新增 `LICENSE`（MIT）
|- **P2.14**: 新增本 `CHANGELOG.md`

## [1.2.0] — 2026-07-14

### ✨ 新增
- Pipeline Skill v1.2.0：自动串联 7 步全流程 + 断点续跑
- knowledge-base v2.0.1：MCP 层方案，通过 `mcp_client.py` 直接访问 Obsidian Vault
- 历史用例按项目维度分层归档（`项目名/批次/TC-xxx.md`）
- 步骤模板映射表（16 种动作关键词→正向/负向步骤模板）

### 🔧 修复
- `generate_excel.py` 步骤模板回退问题（P0 级）
- `generate_excel.py` 优先级分配 P0 覆盖率偏低（15% → 38%）
- `kb_manager_mcp.py` ingest 列错位 Bug（v2.0.1）
- 全流程自验证：78 条用例通过率 87.2%，质量评分 77/100

## [1.1.0] — 2026-07-13

### ✨ 新增
- 7 个独立 Skill 完成开发：requirement-analysis、test-points、generate-testcases、test-case-review、generate-report、knowledge-base、pipeline
- 支持 Excel（12 列结构化）和 XMind（树状脑图）双格式输出
- 知识库 7 种分类（业务规则/历史用例/线上坑点/用例模板/数据字典/业务规范/团队规范）

## [1.0.0] — 2026-07-12

### ✨ 初始版本
- 项目立项，确定独立仓库结构
- 确定全流程 7 步架构：需求分析→知识库检索→测试点→生成用例→评审→执行→报告

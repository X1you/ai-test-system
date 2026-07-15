# Changelog

本文件记录 AI 测试用例生成系统的版本变更历史。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.3.0] — 2026-07-15

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

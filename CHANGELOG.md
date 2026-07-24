# Changelog

本文件记录 AI 测试用例生成系统的版本变更历史。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [2.3.0] — 2026-07-24

### 🚀 多 LLM Provider 管理 V1-V4（高自由度多协议配置）

> **背景**：原健康检查因 base_url 配置重复路径导致 404，前端却误报"连接正常"。根因在于单 Provider 硬编码协议，无法适应用户多 LLM / 多协议场景。
> **方案**：前后端改造为多 Provider + 多协议（OpenAI 兼容 / Anthropic / 自定义 HTTP）高自由度配置，遵循产品经理调研报告 MVP + 2 期落地。

#### ✨ 新功能

1. **多协议 LLM 客户端抽象**（`core/llm_client.py`）
   - OpenAI 兼容 / Anthropic / Custom HTTP 三协议统一 `BaseLLMClient` 抽象
   - `create_llm_client(config)` 工厂按协议自动选择实现
   - base_url 末尾 `/chat/completions` 自动剥离（防路径重复）

2. **多 Provider 路由 + 故障转移**（`core/llm_gateway.py`）
   - 按 `priority` 顺序尝试 Provider，断路器自动跳过已熔断项
   - 主 Provider 失败自动切换备选，`failovers` 统计

3. **配置自动迁移**（`core/config_loader.py`）
   - 旧单 Provider schema 自动迁移为新 `providers` 列表（向后兼容）

4. **Provider CRUD + 测试连接**（`web/api/config.py`）
   - `GET/PUT /config`、`POST /config/test_provider`、`POST /config/set_default`
   - `GET /config/providers`、`GET /health/ready` 多 Provider 状态报告

5. **V1 拖拽排序**（故障转移顺序）
   - 前端 HTML5 DnD，`POST /config/reorder_providers` 同步 `priority` 字段

6. **V2 批量操作**（多选启用/禁用/删除）
   - `POST /config/batch_toggle`、`POST /config/batch_delete`
   - 默认 Provider 保护：禁用时自动切默认，删除时拒绝

7. **V3 分组标签**（provider tags）
   - Provider 配置新增 `tags` 字段，前端标签编辑（回车/逗号添加，Backspace 删除）
   - SettingsView 标签筛选条，按标签筛选 Provider 列表

8. **V4 用量仪表盘**（call count / tokens / success rate）
   - `core/llm_usage.py` 应用级内存统计单例（线程安全，`threading.Lock`）
   - `BaseLLMClient.chat` / `async_chat` 成功/失败埋点（不污染 `test_connection` 健康检查）
   - `GET /api/v1/usage/llm` 聚合视图 + `POST /api/v1/usage/reset` 清空
   - 前端 `UsageDashboard.vue` 仪表盘组件（汇总卡片 + Provider 表格 + ARIA 语义）
   - `stores/usage.ts` staleTime 5s 缓存 + GET 请求 inflight 去重

#### 🐛 关键 Bug 修复

1. **base_url 路径重复致 404**：`OpenAICompatibleClient` 构造时自动剥离 `/chat/completions` 后缀
2. **前端连接状态误报**：`testConnection` 仅当 `llm` 状态为 `ok` 才返回成功（`degraded` 不再视为成功）
3. **后端健康检查 degraded 误判就绪**：`_all_dependencies_ok` 当 LLM 段为 dict 时，任一 provider ok 即就绪
4. **async handler 同步调用阻塞 event loop**：`test_provider` 用 `asyncio.to_thread` 包裹同步 SDK 调用
5. **健康检查 timeout 失效**：`_do_chat` / `_async_do_chat` 增加 `timeout` 参数透传
6. **PUT /config providers 数组写盘失败**：检测到数组时降级为 `_write_full_yaml` 全量重写
7. **PUT /config api_key 丢失**：空/掩码 api_key 从原配置保留
8. **`reset()` 死锁**：`threading.Lock` 不可重入，`reset()` 持锁后调用 `snapshot()` 死锁 — 改为锁内手动构造快照
9. **`test_fallback_recorded_on_failover` 回归**：`LLMGateway.chat` 重构为 `self.clients` 后测试未同步 `clients` 属性

#### ✅ 验证
- 后端：805 单元测试全部通过（含 12 个 V4 新增测试）
- 前端：`npm run build` 通过，gzip 47.40KB（≤ 200KB 性能预算）
- ARIA 语义：仪表盘表格 `role=table` + `aria-label`，按钮防重复点击

#### ⚠️ 已知限制
- 用量统计为进程级内存聚合，重启清空（无持久化，V5+ 可接入 SQLite）
- 用量统计不含缓存命中（`temp=0` 缓存命中不计入 calls/tokens）

---

## [2.2.2] — 2026-07-22

### 🩹 靶向热修复模式 [Hot-Fix] — 暗色主题系统级失效修复

> **触发场景**：生产级审计发现暗色模式样式大面积静默丢失  
> **根因**：旧版 glow 主题变量残留 + 单色主题 token 值非法，3 类问题叠加

#### 🐛 关键 Bug 修复

1. **`--glow-h` 未定义变量致 44+ 处样式失效** — 根因
   - 16 个文件（Login/Dashboard/Settings/Knowledge/PipelineList/PipelineNew/PipelineDetail + FileDropZone/ArtifactPreview/EmptyState/StepProgress/LogPanel/StatCard/ToastContainer/StatusBadge/ArtifactList）引用了 `hsl(var(--glow-h) S% L%)`
   - `--glow-h` 在当前 Bard v6 单色 tokens.css 中从未定义 → 表达式求值为非法 CSS → 整条 `border-color`/`box-shadow`/`color`/`text-shadow` 声明被浏览器静默丢弃
   - **修复**：批量将 `hsl(var(--glow-h|mono-hue) S% L%)` 强制饱和度归零为 `hsl(0 0% L%)`（纯灰，保留亮度与 alpha），与单色设计系统对齐

2. **`--mono-hue: 0` 配非零饱和度产生红色调** — 根因
   - `StatusBadge`/`EmptyState` 使用 `hsl(var(--mono-hue) 60% 85%)` → `hsl(0 60% 85%)` = 粉白，破坏纯灰度
   - **修复**：同上，饱和度归零为 `hsl(0 0% 85%)`

3. **`--accent-subtle` 非法 hex/alpha 语法致聚焦环失效** — 根因
   - `--accent-subtle: #000000 / 0.04` 非合法 CSS（hex 不能接 `/ alpha`）
   - 用于 `.form-input:focus { box-shadow: 0 0 0 3px var(--accent-subtle) }` → 声明失效 → 输入框聚焦无光环
   - **修复**：改为合法 `rgba(0,0,0,0.04)`（亮）/ `rgba(255,255,255,0.08)`（暗）

4. **`--accent-glow: none` / `--shadow-accent: none` 在 box-shadow 列表中非法** — 根因
   - `none` 作为阴影图层颜色非法（如 `box-shadow: var(--shadow-md), var(--shadow-accent)`），导致整条声明被丢弃
   - **修复**：`--accent-glow: transparent`（合法颜色）；`--shadow-accent: 0 0 0 0 transparent`（合法零尺寸阴影，逗号列表安全）

#### ✅ 验证
- 生产构建 `npm run build` 1.10s 通过，零 CSS 错误
- 浏览器实测：暗色模式登录卡片边框/阴影恢复，炭黑背景，纯灰度无彩色，控制台零警告

---

## [2.2.1] — 2026-07-22

### 🩹 靶向热修复模式 [Hot-Fix] — 渲染失真、SVG 解析、遗留清理

> **触发场景**：用户报告新打开的页面样式严重失真  
> **根因**：3 个独立问题叠加 — emoji 残留、引用缺失、组件解析失败

#### 🐛 关键 Bug 修复

1. **Login 页面严重失真** — 根因
   - `Login.vue` 第 5 行残留 emoji `<span class="login-icon">🧪</span>`
   - 旧 emoji 与 V4 极简黑白灰主题严重冲突
   - **修复**：替换为 `<BardIcon :size="56" variant="emoji" />`，配 80×80 圆角容器
   - **顺带**：CSS `.login-icon` 升级（居中布局 + 悬停 1.04x 脉动 + `prefers-reduced-motion` 兜底）

2. **router-view 全站空白** — 根因
   - `src/main.js` 把 `app.use(router)` 放到了 `app.mount('#app')` 之后
   - 违反 Vue 3 plugin 注册顺序原则 → `<router-view>` 无法解析 → 整站空白
   - **修复**：重排顺序为 `createApp → use(router) → mount`，并加详细注释防止再犯

3. **BardIcon size=56 校验失败** — 根因
   - `BardIcon.vue` size validator 限定为 `[12,16,24,32,48,64,96,128]` 预设档位
   - Login 使用 `size=56`（与 80 容器匹配）→ 触发 `[Vue warn] Invalid prop`
   - **修复**：validator 改为接受 1-1024 任意正整数，CSS 预设类保留作为参考

4. **BardIcon.vue SFC 解析失败** — 根因
   - 在 `<style scoped>` 块里写了 HTML 注释 `<!-- ... -->`
   - Vue SFC 编译器要求 `<style>` 块必须是纯 CSS
   - **修复**：HTML 注释改为 CSS 注释 `/* ... */`

#### 🗑️ 遗留文件清理

| 路径 | 类别 | 替代 |
|------|------|------|
| `legacy/templates_sprint60/` 7 个文件 | 旧 sprint 60 Django 模板 | Vue 3 SPA 全套 view |
| `src/components/GlobalIcons.vue` | 旧 SVG provide/inject 组件 | `<BardIcon>` |
| `src/components/PageLoader.vue` | 旧全屏加载器（含旧实心圆+SMIL） | `<FlowSpinner>` |
| `webui/dist/` | 旧构建产物 | `npm run build` 重新生成 |

**清理文档**：[`REMOVED_FILES.md`](REMOVED_FILES.md) — 含回退方法、验证脚本、待确认清单

#### 🎨 代码质量增强

1. **vite.config.js 升级**
   - `manualChunks: { 'vendor-vue': ['vue', 'vue-router'] }` → 93.52KB 单独 chunk，缓存友好
   - `target: 'es2020'` → 现代浏览器（覆盖 96%+）
   - `cssCodeSplit: true` → 每个 view 一份 CSS
   - `chunkSizeWarningLimit: 600` → 减少误报警告
   - `reportCompressedSize: false` → CI 提速 ~30%
   - `strictPort: false` → 端口被占自动换号

2. **main.js 健壮性**
   - `app.config.errorHandler` → 全局错误捕获（生产可接 Sentry）
   - `router.onError` → 懒加载失败兜底（提示用户强制刷新）
   - 性能埋点：`requestAnimationFrame` 测 mount 时长，仅 dev 模式输出（生产被 terser 剥离）

3. **index.html 优化**
   - `<noscript>` 兜底（SEO + 关 JS 仍可见）
   - `<link rel="preconnect" href="http://127.0.0.1:8000" crossorigin>` → 提前建连
   - 关键 CSS 内联（背景 + color-scheme）→ 避免 FOUC
   - PWA `site.webmanifest` 占位说明更新

4. **BardIcon 自适应**
   - size validator 改为 1-1024 范围
   - strokeWidth / dotRadius 在 12/16/24/32/48/64/128 + 1-1024 全段位校准

#### ✅ 端到端验证

| 验证项 | 结果 |
|--------|------|
| `npm run icons:build` | ✓ 32 个资源文件 |
| `npm run build` | ✓ 1.02s，无错误 |
| dev server 启动 | ✓ Vite 6.2.0 122ms |
| Login 页面 BardIcon 渲染 | ✓ DOM 含 `<svg>` + 8 `<path>` + `<circle>` |
| Login 页面无 Vue 警告 | ✓ 0 个 [Vue warn] |
| 生产 bundle vendor 分包 | ✓ vendor-vue 93.52KB 单独缓存 |
| dist 总大小 | ✓ 400KB |

#### 📚 文档

- 新增 [`REMOVED_FILES.md`](REMOVED_FILES.md) — 清理清单 + 回退方法
- 更新 [`CHANGELOG.md`](CHANGELOG.md) — 本节
- 更新 [`webui/VERSION_4_DEPLOYMENT.md`](webui/VERSION_4_DEPLOYMENT.md) — 同步 v2.2.1

---

## [2.2.0] — 2026-07-22

### 🎼 图标系统全面升级（Version Four：Bard 吟游诗人）

> **品牌主线确立**：吟游诗人吹笛子 — 动态、连续线条、单色流线型
> **设计哲学**：流畅的故事讲述者 — 每一次交互都是艺术旅程

#### ✨ 新增
- **SVG 三件套**：
  - `bard-flute.svg` — 主品牌图标（currentColor 自适应主题）
  - `bard-flute-continuous.svg` — 极简线稿版（FlowSpinner 动画源）
  - `bard-flute-emoji.svg` — 白底黑线版（Favicon / 文档 / 外部场景）
- **多尺寸 PNG（30 张，9 尺寸 × 3 变体 + 6 张同步到 public/）**：
  - 规格 512/256/192/128/64/48/32/24/16/12 px
  - 变体：主品牌（白底黑线）/ 透明 / 反色（黑底白线）
  - `favicon.ico` 多尺寸打包（16+32+48，Vista+ 全平台）
  - `site.webmanifest` PWA 元数据
- **BardIcon 组件**（`src/components/BardIcon.vue`）：
  - 统一接口：`<BardIcon :size="32" :variant="brand" :animated="true" />`
  - 自适应描线粗细（12-128px 全段位校准）
  - 内置飞线动画（与 FlowSpinner 同源关键帧）
  - 严格遵循 `prefers-reduced-motion`
- **图标资源管理脚本**（`webui/scripts/generate-icons.mjs`）：
  - `npm run icons:build` 一键重建全部 PNG / ICO / manifest
  - 自写 PNG-in-ICO 编码器（零依赖）
  - 4x 过采样确保 12/16px 锐利
  - 自动同步 HTML 引用尺寸到 public/
- **图标资源管理文档**（`webui/src/assets/icons/README.md`）：
  - 目录结构 / 规格对照表 / 命名规范 / 故障排查
  - 36 个资源文件全覆盖说明

#### 🎨 UI 主题深化（任务书 §2）
- **设计 token 体系重构**（`webui/src/styles/tokens.css`）：
  - 时长 token：`--duration-instant/-fast/-normal/-slow/-slower/-flow/-breath/-page`（8 级）
  - 缓动 token：`--ease-out/-in/-inout/-flow/-breath/-spring`（6 种）
  - Stagger 延迟：`--stagger-1..8`（40ms 递增）
  - Dark 模式动画节奏独立校准（呼吸略快 2200ms）
- **FlowSpinner 重写**：8 条 path 模仿吟游诗人吹笛子，stroke-dasharray + pathLength=100 归一化，staggered 120ms 延迟形成"一笔绘出又抹去"的飞线效果。
- **AppSidebar Logo 修复**：原实心圆遮盖描线（白底看不见白线）的视觉 Bug 已修复，替换为 `<BardIcon animated>`，描线在 light/dark 双模式下均清晰可见，悬停时 1.05x 脉动。
- **index.html 升级**：完整 favicon 链路（SVG → 32px PNG → 16px PNG → ICO → apple-touch-icon → OG image → msapplication-TileImage）。

#### 🛡️ 质量与生产标准
- **依赖锁定绝对版本号**（SOUL.md §A-3）：`sharp 0.33.5` 精确版本，无 `^` `~` `latest`。
- **零依赖 ICO 编码**：自写 ~30 行代码替代 to-ico CJS 包，规避 ESM 互操作风险。
- **可访问性**：全部动画支持 `prefers-reduced-motion`；BardIcon 强制 `role="img"` + `aria-label`。
- **单命令闭环**：`npm run icons:build` 幂等可重入，二次运行零差异。
- **构建验证**：`npm run build` 951ms 通过，全部 HTML 引用命中。

#### 📚 文档闭环
- `webui/VERSION_4_DEPLOYMENT.md` — 升级指南
- `webui/src/assets/icons/README.md` — 资源管理规范
- `CHANGELOG.md` — 本节

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

#!/usr/bin/env bash
# ==============================================================================
# 🧹 无人值守前端资源 / 文档 / 临时文件清理脚本（生产级 · 可回滚 · 双层日志）
# ------------------------------------------------------------------------------
# 项目：AI 测试用例生成系统（ai-test-system）
# 用途：自动识别并清理 (1) 旧版前端资源 (2) 过时文档 (3) 冗余临时文件与缓存
# 策略：
#   Tier 1 - 直接删除：纯临时/可重建文件（__pycache__、.pyc、.DS_Store、.log、
#            .pytest_cache、htmlcov、output、test-run 等）
#   Tier 2 - 隔离移动：疑似过时但可能有价值的文档/资源，移入
#            logs/cleanup-quarantine-YYYYMMDD-HHMMSS/ 目录（可回滚）
# 安全：内置绝对路径白名单，关键源码/配置/运行环境（.venv / .git / IDE 配置）
#       一律跳过；权限错误、误识别均自动跳过并记录异常，绝不中断流程
# 输出：
#   - stdout：保姆级中文提示（零技术黑话）
#   - LOG_FILE：详细技术堆栈日志（供排查，直接写入文件，不依赖 shell 重定向）
#   - REPORT_FILE：Markdown 清理报告（含路径/类型/大小/处置/状态）
# 单命令运行：bash scripts/cleanup_unattended.sh
# ==============================================================================
set -uo pipefail  # -u：未定义变量即错；-o pipefail：管道任一阶段失败即失败
                  # 不使用 -e：单文件失败不中断整体流程，由错误处理函数统一接管

# ----------------------------- 全局变量定义 -----------------------------------
# 自动定位项目根目录（脚本所在目录的上一级），避免硬编码绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 时间戳，用于隔离区目录命名与报告归档（精确到秒，避免重复运行冲突）
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DATE_HUMAN="$(date '+%Y-%m-%d %H:%M:%S')"

# 技术产物集中管理目录：日志、报告、隔离区都放在 logs/ 下
# logs/ 已在 .gitignore 中忽略，不会污染 Git 仓库，且非隐藏目录沙箱不会误清理
LOG_DIR="${ROOT_DIR}/logs"

# 隔离区目录：本次清理的"准删除"文件先搬到这里，确认无误后用户可手动彻底删除
# 放在 logs/ 下而非根目录隐藏目录，避免沙箱环境对 .gitignore 忽略隐藏目录的清理行为
QUARANTINE_DIR="${LOG_DIR}/cleanup-quarantine-${TIMESTAMP}"

# 日志与报告文件路径
LOG_FILE="${LOG_DIR}/cleanup-${TIMESTAMP}.log"
REPORT_FILE="${LOG_DIR}/cleanup-report-${TIMESTAMP}.md"

# 统计计数器：用于最终汇总输出
COUNT_DELETED=0          # Tier 1 直接删除的文件数
COUNT_QUARANTINED=0      # Tier 2 隔离移动的文件数
COUNT_SKIPPED=0          # 因保护/不存在/权限等原因跳过的文件数
COUNT_ERROR=0            # 处理过程中发生的错误数
SIZE_DELETED_BYTES=0     # 已删除文件总字节数
SIZE_QUARANTINED_BYTES=0  # 已隔离文件总字节数

# ----------------------------- 关键保护白名单 ---------------------------------
# 以下路径"绝对不可删除/移动"，任何匹配命中都自动跳过并记录
# 设计原则：保护运行环境、源代码、关键配置、IDE 配置、长期档案
PROTECTED_PATHS=(
  "${ROOT_DIR}/.venv"               # Python 虚拟环境（删除会破坏运行环境）
  "${ROOT_DIR}/.git"                 # Git 版本控制元数据
  "${ROOT_DIR}/.github"              # CI/CD 工作流
  "${ROOT_DIR}/.vscode"              # VS Code IDE 配置（用户本地设置）
  "${ROOT_DIR}/.idea"                # JetBrains IDE 配置
  "${ROOT_DIR}/.trae"                # Trae IDE 配置（沙箱保护，且为本地设置）
  "${ROOT_DIR}/core"                 # 后端核心业务源码
  "${ROOT_DIR}/web"                  # FastAPI Web 后端源码
  "${ROOT_DIR}/webui"                # 前端 Vue SPA 源码（当前前端，不可清理）
  "${ROOT_DIR}/db"                   # 数据库模型与迁移
  "${ROOT_DIR}/integrations"          # 三方集成适配器
  "${ROOT_DIR}/scripts"              # 运维脚本目录（本脚本所在）
  "${ROOT_DIR}/deploy"               # 部署配置
  "${ROOT_DIR}/examples"             # 业务示例
  "${ROOT_DIR}/uploads"              # 用户上传目录（保留 .gitkeep）
  "${ROOT_DIR}/web/uploads"           # Web 上传目录（保留 .gitkeep）
  "${ROOT_DIR}/tests"                # 测试目录（整体保护，仅清理其中具体失效文件）
  "${ROOT_DIR}/docs"                 # 文档目录（整体保护，仅清理其中具体过时文件）
  "${ROOT_DIR}/README.md"             # 项目主文档
  "${ROOT_DIR}/CHANGELOG.md"          # 变更日志
  "${ROOT_DIR}/QUICKSTART.md"         # 快速开始文档
  "${ROOT_DIR}/LICENSE"               # 开源协议
  "${ROOT_DIR}/REMOVED_FILES.md"      # 历史清理记录（需追加而非删除）
  "${ROOT_DIR}/Dockerfile"            # 容器构建文件
  "${ROOT_DIR}/docker-compose.yml"    # 容器编排
  "${ROOT_DIR}/docker-compose.postgres.yml"
  "${ROOT_DIR}/Makefile"              # 构建任务
  "${ROOT_DIR}/pyproject.toml"         # Python 项目配置
  "${ROOT_DIR}/uv.lock"               # 依赖锁定文件
  "${ROOT_DIR}/alembic.ini"            # 数据库迁移配置
  "${ROOT_DIR}/.gitignore"             # Git 忽略规则
  "${ROOT_DIR}/.gitleaks.toml"         # 密钥扫描配置
  "${ROOT_DIR}/.pre-commit-config.yaml" # 提交钩子配置
  "${ROOT_DIR}/.coveragerc"            # 覆盖率配置
  "${ROOT_DIR}/.env.example"           # 环境变量样例
  "${ROOT_DIR}/cli.py"                 # CLI 入口
  "${ROOT_DIR}/logs"                   # 日志目录（保护本次产物）
)

# ----------------------------- 日志与输出函数 ---------------------------------
# 双层可观测性：stdout 给用户看（中文保姆级），LOG_FILE 给技术排查看（详细堆栈）
# 关键设计：log_tech 直接 >> 写入 LOG_FILE，不依赖 exec 重定向，确保日志落盘

# 技术日志：写入 LOG_FILE（详细，供技术排查）+ 同步打印到终端 stderr（实时观察）
# 用法：log_tech "INFO" "详细技术描述信息"
log_tech() {
  local level="$1"
  local msg="$2"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  local line="[${ts}] [${level}] ${msg}"
  # 写入日志文件（追加模式，LOG_DIR 已在 main 开头创建）
  printf '%s\n' "${line}" >> "${LOG_FILE}" 2>/dev/null
  # 同步到终端 stderr，供实时观察（2>/dev/null 防止 LOG_FILE 不可写时报错循环）
  printf '%s\n' "${line}" >&2
}

# 用户提示：stdout 中文保姆级（零技术黑话）
# 用法：log_user "要显示给用户的中文提示"
log_user() {
  local msg="$1"
  printf '%s\n' "${msg}"
}

# 报告追加：写入 REPORT_FILE（Markdown 表格行）
# 参数：路径 | 类型 | 大小(人类可读) | 处置方式 | 状态
report_append() {
  local path="$1"
  local type="$2"
  local size="$3"
  local action="$4"
  local status="$5"
  # 路径转相对项目根的显示形式，更易读
  local rel_path="${path#${ROOT_DIR}/}"
  printf '| `%s` | %s | %s | %s | %s |\n' \
    "${rel_path}" "${type}" "${size}" "${action}" "${status}" >> "${REPORT_FILE}" 2>/dev/null
}

# 字节数转人类可读格式（KB/MB/GB），BSD 兼容
# 用法：human_size 1024 -> "1.00 KB"
human_size() {
  local bytes="$1"
  if [ "${bytes}" -ge 1073741824 ] 2>/dev/null; then
    awk -v b="${bytes}" 'BEGIN{printf "%.2f GB", b/1073741824}'
  elif [ "${bytes}" -ge 1048576 ] 2>/dev/null; then
    awk -v b="${bytes}" 'BEGIN{printf "%.2f MB", b/1048576}'
  elif [ "${bytes}" -ge 1024 ] 2>/dev/null; then
    awk -v b="${bytes}" 'BEGIN{printf "%.2f KB", b/1024}'
  else
    printf '%d B' "${bytes}" 2>/dev/null || echo "0 B"
  fi
}

# 获取文件/目录字节数（macOS BSD stat 兼容）
# 单文件用 stat -f %z；目录用 du -sk 转换
get_size_bytes() {
  local target="$1"
  if [ ! -e "${target}" ]; then
    echo 0
    return
  fi
  if [ -f "${target}" ]; then
    # macOS BSD stat：-f %z 输出文件字节数
    stat -f %z "${target}" 2>/dev/null || echo 0
  else
    # 目录：du -sk 输出 KB（含 1024-byte 块），*1024 转字节
    du -sk "${target}" 2>/dev/null | awk '{print $1 * 1024}'
  fi
}

# ----------------------------- 白名单校验函数 ---------------------------------
# 严格校验：检查路径是否落在保护白名单内（含子路径前缀匹配）
# 用于 safe_delete：批量扫描删除时，整个受保护目录树都不可触碰
# 用法：is_protected "/path/to/check" && echo "受保护，跳过"
is_protected() {
  local target="$1"
  local protected
  for protected in "${PROTECTED_PATHS[@]}"; do
    # 命中条件：目标路径等于受保护路径，或是其子路径（前缀匹配 + 斜杠分隔）
    if [ "${target}" = "${protected}" ] || \
       [[ "${target}" == "${protected}"/* ]]; then
      return 0  # 受保护
    fi
  done
  return 1  # 不在白名单，可处理
}

# 精确校验：仅检查路径是否"精确等于"白名单某一项（不包含子路径）
# 用于 safe_quarantine：隔离是人为指定的精确文件操作，应允许隔离白名单目录下的具体文件
# 例如：docs/ 在白名单中（保护整个目录不被批量删除），但 docs/PRR_SESSION_xxx.md
#       作为具体文件应允许隔离（精确操作，非批量扫描）
# 用法：is_protected_exact "/path/to/file" && echo "精确受保护，跳过"
is_protected_exact() {
  local target="$1"
  local protected
  for protected in "${PROTECTED_PATHS[@]}"; do
    # 仅精确匹配（不做前缀匹配），保护白名单中明确列出的具体文件/目录本身
    if [ "${target}" = "${protected}" ]; then
      return 0  # 精确受保护
    fi
  done
  return 1  # 不精确匹配，可处理
}

# ----------------------------- 核心清理函数 -----------------------------------
# Tier 1：直接删除（可重建的纯临时文件）
# 用法：safe_delete "/path/to/file" "文件类型描述"
safe_delete() {
  local target="$1"
  local type_desc="$2"

  # 防御 1：路径非空校验，避免误删当前目录
  if [ -z "${target}" ]; then
    log_tech "WARN" "收到空路径，跳过删除"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return
  fi

  # 防御 2：白名单校验，关键文件一律跳过
  if is_protected "${target}"; then
    log_tech "WARN" "命中保护白名单，跳过：${target}"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    report_append "${target}" "${type_desc}" "-" "跳过(受保护)" "⚠️ 保护"
    return
  fi

  # 防御 3：路径必须落在项目根目录内（避免 ../ 越界攻击）
  case "${target}" in
    "${ROOT_DIR}"/*) : ;;  # 合法：在项目根下
    *)
      log_tech "ERROR" "路径越出项目根，拒绝处理：${target}"
      COUNT_ERROR=$((COUNT_ERROR + 1))
      report_append "${target}" "${type_desc}" "-" "拒绝(越界)" "❌ 异常"
      return
      ;;
  esac

  # 防御 4：文件不存在时静默跳过（不算错误，常见于重复运行）
  if [ ! -e "${target}" ]; then
    log_tech "INFO" "文件不存在，跳过：${target}"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return
  fi

  # 记录删除前的大小，用于报告与统计
  local size_bytes
  size_bytes="$(get_size_bytes "${target}")"
  local size_human
  size_human="$(human_size "${size_bytes}")"

  # 执行删除：rm -rf 兼容文件和目录；stderr 重定向到 LOG_FILE；|| true 防止中断
  # 注意：2>> 重定向确保 rm 的错误信息进日志文件，便于排查
  if rm -rf "${target}" 2>>"${LOG_FILE}"; then
    log_tech "INFO" "已删除：${target} (${size_human})"
    COUNT_DELETED=$((COUNT_DELETED + 1))
    SIZE_DELETED_BYTES=$((SIZE_DELETED_BYTES + size_bytes))
    report_append "${target}" "${type_desc}" "${size_human}" "直接删除" "✅ 成功"
  else
    # 权限错误/文件锁定等异常 → 记录后继续
    log_tech "ERROR" "删除失败（权限/锁定）：${target}"
    COUNT_ERROR=$((COUNT_ERROR + 1))
    report_append "${target}" "${type_desc}" "${size_human}" "删除失败" "❌ 异常"
  fi
}

# Tier 2：隔离移动（疑似过时但有价值的文档/资源）
# 用法：safe_quarantine "/path/to/file" "文件类型描述"
safe_quarantine() {
  local target="$1"
  local type_desc="$2"

  # 防御 1：路径非空校验
  if [ -z "${target}" ]; then
    log_tech "WARN" "收到空路径，跳过隔离"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return
  fi

  # 防御 2：白名单校验（隔离操作使用精确校验，允许隔离白名单目录下的具体文件）
  # 设计：safe_quarantine 是人为指定的精确文件操作（非批量扫描），因此：
  #   - 目录目标：严格校验，整个受保护目录树不可隔离
  #   - 文件目标：精确校验，仅保护白名单中明确列出的文件，允许隔离白名单目录下的子文件
  if [ -d "${target}" ]; then
    # 目录：严格校验（含子路径前缀匹配），防止误隔离整个受保护目录
    if is_protected "${target}"; then
      log_tech "WARN" "目录命中保护白名单，跳过隔离：${target}"
      COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
      report_append "${target}" "${type_desc}" "-" "跳过(受保护)" "⚠️ 保护"
      return
    fi
  else
    # 文件：精确校验（仅精确匹配保护），允许隔离白名单目录下的具体过时文件
    if is_protected_exact "${target}"; then
      log_tech "WARN" "文件命中保护白名单（精确匹配），跳过隔离：${target}"
      COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
      report_append "${target}" "${type_desc}" "-" "跳过(受保护)" "⚠️ 保护"
      return
    fi
  fi

  # 防御 3：路径越界校验
  case "${target}" in
    "${ROOT_DIR}"/*) : ;;
    *)
      log_tech "ERROR" "路径越出项目根，拒绝处理：${target}"
      COUNT_ERROR=$((COUNT_ERROR + 1))
      report_append "${target}" "${type_desc}" "-" "拒绝(越界)" "❌ 异常"
      return
      ;;
  esac

  # 防御 4：文件不存在时静默跳过
  if [ ! -e "${target}" ]; then
    log_tech "INFO" "文件不存在，跳过：${target}"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return
  fi

  # 记录隔离前的大小
  local size_bytes
  size_bytes="$(get_size_bytes "${target}")"
  local size_human
  size_human="$(human_size "${size_bytes}")"

  # 计算隔离区内的目标路径：保留原相对结构，便于回滚定位
  local rel="${target#${ROOT_DIR}/}"
  local dest="${QUARANTINE_DIR}/${rel}"
  local dest_parent
  dest_parent="$(dirname "${dest}")"

  # 创建隔离目标父目录（-p 允许已存在）
  if ! mkdir -p "${dest_parent}" 2>>"${LOG_FILE}"; then
    log_tech "ERROR" "创建隔离目录失败：${dest_parent}"
    COUNT_ERROR=$((COUNT_ERROR + 1))
    report_append "${target}" "${type_desc}" "${size_human}" "隔离失败" "❌ 异常"
    return
  fi

  # 执行移动：mv -f 强制覆盖；stderr 重定向到 LOG_FILE
  if mv -f "${target}" "${dest}" 2>>"${LOG_FILE}"; then
    # 移动后立即验证目标文件存在（防止沙箱环境异常行为导致文件丢失）
    if [ -e "${dest}" ]; then
      log_tech "INFO" "已隔离：${target} -> ${dest} (${size_human})"
      COUNT_QUARANTINED=$((COUNT_QUARANTINED + 1))
      SIZE_QUARANTINED_BYTES=$((SIZE_QUARANTINED_BYTES + size_bytes))
      report_append "${target}" "${type_desc}" "${size_human}" "隔离(可回滚)" "✅ 成功"
    else
      # 移动命令返回成功但目标不存在（沙箱异常行为）→ 严重错误，记录并尝试回退
      log_tech "ERROR" "移动返回成功但目标不存在（沙箱异常）：${target} -> ${dest}"
      COUNT_ERROR=$((COUNT_ERROR + 1))
      report_append "${target}" "${type_desc}" "${size_human}" "隔离异常(文件丢失)" "❌ 异常"
    fi
  else
    log_tech "ERROR" "移动失败（权限/锁定）：${target}"
    COUNT_ERROR=$((COUNT_ERROR + 1))
    report_append "${target}" "${type_desc}" "${size_human}" "隔离失败" "❌ 异常"
  fi
}

# ----------------------------- 报告头尾函数 ----------------------------------
# 写入 Markdown 报告头部（在清理开始前调用一次）
write_report_header() {
  cat > "${REPORT_FILE}" <<EOF
# 🧹 无人值守清理报告

> **清理时间**：${DATE_HUMAN}
> **项目根目录**：\`${ROOT_DIR}\`
> **隔离区目录**：\`logs/cleanup-quarantine-${TIMESTAMP}/\`（可回滚）
> **详细日志**：\`logs/cleanup-${TIMESTAMP}.log\`

---

## 📋 详细清理清单

| 文件路径 | 类型 | 大小 | 处置方式 | 状态 |
|----------|------|------|----------|------|
EOF
}

# 写入报告尾部统计（在清理结束后调用，此时所有计数器已确定）
write_report_footer() {
  local size_del_human size_quar_human
  size_del_human="$(human_size "${SIZE_DELETED_BYTES}")"
  size_quar_human="$(human_size "${SIZE_QUARANTINED_BYTES}")"

  # 在报告末尾追加最终统计与回滚说明（直接写入已知数字）
  cat >> "${REPORT_FILE}" <<EOF

---

## 📊 清理统计汇总

| 处置方式 | 文件数 | 总大小 |
|----------|--------|--------|
| 直接删除（Tier 1） | ${COUNT_DELETED} | ${size_del_human} |
| 隔离移动（Tier 2） | ${COUNT_QUARANTINED} | ${size_quar_human} |
| 跳过（保护/不存在） | ${COUNT_SKIPPED} | - |
| 异常 | ${COUNT_ERROR} | - |

## 🔁 回滚方法

若发现误清理，可从隔离区恢复：

\`\`\`bash
# 查看隔离区内容
ls -la ${QUARANTINE_DIR}/

# 恢复某个文件（示例）
mv ${QUARANTINE_DIR}/BUGFIX_PIPELINE_START.md ${ROOT_DIR}/
\`\`\`

确认无误后可彻底删除隔离区：

\`\`\`bash
rm -rf ${QUARANTINE_DIR}/
\`\`\`

> 隔离区位于 logs/ 目录下，已被 .gitignore 忽略，不会污染 Git 仓库。

## ⚠️ 异常说明

如"异常"列 > 0，请查看详细日志 \`logs/cleanup-${TIMESTAMP}.log\` 中的 ERROR 条目。
常见原因：文件被其他进程占用、当前用户无写权限。处理方式见《常见问题 3 分钟救急指南》。
EOF
}

# ----------------------------- 清理任务定义 ----------------------------------
# 每个函数对应一类清理任务，便于维护与扩展

# 任务 1：清理 Python 字节码缓存（__pycache__ 目录 + .pyc 文件）
# 注意：严格排除 .venv 目录（虚拟环境内的缓存属于运行环境，不应清理）
clean_python_cache() {
  log_user "🧹 [1/8] 扫描 Python 缓存文件（__pycache__ / .pyc）..."
  log_tech "INFO" "开始任务 1：清理 Python 缓存（排除 .venv）"

  local file
  # find 查找 __pycache__ 目录，-prune 排除 .venv 子树（性能与正确性兼顾）
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    safe_delete "${file}" "Python 缓存目录"
  done < <(find "${ROOT_DIR}" \
              -path "${ROOT_DIR}/.venv" -prune -o \
              -path "${ROOT_DIR}/.git" -prune -o \
              -type d -name "__pycache__" -print 2>/dev/null)

  # 清理散落的 .pyc 文件（同样排除 .venv）
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    safe_delete "${file}" "Python 字节码文件"
  done < <(find "${ROOT_DIR}" \
              -path "${ROOT_DIR}/.venv" -prune -o \
              -path "${ROOT_DIR}/.git" -prune -o \
              -type f -name "*.pyc" -print 2>/dev/null)

  # 清理 .pyo 优化字节码（旧版 Python 遗留）
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    safe_delete "${file}" "Python 优化字节码"
  done < <(find "${ROOT_DIR}" \
              -path "${ROOT_DIR}/.venv" -prune -o \
              -path "${ROOT_DIR}/.git" -prune -o \
              -type f -name "*.pyo" -print 2>/dev/null)
}

# 任务 2：清理 macOS / Windows 系统垃圾文件
clean_os_junk() {
  log_user "🧹 [2/8] 扫描系统垃圾文件（.DS_Store / Thumbs.db）..."
  log_tech "INFO" "开始任务 2：清理 OS 垃圾文件"

  local file
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    safe_delete "${file}" "macOS 目录元数据"
  done < <(find "${ROOT_DIR}" \
              -path "${ROOT_DIR}/.venv" -prune -o \
              -path "${ROOT_DIR}/.git" -prune -o \
              \( -name ".DS_Store" -o -name "Thumbs.db" -o -name "._*" \) -print 2>/dev/null)
}

# 任务 3：清理工具缓存目录（仅清理可重建的工具缓存，不碰 IDE 配置）
# 注意：.vscode / .idea / .trae 是 IDE 用户配置，已加入保护白名单，此处不处理
clean_ide_caches() {
  log_user "🧹 [3/8] 扫描工具缓存（.pytest_cache / .mypy_cache / .ruff_cache 等）..."
  log_tech "INFO" "开始任务 3：清理工具缓存目录（排除 IDE 配置）"

  # 仅清理工具运行时缓存（均为可重建的临时产物）
  # IDE 配置目录（.vscode/.idea/.trae）已在保护白名单中，不会在此处处理
  local cache_dir
  for cache_dir in \
      "${ROOT_DIR}/.pytest_cache" \
      "${ROOT_DIR}/.mypy_cache" \
      "${ROOT_DIR}/.ruff_cache" \
      "${ROOT_DIR}/.codegraph" \
      "${ROOT_DIR}/.meituan-catpaw"; do
    safe_delete "${cache_dir}" "工具缓存目录"
  done
}

# 任务 4：清理覆盖率与测试输出产物（可由 pytest 重新生成）
clean_coverage_artifacts() {
  log_user "🧹 [4/8] 扫描测试覆盖率产物（htmlcov / .coverage / coverage.xml）..."
  log_tech "INFO" "开始任务 4：清理覆盖率产物"

  safe_delete "${ROOT_DIR}/htmlcov" "HTML 覆盖率报告目录"
  safe_delete "${ROOT_DIR}/.coverage" "覆盖率数据文件"
  safe_delete "${ROOT_DIR}/coverage.xml" "覆盖率 XML 报告"
}

# 任务 5：清理运行时输出目录（业务运行产生的临时数据，可重建）
clean_runtime_output() {
  log_user "🧹 [5/8] 扫描运行时输出目录（output / test-run / data）..."
  log_tech "INFO" "开始任务 5：清理运行时输出"

  # 这些目录在 .gitignore 中已显式忽略，删除不影响 Git 跟踪
  safe_delete "${ROOT_DIR}/output" "运行时输出目录"
  safe_delete "${ROOT_DIR}/test-run" "测试运行产物目录"
  safe_delete "${ROOT_DIR}/data" "运行时数据目录"
}

# 任务 6：清理日志与备份文件（根目录散落的 .log / .tmp / .bak / .swp）
clean_log_backup_files() {
  log_user "🧹 [6/8] 扫描散落日志与备份文件（.log / .tmp / .bak / .swp）..."
  log_tech "INFO" "开始任务 6：清理日志与备份文件"

  # 清理散落在项目各处的临时日志/备份
  # 注意：logs/ 目录本身受保护（在白名单中），不会清理本次清理产生的报告
  local file
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    # 跳过本次清理产生的 logs 目录内容
    case "${file}" in
      "${ROOT_DIR}/logs"/*) continue ;;
    esac
    safe_delete "${file}" "日志/备份文件"
  done < <(find "${ROOT_DIR}" \
              -path "${ROOT_DIR}/.venv" -prune -o \
              -path "${ROOT_DIR}/.git" -prune -o \
              -path "${ROOT_DIR}/logs" -prune -o \
              \( -name "*.log" -o -name "*.tmp" -o -name "*.bak" \
                 -o -name "*.swp" -o -name "*.swo" -o -name "*~" \) -print 2>/dev/null)
}

# 任务 7：清理旧版前端资源残留（legacy 目录、旧版构建产物）
# 注意：webui/ 是当前前端（Vue SPA），已在白名单中严格保护，不会被清理
#       此处仅清理已被 .gitignore 忽略的可重建产物（如 dist 构建输出）
clean_legacy_frontend() {
  log_user "🧹 [7/8] 扫描旧版前端资源残留（legacy 目录 / 构建产物）..."
  log_tech "INFO" "开始任务 7：清理旧版前端资源残留（webui/ 受保护不处理）"

  # legacy 目录（REMOVED_FILES.md 已记录历史清理，此处兜底扫描）
  safe_delete "${ROOT_DIR}/legacy" "旧版前端模板目录"

  # webui/dist 构建产物（已被 .gitignore 忽略，每次 build 重建）
  # 注意：webui/ 源码本身在保护白名单中，不会被删除
  safe_delete "${ROOT_DIR}/webui/dist" "前端构建产物目录"
}

# 任务 8：隔离疑似过时的文档与资源（移入隔离区，可回滚）
# 设计原则：仅隔离"明确失效"的文档，长期档案（PRR/优化报告）保留供合规追溯
# 注意：直接调用 safe_quarantine（内部有文件存在性检查），不外层包裹 if
quarantine_obsolete_docs() {
  log_user "🧹 [8/8] 隔离疑似过时的文档与资源（移入隔离区，可回滚）..."
  log_tech "INFO" "开始任务 8：隔离过时文档"

  # 8.1 test_requirement.md：.gitignore 显式忽略的临时测试需求草稿
  safe_quarantine "${ROOT_DIR}/test_requirement.md" "临时测试需求草稿"

  # 8.2 BUGFIX_PIPELINE_START.md：Bug 修复记录，引用的 web/templates/index.html
  #     旧版 HTMX 模板已不存在，前端架构已变更，记录失效
  safe_quarantine "${ROOT_DIR}/BUGFIX_PIPELINE_START.md" "失效 Bug 修复记录"

  # 8.3 docs/PRR_SESSION_2025_07_22.md：日期异常（2025-07-22，与项目当前 2026-07
  #     不符），且为带日期的阶段性会话快照，已无追溯价值
  safe_quarantine "${ROOT_DIR}/docs/PRR_SESSION_2025_07_22.md" "过时会话记录"

  # 8.4 tests/test_error_toast_handling.js：前端 HTMX 时代的错误提示测试，
  #     前端已迁 Vue 后整体移除，该 JS 测试已无运行环境
  safe_quarantine "${ROOT_DIR}/tests/test_error_toast_handling.js" "失效前端测试"
}

# ----------------------------- 主流程函数 ------------------------------------
main() {
  # 步骤 1：准备日志与隔离区目录（logs/ 集中管理所有技术产物）
  if ! mkdir -p "${LOG_DIR}" 2>/dev/null; then
    printf '[错误-01] 无法创建日志目录 %s，请检查项目根目录写权限\n' "${LOG_DIR}"
    exit 1
  fi

  # 步骤 2：初始化日志文件（创建空文件，确保后续 >> 追加可用）
  : > "${LOG_FILE}"

  # 步骤 3：打印启动横幅（用户友好提示）
  log_user "============================================================"
  log_user "🧹 AI 测试系统 · 无人值守清理任务启动"
  log_user "============================================================"
  log_user "📁 项目目录：${ROOT_DIR}"
  log_user "📝 详细日志：${LOG_FILE}"
  log_user "📋 清理报告：${REPORT_FILE}"
  log_user "📦 隔离目录：${QUARANTINE_DIR}"
  log_user "------------------------------------------------------------"
  log_user "💡 提示：本脚本采用'隔离区'机制，疑似过时文件会先搬到隔离区，"
  log_user "        确认无误后可手动删除；纯临时文件直接删除。"
  log_user "------------------------------------------------------------"

  log_tech "INFO" "============================================================"
  log_tech "INFO" "清理任务启动：时间=${DATE_HUMAN} ROOT_DIR=${ROOT_DIR}"
  log_tech "INFO" "LOG_FILE=${LOG_FILE} REPORT_FILE=${REPORT_FILE}"
  log_tech "INFO" "QUARANTINE_DIR=${QUARANTINE_DIR}"
  log_tech "INFO" "保护白名单项数：${#PROTECTED_PATHS[@]}"

  # 步骤 4：写入报告头部
  write_report_header

  # 步骤 5：依次执行 8 个清理任务
  # 每个任务独立，互不阻塞；单个任务失败不影响后续任务
  clean_python_cache
  clean_os_junk
  clean_ide_caches
  clean_coverage_artifacts
  clean_runtime_output
  clean_log_backup_files
  clean_legacy_frontend
  quarantine_obsolete_docs

  # 步骤 6：写入报告尾部统计
  write_report_footer

  # 步骤 7：打印最终汇总（用户友好提示）
  log_user "------------------------------------------------------------"
  log_user "✅ 清理任务完成！"
  log_user "------------------------------------------------------------"
  log_user "📊 结果汇总："
  printf '   • 直接删除：%d 个文件，共 %s\n' \
    "${COUNT_DELETED}" "$(human_size "${SIZE_DELETED_BYTES}")"
  printf '   • 隔离移动：%d 个文件，共 %s\n' \
    "${COUNT_QUARANTINED}" "$(human_size "${SIZE_QUARANTINED_BYTES}")"
  printf '   • 跳过：%d 个（受保护或不存在）\n' "${COUNT_SKIPPED}"
  printf '   • 异常：%d 个\n' "${COUNT_ERROR}"
  log_user "------------------------------------------------------------"
  log_user "📋 详细报告：${REPORT_FILE}"
  log_user "📝 技术日志：${LOG_FILE}"
  if [ "${COUNT_QUARANTINED}" -gt 0 ]; then
    log_user "📦 隔离区已创建：${QUARANTINE_DIR}"
    log_user "💡 确认无误后可彻底删除隔离区：rm -rf ${QUARANTINE_DIR}"
  fi
  if [ "${COUNT_ERROR}" -gt 0 ]; then
    log_user "⚠️ 有 ${COUNT_ERROR} 个文件处理异常，详见日志中的 [ERROR] 条目。"
    log_user "   常见原因：文件被其他程序占用、当前用户无写权限。"
  fi
  log_user "============================================================"

  # 步骤 8：退出码（有异常返回 1，否则 0），便于 CI/CD 集成判断
  if [ "${COUNT_ERROR}" -gt 0 ]; then
    exit 1
  fi
  exit 0
}

# 脚本入口：仅在被直接执行时运行 main（被 source 时不自动执行）
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi

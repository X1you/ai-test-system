#!/bin/bash
# =========================================================================
# AI Agent 自动化测试套件 - 无人值守启动脚本
# =========================================================================
#
# 功能：
#   1. 环境自动检查与准备
#   2. 依赖安装验证
#   3. 启动测试编排器
#   4. 测试完成后自动生成报告
#   5. 异常退出时保留日志和部分结果
#
# 使用方式：
#   ./run_ai_agent_suite.sh                          # 默认配置运行
#   ./run_ai_agent_suite.sh --modules pipeline,web_api  # 指定模块
#   ./run_ai_agent_suite.sh --timeout 90                # 指定超时
#   ./run_ai_agent_suite.sh --output ./custom_reports   # 指定输出目录
#   ./run_ai_agent_suite.sh --no-monitor                # 跳过资源监控
#   ./run_ai_agent_suite.sh --quick                     # 快速模式(仅核心测试)
#
# 退出码：
#   0 - 全部测试通过
#   1 - 存在测试失败或错误
#   2 - 环境准备失败
#   3 - 测试执行异常中断
# =========================================================================

set -euo pipefail

# ─── 配置 ───

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
LOG_DIR="$PROJECT_ROOT/output/ai_agent_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/suite_execution_${TIMESTAMP}.log"

# 默认参数
MODULES="pipeline,web_api,data"
TIMEOUT=120
OUTPUT_DIR="$LOG_DIR"
FAIL_FAST=""
QUIET=""
SKIP_MONITOR=""

# ─── 颜色输出 ───

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%H:%M:%S') $*" | tee -a "$LOG_FILE"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%H:%M:%S') $*" | tee -a "$LOG_FILE"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S') $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $*" | tee -a "$LOG_FILE"; }

# ─── 参数解析 ───

while [[ $# -gt 0 ]]; do
    case $1 in
        --modules|-m)
            MODULES="$2"
            shift 2
            ;;
        --timeout|-t)
            TIMEOUT="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_DIR="$2"
            LOG_DIR="$OUTPUT_DIR"
            LOG_FILE="$LOG_DIR/suite_execution_${TIMESTAMP}.log"
            shift 2
            ;;
        --fail-fast)
            FAIL_FAST="--fail-fast"
            shift
            ;;
        --quiet|-q)
            QUIET="--quiet"
            shift
            ;;
        --no-monitor)
            SKIP_MONITOR="true"
            shift
            ;;
        --quick)
            MODULES="pipeline,web_api"
            TIMEOUT=45
            shift
            ;;
        --help|-h)
            echo "AI Agent 自动化测试套件 - 无人值守启动脚本"
            echo ""
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --modules, -m MODULES    指定测试模块 (默认: pipeline,web_api,data)"
            echo "  --timeout, -t MINUTES    总超时时间(分钟) (默认: 120)"
            echo "  --output, -o DIR         报告输出目录 (默认: ./output/ai_agent_reports)"
            echo "  --fail-fast              首个失败时立即终止"
            echo "  --quiet, -q              减少输出"
            echo "  --no-monitor             跳过资源监控"
            echo "  --quick                  快速模式 (核心模块, 45分钟超时)"
            echo "  --help, -h               显示此帮助"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 2
            ;;
    esac
done

# ─── 准备工作 ───

mkdir -p "$LOG_DIR"
echo "" > "$LOG_FILE"

echo ""
echo "========================================================================="
echo "  AI Agent 自动化测试套件 v1.0.0"
echo "  项目: AI 测试用例生成系统"
echo "  启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================================="
echo ""
echo "  执行模块:  $MODULES"
echo "  超时限制:  ${TIMEOUT} 分钟"
echo "  输出目录:  $OUTPUT_DIR"
echo "  日志文件:  $LOG_FILE"
echo ""

# ─── 1. 环境检查 ───

log_info "========== 阶段 1/5: 环境检查 =========="

# 检查 Python
if [ ! -f "$PYTHON_BIN" ]; then
    log_error "Python 虚拟环境未找到: $PYTHON_BIN"
    log_info "尝试创建虚拟环境..."
    python3 -m venv "$VENV_DIR" || {
        log_error "无法创建虚拟环境，请确保 Python 3.11+ 已安装"
        exit 2
    }
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1)
log_ok "Python: $PYTHON_VERSION"

# 检查关键依赖
log_info "检查关键依赖..."
DEPS_OK=true
for dep in pytest fastapi sqlalchemy openpyxl; do
    if "$PYTHON_BIN" -c "import $dep" 2>/dev/null; then
        log_ok "  $dep: 已安装"
    else
        log_warn "  $dep: 未安装"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = false ]; then
    log_info "正在安装缺失依赖..."
    "$PIP_BIN" install pytest fastapi sqlalchemy openpyxl psutil pyyaml 2>&1 | tee -a "$LOG_FILE" || {
        log_error "依赖安装失败"
        exit 2
    }
    log_ok "依赖安装完成"
fi

# 检查 psutil (资源监控)
if "$PYTHON_BIN" -c "import psutil" 2>/dev/null; then
    log_ok "psutil (资源监控): 已安装"
else
    log_warn "psutil 未安装，资源监控功能将不可用"
    SKIP_MONITOR="true"
fi

# 检查项目文件
log_info "检查项目文件完整性..."
REQUIRED_FILES=(
    "tests/ai_agent_suite/orchestrator.py"
    "tests/ai_agent_suite/monitor.py"
    "tests/ai_agent_suite/reporter.py"
    "tests/ai_agent_suite/conftest.py"
    "tests/ai_agent_suite/module_pipeline/test_pipeline_e2e.py"
    "tests/ai_agent_suite/module_web_api/test_api_services.py"
    "tests/ai_agent_suite/module_data/test_data_integration.py"
    "core/pipeline.py"
    "core/llm_client.py"
    "core/config_loader.py"
)

ALL_FILES_OK=true
for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$f" ]; then
        log_ok "  $f"
    else
        log_error "  $f: 文件不存在"
        ALL_FILES_OK=false
    fi
done

if [ "$ALL_FILES_OK" = false ]; then
    log_error "关键文件缺失，请检查项目结构"
    exit 2
fi

# 检查 LLM API Key
if [ -n "${LLM_API_KEY:-}" ]; then
    log_ok "LLM_API_KEY: 已设置 (${LLM_API_KEY:0:8}...)"
else
    log_warn "LLM_API_KEY 未设置，AI 相关测试将使用 Mock 模式"
    export LLM_API_KEY="sk-test-dummy-for-agent-suite"
fi

echo ""

# ─── 2. 环境准备 ───

log_info "========== 阶段 2/5: 环境准备 =========="

# 清理旧的测试数据
log_info "清理旧的测试输出..."
rm -rf "$OUTPUT_DIR"/monitor 2>/dev/null || true
rm -rf "$OUTPUT_DIR"/reports 2>/dev/null || true
rm -f "$OUTPUT_DIR"/raw_results.json 2>/dev/null || true
log_ok "清理完成"

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/monitor"
mkdir -p "$OUTPUT_DIR/reports"

# 初始化数据库
log_info "初始化数据库..."
"$PYTHON_BIN" -c "
from db.session import init_db
init_db()
print('数据库初始化完成')
" 2>&1 | tee -a "$LOG_FILE" || {
    log_warn "数据库初始化有警告，但将继续执行"
}

log_ok "环境准备完成"
echo ""

# ─── 3. 测试套件验证 ───

log_info "========== 阶段 3/5: 测试套件验证 =========="

"$PYTHON_BIN" "$PROJECT_ROOT/tests/ai_agent_suite/verify_suite.py" 2>&1 | tee -a "$LOG_FILE"
VERIFY_EXIT=$?

if [ $VERIFY_EXIT -ne 0 ]; then
    log_warn "测试套件验证有警告，将继续执行测试"
else
    log_ok "测试套件验证通过"
fi
echo ""

# ─── 4. 执行测试 ───

log_info "========== 阶段 4/5: 执行自动化测试 =========="
log_info "预计执行时间: 60+ 分钟"
log_info "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

START_TIME=$(date +%s)

# 构建命令
CMD=("$PYTHON_BIN" "-m" "tests.ai_agent_suite.orchestrator"
    "--output" "$OUTPUT_DIR"
    "--modules" "$MODULES"
    "--timeout" "$TIMEOUT"
)

if [ -n "$FAIL_FAST" ]; then
    CMD+=("$FAIL_FAST")
fi
if [ -n "$QUIET" ]; then
    CMD+=("$QUIET")
fi

log_info "执行命令: ${CMD[*]}"

# 执行测试
EXIT_CODE=0
"${CMD[@]}" 2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_MIN=$((ELAPSED / 60))
ELAPSED_SEC=$((ELAPSED % 60))

echo ""
log_info "测试执行完成"
log_info "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
log_info "总耗时: ${ELAPSED_MIN} 分 ${ELAPSED_SEC} 秒"
echo ""

# ─── 5. 结果处理 ───

log_info "========== 阶段 5/5: 结果处理与报告生成 =========="

# 检查报告文件
REPORT_DIR="$OUTPUT_DIR/reports"
if [ -d "$REPORT_DIR" ]; then
    log_info "报告文件列表:"
    for f in "$REPORT_DIR"/*; do
        if [ -f "$f" ]; then
            FNAME=$(basename "$f")
            FSIZE=$(du -h "$f" | cut -f1)
            log_info "  $FNAME ($FSIZE)"
        fi
    done
else
    log_warn "报告目录不存在: $REPORT_DIR"
fi

# 检查监控数据
MONITOR_DIR="$OUTPUT_DIR/monitor"
if [ -f "$MONITOR_DIR/resource_summary.json" ]; then
    log_ok "资源监控数据已生成"
    # 提取关键指标
    "$PYTHON_BIN" -c "
import json
with open('$MONITOR_DIR/resource_summary.json') as f:
    data = json.load(f)
cpu = data.get('cpu', {})
mem = data.get('memory', {})
proc = data.get('process', {})
print(f'  CPU 平均: {cpu.get(\"avg_percent\", \"N/A\")}%, 峰值: {cpu.get(\"max_percent\", \"N/A\")}%')
print(f'  内存平均: {mem.get(\"avg_percent\", \"N/A\")}%, 峰值: {mem.get(\"max_percent\", \"N/A\")}%')
print(f'  进程 RSS 峰值: {proc.get(\"max_rss_mb\", \"N/A\")} MB')
print(f'  采样次数: {data.get(\"samples\", 0)}')
" 2>/dev/null || true
fi

# 检查原始结果
if [ -f "$OUTPUT_DIR/raw_results.json" ]; then
    log_ok "原始结果数据已保存"
    # 提取关键统计
    "$PYTHON_BIN" -c "
import json
with open('$OUTPUT_DIR/raw_results.json') as f:
    data = json.load(f)
summary = data.get('summary', {})
print(f'  总用例: {summary.get(\"total\", 0)}')
print(f'  通过: {summary.get(\"passed\", 0)}')
print(f'  失败: {summary.get(\"failed\", 0)}')
print(f'  通过率: {summary.get(\"pass_rate\", 0)}%')
print(f'  耗时: {summary.get(\"total_duration_minutes\", 0)} 分钟')
" 2>/dev/null || true
fi

# 生成执行摘要
SUMMARY_FILE="$OUTPUT_DIR/execution_summary_${TIMESTAMP}.txt"
{
    echo "=============================================="
    echo "  AI Agent 自动化测试套件 - 执行摘要"
    echo "=============================================="
    echo ""
    echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "执行模块: $MODULES"
    echo "超时限制: ${TIMEOUT} 分钟"
    echo "实际耗时: ${ELAPSED_MIN} 分 ${ELAPSED_SEC} 秒"
    echo "退出码:   $EXIT_CODE"
    echo ""
    echo "报告目录: $OUTPUT_DIR"
    echo "日志文件: $LOG_FILE"
    echo ""
} > "$SUMMARY_FILE"

log_ok "执行摘要已保存: $SUMMARY_FILE"
echo ""

# ─── 最终汇总 ───

echo "========================================================================="
echo "  测试套件执行完成"
echo "========================================================================="
echo ""
echo "  总耗时:     ${ELAPSED_MIN} 分 ${ELAPSED_SEC} 秒"
echo "  退出码:     $EXIT_CODE"
echo "  报告目录:   $OUTPUT_DIR"
echo "  日志文件:   $LOG_FILE"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "  状态:       ${GREEN}全部通过${NC}"
    echo ""
    echo "========================================================================="
    exit 0
elif [ $EXIT_CODE -eq 1 ]; then
    echo -e "  状态:       ${RED}存在失败或错误${NC}"
    echo "  请检查报告目录中的详细结果"
    echo ""
    echo "========================================================================="
    exit 1
else
    echo -e "  状态:       ${RED}执行异常${NC}"
    echo "  请检查日志文件: $LOG_FILE"
    echo ""
    echo "========================================================================="
    exit 3
fi
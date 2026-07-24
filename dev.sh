#!/bin/bash
# =========================================================================
# AI 测试用例生成系统 — 一键启动前后端开发服务器
# =========================================================================
#
# 功能：
#   • 同时拉起 FastAPI 后端 (:8080) + Vite 前端 (:5173)
#   • 自动检查 .venv / node_modules，缺失时提示安装
#   • 后台运行，PID + 日志落盘到 logs/
#   • 支持 start | stop | restart | status | logs
#
# 用法：
#   ./dev.sh                # 等同于 start（前台输出，Ctrl-C 退出两服务）
#   ./dev.sh start          # 后台启动
#   ./dev.sh stop           # 停止
#   ./dev.sh restart        # 重启
#   ./dev.sh status         # 查看运行状态
#   ./dev.sh logs           # 查看后端日志（tail -f）
#   ./dev.sh logs frontend  # 查看前端日志
#
# 端口：
#   后端 8080  — FastAPI (web.app:app)
#   前端 5173  — Vite dev server，/api /health 代理到 8080
# =========================================================================

set -euo pipefail

# ─── 路径与常量 ───

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
WEBUI_DIR="$PROJECT_ROOT/webui"
LOG_DIR="$PROJECT_ROOT/logs"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

BACKEND_HOST="127.0.0.1"
BACKEND_PORT=8080
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT=5173

# ─── 颜色 ───

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── 依赖检查 ───

check_deps() {
    local missing=false

    if [ ! -f "$PYTHON_BIN" ]; then
        err "Python 虚拟环境未找到: $VENV_DIR"
        info "请运行: uv venv .venv --python 3.11 && uv pip install -e \".[dev-all]\""
        missing=true
    fi

    if [ ! -d "$WEBUI_DIR/node_modules" ]; then
        err "前端依赖未安装: $WEBUI_DIR/node_modules"
        info "请运行: cd webui && npm install"
        missing=true
    fi

    if [ "$missing" = true ]; then
        exit 1
    fi
}

# ─── PID 工具 ───

is_running() {
    local pid_file="$1"
    [ -f "$pid_file" ] || return 1
    local pid
    pid=$(cat "$pid_file" 2>/dev/null) || return 1
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

backend_running()  { is_running "$BACKEND_PID_FILE"; }
frontend_running() { is_running "$FRONTEND_PID_FILE"; }

port_in_use() {
    local port="$1"
    lsof -i :"$port" -P -n 2>/dev/null | grep -q LISTEN
}

# ─── 启动 ───

start_backend() {
    if backend_running; then
        warn "后端已在运行 (PID $(cat "$BACKEND_PID_FILE"))"
        return 0
    fi

    if port_in_use "$BACKEND_PORT" && ! backend_running; then
        err "端口 $BACKEND_PORT 被其他进程占用（非本脚本启动）："
        lsof -i :"$BACKEND_PORT" -P -n 2>/dev/null | grep LISTEN >&2 || true
        err "请先释放该端口或修改 BACKEND_PORT"
        exit 1
    fi

    info "启动后端 FastAPI → http://${BACKEND_HOST}:${BACKEND_PORT}"
    cd "$PROJECT_ROOT"
    nohup "$PYTHON_BIN" -m uvicorn web.app:app \
        --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
        > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$BACKEND_PID_FILE"

    # 等待就绪（最长 15 秒）
    local i
    for i in $(seq 1 30); do
        if port_in_use "$BACKEND_PORT"; then
            ok "后端已就绪 (PID $pid)"
            return 0
        fi
        # 检查进程是否已退出
        if ! kill -0 "$pid" 2>/dev/null; then
            err "后端启动失败，进程已退出"
            err "--- 日志尾部 ---"
            tail -20 "$BACKEND_LOG" >&2 || true
            rm -f "$BACKEND_PID_FILE"
            exit 1
        fi
        sleep 0.5
    done
    warn "后端就绪检测超时（15s），请检查日志: $BACKEND_LOG"
}

start_frontend() {
    if frontend_running; then
        warn "前端已在运行 (PID $(cat "$FRONTEND_PID_FILE"))"
        return 0
    fi

    if port_in_use "$FRONTEND_PORT" && ! frontend_running; then
        err "端口 $FRONTEND_PORT 被其他进程占用（非本脚本启动）："
        lsof -i :"$FRONTEND_PORT" -P -n 2>/dev/null | grep LISTEN
        err "请先释放该端口或修改 FRONTEND_PORT"
        exit 1
    fi

    info "启动前端 Vite → http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    cd "$WEBUI_DIR"
    nohup npx vite --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
        > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRONTEND_PID_FILE"

    # 等待就绪（最长 15 秒）
    local i
    for i in $(seq 1 30); do
        if port_in_use "$FRONTEND_PORT"; then
            ok "前端已就绪 (PID $pid)"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            err "前端启动失败，进程已退出"
            err "--- 日志尾部 ---"
            tail -20 "$FRONTEND_LOG" >&2 || true
            rm -f "$FRONTEND_PID_FILE"
            exit 1
        fi
        sleep 0.5
    done
    warn "前端就绪检测超时（15s），请检查日志: $FRONTEND_LOG"
}

do_start() {
    check_deps
    mkdir -p "$LOG_DIR"
    echo ""
    echo "========================================================================="
    echo "  AI 测试用例生成系统 — 开发服务器"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================================================="
    echo ""
    start_backend
    start_frontend
    echo ""
    ok "全部就绪！"
    echo ""
    echo "    后端 API :  http://${BACKEND_HOST}:${BACKEND_PORT}"
    echo "    前端页面 :  http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    echo ""
    echo "    后端日志 :  $BACKEND_LOG"
    echo "    前端日志 :  $FRONTEND_LOG"
    echo "    停止服务 :  ./dev.sh stop"
    echo ""
}

# ─── 停止 ───

stop_pid() {
    local name="$1" pid_file="$2"
    if ! is_running "$pid_file"; then
        warn "$name 未在运行"
        rm -f "$pid_file" 2>/dev/null || true
        return 0
    fi
    local pid
    pid=$(cat "$pid_file")
    info "停止 $name (PID $pid) ..."
    kill "$pid" 2>/dev/null || true
    local i
    for i in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
        warn "$name 未在 5s 内退出，发送 SIGKILL"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
    ok "$name 已停止"
}

do_stop() {
    echo ""
    stop_pid "后端" "$BACKEND_PID_FILE"
    stop_pid "前端" "$FRONTEND_PID_FILE"
    echo ""
}

# ─── 状态 ───

do_status() {
    echo ""
    echo "========================================================================="
    echo "  开发服务器状态"
    echo "========================================================================="
    echo ""

    local b_pid="-" f_pid="-"
    if backend_running; then
        b_pid=$(cat "$BACKEND_PID_FILE")
        printf "  后端  %-6s  ${GREEN}● 运行中${NC}    http://%s:%s\n" "$b_pid" "$BACKEND_HOST" "$BACKEND_PORT"
    else
        printf "  后端  %-6s  ${RED}○ 未运行${NC}\n" "$b_pid"
    fi

    if frontend_running; then
        f_pid=$(cat "$FRONTEND_PID_FILE")
        printf "  前端  %-6s  ${GREEN}● 运行中${NC}    http://%s:%s\n" "$f_pid" "$FRONTEND_HOST" "$FRONTEND_PORT"
    else
        printf "  前端  %-6s  ${RED}○ 未运行${NC}\n" "$f_pid"
    fi
    echo ""
}

# ─── 日志 ───

do_logs() {
    local target="${1:-backend}"
    case "$target" in
        backend|be|b)
            info "追踪后端日志: $BACKEND_LOG (Ctrl-C 退出)"
            tail -f "$BACKEND_LOG"
            ;;
        frontend|fe|f)
            info "追踪前端日志: $FRONTEND_LOG (Ctrl-C 退出)"
            tail -f "$FRONTEND_LOG"
            ;;
        *)
            err "未知日志目标: $target (可选: backend | frontend)"
            exit 1
            ;;
    esac
}

# ─── 帮助 ───

do_help() {
    cat <<'EOF'

  AI 测试用例生成系统 — 开发服务器一键启动脚本

  用法:
    ./dev.sh                 前台启动前后端（Ctrl-C 同时退出，默认）
    ./dev.sh start           后台启动
    ./dev.sh stop            停止前后端
    ./dev.sh restart         重启前后端
    ./dev.sh status          查看运行状态
    ./dev.sh logs [target]   追踪日志 (backend | frontend，默认 backend)
    ./dev.sh fg              前台启动（等同无参数）

  端口:
    后端 8080  — FastAPI
    前端 5173  — Vite (代理 /api /health → 8080)

  日志位置:
    logs/backend.log
    logs/frontend.log

EOF
}

# ─── 前台模式（Ctrl-C 同时退出） ───

do_foreground() {
    check_deps
    mkdir -p "$LOG_DIR"

    # 如果已在运行，先提示
    if backend_running || frontend_running; then
        warn "检测到已有实例在运行，请先执行 ./dev.sh stop"
        do_status
        exit 1
    fi

    echo ""
    echo "========================================================================="
    echo "  AI 测试用例生成系统 — 开发服务器（前台模式）"
    echo "  按 Ctrl-C 退出前后端"
    echo "========================================================================="
    echo ""

    cd "$PROJECT_ROOT"
    nohup "$PYTHON_BIN" -m uvicorn web.app:app \
        --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
        > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

    cd "$WEBUI_DIR"
    nohup npx vite --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
        > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

    # 捕获退出信号，清理子进程
    cleanup() {
        echo ""
        info "收到退出信号，正在停止服务 ..."
        kill "$BACKEND_PID" 2>/dev/null || true
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
        rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
        ok "已退出"
        exit 0
    }
    trap cleanup SIGINT SIGTERM

    # 等待两个服务就绪
    info "启动后端 (PID $BACKEND_PID) ..."
    for i in $(seq 1 30); do
        port_in_use "$BACKEND_PORT" && break
        kill -0 "$BACKEND_PID" 2>/dev/null || { err "后端启动失败"; tail -20 "$BACKEND_LOG" >&2; exit 1; }
        sleep 0.5
    done
    ok "后端就绪 → http://${BACKEND_HOST}:${BACKEND_PORT}"

    info "启动前端 (PID $FRONTEND_PID) ..."
    for i in $(seq 1 30); do
        port_in_use "$FRONTEND_PORT" && break
        kill -0 "$FRONTEND_PID" 2>/dev/null || { err "前端启动失败"; tail -20 "$FRONTEND_LOG" >&2; exit 1; }
        sleep 0.5
    done
    ok "前端就绪 → http://${FRONTEND_HOST}:${FRONTEND_PORT}"

    echo ""
    ok "全部就绪！打开浏览器: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    echo "    Ctrl-C 退出  |  实时日志: tail -f $BACKEND_LOG"
    echo ""

    # 挂起，等待信号
    wait
}

# ─── 入口 ───

if [ $# -eq 0 ]; then
    do_foreground
    exit 0
fi

case "$1" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_stop
        sleep 1
        do_start
        ;;
    status)
        do_status
        ;;
    logs)
        do_logs "${2:-backend}"
        ;;
    fg)
        do_foreground
        ;;
    help|-h|--help)
        do_help
        ;;
    *)
        err "未知命令: $1"
        do_help
        exit 1
        ;;
esac

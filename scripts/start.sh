#!/bin/bash

# Mystery Agents - 本地演示版启动脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/.pids"
BACKEND_PYTHON_DEFAULT="/opt/anaconda3/envs/scienv/bin/python"
BACKEND_PYTHON="${BACKEND_PYTHON:-$BACKEND_PYTHON_DEFAULT}"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Mystery Agents 本地演示版${NC}"
echo -e "${BLUE}========================================${NC}"
echo

if [ ! -x "$BACKEND_PYTHON" ]; then
    echo -e "${YELLOW}未找到后端 Python: $BACKEND_PYTHON${NC}"
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo -e "${YELLOW}未找到 Node.js，请先安装 Node.js 18+${NC}"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "${YELLOW}提示: 未发现 backend/.env，可参考 backend/.env.example 创建${NC}"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}前端依赖未安装，请先在 frontend 目录执行 npm install${NC}"
    exit 1
fi

if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "${YELLOW}未发现 backend/.venv，建议先使用 uv 创建并安装依赖${NC}"
fi

echo -e "${BLUE}启动后端服务...${NC}"
cd "$BACKEND_DIR"
"$BACKEND_PYTHON" main.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo -e "${BLUE}等待后端就绪...${NC}"
BACKEND_READY=0
for _ in {1..30}; do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
    echo -e "${YELLOW}后端未在 30 秒内就绪，请查看日志: $LOG_DIR/backend.log${NC}"
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    exit 1
fi

echo -e "${BLUE}启动前端服务...${NC}"
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

echo
echo -e "${GREEN}服务已启动${NC}"
echo -e "后端 API: ${BLUE}http://localhost:8000${NC}"
echo -e "前端应用: ${BLUE}http://localhost:5173${NC}"
echo -e "日志目录: ${YELLOW}$LOG_DIR${NC}"
echo -e "停止服务: ${YELLOW}./scripts/stop.sh${NC}"

auto_stop() {
    echo
    echo -e "${YELLOW}正在停止服务...${NC}"
    if [ -f "$PID_FILE" ]; then
        while read -r pid; do
            if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
                kill "$pid" >/dev/null 2>&1 || true
            fi
        done < <(tr ' ' '\n' < "$PID_FILE")
        rm -f "$PID_FILE"
    fi
}

trap auto_stop INT TERM
wait

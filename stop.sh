#!/bin/bash

# Undercover AI Sandbox - 停止本地演示版服务

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT_DIR/.pids"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}正在停止 Undercover AI Sandbox 服务...${NC}"

if [ -f "$PID_FILE" ]; then
    while read -r pid; do
        if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
            echo "已停止进程 $pid"
        fi
    done < <(tr ' ' '\n' < "$PID_FILE")
    rm -f "$PID_FILE"
fi

pkill -f "python3 main.py" >/dev/null 2>&1 || true
pkill -f "uvicorn.*main:app" >/dev/null 2>&1 || true
pkill -f "vite" >/dev/null 2>&1 || true

echo -e "${GREEN}所有服务已停止${NC}"

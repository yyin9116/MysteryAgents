#!/bin/bash
# 本地演示版验证脚本
# 说明：该脚本不是完整 E2E，仅用于快速验证后端可启动以及两个集成脚本可运行。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
INTEGRATION_TEST_DIR="$SCRIPT_DIR/tests/integration"
BACKEND_PYTHON_DEFAULT="/opt/anaconda3/envs/scienv/bin/python"
BACKEND_PYTHON="${BACKEND_PYTHON:-$BACKEND_PYTHON_DEFAULT}"

RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
BLUE='[0;34m'
NC='[0m'
BACKEND_PID=""

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}端口 $port 已被占用${NC}"
        return 1
    fi
    return 0
}

start_backend() {
    echo -e "${BLUE}启动后端服务...${NC}"
    if ! check_port 8000; then
        echo -e "${RED}请先释放端口 8000${NC}"
        exit 1
    fi

    cd "$BACKEND_DIR"
    "$BACKEND_PYTHON" main.py > /tmp/test_backend.log 2>&1 &
    BACKEND_PID=$!

    for _ in {1..30}; do
        if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
            echo -e "${GREEN}后端启动成功${NC}"
            return 0
        fi
        sleep 1
    done

    echo -e "${RED}后端启动超时${NC}"
    exit 1
}

stop_backend() {
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
        wait "$BACKEND_PID" >/dev/null 2>&1 || true
    fi
}

run_python_test() {
    local label=$1
    local script=$2
    echo -e "${BLUE}运行: $label${NC}"
    cd "$SCRIPT_DIR"
    if env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
        "$BACKEND_PYTHON" "$script"; then
        echo -e "${GREEN}$label 通过${NC}"
        return 0
    fi
    echo -e "${RED}$label 失败${NC}"
    return 1
}

main() {
    trap stop_backend EXIT INT TERM
    start_backend

    local passed=0
    local failed=0

    if run_python_test "狼人杀集成脚本" "$INTEGRATION_TEST_DIR/test_undercover_game.py"; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi

    if run_python_test "讨论模式集成脚本" "$INTEGRATION_TEST_DIR/test_discussion_mode.py"; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi

    echo -e "${BLUE}验证完成: 通过 $passed, 失败 $failed${NC}"
    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

main

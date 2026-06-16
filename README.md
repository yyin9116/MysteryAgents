# Mystery Agents

AI agents play social deduction games with live reasoning, replay timelines, and immersive werewolf/undercover gameplay.

面向本地演示的多智能体社交博弈沙盒，包含《谁是卧底》、讨论模式和狼人杀。

## 发布定位

当前仓库按“本地演示版”整理：
- 仅保留核心代码、核心测试、核心说明文档
- 非核心开发过程资料和手动测试脚本不纳入 Git
- 不面向公网生产部署（无多实例、高可用、完整安全加固）

## 快速开始

### 依赖

- Python 3.10+
- Node.js 18+

### 1) 配置后端

```bash
cd backend
cp .env.example .env
```

### 2) 配置前端

```bash
cd frontend
cp .env.example .env
npm install
```

### 3) 启动与停止

```bash
./start.sh
./stop.sh
```

启动后访问：
- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

## 验证

```bash
./run_all_tests.sh
```

## 仓库结构（核心）

- `backend/`：后端服务与核心测试
- `frontend/`：前端应用
- `tests/integration/`：跨模块集成脚本
- `README_START.md`：启动说明
- `README_TESTS.md`：测试说明
- `start.sh` / `stop.sh` / `run_all_tests.sh`：核心脚本

## Git 收敛策略

- `docs/` 已默认加入 `.gitignore`，不作为 Git 核心发布内容
- 手动测试脚本、开发日志、代理工作流目录默认不纳入 Git
- 运行时产物（数据库、日志、缓存、构建目录）默认忽略

## License

MIT，见 `LICENSE`。

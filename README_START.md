# 启动指南（本地演示版）

## 适用范围

本项目仅保证本地演示链路可运行，不承诺公网生产可用性。

## 一键启动

```bash
./start.sh
./stop.sh
```

## 手动启动

### 后端

```bash
cd backend
cp .env.example .env
python3 main.py
```

### 前端

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## 地址

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`
- API 文档：`http://localhost:8000/docs`

## 日志

```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

## 常见问题

### 端口占用

```bash
lsof -ti:8000
lsof -ti:5173
kill <PID>
```

### 前后端地址不一致

确认 `frontend/.env`：

```env
VITE_API_BASE_URL=http://localhost:8000
```

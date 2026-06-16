# Backend（本地演示版）

## 快速开始

```bash
cd backend
uv pip install -r requirements.txt
cp .env.example .env
python3 main.py
```

服务默认地址：`http://localhost:8000`

## 目录（核心）

- `api/`：接口路由
- `services/`：业务逻辑
- `models/`：数据模型
- `database/`：数据库层
- `config/`：配置
- `tests/`：核心测试（`integration/`）

## 测试

```bash
pytest tests
```

## 说明

- `tests/manual/` 为非核心联调目录，不纳入发布版本
- 运行时数据（数据库、日志、缓存、状态目录）均为本地产物，默认不进 Git

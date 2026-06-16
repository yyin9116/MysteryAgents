# 测试说明（本地演示版）

## 核心测试

当前仅保留并要求以下核心集成测试：
- `tests/integration/test_undercover_game.py`
- `tests/integration/test_discussion_mode.py`

## 一键执行

```bash
./run_all_tests.sh
```

脚本会：
- 启动本地后端
- 运行上述两个核心集成脚本
- 输出通过/失败汇总
- 自动停止后端

## 说明

- 手动专项脚本（例如供应商联调）不属于核心发布内容
- 当前目标是保证本地演示主链路稳定，而非公网生产验收

## 故障排查

- 后端日志：`logs/backend.log`
- 前端日志：`logs/frontend.log`
- 健康检查：`curl http://localhost:8000/health`

"""
Game stream broker: drives a game loop in a background asyncio task and fans
out events to any number of SSE subscribers.

对局事件中枢 —— 解决三个问题：
1. 终止对局：DELETE/terminate 时 cancel 后台任务，即使模型调用进行中也会立即中断；
2. 用户退出：SSE 断开只移除订阅者，对局在后台继续跑到终局并落盘回放；
3. 断线重连：重连后先回放 backlog（带 seq 序列号），前端按 seq 去重即可无缝续播。
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 结束后保留时长（秒）：让最后的事件被订阅者取走
_FINISHED_RETENTION_SECONDS = 60.0


class GameBroker:
    """Per-game background loop + pub/sub fan-out."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._backlog: Dict[str, List[Dict[str, Any]]] = {}
        # 结束时间（正常结束或被终止）；None = 尚在运行或未启动
        self._finished_at: Dict[str, Optional[float]] = {}

    # ------------------------------------------------------------------ #
    # Publishing / lifecycle
    # ------------------------------------------------------------------ #

    def is_running(self, game_id: str) -> bool:
        task = self._tasks.get(game_id)
        return task is not None and not task.done()

    def has_game(self, game_id: str) -> bool:
        """Whether the broker still tracks this game (running or draining)."""
        return game_id in self._tasks

    def start(self, game_id: str, loop: Callable[[Callable[[Dict], None]], Any]) -> bool:
        """Start driving `loop(emit)` in a background task.

        Returns True if a new task was started, False when one is already
        running (idempotent — SSE reconnects never restart the game).
        """
        if self.is_running(game_id):
            return False
        # 之前一局已结束：清掉旧痕，全新开始
        if game_id in self._tasks:
            self._tasks.pop(game_id, None)
            self._backlog.pop(game_id, None)
            self._finished_at.pop(game_id, None)
        self._backlog.setdefault(game_id, [])
        self._subscribers.setdefault(game_id, [])
        self._finished_at[game_id] = None
        self._tasks[game_id] = asyncio.create_task(self._run(game_id, loop))
        logger.info("Broker started game loop for %s", game_id)
        return True

    async def _run(self, game_id: str, loop: Callable[[Callable[[Dict], None]], Any]) -> None:
        # 注意：emit 必须是同步函数 —— 游戏循环里全部是 `emit(...)` 直调，
        # 若定义为 async，事件会以「未 await 的协程」形式被丢弃（SSE 永远收不到）。
        def emit(event: Dict[str, Any]) -> None:
            event.setdefault("seq", len(self._backlog.get(game_id, [])) + 1)
            self._backlog.setdefault(game_id, []).append(event)
            for queue in list(self._subscribers.get(game_id, [])):
                try:
                    queue.put_nowait(event)
                except Exception:  # pragma: no cover - put_nowait rarely fails
                    pass

        try:
            await loop(emit)
        except asyncio.CancelledError:
            logger.info("Game loop %s cancelled", game_id)
            # 被终止：通知所有订阅者（backlog 同步写入，取消期间仍可写入）
            self._publish_raw(game_id, {
                "type": "game_terminated",
                "message": "对局已终止",
                "seq": len(self._backlog.get(game_id, [])) + 1,
            })
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Game loop %s crashed: %s", game_id, exc)
            self._publish_raw(game_id, {"type": "error", "message": str(exc)})
        finally:
            self._finished_at[game_id] = time.monotonic()
            self._wake_subscribers(game_id)

    def _publish_raw(self, game_id: str, event: Dict[str, Any]) -> None:
        self._backlog.setdefault(game_id, []).append(event)
        for queue in list(self._subscribers.get(game_id, [])):
            try:
                queue.put_nowait(event)
            except Exception:
                pass

    def _wake_subscribers(self, game_id: str) -> None:
        for queue in list(self._subscribers.get(game_id, [])):
            try:
                queue.put_nowait(None)  # 结束哨兵
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Subscription
    # ------------------------------------------------------------------ #

    def subscribe(self, game_id: str) -> Optional[Tuple[List[Dict[str, Any]], asyncio.Queue]]:
        """Subscribe to a game's events. Returns (backlog, live queue)."""
        if game_id not in self._tasks:
            return None
        queue: asyncio.Queue = asyncio.Queue()
        backlog = list(self._backlog.get(game_id, []))
        self._subscribers.setdefault(game_id, []).append(queue)
        return backlog, queue

    def unsubscribe(self, game_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(game_id)
        if subscribers and queue in subscribers:
            subscribers.remove(queue)

    # ------------------------------------------------------------------ #
    # Cancellation / cleanup
    # ------------------------------------------------------------------ #

    def cancel(self, game_id: str) -> bool:
        """Terminate the game loop immediately (interrupts in-flight LLM calls)."""
        task = self._tasks.get(game_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def discard(self, game_id: str) -> None:
        """Forget all broker state for a game (called after delete)."""
        self.cancel(game_id)
        self._wake_subscribers(game_id)
        self._tasks.pop(game_id, None)
        self._backlog.pop(game_id, None)
        self._subscribers.pop(game_id, None)
        self._finished_at.pop(game_id, None)

    async def sse_stream(
        self,
        game_id: str,
        format_event: Callable[[Dict[str, Any]], str],
        heartbeat_seconds: float = 15.0,
    ) -> AsyncGenerator[str, None]:
        """SSE generator: replay backlog, then stream live events until done."""
        subscription = self.subscribe(game_id)
        if subscription is None:
            yield format_event({"type": "error", "message": f"Game not found: {game_id}"})
            return
        backlog, queue = subscription
        try:
            for event in backlog:
                yield format_event(event)
            last_beat = time.monotonic()
            while True:
                if self._finished_at.get(game_id) is not None and queue.empty():
                    break
                try:
                    timeout = max(0.0, heartbeat_seconds - (time.monotonic() - last_beat))
                    event = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    last_beat = time.monotonic()
                    continue
                if event is None:
                    # 结束哨兵：把 backlog 里剩余的事件补发完
                    for pending in list(self._backlog.get(game_id, [])):
                        pass  # backlog 已在订阅时拿到；哨兵仅表示流程终结
                    break
                yield format_event(event)
                last_beat = time.monotonic()
        finally:
            self.unsubscribe(game_id, queue)
            self._maybe_cleanup(game_id)

    def _maybe_cleanup(self, game_id: str) -> None:
        finished_at = self._finished_at.get(game_id)
        if finished_at is None:
            return
        task = self._tasks.get(game_id)
        if task is not None and not task.done():
            return
        if not self._subscribers.get(game_id):
            # 保留 backlog 一段时间供重连，超时后清理
            if time.monotonic() - finished_at > _FINISHED_RETENTION_SECONDS:
                self.discard(game_id)


# 全局单例：狼人杀 / 剧本杀等各模式共用
game_broker = GameBroker()

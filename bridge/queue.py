"""Asynchronous message queue service."""

import asyncio
from collections.abc import Awaitable, Callable

from bridge.logger import Logger

logger = Logger.get_logger("queue")


class MessageQueue:
    """Simple asyncio-based message queue with a single consumer."""

    def __init__(
        self, consumer: Callable[[object], Awaitable[None]], max_size: int = 0
    ):
        self._consumer = consumer
        self._queue: asyncio.Queue[object] = asyncio.Queue(maxsize=max_size)
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        """Start the background worker."""
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the background worker."""
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def enqueue(self, item: object) -> None:
        """Add an item to the queue without waiting if full."""
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("Queue is full, dropping item")

    async def _run(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                await self._consumer(item)
            except Exception as ex:  # pylint: disable=broad-except
                logger.error("Error processing queued item: %s", ex)
            finally:
                self._queue.task_done()

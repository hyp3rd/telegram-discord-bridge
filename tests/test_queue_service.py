"""Tests for the optional message queue service."""

import asyncio

from bridge.queue import MessageQueue


def test_message_queue_processes_items():
    """Queued items are passed to the consumer."""
    processed: list[str] = []

    async def consumer(item: object) -> None:
        processed.append(str(item))

    async def run_test() -> None:
        queue = MessageQueue(consumer, max_size=2)
        queue.start()
        await queue.enqueue("msg")
        await asyncio.sleep(0)
        await queue.stop()

    asyncio.run(run_test())
    assert processed == ["msg"]

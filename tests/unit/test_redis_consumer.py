"""Unit tests for RedisConsumer snapshot cache debouncing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.consumers.redis_consumer import RedisConsumer


def _build_snapshot_msg(symbol: str = 'BTCUSDT') -> SimpleNamespace:
    """Build a lightweight message object for snapshot handler tests."""
    return SimpleNamespace(
        value={
            'symbol': symbol,
            'timestamp': '2026-03-03T00:00:00Z',
            'bids': [[100.0, 1.0]],
            'asks': [[101.0, 1.5]],
        }
    )


@pytest.mark.asyncio
async def test_snapshot_cache_debounces_within_min_interval(monkeypatch):
    """Second write inside interval is skipped for the same symbol."""
    consumer = RedisConsumer()
    consumer.redis.cache_orderbook = AsyncMock(return_value=True)
    consumer._snapshot_min_write_interval_seconds = 30

    msg = _build_snapshot_msg(symbol='btcusdt')
    clock_values = iter([1000.0, 1010.0])
    monkeypatch.setattr(
        'src.consumers.redis_consumer.monotonic',
        lambda: next(clock_values),
    )

    await consumer._handle_cache_snapshot(msg)
    await consumer._handle_cache_snapshot(_build_snapshot_msg(symbol='BTCUSDT'))

    assert consumer.redis.cache_orderbook.await_count == 1


@pytest.mark.asyncio
async def test_snapshot_cache_writes_again_after_interval(monkeypatch):
    """A write is allowed once debounce interval has elapsed."""
    consumer = RedisConsumer()
    consumer.redis.cache_orderbook = AsyncMock(return_value=True)
    consumer._snapshot_min_write_interval_seconds = 30

    clock_values = iter([1000.0, 1031.0, 1031.0])
    monkeypatch.setattr(
        'src.consumers.redis_consumer.monotonic',
        lambda: next(clock_values),
    )

    await consumer._handle_cache_snapshot(_build_snapshot_msg(symbol='ETHUSDT'))
    await consumer._handle_cache_snapshot(_build_snapshot_msg(symbol='ETHUSDT'))

    assert consumer.redis.cache_orderbook.await_count == 2


@pytest.mark.asyncio
async def test_snapshot_cache_without_debounce_writes_every_message():
    """Interval 0 disables debounce and writes every incoming snapshot."""
    consumer = RedisConsumer()
    consumer.redis.cache_orderbook = AsyncMock(return_value=True)
    consumer._snapshot_min_write_interval_seconds = 0

    await consumer._handle_cache_snapshot(_build_snapshot_msg(symbol='SOLUSDT'))
    await consumer._handle_cache_snapshot(_build_snapshot_msg(symbol='SOLUSDT'))

    assert consumer.redis.cache_orderbook.await_count == 2

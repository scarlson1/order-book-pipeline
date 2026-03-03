"""Integration tests for src/consumers/redis_consumer.py."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from uuid import uuid4

import pytest

from src.common.redpanda_client import RedpandaConsumer, RedpandaProducer
from src.common.redis_client import RedisClient
from src.config import settings
from src.consumers.redis_consumer import RedisConsumer


def _new_group_id(suffix: str) -> str:
    """Create a unique group id for isolated offset state per test."""
    return f'test-redis-consumer-{suffix}-{uuid4().hex[:8]}'


def _build_metrics_message(symbol: str, mid_price: float) -> dict:
    """Build a valid metrics message for orderbook.metrics."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        'timestamp': now,
        'symbol': symbol,
        'mid_price': mid_price,
        'best_bid': mid_price - 0.5,
        'best_ask': mid_price + 0.5,
        'imbalance_ratio': 0.2,
        'spread_bps': 2.2,
    }


def _build_alert_message(symbol: str, sequence: int) -> dict:
    """Build an alert message with numeric timestamp score for sorted-set storage."""
    timestamp_score = datetime.now(timezone.utc).timestamp() + sequence
    return {
        'timestamp': timestamp_score,
        'symbol': symbol,
        'alert_type': 'EXTREME_IMBALANCE',
        'severity': 'HIGH',
        'message': f'Alert #{sequence}',
        'metric_value': 0.8,
    }


async def _process_symbol_messages(redis_consumer: RedisConsumer,
                                   symbol: str,
                                   expected_count: int,
                                   handler: Callable[[object], Awaitable[None]],
                                   topic: str,
                                   timeout_s: float = 20.0) -> int:
    """Poll Kafka directly and route matching records to a RedisConsumer handler."""
    kafka_consumer = redis_consumer.consumer.consumer
    if kafka_consumer is None:
        return 0

    processed = 0
    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)

    while processed < expected_count and datetime.now(timezone.utc) < deadline:
        message_batch = await asyncio.to_thread(kafka_consumer.poll, timeout_ms=500)
        for messages in message_batch.values():
            for msg in messages:
                if msg.topic != topic:
                    continue
                if not isinstance(msg.value, dict):
                    continue
                if msg.value.get('symbol') != symbol:
                    continue

                await handler(msg)
                processed += 1
                if processed >= expected_count:
                    break
            if processed >= expected_count:
                break

    return processed


@asynccontextmanager
async def _connected_redis_consumer(topics: list[str], group_id: str):
    """Create a connected RedisConsumer scoped to selected topics."""
    redis_consumer = RedisConsumer()
    redis_consumer.consumer = RedpandaConsumer(topics=topics,
                                               group_id=group_id,
                                               auto_commit=False,
                                               auto_offset_reset='latest')

    try:
        await asyncio.gather(redis_consumer.redis.connect(), redis_consumer.consumer.connect())
    except Exception as error:
        await asyncio.gather(redis_consumer.redis.close(), redis_consumer.consumer.close())
        pytest.skip(f'Required services unavailable for redis consumer test: {error}')

    try:
        if redis_consumer.consumer.consumer is not None:
            await asyncio.to_thread(redis_consumer.consumer.consumer.poll, timeout_ms=200)
        yield redis_consumer
    finally:
        await asyncio.gather(redis_consumer.consumer.close(), redis_consumer.redis.close())


@pytest.fixture
def producer() -> RedpandaProducer:
    """Create a Redpanda producer for publishing test messages."""
    return RedpandaProducer()


@pytest.fixture
async def connected_producer(producer: RedpandaProducer):
    """Connected producer fixture that skips when Redpanda is unavailable."""
    try:
        await producer.connect()
    except Exception as error:
        pytest.skip(f'Redpanda unavailable for redis consumer tests: {error}')

    try:
        yield producer
    finally:
        await producer.close()


@pytest.mark.integration
async def test_publish_metrics_message_caches_redis_key(connected_producer: RedpandaProducer):
    """Publish to orderbook.metrics and verify metrics key appears in Redis."""
    symbol = f'REDISMET{uuid4().hex[:8]}'.upper()
    payload = _build_metrics_message(symbol=symbol, mid_price=45000.0)

    async with _connected_redis_consumer([settings.redpanda_topics['metrics']],
                                         _new_group_id('metrics-cache')) as redis_consumer:
        ok = await connected_producer.publish(topic=settings.redpanda_topics['metrics'],
                                              key=symbol,
                                              value=payload)
        assert ok is True
        await connected_producer.flush()

        processed = await _process_symbol_messages(redis_consumer,
                                                   symbol=symbol,
                                                   expected_count=1,
                                                   handler=redis_consumer._handle_cache_metrics,
                                                   topic=settings.redpanda_topics['metrics'])
        assert processed == 1

        cached = await redis_consumer.redis.get_cached_metrics(symbol)
        assert cached is not None
        assert cached['symbol'] == symbol
        assert float(cached['mid_price']) == payload['mid_price']


@pytest.mark.integration
async def test_metrics_cached_with_60_second_ttl(connected_producer: RedpandaProducer):
    """Metrics cached from orderbook.metrics should have a TTL <= 60 seconds."""
    symbol = f'REDISTTL{uuid4().hex[:8]}'.upper()
    payload = _build_metrics_message(symbol=symbol, mid_price=46000.0)

    async with _connected_redis_consumer([settings.redpanda_topics['metrics']],
                                         _new_group_id('metrics-ttl')) as redis_consumer:
        ok = await connected_producer.publish(topic=settings.redpanda_topics['metrics'],
                                              key=symbol,
                                              value=payload)
        assert ok is True
        await connected_producer.flush()

        processed = await _process_symbol_messages(redis_consumer,
                                                   symbol=symbol,
                                                   expected_count=1,
                                                   handler=redis_consumer._handle_cache_metrics,
                                                   topic=settings.redpanda_topics['metrics'])
        assert processed == 1

        key = RedisClient._metrics_key(symbol)
        assert redis_consumer.redis.client is not None
        ttl = await redis_consumer.redis.client.ttl(key)
        assert ttl > 0
        assert ttl <= RedisConsumer.METRICS_TTL_SECONDS


@pytest.mark.integration
async def test_alert_list_is_capped_at_100_per_symbol(connected_producer: RedpandaProducer):
    """Alerts cached from orderbook.alerts should be trimmed to 100 items per symbol."""
    symbol = f'REDISALERT{uuid4().hex[:8]}'.upper()
    alerts = [_build_alert_message(symbol, sequence=i) for i in range(120)]

    async with _connected_redis_consumer([settings.redpanda_topics['alerts']],
                                         _new_group_id('alerts-cap')) as redis_consumer:
        published = await connected_producer.publish_batch(settings.redpanda_topics['alerts'],
                                                           alerts)
        assert published == 120
        await connected_producer.flush()

        processed = await _process_symbol_messages(redis_consumer,
                                                   symbol=symbol,
                                                   expected_count=120,
                                                   handler=redis_consumer._handle_add_alert,
                                                   topic=settings.redpanda_topics['alerts'])
        assert processed == 120

        assert redis_consumer.redis.client is not None
        key = RedisClient._alerts_key(symbol)
        count = await redis_consumer.redis.client.zcard(key)
        assert count > 0
        assert count <= RedisConsumer.MAX_ALERTS_PER_SYMBOL

"""Integration tests for src/consumers/db_consumer.py."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.common.redpanda_client import RedpandaConsumer, RedpandaProducer
from src.config import settings
from src.consumers.db_consumer import DatabaseConsumer


def _new_group_id(suffix: str) -> str:
    """Create a unique group id for isolated offset state per test."""
    return f'test-db-consumer-{suffix}-{uuid4().hex[:8]}'


def _build_metrics_message(symbol: str, update_id: int, mid_price: float) -> dict:
    """Build a valid orderbook.metrics payload for database writes."""
    now = datetime.now(timezone.utc)
    return {
        'timestamp': now.isoformat(),
        'symbol': symbol,
        'mid_price': mid_price,
        'best_bid': mid_price - 0.5,
        'best_ask': mid_price + 0.5,
        'imbalance_ratio': 0.12,
        'weighted_imbalance': 0.11,
        'bid_volume': 120.0,
        'ask_volume': 100.0,
        'total_volume': 220.0,
        'spread_bps': 2.0,
        'spread_abs': 1.0,
        'vtob_ratio': 0.54,
        'best_bid_volume': 10.0,
        'best_ask_volume': 9.0,
        'imbalance_velocity': 0.01,
        'depth_levels': 20,
        'update_id': update_id,
    }


async def _process_symbol_messages(db_consumer: DatabaseConsumer,
                                   symbol: str,
                                   expected_count: int,
                                   timeout_s: float = 20.0) -> int:
    """Poll Kafka directly and route matching messages into DatabaseConsumer logic."""
    kafka_consumer = db_consumer.consumer.consumer
    if kafka_consumer is None:
        return 0

    processed = 0
    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)

    while processed < expected_count and datetime.now(timezone.utc) < deadline:
        message_batch = await asyncio.to_thread(kafka_consumer.poll, timeout_ms=500)
        for messages in message_batch.values():
            for msg in messages:
                if msg.topic != settings.redpanda_topics['metrics']:
                    continue
                if not isinstance(msg.value, dict):
                    continue
                if msg.value.get('symbol') != symbol:
                    continue

                await db_consumer._process_message(msg)
                processed += 1
                if processed >= expected_count:
                    break
            if processed >= expected_count:
                break

    return processed


@asynccontextmanager
async def _connected_db_consumer(group_id: str):
    """Create a connected DatabaseConsumer scoped to metrics topic only."""
    db_consumer = DatabaseConsumer()
    db_consumer.consumer = RedpandaConsumer(topics=[settings.redpanda_topics['metrics']],
                                            group_id=group_id,
                                            auto_commit=False,
                                            auto_offset_reset='latest')

    try:
        await asyncio.gather(db_consumer.db.connect(), db_consumer.consumer.connect())
    except Exception as error:
        await asyncio.gather(db_consumer.db.close(), db_consumer.consumer.close())
        pytest.skip(f'Required services unavailable for db consumer test: {error}')

    try:
        if db_consumer.consumer.consumer is not None:
            await asyncio.to_thread(db_consumer.consumer.consumer.poll, timeout_ms=200)
        yield db_consumer
    finally:
        await asyncio.gather(db_consumer.consumer.close(), db_consumer.db.close())


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
        pytest.skip(f'Redpanda unavailable for db consumer tests: {error}')

    try:
        yield producer
    finally:
        await producer.close()


@pytest.mark.integration
async def test_publish_metrics_message_persists_row_in_database(
        connected_producer: RedpandaProducer):
    """Publish to orderbook.metrics and verify a row is written to the database."""
    symbol = f'DBCONSUME{uuid4().hex[:8]}'.upper()
    payload = _build_metrics_message(symbol=symbol, update_id=1, mid_price=50000.0)

    async with _connected_db_consumer(_new_group_id('persist')) as db_consumer:
        ok = await connected_producer.publish(topic=settings.redpanda_topics['metrics'],
                                              key=symbol,
                                              value=payload)
        assert ok is True
        await connected_producer.flush()

        processed = await _process_symbol_messages(db_consumer, symbol=symbol, expected_count=1)
        assert processed == 1

        await db_consumer._flush_metrics_batch()

        rows = await db_consumer.db.fetch_recent_metrics(symbol, limit=1)
        assert rows, 'Expected at least one metrics row in DB'
        assert rows[0]['symbol'] == symbol
        assert float(rows[0]['mid_price']) == payload['mid_price']


@pytest.mark.integration
async def test_metrics_batch_insert_flushes_at_100_messages(connected_producer: RedpandaProducer):
    """Batch insert logic flushes automatically when 100 metrics are buffered."""
    symbol = f'DBBATCH{uuid4().hex[:8]}'.upper()
    messages = [
        _build_metrics_message(symbol=symbol, update_id=i, mid_price=50000.0 + (i * 0.01))
        for i in range(100)
    ]

    async with _connected_db_consumer(_new_group_id('batch100')) as db_consumer:
        db_consumer._metrics_batch_max_size = 100
        db_consumer._metrics_batch_timeout_seconds = 120.0

        published = await connected_producer.publish_batch(settings.redpanda_topics['metrics'],
                                                           messages)
        assert published == 100
        await connected_producer.flush()

        processed = await _process_symbol_messages(db_consumer, symbol=symbol, expected_count=100)
        assert processed == 100

        assert db_consumer.get_stats()['metrics_batch_count'] == 0

        assert db_consumer.db.pool is not None
        async with db_consumer.db.pool.acquire() as conn:
            count = await conn.fetchval('SELECT COUNT(*) FROM orderbook_metrics WHERE symbol = $1',
                                        symbol)
        assert count == 100


@pytest.mark.integration
async def test_offset_committed_after_successful_metrics_write(
        connected_producer: RedpandaProducer):
    """Offsets are committed after the metrics batch is successfully written."""
    symbol = f'DBOFFSET{uuid4().hex[:8]}'.upper()
    payload = _build_metrics_message(symbol=symbol, update_id=1, mid_price=51000.0)

    async with _connected_db_consumer(_new_group_id('commit')) as db_consumer:
        ok = await connected_producer.publish(topic=settings.redpanda_topics['metrics'],
                                              key=symbol,
                                              value=payload)
        assert ok is True
        await connected_producer.flush()

        processed = await _process_symbol_messages(db_consumer, symbol=symbol, expected_count=1)
        assert processed == 1

        await db_consumer._flush_metrics_batch()

        rows = await db_consumer.db.fetch_recent_metrics(symbol, limit=1)
        assert rows, 'Expected persisted row before validating committed offsets'

        kafka_consumer = db_consumer.consumer.consumer
        assert kafka_consumer is not None
        assigned_partitions = await asyncio.to_thread(kafka_consumer.assignment)
        assert assigned_partitions, 'Expected assigned partitions for committed offset check'

        committed_offsets = []
        for topic_partition in assigned_partitions:
            committed = await asyncio.to_thread(kafka_consumer.committed, topic_partition)
            if committed is not None:
                committed_offsets.append(committed)

        assert committed_offsets, 'Expected at least one committed offset'
        assert any(offset > 0 for offset in committed_offsets)

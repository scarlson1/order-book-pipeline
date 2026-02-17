"""Integration tests for src/common/redpanda_client.py.

These tests require a running Redpanda/Kafka broker reachable at the
bootstrap servers configured in `settings.redpanda_bootstrap_servers`.

Each test will **skip** rather than fail if a connection cannot be
established (e.g. when Redpanda is not running in CI or local env).

Covers checklist items:
- Test producer connects successfully
- Test publish single message
- Test publish batch
- Test consumer receives published messages
- Test consumer group offset tracking
- Test graceful shutdown flushes before closing
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pytest

from src.common.redpanda_client import RedpandaProducer, RedpandaConsumer
from src.config import settings


TEST_TOPIC = "test.orderbook.redpanda"
TEST_GROUP = "test-orderbook-consumer-group"


# ----- Fixtures ----- #


@pytest.fixture
def producer() -> RedpandaProducer:
    """Create a RedpandaProducer instance (caller connects/closes)."""
    return RedpandaProducer()


@pytest.fixture
async def connected_producer(producer: RedpandaProducer):
    """Producer connected to a real Redpanda broker.

    Skips tests if connection fails (e.g. broker not running).
    """
    try:
        await producer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for producer tests: {e}")

    try:
        yield producer
    finally:
        await producer.close()


@pytest.fixture
def consumer_factory():
    """Factory to create RedpandaConsumer instances for topics/group."""

    def _make(topics: List[str] = None, group_id: str = TEST_GROUP) -> RedpandaConsumer:
        return RedpandaConsumer(
            topics=topics or [TEST_TOPIC],
            group_id=group_id,
            auto_commit=True,
            auto_offset_reset="earliest",
        )

    return _make


@pytest.fixture
async def connected_consumer(consumer_factory):
    """Connected consumer for the test topic.

    Skips tests if Redpanda is not reachable.
    """
    consumer = consumer_factory()
    try:
        # connect() is currently synchronous
        consumer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for consumer tests: {e}")

    try:
        yield consumer
    finally:
        await consumer.close()


@pytest.fixture
def sample_message() -> Dict[str, Any]:
    """Sample orderbook-like payload."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": datetime.utcnow().isoformat(),
        "bids": [[50000.0, 1.5], [49999.5, 2.0]],
        "asks": [[50000.5, 1.2], [50001.0, 1.8]],
    }


# ----- Helper utilities ----- #


async def _drain_consumer(consumer: RedpandaConsumer, max_messages: int = 100, timeout_s: float = 5.0):
    """Drain up to max_messages from consumer within timeout."""
    messages = []
    deadline = datetime.utcnow() + timedelta(seconds=timeout_s)

    while len(messages) < max_messages and datetime.utcnow() < deadline:
        async for msg in consumer.consume(timeout_ms=500):
            messages.append(msg)
            if len(messages) >= max_messages:
                break

        # Small pause to avoid tight loop when no data
        await asyncio.sleep(0.05)

    return messages


# ----- Tests ----- #


@pytest.mark.integration
async def test_producer_connects_successfully(producer: RedpandaProducer):
    """Test producer connects successfully (check underlying producer is set)."""
    try:
        await producer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available: {e}")

    assert producer.producer is not None
    await producer.close()


@pytest.mark.integration
async def test_publish_single_message(connected_producer: RedpandaProducer, sample_message: Dict[str, Any]):
    """Test publish single message returns True and updates stats."""
    before_stats = connected_producer.get_stats()

    ok = await connected_producer.publish(
        topic=TEST_TOPIC,
        key=sample_message["symbol"],
        value=sample_message,
    )

    assert ok is True

    # Flush to ensure message is actually sent to broker.
    await connected_producer.flush()

    after_stats = connected_producer.get_stats()
    assert after_stats["messages_sent"] == before_stats["messages_sent"] + 1


@pytest.mark.integration
async def test_publish_batch(connected_producer: RedpandaProducer):
    """Test publish_batch sends multiple messages and returns correct count."""
    messages = [
        {"symbol": "BTCUSDT", "price": 50000.0},
        {"symbol": "ETHUSDT", "price": 3000.0},
        {"symbol": "SOLUSDT", "price": 100.0},
    ]

    count = await connected_producer.publish_batch(TEST_TOPIC, messages)
    await connected_producer.flush()

    assert count == len(messages)


@pytest.mark.integration
async def test_consumer_receives_published_messages(
    connected_producer: RedpandaProducer,
    consumer_factory,
    sample_message: Dict[str, Any],
):
    """End-to-end: producer publishes, consumer receives."""
    # Ensure Redpanda is actually enabled in config; if not, skip instead of hanging.
    if not settings.redpanda_enabled:
        pytest.skip("Redpanda is disabled in settings; skipping integration test.")

    # Publish a couple of messages.
    for i in range(3):
        msg = {**sample_message, "sequence": i}
        ok = await connected_producer.publish(
            topic=TEST_TOPIC,
            key=msg["symbol"],
            value=msg,
        )
        assert ok is True

    await connected_producer.flush()

    consumer = consumer_factory(group_id=f"{TEST_GROUP}-receive")
    try:
        consumer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for consumer: {e}")

    try:
        received = await _drain_consumer(consumer, max_messages=3, timeout_s=10.0)
    finally:
        await consumer.close()

    assert len(received) >= 1
    # At least one message value should have our symbol.
    assert any(msg.value.get("symbol") == sample_message["symbol"] for msg in received)


@pytest.mark.integration
async def test_consumer_group_offset_tracking(
    connected_producer: RedpandaProducer,
    consumer_factory,
    sample_message: Dict[str, Any],
):
    """Messages read by one consumer in a group should not be re-delivered to a second consumer.

    This relies on auto-commit being enabled for the consumer group.
    """
    if not settings.redpanda_enabled:
        pytest.skip("Redpanda is disabled in settings; skipping integration test.")

    # Publish a unique marker message.
    marker = datetime.utcnow().isoformat()
    msg = {**sample_message, "marker": marker}
    ok = await connected_producer.publish(
        topic=TEST_TOPIC,
        key=msg["symbol"],
        value=msg,
    )
    assert ok is True
    await connected_producer.flush()

    group_id = f"{TEST_GROUP}-offsets"

    # First consumer in the group reads the message (and auto-commits).
    consumer1 = consumer_factory(group_id=group_id)
    try:
        consumer1.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for consumer: {e}")

    try:
        received1 = await _drain_consumer(consumer1, max_messages=10, timeout_s=10.0)
    finally:
        await consumer1.close()

    assert any(
        getattr(msg, "value", {}).get("marker") == marker
        for msg in received1
        if msg.value is not None
    )

    # Small delay to give auto-commit a chance to persist offsets.
    await asyncio.sleep(2.0)

    # Second consumer in same group should not see the same marker message again.
    consumer2 = consumer_factory(group_id=group_id)
    try:
        consumer2.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for consumer: {e}")

    try:
        received2 = await _drain_consumer(consumer2, max_messages=10, timeout_s=5.0)
    finally:
        await consumer2.close()

    assert all(
        getattr(msg, "value", {}).get("marker") != marker
        for msg in received2
        if msg.value is not None
    )


@pytest.mark.integration
async def test_graceful_shutdown_flushes_before_closing(
    producer: RedpandaProducer,
    sample_message: Dict[str, Any],
):
    """Using close() should flush buffered messages before shutting down.

    We validate this indirectly by checking that messages_sent increases
    and close() does not raise when Redpanda is available.
    """
    try:
        await producer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available: {e}")

    before_stats = producer.get_stats()

    ok = await producer.publish(
        topic=TEST_TOPIC,
        key=sample_message["symbol"],
        value=sample_message,
    )
    assert ok is True

    # close() internally calls flush(); should complete without raising.
    await producer.close()

    after_stats = producer.get_stats()
    assert after_stats["messages_sent"] == before_stats["messages_sent"] + 1


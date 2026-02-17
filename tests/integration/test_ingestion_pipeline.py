"""Integration tests for the ingestion pipeline.

These tests avoid external Binance dependencies by patching the
BinanceWebSocketClient to emit a synthetic message. A running
Redpanda broker is still required; tests will skip if unavailable.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import numbers
import uuid

import pytest

from src.common.redpanda_client import RedpandaConsumer
from src.config import settings
from src.ingestion.main import IngestionService


def _make_fake_ws_client(symbol: str, raw_message: dict):
    class FakeWebSocketClient:
        def __init__(self, callback):
            self.callback = callback

        async def start(self) -> None:
            # Yield to event loop, then emit one synthetic message.
            await asyncio.sleep(0)
            await self.callback(symbol, raw_message)

        async def stop(self) -> None:
            return

    return FakeWebSocketClient


async def _wait_for_message(consumer: RedpandaConsumer, symbol: str, timeout_s: float = 10.0):
    deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout_s)

    while datetime.now(timezone.utc) < deadline:
        batch = await asyncio.to_thread(consumer.consumer.poll, timeout_ms=500)
        for msgs in batch.values():
            for msg in msgs:
                if msg.value and msg.value.get("symbol") == symbol:
                    return msg
        await asyncio.sleep(0.05)

    return None


@pytest.fixture
async def ingestion_message(monkeypatch):
    if not settings.redpanda_enabled:
        pytest.skip("Redpanda is disabled in settings; skipping integration test.")

    topic = settings.redpanda_topics["raw"]
    group_id = f"test-ingestion-pipeline-{uuid.uuid4().hex[:8]}"

    consumer = RedpandaConsumer(
        topics=[topic],
        group_id=group_id,
        auto_commit=True,
        auto_offset_reset="latest",
    )

    try:
        await consumer.connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Redpanda not available for ingestion pipeline tests: {e}")

    # Warm-up poll to join the consumer group at the latest offset.
    await asyncio.to_thread(consumer.consumer.poll, timeout_ms=100)

    symbol = f"TEST{uuid.uuid4().hex[:6].upper()}"
    raw_message = {
        "lastUpdatedId": 12345,
        "bids": [["100.0", "1.0"], ["99.5", "2.0"]],
        "asks": [["101.0", "1.5"], ["102.0", "3.0"]],
        "E": 1700000000000,
    }

    FakeWebSocketClient = _make_fake_ws_client(symbol, raw_message)

    async def _no_log_stats(self) -> None:
        return

    monkeypatch.setattr("src.ingestion.main.BinanceWebSocketClient", FakeWebSocketClient)
    monkeypatch.setattr(IngestionService, "_log_stats", _no_log_stats, raising=True)

    service = IngestionService()

    try:
        await service.start()
    finally:
        # Ensure cleanup even if assertions fail later.
        await service.stop()

    try:
        msg = await _wait_for_message(consumer, symbol, timeout_s=10.0)
    finally:
        with suppress(Exception):
            await consumer.close()

    assert msg is not None
    return msg


@pytest.mark.integration
async def test_ingestion_service_publishes_to_raw(ingestion_message):
    msg = ingestion_message
    assert msg.topic == settings.redpanda_topics["raw"]
    assert msg.value is not None


@pytest.mark.integration
async def test_raw_message_schema_matches_expected_format(ingestion_message):
    msg = ingestion_message
    value = msg.value

    required_keys = {
        "timestamp",
        "symbol",
        "bids",
        "asks",
        "update_id",
        "ingested_at",
        "source",
    }
    assert required_keys.issubset(value.keys())

    assert value["source"] == "binance_websocket"
    assert isinstance(value["symbol"], str) and value["symbol"].strip()

    # Timestamps should be ISO-parsable strings.
    datetime.fromisoformat(value["timestamp"])
    datetime.fromisoformat(value["ingested_at"])

    # Order book levels should be numeric pairs with positive values.
    for side in ("bids", "asks"):
        levels = value[side]
        assert isinstance(levels, list) and len(levels) > 0
        for level in levels:
            assert isinstance(level, (list, tuple)) and len(level) == 2
            price, volume = level
            assert isinstance(price, numbers.Real) and price > 0
            assert isinstance(volume, numbers.Real) and volume > 0

    update_id = value["update_id"]
    assert update_id is None or isinstance(update_id, int)

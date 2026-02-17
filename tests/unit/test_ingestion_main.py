"""Unit tests for IngestionService and signal handling."""

import asyncio
import signal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.models import OrderBookSnapshot
from src.ingestion.main import IngestionService, setup_signal_handlers


# ----- handle_orderbook: parser then publisher -----


@pytest.mark.asyncio
async def test_handle_orderbook_calls_parser_then_publisher():
    """handle_orderbook parses with parser then publishes message to producer."""
    service = IngestionService()
    service.parser = MagicMock()
    service.producer = AsyncMock()

    symbol = "BTCUSDT"
    raw_data = {"b": [["100", "1"]], "a": [["101", "1"]], "E": 1700000000000}
    snapshot = OrderBookSnapshot(
        timestamp=datetime.now(timezone.utc),
        symbol=symbol,
        bids=[(100.0, 1.0)],
        asks=[(101.0, 1.0)],
        update_id=1,
    )
    service.parser.parse.return_value = snapshot

    with patch("src.ingestion.main.settings") as mock_settings:
        mock_settings.redpanda_topics = {"raw": "orderbook.raw"}
        await service.handle_orderbook(symbol, raw_data)

    service.parser.parse.assert_called_once_with(symbol, raw_data)
    service.producer.publish.assert_called_once()
    call_kw = service.producer.publish.call_args.kwargs
    assert call_kw["key"] == symbol
    assert call_kw["topic"] == "orderbook.raw"
    value = call_kw["value"]
    assert value["symbol"] == symbol
    assert "ingested_at" in value
    assert value["source"] == "binance_websocket"
    assert value["bids"] == [(100.0, 1.0)]
    assert value["asks"] == [(101.0, 1.0)]


@pytest.mark.asyncio
async def test_handle_orderbook_does_not_publish_when_parser_returns_none():
    """When parser returns None, handle_orderbook does not call publisher."""
    service = IngestionService()
    service.parser = MagicMock(return_value=None)
    service.producer = AsyncMock()

    await service.handle_orderbook("BTCUSDT", {"b": [], "a": []})

    service.parser.parse.assert_called_once_with("BTCUSDT", {"b": [], "a": []})
    service.producer.publish.assert_not_called()


# ----- stop(): flush producer before closing -----


@pytest.mark.asyncio
async def test_stop_flushes_producer_before_closing():
    """stop() flushes producer then closes it (via producer.close())."""
    service = IngestionService()
    service._running = True
    service.ws_client = AsyncMock()
    service.producer = AsyncMock()
    service.producer.close = AsyncMock()
    service.producer.get_stats.return_value = {"messages_sent": 0, "messages_failed": 0}

    # RedpandaProducer.close() internally calls flush() then close; we only need to
    # ensure close() is awaited. Optionally assert order if we patch flush separately.
    flush_mock = AsyncMock()
    service.producer.flush = flush_mock
    # Make close() call flush so we can assert order
    async def close_side_effect():
        await service.producer.flush()
    service.producer.close.side_effect = close_side_effect

    await service.stop()

    service.ws_client.stop.assert_awaited_once()
    service.producer.close.assert_awaited_once()
    flush_mock.assert_awaited_once()
    # flush is awaited before close returns, so flush is effectively "before" close
    assert flush_mock.await_count == 1
    assert service.producer.close.await_count == 1


@pytest.mark.asyncio
async def test_stop_idempotent_when_not_running():
    """stop() returns without doing work when _running is False."""
    service = IngestionService()
    service._running = False
    service.producer = AsyncMock()
    service.producer.close = AsyncMock()

    await service.stop()

    service.producer.close.assert_not_awaited()


# ----- Signal handler triggers graceful stop -----


def test_signal_handler_triggers_graceful_stop():
    """setup_signal_handlers registers SIGTERM/SIGINT; handler schedules service.stop()."""
    service = IngestionService()
    service.stop = AsyncMock()
    loop = MagicMock()
    loop.add_signal_handler = MagicMock()
    loop.create_task = MagicMock(return_value=MagicMock())

    with patch("src.ingestion.main.asyncio.get_event_loop", return_value=loop):
        setup_signal_handlers(service)

    assert loop.add_signal_handler.call_count == 2
    calls = [loop.add_signal_handler.call_args_list[i][0] for i in range(2)]
    sigs = {c[0] for c in calls}
    assert sigs == {signal.SIGTERM, signal.SIGINT}

    handler = loop.add_signal_handler.call_args_list[0][0][1]
    handler()
    service.stop.assert_called_once()
    loop.create_task.assert_called_once()
    # create_task was called with the coroutine from service.stop()
    task_arg = loop.create_task.call_args[0][0]
    assert task_arg == service.stop.return_value

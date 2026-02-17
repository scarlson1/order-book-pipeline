"""Integration tests for src/common/database.py.

Requires a running PostgreSQL/TimescaleDB instance with schema from init-db.sql.
Skip when database is unavailable (e.g. CI without services).
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from src.common.database import DatabaseClient


# ----- Fixtures ----- #


@pytest.fixture
def db_client():
    """Create and return a DatabaseClient (caller must connect/close)."""
    return DatabaseClient()


@pytest.fixture
async def connected_db(db_client):
    """Database client connected to a real DB. Skips the test if connection fails."""
    try:
        await db_client.connect()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    try:
        yield db_client
    finally:
        await db_client.close()


@pytest.fixture
def sample_metrics():
    """Minimal valid metrics dict for insert_metrics."""
    return {
        "timestamp": datetime.now(timezone.utc),
        "symbol": "BTCUSDT",
        "mid_price": 50000.0,
        "best_bid": 49999.0,
        "best_ask": 50001.0,
        "imbalance_ratio": 0.1,
        "bid_volume": 100.0,
        "ask_volume": 90.0,
        "spread_bps": 4.0,
        "weighted_imbalance": 0.12,
        "total_volume": 190.0,
        "spread_abs": 2.0,
        "vtob_ratio": 0.55,
        "best_bid_volume": 10.0,
        "best_ask_volume": 9.0,
        "imbalance_velocity": 0.01,
        "depth_levels": 10,
        "update_id": 12345,
    }


@pytest.fixture
def sample_alert():
    """Minimal valid alert dict for insert_alert."""
    return {
        "timestamp": datetime.now(timezone.utc),
        "symbol": "BTCUSDT",
        "alert_type": "EXTREME_IMBALANCE",
        "severity": "HIGH",
        "message": "Imbalance above threshold",
        "metric_value": 0.75,
        "threshold_value": 0.70,
        "side": "BID",
        "mid_price": 50000.0,
        "imbalance_ratio": 0.75,
    }


# ----- Insert operations ----- #


@pytest.mark.integration
async def test_insert_metrics(connected_db, sample_metrics):
    """insert_metrics persists a row and does not raise."""
    await connected_db.insert_metrics(sample_metrics)


@pytest.mark.integration
async def test_insert_metrics_then_fetch(connected_db, sample_metrics):
    """Inserted metrics can be read back via fetch_recent_metrics."""
    await connected_db.insert_metrics(sample_metrics)
    rows = await connected_db.fetch_recent_metrics(sample_metrics["symbol"], limit=5)
    assert len(rows) >= 1
    latest = rows[0]
    assert latest["symbol"] == sample_metrics["symbol"]
    assert float(latest["mid_price"]) == sample_metrics["mid_price"]
    assert float(latest["imbalance_ratio"]) == sample_metrics["imbalance_ratio"]


@pytest.mark.integration
async def test_insert_alert(connected_db, sample_alert):
    """insert_alert persists a row and does not raise."""
    await connected_db.insert_alert(sample_alert)


@pytest.mark.integration
async def test_insert_alert_then_fetch(connected_db, sample_alert):
    """Inserted alerts can be read back via fetch_alerts."""
    await connected_db.insert_alert(sample_alert)
    rows = await connected_db.fetch_alerts(symbol=sample_alert["symbol"], limit=5)
    assert len(rows) >= 1
    latest = rows[0]
    assert latest["symbol"] == sample_alert["symbol"]
    assert latest["alert_type"] == sample_alert["alert_type"]
    assert latest["severity"] == sample_alert["severity"]
    assert latest["message"] == sample_alert["message"]


# ----- Query operations ----- #


@pytest.mark.integration
async def test_fetch_recent_metrics_empty(connected_db):
    """fetch_recent_metrics returns empty list for symbol with no data."""
    rows = await connected_db.fetch_recent_metrics("NODATAUSDT", limit=10)
    assert rows == []


@pytest.mark.integration
async def test_fetch_recent_metrics_respects_limit(connected_db, sample_metrics):
    """fetch_recent_metrics returns at most limit rows."""
    for i in range(5):
        data = {**sample_metrics, "mid_price": sample_metrics["mid_price"] + i * 0.01}
        await connected_db.insert_metrics(data)
    rows = await connected_db.fetch_recent_metrics(sample_metrics["symbol"], limit=3)
    assert len(rows) <= 3


@pytest.mark.integration
async def test_fetch_time_series(connected_db, sample_metrics):
    """fetch_time_series returns metrics in time range."""
    await connected_db.insert_metrics(sample_metrics)
    start = (sample_metrics["timestamp"] - timedelta(seconds=60)).replace(tzinfo=timezone.utc)
    end = (sample_metrics["timestamp"] + timedelta(seconds=60)).replace(tzinfo=timezone.utc)
    rows = await connected_db.fetch_time_series(sample_metrics["symbol"], start, end)
    assert len(rows) >= 1
    assert rows[0]["symbol"] == sample_metrics["symbol"]


@pytest.mark.integration
async def test_fetch_time_series_empty_range(connected_db, sample_metrics):
    """fetch_time_series returns empty list when range has no data."""
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime(2000, 1, 2, tzinfo=timezone.utc)
    rows = await connected_db.fetch_time_series(sample_metrics["symbol"], start, end)
    assert rows == []


@pytest.mark.integration
async def test_fetch_alerts_all(connected_db, sample_alert):
    """fetch_alerts without symbol returns recent alerts."""
    await connected_db.insert_alert(sample_alert)
    rows = await connected_db.fetch_alerts(limit=10)
    assert isinstance(rows, list)
    if rows:
        assert "time" in rows[0] and "symbol" in rows[0] and "alert_type" in rows[0]


@pytest.mark.integration
async def test_fetch_alerts_by_symbol(connected_db, sample_alert):
    """fetch_alerts with symbol filters by symbol."""
    await connected_db.insert_alert(sample_alert)
    rows = await connected_db.fetch_alerts(symbol=sample_alert["symbol"], limit=10)
    assert all(r["symbol"] == sample_alert["symbol"] for r in rows)


@pytest.mark.integration
async def test_get_statistics(connected_db, sample_metrics):
    """get_statistics returns a dict with expected keys (may be empty)."""
    await connected_db.insert_metrics(sample_metrics)
    stats = await connected_db.get_statistics(sample_metrics["symbol"], hours=1)
    assert isinstance(stats, dict)
    if stats:
        assert "avg_imbalance" in stats or "sample_count" in stats


# ----- Connection pooling ----- #


@pytest.mark.integration
async def test_get_pool_stats_when_connected(connected_db):
    """get_pool_stats returns size/free/max_size/min_size when connected."""
    stats = await connected_db.get_pool_stats()
    assert stats.get("status") != "not_connected"
    assert "size" in stats
    assert "free" in stats
    assert "max_size" in stats
    assert "min_size" in stats
    assert stats["min_size"] >= 0
    assert stats["max_size"] >= stats["min_size"]


@pytest.mark.integration
async def test_get_pool_stats_when_not_connected(db_client):
    """get_pool_stats returns not_connected when pool is None."""
    stats = await db_client.get_pool_stats()
    assert stats == {"status": "not_connected"}


@pytest.mark.integration
async def test_health_check_returns_true_when_connected(connected_db):
    """health_check returns True when pool is healthy."""
    ok = await connected_db.health_check()
    assert ok is True


@pytest.mark.integration
async def test_concurrent_acquires_use_pool(connected_db):
    """Multiple concurrent operations use the pool without error."""
    import asyncio

    async def query():
        return await connected_db.fetch_recent_metrics("BTCUSDT", limit=1)

    results = await asyncio.gather(*[query() for _ in range(5)])
    assert len(results) == 5
    for r in results:
        assert isinstance(r, list)


# ----- Error handling ----- #


@pytest.mark.integration
async def test_connect_with_bad_credentials_raises():
    """connect() raises when credentials are invalid."""
    with patch("src.common.database.settings") as mock_settings:
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_port = 5432
        mock_settings.postgres_user = "nonexistent_user_xyz"
        mock_settings.postgres_password = "wrong"
        mock_settings.postgres_db = "nonexistent_db"
        client = DatabaseClient()
        with pytest.raises(Exception):
            await client.connect()


@pytest.mark.integration
async def test_insert_metrics_without_connect_raises(db_client, sample_metrics):
    """insert_metrics raises when pool is None (not connected)."""
    with pytest.raises(AttributeError):
        await db_client.insert_metrics(sample_metrics)


@pytest.mark.integration
async def test_insert_alert_without_connect_raises(db_client, sample_alert):
    """insert_alert raises when pool is None (not connected)."""
    with pytest.raises(AttributeError):
        await db_client.insert_alert(sample_alert)


@pytest.mark.integration
async def test_fetch_recent_metrics_without_connect_raises(db_client):
    """fetch_recent_metrics raises when pool is None."""
    with pytest.raises(AttributeError):
        await db_client.fetch_recent_metrics("BTCUSDT", limit=10)


@pytest.mark.integration
async def test_health_check_returns_false_when_not_connected(db_client):
    """health_check returns False when pool is None."""
    ok = await db_client.health_check()
    assert ok is False


@pytest.mark.integration
async def test_close_idempotent(db_client):
    """close() when pool is None does not raise."""
    await db_client.close()
    await db_client.close()


@pytest.mark.integration
async def test_insert_metrics_missing_required_key_raises(connected_db, sample_metrics):
    """insert_metrics with missing required key raises."""
    bad = {k: v for k, v in sample_metrics.items() if k != "symbol"}
    with pytest.raises((KeyError, Exception)):
        await connected_db.insert_metrics(bad)


@pytest.mark.integration
async def test_insert_alert_missing_required_key_raises(connected_db, sample_alert):
    """insert_alert with missing required key raises."""
    bad = {k: v for k, v in sample_alert.items() if k != "message"}
    with pytest.raises((KeyError, Exception)):
        await connected_db.insert_alert(bad)

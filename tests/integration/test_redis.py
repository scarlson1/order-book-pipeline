"""Integration tests for src/common/redis_client.py.

Requires a running Redis instance. Skips when Redis is unavailable (e.g. CI without services).

Covers: caching operations, TTL expiration, key naming.
"""
from datetime import datetime, timezone

import pytest

from src.common.redis_client import RedisClient


# ----- Fixtures ----- #


@pytest.fixture
def redis_client():
    """Create and return a RedisClient (caller must connect/close)."""
    return RedisClient()


@pytest.fixture
async def connected_redis(redis_client):
    """Redis client connected to a real Redis. Skips the test if connection fails."""
    try:
        await redis_client.connect()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    try:
        yield redis_client
    finally:
        await redis_client.close()


@pytest.fixture
def sample_metrics():
    """Sample metrics dict for caching."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "BTCUSDT",
        "mid_price": 50000.0,
        "imbalance_ratio": 0.1,
        "spread_bps": 4.0,
    }


@pytest.fixture
def sample_orderbook():
    """Sample orderbook snapshot for caching."""
    return {
        "symbol": "ETHUSDT",
        "bids": [[3000.0, 1.5], [2999.0, 2.0]],
        "asks": [[3001.0, 1.2], [3002.0, 1.8]],
    }


@pytest.fixture
def sample_alert():
    """Sample alert dict for list caching."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "BTCUSDT",
        "alert_type": "EXTREME_IMBALANCE",
        "severity": "HIGH",
        "message": "Test alert",
        "metric_value": 0.75,
    }


@pytest.fixture
def sample_stats():
    """Sample statistics dict for caching."""
    return {
        "symbol": "BTCUSDT",
        "avg_imbalance": 0.2,
        "avg_spread_bps": 5.0,
        "sample_count": 100,
    }


# ----- Key naming ----- #


@pytest.mark.integration
def test_metrics_key_naming():
    """Key for latest metrics follows orderbook:{symbol}:latest."""
    assert RedisClient._metrics_key("BTCUSDT") == "orderbook:BTCUSDT:latest"
    assert RedisClient._metrics_key("btcusdt") == "orderbook:BTCUSDT:latest"
    assert RedisClient._metrics_key("EthUsdt") == "orderbook:ETHUSDT:latest"


@pytest.mark.integration
def test_snapshot_key_naming():
    """Key for snapshot follows orderbook:{symbol}:snapshot."""
    assert RedisClient._snapshot_key("BTCUSDT") == "orderbook:BTCUSDT:snapshot"
    assert RedisClient._snapshot_key("ethusdt") == "orderbook:ETHUSDT:snapshot"


@pytest.mark.integration
def test_alerts_key_naming():
    """Key for alerts list follows orderbook:alerts:{symbol}."""
    assert RedisClient._alerts_key("BTCUSDT") == "orderbook:alerts:BTCUSDT"
    assert RedisClient._alerts_key("ethusdt") == "orderbook:alerts:ETHUSDT"


@pytest.mark.integration
def test_stats_key_naming():
    """Key for stats follows orderbook:stats:{symbol}."""
    assert RedisClient._stats_key("BTCUSDT") == "orderbook:stats:BTCUSDT"
    assert RedisClient._stats_key("btcusdt") == "orderbook:stats:BTCUSDT"


@pytest.mark.integration
def test_key_naming_no_collision():
    """Metrics, snapshot, alerts, and stats keys are distinct for same symbol."""
    symbol = "BTCUSDT"
    keys = [
        RedisClient._metrics_key(symbol),
        RedisClient._snapshot_key(symbol),
        RedisClient._alerts_key(symbol),
        RedisClient._stats_key(symbol),
    ]
    assert len(keys) == len(set(keys))


# ----- Caching operations ----- #


@pytest.mark.integration
async def test_insert_metrics_and_get_cached_metrics(connected_redis, sample_metrics):
    """cache (insert_metrics) then get_cached_metrics returns same data."""
    symbol = sample_metrics["symbol"]
    ok = await connected_redis.insert_metrics(symbol, sample_metrics, ttl=60)
    assert ok is True
    cached = await connected_redis.get_cached_metrics(symbol)
    assert cached is not None
    assert cached["symbol"] == sample_metrics["symbol"]
    assert cached["mid_price"] == sample_metrics["mid_price"]
    assert cached["imbalance_ratio"] == sample_metrics["imbalance_ratio"]


@pytest.mark.integration
async def test_get_cached_metrics_miss_returns_none(connected_redis):
    """get_cached_metrics returns None for uncached symbol."""
    result = await connected_redis.get_cached_metrics("NOCACHEUSDT")
    assert result is None


@pytest.mark.integration
async def test_cache_orderbook_and_get(connected_redis, sample_orderbook):
    """cache_orderbook then get_cached_orderbook returns same data."""
    symbol = sample_orderbook["symbol"]
    ok = await connected_redis.cache_orderbook(symbol, sample_orderbook, ttl=30)
    assert ok is True
    cached = await connected_redis.get_cached_orderbook(symbol)
    assert cached is not None
    assert cached["symbol"] == sample_orderbook["symbol"]
    assert cached["bids"] == sample_orderbook["bids"]
    assert cached["asks"] == sample_orderbook["asks"]


@pytest.mark.integration
async def test_get_cached_orderbook_miss_returns_none(connected_redis):
    """get_cached_orderbook returns None for uncached symbol."""
    result = await connected_redis.get_cached_orderbook("NOCACHEUSDT")
    assert result is None


@pytest.mark.integration
async def test_cache_statistics_and_get(connected_redis, sample_stats):
    """cache_statistics then get_cached_statistics returns same data."""
    symbol = sample_stats["symbol"]
    ok = await connected_redis.cache_statistics(symbol, sample_stats, ttl=300)
    assert ok is True
    cached = await connected_redis.get_cached_statistics(symbol)
    assert cached is not None
    assert cached["symbol"] == sample_stats["symbol"]
    assert cached["avg_imbalance"] == sample_stats["avg_imbalance"]
    assert cached["sample_count"] == sample_stats["sample_count"]


@pytest.mark.integration
async def test_add_alert_and_get_alerts(connected_redis, sample_alert):
    """add_alert then get_alerts returns the alert."""
    symbol = sample_alert["symbol"]
    ok = await connected_redis.add_alert(symbol, sample_alert, max_alerts=100)
    assert ok is True
    alerts = await connected_redis.get_alerts(symbol, limit=10)
    assert len(alerts) >= 1
    assert alerts[0]["message"] == sample_alert["message"]
    assert alerts[0]["alert_type"] == sample_alert["alert_type"]


@pytest.mark.integration
async def test_get_alerts_empty_returns_empty_list(connected_redis):
    """get_alerts for symbol with no alerts returns empty list."""
    result = await connected_redis.get_alerts("NOALERTSUSDT", limit=10)
    assert result == []


@pytest.mark.integration
async def test_cache_multiple_metrics_and_get_multiple(connected_redis, sample_metrics):
    """cache_multiple_metrics then get_multiple_metrics returns data for each symbol."""
    items = [
        {**sample_metrics, "symbol": "BTCUSDT", "mid_price": 50000.0},
        {**sample_metrics, "symbol": "ETHUSDT", "mid_price": 3000.0},
        {**sample_metrics, "symbol": "SOLUSDT", "mid_price": 100.0},
    ]
    count = await connected_redis.cache_multiple_metrics(items, ttl=60)
    assert count == 3
    result = await connected_redis.get_multiple_metrics(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    assert result["BTCUSDT"] is not None
    assert result["ETHUSDT"] is not None
    assert result["SOLUSDT"] is not None
    assert result["BTCUSDT"]["mid_price"] == 50000.0
    assert result["ETHUSDT"]["mid_price"] == 3000.0


@pytest.mark.integration
async def test_get_multiple_metrics_mixed_miss(connected_redis, sample_metrics):
    """get_multiple_metrics returns None for uncached symbols."""
    await connected_redis.insert_metrics("BTCUSDT", sample_metrics, ttl=60)
    result = await connected_redis.get_multiple_metrics(["BTCUSDT", "MISSINGUSDT"])
    assert result["BTCUSDT"] is not None
    assert result["MISSINGUSDT"] is None


@pytest.mark.integration
async def test_insert_metrics_when_disconnected_returns_false(redis_client, sample_metrics):
    """insert_metrics returns False when not connected."""
    ok = await redis_client.insert_metrics("BTCUSDT", sample_metrics, ttl=60)
    assert ok is False


@pytest.mark.integration
async def test_get_cached_metrics_when_disconnected_returns_none(redis_client):
    """get_cached_metrics returns None when not connected."""
    result = await redis_client.get_cached_metrics("BTCUSDT")
    assert result is None


# ----- TTL expiration ----- #


@pytest.mark.integration
async def test_metrics_ttl_set_on_key(connected_redis, sample_metrics):
    """insert_metrics sets TTL on the key; TTL is positive and <= requested."""
    symbol = "TTLCHECK"
    ttl_requested = 120
    await connected_redis.insert_metrics(symbol, sample_metrics, ttl=ttl_requested)
    key = RedisClient._metrics_key(symbol)
    actual_ttl = await connected_redis.client.ttl(key)
    assert actual_ttl > 0
    assert actual_ttl <= ttl_requested


@pytest.mark.integration
async def test_orderbook_ttl_set_on_key(connected_redis, sample_orderbook):
    """cache_orderbook sets TTL on the key."""
    symbol = sample_orderbook["symbol"]
    ttl_requested = 45
    await connected_redis.cache_orderbook(symbol, sample_orderbook, ttl=ttl_requested)
    key = RedisClient._snapshot_key(symbol)
    actual_ttl = await connected_redis.client.ttl(key)
    assert actual_ttl > 0
    assert actual_ttl <= ttl_requested


@pytest.mark.integration
async def test_stats_ttl_set_on_key(connected_redis, sample_stats):
    """cache_statistics sets TTL on the key."""
    symbol = sample_stats["symbol"]
    ttl_requested = 300
    await connected_redis.cache_statistics(symbol, sample_stats, ttl=ttl_requested)
    key = RedisClient._stats_key(symbol)
    actual_ttl = await connected_redis.client.ttl(key)
    assert actual_ttl > 0
    assert actual_ttl <= ttl_requested


@pytest.mark.integration
async def test_alerts_key_has_ttl(connected_redis, sample_alert):
    """add_alert sets TTL on the alerts list key (1 hour)."""
    symbol = sample_alert["symbol"]
    await connected_redis.add_alert(symbol, sample_alert, max_alerts=10)
    key = RedisClient._alerts_key(symbol)
    actual_ttl = await connected_redis.client.ttl(key)
    assert actual_ttl > 0
    assert actual_ttl <= 3600


@pytest.mark.integration
async def test_expired_key_returns_none(connected_redis, sample_metrics):
    """After key expires (or we set 1s TTL and wait), get returns None."""
    symbol = "EXPIREME"
    await connected_redis.insert_metrics(symbol, sample_metrics, ttl=1)
    # Key exists immediately
    cached = await connected_redis.get_cached_metrics(symbol)
    assert cached is not None
    # Force expire the key
    key = RedisClient._metrics_key(symbol)
    await connected_redis.client.expire(key, 0)
    # Now get should return None
    cached_after = await connected_redis.get_cached_metrics(symbol)
    assert cached_after is None


# ----- Cleanup / utility ----- #


@pytest.mark.integration
async def test_delete_key_removes_value(connected_redis, sample_metrics):
    """delete_key removes the key; get_cached_metrics then returns None."""
    symbol = "DELME"
    await connected_redis.insert_metrics(symbol, sample_metrics, ttl=60)
    assert await connected_redis.get_cached_metrics(symbol) is not None
    key = RedisClient._metrics_key(symbol)
    deleted = await connected_redis.delete_key(key)
    assert deleted is True
    assert await connected_redis.get_cached_metrics(symbol) is None


@pytest.mark.integration
async def test_health_check_when_connected(connected_redis):
    """health_check returns True when connected."""
    assert await connected_redis.health_check() is True


@pytest.mark.integration
async def test_health_check_when_disconnected(redis_client):
    """health_check returns False when not connected."""
    assert await redis_client.health_check() is False

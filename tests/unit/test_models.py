from datetime import datetime

import pytest
from pydantic import ValidationError

from src.common.models import (
    Alert,
    AlertType,
    OrderBookLevel,
    OrderBookMetrics,
    OrderBookSnapshot,
    Severity,
    Side,
)


# ----- Valid creation -----

def test_valid_order_book_level():
    level = OrderBookLevel(price=89.43, volume=538)
    assert level.price == 89.43
    assert level.volume == 538


def test_valid_order_book_level_small_positive_values():
    level = OrderBookLevel(price=0.01, volume=0.001)
    assert level.price == 0.01
    assert level.volume == 0.001


def test_valid_order_book_level_large_values():
    level = OrderBookLevel(price=1e6, volume=1e9)
    assert level.price == 1e6
    assert level.volume == 1e9


# ----- Invalid price -----

def test_order_book_level_rejects_zero_price():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(price=0.0, volume=1.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("price",) for e in errors)


def test_order_book_level_rejects_negative_price():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(price=-10.5, volume=1.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("price",) for e in errors)


# ----- Invalid volume -----

def test_order_book_level_rejects_zero_volume():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(price=100.0, volume=0.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("volume",) for e in errors)


def test_order_book_level_rejects_negative_volume():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(price=100.0, volume=-5.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("volume",) for e in errors)


# ----- validate_assignment -----

def test_order_book_level_validates_assignment():
    level = OrderBookLevel(price=100.0, volume=10.0)
    level.price = 200.0
    level.volume = 20.0
    assert level.price == 200.0
    assert level.volume == 20.0


def test_order_book_level_rejects_invalid_assignment_price():
    level = OrderBookLevel(price=100.0, volume=10.0)
    with pytest.raises(ValidationError):
        level.price = -1.0


def test_order_book_level_rejects_invalid_assignment_volume():
    level = OrderBookLevel(price=100.0, volume=10.0)
    with pytest.raises(ValidationError):
        level.volume = 0.0


# ----- Serialization -----

def test_order_book_level_model_dump():
    level = OrderBookLevel(price=50.5, volume=2.5)
    data = level.model_dump()
    assert data == {"price": 50.5, "volume": 2.5}


def test_order_book_level_from_dict():
    data = {"price": 99.99, "volume": 3.14}
    level = OrderBookLevel.model_validate(data)
    assert level.price == 99.99
    assert level.volume == 3.14


# ----- Missing required fields -----

def test_order_book_level_requires_price():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(volume=1.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("price",) for e in errors)


def test_order_book_level_requires_volume():
    with pytest.raises(ValidationError) as exc_info:
        OrderBookLevel(price=1.0)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("volume",) for e in errors)


# =============================================================================
# OrderBookSnapshot
# =============================================================================


def _snapshot_bids_asks():
    """Minimal valid bids/asks for OrderBookSnapshot."""
    return (
        [(50000.0, 1.5), (49999.0, 2.0)],
        [(50001.0, 1.2), (50002.0, 1.8)],
    )


# ----- Valid creation -----


def test_order_book_snapshot_valid_creation():
    bids, asks = _snapshot_bids_asks()
    ts = datetime(2024, 1, 15, 12, 0, 0)
    snapshot = OrderBookSnapshot(
        timestamp=ts,
        symbol="BTCUSDT",
        bids=bids,
        asks=asks,
        update_id=12345,
    )
    assert snapshot.timestamp == ts
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.bids == bids
    assert snapshot.asks == asks
    assert snapshot.update_id == 12345


def test_order_book_snapshot_default_timestamp():
    bids, asks = _snapshot_bids_asks()
    before = datetime.now()
    snapshot = OrderBookSnapshot(symbol="ETHUSDT", bids=bids, asks=asks)
    after = datetime.now()
    assert before <= snapshot.timestamp <= after
    assert snapshot.update_id is None


def test_order_book_snapshot_symbol_uppercased():
    bids, asks = _snapshot_bids_asks()
    snapshot = OrderBookSnapshot(
        symbol="  btcusdt  ",
        bids=bids,
        asks=asks,
    )
    assert snapshot.symbol == "BTCUSDT"


# ----- Invalid symbol -----


def test_order_book_snapshot_rejects_empty_symbol():
    bids, asks = _snapshot_bids_asks()
    with pytest.raises(ValidationError) as exc_info:
        OrderBookSnapshot(symbol="", bids=bids, asks=asks)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("symbol",) for e in errors)


def test_order_book_snapshot_rejects_whitespace_only_symbol():
    bids, asks = _snapshot_bids_asks()
    with pytest.raises(ValidationError):
        OrderBookSnapshot(symbol="   ", bids=bids, asks=asks)


# ----- Invalid bids/asks -----


def test_order_book_snapshot_rejects_empty_bids():
    _, asks = _snapshot_bids_asks()
    with pytest.raises(ValidationError) as exc_info:
        OrderBookSnapshot(symbol="BTCUSDT", bids=[], asks=asks)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("bids",) for e in errors)


def test_order_book_snapshot_rejects_empty_asks():
    bids, _ = _snapshot_bids_asks()
    with pytest.raises(ValidationError) as exc_info:
        OrderBookSnapshot(symbol="BTCUSDT", bids=bids, asks=[])
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("asks",) for e in errors)


def test_order_book_snapshot_rejects_invalid_price_in_bids():
    bids = [(0.0, 1.0), (49999.0, 2.0)]  # first level has invalid price
    asks = [(50001.0, 1.2)]
    with pytest.raises(ValidationError) as exc_info:
        OrderBookSnapshot(symbol="BTCUSDT", bids=bids, asks=asks)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("bids",) for e in errors)


def test_order_book_snapshot_rejects_invalid_volume_in_asks():
    bids = [(50000.0, 1.5)]
    asks = [(50001.0, 0.0)]  # zero volume
    with pytest.raises(ValidationError) as exc_info:
        OrderBookSnapshot(symbol="BTCUSDT", bids=bids, asks=asks)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("asks",) for e in errors)


# ----- mid_price -----


def test_order_book_snapshot_mid_price():
    bids, asks = _snapshot_bids_asks()
    snapshot = OrderBookSnapshot(
        symbol="BTCUSDT",
        bids=bids,
        asks=asks,
    )
    # best_bid=50000.0, best_ask=50001.0 -> mid = 50000.5
    assert snapshot.mid_price == 50000.5


def test_order_book_snapshot_mid_price_raises_when_empty_bids():
    bids, asks = _snapshot_bids_asks()
    empty_bids_snapshot = OrderBookSnapshot.model_construct(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[],
        asks=asks,
    )
    with pytest.raises(ValueError, match="Cannot calculate mid-price"):
        _ = empty_bids_snapshot.mid_price


def test_order_book_snapshot_mid_price_raises_when_empty_asks():
    bids, asks = _snapshot_bids_asks()
    snapshot = OrderBookSnapshot.model_construct(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=bids,
        asks=[],
    )
    with pytest.raises(ValueError, match="Cannot calculate mid-price"):
        _ = snapshot.mid_price


# ----- spread -----


def test_order_book_snapshot_spread():
    bids, asks = _snapshot_bids_asks()
    snapshot = OrderBookSnapshot(symbol="BTCUSDT", bids=bids, asks=asks)
    # best_ask 50001.0 - best_bid 50000.0 = 1.0
    assert snapshot.spread == 1.0


def test_order_book_snapshot_spread_empty_sides_returns_zero():
    bids, asks = _snapshot_bids_asks()
    no_bids = OrderBookSnapshot.model_construct(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=[],
        asks=asks,
    )
    assert no_bids.spread == 0.0
    no_asks = OrderBookSnapshot.model_construct(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        bids=bids,
        asks=[],
    )
    assert no_asks.spread == 0.0


# ----- spread_bps -----


def test_order_book_snapshot_spread_bps():
    bids, asks = _snapshot_bids_asks()
    snapshot = OrderBookSnapshot(symbol="BTCUSDT", bids=bids, asks=asks)
    # spread=1.0, mid_price=50000.5 -> (1/50000.5)*10000 ≈ 0.199996...
    expected_bps = (1.0 / 50000.5) * 10000
    assert abs(snapshot.spread_bps - expected_bps) < 1e-6


def test_order_book_snapshot_spread_bps_zero_mid_returns_zero():
    snapshot = OrderBookSnapshot(
        symbol="BTCUSDT",
        bids=[(1.0, 1.0)],
        asks=[(1.0, 1.0)],  # mid = 1.0, spread = 0
    )
    # spread is 0 so spread_bps is 0; implementation also guards mid_price == 0
    assert snapshot.spread_bps == 0.0


# ----- Serialization -----


def test_order_book_snapshot_model_dump():
    bids, asks = _snapshot_bids_asks()
    ts = datetime(2024, 1, 15, 12, 0, 0)
    snapshot = OrderBookSnapshot(
        timestamp=ts,
        symbol="BTCUSDT",
        bids=bids,
        asks=asks,
        update_id=99,
    )
    data = snapshot.model_dump()
    assert data["timestamp"] == ts
    assert data["symbol"] == "BTCUSDT"
    assert data["bids"] == bids
    assert data["asks"] == asks
    assert data["update_id"] == 99


def test_order_book_snapshot_from_dict():
    bids, asks = _snapshot_bids_asks()
    ts = datetime(2024, 1, 15, 12, 0, 0)
    data = {
        "timestamp": ts,
        "symbol": "btcusdt",
        "bids": bids,
        "asks": asks,
        "update_id": 100,
    }
    snapshot = OrderBookSnapshot.model_validate(data)
    assert snapshot.timestamp == ts
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.bids == bids
    assert snapshot.asks == asks
    assert snapshot.update_id == 100


# =============================================================================
# OrderBookMetrics
# =============================================================================


def _metrics_required_fields():
    """Minimal required fields for OrderBookMetrics."""
    return {
        "timestamp": datetime(2024, 1, 15, 12, 0, 0),
        "symbol": "BTCUSDT",
        "mid_price": 50000.0,
        "best_bid": 49999.0,
        "best_ask": 50001.0,
        "imbalance_ratio": 0.65,
        "bid_volume": 100.5,
        "ask_volume": 85.3,
        "spread_bps": 2.5,
    }


# ----- Valid creation -----


def test_order_book_metrics_valid_creation_minimal():
    data = _metrics_required_fields()
    metrics = OrderBookMetrics(**data)
    assert metrics.timestamp == data["timestamp"]
    assert metrics.symbol == data["symbol"]
    assert metrics.mid_price == data["mid_price"]
    assert metrics.best_bid == data["best_bid"]
    assert metrics.best_ask == data["best_ask"]
    assert metrics.imbalance_ratio == data["imbalance_ratio"]
    assert metrics.bid_volume == data["bid_volume"]
    assert metrics.ask_volume == data["ask_volume"]
    assert metrics.spread_bps == data["spread_bps"]
    assert metrics.weighted_imbalance is None
    assert metrics.total_volume is None
    assert metrics.spread_abs is None
    assert metrics.update_id is None


def test_order_book_metrics_valid_creation_with_optionals():
    data = {
        **_metrics_required_fields(),
        "weighted_imbalance": 0.72,
        "total_volume": 185.8,
        "spread_abs": 2.0,
        "vtob_ratio": 0.15,
        "best_bid_volume": 10.0,
        "best_ask_volume": 8.0,
        "imbalance_velocity": 0.01,
        "depth_levels": 10,
        "update_id": 12345,
    }
    metrics = OrderBookMetrics(**data)
    assert metrics.weighted_imbalance == 0.72
    assert metrics.total_volume == 185.8
    assert metrics.spread_abs == 2.0
    assert metrics.vtob_ratio == 0.15
    assert metrics.best_bid_volume == 10.0
    assert metrics.best_ask_volume == 8.0
    assert metrics.imbalance_velocity == 0.01
    assert metrics.depth_levels == 10
    assert metrics.update_id == 12345


def test_order_book_metrics_symbol_uppercased():
    data = _metrics_required_fields()
    data["symbol"] = "  ethusdt  "
    metrics = OrderBookMetrics(**data)
    assert metrics.symbol == "ETHUSDT"


def test_order_book_metrics_imbalance_ratio_bounds():
    data = _metrics_required_fields()
    data["imbalance_ratio"] = -1.0
    metrics = OrderBookMetrics(**data)
    assert metrics.imbalance_ratio == -1.0
    data["imbalance_ratio"] = 1.0
    metrics = OrderBookMetrics(**data)
    assert metrics.imbalance_ratio == 1.0


# ----- Invalid required fields -----


def test_order_book_metrics_rejects_zero_mid_price():
    data = _metrics_required_fields()
    data["mid_price"] = 0.0
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mid_price",) for e in errors)


def test_order_book_metrics_rejects_negative_best_bid():
    data = _metrics_required_fields()
    data["best_bid"] = -1.0
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("best_bid",) for e in errors)


def test_order_book_metrics_rejects_imbalance_ratio_above_one():
    data = _metrics_required_fields()
    data["imbalance_ratio"] = 1.5
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("imbalance_ratio",) for e in errors)


def test_order_book_metrics_rejects_imbalance_ratio_below_minus_one():
    data = _metrics_required_fields()
    data["imbalance_ratio"] = -1.5
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("imbalance_ratio",) for e in errors)


def test_order_book_metrics_rejects_negative_bid_volume():
    data = _metrics_required_fields()
    data["bid_volume"] = -0.1
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("bid_volume",) for e in errors)


def test_order_book_metrics_rejects_negative_spread_bps():
    data = _metrics_required_fields()
    data["spread_bps"] = -1.0
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("spread_bps",) for e in errors)


# ----- Optional field constraints -----


def test_order_book_metrics_rejects_weighted_imbalance_above_one():
    data = {**_metrics_required_fields(), "weighted_imbalance": 1.5}
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("weighted_imbalance",) for e in errors)


def test_order_book_metrics_rejects_negative_total_volume():
    data = {**_metrics_required_fields(), "total_volume": -1.0}
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("total_volume",) for e in errors)


def test_order_book_metrics_rejects_depth_levels_below_one():
    data = {**_metrics_required_fields(), "depth_levels": 0}
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("depth_levels",) for e in errors)


# ----- validate_assignment -----


def test_order_book_metrics_validates_assignment():
    data = _metrics_required_fields()
    metrics = OrderBookMetrics(**data)
    metrics.imbalance_ratio = 0.0
    metrics.bid_volume = 50.0
    assert metrics.imbalance_ratio == 0.0
    assert metrics.bid_volume == 50.0


def test_order_book_metrics_rejects_invalid_assignment_mid_price():
    data = _metrics_required_fields()
    metrics = OrderBookMetrics(**data)
    with pytest.raises(ValidationError):
        metrics.mid_price = 0.0


def test_order_book_metrics_rejects_invalid_assignment_imbalance_ratio():
    data = _metrics_required_fields()
    metrics = OrderBookMetrics(**data)
    with pytest.raises(ValidationError):
        metrics.imbalance_ratio = 2.0


# ----- Serialization -----


def test_order_book_metrics_model_dump():
    data = _metrics_required_fields()
    data["update_id"] = 99
    metrics = OrderBookMetrics(**data)
    dumped = metrics.model_dump()
    assert dumped["timestamp"] == data["timestamp"]
    assert dumped["symbol"] == "BTCUSDT"
    assert dumped["mid_price"] == data["mid_price"]
    assert dumped["imbalance_ratio"] == data["imbalance_ratio"]
    assert dumped["spread_bps"] == data["spread_bps"]
    assert dumped["update_id"] == 99


def test_order_book_metrics_from_dict():
    data = {
        **_metrics_required_fields(),
        "symbol": "btcusdt",
        "update_id": 100,
    }
    metrics = OrderBookMetrics.model_validate(data)
    assert metrics.symbol == "BTCUSDT"
    assert metrics.update_id == 100


# ----- Missing required fields -----


def test_order_book_metrics_requires_timestamp():
    data = _metrics_required_fields()
    del data["timestamp"]
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("timestamp",) for e in errors)


def test_order_book_metrics_requires_symbol():
    data = _metrics_required_fields()
    del data["symbol"]
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("symbol",) for e in errors)


def test_order_book_metrics_requires_spread_bps():
    data = _metrics_required_fields()
    del data["spread_bps"]
    with pytest.raises(ValidationError) as exc_info:
        OrderBookMetrics(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("spread_bps",) for e in errors)


# =============================================================================
# Alert
# =============================================================================


def _alert_required_fields():
    """Minimal required fields for Alert."""
    return {
        "symbol": "BTCUSDT",
        "alert_type": AlertType.EXTREME_IMBALANCE,
        "severity": Severity.HIGH,
        "message": "Extreme buy pressure detected",
        "metric_value": 0.85,
    }


# ----- Valid creation -----


def test_alert_valid_creation_minimal():
    data = _alert_required_fields()
    alert = Alert(**data)
    assert alert.symbol == data["symbol"]
    assert alert.alert_type == data["alert_type"]
    assert alert.severity == data["severity"]
    assert alert.message == data["message"]
    assert alert.metric_value == data["metric_value"]
    assert alert.threshold_value is None
    assert alert.side is None
    assert alert.mid_price is None
    assert alert.imbalance_ratio is None
    assert alert.time is not None


def test_alert_valid_creation_with_optionals():
    data = {
        **_alert_required_fields(),
        "time": datetime(2024, 1, 15, 12, 0, 0),
        "threshold_value": 0.70,
        "side": Side.BID,
        "mid_price": 50000.0,
        "imbalance_ratio": 0.65,
    }
    alert = Alert(**data)
    assert alert.time == data["time"]
    assert alert.threshold_value == 0.70
    assert alert.side == Side.BID
    assert alert.mid_price == 50000.0
    assert alert.imbalance_ratio == 0.65


def test_alert_symbol_uppercased():
    data = _alert_required_fields()
    data["symbol"] = "  ethusdt  "
    alert = Alert(**data)
    assert alert.symbol == "ETHUSDT"


def test_alert_default_time():
    data = _alert_required_fields()
    before = datetime.now()
    alert = Alert(**data)
    after = datetime.now()
    assert before <= alert.time <= after


def test_alert_all_alert_types():
    for alert_type in AlertType:
        data = {**_alert_required_fields(), "alert_type": alert_type}
        alert = Alert(**data)
        assert alert.alert_type == alert_type


def test_alert_all_severities():
    for severity in Severity:
        data = {**_alert_required_fields(), "severity": severity}
        alert = Alert(**data)
        assert alert.severity == severity


# ----- Invalid / constraints -----


def test_alert_rejects_empty_message():
    data = _alert_required_fields()
    data["message"] = ""
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("message",) for e in errors)


def test_alert_rejects_negative_mid_price():
    data = {**_alert_required_fields(), "mid_price": -1.0}
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("mid_price",) for e in errors)


def test_alert_rejects_imbalance_ratio_above_one():
    data = {**_alert_required_fields(), "imbalance_ratio": 1.5}
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("imbalance_ratio",) for e in errors)


def test_alert_rejects_imbalance_ratio_below_minus_one():
    data = {**_alert_required_fields(), "imbalance_ratio": -1.5}
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("imbalance_ratio",) for e in errors)


def test_alert_accepts_imbalance_ratio_bounds():
    data = {**_alert_required_fields(), "imbalance_ratio": -1.0}
    alert = Alert(**data)
    assert alert.imbalance_ratio == -1.0
    data["imbalance_ratio"] = 1.0
    alert = Alert(**data)
    assert alert.imbalance_ratio == 1.0


# ----- Methods -----


def test_alert_is_critical():
    data = _alert_required_fields()
    data["severity"] = Severity.CRITICAL
    alert = Alert(**data)
    assert alert.is_critical() is True
    data["severity"] = Severity.HIGH
    alert = Alert(**data)
    assert alert.is_critical() is False


def test_alert_is_high_or_critical():
    data = _alert_required_fields()
    data["severity"] = Severity.HIGH
    alert = Alert(**data)
    assert alert.is_high_or_critical() is True
    data["severity"] = Severity.CRITICAL
    alert = Alert(**data)
    assert alert.is_high_or_critical() is True
    data["severity"] = Severity.MEDIUM
    alert = Alert(**data)
    assert alert.is_high_or_critical() is False


def test_alert_to_dict():
    data = {
        **_alert_required_fields(),
        "time": datetime(2024, 1, 15, 12, 0, 0),
        "threshold_value": 0.70,
    }
    alert = Alert(**data)
    d = alert.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["alert_type"] == AlertType.EXTREME_IMBALANCE.value  # use_enum_values=True
    assert d["severity"] == Severity.HIGH.value
    assert d["message"] == data["message"]
    assert d["metric_value"] == data["metric_value"]
    assert d["threshold_value"] == 0.70


# ----- validate_assignment -----


def test_alert_validates_assignment():
    data = _alert_required_fields()
    alert = Alert(**data)
    alert.message = "Updated message"
    alert.metric_value = 0.5
    assert alert.message == "Updated message"
    assert alert.metric_value == 0.5


def test_alert_rejects_invalid_assignment_imbalance_ratio():
    data = {**_alert_required_fields(), "imbalance_ratio": 0.0}
    alert = Alert(**data)
    with pytest.raises(ValidationError):
        alert.imbalance_ratio = 2.0


# ----- Serialization -----


def test_alert_model_dump():
    data = _alert_required_fields()
    data["threshold_value"] = 0.7
    alert = Alert(**data)
    dumped = alert.model_dump()
    assert dumped["symbol"] == "BTCUSDT"
    assert dumped["alert_type"] == AlertType.EXTREME_IMBALANCE
    assert dumped["severity"] == Severity.HIGH
    assert dumped["metric_value"] == data["metric_value"]
    assert dumped["threshold_value"] == 0.7


def test_alert_from_dict():
    data = {
        **_alert_required_fields(),
        "symbol": "btcusdt",
        "threshold_value": 0.7,
    }
    alert = Alert.model_validate(data)
    assert alert.symbol == "BTCUSDT"
    assert alert.threshold_value == 0.7


# ----- Missing required fields -----


def test_alert_requires_symbol():
    data = _alert_required_fields()
    del data["symbol"]
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("symbol",) for e in errors)


def test_alert_requires_message():
    data = _alert_required_fields()
    del data["message"]
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("message",) for e in errors)


def test_alert_requires_alert_type():
    data = _alert_required_fields()
    del data["alert_type"]
    with pytest.raises(ValidationError) as exc_info:
        Alert(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("alert_type",) for e in errors)


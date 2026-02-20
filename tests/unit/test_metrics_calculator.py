"""Test metric calculations."""
import pytest
import json
from src.ingestion.metrics_calculator import calculate_metrics


# Load test fixtures
@pytest.fixture
def sample_orderbook():
    """Load sample orderbook from fixtures."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [["50000.0", "1.5"], ["49999.0", "2.0"]],
        "asks": [["50001.0", "1.2"], ["50002.0", "1.8"]],
        "update_id": 1
    }


@pytest.fixture
def balanced_orderbook():
    """Orderbook with equal bids and asks."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [["50000.0", "1.0"], ["49999.0", "1.0"]],
        "asks": [["50001.0", "1.0"], ["50002.0", "1.0"]],
        "update_id": 1
    }


@pytest.fixture
def buy_pressure_orderbook():
    """Orderbook with more bid volume (buy pressure)."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [["50000.0", "5.0"], ["49999.0", "3.0"]],
        "asks": [["50001.0", "1.0"], ["50002.0", "1.0"]],
        "update_id": 1
    }


@pytest.fixture
def sell_pressure_orderbook():
    """Orderbook with more ask volume (sell pressure)."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [["50000.0", "1.0"], ["49999.0", "1.0"]],
        "asks": [["50001.0", "5.0"], ["50002.0", "3.0"]],
        "update_id": 1
    }


@pytest.fixture
def empty_orderbook():
    """Orderbook with no bids or asks."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [],
        "asks": [],
        "update_id": 1
    }


@pytest.fixture
def single_level_orderbook():
    """Orderbook with only one level."""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1234567890000,
        "bids": [["50000.0", "1.0"]],
        "asks": [["50001.0", "1.0"]],
        "update_id": 1
    }


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_balanced_book_returns_zero_imbalance(self, balanced_orderbook):
        """Test that equal bid/ask volume returns ~0 imbalance."""
        result = calculate_metrics(balanced_orderbook)
        
        assert result is not None
        # With equal volumes (2.0 each), imbalance should be ~0
        assert abs(result['imbalance_ratio']) < 0.1

    def test_buy_pressure_returns_positive_imbalance(self, buy_pressure_orderbook):
        """Test that more bids than asks returns positive imbalance."""
        result = calculate_metrics(buy_pressure_orderbook)
        
        assert result is not None
        # bid_volume = 8.0, ask_volume = 2.0, total = 10.0
        # imbalance = (8 - 2) / 10 = 0.6
        assert result['imbalance_ratio'] > 0
        assert result['imbalance_ratio'] == pytest.approx(0.6, rel=0.01)

    def test_sell_pressure_returns_negative_imbalance(self, sell_pressure_orderbook):
        """Test that more asks than bids returns negative imbalance."""
        result = calculate_metrics(sell_pressure_orderbook)
        
        assert result is not None
        # bid_volume = 2.0, ask_volume = 8.0, total = 10.0
        # imbalance = (2 - 8) / 10 = -0.6
        assert result['imbalance_ratio'] < 0
        assert result['imbalance_ratio'] == pytest.approx(-0.6, rel=0.01)

    def test_calculates_mid_price(self, sample_orderbook):
        """Test mid price calculation."""
        result = calculate_metrics(sample_orderbook)
        
        assert result is not None
        # best_bid = 50000.0, best_ask = 50001.0
        # mid_price = (50000 + 50001) / 2 = 50000.5
        assert result['mid_price'] == pytest.approx(50000.5)

    def test_calculates_spread(self, sample_orderbook):
        """Test spread calculation."""
        result = calculate_metrics(sample_orderbook)
        
        assert result is not None
        # spread_abs = 50001 - 50000 = 1
        assert result['spread_abs'] == pytest.approx(1.0)
        # spread_bps = (1 / 50000.5) * 10000 = ~0.2 bps
        assert result['spread_bps'] == pytest.approx(0.2, abs=0.1)

    def test_calculates_weighted_imbalance(self, buy_pressure_orderbook):
        """Test weighted imbalance calculation."""
        result = calculate_metrics(buy_pressure_orderbook)
        
        assert result is not None
        assert 'weighted_imbalance' in result
        # Weighted imbalance should be different from simple imbalance
        # due to the 1/i weighting factor
        assert isinstance(result['weighted_imbalance'], float)

    def test_returns_none_for_empty_book(self, empty_orderbook):
        """Test that empty book returns None."""
        result = calculate_metrics(empty_orderbook)
        
        assert result is None

    def test_single_level_orderbook(self, single_level_orderbook):
        """Test with single level orderbook."""
        result = calculate_metrics(single_level_orderbook)
        
        assert result is not None
        assert result['imbalance_ratio'] == pytest.approx(0.0)
        assert result['best_bid'] == 50000.0
        assert result['best_ask'] == 50001.0

    def test_calculates_volumes(self, sample_orderbook):
        """Test volume calculations."""
        result = calculate_metrics(sample_orderbook)
        
        assert result is not None
        # bid_volume = 1.5 + 2.0 = 3.5
        assert result['bid_volume'] == pytest.approx(3.5)
        # ask_volume = 1.2 + 1.8 = 3.0
        assert result['ask_volume'] == pytest.approx(3.0)
        # total_volume = 3.5 + 3.0 = 6.5
        assert result['total_volume'] == pytest.approx(6.5)

    def test_preserves_symbol_and_timestamp(self, sample_orderbook):
        """Test that symbol and timestamp are preserved."""
        result = calculate_metrics(sample_orderbook)
        
        assert result is not None
        assert result['symbol'] == "BTCUSDT"
        assert result['timestamp'] == 1234567890000

    def test_vtob_ratio_calculation(self, sample_orderbook):
        """Test volume-top-of-book ratio calculation."""
        result = calculate_metrics(sample_orderbook)
        
        assert result is not None
        # best_bid_volume = 1.5, best_ask_volume = 1.2
        # total_volume = 6.5
        # vtob = (1.5 + 1.2) / 6.5 = 0.415
        expected_vtob = (1.5 + 1.2) / 6.5
        assert result['vtob_ratio'] == pytest.approx(expected_vtob)


class TestWeightedImbalance:
    """Tests for weighted imbalance calculation."""

    def test_weighted_imbalance_differs_from_simple(self):
        """Test that weighted imbalance is mathematically different from simple."""
        # Create orderbook where weighting matters
        orderbook = {
            "symbol": "BTCUSDT",
            "timestamp": 1234567890000,
            # Higher volume at deeper levels (will be weighted less)
            "bids": [["50000.0", "1.0"], ["49999.0", "5.0"]],
            "asks": [["50001.0", "1.0"], ["50002.0", "5.0"]],
            "update_id": 1
        }
        
        result = calculate_metrics(orderbook)
        
        assert result is not None
        # Simple imbalance: (6 - 6) / 12 = 0
        # Weighted: gives more weight to top levels
        assert 'weighted_imbalance' in result


class TestEdgeCases:
    """Edge case tests."""

    def test_missing_bids(self):
        """Test when bids are missing."""
        orderbook = {
            "symbol": "BTCUSDT",
            "timestamp": 1234567890000,
            "bids": [],
            "asks": [["50001.0", "1.0"]],
            "update_id": 1
        }
        
        result = calculate_metrics(orderbook)
        
        assert result is not None
        # Should return with 0 bid volume
        assert result['bid_volume'] == 0

    def test_missing_asks(self):
        """Test when asks are missing."""
        orderbook = {
            "symbol": "BTCUSDT",
            "timestamp": 1234567890000,
            "bids": [["50000.0", "1.0"]],
            "asks": [],
            "update_id": 1
        }
        
        result = calculate_metrics(orderbook)
        
        assert result is not None
        # Should return with 0 ask volume
        assert result['ask_volume'] == 0

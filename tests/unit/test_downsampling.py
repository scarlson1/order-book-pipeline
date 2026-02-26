"""
Unit and integration tests for the refactored downsampling module.

Run with: pytest tests/unit/test_downsampling_refactored.py -v

Documentation:
- pytest: https://docs.pytest.org/
- dataclasses: https://docs.python.org/3/library/dataclasses.html
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, call

from src.ingestion.downsampling import (
    OrderbookLevel,
    OrderbookTick,
    MetricsAccumulator,
    MetricCalculator,
    TickBuffer,
    DownsampledMetric,
    OrderbookDownsampler,
)


# ===== FIXTURES =====

@pytest.fixture
def sample_binance_message():
    """Sample Binance WebSocket depth message."""
    return {
        'bids': [
            ['50000.00', '1.5'],
            ['49999.00', '2.0'],
            ['49998.00', '2.5'],
        ],
        'asks': [
            ['50001.00', '1.2'],
            ['50002.00', '1.8'],
            ['50003.00', '2.2'],
        ],
    }


@pytest.fixture
def sample_extreme_message():
    """Sample with extreme imbalance (all bids)."""
    return {
        'bids': [
            ['50000.00', '10.0'],
            ['49999.00', '10.0'],
            ['49998.00', '10.0'],
        ],
        'asks': [
            ['50001.00', '0.1'],
            ['50002.00', '0.1'],
            ['50003.00', '0.1'],
        ],
    }


@pytest.fixture
def sample_tight_spread_message():
    """Sample with tight spread."""
    return {
        'bids': [
            ['50000.00', '1.0'],
            ['49999.99', '1.0'],
            ['49999.98', '1.0'],
        ],
        'asks': [
            ['50000.01', '1.0'],
            ['50000.02', '1.0'],
            ['50000.03', '1.0'],
        ],
    }


@pytest.fixture
def downsampler_short_bucket():
    """Downsampler with short bucket for testing."""
    return OrderbookDownsampler(bucket_seconds=1, max_depth=10)


# ===== ORDERBOOK LEVEL TESTS =====

class TestOrderbookLevel:
    """Test OrderbookLevel dataclass."""
    
    def test_create_valid_level(self):
        """Test creating valid order book level."""
        level = OrderbookLevel(price=50000.0, quantity=1.5)
        assert level.price == 50000.0
        assert level.quantity == 1.5
    
    def test_invalid_price_zero(self):
        """Test that zero price is rejected."""
        with pytest.raises(ValueError):
            OrderbookLevel(price=0.0, quantity=1.5)
    
    def test_invalid_price_negative(self):
        """Test that negative price is rejected."""
        with pytest.raises(ValueError):
            OrderbookLevel(price=-1.0, quantity=1.5)
    
    def test_invalid_quantity_zero(self):
        """Test that zero quantity is rejected."""
        with pytest.raises(ValueError):
            OrderbookLevel(price=50000.0, quantity=0.0)
    
    def test_invalid_quantity_negative(self):
        """Test that negative quantity is rejected."""
        with pytest.raises(ValueError):
            OrderbookLevel(price=50000.0, quantity=-1.5)
    
    def test_level_is_immutable(self):
        """Test that OrderbookLevel is frozen."""
        level = OrderbookLevel(price=50000.0, quantity=1.5)
        with pytest.raises(Exception):  # FrozenInstanceError
            level.price = 50001.0


# ===== ORDERBOOK TICK TESTS =====

class TestOrderbookTick:
    """Test OrderbookTick dataclass."""
    
    def test_create_valid_tick(self, sample_binance_message):
        """Test creating valid tick from Binance message."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        assert tick.symbol is not None  # Created from_binance sets defaults
        assert len(tick.bids) == 3
        assert len(tick.asks) == 3
    
    def test_tick_properties(self, sample_binance_message):
        """Test tick calculated properties."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        
        # Should have bids descending and asks ascending
        bid_prices = [level.price for level in tick.bids]
        ask_prices = [level.price for level in tick.asks]
        
        assert bid_prices == sorted(bid_prices, reverse=True)
        assert ask_prices == sorted(ask_prices)
    
    def test_best_bid_best_ask(self, sample_binance_message):
        """Test best bid/ask properties."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        assert tick.best_bid == 50000.0
        assert tick.best_ask == 50001.0
    
    def test_mid_price(self, sample_binance_message):
        """Test mid price calculation."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        assert tick.mid_price == 50000.5
    
    def test_spread_bps(self, sample_binance_message):
        """Test spread calculation in basis points."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        # spread = (50001 - 50000) / 50000.5 * 10000
        expected_spread = (50001.0 - 50000.0) / 50000.5 * 10000
        assert abs(tick.spread_bps - expected_spread) < 0.01
    
    def test_tight_spread(self, sample_tight_spread_message):
        """Test with very tight spread."""
        tick = OrderbookTick.from_binance(sample_tight_spread_message)
        # spread = (50000.01 - 50000) / 50000.005 * 10000
        assert 0 < tick.spread_bps < 0.1  # Very tight
    
    def test_parse_depth_limit(self, sample_binance_message):
        """Test that max_depth is respected."""
        tick = OrderbookTick.from_binance(sample_binance_message, max_depth=2)
        assert len(tick.bids) <= 2
        assert len(tick.asks) <= 2
    
    def test_invalid_message_missing_bids(self):
        """Test that message without bids fails."""
        invalid = {'asks': [['50001.00', '1.0']]}
        with pytest.raises(ValueError):
            OrderbookTick.from_binance(invalid)
    
    def test_invalid_message_invalid_price(self):
        """Test that non-numeric price fails."""
        invalid = {
            'bids': [['invalid', '1.0']],
            'asks': [['50001.00', '1.0']],
        }
        with pytest.raises(ValueError):
            OrderbookTick.from_binance(invalid)


# ===== METRICS ACCUMULATOR TESTS =====

class TestMetricsAccumulator:
    """Test streaming statistics calculation with Welford's algorithm."""
    
    def test_single_value(self):
        """Test accumulator with single value."""
        acc = MetricsAccumulator()
        acc.add(5.0)
        
        assert acc.count == 1
        assert acc.mean == 5.0
        assert acc.min_value == 5.0
        assert acc.max_value == 5.0
        assert acc.std_dev == 0.0  # No variance with one value
    
    def test_two_values(self):
        """Test with two values."""
        acc = MetricsAccumulator()
        acc.add(2.0)
        acc.add(4.0)
        
        assert acc.count == 2
        assert acc.mean == 3.0
        assert acc.min_value == 2.0
        assert acc.max_value == 4.0
        assert abs(acc.variance - 2.0) < 0.001  # (2-3)^2 + (4-3)^2 / 1 = 2
    
    def test_multiple_values(self):
        """Test with multiple values."""
        acc = MetricsAccumulator()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        for v in values:
            acc.add(v)
        
        assert acc.count == 5
        assert acc.mean == 3.0
        assert acc.min_value == 1.0
        assert acc.max_value == 5.0
        assert acc.std_dev > 0
    
    def test_welford_accuracy(self):
        """Test accuracy of Welford's algorithm against standard calculation."""
        import statistics
        
        values = [1.5, 2.3, 4.1, 1.9, 5.2, 3.4]
        
        # Standard calculation
        std_expected = statistics.stdev(values)
        
        # Welford's algorithm
        acc = MetricsAccumulator()
        for v in values:
            acc.add(v)
        
        assert abs(acc.std_dev - std_expected) < 0.0001
    
    def test_to_dict(self):
        """Test dictionary export."""
        acc = MetricsAccumulator()
        for v in [1.0, 2.0, 3.0]:
            acc.add(v)
        
        d = acc.to_dict()
        assert 'count' in d
        assert 'mean' in d
        assert 'min' in d
        assert 'max' in d
        assert 'std_dev' in d


# ===== METRIC CALCULATOR TESTS =====

class TestMetricCalculator:
    """Test metric calculation logic."""
    
    def test_imbalance_balanced(self, sample_binance_message):
        """Test imbalance calculation with balanced order book."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        calc = MetricCalculator(max_depth=10)
        
        imbalance = calc.calculate_imbalance_ratio(tick)
        # bid_vol = 1.5 + 2.0 + 2.5 = 6.0
        # ask_vol = 1.2 + 1.8 + 2.2 = 5.2
        # imbalance = (6.0 - 5.2) / 11.2 = 0.071...
        assert 0 < imbalance < 1
    
    def test_imbalance_extreme_buy(self, sample_extreme_message):
        """Test imbalance with extreme buy pressure."""
        tick = OrderbookTick.from_binance(sample_extreme_message)
        calc = MetricCalculator(max_depth=10)
        
        imbalance = calc.calculate_imbalance_ratio(tick)
        # bid_vol = 30.0, ask_vol = 0.3
        # imbalance = (30 - 0.3) / 30.3 = 0.9802...
        assert imbalance > 0.95  # Very high imbalance
    
    def test_imbalance_range(self):
        """Test that imbalance is always between -1 and 1."""
        calc = MetricCalculator()
        
        # Test various scenarios
        for bid_qty in [0.1, 1.0, 10.0, 100.0]:
            for ask_qty in [0.1, 1.0, 10.0, 100.0]:
                tick = OrderbookTick(
                    timestamp=datetime.now(timezone.utc),
                    bids=(OrderbookLevel(50000.0, bid_qty),),
                    asks=(OrderbookLevel(50001.0, ask_qty),),
                )
                imbalance = calc.calculate_imbalance_ratio(tick)
                assert -1 <= imbalance <= 1, f"Imbalance {imbalance} out of range"
    
    def test_weighted_imbalance(self, sample_binance_message):
        """Test weighted imbalance calculation."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        calc = MetricCalculator(max_depth=10)
        
        weighted = calc.calculate_weighted_imbalance(tick)
        assert -1 <= weighted <= 1
    
    def test_vtob_ratio(self, sample_binance_message):
        """Test volume at top of book ratio."""
        tick = OrderbookTick.from_binance(sample_binance_message)
        calc = MetricCalculator(max_depth=10)
        
        vtob = calc.calculate_vtob_ratio(tick)
        # top = 1.5 + 1.2 = 2.7
        # total = 6.0 + 5.2 = 11.2
        # vtob = 2.7 / 11.2 = 0.241...
        assert 0 < vtob < 1
    
    def test_max_depth_respected(self, sample_binance_message):
        """Test that max_depth parameter is respected."""
        tick = OrderbookTick.from_binance(sample_binance_message, max_depth=10)
        
        calc_d1 = MetricCalculator(max_depth=1)
        calc_d2 = MetricCalculator(max_depth=2)
        calc_d3 = MetricCalculator(max_depth=3)
        
        imb1 = calc_d1.calculate_imbalance_ratio(tick)
        imb2 = calc_d2.calculate_imbalance_ratio(tick)
        imb3 = calc_d3.calculate_imbalance_ratio(tick)
        
        # With only 3 levels in tick, all should be same
        assert imb1 == imb2 == imb3


# ===== TICK BUFFER TESTS =====

class TestTickBuffer:
    """Test TickBuffer accumulation logic."""
    
    def test_add_tick_to_buffer(self, sample_binance_message):
        """Test adding tick to buffer."""
        buffer = TickBuffer(
            symbol='BTCUSDT',
            bucket_seconds=60,
            max_depth=10,
        )
        
        tick = OrderbookTick.from_binance(sample_binance_message)
        buffer.add_tick(tick)
        
        assert len(buffer.ticks) == 1
        assert buffer.imbalance_acc.count == 1
        assert buffer.spread_acc.count == 1
    
    def test_should_flush_new_buffer(self):
        """Test that new buffer shouldn't flush immediately."""
        buffer = TickBuffer(
            symbol='BTCUSDT',
            bucket_seconds=60,
            max_depth=10,
        )
        
        assert not buffer.should_flush()
    
    def test_should_flush_after_time(self):
        """Test flush detection after time passes."""
        buffer = TickBuffer(
            symbol='BTCUSDT',
            bucket_seconds=1,  # 1 second
            max_depth=10,
        )
        
        assert not buffer.should_flush()
        time.sleep(1.5)
        assert buffer.should_flush()
    
    def test_get_metric_from_buffer(self, sample_binance_message):
        """Test generating metric from buffer."""
        buffer = TickBuffer(
            symbol='BTCUSDT',
            bucket_seconds=60,
            max_depth=10,
        )
        
        tick = OrderbookTick.from_binance(sample_binance_message)
        buffer.add_tick(tick)
        
        metric = buffer.get_metric()
        
        assert isinstance(metric, DownsampledMetric)
        assert metric.symbol == 'BTCUSDT'
        assert metric.tick_count == 1
        assert -1 <= metric.imbalance_ratio_mean <= 1
    
    def test_reset_buffer(self, sample_binance_message):
        """Test buffer reset."""
        buffer = TickBuffer(
            symbol='BTCUSDT',
            bucket_seconds=60,
            max_depth=10,
        )
        
        tick = OrderbookTick.from_binance(sample_binance_message)
        buffer.add_tick(tick)
        assert len(buffer.ticks) == 1
        
        buffer.reset()
        assert len(buffer.ticks) == 0
        assert buffer.imbalance_acc.count == 0


# ===== DOWNSAMPLER TESTS =====

class TestOrderbookDownsampler:
    """Test main OrderbookDownsampler class."""
    
    def test_create_downsampler(self):
        """Test creating downsampler instance."""
        ds = OrderbookDownsampler(bucket_seconds=60, max_depth=10)
        assert ds.bucket_seconds == 60
        assert ds.max_depth == 10
    
    def test_add_tick(self, sample_binance_message):
        """Test adding tick to downsampler."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        
        assert 'BTCUSDT' in ds.buffers
        assert len(ds.buffers['BTCUSDT'].ticks) == 1
    
    def test_add_multiple_symbols(self, sample_binance_message):
        """Test adding ticks for multiple symbols."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        ds.add_tick('ETHUSDT', sample_binance_message)
        
        assert len(ds.buffers) == 2
        assert 'BTCUSDT' in ds.buffers
        assert 'ETHUSDT' in ds.buffers
    
    def test_should_flush(self, sample_binance_message):
        """Test flush readiness check."""
        ds = OrderbookDownsampler(bucket_seconds=1)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        assert not ds.should_flush('BTCUSDT')
        
        time.sleep(1.5)
        assert ds.should_flush('BTCUSDT')
    
    def test_flush_metric(self, sample_binance_message):
        """Test flushing metric."""
        ds = OrderbookDownsampler(bucket_seconds=1)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        time.sleep(1.5)
        
        metric = ds.flush('BTCUSDT')
        
        assert metric is not None
        assert metric.symbol == 'BTCUSDT'
        assert metric.tick_count >= 1
    
    def test_get_ready_metrics(self, sample_binance_message):
        """Test getting all ready metrics."""
        ds = OrderbookDownsampler(bucket_seconds=1)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        ds.add_tick('ETHUSDT', sample_binance_message)
        
        time.sleep(1.5)
        
        metrics = ds.get_ready_metrics()
        
        assert len(metrics) == 2
        assert metrics[0].symbol in ['BTCUSDT', 'ETHUSDT']
    
    def test_flush_all(self, sample_binance_message):
        """Test force flushing all buffers."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        ds.add_tick('ETHUSDT', sample_binance_message)
        
        # Force flush without waiting
        metrics = ds.flush_all()
        
        assert len(metrics) == 2
    
    def test_on_flush_callback(self, sample_binance_message):
        """Test flush callback invocation."""
        callback_mock = Mock()
        
        ds = OrderbookDownsampler(
            bucket_seconds=1,
            on_flush=callback_mock
        )
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        time.sleep(1.5)
        ds.flush('BTCUSDT')
        
        callback_mock.assert_called_once()
        metric = callback_mock.call_args[0][0]
        assert isinstance(metric, DownsampledMetric)
    
    def test_get_status(self, sample_binance_message):
        """Test status reporting."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        
        status = ds.get_status()
        
        assert 'elapsed_seconds' in status
        assert 'total_ticks_received' in status
        assert 'compression_ratio' in status
        assert 'active_symbols' in status
        assert status['active_symbols'] == 1
    
    def test_metrics_tracking(self, sample_binance_message):
        """Test internal metrics tracking."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        
        initial_ticks = ds.metrics_total_ticks
        
        ds.add_tick('BTCUSDT', sample_binance_message)
        
        assert ds.metrics_total_ticks > initial_ticks
    
    def test_repr(self, sample_binance_message):
        """Test string representation."""
        ds = OrderbookDownsampler(bucket_seconds=60)
        ds.add_tick('BTCUSDT', sample_binance_message)
        
        repr_str = repr(ds)
        assert 'OrderbookDownsampler' in repr_str
        assert 'bucket=60s' in repr_str


# ===== DOWNSAMPLED METRIC TESTS =====

class TestDownsampledMetric:
    """Test DownsampledMetric output format."""
    
    def test_to_dict(self):
        """Test converting metric to dictionary."""
        metric = DownsampledMetric(
            symbol='BTCUSDT',
            bucket_start=datetime.now(timezone.utc),
            bucket_end=datetime.now(timezone.utc) + timedelta(seconds=60),
            tick_count=1800,
            imbalance_ratio_mean=0.45,
            imbalance_ratio_min=0.05,
            imbalance_ratio_max=0.85,
            imbalance_ratio_std=0.12,
            weighted_imbalance=0.52,
            spread_bps_mean=2.3,
            spread_bps_min=1.1,
            spread_bps_max=5.2,
            spread_bps_std=0.8,
            vtob_ratio=0.15,
            price_open=50000.0,
            price_close=50001.5,
            price_high=50002.0,
            price_low=49999.5,
        )
        
        d = metric.to_dict()
        
        assert isinstance(d, dict)
        assert d['symbol'] == 'BTCUSDT'
        assert d['tick_count'] == 1800
        assert isinstance(d['bucket_start'], str)  # ISO format
    
    def test_to_dict_precision(self):
        """Test precision parameter in to_dict()."""
        metric = DownsampledMetric(
            symbol='BTCUSDT',
            bucket_start=datetime.now(timezone.utc),
            bucket_end=datetime.now(timezone.utc) + timedelta(seconds=60),
            imbalance_ratio_mean=0.123456789,
        )
        
        d = metric.to_dict(precision=2)
        
        # Should be rounded to 2 decimal places
        assert d['imbalance_ratio_mean'] == 0.12
    
    def test_to_dict_compact(self):
        """Test compact output format."""
        metric = DownsampledMetric(
            symbol='BTCUSDT',
            bucket_start=datetime.now(timezone.utc),
            bucket_end=datetime.now(timezone.utc),
            imbalance_ratio_mean=0.45,
            price_close=50000.5,
        )
        
        d = metric.to_dict_compact()
        
        # Should have fewer fields
        assert len(d) < len(metric.to_dict())
        assert 'symbol' in d
        assert 'price' in d


# ===== INTEGRATION TESTS =====

class TestDownsamplingIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_full_workflow(self, sample_binance_message):
        """Test complete workflow from tick to metric."""
        ds = OrderbookDownsampler(bucket_seconds=1, max_depth=10)
        
        # Add multiple ticks
        for _ in range(10):
            ds.add_tick('BTCUSDT', sample_binance_message)
            time.sleep(0.1)
        
        # Flush
        time.sleep(1)
        metrics = ds.get_ready_metrics()
        
        assert len(metrics) == 1
        assert metrics[0].tick_count == 10
    
    def test_multiple_symbols_independent(self, sample_binance_message):
        """Test that multiple symbols have independent buffers."""
        ds = OrderbookDownsampler(bucket_seconds=1)
        
        # Add different count of ticks to each symbol
        for i in range(5):
            ds.add_tick('BTCUSDT', sample_binance_message)
        
        for i in range(10):
            ds.add_tick('ETHUSDT', sample_binance_message)
        
        time.sleep(1.5)
        metrics = ds.get_ready_metrics()
        
        btc_metric = next((m for m in metrics if m.symbol == 'BTCUSDT'), None)
        eth_metric = next((m for m in metrics if m.symbol == 'ETHUSDT'), None)
        
        assert btc_metric.tick_count == 5
        assert eth_metric.tick_count == 10
    
    def test_stress_test(self, sample_binance_message):
        """Test with high volume of ticks."""
        ds = OrderbookDownsampler(bucket_seconds=1)
        
        # Simulate 1000 ticks
        start = time.time()
        for _ in range(1000):
            ds.add_tick('BTCUSDT', sample_binance_message)
        elapsed = time.time() - start
        
        # Should be fast (< 1 second for 1000 ticks)
        assert elapsed < 1.0
        
        time.sleep(1.5)
        metrics = ds.get_ready_metrics()
        
        assert len(metrics) == 1
        assert metrics[0].tick_count == 1000


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
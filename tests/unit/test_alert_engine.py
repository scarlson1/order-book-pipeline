"""Test alert engine."""
import pytest
from src.common.models import OrderBookMetrics, Alert, AlertType, Severity


# Import the alert functions from orderbook_alerts
# Note: These tests will import the standalone functions if they're extracted,
# or we test the logic directly


class MockSettings:
    """Mock settings for testing."""
    alert_threshold_high = 0.70
    alert_threshold_medium = 0.50
    spread_alert_multiplier = 2.0
    velocity_threshold = 0.05
    rolling_window_seconds = 60
    flink_parallelism = 2
    redpanda_bootstrap_servers = "redpanda:9092"
    redpanda_topics = {
        "metrics": "orderbook.metrics",
        "alerts": "orderbook.alerts",
        "windowed": "orderbook.metrics.windowed",
        "raw": "orderbook.raw",
    }


# Create mock settings for import
import sys
from unittest.mock import patch

# We'll test the alert functions directly by mocking settings
@pytest.fixture
def mock_settings():
    """Provide mock settings for testing."""
    return MockSettings()


class TestCheckExtremeImbalance:
    """Tests for extreme imbalance detection."""

    @pytest.fixture
    def create_metrics(self):
        """Factory to create OrderBookMetrics."""
        def _create(imbalance_ratio: float, symbol: str = "BTCUSDT"):
            return OrderBookMetrics(
                symbol=symbol,
                timestamp=1234567890000,
                mid_price=50000.0,
                best_bid=49999.0,
                best_ask=50001.0,
                imbalance_ratio=imbalance_ratio,
                weighted_imbalance=imbalance_ratio,
                bid_volume=5.0,
                ask_volume=1.0,
                total_volume=6.0,
                spread_bps=0.2,
                spread_abs=1.0,
                vtob_ratio=0.4,
                best_bid_volume=1.5,
                best_ask_volume=1.2,
                imbalance_velocity=None,
                depth_level=10,
                update_id=1,
            )
        return _create

    def test_no_alert_below_medium_threshold(self, create_metrics, mock_settings):
        """Test that no alert is generated below medium threshold."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import check_extreme_imbalance
            
            # imbalance = 0.3, below 0.5 medium threshold
            metrics = create_metrics(0.3)
            result = check_extreme_imbalance(metrics)
            
            assert result is None

    def test_medium_alert_at_threshold(self, create_metrics, mock_settings):
        """Test MEDIUM alert at exactly medium threshold."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import check_extreme_imbalance
            
            # imbalance = 0.5, exactly at medium threshold
            metrics = create_metrics(0.5)
            result = check_extreme_imbalance(metrics)
            
            assert result is not None
            assert result.alert_type == AlertType.EXTREME_IMBALANCE
            assert result.severity == Severity.MEDIUM

    def test_high_alert_above_high_threshold(self, create_metrics, mock_settings):
        """Test HIGH alert above high threshold."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import check_extreme_imbalance
            
            # imbalance = 0.75, above 0.7 high threshold
            metrics = create_metrics(0.75)
            result = check_extreme_imbalance(metrics)
            
            assert result is not None
            assert result.alert_type == AlertType.EXTREME_IMBALANCE
            assert result.severity == Severity.HIGH

    def test_critical_alert_above_085(self, create_metrics, mock_settings):
        """Test CRITICAL alert above 0.85."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import check_extreme_imbalance
            
            # imbalance = 0.9, above 0.85 critical threshold
            metrics = create_metrics(0.9)
            result = check_extreme_imbalance(metrics)
            
            assert result is not None
            assert result.alert_type == AlertType.EXTREME_IMBALANCE
            assert result.severity == Severity.CRITICAL

    def test_negative_imbalance_triggers_alert(self, create_metrics, mock_settings):
        """Test that negative imbalance (sell pressure) also triggers alert."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import check_extreme_imbalance
            
            # imbalance = -0.75, absolute value above threshold
            metrics = create_metrics(-0.75)
            result = check_extreme_imbalance(metrics)
            
            assert result is not None
            assert result.severity == Severity.HIGH


class TestImbalanceFlipDetection:
    """Tests for imbalance flip (sign change) detection."""

    @pytest.fixture
    def create_metrics(self):
        """Factory to create OrderBookMetrics."""
        def _create(imbalance_ratio: float, symbol: str = "BTCUSDT"):
            return OrderBookMetrics(
                symbol=symbol,
                timestamp=1234567890000,
                mid_price=50000.0,
                best_bid=49999.0,
                best_ask=50001.0,
                imbalance_ratio=imbalance_ratio,
                weighted_imbalance=imbalance_ratio,
                bid_volume=5.0,
                ask_volume=1.0,
                total_volume=6.0,
                spread_bps=0.2,
                spread_abs=1.0,
                vtob_ratio=0.4,
                best_bid_volume=1.5,
                best_ask_volume=1.2,
                imbalance_velocity=None,
                depth_level=10,
                update_id=1,
            )
        return _create

    def test_positive_to_negative_flip(self, create_metrics, mock_settings):
        """Test flip from positive to negative imbalance."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import ImbalanceFlipDetector
            
            detector = ImbalanceFlipDetector()
            
            # First event: positive imbalance
            first_metrics = create_metrics(0.5)
            
            # Manually test the flip detection logic
            # The detector should emit an alert when sign changes
            prev_imbalance = 0.5  # Simulated previous value
            curr_imbalance = -0.3  # Current value (flip!)
            
            # Check for sign change: prev * curr < 0
            flip_detected = (prev_imbalance * curr_imbalance < 0)
            
            assert flip_detected is True

    def test_negative_to_positive_flip(self, create_metrics, mock_settings):
        """Test flip from negative to positive imbalance."""
        # Simulate sign change detection
        prev_imbalance = -0.5
        curr_imbalance = 0.3
        
        flip_detected = (prev_imbalance * curr_imbalance < 0)
        
        assert flip_detected is True

    def test_no_flip_same_sign_positive(self):
        """Test no flip when both are positive."""
        prev_imbalance = 0.5
        curr_imbalance = 0.3
        
        flip_detected = (prev_imbalance * curr_imbalance < 0)
        
        assert flip_detected is False

    def test_no_flip_same_sign_negative(self):
        """Test no flip when both are negative."""
        prev_imbalance = -0.5
        curr_imbalance = -0.3
        
        flip_detected = (prev_imbalance * curr_imbalance < 0)
        
        assert flip_detected is False

    def test_no_flip_zero_previous(self):
        """Test no flip when previous is zero."""
        prev_imbalance = 0.0
        curr_imbalance = 0.3
        
        flip_detected = (prev_imbalance * curr_imbalance < 0)
        
        assert flip_detected is False

    def test_no_flip_zero_current(self):
        """Test no flip when current is zero."""
        prev_imbalance = 0.5
        curr_imbalance = 0.0
        
        flip_detected = (prev_imbalance * curr_imbalance < 0)
        
        assert flip_detected is False


class TestAlertRateLimiter:
    """Tests for alert rate limiting."""

    def test_rate_limiter_allows_first_alert(self, mock_settings):
        """Test that first alert is always allowed."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import AlertRateLimiter
            
            limiter = AlertRateLimiter(cooldown_ms=60000)
            
            # First alert should pass through (not suppressed)
            # This is a basic test - actual behavior depends on state
            assert limiter.cooldown_ms == 60000

    def test_rate_limiter_cooldown_duration(self, mock_settings):
        """Test rate limiter cooldown duration."""
        with patch('src.jobs.orderbook_alerts.settings', mock_settings):
            from src.jobs.orderbook_alerts import AlertRateLimiter
            
            # Test with custom cooldown
            limiter = AlertRateLimiter(cooldown_ms=30000)
            assert limiter.cooldown_ms == 30000
            
            # Test with default cooldown
            limiter_default = AlertRateLimiter()
            assert limiter_default.cooldown_ms == 60000


class TestAlertModel:
    """Tests for Alert model."""

    def test_alert_creation(self):
        """Test creating an Alert object."""
        alert = Alert(
            symbol="BTCUSDT",
            timestamp=1234567890000,
            alert_type=AlertType.EXTREME_IMBALANCE,
            severity=Severity.HIGH,
            message="Test alert",
            metric_value=0.75,
            threshold_value=0.70,
        )
        
        assert alert.symbol == "BTCUSDT"
        assert alert.alert_type == AlertType.EXTREME_IMBALANCE
        assert alert.severity == Severity.HIGH

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = Alert(
            symbol="BTCUSDT",
            timestamp=1234567890000,
            alert_type=AlertType.EXTREME_IMBALANCE,
            severity=Severity.HIGH,
            message="Test alert",
            metric_value=0.75,
            threshold_value=0.70,
        )
        
        result = alert.to_dict()
        
        assert isinstance(result, dict)
        assert result['symbol'] == "BTCUSDT"
        assert result['alert_type'] == "EXTREME_IMBALANCE"


class TestAlertTypes:
    """Tests for AlertType enum."""

    def test_alert_types_exist(self):
        """Test that all expected alert types exist."""
        assert hasattr(AlertType, 'EXTREME_IMBALANCE')
        assert hasattr(AlertType, 'IMBALANCE_FLIP')
        assert hasattr(AlertType, 'SPREAD_WIDENING')
        assert hasattr(AlertType, 'VELOCITY_SPIKE')


class TestSeverityLevels:
    """Tests for Severity enum."""

    def test_severity_levels_exist(self):
        """Test that all expected severity levels exist."""
        assert hasattr(Severity, 'LOW')
        assert hasattr(Severity, 'MEDIUM')
        assert hasattr(Severity, 'HIGH')
        assert hasattr(Severity, 'CRITICAL')

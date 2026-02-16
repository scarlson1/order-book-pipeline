"""Pydantic data models."""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Tuple, Optional
from datetime import datetime
from enum import Enum

# ===== ENUMS =====

# Reference: https://docs.pydantic.dev/latest/concepts/types/#enums

class AlertType(str, Enum):
    EXTREME_IMBALANCE = 'EXTREME_IMBALANCE'
    IMBALANCE_FLIP = 'IMBALANCE_FLIP'
    SPREAD_WIDENING = "SPREAD_WIDENING"
    VELOCITY_SPIKE = "VELOCITY_SPIKE"
    UNUSUAL_VOLUME = "UNUSUAL_VOLUME"

class Severity(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'

class Side(str, Enum):
    """Order book side."""
    BID = "BID"
    ASK = "ASK"

# ===== Order Book Models =====

class OrderBookLevel(BaseModel):
    price: float = Field(..., gt=0, description="Price level")
    volume: float = Field(..., gt=0, description="Volume at this price")

    model_config = ConfigDict(
        frozen=False,  # Allow mutation if needed
        str_strip_whitespace=True,
        validate_assignment=True  # Validate on assignment too
    )

    @field_validator('price', 'volume')
    @classmethod
    def validate_positive(cls, v: float) -> float:
        """Ensure price and volume are not negative.
        
        Reference: https://docs.pydantic.dev/latest/concepts/validators/#field-validators
        """
        if v < 0:
            raise ValueError(f"Value must be positive, got {v}")
        return v

class OrderBookSnapshot(BaseModel):
    """Complete order book snapshot at a point in time.
    
    Documentation:
    - Model Config: https://docs.pydantic.dev/latest/concepts/config/
    - Datetime: https://docs.pydantic.dev/latest/concepts/types/#datetime-types
    
    Example:
        >>> snapshot = OrderBookSnapshot(
        ...     timestamp=datetime.now(),
        ...     symbol="BTCUSDT",
        ...     bids=[(50000.0, 1.5), (49999.0, 2.0)],
        ...     asks=[(50001.0, 1.2), (50002.0, 1.8)],
        ...     update_id=12345
        ... )
        >>> print(snapshot.mid_price)
        50000.5
    """
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of the snapshot"
    )
    symbol: str = Field(..., min_length=1, description="Trading symbol (e.g., BTCUSDT)")
    bids: List[Tuple[float, float]] = Field(
        ...,
        description="List of bid levels [(price, volume), ...]"
    ) # (price, volume) # List[OrderBookLevel]
    asks: List[Tuple[float, float]] = Field(
        ...,
        description="List of ask levels [(price, volume), ...]"
    )
    update_id: Optional[int] = Field(
        None,
        description="Exchange update ID for tracking"
    )

    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase and not empty.
        
        Reference: https://docs.pydantic.dev/latest/concepts/validators/
        """
        if not v or not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.strip().upper()
    
    @field_validator('bids', 'asks')
    @classmethod
    def validate_levels(cls, v: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Validate that all price levels are valid.
        
        Reference: https://docs.pydantic.dev/latest/concepts/validators/#field-validators
        """
        if not v:
            raise ValueError("Order book side cannot be empty")
        
        for price, volume in v:
            if price <= 0:
                raise ValueError(f"Invalid price: {price}")
            if volume <= 0:
                raise ValueError(f"Invalid volume: {volume}")
        
        return v

    @property
    def mid_price(self) -> float:
        """Calculate mid-price (average of best bid and ask).
        
        Reference: https://docs.pydantic.dev/latest/concepts/models/#properties
        
        Returns:
            Mid-price between best bid and ask
        """
        if not self.bids or not self.asks:
            raise ValueError("Cannot calculate mid-price: empty order book")
        
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        return (best_bid + best_ask) / 2

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread.
        
        Returns:
            Absolute spread between best bid and ask
        """
        if not self.bids or not self.asks:
            return 0.0
        
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        return best_ask - best_bid
    
    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points.
        
        Returns:
            Spread as basis points (1/10000 of price)
        """
        if self.mid_price == 0:
            return 0.0
        return (self.spread / self.mid_price) * 10000

# ===== Metrics Models =====

class OrderBookMetrics(BaseModel):
    """Calculated metrics from order book snapshot.
    
    Contains all computed indicators and imbalance measures.
    
    Documentation:
    - Optional Fields: https://docs.pydantic.dev/latest/concepts/fields/#optional-fields
    - Field Constraints: https://docs.pydantic.dev/latest/concepts/fields/#numeric-constraints
    
    Example:
        >>> metrics = OrderBookMetrics(
        ...     timestamp=datetime.now(),
        ...     symbol="BTCUSDT",
        ...     mid_price=50000.0,
        ...     imbalance_ratio=0.65,
        ...     weighted_imbalance=0.72,
        ...     spread_bps=2.5,
        ...     bid_volume=100.5,
        ...     ask_volume=85.3
        ... )
        >>> print(f"Imbalance: {metrics.imbalance_ratio:.2%}")
        Imbalance: 65.00%
    """
    # required fields
    timestamp: datetime = Field(..., description="Metric timestamp")
    symbol: str = Field(..., description="Trading symbol")
    mid_price: float = Field(..., gt=0, description="Mid-price")
    
    # Price data
    best_bid: float = Field(..., gt=0, description="Best bid price")
    best_ask: float = Field(..., gt=0, description="Best ask price")

    # Imbalance metrics
    imbalance_ratio: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Basic imbalance ratio (-1 to 1)"
    )
    weighted_imbalance: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Distance-weighted imbalance"
    )

    # Volume metrics
    bid_volume: float = Field(..., ge=0, description="Total bid volume")
    ask_volume: float = Field(..., ge=0, description="Total ask volume")
    total_volume: Optional[float] = Field(None, ge=0, description="Total volume")
    
    # Spread metrics
    spread_bps: float = Field(..., ge=0, description="Spread in basis points")
    spread_abs: Optional[float] = Field(None, ge=0, description="Absolute spread")

    # Top of book metrics
    vtob_ratio: Optional[float] = Field(
        None,
        description="Volume at top of book ratio"
    )
    best_bid_volume: Optional[float] = Field(None, ge=0)
    best_ask_volume: Optional[float] = Field(None, ge=0)

    # Velocity and derivatives
    imbalance_velocity: Optional[float] = Field(
        None,
        description="Rate of change in imbalance"
    )

    # Metadata
    depth_levels: Optional[int] = Field(None, ge=1, description="Depth used")
    update_id: Optional[int] = Field(None, description="Update ID")

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-01T12:00:00Z",
                "symbol": "BTCUSDT",
                "mid_price": 50000.0,
                "imbalance_ratio": 0.65,
                "spread_bps": 2.5
            }
        }
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.strip().upper()

# ===== Alert Models =====

class Alert(BaseModel):
    """Alert generated when conditions are met.
    
    Serialization: https://docs.pydantic.dev/latest/concepts/serialization/
    
    Example:
        >>> alert = Alert(
        ...     timestamp=datetime.now(),
        ...     symbol="BTCUSDT",
        ...     alert_type=AlertType.EXTREME_IMBALANCE,
        ...     severity=Severity.HIGH,
        ...     message="Extreme buy pressure detected",
        ...     metric_value=0.85,
        ...     threshold_value=0.70,
        ...     side=Side.BID
        ... )
        >>> alert.is_critical()
        False
    """
    time: datetime = Field(default_factory=datetime.now)
    symbol: str = Field(..., description="Trading symbol")

    # alert details
    alert_type: AlertType = Field(..., description="Type of alert")
    severity: Severity = Field(..., description="Alert severity")
    message: str = Field(..., min_length=1, description="Human-readable message")

    # metrics
    metric_value: float = Field(..., description="Current metric value")
    threshold_value: Optional[float] = Field(None, description="Threshold that triggered")

    # context
    side: Optional[Side] = Field(None, description="Which side (bid/ask)")
    mid_price: Optional[float] = Field(None, gt=0, description="Price at alert time")
    imbalance_ratio: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Basic imbalance ratio"
    )

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True  # Serialize enums as values
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.strip().upper()

    def is_critical(self) -> bool:
        """Check if alert is critical severity."""
        return self.severity == Severity.CRITICAL
    
    def is_high_or_critical(self) -> bool:
        """Check if alert is high or critical."""
        return self.severity in (Severity.HIGH, Severity.CRITICAL)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage.
        
        Reference: https://docs.pydantic.dev/latest/concepts/serialization/#modelmodel_dump
        
        Returns:
            Dictionary representation
        """
        return self.model_dump(mode='json')

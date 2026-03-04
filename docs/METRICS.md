# Metric Definitions

This document defines all metrics calculated by the order book pipeline.

## Overview

The pipeline calculates real-time order book imbalance metrics from raw order book data streamed via WebSocket (Binance) and published to Redpanda Kafka topics. Metrics are computed in real-time using a PyFlink streaming job.

## Configuration Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CALCULATE_DEPTH` | 10 | Number of order book levels (depth) to include in calculations |
| `ROLLING_WINDOW_SECONDS` | 60 | Window size in seconds for velocity/time-series calculations |
| `CALCULATE_VELOCITY` | true | Enable/disable velocity calculations |
| `ALERT_THRESHOLD_HIGH` | 0.70 | High imbalance alert threshold (70%) |
| `ALERT_THRESHOLD_MEDIUM` | 0.50 | Medium imbalance alert threshold (50%) |
| `SPREAD_ALERT_MULTIPLIER` | 2.0 | Alert multiplier for spread anomalies (2x normal) |
| `VELOCITY_THRESHOLD` | 0.05 | Threshold for rapid price changes (0.05) |

---

## Market Metrics

### `mid_price`

The midpoint price between the best bid and best ask.

**Formula:**
```
mid_price = (best_bid + best_ask) / 2
```

**Interpretation:**
The theoretical fair value of the asset where buy and sell orders meet. Used as a reference point for other calculations.

---

### `best_bid`

The highest price at which a buyer is willing to purchase the asset.

**Interpretation:**
The top of the bid side of the order book. Represents immediate market demand at this price level.

---

### `best_ask`

The lowest price at which a seller is willing to sell the asset.

**Interpretation:**
The top of the ask side of the order book. Represents immediate market supply at this price level.

---

### `spread_abs`

The absolute difference between best ask and best bid prices.

**Formula:**
```
spread_abs = best_ask - best_bid
```

**Interpretation:**
The raw price difference between buy and sell orders. Higher spread indicates lower liquidity or higher market volatility.

---

### `spread_bps`

The spread expressed in basis points (basis points = 1/100th of 1%).

**Formula:**
```
spread_bps = (spread_abs / mid_price) * 10000
         = ((best_ask - best_bid) / mid_price) * 10000
```

**Interpretation:**
Normalized spread measurement that allows comparison across assets with different price levels. Useful for detecting unusual spread widening events.

---

### `bid_volume`

Total volume of all bid orders within the configured depth.

**Formula:**
```
bid_volume = \sum(bid_volume_i) for i in 1 to calculate_depth
```

**Interpretation:**
Total buy-side liquidity available at the top levels of the order book. Higher values indicate strong buying interest.

---

### `ask_volume`

Total volume of all ask orders within the configured depth.

**Formula:**
```
ask_volume = \sum(ask_volume_i) for i in 1 to calculate_depth
```

**Interpretation:**
Total sell-side liquidity available at the top levels of the order book. Higher values indicate strong selling interest.

---

### `total_volume`

Combined bid and ask volume within the configured depth.

**Formula:**
```
total_volume = bid_volume + ask_volume
```

**Interpretation:**
Total market liquidity (both buy and sell sides) at the top levels of the order book.

---

## Imbalance Metrics

### `imbalance_ratio`

Order book imbalance ratio measuring bias between bid and ask volume.

**Formula:**
```
imbalance_ratio = (bid_volume - ask_volume) / total_volume
                = (\sum bid_volumes - \sum ask_volumes) / (\sum bid_volumes + \sum ask_volumes)
```

Expanded form:
```
imbalance_ratio =
    (v_b1 + v_b2 + ... + v_bd -
     a1 + a2 + ... + ad)) /
    ((v_b1 + v_b2 + ... + vd) + (a1 + a2 + ... + ad))
```

**Interpretation:**
- **Positive value (> 0)**: More buying pressure than selling pressure. Bullish signal.
- **Negative value (< 0)**: More selling pressure than buying pressure. Bearish signal.
- **Zero (0)**: Neutral balance between buy and sell orders.
- **Range**: [-1, 1]

**Thresholds:**
| Value | Severity | Interpretation |
|-------|----------------|----------------|
| \u2265 0.70 | High Alert | Strong bullish pressure - potential price upward movement |
| \u2265 0.50 | Medium Alert | Moderate bullish pressure |
| \u2264 -0.70 | High Alert | Strong bearish pressure - potential price downward movement |
| \u2264 -0.50 | Medium Alert | Moderate bearish pressure |

---

### `weighted_imbalance`

Weighted order book imbalance that gives less weight to deeper levels in the order book.

**Formula:**
```
weighted_bid_vol = \sum(bid_volume_i * w_i) for i in 1 to calculate_depth
where:           w_i = 1 / i

weighted_ask_vol = \sum(ask_volume_i * w_i) for i in 1 to calculate_depth

weighted_total_vol = weighted_bid_vol + weighted_ask_vol

weighted_imbalance = (weighted_bid_vol - weighted_ask_vol) / weighted_total_vol
```

Expanded:
```
weighted_bid_vol = v_b1/1 + v_b2/2 + v_b3/3 + ... + v_bd/d
weighted_ask_vol = a1/1 + a2/2 + a3/3 + ... + ad/d
```

**Interpretation:**
Similar to `imbalance_ratio` but prioritizes top-of-book liquidity. This metric is generally more responsive to immediate price impact since it weights the best prices most heavily.
- **Use case**: Better for detecting short-term momentum changes.
- **Range**: [-1, 1]

---

### `vtob_ratio` (Volume to Best Ask/Bid Ratio)

The proportion of volume at the best levels relative to total book volume.

**Formula:**
```
vtob_ratio = (best_bid_volume + best_ask_volume) / total_volume
```

**Interpretation:**
- **High ratio (close to 1)**: Volume is concentrated at top-of-book - thin book, potentially fragile price.
- **Low ratio**: Volume distributed across multiple levels - deep book, more stable price.

---

## Advanced Metrics (Planned)

### `imbalance_velocity`

Rate of change of imbalance over time (currently `None` in calculation).

**Formula (planned):**
```
imbalance_velocity = current_imbalance - previous_imbalance
                    / (current_timestamp - previous_timestamp)
```

**Interpretation:**
Measures how quickly order book pressure is changing. Rapid velocity changes can indicate:
- Large order cancellations
- Market impact events
- News-driven price movements

**Threshold:**
```env
VELOCITY_THRESHOLD=0.05
```
Alert when `abs(imbalance_velocity)` exceeds the threshold within the rolling window.

---

## Output Topics

Metrics are published to the following Redpanda Kafka topics:

| Topic | Description |
|-------|-------------|
| `{prefix}.metrics` | Processed order book metrics stream |
| `{prefix}.alerts` | Alert notifications (currently disabled in job) |
| `{prefix}.metrics.windowed` | Windowed aggregations (future) |

---

## Reference

### Calculation Depth

The number of order book levels included in calculations is configured via `CALCULATE_DEPTH` (default: 10). This determines how much "depth" above and below the mid-price is considered when computing imbalance metrics.

### Weighting Scheme

For weighted imbalance, each level `i` is weighted as `1/i`. This means:
- Level 1 (best price): weight = 1.0
- Level 2: weight = 0.5
- Level 3: weight = 0.33
- etc.

This exponential decay in weights reflects the typical market microstructure where liquidity and price impact diminish with distance from the mid-price.

# src/ingestion/downsampling.py
"""
Downsample raw order book ticks into 1-minute aggregated metrics.

This solves the storage problem with free tier databases when ingesting
live Binance data continuously. Instead of storing 30 inserts/second
(2.6 GB/day), we aggregate into 1-minute buckets and store 3 inserts/minute
(2 MB/day).

Usage:
    downsampler = OrderbookDownsampler(bucket_seconds=60)
    
    # For every Binance tick:
    downsampler.add_tick(symbol, raw_orderbook)
    
    # Periodically check and flush full buckets:
    if downsampler.should_flush(symbol, current_time):
        metric = downsampler.flush(symbol)
        await db.insert_metric(metric)
"""

import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class OrderbookTick:
    """Single order book snapshot from Binance"""
    timestamp: float
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]


@dataclass
class AggregatedMetric:
    """1-minute aggregated metric"""
    symbol: str
    bucket_timestamp: datetime
    tick_count: int
    avg_imbalance_ratio: float
    max_imbalance_ratio: float
    min_imbalance_ratio: float
    avg_spread_bps: float
    max_spread_bps: float
    min_spread_bps: float
    weighted_imbalance: float
    vtob_ratio: float


class OrderbookDownsampler:
    """
    Downsample raw Binance order book ticks into aggregated metrics.
    
    Maintains buffers per symbol and flushes them when they exceed
    the bucket size (default: 60 seconds = 1 minute).
    """
    
    def __init__(self, bucket_seconds: int = 60, depth: int = 10):
        """
        Initialize downsampler.
        
        Args:
            bucket_seconds: Size of aggregation bucket in seconds (default: 60)
            depth: Number of order book levels to use for calculations (default: 10)
        """
        self.bucket_seconds = bucket_seconds
        self.depth = depth
        
        # Buffers for each symbol
        self.buffers: Dict[str, List[OrderbookTick]] = defaultdict(list)
        
        # Metrics buffers for aggregation
        self.metrics_buffer: Dict[str, List[float]] = defaultdict(list)  # imbalance
        self.spreads_buffer: Dict[str, List[float]] = defaultdict(list)  # spreads
    
    def add_tick(self, symbol: str, raw_orderbook: dict) -> None:
        """
        Add a raw Binance order book tick to the buffer.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            raw_orderbook: Raw dict from Binance with 'bids', 'asks', etc.
        """
        tick = OrderbookTick(
            timestamp=time.time(),
            bids=self._parse_levels(raw_orderbook.get('bids', [])),
            asks=self._parse_levels(raw_orderbook.get('asks', []))
        )
        
        self.buffers[symbol].append(tick)
        
        # Calculate metrics for this tick
        imbalance = self._calculate_imbalance(tick)
        spread = self._calculate_spread(tick)
        
        self.metrics_buffer[symbol].append(imbalance)
        self.spreads_buffer[symbol].append(spread)
    
    def should_flush(self, symbol: str, current_time: Optional[float] = None) -> bool:
        """
        Check if buffer for symbol is ready to flush.
        
        Args:
            symbol: Trading pair
            current_time: Current timestamp (default: now)
            
        Returns:
            True if bucket is full (bucket_seconds have elapsed)
        """
        if symbol not in self.buffers or not self.buffers[symbol]:
            return False
        
        if current_time is None:
            current_time = time.time()
        
        oldest_tick = self.buffers[symbol][0]
        time_elapsed = current_time - oldest_tick.timestamp
        
        return time_elapsed >= self.bucket_seconds
    
    def flush(self, symbol: str) -> Optional[AggregatedMetric]:
        """
        Aggregate buffer and return metric. Clears the buffer.
        
        Args:
            symbol: Trading pair
            
        Returns:
            AggregatedMetric with 1-minute aggregated values, or None if empty
        """
        if symbol not in self.buffers or not self.buffers[symbol]:
            return None
        
        buffer = self.buffers[symbol]
        metrics = self.metrics_buffer[symbol]
        spreads = self.spreads_buffer[symbol]
        
        if not buffer:
            return None
        
        # Aggregate metrics
        metric = AggregatedMetric(
            symbol=symbol,
            bucket_timestamp=datetime.fromtimestamp(buffer[-1].timestamp),
            tick_count=len(buffer),
            avg_imbalance_ratio=statistics.mean(metrics),
            max_imbalance_ratio=max(metrics),
            min_imbalance_ratio=min(metrics),
            avg_spread_bps=statistics.mean(spreads),
            max_spread_bps=max(spreads),
            min_spread_bps=min(spreads),
            weighted_imbalance=self._calculate_weighted_imbalance(buffer),
            vtob_ratio=self._calculate_vtob_ratio(buffer),
        )
        
        # Clear buffers
        self.buffers[symbol] = []
        self.metrics_buffer[symbol] = []
        self.spreads_buffer[symbol] = []
        
        return metric
    
    def get_all_ready_metrics(self) -> List[AggregatedMetric]:
        """
        Get all metrics from symbols that are ready to flush.
        
        Returns:
            List of AggregatedMetric for all ready symbols
        """
        current_time = time.time()
        metrics = []
        
        for symbol in list(self.buffers.keys()):
            if self.should_flush(symbol, current_time):
                metric = self.flush(symbol)
                if metric:
                    metrics.append(metric)
        
        return metrics
    
    # Private methods for metric calculations
    
    def _parse_levels(self, levels: List[List]) -> List[List[float]]:
        """Parse price/quantity pairs from Binance format"""
        try:
            return [[float(price), float(qty)] for price, qty in levels[:self.depth]]
        except (ValueError, TypeError, IndexError):
            return []
    
    def _calculate_imbalance(self, tick: OrderbookTick) -> float:
        """
        Calculate bid-ask imbalance ratio.
        
        Formula: (bid_volume - ask_volume) / (bid_volume + ask_volume)
        Range: -1 to +1 (negative = more asks, positive = more bids)
        """
        if not tick.bids or not tick.asks:
            return 0.0
        
        bid_volume = sum(qty for _, qty in tick.bids)
        ask_volume = sum(qty for _, qty in tick.asks)
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / total
    
    def _calculate_spread(self, tick: OrderbookTick) -> float:
        """
        Calculate bid-ask spread in basis points.
        
        Formula: (ask_price - bid_price) / mid_price * 10000
        """
        if not tick.bids or not tick.asks:
            return 0.0
        
        best_bid = float(tick.bids[0][0])
        best_ask = float(tick.asks[0][0])
        
        if best_bid == 0:
            return 0.0
        
        mid_price = (best_bid + best_ask) / 2
        spread = (best_ask - best_bid) / mid_price * 10000
        
        return spread
    
    def _calculate_weighted_imbalance(self, buffer: List[OrderbookTick]) -> float:
        """
        Calculate volume-weighted imbalance using all depth levels.
        
        Weights volumes by their distance from mid-price.
        """
        if not buffer:
            return 0.0
        
        last_tick = buffer[-1]
        if not last_tick.bids or not last_tick.asks:
            return 0.0
        
        best_bid = float(last_tick.bids[0][0])
        best_ask = float(last_tick.asks[0][0])
        mid = (best_bid + best_ask) / 2
        
        # Weighted bid volume (closer to mid = higher weight)
        bid_volume = 0.0
        for price, qty in last_tick.bids:
            price = float(price)
            distance_weight = 1 - (best_bid - price) / (best_bid * 0.01)  # 1% depth max
            distance_weight = max(0, min(1, distance_weight))
            bid_volume += float(qty) * distance_weight
        
        # Weighted ask volume
        ask_volume = 0.0
        for price, qty in last_tick.asks:
            price = float(price)
            distance_weight = 1 - (price - best_ask) / (best_ask * 0.01)
            distance_weight = max(0, min(1, distance_weight))
            ask_volume += float(qty) * distance_weight
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / total
    
    def _calculate_vtob_ratio(self, buffer: List[OrderbookTick]) -> float:
        """
        Calculate volume-to-notional ratio (VTOB).
        
        Measures the efficiency of order book depth.
        """
        if not buffer:
            return 0.0
        
        last_tick = buffer[-1]
        if not last_tick.bids or not last_tick.asks:
            return 0.0
        
        best_bid = float(last_tick.bids[0][0])
        best_ask = float(last_tick.asks[0][0])
        mid = (best_bid + best_ask) / 2
        
        # Total notional value at bid side
        bid_notional = sum(
            float(price) * float(qty)
            for price, qty in last_tick.bids
        )
        
        # Total notional value at ask side
        ask_notional = sum(
            float(price) * float(qty)
            for price, qty in last_tick.asks
        )
        
        total_notional = bid_notional + ask_notional
        
        if total_notional == 0:
            return 0.0
        
        # VTOB = (bid_notional - ask_notional) / total_notional
        return (bid_notional - ask_notional) / total_notional
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        symbols_status = []
        current_time = time.time()
        
        for symbol, buffer in self.buffers.items():
            if buffer:
                age = current_time - buffer[0].timestamp
                symbols_status.append(
                    f"{symbol}: {len(buffer)} ticks, {age:.1f}s old"
                )
        
        return (
            f"OrderbookDownsampler("
            f"bucket={self.bucket_seconds}s, "
            f"depth={self.depth}, "
            f"symbols={list(self.buffers.keys())}): "
            f"{'; '.join(symbols_status)}"
        )


# Example usage and tests
if __name__ == "__main__":
    import json
    
    # Create downsampler
    downsampler = OrderbookDownsampler(bucket_seconds=5)  # 5 sec for testing
    
    # Simulate Binance order book ticks
    sample_ticks = [
        {
            'bids': [['50000', '1.5'], ['49999', '2.0'], ['49998', '2.5']],
            'asks': [['50001', '1.2'], ['50002', '1.8'], ['50003', '2.2']]
        },
        {
            'bids': [['50002', '1.6'], ['50001', '2.1'], ['50000', '2.6']],
            'asks': [['50003', '1.3'], ['50004', '1.9'], ['50005', '2.3']]
        },
        {
            'bids': [['50001', '1.7'], ['50000', '2.2'], ['49999', '2.7']],
            'asks': [['50002', '1.4'], ['50003', '2.0'], ['50004', '2.4']]
        },
    ]
    
    print("Testing OrderbookDownsampler\n")
    
    # Add ticks
    for i, tick in enumerate(sample_ticks):
        downsampler.add_tick('BTCUSDT', tick)
        print(f"Added tick {i+1}: {downsampler}")
    
    # Wait a bit (in real usage, this would be 60 seconds)
    time.sleep(6)
    
    # Check if ready to flush
    if downsampler.should_flush('BTCUSDT'):
        metric = downsampler.flush('BTCUSDT')
        print(f"\nFlushed metric:")
        print(f"  Symbol: {metric.symbol}")
        print(f"  Timestamp: {metric.bucket_timestamp}")
        print(f"  Ticks: {metric.tick_count}")
        print(f"  Avg Imbalance: {metric.avg_imbalance_ratio:.4f}")
        print(f"  Avg Spread (bps): {metric.avg_spread_bps:.2f}")
        print(f"  Weighted Imbalance: {metric.weighted_imbalance:.4f}")
        print(f"  VTOB Ratio: {metric.vtob_ratio:.4f}")
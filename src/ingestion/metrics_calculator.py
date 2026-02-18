"""Calculate order book imbalance metrics."""

from src.config import settings


def calculate_metrics(data: dict) -> dict:
    """Calculate order book imbalance metrics.
    
    Args:
        data: Parsed order book dictionary
        
    Returns:
        Dictionary with calculated metrics
    """
    # TODO: make sure depth is documented in readme
    bids = data.get('bids', [])[:settings.calculate_depth]
    asks = data.get('asks', [])[:settings.calculate_depth]
    
    # volumes
    bid_volume = sum(float(vol) for _, vol in bids)
    ask_volume = sum(float(vol) for _, vol in asks)
    total_volume = bid_volume + ask_volume
    
    if total_volume == 0:
        return None
    
    imbalance_ratio = (bid_volume - ask_volume) / total_volume

    # formula ?? how are weights determined?? dist to mid_price ?? could use w_i = 1/i
    weighted_bid_vol =  sum(float(b[1]) * (1/i) for i, b in enumerate(bids))
    weighted_ask_vol =  sum(float(a[1]) * (1/i) for i, a in enumerate(asks))
    weighted_total_vol = weighted_bid_vol + weighted_ask_vol

    weighted_imbalance = (weighted_bid_vol - weighted_ask_vol) / weighted_total_vol
    
    # top of book
    best_bid = float(bids[0][0]) if bids else 0
    best_ask = float(asks[0][0]) if asks else 0
    best_bid_volume = float(bids[0][1])
    best_ask_volume = float(asks[0][1])

    mid_price = (best_bid + best_ask) / 2
    spread_abs = best_ask - best_bid
    spread_bps = (spread_abs / mid_price * 10000) if mid_price > 0 else 0

    vtob_ratio = (
        (best_bid_volume + best_ask_volume) / total_volume if total_volume else None
    )

    # Placeholders for advanced metrics you may define later
    imbalance_velocity = None # formula ?? need to calc in timeseries later

    
    return {
        'symbol': data['symbol'],
        'timestamp': data['timestamp'],
        'mid_price': mid_price,
        'best_bid': best_bid,
        'best_ask': best_ask,
        'imbalance_ratio': imbalance_ratio,
        'weighted_imbalance': weighted_imbalance,
        'bid_volume': bid_volume,
        'ask_volume': ask_volume,
        'total_volume': total_volume,
        'spread_bps': spread_bps,
        'spread_abs': spread_abs,
        'vtob_ratio': vtob_ratio,
        'best_bid_volume': best_bid_volume,
        'best_ask_volume': best_ask_volume,
        'imbalance_velocity': imbalance_velocity,
        'depth_level': settings.calculate_depth,
        'update_id': data.get('update_id'),
    }


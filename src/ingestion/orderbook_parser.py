"""Order book data parser."""

# Binance Diff Depth Stream structure:
# {
#     "e": "depthUpdate",     // Event type
#     "E": 1672515782136,     // Event time
#     "s": "BNBBTC",          // Symbol
#     "U": 157,               // First update ID in event
#     "u": 160,               // Final update ID in event
#     "b": [                  // Bids to be updated
#         [
#             "0.0024",       // Price level to be updated
#             "10"            // Quantity
#         ]
#     ],
#     "a": [                  // Asks to be updated
#         [
#             "0.0026",       // Price level to be updated
#             "100"           // Quantity
#         ]
#     ]
# }

# TODO: Parse and validate order book data
# - Parse WebSocket messages
# - Validate structure
# - Convert to internal models
# - Binance Docs: https://docs.binance.us/#order-book-streams

# parse websocket message format

# validate order book structure

# sort bids (descending) and asks (ascending)

# convert to `OrderBookSnapshot` model

# Handle snapshot vs delta updates

# calculate mid price

# filter invalid levels (price <= 0; volume <= 0) (remove price level if quantity is 0)

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from pydantic import ValidationError
from loguru import logger

from src.common.models import OrderBookSnapshot
from src.config import settings


class OrderBookParser:
    """
    Parse incoming raw Binance order book data → `OrderBookSnapshot`

    Supports:
    - partial depth stream: {"lastUpdateId", "bids", "asks"}
    - diff depth stream: {"E", "b", "a", "U", "u"}
    """

    def _parse_levels(self, levels: Iterable[Iterable[Any]]) -> List[Tuple[float, float]]:
        parsed: List[Tuple[float, float]] = []

        for level in levels:
            if not level or len(level) < 2:
                continue
            try:
                price = float(level[0])
                volume = float(level[1])
            except (TypeError, ValueError):
                continue
            if price <=0 or volume <= 0:
                logger.warn(f'volume or price <= 0. v={volume}; p={price}')
                continue
            parsed.append((price, volume))
        return parsed

    def parse(self, symbol: str, raw: Dict[str, Any]) -> OrderBookSnapshot | None:
        """
            convert raw Binance dict → `OrderBookSnapshot`

            - Convert string prices/volumes to float
            - Sort bids descending, asks ascending
            - Filter invalid levels (price <= 0, volume <= 0)
            - Attach timestamp and symbol
            - Handle missing or malformed fields gracefully
        """
        if not isinstance(raw, dict):
            logger.warning(f'Invalid order book payload type: {type(raw)}')
            return None

        bids_raw = raw.get('bids') or raw.get('b')
        asks_raw = raw.get('asks') or raw.get('a')

        if not bids_raw or not asks_raw:
            logger.warning(f'Missing bids/asks for {symbol}: {raw}')
            return None

        bids = self._parse_levels(bids_raw)
        asks = self._parse_levels(asks_raw)

        if not bids or not asks:
            logger.warning(f'Empty book after parsing or {symbol}')
            return None

        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])

        # Optional: trim to configured depth
        # depth = settings.depth_levels
        # bids = bids[:depth]
        # asks = asks[:depth]

        event_ms = raw.get('E')
        timestamp = (
            datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc)
            if isinstance(event_ms, (int, float))
            else datetime.now(timezone.utc)
        )

        update_id = raw.get('lastUpdatedId') or raw.get('u') or raw.get('U')

        try:
            return OrderBookSnapshot(
                timestamp=timestamp,
                symbol=symbol,
                bids=bids,
                asks=asks,
                update_id=update_id
            )
        except ValidationError as e:
            logger.error(f'OrderBookSnapshot validation failed for {symbol}: {e}')
            return None


        
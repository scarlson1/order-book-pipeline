"""Order book data parser."""

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
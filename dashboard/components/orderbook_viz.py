"""Order book visualization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
# from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async

BID_COLOR = "#16a34a"
ASK_COLOR = "#dc2626"
MID_COLOR = "#f59e0b"

def _coerce_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_levels(levels: Any, side: str, depth_levels: int) -> list[dict[str, float | int]]:
    if not isinstance(levels, list):
        return []

    rows: list[dict[str, float | int]] = []
    for i, level in enumerate(levels[:depth_levels], start=1):
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        try:
            price = float(level[0])
            volume = float(level[1])
        except (TypeError, ValueError):
            continue
        if price <= 0 or volume <= 0:
            continue
        rows.append({"level": i, "price": price, "volume": volume})

    rows.sort(key=lambda row: row["price"], reverse=(side == "bid"))

    cumulative = 0.0
    for row in rows:
        cumulative += float(row["volume"])
        row["cum_volume"] = cumulative

    return rows


def _get_orderbook_snapshot(symbol: str) -> dict[str, Any] | None:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    # Preferred: DataLayer method if available.
    if hasattr(data_layer, "get_orderbook_snapshot"):
        return run_async(data_layer.get_orderbook_snapshot(symbol), timeout=5)

    # Fallback to existing Redis client chain.
    return run_async(data_layer.redis.redis.get_cached_orderbook(symbol), timeout=5)

def _create_depth_figure(
    symbol: str,
    bids: list[dict[str, float | int]],
    asks: list[dict[str, float | int]],
    mid_price: float | None,
) -> go.Figure:
    fig = go.Figure()

    # bids
    fig.add_trace(
        go.Scatter(
            x=[row["price"] for row in bids],
            y=[row["cum_volume"] for row in bids],
            customdata=[[row["volume"], row["level"]] for row in bids],
            mode="lines",
            name="Bids",
            fill="tozeroy",
            line={"color": BID_COLOR, "width": 2},
            hovertemplate=(
                "Side: Bid<br>"
                "Price: %{x:,.4f}<br>"
                "Level: %{customdata[1]}<br>"
                "Level Vol: %{customdata[0]:,.4f}<br>"
                "Cum Vol: %{y:,.4f}<extra></extra>"
            ),
        )
    )

    # asks
    fig.add_trace(
        go.Scatter(
            x=[row["price"] for row in asks],
            y=[row["cum_volume"] for row in asks],
            customdata=[[row["volume"], row["level"]] for row in asks],
            mode="lines",
            name="Asks",
            fill="tozeroy",
            line={"color": ASK_COLOR, "width": 2},
            hovertemplate=(
                "Side: Ask<br>"
                "Price: %{x:,.4f}<br>"
                "Level: %{customdata[1]}<br>"
                "Level Vol: %{customdata[0]:,.4f}<br>"
                "Cum Vol: %{y:,.4f}<extra></extra>"
            ),
        )
    )

    if mid_price is not None:
        fig.add_vline(
            x=mid_price,
            line_color=MID_COLOR,
            line_dash="dash",
            line_width=2,
            annotation_text=f"Mid {mid_price:,.4f}",
            annotation_position="top",
        )

    fig.update_layout(
        template="plotly_white",
        title=f"{symbol} Depth Chart",
        xaxis_title="Price",
        yaxis_title="Cumulative Volume",
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        # legend={"orientation": "h", "yanchor": "bottom", "y": 1.25, "x": 0.0},
        legend={ 'orientation': 'h' },
        uirevision=f"orderbook-depth-{symbol}",
    )
    
    return fig

@st.fragment()
def render_orderbook_viz(symbol: str, depth_levels: int = 20, refresh_rate: int = 10000) -> None:
    st_autorefresh(interval=refresh_rate, key="data_orderbook_refresh")

    snapshot = _get_orderbook_snapshot(symbol)
    if not snapshot:
        st.info(f"No cached order book snapshot for {symbol} yet.")
        return

    bids = _normalize_levels(snapshot.get("bids"), side="bid", depth_levels=depth_levels)
    asks = _normalize_levels(snapshot.get("asks"), side="ask", depth_levels=depth_levels)

    if not bids or not asks:
        st.warning("Snapshot exists but has no valid bid/ask levels.")
        return

    best_bid = float(bids[0]["price"])
    best_ask = float(asks[0]["price"])
    mid_price = (best_bid + best_ask) / 2.0

    fig = _create_depth_figure(symbol=symbol, bids=bids, asks=asks, mid_price=mid_price)
    st.plotly_chart(fig, width='stretch', config={'displaylogo': False})

    spread_bps = ((best_ask - best_bid) / mid_price) * 10_000 if mid_price else 0.0
    ts = _coerce_timestamp(snapshot.get("timestamp") or snapshot.get("time"))
    age_text = ""
    if ts is not None:
        age_sec = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
        age_text = f" | age: {age_sec:.1f}s"

    st.caption(
        f"best bid: {best_bid:,.4f} | best ask: {best_ask:,.4f} | spread: {spread_bps:.2f} bps{age_text}"
    )

################################################
# ===== Cline implementation suggestion: ===== #
################################################

# ### Data Source

# # The order book data is cached in Redis with key: `orderbook:{symbol}:snapshot`

# # Looking at `redis_client.py`:

# # - `cache_orderbook()` stores: `{ bids: [(price, volume), ...], asks: [(price, volume), ...] }`
# # - TTL is 30 seconds (real-time)


# """Order book visualization."""
# import plotly.graph_objects as go
# import streamlit as st
# import pandas as pd

# from dashboard.utils.async_runner import run_async

# from streamlit_autorefresh import st_autorefresh

# # Add auto-refresh (every 5 seconds)
# st_autorefresh(interval=5000, key="orderbook_refresh")


# def create_depth_chart(snapshot: dict) -> go.Figure:
#     """Create depth chart from order book snapshot.
    
#     Args:
#         snapshot: Dict with 'bids' and 'asks' as [(price, volume), ...]
        
#     Returns:
#         Plotly figure with stacked area chart
#     """
#     bids = snapshot.get('bids', [])
#     asks = snapshot.get('asks', [])
    
#     if not bids or not asks:
#         return None
    
#     # Convert to DataFrames for easier processing
#     bid_df = pd.DataFrame(bids, columns=['price', 'volume'])
#     ask_df = pd.DataFrame(asks, columns=['price', 'volume'])
    
#     # Calculate cumulative volume
#     bid_df['cumulative'] = bid_df['volume'].cumsum()
#     ask_df['cumulative'] = ask_df['volume'].cumsum()
    
#     # Reverse asks so area fills correctly (ascending price)
#     ask_df = ask_df.iloc[::-1]
    
#     # Create figure
#     fig = go.Figure()
    
#     # Bids area (green)
#     fig.add_trace(go.Scatter(
#         x=bid_df['price'],
#         y=bid_df['cumulative'],
#         fill='tozeroy',
#         mode='none',
#         fillcolor='rgba(34, 197, 94, 0.5)',  # Green
#         name='Bids'
#     ))
    
#     # Asks area (red) - filled to y-axis of bids
#     fig.add_trace(go.Scatter(
#         x=ask_df['price'],
#         y=ask_df['cumulative'],
#         fill='tonexty',
#         mode='none',
#         fillcolor='rgba(239, 68, 68, 0.5)',  # Red
#         name='Asks'
#     ))
    
#     # Mid-price line
#     mid_price = snapshot.get('mid_price', (bids[0][0] + asks[0][0]) / 2)
#     fig.add_vline(x=mid_price, line_color='#3B82F6', line_dash='dash')
    
#     return fig


# def render_orderbook_viz(symbol: str):
#     """Render order book visualization component."""
#     data_client = st.session_state.data_layer
    
#     # Get latest snapshot from Redis
#     snapshot = run_async(
#         data_client.redis.get_cached_orderbook(symbol),
#         timeout=5
#     )
    
#     if not snapshot:
#         st.warning(f"No order book data for {symbol}")
#         return
    
#     # Create chart
#     fig = create_depth_chart(snapshot)
    
#     if fig:
#         fig.update_layout(
#             title=f"Order Book Depth - {symbol}",
#             xaxis_title="Price",
#             yaxis_title="Cumulative Volume",
#             template="plotly_dark"
#         )
#         st.plotly_chart(fig, width='stretch')


# # def create_depth_heatmap(snapshot: dict) -> go.Figure:
#     """Create heatmap of order book depth."""
#     # Combine bids/asks into price levels
#     # Use go.Heatmap with z=volume, x=price

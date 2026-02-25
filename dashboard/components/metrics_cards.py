"""Metric card components for top-of-dashboard KPIs."""

from __future__ import annotations
import json
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.formatting import format_bps, format_percentage, format_volume, format_price

from dashboard.utils.async_runner import run_async

# async def load_data(symbol: str):
# 	data_client = DataLayer()
# 	return await data_client.get_latest_metrics_with_changes(symbol)

def _format_volume_delta(value: float | None) -> str | None:
    """Format volume delta with explicit sign."""
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{format_volume(value, abbreviated=True)}"

def _format_bps_delta(value: float | None) -> str | None:
    """Format basis points delta with explicit sign."""
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f} bps"

@st.fragment()
def render_metrics_cards(symbol: str, refresh_rate: int = 1000):
	st_autorefresh(interval=refresh_rate, key="data_metrics_refresh")
	# data_load_state = st.text('Loading data...')
	data_client = st.session_state.data_layer
	# result = asyncio.run(data_client.get_latest_metrics_with_changes(symbol))
	result = run_async(data_client.get_latest_metrics_with_changes(symbol), timeout=10)
	# data_load_state.text('Loading data...done!')
	# print(f'METRICS RESULT: {json.dumps(result, indent=4, default=str)}')

	if not result:
		return st.text('Failed to load metrics')

	col1, col2, col3, col4 = st.columns(4)

	current = result.get('current', {})
	changes = result.get('changes', {})

	bid_volume = current.get('bid_volume', 0)
	ask_volume = current.get('ask_volume', 0)
	total_volume= bid_volume + ask_volume

	# Display in Streamlit
	with col1:
		price_pct = changes.get('price_pct')
		st.metric(
			'Price',
			value=format_price(current.get('mid_price', '--'), currency='$'),
			delta=format_percentage(price_pct / 100 if price_pct not in (None, '--') else '--', precision=1),
			# f"${result['current']['mid_price']:,.2f}",
			# delta=f"{result['changes']['price_pct']:+.2f}%"
			border=True
		)

	with col2:
		st.metric(
			label="Spread",
			value=format_bps(current.get('spread_bps', '--')),
			delta=_format_bps_delta(changes.get('spread_pct', '--')),
			delta_color="inverse",  # Lower spread is better.
			border=True
		)
		# _render_level_badge(spread_level, spread_color)

	with col3:
		imbalance_pct = changes.get('imbalance_pct', '--')
		st.metric(
			label='⚖️ Imbalance',
			value=format_percentage(current.get('imbalance_ratio', '--'), precision=1),
			# value=f"{current.get('imbalance_ratio', '--')*100:+.1f}%",
			delta=f"{format_percentage(imbalance_pct / 100 if imbalance_pct not in (None, '--') else '--', precision=1)} vs avg",
			border=True
		)

	with col4:
		st.metric(
			label="Volume",
			value=format_volume(total_volume, abbreviated=True),
			delta=_format_volume_delta(changes.get('volume_pct', 0)),
			border=True
		)
        # _render_level_badge(volume_level, volume_color)


# col1, col2, col3, col4 = st.columns(4)

# with col1:
#     st.metric(
#         label="💰 Current Price",
#         value=f"${data['current']['mid_price']:,.2f}",
#         delta=f"{data['changes']['price_pct']:+.2f}%",  # +2.3% or -1.5%
#         delta_color="normal"  # Green for positive, red for negative
#     )

# with col2:
#     st.metric(
#         label="⚖️ Imbalance",
#         value=f"{data['current']['imbalance_ratio']*100:+.1f}%",
#         delta=f"{data['changes']['imbalance_pct']:+.1f}% vs avg",
#         delta_color="inverse"  # Red for high imbalance might be warning
#     )

# def _to_float(value: Any) -> float | None:
#     """Return float value when possible, else None."""
#     if value is None:
#         return None
#     try:
#         return float(value)
#     except (TypeError, ValueError):
#         return None


# def _delta(current: float | None, previous: float | None) -> float | None:
#     """Return current - previous when both values exist."""
#     if current is None or previous is None:
#         return None
#     return current - previous


# def _format_percentage_delta(value: float | None) -> str | None:
#     """Format percentage delta using signed percent text."""
#     if value is None:
#         return None
#     return format_percentage(value, include_sign=True)

# def _imbalance_level(value: float | None) -> tuple[str, str]:
#     """Color + semantic level for imbalance."""
#     if value is None:
#         return "#6b7280", "Unknown"
#     abs_val = abs(value)
#     if abs_val >= 0.70:
#         return "#dc2626", "Extreme"
#     if abs_val >= 0.50:
#         return "#d97706", "Elevated"
#     return "#16a34a", "Normal"


# def _spread_level(value: float | None) -> tuple[str, str]:
#     """Color + semantic level for spread in bps."""
#     if value is None:
#         return "#6b7280", "Unknown"
#     if value >= 10:
#         return "#dc2626", "Wide"
#     if value >= 4:
#         return "#d97706", "Moderate"
#     return "#16a34a", "Tight"


# def _volume_level(current: float | None, delta_value: float | None) -> tuple[str, str]:
#     """Color + semantic level for volume."""
#     if current is None:
#         return "#6b7280", "Unknown"
#     if delta_value is None:
#         return "#2563eb", "Stable"
#     if delta_value > 0:
#         return "#16a34a", "Rising"
#     if delta_value < 0:
#         return "#dc2626", "Falling"
#     return "#2563eb", "Flat"


# def _render_level_badge(label: str, color: str) -> None:
#     """Render small color-coded status badge below metric."""
#     st.markdown(
#         (
#             "<div style='margin-top:-6px;'>"
#             f"<span style='color:{color};font-size:0.82rem;font-weight:600;'>{label}</span>"
#             "</div>"
#         ),
#         unsafe_allow_html=True,
#     )


# def render_metrics_cards(
#     current_metrics: dict[str, Any],
#     previous_metrics: dict[str, Any] | None = None,
# ) -> None:
#     """Render imbalance, spread, and volume KPI cards with deltas."""
#     previous_metrics = previous_metrics or {}

#     curr_imbalance = _to_float(current_metrics.get("imbalance_ratio"))
#     prev_imbalance = _to_float(previous_metrics.get("imbalance_ratio"))
#     imbalance_delta = _delta(curr_imbalance, prev_imbalance)

#     curr_spread = _to_float(current_metrics.get("spread_bps"))
#     prev_spread = _to_float(previous_metrics.get("spread_bps"))
#     spread_delta = _delta(curr_spread, prev_spread)

#     curr_volume = _to_float(current_metrics.get("total_volume"))
#     prev_volume = _to_float(previous_metrics.get("total_volume"))
#     volume_delta = _delta(curr_volume, prev_volume)

#     imbalance_color, imbalance_level = _imbalance_level(curr_imbalance)
#     spread_color, spread_level = _spread_level(curr_spread)
#     volume_color, volume_level = _volume_level(curr_volume, volume_delta)

#     col1, col2, col3 = st.columns(3)

#     with col1:
#         st.metric(
#             "Imbalance",
#             format_percentage(curr_imbalance, precision=2),
#             _format_percentage_delta(imbalance_delta),
#         )
#         _render_level_badge(imbalance_level, imbalance_color)

#     with col2:
#         st.metric(
#             "Spread",
#             format_bps(curr_spread, precision=2),
#             _format_bps_delta(spread_delta),
#             delta_color="inverse",  # Lower spread is better.
#         )
#         _render_level_badge(spread_level, spread_color)

#     with col3:
#         st.metric(
#             "Volume",
#             format_volume(curr_volume, abbreviated=True),
#             _format_volume_delta(volume_delta),
#         )
#         _render_level_badge(volume_level, volume_color)

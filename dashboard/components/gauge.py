"""Imbalance gauge component."""
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async

# https://plotly.com/python/gauge-charts/

# TODO: Create gauge visualization
# - Plotly indicator gauge (imbalance ratio visualization)
# - Color coding

def _get_imb_data(symbol: str):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_latest_metrics(symbol), timeout=5)

def _create_gauge_fig(imbalance: float):
    imbalance = max(-1.0, min(1.0, float(imbalance)))
    normalized = (imbalance + 1.0) / 2.0

    fig = go.Figure(go.Indicator(
    domain = {'x': [0, 1], 'y': [0, 1]},
    value = imbalance,
    number={'valueformat': '.2f'},
    mode = "gauge+number",
    title = {'text': "Imbalance Ratio"},
    # delta = {'reference': 380},
    gauge = {
        # 'axis': {'range': [-1, 1]},
        'axis': {
            'range': [0, 1],
            'tickmode': 'array',
            'tickvals': [0, 0.25, 0.5, 0.75, 1],
            'ticktext': ['-1', '-0.5', '0', '0.5', '1'],
        },
        'bar': {'color': "lightgrey"},
        'steps': [
            {'range': [0.0, 0.335], 'color': '#EF4444'},
            {'range': [0.335, 0.665], 'color': '#6B7280'},
            {'range': [0.665, 1.0], 'color': '#22C55E'},
        ],
        # 'steps' : [
        #     {'range': [-1, -0.33], 'color': '#EF4444'},
        #     {'range': [-0.33, 0.33], 'color': '#6B7280'},
        #     {'range': [0.33, 1], 'color': '#22C55E'},
        # ],
        'threshold' : {'line': {'color': "black", 'width': 3},  'value': normalized}
    }))

    return fig
            # "buy": "#22C55E",      # Green
            # "sell": "#EF4444",     # Red
            # "neutral": "#6B7280",  # Gray

def _coerce_datetime(ts) -> datetime | None:
    """Return timezone-aware datetime from input, or None."""
    if ts is None:
        return None

    if isinstance(ts, datetime):
        return ts

    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            return None

    return None


def render_countdown_from_timestamp(ts, ttl_seconds: int = 6) -> None:
    # Re-run this block every 100ms (non-blocking)
    st_autorefresh(interval=100, key='countdown_refresh')

    parsed_ts = _coerce_datetime(ts)
    if parsed_ts is None:
        return

    now = datetime.now(timezone.utc)
    if parsed_ts.tzinfo is None:
        parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)

    deadline = parsed_ts + timedelta(seconds=ttl_seconds)
    remaining = max(0.0, (deadline - now).total_seconds())

    # 100 -> 0 as time runs out
    pct_remaining = int((remaining / ttl_seconds) * 100)
    st.progress(pct_remaining, text=f'{remaining:0.1f}s remaining')
    st.metric('Time Remaining', f'{remaining:0.1f}s')


@st.fragment()
def render_imbalance_gauge(symbol: str, refresh_rate: int = 2000):
    st_autorefresh(interval=refresh_rate, key='imbalance_gauge')

    data = _get_imb_data(symbol)
    if not data:
        st.warning('No gauge data available')
        return

    imb_ratio = data.get('imbalance_ratio')

    if imb_ratio is None:
        st.warning('Failed to find valid data for imbalance gauge')
        return

    fig = _create_gauge_fig(imb_ratio)

    if fig is None:
        st.warning('Failed to create imbalance gauge chart')
        return

    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now()

    st.write(data)
    event_time = _coerce_datetime(data.get('time'))
    if event_time is not None:
        # TODO: use reload/timing function like render_countdown to show updated x.y seconds ago
        st.write(event_time)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        elapsed = now - event_time
        seconds_ago = int(elapsed.total_seconds())

        st.plotly_chart(fig)
        st.write(f'Last updated: **{seconds_ago} seconds ago**')

        # render_countdown_from_timestamp(event_time, 2)
    else:
        st.plotly_chart(fig)

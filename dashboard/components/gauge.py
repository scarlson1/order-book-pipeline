"""Imbalance gauge component."""
from datetime import datetime
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

def _create_gauge_fig(value: float):
    fig = go.Figure(go.Indicator(
    domain = {'x': [0, 1], 'y': [0, 1]},
    value = value,
    mode = "gauge+number+delta",
    title = {'text': "Speed"},
    delta = {'reference': 380},
    gauge = {'axis': {'range': [None, 500]},
                'steps' : [
                    {'range': [0, 250], 'color': "lightgray"},
                    {'range': [250, 400], 'color': "gray"}],
                'threshold' : {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 0.5}}))

    return fig


@st.fragment()
def render_imbalance_gauge(symbol: str, refresh_rate: int = 5000):
    st_autorefresh(interval=refresh_rate, key='imbalance_gauge')

    data = _get_imb_data(symbol)
    st.write(data)

    imb_ratio = data.get('imbalance_ratio')

    fig = _create_gauge_fig(imb_ratio)

    if fig is None:
        st.warning('Failed to find valid data for imbalance gauge')
        return

    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now()

    now = datetime.now()
    elapsed = now - st.session_state.start_time
    seconds_ago = int(elapsed.total_seconds())

    st.plotly_chart(fig)

    st.write(f"This page was last updated: **{seconds_ago} seconds ago**")
    st.write(f"Actual time: {now.strftime('%H:%M:%S')}")


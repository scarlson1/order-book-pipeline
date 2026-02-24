import streamlit as st

from dashboard.utils.async_runner import run_async


def _get_windowed_aggregates(
        symbol: str,
        window_type: str = '5m_sliding',
        limit: int = 12
    ):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_windowed_aggregates(symbol, window_type, limit), timeout=5)


def render_windowed_aggregates(symbol: str):
    data = _get_windowed_aggregates(symbol)
    print(data)
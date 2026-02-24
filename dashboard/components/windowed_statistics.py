from datetime import datetime
import streamlit as st

from dashboard.utils.async_runner import run_async


def _get_windowed_latest(
        symbol: str,
        window_type: str = '5m_sliding',
    ):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_latest_windowed(symbol, window_type), timeout=5)

def _format_metric_value(value, metric_name: str) -> str:
    """Format metric values appropriately based on metric type."""
    if value is None:
        return "N/A"
    
    if 'spread' in metric_name.lower():
        return f"{value:.1f} bps"
    elif 'volume' in metric_name.lower():
        return f"{value:,.0f}"
    elif 'imbalance' in metric_name.lower():
        return f"{value:.2f}"
    elif 'velocity' in metric_name.lower():
        return f"{value:.2f}"
    elif 'sample' in metric_name.lower():
        return f"{int(value)}"
    else:
        return f"{value:.2f}"

def _format_datetime(dt) -> str:
    """Format datetime for display."""
    if isinstance(dt, datetime):
        return dt.strftime("%H:%M")
    return str(dt)

def render_windowed_stats(symbol: str, window_type: str = '5m_sliding'):
    data = _get_windowed_latest(symbol, window_type)

    if not data:
        st.info("No windowed statistics available")
        return

    window_start = _format_datetime(data.get('window_start', 'N/A'))
    window_end = _format_datetime(data.get('window_end', 'N/A'))
    st.caption(f"Window: {window_start} - {window_end}")

    # st.subheader(f"📊 WINDOWED STATISTICS ({data.get('window_type', window_type).replace('_', ' ').upper()})")

    # st.text(f"Window: {data.get('window_start')} - {data.get('window_end')}")

    # col_metric, col_avg, col_min, col_max = st.columns([2, 1, 1, 1])
    # with col_metric:
    #     st.markdown("**Metric**")
    # with col_avg:
    #     st.markdown("**Avg**")
    # with col_min:
    #     st.markdown("**Min**")
    # with col_max:
    #     st.markdown("**Max**")

    col_metric, col_avg = st.columns([2, 1])
    with col_metric:
        st.markdown("**Metric**")
    with col_avg:
        st.markdown("**Avg**")

    st.markdown('---')

    # Metrics configuration: (display_name, data_key)
    # metrics_config = [
    #     ("Imbalance", "imbalance"),
    #     ("Spread (bps)", "spread"),
    #     ("Volume", "volume"),
    #     ("Velocity", "velocity"),
    #     ("Samples", "samples"),
    # ]

    # for display_name, data_key in metrics_config:
    #     col_name, col_avg, col_min, col_max = st.columns([2, 1, 1, 1])
        
    #     avg_val = data.get(f"{data_key}_avg")
    #     min_val = data.get(f"{data_key}_min")
    #     max_val = data.get(f"{data_key}_max")
        
    #     # Handle samples which might just be a count
    #     if data_key == "samples":
    #         avg_val = data.get("sample_count", 0)
    #         min_val = None
    #         max_val = None

    #     with col_name:
    #         st.markdown(f"**{display_name}**")
    #     with col_avg:
    #         st.text(_format_metric_value(avg_val, display_name))
    #     with col_min:
    #         st.text(_format_metric_value(min_val, display_name))
    #     with col_max:
    #         st.text(_format_metric_value(max_val, display_name))

    metrics_config = [
        ("Imbalance", "avg_imbalance"),
        ("Spread (bps)", "avg_spread_bps"),
        ("Volume", "avg_total_volume"),
        ("Velocity", "window_velocity"),
        ("Samples", "sample_count"),
    ]

    for display_name, data_key in metrics_config:
        col_name, col_avg_val = st.columns([2, 1])
        
        avg_val = data.get(data_key)

        with col_name:
            st.markdown(f"**{display_name}**")
        with col_avg_val:
            st.text(_format_metric_value(avg_val, display_name))

    st.markdown('---')
    st.json(data, expanded=False)

import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from dashboard.utils.async_runner import run_async


def _get_volatility_data(symbol: str):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_volatility_data(symbol), timeout=5)


def _create_volatility_chart(symbol: str):
    """Show imbalance volatility by hour and day of week."""
    rows = _get_volatility_data(symbol)
    
    if not rows:
        return None
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        return None
    
    # Check required columns exist
    required_cols = ['day_of_week', 'hour', 'avg_volatility']
    if not all(col in df.columns for col in required_cols):
        return None
    
    # Pivot for heatmap
    pivot = df.pivot(
        index='day_of_week',
        columns='hour',
        values='avg_volatility'
    )
    
    # Day names
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    pivot.index = [day_names[int(i)] for i in pivot.index]
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[f'{int(h):02d}:00' for h in pivot.columns],
        y=pivot.index,
        colorscale='RdYlGn_r',
        colorbar=dict(title='Volatility')
    ))
    
    fig.update_layout(
        title=f'{symbol} - Volatility by Time of Day/Week',
        xaxis_title='Hour (UTC)',
        yaxis_title='Day of Week',
        height=400
    )
    
    return fig


def render_volatility_heatmap(symbol: str):
    fig = _create_volatility_chart(symbol)

    if fig is None:
        st.warning('Failed to find valid data for volatility heatmap')
        return

    st.plotly_chart(fig, use_container_width=True)

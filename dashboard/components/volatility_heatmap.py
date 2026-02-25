import plotly.graph_objects as go
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async


def _get_volatility_data(symbol: str, timezone: str, days: int = 7):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_volatility_data(symbol, timezone), timeout=5)


def _create_volatility_chart(df, symbol: str, timezone_pref: str = 'America/New_York'):
    """Show imbalance volatility by hour and day of week."""
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
        xaxis_title=f'Hour ({timezone_pref})',
        yaxis_title='Day of Week',
        height=400
    )
    
    return fig

@st.fragment()
def render_volatility_heatmap(symbol: str, timezone_pref: str = 'America/New_York', days: int = 7, refresh_rate: int = 300000):
    st_autorefresh(interval=refresh_rate, key="data_vol_heatmap_refresh")

    days_input = st.selectbox(
        "Last Days",
        (7, 14, 30),
        index=0 if days == 7 else 1 if days == 14 else 2 if days == 30 else 0,
        width=120
    )

    rows = _get_volatility_data(symbol, timezone_pref, days_input)
    print(f'ROWS: {rows[:1]}')
    
    if not rows:
        st.warning('Failed to find valid data for volatility heatmap')
        return
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.warning('Failed to find valid data for volatility heatmap')
        return

    fig = _create_volatility_chart(df, symbol, timezone_pref)

    if fig is None:
        st.warning('Failed to find valid data for volatility heatmap')
        return

    st.plotly_chart(fig, width='stretch')

    st.caption(f'calculated from last {days_input} days')

import streamlit as st
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async

def _get_windowed_data(symbol: str):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_windowed_aggregates(symbol, limit=60))


def _create_multi_metric_windows(df, symbol: str, timezone_pref: str):
    """Show imbalance, spread, and volume in subplots."""
    
    # Create subplots
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            'Imbalance Ratio',
            'Spread (bps)',
            'Volume'
        ),
        vertical_spacing=0.08,
        shared_xaxes=True
    )
    
    # Imbalance
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['avg_imbalance'],
            name='Imbalance',
            line=dict(color='blue', width=2)
        ),
        row=1, col=1
    )
    
    # Spread
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=df['avg_spread_bps'],
            name='Spread',
            line=dict(color='orange', width=2)
        ),
        row=2, col=1
    )
    
    # Volume
    fig.add_trace(
        go.Bar(
            x=df['time'],
            y=df['avg_total_volume'],
            name='Volume',
            marker_color='green'
        ),
        row=3, col=1
    )
    
    fig.update_xaxes(title_text=f'Time ({timezone_pref})', row=3, col=1)
    fig.update_yaxes(title_text="Ratio", row=1, col=1)
    fig.update_yaxes(title_text="bps", row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    fig.update_layout(
        title=f'{symbol} - Multi-Metric Overview',
        height=800,
        showlegend=False
    )
    
    return fig

@st.fragment()
def render_multi_metric_windows(symbol: str, timezone_pref: str = 'America/New_York', refresh_rate: int = 30000):
    
    st_autorefresh(interval=refresh_rate, key="data_multi_windowed_metrics_refresh")
    rows = _get_windowed_data(symbol)

    if rows is None:
        st.warning('Failed to get windowed data for multi-metric chart')
        return
    
    df = pd.DataFrame(rows)

    # convert UTC to specified timezone
    if 'time' in df.columns:
        df['time'] = df['time'].dt.tz_convert(timezone_pref)
    else:
        st.error(f"Expected 'time' column not found in data columns: {df.columns.tolist()}")
        return

    fig = _create_multi_metric_windows(df, symbol, timezone_pref)

    st.plotly_chart(fig, width='stretch')

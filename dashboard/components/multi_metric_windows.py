import streamlit as st
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from dashboard.utils.async_runner import run_async

def _get_windowed_data(symbol: str):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_windowed_aggregates(symbol))


def _create_multi_metric_windows(df, symbol: str, timezone_pref: str):
    """Show imbalance, spread, and volume in subplots."""
    
    # query = """
    #     SELECT 
    #         window_end as time,
    #         avg_imbalance,
    #         avg_spread_bps,
    #         avg_total_volume,
    #         sample_count
    #     FROM orderbook_metrics_windowed
    #     WHERE symbol = $1
    #         AND window_type = '5m_sliding'
    #         AND window_end >= NOW() - INTERVAL '2 hours'
    #     ORDER BY window_end ASC
    # """
    
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

def render_multi_metric_windows(symbol: str, timezone_pref: str = 'America/New_York'):
    rows = _get_windowed_data(symbol)

    if rows is None:
        st.warning('Failed to get windowed data for multi-metric chart')
        return
    
    df = pd.DataFrame(rows)
    df['time'] = df['time'].dt.tz_convert(timezone_pref)

    fig = _create_multi_metric_windows(df, symbol, timezone_pref)

    st.plotly_chart(fig, use_container_width=True)

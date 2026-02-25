import plotly.graph_objects as go
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async

def _get_imb_trend_data(symbol: str, window_type: str = '5m_sliding'):
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None

    return run_async(data_layer.get_windowed_aggregates(symbol, window_type), timeout=5)

def _create_imbalance_chart(df):
    """Show imbalance trend with min/max bands."""

    # Create figure
    fig = go.Figure()
    
    # Add confidence band (min/max)
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['max_imbalance'],
        fill=None,
        mode='lines',
        line_color='rgba(100,100,100,0)',
        showlegend=False,
        name='Max'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['min_imbalance'],
        fill='tonexty',
        mode='lines',
        line_color='rgba(100,100,100,0)',
        fillcolor='rgba(68,114,196,0.2)',
        name='Range',
        showlegend=True
    ))
    
    # Add average line
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['avg_imbalance'],
        mode='lines+markers',
        name='Average Imbalance',
        line=dict(color='rgb(68,114,196)', width=3),
        marker=dict(size=6)
    ))
    
    # Add zero line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        annotation_text="Neutral"
    )
    
    return fig

@st.fragment()
def render_imbalance_trend(symbol: str, timezone_pref: str = 'America/New_York', refresh_rate: int = 10000):
    st_autorefresh(interval=refresh_rate, key="data_imbalance_refresh")

    rows = _get_imb_trend_data(symbol)
    
    df = pd.DataFrame(rows)
    # convert UTC to specified timezone
    df['time'] = df['time'].dt.tz_convert(timezone_pref)

    fig = _create_imbalance_chart(df)

    if fig is None:
        st.warning('Failed to find valid data for imbalance chart')
        return

    fig.update_layout(
        title=f'{symbol} - Imbalance Trend (Last Hour)',
        xaxis_title='Time',
        yaxis_title='Imbalance Ratio',
        hovermode='x unified',
        height=400
    )

    st.plotly_chart(
        fig,
        width='stretch'
    )
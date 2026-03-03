"""Time series chart components."""
from typing import Dict, List
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import pandas as pd
import json

from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async

# TODO: Create time series charts
# - Dual-axis plots
# - Zooming and panning

# streamlit plotly: https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart


# Get last hour of data at 5-minute intervals
# data = await data_layer.get_time_series_last_n_hours(
#     symbol="BTCUSDT",
#     hours=1,
#     interval="5m"
# )

# # Convert to DataFrame for Plotly
# df = pd.DataFrame(data)
# fig = px.line(df, x='time', y='mid_price')
# st.plotly_chart(fig)

def _get_timeseries_data(
        symbol: str,
        hours: int = 1,
        interval: str = '5m',
    ):
    data_client = st.session_state.get("data_layer")
    if data_client is None:
        return None

    data = run_async(data_client.get_time_series_last_n_hours(symbol, hours, interval), timeout=10)
    return data

def _get_alerts(
        symbol: str,
        limit: int = 100
    ):
    data_client = st.session_state.get("data_layer")
    if data_client is None:
        return None

    alerts = run_async(data_client.get_recent_alerts(
        symbol=symbol,
        limit=limit 
    ))
    return alerts

def create_imbalance_chart(df, alerts: List[Dict]):
    # dual-axis = left = imbalance %; right = price
    fig = make_subplots(specs=[[{ 'secondary_y': True }]])

    fig.add_trace(go.Scatter(x=df['time'], y=df['imbalance_ratio'], name='Imbalance', ), secondary_y=False)
    # line=dict(color='#3B82F6')

    fig.add_trace(go.Scatter(x=df['time'], y=df['mid_price'], name='Price'), secondary_y=True)
    # line=dict(color='#8B5CF6')

    # Add zero line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        annotation_text="Neutral"
    )

    # alert markers
    for alert in alerts:
        fig.add_vline(x=alert['time'], line_color='#EF4444')

    fig.update_layout(
        margin={'l': 10, 'r': 10, 't': 20, 'b': 20},
        # legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.0, 'x': 0.0},
        legend={ 'orientation': 'h' },
        title='Imbalance & Price',
    )

    return fig



@st.fragment()
def render_timeseries_chart(symbol: str, hours: int = 1, interval: str = '5m', timezone_pref: str = 'America/New_York', refresh_rate: int = 10000):
    st_autorefresh(interval=refresh_rate, key="data_timeseries_refresh")

    data = _get_timeseries_data(symbol, hours, interval)

    df = pd.DataFrame(data)

    if df.empty or 'time' not in df.columns:
        st.warning(f'failed to load timeseries chart data for {symbol}')
        return None

    alerts = _get_alerts(symbol, 100)

    # print(f'timeseries data: {json.dumps(data[:1], indent=4, default=str)}')
    # print(f'alert data: {json.dumps(alerts[:1], indent=4, default=str)}')

    fig = create_imbalance_chart(df, alerts)

    if fig is None:
        st.warning('Failed to find valid data for timeseries chart')
        return 
        
    st.plotly_chart(fig)

# timeseries_data = [{
#     "time": "2026-02-23 19:12:11.218277+00:00",
#     "symbol": "SOLUSDT",
#     "mid_price": 78.895,
#     "imbalance_ratio": 0.4949552689031068,
#     "spread_bps": 3.8025223398188905,
#     "bid_volume": 651.207,
#     "ask_volume": 219.99899999999997,
#     "total_volume": 871.2059999999999
# }]

# alert_data = [{
#     "id": 512,
#     "time": "2026-02-23 20:12:03.194896+00:00",
#     "symbol": "SOLUSDT",
#     "alert_type": "SPREAD_WIDENING",
#     "severity": "HIGH",
#     "message": "Spread 8.94 bps > 2.0\u00d7 avg (4.31)",
#     "metric_value": 8.93826214645894,
#     "threshold_value": 8.625210494867407,
#     "side": null,
#     "mid_price": null,
#     "imbalance_ratio": null
# }]
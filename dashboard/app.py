import streamlit as st
import pandas as pd
from numpy.random import default_rng as rng

from dashboard.components.alert_feed import render_alert_feed
from dashboard.components.imbalance_trend import render_imbalance_trend
from dashboard.components.metrics_cards import render_metrics_cards
from dashboard.components.multi_metric_windows import render_multi_metric_windows
from dashboard.components.orderbook_viz import render_orderbook_viz
from dashboard.components.services_health_status import render_status_indicators
from dashboard.components.timeseries import render_timeseries_chart
from dashboard.components.volatility_heatmap import render_volatility_heatmap
from dashboard.components.windowed_aggregates import render_windowed_aggregates
from dashboard.components.windowed_statistics import render_windowed_stats
from dashboard.data.data_layer import DataLayer

# Initialize once per session
if 'data_layer' not in st.session_state:
    st.session_state.data_layer = DataLayer()

render_status_indicators()

# st.title('Crypto Orderbook Dashboard')
st.set_page_config(
    page_title='Crypto Orderbook Dashboard',
    page_icon=':chart_with_upwards_trend:',
    layout='wide',
)

"""
# :material/query_stats: Crypto Orderbook Pipeline

Stream orderbook data in real-time with metric calculations & alerts.
"""

# st.sidebar.title()
# st.logo(f'🚀 Stock Pipeline')
# st.logo(sidebar_logo, icon_image=main_body_logo) # https://docs.streamlit.io/develop/api-reference/media/st.logo


# TODO: get symbols from config
symbol = st.sidebar.selectbox(
    'Symbol',
    ('SOLUSDT', 'BTCUSDT', 'ETHUSDT')
)

interval = st.sidebar.selectbox(
    'Interval',
    ('1m', '5m', '1h', '4h', '1d')
)
st.sidebar.caption('not currently using interval input')

refresh_rate = st.sidebar.selectbox(
    'Refresh rate',
    ('1s')
)
st.sidebar.caption('refresh rate not implemented yet')

timezone_pref = st.sidebar.selectbox(
    'Timezone',
    ['America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/London', 'UTC']
)

st.sidebar.space('stretch')



# # Get latest metrics for all watch list symbols
# symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# all_metrics = await data_layer.get_multiple_symbols(symbols)

# for symbol, metrics in all_metrics.items():
#     if metrics:
#         st.write(f"{symbol}: ${metrics['mid_price']}")

# display metrics (price, imbalance, spread, volume)
# need current and previous period to display metrics cards ??
render_metrics_cards(symbol)

# display real-time imbalance chart
with st.container(border=True):
    render_timeseries_chart(symbol, hours=1, interval=interval)

with st.container(border=True):
    render_orderbook_viz(symbol=symbol, depth_levels=20, refresh_rate=refresh_rate)

# two columns: spread & volatility; volume distribution


# active alerts
render_alert_feed(symbol=symbol, limit=50)
# with st.container():
#     st.text('🚨 Active Alerts')
#     st.button('🔕 Clear All (not implemented)')
#     render_alert_feed(symbol)

# two columns: windowed statistics; alert frequency
col_windowed_stats, col_alert_freq = st.columns(2)

with col_windowed_stats:
    st.text('📊 Windowed Statistics')
    render_windowed_stats(symbol)

with col_alert_freq:
    # st.bar_chart()
    st.text('TODO: Alert Frequency')


with st.container(border=True):
    render_imbalance_trend(symbol, timezone_pref)

with st.container(border=True):
    render_volatility_heatmap(symbol=symbol, timezone_pref=timezone_pref)

with st.container(border=True):
    render_multi_metric_windows(symbol=symbol, timezone_pref=timezone_pref)

# advanced controls:
# time range; chart type; export CSV
# st.text('Config/Settings')

# system status: redpanda, flink jobs, timescaleDB, redis, consumers
st.text('System Status')
import streamlit as st
import pandas as pd
from numpy.random import default_rng as rng

from dashboard.components.metrics_cards import render_metrics_cards
from dashboard.components.orderbook_viz import render_orderbook_viz
from dashboard.components.services_health_status import render_status_indicators
from dashboard.components.timeseries import render_timeseries_chart
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

refresh_rate = st.sidebar.selectbox(
    'Refresh rate',
    ('1s')
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

# two columns: windowed statistics; alert frequency
col_windowed_stats, col_alert_freq = st.columns(2)

df = pd.DataFrame(
    rng(0).standard_normal((50, 20)), columns=("col %d" % i for i in range(20))
)

with col_windowed_stats:
    st.text('Windowed Statistics')
    st.dataframe(df)

with col_alert_freq:
    # st.bar_chart()
    st.text('Alert Frequency')

# # Get last hour of 5-minute windows (12 windows)
# windows = await data_layer.get_windowed_aggregates(
#     symbol="BTCUSDT",
#     window_type="5m_sliding",
#     limit=12
# )

# # Show average imbalance over time
# avg_imbalances = [w['avg_imbalance'] for w in windows]
# st.line_chart(avg_imbalances)


# advanced controls:
# time range; chart type; export CSV
st.text('Config/Settings')

# system status: redpanda, flink jobs, timescaleDB, redis, consumers
st.text('System Status')
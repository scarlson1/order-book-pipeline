
# from dashboard.data.data_layer import DataLayer

# data_layer = DataLayer()

# # Dashboard doesn't know if this comes from Redis or DB!
# metrics = await data_layer.get_latest_metrics('BTCUSDT')

# st.metric("Imbalance", f"{metrics['imbalance_ratio']:.2%}")

import streamlit as st
import pandas as pd

from dashboard.components.metrics_cards import render_metrics_cards

# st.title('Crypto Orderbook Dashboard')
st.set_page_config(
    page_title='Crypto Orderbook Dashboard',
    page_icon=':chart_with_upwards_trend:',
    layout='wide',
)

# st.logo(image, *, size="medium", link=None, icon_image=None)
# st.logo(
#     LOGO_URL_LARGE,
#     # link="https://streamlit.io/gallery",
#     icon_image=LOGO_URL_SMALL,
# )

"""
# :material/query_stats: Crypto Orderbook Pipeline

Stream orderbook data in real-time with metric calculations & alerts.
"""

# Add a selectbox to the sidebar:
# TODO: get symbols from config
symbol = st.sidebar.selectbox(
    'Symbol',
    ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
)

# Add a slider to the sidebar:
add_slider = st.sidebar.slider(
    'Select a range of values',
    0.0, 100.0, (25.0, 75.0)
)

# # Get latest metrics for all watchlist symbols
# symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
# all_metrics = await data_layer.get_multiple_symbols(symbols)

# for symbol, metrics in all_metrics.items():
#     if metrics:
#         st.write(f"{symbol}: ${metrics['mid_price']}")

# display metrics (price, imbalance, spread, volume)
# need current and previous period to display metrics cards ??
render_metrics_cards(symbol)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Sales", value="1500", delta="10%")

with col2:
    st.metric(label="Profit", value="$12k", delta="-2%")

with col3:
    st.metric(label="Customers", value="450", delta="50", delta_color="inverse")

# display real-time imbalance chart

# two columns: spread & volatility; volume distribution

# active alerts

# two columns: windowed statistics; alert frequency

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

# system status: redpanda, flink jobs, timescaleDB, redis, consumers
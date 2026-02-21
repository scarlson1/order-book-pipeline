
# from dashboard.data.data_layer import DataLayer

# data_layer = DataLayer()

# # Dashboard doesn't know if this comes from Redis or DB!
# metrics = await data_layer.get_latest_metrics('BTCUSDT')

# st.metric("Imbalance", f"{metrics['imbalance_ratio']:.2%}")

import streamlit as st
import pandas as pd

from dashboard.components.metrics_cards import render_metrics_cards

st.set_page_config(
    page_title="Crypto Orderbook Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
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
add_selectbox = st.sidebar.selectbox(
    'Symbol',
    ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
)

# Add a slider to the sidebar:
add_slider = st.sidebar.slider(
    'Select a range of values',
    0.0, 100.0, (25.0, 75.0)
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Sales", value="1500", delta="10%")

with col2:
    st.metric(label="Profit", value="$12k", delta="-2%")

with col3:
    st.metric(label="Customers", value="450", delta="50", delta_color="inverse")


import sys
from pathlib import Path

from dashboard.components.alert_heatmap import render_alert_heatmap
from dashboard.components.orderbook_depth_heatmap import render_depth_heatmap

# Add project root to sys.path for Streamlit Cloud compatibility
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.components.alert_feed import render_alert_feed
from dashboard.components.gauge import render_imbalance_gauge
from dashboard.components.imbalance_trend import render_imbalance_trend
from dashboard.components.metrics_cards import render_metrics_cards
from dashboard.components.multi_metric_windows import render_multi_metric_windows
from dashboard.components.orderbook_viz import render_orderbook_viz
from dashboard.components.services_health_status import render_status_indicators
from dashboard.components.timeseries import render_timeseries_chart
from dashboard.components.volatility_heatmap import render_volatility_heatmap
# from dashboard.components.windowed_aggregates import render_windowed_aggregates
from dashboard.components.windowed_statistics import render_windowed_stats
from dashboard.components.infra_metrics import render_infra_metrics
from dashboard.data.data_layer import DataLayer
from src.config import settings

# Initialize once per session
if 'data_layer' not in st.session_state:
    st.session_state.data_layer = DataLayer()

render_status_indicators()

# st.title('Crypto Orderbook Dashboard')
st.set_page_config(
    page_title='Crypto Orderbook Dashboard',
    page_icon=':chart_with_upwards_trend:',
    layout='wide',
    initial_sidebar_state="expanded"
)

"""
# :material/query_stats: Crypto Orderbook Pipeline

Stream orderbook data in real-time with metric calculations & alerts.
"""

# st.sidebar.title()
# st.logo(f'🚀 Stock Pipeline')
# st.logo(sidebar_logo, icon_image=main_body_logo) # https://docs.streamlit.io/develop/api-reference/media/st.logo

symbol = st.sidebar.selectbox(
    'Symbol',
    settings.symbol_list
)

timezone_pref = st.sidebar.selectbox(
    'Timezone',
    ['America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/London', 'UTC'],
    index=0
)

st.sidebar.space('stretch')

# doesn't work (need to go CSS injection route to switch themes)
# # Initialize theme state
# if "theme" not in st.session_state:
#     st.session_state.theme = "dark"

# # Sidebar theme switcher
# # with st.sidebar:
#     # st.header("⚙️ Settings")
# theme_choice = st.sidebar.radio(
#     "Choose Theme:",
#     options=["light", "dark"],
#     index=0 if st.session_state.theme == "light" else 1
# )

# if theme_choice != st.session_state.theme:
#     st.session_state.theme = theme_choice
#     st.rerun()

# display metrics (price, imbalance, spread, volume)
render_metrics_cards(symbol)

# display real-time imbalance chart
with st.container(border=True):
    render_timeseries_chart(symbol, hours=1, timezone_pref=timezone_pref)

with st.container(border=True):
    render_orderbook_viz(symbol=symbol, depth_levels=20)


# active alerts
render_alert_feed(symbol=symbol, limit=50)


with st.container(border=True):
    render_alert_heatmap(symbol)

with st.container(border=True):
    render_imbalance_trend(symbol, timezone_pref)

# with st.container(border=True):
#     render_multi_metric_windows(symbol=symbol, timezone_pref=timezone_pref)

with st.container(border=True):
    render_depth_heatmap(symbol, timezone_pref)

with st.container(border=True):
    render_volatility_heatmap(symbol=symbol, timezone_pref=timezone_pref)

render_infra_metrics()

# # two columns: windowed statistics; alert frequency
# col_windowed_stats, col_alert_freq = st.columns(2)

# with col_windowed_stats:
#     st.text('📊 Windowed Statistics')
#     render_windowed_stats(symbol, timezone_pref=timezone_pref)

# with col_alert_freq:
#     # st.bar_chart()
#     # st.text('TODO: Alert Frequency')
#     st.text('Imbalance Ratio')
#     render_imbalance_gauge(symbol)
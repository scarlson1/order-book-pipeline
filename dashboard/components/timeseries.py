"""Time series chart components."""
import plotly.graph_objects as go
import streamlit as st

# TODO: Create time series charts
# - Dual-axis plots
# - Zooming and panning

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
"""Chart configuration helpers."""
# TODO: Chart utilities
# - Plotly themes
# - Common configurations

import streamlit as st

st.header("Chart elements")
chart_data = st.session_state.chart_data
map_data = st.session_state.map_data

st.subheader("Area chart")
st.area_chart(chart_data)
st.subheader("Bar chart")
st.bar_chart(chart_data)
st.subheader("Line chart")
st.line_chart(chart_data)
st.subheader("Scatter chart")
st.scatter_chart(chart_data)
st.subheader("Map")
st.map(map_data)

# import streamlit as st
# import plotly.express as px

# df = px.data.gapminder().query("year==2007")
# fig = px.scatter(df, x="gdpPercap", y="lifeExp", size="pop", color="continent")

# # Default Streamlit Theme
# st.plotly_chart(fig, theme="streamlit")

# # Native Plotly Theme
# st.plotly_chart(fig, theme=None)

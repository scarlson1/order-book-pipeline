"""Imbalance gauge component."""
import plotly.graph_objects as go
import streamlit as st

# https://plotly.com/python/gauge-charts/

# TODO: Create gauge visualization
# - Plotly indicator gauge (imbalance ratio visualization)
# - Color coding



# fig = go.Figure(go.Indicator(
#     domain = {'x': [0, 1], 'y': [0, 1]},
#     value = 450,
#     mode = "gauge+number+delta",
#     title = {'text': "Speed"},
#     delta = {'reference': 380},
#     gauge = {'axis': {'range': [None, 500]},
#              'steps' : [
#                  {'range': [0, 250], 'color': "lightgray"},
#                  {'range': [250, 400], 'color': "gray"}],
#              'threshold' : {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 490}}))

# fig.show()
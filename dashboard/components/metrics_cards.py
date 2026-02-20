"""Metric display cards."""

# TODO: Create metric cards
# - Current values
# - Delta indicators

# https://docs.streamlit.io/get-started/fundamentals/main-concepts

"""
# My first app
Here's our first attempt at using data to create a table:
"""

import streamlit as st
import pandas as pd
df = pd.DataFrame({
  'first column': [1, 2, 3, 4],
  'second column': [10, 20, 30, 40]
})

df
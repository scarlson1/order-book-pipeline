
# from dashboard.data.data_layer import DataLayer

# data_layer = DataLayer()

# # Dashboard doesn't know if this comes from Redis or DB!
# metrics = await data_layer.get_latest_metrics('BTCUSDT')

# st.metric("Imbalance", f"{metrics['imbalance_ratio']:.2%}")

import streamlit as st
import pandas as pd
df = pd.DataFrame({
  'first column': [1, 2, 3, 4],
  'second column': [10, 20, 30, 40]
})

df
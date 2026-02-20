
from dashboard.data.data_layer import DataLayer

data_layer = DataLayer()

# Dashboard doesn't know if this comes from Redis or DB!
metrics = await data_layer.get_latest_metrics('BTCUSDT')

st.metric("Imbalance", f"{metrics['imbalance_ratio']:.2%}")
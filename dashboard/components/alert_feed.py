"""Alert feed component."""
import streamlit as st

# TODO: Create alert feed
# - Recent alerts table
# - Filtering

# # Get last 50 alerts (Redis first, DB fallback)
# alerts = await data_layer.get_recent_alerts(limit=50)

# for alert in alerts:
#     if alert['severity'] == 'CRITICAL':
#         st.error(f"🔴 {alert['alert_type']}: {alert['message']}")
#     elif alert['severity'] == 'HIGH':
#         st.warning(f"🟠 {alert['alert_type']}: {alert['message']}")
"""Alert feed component."""
from typing import Any, Optional
import streamlit as st
from streamlit.column_config import DatetimeColumn, TextColumn, NumberColumn
import pandas as pd
from datetime import datetime, timedelta

from src.common.models import AlertType, Severity
from dashboard.utils.async_runner import run_async

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

def _get_alerts(symbol: str, limit: int = 50, since: Optional[datetime] = None) -> dict[str, Any] | None:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return []
    if hasattr(data_layer, "get_orderbook_snapshot"):
        return run_async(data_layer.get_recent_alerts(symbol, limit, since), timeout=5) or []
    return []

def _severity_icon(severity):
    colors = {
        "CRITICAL": "🔴",
        "HIGH": "🟠", 
        "MEDIUM": "🟡",
        "LOW": "⚪"
    }
    return colors.get(severity.upper(), "⚪")

# or use get_color_for_severity from utils ??
def _severity_color(severity: str) -> str:
    """Return Streamlit color for severity level."""
    colors = {
        "CRITICAL": "red",
        "HIGH": "orange", 
        "MEDIUM": "yellow",
        "LOW": "gray",
    }
    return colors.get(severity.upper(), "gray")

def _render_alert_summary(alerts: list[dict]) -> None:
    """Render summary metrics at the top."""
    if not alerts:
        st.info("No alerts in the selected time window")
        return

    # Count by severity
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for alert in alerts:
        sev = alert.get("severity", "LOW")
        if sev.upper() in counts:
            counts[sev.upper()] += 1

    # Display metric cards in columns
    cols = st.columns(4)
    for idx, (severity, count) in enumerate(counts.items()):
        with cols[idx]:
            color = _severity_color(severity)
            icon = _severity_icon(severity)
            st.metric(
                label=f"{icon} {severity}",
                value=count,
                delta_color="inverse" if severity in ("CRITICAL", "HIGH") else "normal",
            )

def _render_alert_table(alerts: list[dict], severity_filter: str = 'ALL') -> None:
    if not alerts:
        st.warning('No alerts to display')
        return

    df = pd.DataFrame(alerts)

    if severity_filter != 'ALL':
        df = df[df['severity'].str.upper() == severity_filter.upper()]

    if df.empty:
        st.info(f'No {severity_filter} alerts found')

    df['severity_icon'] = df['severity'].apply(_severity_icon)

    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])

    column_config = {
        'time': DatetimeColumn('Time', format='MMM DD HH:mm:ss', pinned=True),
        'symbol': TextColumn('Symbol', width="small",
            help="Trading pair",),
        'severity_icon': TextColumn('Sev', width="small",
            help="Severity level",),
        'alert_type': TextColumn('Type', width="medium",
            help="Type of alert",),
        'message': TextColumn('Message', width="large",
            help="Alert details",),
        'metric_value': NumberColumn('Value', width="small",
            format="%.3f",
            help="Triggering metric value",),
        'threshold_value': NumberColumn('Threshold',width="small", 
            format="%.3f",
            help="Threshold that was exceeded",),
    }

    # only show columns if available
    available_config = { k: v for k, v in column_config.items() if k in df.columns }

    st.dataframe(
        df,
        column_config=available_config,
        hide_index=True,
        width='stretch',
        height=400
    )


def _render_alert_details(alerts: list[dict], max_display: int = 5) -> None:
    '''Render expandable alert details for recent critical/high alerts'''
    important_alerts = [
        a for a in alerts
        if a.get('severity', '').upper() in ('CRITICAL', 'HIGH')
    ][:max_display]

    if not important_alerts:
        return
    
    with st.expander(f'⚠️ Recent Critical Alerts ({len(important_alerts)})', expanded=True):
        for alert in important_alerts:
            severity = alert.get('severity', 'LOW')
            color = _severity_color(severity)
            icon = _severity_icon(severity)

            with st.container(border=True):
                st.markdown(
                    f"""
                    **{icon} {alert.get('symbol', 'N/A')}** | `{alert.get('alert_type', 'UNKNOWN')}` | {alert.get('severity', 'N/A')}

                    {alert.get('message', 'No message')}

                    Value: **{alert.get('metric_value', 'N/A')}** | Threshold: **{alert.get('threshold_value', 'N/A')}**
                    """
                )


def render_alert_feed(
    symbol: str,
    limit: int= 50,
    time_window: str = '1h'
) -> None:
    st.subheader(f'🔔 Alerts: {symbol}')

    # Use timezone-aware datetime for comparison
    now = datetime.now()
    if time_window == '1h':
        since = now - timedelta(hours=1)
    elif time_window == '24h':
        since = now - timedelta(days=1)
    elif time_window == '7d':
        since = now - timedelta(days=7)
    else:
        since = None

    alerts = _get_alerts(symbol, limit)

    # filter time window if needed
    if since and alerts:
        alerts = [
            a for a in alerts
            if pd.to_datetime(a.get('time')).tz_localize(None) >= since
        ]

    col_filter, col_type, col_window = st.columns([2, 1, 1])

    with col_filter:
        severity_filter = st.segmented_control(
            'Filter by severity',
            options=['ALL', *[e.name for e in Severity]],
            # options=['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
            default='ALL',
            key='alert_severity_filter'
        )

    with col_type:
        type_filter = st.selectbox(
            'Alert Type',
            options=['ALL', *[e.name for e in AlertType]],
            index=0,
            key='alert_type_filter'
        )

    with col_window:
        st.selectbox(
            "Time window",
            options=["1h", "24h", "7d"],
            index=0,
            key="alert_time_window",
        )

    # Re-filter based on updated controls
    if (severity_filter != 'ALL' or type_filter != 'ALL') and alerts:
        alerts = [
            a for a in alerts
            if (severity_filter == 'ALL' or a.get("severity", "").upper() == severity_filter.upper())
            and (type_filter == 'ALL' or a.get("alert_type", "").upper() == type_filter.upper())
        ]

    _render_alert_summary(alerts)

    st.markdown('---')

    _render_alert_table(alerts, severity_filter)

    # expandable details for important alerts
    _render_alert_details(alerts)

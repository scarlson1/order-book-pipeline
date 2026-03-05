"""
dashboard/components/alert_heatmap.py

Alert Type × Severity heatmap.

Shows count of alerts per (alert_type, severity) combination as a
colour-encoded grid — immediately reveals which conditions are firing
most and at what severity.

Add to app.py:
    from dashboard.components.alert_heatmap import render_alert_heatmap
    ...
    with st.container(border=True):
        render_alert_heatmap(symbol=symbol)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async
from src.common.models import AlertType, Severity

# ── canonical ordering ────────────────────────────────────────────────────────

# Severity: left → right, low → critical
SEVERITY_ORDER = [s.value for s in (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)]

# Alert types: top → bottom
ALERT_TYPE_ORDER = [a.value for a in AlertType]

# Severity axis colour for annotations
SEVERITY_COLORS = {
    "LOW":      "rgba(100,180,100,0.9)",
    "MEDIUM":   "rgba(220,180,50,0.9)",
    "HIGH":     "rgba(220,120,30,0.9)",
    "CRITICAL": "rgba(210,50,50,0.9)",
}


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

def _get_alerts(symbol: str, since: datetime | None) -> list[dict]:
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return []
    return run_async(
        data_layer.get_recent_alerts(symbol=symbol, limit=1000, since=since),
        timeout=10,
    ) or []


# ─────────────────────────────────────────────────────────────────────────────
# Pivot + figure
# ─────────────────────────────────────────────────────────────────────────────

def _build_pivot(alerts: list[dict]) -> pd.DataFrame:
    """
    Returns a DataFrame shaped (alert_type × severity) with counts.
    All canonical categories are present even if count = 0.
    """
    df = pd.DataFrame(alerts)

    if df.empty:
        return pd.DataFrame(0, index=ALERT_TYPE_ORDER, columns=SEVERITY_ORDER)

    df["alert_type"] = df["alert_type"].str.upper()
    df["severity"]   = df["severity"].str.upper()

    # keep only known categories
    df = df[
        df["alert_type"].isin(ALERT_TYPE_ORDER) &
        df["severity"].isin(SEVERITY_ORDER)
    ]

    pivot = (
        df.groupby(["alert_type", "severity"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=ALERT_TYPE_ORDER, columns=SEVERITY_ORDER, fill_value=0)
    )
    return pivot


def _build_figure(pivot: pd.DataFrame, symbol: str, window_label: str) -> go.Figure:
    z      = pivot.values.astype(float)
    x_cats = pivot.columns.tolist()   # severity   (L → R)
    y_cats = pivot.index.tolist()     # alert type (T → B)

    # ── annotation text: count + percentage of row total ─────────────
    row_totals = z.sum(axis=1, keepdims=True)
    text_matrix = []
    for row_i, row in enumerate(z):
        row_total = row_totals[row_i, 0]
        text_row = []
        for val in row:
            if val == 0:
                text_row.append("")
            elif row_total > 0:
                pct = val / row_total * 100
                text_row.append(f"<b>{int(val)}</b><br><span style='font-size:10px'>{pct:.0f}%</span>")
            else:
                text_row.append(f"<b>{int(val)}</b>")
        text_matrix.append(text_row)

    # ── colorscale: white → deep red (sequential, severity-appropriate) ──
    colorscale = [
        [0.0,  "#1a1a2e"],   # zero  → near-black (dark bg)
        [0.01, "#2d1b4e"],   # trace → deep purple
        [0.3,  "#6b2d8b"],   # low   → purple
        [0.6,  "#c0392b"],   # mid   → red
        [1.0,  "#ff6b35"],   # high  → bright orange-red
    ]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_cats,
            y=y_cats,
            text=text_matrix,
            texttemplate="%{text}",
            colorscale=colorscale,
            showscale=True,
            colorbar=dict(
                title=dict(text="Count", side="right", font=dict(size=11)),
                thickness=12,
                len=0.8,
                tickfont=dict(size=10),
            ),
            hovertemplate=(
                "Alert Type: <b>%{y}</b><br>"
                "Severity: <b>%{x}</b><br>"
                "Count: <b>%{z}</b><extra></extra>"
            ),
            xgap=3,
            ygap=3,
        )
    )

    # ── severity colour band along the x-axis (decorative markers) ───
    for sev in x_cats:
        color = SEVERITY_COLORS.get(sev, "rgba(150,150,150,0.6)")
        fig.add_annotation(
            x=sev,
            y=1.06,
            yref="paper",
            text=f"<b>{sev}</b>",
            showarrow=False,
            font=dict(color=color, size=11),
            xanchor="center",
        )

    # ── row totals on the right ────────────────────────────────────────
    for row_i, alert_type in enumerate(y_cats):
        total = int(z[row_i].sum())
        fig.add_annotation(
            x=1.18,
            xref="paper",
            y=alert_type,
            text=f"<span style='color:#888;font-size:10px'>n={total}</span>",
            showarrow=False,
            xanchor="left",
            font=dict(size=10),
        )

    # ── layout ────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b>  —  Alert Type × Severity  ({window_label})",
            font=dict(size=13, color="#cccccc"),
            x=0.0,
            xanchor="left",
        ),
        paper_bgcolor="#0d0d0d",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#cccccc", size=11),
        height=340,
        margin=dict(l=180, r=100, t=60, b=60),
        xaxis=dict(
            side="bottom",
            showgrid=False,
            linecolor="rgba(255,255,255,0.1)",
            tickfont=dict(size=11),
            # hide default tick labels — replaced by annotations above
            showticklabels=False,
        ),
        yaxis=dict(
            showgrid=False,
            linecolor="rgba(255,255,255,0.1)",
            tickfont=dict(size=11),
            autorange="reversed",   # keep canonical top-to-bottom order
        ),
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit component
# ─────────────────────────────────────────────────────────────────────────────

TIME_WINDOW_OPTIONS = {
    "1h":  timedelta(hours=1),
    "6h":  timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
    "All": None,
}


@st.fragment()
def render_alert_heatmap(
    symbol: str,
    refresh_rate: int = 30_000,
) -> None:
    """
    Render the Alert Type × Severity heatmap.

    Data source: orderbook_alerts (via data_layer.get_recent_alerts)
    All five AlertType values and all four Severity levels are always
    shown — cells with zero alerts are rendered dark so the absence of
    a condition is also visible.
    """
    st_autorefresh(interval=refresh_rate, key="alert_heatmap_refresh")

    st.markdown("#### 🔥 Alert Type × Severity")

    # ── time-window selector ──────────────────────────────────────────
    window_key = st.segmented_control(
        "Time window",
        options=list(TIME_WINDOW_OPTIONS.keys()),
        default="24h",
        key="alert_heatmap_window",
    )
    delta    = TIME_WINDOW_OPTIONS[window_key]
    since    = (datetime.utcnow() - delta) if delta else None

    # ── fetch ─────────────────────────────────────────────────────────
    alerts = _get_alerts(symbol, since)

    # ── summary line ──────────────────────────────────────────────────
    total = len(alerts)
    if total == 0:
        st.info(f"No alerts for **{symbol}** in the last {window_key}.")
        # still render empty grid so shape is visible
        pivot = _build_pivot([])
    else:
        pivot = _build_pivot(alerts)

    # ── top-level KPIs ────────────────────────────────────────────────
    if total > 0:
        critical_count = int(pivot.get("CRITICAL", pd.Series(0, index=ALERT_TYPE_ORDER)).sum())
        high_count     = int(pivot.get("HIGH",     pd.Series(0, index=ALERT_TYPE_ORDER)).sum())
        dominant_type  = pivot.sum(axis=1).idxmax()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total alerts",    total)
        c2.metric("🔴 Critical",     critical_count)
        c3.metric("🟠 High",         high_count)
        c4.metric("Top alert type",  dominant_type.replace("_", " ").title())

    # ── heatmap ───────────────────────────────────────────────────────
    fig = _build_figure(pivot, symbol, window_key)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    # ── raw counts table (collapsed) ──────────────────────────────────
    with st.expander("Raw counts", expanded=False):
        max_val = pivot.values.max()

        def _color_cell(val: float) -> str:
            """Scale cell background from dark → red without matplotlib."""
            if max_val == 0 or val == 0:
                return "background-color: #1a1a2e; color: #555555"
            intensity = val / max_val          # 0.0 → 1.0
            r = int(40  + intensity * 215)     # 40  → 255
            g = int(10  + intensity * 30)      # 10  → 40
            b = int(30  + intensity * 10)      # 30  → 40
            text = "#ffffff" if intensity > 0.4 else "#aaaaaa"
            return f"background-color: rgb({r},{g},{b}); color: {text}"

        st.dataframe(
            pivot.style.map(_color_cell),
            use_container_width=True,
        )
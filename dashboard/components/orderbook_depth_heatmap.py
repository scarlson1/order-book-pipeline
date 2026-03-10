"""
dashboard/components/orderbook_depth_heatmap.py

Order Book Depth Heatmap approximated from windowed aggregate data.

Heatmap approximation strategy (5m_sliding windows):
  - Y-axis price levels: avg_mid_price ± range derived from avg_spread_bps
  - Volume per level: Gaussian centered on mid, skewed by avg_imbalance,
    scaled by avg_total_volume
  - Distribution width: broadened by (max_spread_bps - min_spread_bps),
    i.e. wider when spread was volatile during that window
  - Bid side (below mid): boosted when avg_imbalance > 0
  - Ask side (above mid): boosted when avg_imbalance < 0

Add to app.py:
    from dashboard.components.orderbook_depth_heatmap import render_depth_heatmap
    ...
    with st.container(border=True):
        render_depth_heatmap(symbol=symbol, timezone_pref=timezone_pref)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.utils.async_runner import run_async


# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────

def _get_windowed_data(symbol: str, limit: int = 100) -> list[dict] | None:
    """
    Fetch 5m_sliding windowed aggregates (most recent `limit` windows).
    Returns list of dicts with at minimum:
        window_end, avg_mid_price, avg_imbalance, min_imbalance, max_imbalance,
        avg_spread_bps, min_spread_bps, max_spread_bps,
        avg_bid_volume, avg_ask_volume, avg_total_volume
    """
    data_layer = st.session_state.get("data_layer")
    if data_layer is None:
        return None
    return run_async(
        data_layer.get_windowed_aggregates(symbol, window_type="5m_sliding", limit=limit),
        timeout=10,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Heatmap approximation
# ─────────────────────────────────────────────────────────────────────────────

def _build_heatmap_matrix(
    df: pd.DataFrame,
    n_price_levels: int = 60,
    price_band_multiplier: float = 8.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert windowed aggregate rows into a (price_levels × time) heatmap matrix.

    Parameters
    ----------
    df                  : windowed DataFrame sorted ascending by window_end
    n_price_levels      : vertical resolution of the heatmap
    price_band_multiplier: how many spread-widths above/below mid to show

    Returns
    -------
    heatmap   : 2-D ndarray shape (n_price_levels, n_windows)
    price_arr : 1-D ndarray of price values for the Y-axis
    """
    mid_prices   = df["avg_mid_price"].to_numpy(dtype=float)
    imbalances   = df["avg_imbalance"].fillna(0).to_numpy(dtype=float)
    spreads_avg  = df["avg_spread_bps"].fillna(2).to_numpy(dtype=float)
    spreads_min  = df["min_spread_bps"].fillna(df["avg_spread_bps"].fillna(2)).to_numpy(dtype=float)
    spreads_max  = df["max_spread_bps"].fillna(df["avg_spread_bps"].fillna(2)).to_numpy(dtype=float)
    total_vols   = df["avg_total_volume"].fillna(1).to_numpy(dtype=float)
    bid_vols     = df["avg_bid_volume"].fillna(df["avg_total_volume"].fillna(2) / 2).to_numpy(dtype=float)
    ask_vols     = df["avg_ask_volume"].fillna(df["avg_total_volume"].fillna(2) / 2).to_numpy(dtype=float)

    global_mid   = np.nanmean(mid_prices)
    # spread in bps → absolute price spread
    avg_spread_abs = global_mid * np.nanmean(spreads_avg) / 10_000

    # build a fixed price grid spanning the entire visible window
    price_range  = global_mid * np.nanmean(spreads_max) / 10_000 * price_band_multiplier
    price_arr    = np.linspace(global_mid - price_range, global_mid + price_range, n_price_levels)

    n_windows    = len(df)
    heatmap      = np.zeros((n_price_levels, n_windows), dtype=float)

    for t, (mid, imb, sp_avg, sp_min, sp_max, tot_vol, b_vol, a_vol) in enumerate(
        zip(mid_prices, imbalances, spreads_avg, spreads_min, spreads_max,
            total_vols, bid_vols, ask_vols)
    ):
        if np.isnan(mid) or mid <= 0:
            continue

        # sigma: base width from average spread; widened when spread was volatile
        spread_abs  = mid * sp_avg / 10_000
        spread_vol  = mid * max(sp_max - sp_min, 0) / 10_000   # spread volatility
        sigma       = max(spread_abs + 0.5 * spread_vol, avg_spread_abs * 0.3)

        # ── bid side (below mid) ──────────────────────────────────────
        # Positive imbalance → more volume on bid side
        bid_weight  = 0.5 + 0.5 * max(imb, 0)   # range [0.5, 1.0]
        bid_sigma   = sigma * (1.0 + 0.4 * max(imb, 0))

        bid_dist    = np.where(
            price_arr <= mid,
            np.exp(-0.5 * ((price_arr - mid) / bid_sigma) ** 2),
            0.0,
        )
        bid_mass    = bid_dist.sum()
        if bid_mass > 0:
            heatmap[:, t] += bid_dist / bid_mass * b_vol * bid_weight

        # ── ask side (above mid) ──────────────────────────────────────
        ask_weight  = 0.5 + 0.5 * max(-imb, 0)  # range [0.5, 1.0]
        ask_sigma   = sigma * (1.0 + 0.4 * max(-imb, 0))

        ask_dist    = np.where(
            price_arr >= mid,
            np.exp(-0.5 * ((price_arr - mid) / ask_sigma) ** 2),
            0.0,
        )
        ask_mass    = ask_dist.sum()
        if ask_mass > 0:
            heatmap[:, t] += ask_dist / ask_mass * a_vol * ask_weight

    return heatmap, price_arr


# ─────────────────────────────────────────────────────────────────────────────
# Figure builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_figure(
    df: pd.DataFrame,
    heatmap: np.ndarray,
    price_arr: np.ndarray,
    symbol: str,
    timezone_pref: str,
) -> go.Figure:
    """
    Two-panel figure:
      Row 1: depth heatmap (plasma colorscale) + mid-price line + spread band
      Row 2: order book delta bars (bid_vol - ask_vol)
    """
    times = df["window_end"].tolist()
    delta = (df["avg_bid_volume"] - df["avg_ask_volume"]).fillna(0)

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.70, 0.30],
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=[
            "Order Book Depth (approximated from 5m windows)",
            "Order Book Delta (bid vol − ask vol)",
        ],
    )

    # ── heatmap ───────────────────────────────────────────────────────
    fig.add_trace(
        go.Heatmap(
            z=heatmap,
            x=times,
            y=price_arr,
            colorscale="plasma",
            zsmooth="best",
            showscale=True,
            colorbar=dict(
                x=1.01,
                thickness=12,
                len=0.68,
                tickfont=dict(size=9),
                title=dict(text="Vol", side="right", font=dict(size=10)),
            ),
            hovertemplate=(
                "Time: %{x}<br>"
                "Price: %{y:.2f}<br>"
                "Approx Vol: %{z:,.0f}<extra></extra>"
            ),
            name="Depth",
        ),
        row=1, col=1,
    )

    # ── mid-price line ────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=times,
            y=df["avg_mid_price"],
            mode="lines",
            name="Mid Price",
            line=dict(color="rgba(255,220,80,0.9)", width=1.5, dash="dot"),
            hovertemplate="Mid: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # ── spread band (min/max price range per window) ──────────────────
    mid   = df["avg_mid_price"]
    # convert bps → absolute price
    upper = mid * (1 + df["max_spread_bps"] / 10_000 / 2)
    lower = mid * (1 - df["max_spread_bps"] / 10_000 / 2)

    fig.add_trace(
        go.Scatter(
            x=list(times) + list(reversed(times)),
            y=list(upper) + list(reversed(lower)),
            fill="toself",
            fillcolor="rgba(255,255,255,0.04)",
            line=dict(color="rgba(255,255,255,0)", width=0),
            name="Spread Band",
            hoverinfo="skip",
            showlegend=True,
        ),
        row=1, col=1,
    )

    # ── delta bars ────────────────────────────────────────────────────
    bar_colors = [
        "rgba(0,210,120,0.85)" if v >= 0 else "rgba(210,50,50,0.85)"
        for v in delta
    ]
    fig.add_trace(
        go.Bar(
            x=times,
            y=delta,
            marker_color=bar_colors,
            name="OB Delta",
            hovertemplate="Delta: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    fig.add_hline(y=0, line_color="rgba(200,200,200,0.25)", line_width=1, row=2, col=1)

    # ── layout ────────────────────────────────────────────────────────
    bg       = "#0d0d0d"
    grid_col = "rgba(255,255,255,0.06)"
    ax_line  = "rgba(255,255,255,0.12)"
    font_col = "#cccccc"

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol}</b>  Order Book Depth with Price Action (5m sliding) "
                f"— approximated from windowed aggregates"
            ),
            font=dict(size=13, color=font_col),
            x=0.0,
            xanchor="left",
        ),
        # paper_bgcolor=bg,
        # plot_bgcolor=bg,
        font=dict(color=font_col, size=11),
        height=720,
        margin=dict(l=60, r=80, t=55, b=45),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            x=0.55,
            y=1.02,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        barmode="relative",
    )

    axis_style = dict(
        showgrid=True,
        gridcolor=grid_col,
        linecolor=ax_line,
        tickfont=dict(size=10),
        zeroline=False,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)

    fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Delta", row=2, col=1)
    fig.update_xaxes(title_text=f"Time ({timezone_pref})", row=2, col=1)

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit component
# ─────────────────────────────────────────────────────────────────────────────

@st.fragment()
def render_depth_heatmap(
    symbol: str,
    timezone_pref: str = "America/New_York",
    limit: int = 100,
    refresh_rate: int = 60_000,
) -> None:
    """
    Render the approximated order book depth heatmap.

    Data requirements (all already in orderbook_metrics_windowed):
        avg_mid_price, avg_imbalance, min_imbalance, max_imbalance,
        avg_spread_bps, min_spread_bps, max_spread_bps,
        avg_bid_volume, avg_ask_volume, avg_total_volume, window_end
    """
    st_autorefresh(interval=refresh_rate, key="data_depth_heatmap_refresh")

    rows = _get_windowed_data(symbol, limit=limit)

    if not rows:
        st.warning("No windowed data available for depth heatmap")
        return

    df = pd.DataFrame(rows)

    # ── validate required columns ─────────────────────────────────────
    required = {
        "window_end", "avg_mid_price", "avg_imbalance",
        "min_imbalance", "max_imbalance",
        "avg_spread_bps", "min_spread_bps", "max_spread_bps",
        "avg_bid_volume", "avg_ask_volume", "avg_total_volume",
    }
    missing = required - set(df.columns)
    if missing:
        st.error(f"Missing columns in windowed data: {missing}")
        return

    # ── timezone conversion ───────────────────────────────────────────
    df["window_end"] = pd.to_datetime(df["window_end"])
    if df["window_end"].dt.tz is None:
        df["window_end"] = df["window_end"].dt.tz_localize("UTC")
    df["window_end"] = df["window_end"].dt.tz_convert(timezone_pref)

    # sort ascending for correct time ordering in heatmap
    df = df.sort_values("window_end").reset_index(drop=True)

    # drop rows with no mid price (can't place them on price axis)
    df = df.dropna(subset=["avg_mid_price"])
    if df.empty:
        st.warning("All windowed rows are missing avg_mid_price — cannot render heatmap")
        return

    # ── build approximated heatmap matrix ─────────────────────────────
    heatmap, price_arr = _build_heatmap_matrix(df)

    # ── build & render figure ─────────────────────────────────────────
    fig = _build_figure(df, heatmap, price_arr, symbol, timezone_pref)

    st.plotly_chart(fig, width='stretch', config={"displaylogo": False})
    st.caption(
        "⚠️ Depth heatmap is **approximated** from 5m sliding window aggregates "
        "(avg_mid_price, avg_imbalance, avg_bid/ask_volume, spread). "
        "It shows relative bid/ask pressure per window — not true level-by-level depth."
    )
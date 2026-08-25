"""
Ticker Explorer - single-ticker Historicals + Fundamentals dashboard.

Layout and data-sourcing decisions are recorded in
.scratch/ticker-explorer/spec.md; this file implements them. All data
fetching/shaping lives in ticker_data.py, kept free of Streamlit so it can
be unit-tested without a running app (see spec.md's Testing Decisions).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, TypeVar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ticker_data import (
    get_fundamentals_history,
    get_fundamentals_snapshot,
    get_historicals,
    load_company_tickers,
    resolve_ticker,
)

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Ticker Explorer", layout="wide")

# Caching lives here, not in ticker_data.py -- see spec.md's Implementation
# Decisions ("use Streamlit's st.cache_data for all four data-service
# calls"). The EDGAR-derived historical series changes only on new
# filings, so it's cached far longer than the daily-refreshing snapshot
# and price data.
cached_load_company_tickers = st.cache_data(ttl=24 * 3600)(load_company_tickers)
cached_get_historicals = st.cache_data(ttl=3600)(get_historicals)
cached_get_fundamentals_snapshot = st.cache_data(ttl=3600)(get_fundamentals_snapshot)
cached_get_fundamentals_history = st.cache_data(ttl=24 * 3600)(get_fundamentals_history)

DEFAULT_LOOKBACK_DAYS = 365 * 5
# The window used to fetch the ticker's *actual* full history, so the
# right column's date-range slider can bound itself to real data (its
# earliest returned date) rather than a hardcoded number -- spec.md calls
# for "no artificial cap". This constant is just how far back the fetch
# reaches to discover that boundary, not a limit shown to the user.
FULL_HISTORY_FETCH_DAYS = 365 * 75

SPARKLINE_METRICS = ["Revenue", "NetIncome", "EPS"]

T = TypeVar("T")


def fetch_or_none(fn: Callable[..., T], *args, error_message: str, show=st.error, **kwargs) -> T | None:
    """Call fn, logging and surfacing `error_message` (via `show`, e.g.
    st.error or st.caption) instead of crashing the page on failure. Every
    external call in this app goes through here so a transient yfinance/
    EDGAR outage degrades to a visible message, per spec.md's "plain
    error state, no fallback" decision.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("%s failed", getattr(fn, "__name__", repr(fn)))
        show(error_message)
        return None


def format_price_change(change_pct: float) -> tuple[str, str]:
    sign = "+" if change_pct >= 0 else ""
    color = "#2f7d32" if change_pct >= 0 else "#b3261e"
    return f"{sign}{change_pct:.2f}%", color


def price_chart(df: pd.DataFrame, chart_type: str) -> go.Figure:
    fig = go.Figure()
    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            )
        )
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines"))
    fig.update_layout(height=440, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
    return fig


def sparkline(hist: pd.DataFrame, column: str, label: str) -> go.Figure:
    series = hist[column].dropna()
    fig = go.Figure(go.Scatter(x=series.index, y=series.values, mode="lines", line=dict(width=1.5)))
    fig.update_layout(
        height=100, margin=dict(l=0, r=0, t=18, b=0),
        title=dict(text=label, font=dict(size=12)),
        xaxis_visible=False, yaxis_visible=False,
    )
    return fig


def render_left_rail(ticker: str, cik: str | None, price_history: pd.DataFrame) -> None:
    st.markdown("**Fundamentals**")
    snapshot = fetch_or_none(
        cached_get_fundamentals_snapshot, ticker,
        error_message="Fundamentals snapshot temporarily unavailable.",
    )
    if snapshot is None:
        return

    for key, label in [
        ("market_cap", "Market Cap"),
        ("trailing_pe", "Trailing P/E"),
        ("forward_pe", "Forward P/E"),
        ("eps_ttm", "EPS (TTM)"),
        ("dividend_yield", "Dividend Yield"),
        ("sector", "Sector"),
        ("industry", "Industry"),
        ("fifty_two_week_high", "52-Wk High"),
        ("fifty_two_week_low", "52-Wk Low"),
    ]:
        value = snapshot.get(key)
        st.text(f"{label}:  {value if value is not None else '—'}")

    st.markdown("**Trends**")
    unavailable_note = "Historical depth isn't available for this ticker."

    # No CIK at all (the query didn't resolve against SEC's own ticker
    # directory) is the same "EDGAR has nothing for this one" case as a
    # CIK that resolves but has no companyfacts (e.g. an ETF, which files
    # no 10-K) -- both skip straight to the note rather than attempting
    # a call SEC's own directory has already told us can't succeed.
    if cik is None:
        st.caption(unavailable_note)
        return

    history = fetch_or_none(
        cached_get_fundamentals_history, cik, price_history,
        error_message=unavailable_note, show=st.caption,
    )
    if history is None or history.empty:
        if history is not None:
            st.caption(unavailable_note)
        return

    for metric in SPARKLINE_METRICS:
        if metric in history.columns and history[metric].notna().any():
            st.plotly_chart(sparkline(history, metric, metric), width="stretch", config={"displayModeBar": False})


def render_right_column(ticker: str, min_date: date) -> None:
    c1, c2 = st.columns([3, 1])
    with c1:
        start_date, end_date = st.slider(
            "Date range",
            min_value=min_date,
            max_value=date.today(),
            value=(max(min_date, date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)), date.today()),
        )
    with c2:
        chart_type = st.radio("Chart type", ["Line", "Candlestick"], horizontal=True)

    df = fetch_or_none(
        cached_get_historicals, ticker, start_date, end_date,
        error_message="Price data is temporarily unavailable for this ticker. Try again shortly.",
    )
    if df is None:
        return

    st.plotly_chart(price_chart(df, chart_type), width="stretch")
    st.download_button(
        "Download Historicals CSV",
        df.to_csv().encode(),
        file_name=f"{ticker}_historicals.csv",
        mime="text/csv",
    )


def main() -> None:
    query = st.text_input("Ticker or company name", value="AAPL")
    if not query.strip():
        st.stop()

    tickers = fetch_or_none(
        cached_load_company_tickers,
        error_message="Couldn't reach the ticker directory (SEC EDGAR). Try again shortly.",
    )
    if tickers is None:
        st.stop()

    matches = resolve_ticker(query, tickers)
    if matches:
        ticker, cik = matches[0]["ticker"], matches[0]["cik"]
    else:
        # Not in SEC's own ticker directory -- try it as a raw yfinance
        # symbol anyway (a real, if unusual, ticker yfinance recognizes
        # but SEC doesn't) rather than failing immediately. If that also
        # comes up empty, get_historicals raises and the block below
        # reports "no match" either way. cik stays None either way, which
        # render_left_rail treats the same as an EDGAR-no-CIK-match --
        # a snapshot with no historical depth (see spec.md).
        ticker, cik = query.strip().upper(), None

    # A wide, generous window: establishes the ticker's actual earliest
    # available date (so the date-range slider can bound itself to real
    # data rather than a hardcoded cap) and doubles as the day-change
    # figure for the hero line and the price series Fundamentals-history
    # needs for its market-cap/P-E derivation.
    full_history = fetch_or_none(
        cached_get_historicals, ticker,
        date.today() - timedelta(days=FULL_HISTORY_FETCH_DAYS), date.today(),
        error_message=f"No match found for {query!r}.",
    )
    if full_history is None:
        st.stop()

    last_close = full_history["Close"].iloc[-1]
    prev_close = full_history["Close"].iloc[-2]
    change_str, color = format_price_change((last_close - prev_close) / prev_close * 100)

    st.markdown(
        f"## {ticker}   ${last_close:,.2f}   "
        f"<span style='color:{color}; font-size:1.1rem;'>{change_str}</span>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 2])
    with left:
        render_left_rail(ticker, cik, full_history)
    with right:
        render_right_column(ticker, full_history.index.min().date())


if __name__ == "__main__":
    main()

"""
PROTOTYPE — throwaway. Not real code, not real data.

Resolves the "Ticker page layout prototype" ticket on the Ticker Explorer
wayfinder map: .scratch/ticker-explorer/issues/03-ticker-page-layout-prototype.md

Run:  streamlit run prototype_ticker_page.py
Switch variants with the selector at the top, or ?variant=A / B / C in the URL.

Second design pass: the first pass (a generic "minimal" tab and a
cyan/violet-gradient glassmorphism "futuristic" tab) read as generic
AI-generated SaaS/dashboard output. Specific tells that were removed:

- Cyan-to-violet (or any) gradients on buttons, text, or backgrounds
- Glassmorphism: translucent white panels + backdrop-blur + glow shadows
- The "uppercase tracked micro-label above a big bold number" stat-tile,
  repeated in a grid of identical cards — probably THE most common AI
  dashboard tell
- Unicode arrow glyphs (▲▼) as decoration standing in for real iconography
- Rounded corners + drop shadows applied uniformly as a default, rather
  than as a choice
- A radial-gradient "hero glow" background

Replaced with two directions that borrow from specific, real reference
points instead of generic "modern SaaS" trends:

- **Ledger**: a financial-statement/print register register. Warm paper
  background, serif display type paired with tabular monospace figures,
  hairline rules instead of cards, muted ink-green/ink-red instead of
  saturated stoplight colors.
- **Terminal**: a trading-terminal register (Bloomberg/Refinitiv-style).
  Full commitment to monospace type, flat black, a single amber accent,
  1px hairline borders — no blur, no glow, no gradient.

UI/UX principles still applied across both, unchanged from before:
- One dominant element per screen; everything else recedes.
- Every signed value pairs color with an explicit +/- sign, never color
  alone.
- The same control (date range, chart-type toggle, CSV button) behaves
  identically across variants — only the shell changes.
- Related controls sit close to what they control; unrelated groups get
  real whitespace or a rule, not just a card boundary.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="PROTOTYPE: Ticker Explorer", layout="wide")

VARIANTS = {
    "A": "Ledger",
    "B": "Terminal",
    "C": "Dashboard (hero + side-by-side)",
}

FUNDAMENTALS_HISTORY_METRICS = [
    "Revenue", "Net Income", "EPS", "Dividends/Share",
    "Shares Outstanding", "Market Cap (derived)", "Trailing P/E (derived)",
]


# ---------------------------------------------------------------- mock data

@st.cache_data
def mock_historicals(ticker: str, years: int = 15) -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(ticker)) % (2**32))
    n = years * 252
    dates = pd.bdate_range(end=date.today(), periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.018, n)))
    high = close * (1 + rng.uniform(0, 0.015, n))
    low = close * (1 - rng.uniform(0, 0.015, n))
    open_ = low + (high - low) * rng.uniform(0, 1, n)
    volume = rng.integers(1_000_000, 20_000_000, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.Index(dates, name="Date"),
    )


@st.cache_data
def mock_fundamentals_snapshot(ticker: str) -> dict:
    rng = np.random.default_rng(abs(hash(ticker + "f")) % (2**32))
    return {
        "Market Cap": f"${rng.uniform(10, 900):.1f}B",
        "Trailing P/E": f"{rng.uniform(8, 45):.1f}",
        "Forward P/E": f"{rng.uniform(8, 40):.1f}",
        "EPS (TTM)": f"${rng.uniform(1, 20):.2f}",
        "Dividend Yield": f"{rng.uniform(0, 4):.2f}%",
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
        "52-Wk High": f"${rng.uniform(150, 300):.2f}",
        "52-Wk Low": f"${rng.uniform(80, 150):.2f}",
    }


@st.cache_data
def mock_fundamentals_history(ticker: str, metric: str, years: int = 15) -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(ticker + metric)) % (2**32))
    years_list = list(range(date.today().year - years, date.today().year + 1))
    base = rng.uniform(1, 10)
    vals = base * np.cumprod(1 + rng.normal(0.06, 0.1, len(years_list)))
    return pd.DataFrame({"Year": years_list, metric: vals})


# ---------------------------------------------------------------- shared bits

def ticker_input(key_suffix: str) -> str:
    return st.text_input("Ticker or company name", value="AAPL", key=f"ticker_{key_suffix}")


def date_range_slider(key_suffix: str):
    return st.slider(
        "Date range",
        min_value=date.today() - timedelta(days=365 * 15),
        max_value=date.today(),
        value=(date.today() - timedelta(days=365 * 5), date.today()),
        key=f"range_{key_suffix}",
    )


def csv_download(df: pd.DataFrame, ticker: str, key_suffix: str, label: str = "Download Historicals CSV"):
    st.download_button(
        label, df.to_csv().encode(),
        file_name=f"{ticker}_historicals.csv", mime="text/csv",
        key=f"csv_{key_suffix}",
    )


def price_change(df: pd.DataFrame):
    last_close = df["Close"].iloc[-1]
    prev_close = df["Close"].iloc[-2]
    change = (last_close - prev_close) / prev_close * 100
    return last_close, change


def signed(change: float) -> str:
    return f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"


# ---------------------------------------------------------------- Variant A: Ledger
# A financial-statement register: warm paper background, serif display type
# for the ticker name, tabular monospace for every number, hairline rules
# instead of cards. Muted ink-green / ink-red, not stoplight red/green.

INK = "#1c1c1a"
INK_MUTED = "#6b675e"
INK_RULE = "#ddd8cc"
INK_GAIN = "#2f5233"
INK_LOSS = "#7a2e2e"

def variant_a():
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{ background: #f6f4ef; }}
        [data-testid="stAppViewContainer"] * {{ color: {INK}; }}
        .ledger-title {{ font-family: Georgia, 'Times New Roman', serif; font-weight: 400;
                          font-size: 2.1rem; margin-bottom: 0; }}
        .ledger-sub {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.95rem;
                        color: {INK_MUTED}; margin-top: 2px; }}
        .ledger-row {{ display: flex; justify-content: space-between; align-items: baseline;
                        padding: 9px 0; border-bottom: 1px solid {INK_RULE}; }}
        .ledger-row .label {{ color: {INK_MUTED}; font-size: 0.92rem; }}
        .ledger-row .value {{ font-family: ui-monospace, Menlo, Consolas, monospace;
                               font-size: 0.98rem; }}
        button {{ background: transparent !important; color: {INK} !important;
                  border: 1px solid {INK} !important; border-radius: 2px !important;
                  box-shadow: none !important; }}
        [data-testid="stTabs"] button[aria-selected="true"] {{ border-bottom: 2px solid {INK} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    ticker = ticker_input("a")
    df_full = mock_historicals(ticker)
    last_close, change = price_change(df_full)
    color = INK_GAIN if change >= 0 else INK_LOSS

    st.markdown(f"<div class='ledger-title'>{ticker}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='ledger-sub'>${last_close:,.2f} &nbsp;·&nbsp; "
        f"<span style='color:{color};'>{signed(change)} today</span></div>",
        unsafe_allow_html=True,
    )
    st.write("")

    tab_hist, tab_fund = st.tabs(["Historicals", "Fundamentals"])

    with tab_hist:
        c1, c2 = st.columns([3, 1])
        with c1:
            date_range = date_range_slider("a")
        with c2:
            chart_type = st.radio("Chart type", ["Line", "Candlestick"], key="type_a")

        df = df_full.loc[(df_full.index.date >= date_range[0]) & (df_full.index.date <= date_range[1])]

        fig = go.Figure()
        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                increasing_line_color=INK_GAIN, decreasing_line_color=INK_LOSS,
            ))
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines",
                                      line=dict(color=INK, width=1.25)))
        fig.update_layout(
            height=420, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False, plot_bgcolor="#f6f4ef", paper_bgcolor="#f6f4ef",
            font=dict(family="ui-monospace, Menlo, Consolas, monospace", color=INK_MUTED, size=11),
            xaxis=dict(showgrid=False, linecolor=INK_RULE),
            yaxis=dict(showgrid=True, gridcolor=INK_RULE),
        )
        st.plotly_chart(fig, use_container_width=True)
        csv_download(df, ticker, "a", "Download CSV")

    with tab_fund:
        snap = mock_fundamentals_snapshot(ticker)
        for k, v in snap.items():
            st.markdown(
                f"<div class='ledger-row'><span class='label'>{k}</span>"
                f"<span class='value'>{v}</span></div>",
                unsafe_allow_html=True,
            )
        st.write("")
        metric = st.selectbox("Historical metric", FUNDAMENTALS_HISTORY_METRICS, key="metric_a")
        hist = mock_fundamentals_history(ticker, metric)
        fig = go.Figure(go.Bar(x=hist["Year"], y=hist[metric], marker_color=INK))
        fig.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="#f6f4ef", paper_bgcolor="#f6f4ef",
            font=dict(family="ui-monospace, Menlo, Consolas, monospace", color=INK_MUTED, size=11),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=INK_RULE),
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------- Variant B: Terminal
# A trading-terminal register: flat black, one amber accent, full commitment
# to monospace type (not just the numbers), 1px hairline borders. No blur,
# no glow, no gradient — the restraint is the point.

TERM_BG = "#0b0b0b"
TERM_TEXT = "#d8d8d0"
TERM_AMBER = "#ffb000"
TERM_BORDER = "#333331"
TERM_GAIN = "#5fbf6a"
TERM_LOSS = "#e05a4f"

def variant_b():
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{ background: {TERM_BG}; }}
        [data-testid="stAppViewContainer"] * {{
            color: {TERM_TEXT} !important;
            font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace !important;
        }}
        .term-prompt {{ color: {TERM_AMBER}; font-size: 1.6rem; }}
        .term-row {{ display: flex; justify-content: space-between;
                     padding: 7px 10px; border: 1px solid {TERM_BORDER}; margin-bottom: -1px; }}
        .term-row .label {{ color: {TERM_TEXT}; opacity: 0.65; font-size: 0.82rem; }}
        .term-row .value {{ color: {TERM_AMBER}; font-size: 0.9rem; }}
        button {{ background: {TERM_BG} !important; color: {TERM_AMBER} !important;
                  border: 1px solid {TERM_AMBER} !important; border-radius: 0 !important;
                  box-shadow: none !important; }}
        [data-testid="stTabs"] button[aria-selected="true"] {{ border-bottom: 2px solid {TERM_AMBER} !important; }}
        input {{ background: {TERM_BG} !important; border: 1px solid {TERM_BORDER} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    ticker = ticker_input("b")
    df_full = mock_historicals(ticker)
    last_close, change = price_change(df_full)
    delta_color = TERM_GAIN if change >= 0 else TERM_LOSS

    st.markdown(f"<span class='term-prompt'>&gt; {ticker}</span>", unsafe_allow_html=True)
    st.markdown(
        f"<span style='color:{TERM_AMBER}; font-size:1.3rem;'>{last_close:,.2f}</span>"
        f"&nbsp;&nbsp;<span style='color:{delta_color};'>{signed(change)}</span>",
        unsafe_allow_html=True,
    )
    st.write("")

    tab_hist, tab_fund = st.tabs(["HISTORICALS", "FUNDAMENTALS"])

    with tab_hist:
        c1, c2 = st.columns([3, 1])
        with c1:
            date_range = date_range_slider("b")
        with c2:
            chart_type = st.radio("Chart type", ["Line", "Candlestick"], key="type_b")

        df = df_full.loc[(df_full.index.date >= date_range[0]) & (df_full.index.date <= date_range[1])]

        fig = go.Figure()
        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                increasing_line_color=TERM_GAIN, decreasing_line_color=TERM_LOSS,
            ))
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines",
                                      line=dict(color=TERM_AMBER, width=1.5)))
        fig.update_layout(
            height=420, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_rangeslider_visible=False,
            plot_bgcolor=TERM_BG, paper_bgcolor=TERM_BG,
            font=dict(family="ui-monospace, monospace", color=TERM_TEXT, size=11),
            xaxis=dict(showgrid=False, linecolor=TERM_BORDER),
            yaxis=dict(showgrid=True, gridcolor=TERM_BORDER),
        )
        st.plotly_chart(fig, use_container_width=True)
        csv_download(df, ticker, "b", "DOWNLOAD CSV")

    with tab_fund:
        snap = mock_fundamentals_snapshot(ticker)
        for k, v in snap.items():
            st.markdown(
                f"<div class='term-row'><span class='label'>{k.upper()}</span>"
                f"<span class='value'>{v}</span></div>",
                unsafe_allow_html=True,
            )
        st.write("")
        metric = st.selectbox("Historical metric", FUNDAMENTALS_HISTORY_METRICS, key="metric_b")
        hist = mock_fundamentals_history(ticker, metric)
        fig = go.Figure(go.Bar(x=hist["Year"], y=hist[metric], marker_color=TERM_AMBER))
        fig.update_layout(
            height=260, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor=TERM_BG, paper_bgcolor=TERM_BG,
            font=dict(family="ui-monospace, monospace", color=TERM_TEXT, size=11),
            xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=TERM_BORDER),
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------- Variant C: Dashboard
# Kept structurally as before: hero summary line, compact Fundamentals rail
# with sparkline trends on the left, dominant Historicals chart on the
# right. Cleaned up: arrow glyphs and the gradient-fill sparklines are gone.

def variant_c():
    ticker = ticker_input("c")
    snap = mock_fundamentals_snapshot(ticker)
    df_full = mock_historicals(ticker)
    last_close, change = price_change(df_full)
    color = "#2f7d32" if change >= 0 else "#b3261e"

    st.markdown(
        f"## {ticker}   ${last_close:,.2f}   "
        f"<span style='color:{color}; font-size:1.1rem;'>{signed(change)}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"{snap['Sector']} · {snap['Industry']}")

    left, right = st.columns([1, 2])

    with left:
        st.markdown("**Fundamentals**")
        for k, v in snap.items():
            if k in ("Sector", "Industry"):
                continue
            st.text(f"{k}:  {v}")
        st.markdown("**Trends**")
        for metric in ["Revenue", "Net Income", "EPS"]:
            hist = mock_fundamentals_history(ticker, metric)
            fig = go.Figure(go.Scatter(x=hist["Year"], y=hist[metric], mode="lines",
                                        line=dict(width=1.5)))
            fig.update_layout(
                height=100, margin=dict(l=0, r=0, t=18, b=0),
                title=dict(text=metric, font=dict(size=12)),
                xaxis_visible=False, yaxis_visible=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with right:
        date_range = date_range_slider("c")
        chart_type = st.radio("Chart type", ["Line", "Candlestick"], key="type_c", horizontal=True)
        df = df_full.loc[(df_full.index.date >= date_range[0]) & (df_full.index.date <= date_range[1])]
        fig = go.Figure()
        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                                          low=df["Low"], close=df["Close"]))
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines"))
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        csv_download(df, ticker, "c")


VARIANT_FN = {"A": variant_a, "B": variant_b, "C": variant_c}


# ---------------------------------------------------------------- switcher
# UI.md's floating-bottom-bar pattern assumes real CSS control over the DOM,
# which Streamlit's script-rerun model doesn't give cheaply. Adapted: a
# selector pinned at the very top instead, still URL-synced via
# st.query_params so a variant is shareable/reload-stable.

params = st.query_params
current = params.get("variant", "A")
if current not in VARIANTS:
    current = "A"

choice = st.radio(
    "Variant",
    list(VARIANTS.keys()),
    index=list(VARIANTS.keys()).index(current),
    format_func=lambda k: f"{k} — {VARIANTS[k]}",
    horizontal=True,
    key="variant_selector",
)
if choice != current:
    st.query_params["variant"] = choice
    st.rerun()

st.caption("PROTOTYPE · mock data · resolves issue 03 on the Ticker Explorer map")
st.divider()

VARIANT_FN[current]()

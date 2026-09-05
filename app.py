"""
Ticker Explorer - single-ticker Historicals + Fundamentals dashboard.

Layout and data-sourcing decisions are recorded in
.scratch/ticker-explorer/spec.md; this file implements them. All data
fetching/shaping lives in ticker_data.py, kept free of Streamlit so it can
be unit-tested without a running app (see spec.md's Testing Decisions).

Visual design: Hallmark's Aurora theme (atmospheric genre) -- a dark
instrument-panel canvas with two ambient aurora blooms, not the parchment
editorial-journal look this file used to have. See the design notes in
THEME_CSS below for the specific choices and why.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, TypeVar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from yfinance.exceptions import YFRateLimitError

from ticker_data import (
    build_fundamentals_pivot,
    build_peer_fundamentals_pivot,
    build_peer_price_frame,
    compute_peer_performance_stats,
    get_fundamentals_from_alpha_vantage,
    get_fundamentals_from_finnhub,
    get_fundamentals_history,
    get_fundamentals_snapshot,
    fetch_as_filed_statement,
    format_money,
    get_historicals,
    get_multi_ticker_historicals,
    get_normalized_10k_financials,
    list_10k_filings,
    load_company_tickers,
    load_sp500_constituents,
    map_filing_statements,
    merge_as_filed_statements,
    resolve_ticker,
)

logger = logging.getLogger(__name__)

# Loads FINNHUB_API_KEY / ALPHAVANTAGE_API_KEY from a local .env (gitignored,
# not present by default) into the process environment, where
# build_fundamentals_pivot's per-source checks read them. A missing .env is
# not an error -- load_dotenv() is a no-op then, and those two Fundamentals
# columns are just silently omitted, per spec.md's "API keys" decision.
load_dotenv()

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
cached_get_fundamentals_from_finnhub = st.cache_data(ttl=3600)(get_fundamentals_from_finnhub)
# Alpha Vantage's free tier is 25 requests/day -- cached far longer than
# the other snapshot sources so repeat views of the same ticker don't
# burn the daily quota. See spec.md's "Alpha Vantage rate limit" decision.
cached_get_fundamentals_from_alpha_vantage = st.cache_data(ttl=24 * 3600)(get_fundamentals_from_alpha_vantage)
# S&P 500 constituents (Peer Analysis's sector/industry -> ticker-list
# source) change rarely -- same 24h TTL as the SEC ticker directory. See
# .scratch/peer-analysis/spec.md.
cached_load_sp500_constituents = st.cache_data(ttl=24 * 3600)(load_sp500_constituents)
# A filer's 10-K history changes once a year at most -- same 24h TTL as
# the other directory-style SEC lookups above. See .scratch/10k-reader/spec.md.
cached_list_10k_filings = st.cache_data(ttl=24 * 3600)(list_10k_filings)
# A given filing's own FilingSummary.xml/R.htm never change once filed --
# cache indefinitely (well, 24h -- st.cache_data has no infinite option
# here, but a specific past filing's contents are immutable).
cached_map_filing_statements = st.cache_data(ttl=24 * 3600)(map_filing_statements)
cached_fetch_as_filed_statement = st.cache_data(ttl=24 * 3600)(fetch_as_filed_statement)
cached_get_normalized_10k_financials = st.cache_data(ttl=24 * 3600)(get_normalized_10k_financials)
# get_multi_ticker_historicals and build_peer_fundamentals_pivot are
# deliberately NOT wrapped in st.cache_data themselves -- both take a
# cached function (e.g. cached_get_historicals) as an argument, and
# Streamlit's cache hasher can't hash a CachedFunc object
# (UnhashableParamError). Same reason build_fundamentals_pivot above
# isn't cached at its own level either: the real caching happens at the
# leaf fetchers passed in as fetch_* kwargs, which is where the actual
# I/O -- and the benefit of caching it -- lives.

# Quick date-range presets for the Historicals chart. "Custom" isn't in
# here -- it's handled separately since it needs a date_input, not a
# lookback day-count. See spec.md's Historicals-section decisions.
DATE_RANGE_OPTIONS = ["1W", "1M", "1Y", "5Y", "ALL", "Custom"]
DATE_RANGE_LOOKBACK_DAYS = {"1W": 7, "1M": 30, "1Y": 365, "5Y": 365 * 5}
DEFAULT_DATE_RANGE = "5Y"
# The window used to fetch the ticker's *actual* full history, so the
# right column's date-range slider can bound itself to real data (its
# earliest returned date) rather than a hardcoded number -- spec.md calls
# for "no artificial cap". This constant is just how far back the fetch
# reaches to discover that boundary, not a limit shown to the user.
FULL_HISTORY_FETCH_DAYS = 365 * 75

# Peer Analysis constants -- see .scratch/peer-analysis/spec.md.
PEER_MAX_PEERS = 8
PEER_PRECHECK_COUNT = 5
# GICS Sector label, matching the S&P 500 constituents dataset's own
# spelling -- guarded with a fallback to sectors[0] in
# render_peer_analysis_tab in case that spelling ever drifts.
PEER_DEFAULT_SECTOR = "Information Technology"
# The dataviz skill's validated 8-hue categorical dark palette, fixed
# order (never cycled or reassigned by rank -- a peer keeps its color
# across reruns even if others are added/removed). Re-validated against
# this app's actual Aurora paper (#070B14, darker than the skill's default
# dark surface) -- all six checks pass (adjacent CVD floor 8.4, adjacent
# normal-vision floor 19.3, contrast >=3:1 for all eight).
PEER_LINE_COLORS = [
    "#3987e5",  # 1 blue
    "#d95926",  # 2 orange
    "#199e70",  # 3 aqua
    "#c98500",  # 4 yellow
    "#d55181",  # 5 magenta
    "#008300",  # 6 green
    "#9085e9",  # 7 violet
    "#e66767",  # 8 red
]

SPARKLINE_METRICS = ["Revenue", "NetIncome", "EPS"]
# Display label and y-axis unit per metric -- SPARKLINE_METRICS holds the
# raw DataFrame column names (ticket v2-02: those must never reach the UI
# directly, e.g. "NetIncome" with no space).
SPARKLINE_LABELS = {"Revenue": "Revenue", "NetIncome": "Net Income", "EPS": "EPS"}
SPARKLINE_UNITS = {"Revenue": "USD", "NetIncome": "USD", "EPS": "USD per share"}

# Rows whose cross-source values aren't apples-to-apples -- flagged with a
# tiny (*) on the row label in the Fundamentals table, expanded only as a
# hover/focus tooltip rather than a permanent caption under the table.
FUNDAMENTALS_ROW_NOTES = {
    "Revenue": (
        "SEC EDGAR reports the most recently filed fiscal year; Alpha Vantage reports "
        "trailing twelve months. Disagreement between columns reflects each source's own "
        "update timing and calculation method — that's the point of comparing them side by "
        "side, not a bug in the table."
    ),
    "Net income": (
        "SEC EDGAR reports the most recently filed fiscal year; Alpha Vantage reports "
        "trailing twelve months. Disagreement between columns reflects each source's own "
        "update timing and calculation method — that's the point of comparing them side by "
        "side, not a bug in the table."
    ),
}

T = TypeVar("T")

# --------------------------------------------------------------- design system
#
# Hallmark · genre: atmospheric · macrostructure: unchanged (existing app
# chrome, not a marketing page -- redesign scope is visual/component voice
# only, per hallmark redesign's single-page flow) · theme: Aurora
# · nav: n/a · footer: n/a
#
# Direction: a dark instrument-panel canvas -- the tool reads as something
# built for after-hours reading, not a SaaS dashboard and not the parchment
# editorial-journal look this file used to have.
#
# Color: deliberate deviation from atmospheric's warm-hue default (same
# precedent as the Terminal theme's phosphor green) -- Aurora's identity IS
# a cool-hue phenomenon. Teal/emerald is the single primary accent (gains,
# focus rings, primary actions); violet is confined to the ambient
# background bloom only, never on text or UI; a warm coral is reserved for
# losses, paired with a directional glyph rather than color alone (color.md
# bans red/green as the *only* signal). See AURORA below -- these hex
# values are the sRGB conversion of the oklch() tokens in THEME_CSS's
# :root block; keep the two in sync if either changes, since Plotly can't
# consume CSS custom properties.
#
# Type: Bricolage Grotesque (display) + Geist (body) -- both allowlisted
# for atmospheric, paired instead of collapsed into one family so the
# hero ticker has real weight against the body. Geist Mono is the outlier,
# reserved for one role: financial figures (hero price, chart axes, table
# values) -- not a fourth surface.
#
# Signature: the hero is still one sentence ("AAPL -- $233.42, up 1.8% on
# the day"), but direction now carries both the accent color AND a small
# up/down glyph, and every section label is roman (italic headers are an
# atmospheric-wide ban, not just an editorial one). The ticker search bar
# is pinned (position: sticky) below Streamlit's own header so it's always
# reachable without scrolling back up.
AURORA = {
    "paper": "#070B14",
    "paper_2": "#0F141D",
    "paper_3": "#171D27",
    "ink": "#E7EBF2",
    "ink_muted": "#9DA5B1",
    "accent": "#37D59F",       # gains, focus rings, primary actions
    "accent_ink": "#070B14",   # text on accent fill
    "violet": "#9964E5",       # ambient bloom only -- never UI or text
    "loss": "#F75D59",         # losses, always paired with a glyph
}

THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap');

:root {{
    --color-paper: oklch(15% 0.02 260);
    --color-paper-2: oklch(19% 0.02 260);
    --color-paper-3: oklch(23% 0.022 260);
    --color-ink: oklch(94% 0.01 260);
    --color-ink-muted: oklch(72% 0.02 260);
    --color-accent: oklch(78% 0.15 165);
    --color-accent-ink: oklch(15% 0.02 260);
    --color-violet: oklch(62% 0.19 300);
    --color-loss: oklch(68% 0.19 25);
    --color-focus: oklch(78% 0.15 165);
}}

[data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
    background:
        radial-gradient(ellipse 60% 45% at 12% 8%, color-mix(in oklch, var(--color-accent) 22%, transparent), transparent),
        radial-gradient(ellipse 55% 50% at 92% 85%, color-mix(in oklch, var(--color-violet) 18%, transparent), transparent),
        var(--color-paper);
    background-attachment: fixed;
}}
[data-testid="stHeader"] {{ display: none; }}
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] div,
[data-testid="stAppViewContainer"] li {{
    color: var(--color-ink);
    font-family: 'Geist', -apple-system, sans-serif;
}}
/* The rule above's font-family also caught stIconMaterial spans
   (expander chevrons, etc.), which render via a ligature font --
   "keyboard_arrow_down" showed up as literal text instead of the arrow
   glyph once Geist replaced Streamlit's own icon font. Restore it
   (self-hosted by Streamlit, confirmed via its own @font-face rule --
   not a Google Fonts dependency). */
[data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded' !important;
}}
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3 {{
    font-family: 'Bricolage Grotesque', ui-sans-serif, sans-serif;
    font-style: normal;
    color: var(--color-ink);
}}

/* Atmospheric drops hairlines in favor of elevation -- a divider is now
   just rhythm, not a drawn line. */
hr {{ border: none; margin: 1.6rem 0; }}

.te-eyebrow {{
    font-family: 'Geist', sans-serif;
    font-style: normal;
    font-size: 0.85rem;
    letter-spacing: 0.04em;
    color: var(--color-ink-muted);
}}

/* Frozen search bar: `position: fixed`, not `sticky` -- every Streamlit
   container wraps its content in a flex box that's shrink-wrapped to that
   content's own height, which gives a sticky descendant no "runway" to
   stick within (it un-sticks on the very first pixel of scroll). Fixed
   sidesteps that entirely; stMainBlockContainer's top padding is pushed
   down below to leave room for it instead. Pinned at the literal viewport
   top -- Streamlit's own header is hidden entirely (see stHeader rule
   above), so there's nothing above this bar to leave room for or bleed
   through underneath it. An opaque fill + drop shadow (not a hairline,
   per atmospheric's elevation-over-hairline rule) separates it from the
   content scrolling underneath. */
div[class*="st-key-ticker_search_bar"] {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 200;
    background: var(--color-paper);
    padding: 0.9rem clamp(1rem, 5vw, 5rem) 1.1rem;
    box-shadow: 0 16px 28px -18px rgba(0, 0, 0, 0.7);
}}
[data-testid="stMainBlockContainer"] {{
    padding-top: 5.1rem !important;
}}

.te-hero-ticker {{
    font-family: 'Bricolage Grotesque', sans-serif;
    font-style: normal;
    font-weight: 800;
    font-size: 3rem;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 0.3rem 0 0.2rem;
}}
.te-hero-company {{
    font-family: 'Geist', sans-serif;
    font-weight: 400;
    font-size: 1.35rem;
    letter-spacing: 0;
    color: var(--color-ink-muted);
    margin-left: 0.6rem;
    vertical-align: middle;
}}
.te-hero-line {{
    font-family: 'Geist Mono', monospace;
    font-style: normal;
    font-size: 1.15rem;
    font-variant-numeric: tabular-nums;
    color: var(--color-ink-muted);
}}
.te-hero-line .move-up {{ color: var(--color-accent); font-weight: 500; }}
.te-hero-line .move-down {{ color: var(--color-loss); font-weight: 500; }}
.te-byline {{
    font-family: 'Geist', sans-serif;
    font-size: 0.85rem;
    color: var(--color-ink-muted);
    margin-top: 0.15rem;
}}

/* Section labels: roman, not italic -- the accent tick mark (not italics)
   is what signals "this is a section head". */
.te-group-title {{
    font-family: 'Geist', sans-serif;
    font-style: normal;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-ink-muted);
    margin: 1.6rem 0 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.te-group-title::before {{
    content: "";
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 2px;
    background: var(--color-accent);
    flex: none;
}}
.te-group-title:first-child {{ margin-top: 0.4rem; }}
.te-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.55rem 0.75rem;
    border-radius: 10px;
    background: var(--color-paper-2);
    gap: 1rem;
    margin-bottom: 0.35rem;
}}
.te-row .lbl {{ font-size: 0.85rem; color: var(--color-ink-muted); }}
.te-row .val {{
    font-family: 'Geist Mono', monospace;
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.te-note {{
    font-family: 'Geist', sans-serif;
    font-style: normal;
    font-size: 0.9rem;
    color: var(--color-ink-muted);
}}

/* Text input: a filled pill on the dark canvas, not the old underline. */
[data-testid="stAppViewContainer"] input[type="text"] {{
    background: var(--color-paper-2) !important;
    border: 1px solid transparent !important;
    border-radius: 999px !important;
    font-family: 'Geist', sans-serif;
    font-size: 1rem;
    color: var(--color-ink) !important;
    padding: 0.5rem 1rem !important;
}}
[data-testid="stAppViewContainer"] input[type="text"]:focus-visible {{
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
}}

/* Buttons: neutral pill by default -- confident accent fill is reserved
   for the selected/primary action, not every control (keeps the accent
   under its footprint budget with this many controls on one view). */
[data-testid="stAppViewContainer"] button {{
    background: var(--color-paper-2) !important;
    color: var(--color-ink-muted) !important;
    border: 1px solid transparent !important;
    border-radius: 999px !important;
    font-family: 'Geist', sans-serif !important;
    font-weight: 500;
    font-size: 0.8rem !important;
    letter-spacing: 0.01em;
    box-shadow: none !important;
    transition: background-color 160ms ease-out, color 160ms ease-out;
}}
[data-testid="stAppViewContainer"] button:hover {{
    background: var(--color-paper-3) !important;
    color: var(--color-ink) !important;
}}
[data-testid="stAppViewContainer"] button:focus-visible {{
    outline: 2px solid var(--color-focus) !important;
    outline-offset: 2px;
}}
[data-testid="stAppViewContainer"] button:active {{
    background: var(--color-paper) !important;
}}

/* Selected segmented-control pill gets the confident accent fill. */
[data-testid="stAppViewContainer"] button[aria-checked="true"] {{
    background: var(--color-accent) !important;
    color: var(--color-accent-ink) !important;
}}

/* Multiselect tags (e.g. Peer Analysis's selected peers) are the other
   accent-filled control -- same fill color, so they need the same dark
   ink text as the segmented control above. Without this they inherit
   the global light --color-ink text rule, which reads poorly against
   the bright teal fill. */
[data-testid="stMultiSelectTagsContainer"] span {{
    color: var(--color-accent-ink) !important;
}}

/* Every button's label renders in a nested <p>/<span>, which carries its
   own explicit color from the global text rule above -- set it here too
   or hover/selected buttons go text-color-mismatched-to-fill. */
[data-testid="stAppViewContainer"] button:hover p,
[data-testid="stAppViewContainer"] button:hover span,
[data-testid="stAppViewContainer"] button:hover div,
[data-testid="stAppViewContainer"] button[aria-checked="true"] p,
[data-testid="stAppViewContainer"] button[aria-checked="true"] span,
[data-testid="stAppViewContainer"] button[aria-checked="true"] div {{
    color: inherit !important;
}}

[data-testid="stRadio"] label p {{ font-family: 'Geist', sans-serif; font-size: 0.85rem; }}
[data-testid="stAppViewContainer"] input[type="radio"] {{ accent-color: var(--color-accent); }}
[data-testid="stSlider"] [role="slider"] {{ background-color: var(--color-accent) !important; }}
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {{
    font-family: 'Geist Mono', monospace; color: var(--color-ink-muted);
}}

/* Fundamentals pivot table -- hand-built HTML instead of st.dataframe so
   the Revenue/Net income caveat can live as a per-row hover tooltip
   (a canvas-rendered st.dataframe grid can't host real DOM tooltips). */
.te-pivot-wrap {{
    overflow-x: auto;
    border-radius: 10px;
    background: var(--color-paper-2);
}}
.te-pivot-table {{
    width: 100%;
    border-collapse: collapse;
    font-family: 'Geist', sans-serif;
    font-size: 0.85rem;
}}
.te-pivot-table th, .te-pivot-table td {{
    padding: 0.55rem 0.9rem;
    text-align: right;
    white-space: nowrap;
}}
.te-pivot-table th:first-child, .te-pivot-table td:first-child {{
    text-align: left;
}}
.te-pivot-table thead th {{
    color: var(--color-ink-muted);
    font-weight: 500;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--color-paper-3);
}}
.te-pivot-table td:first-child {{
    font-family: 'Geist', sans-serif;
    color: var(--color-ink-muted);
}}
.te-pivot-table td:not(:first-child) {{
    font-family: 'Geist Mono', monospace;
    font-variant-numeric: tabular-nums;
    color: var(--color-ink);
}}
.te-pivot-table tbody tr:hover {{
    background: var(--color-paper-3);
}}

/* Disclaimer-on-hover: a dotted-underline (*) marker on the row label,
   expanded as a popup only on hover/focus -- never a permanent caption. */
.te-note-marker {{
    position: relative;
    cursor: help;
    border-bottom: 1px dotted var(--color-ink-muted);
}}
.te-note-marker sup {{
    color: var(--color-accent);
    font-size: 0.75em;
    margin-left: 1px;
}}
.te-note-marker:focus-visible {{
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
}}
.te-tooltip-bubble {{
    display: none;
    position: absolute;
    left: 0;
    bottom: calc(100% + 0.5rem);
    width: max-content;
    max-width: 19rem;
    background: var(--color-paper-3);
    color: var(--color-ink);
    font-size: 0.78rem;
    line-height: 1.5;
    font-weight: 400;
    text-align: left;
    white-space: normal;
    padding: 0.65rem 0.85rem;
    border-radius: 8px;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.5);
    z-index: 60;
}}
.te-note-marker:hover .te-tooltip-bubble,
.te-note-marker:focus .te-tooltip-bubble,
.te-note-marker:focus-within .te-tooltip-bubble {{
    display: block;
}}
</style>
"""

CHART_FONT = dict(family="Geist Mono, monospace", color=AURORA["ink_muted"], size=11)
SPARKLINE_TITLE_FONT = dict(family="Geist, sans-serif", size=13, color=AURORA["ink_muted"])


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def fetch_or_none(fn: Callable[..., T], *args, error_message: str, show=st.error, **kwargs) -> T | None:
    """Call fn, logging and surfacing `error_message` (via `show`, e.g.
    st.error or st.caption) instead of crashing the page on failure. Every
    external call in this app goes through here so a transient yfinance/
    EDGAR outage degrades to a visible message, per spec.md's "plain
    error state, no fallback" decision.

    Yahoo Finance rate-limiting (yfinance's own YFRateLimitError) is
    caught before the generic case and given its own message -- shared
    hosting (e.g. Streamlit Community Cloud) shares an IP pool with many
    other yfinance-using apps and hits this often. Without this, a
    rate-limited call looked identical to "no such ticker" to the user,
    which is actively misleading (the ticker is fine; retrying shortly
    usually works).
    """
    try:
        return fn(*args, **kwargs)
    except YFRateLimitError:
        logger.exception("%s rate-limited by Yahoo Finance", getattr(fn, "__name__", repr(fn)))
        show(
            "Yahoo Finance is temporarily rate-limiting requests from this app "
            "(common on shared hosting like Streamlit Community Cloud) -- try again in a minute or two."
        )
        return None
    except Exception:
        logger.exception("%s failed", getattr(fn, "__name__", repr(fn)))
        show(error_message)
        return None


def price_chart(df: pd.DataFrame, chart_type: str) -> go.Figure:
    fig = go.Figure()
    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                increasing_line_color=AURORA["accent"], decreasing_line_color=AURORA["loss"],
            )
        )
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", line=dict(color=AURORA["accent"], width=1.5)))
    fig.update_layout(
        height=440, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False,
        plot_bgcolor=AURORA["paper_2"], paper_bgcolor="rgba(0,0,0,0)", font=CHART_FONT,
        xaxis=dict(showgrid=False, linecolor=AURORA["paper_3"]),
        yaxis=dict(showgrid=True, gridcolor=AURORA["paper_3"]),
    )
    return fig


def _year_tick_step(fiscal_years: pd.Index) -> int:
    """A tick spacing (in whole years) that keeps a fiscal-year x-axis to
    roughly 8 ticks or fewer, so a ticker with 5 years of EDGAR history
    gets yearly ticks and one with 40 gets 5- or 10-year ticks instead of
    either "2020.5" (Plotly's default numeric auto-ticking on a small
    integer range) or a wall of overlapping year labels.
    """
    span = int(fiscal_years.max()) - int(fiscal_years.min())
    for step in (1, 2, 5, 10, 20, 25, 50):
        if span <= step * 8:
            return step
    return 100


def sparkline(hist: pd.DataFrame, column: str, label: str, y_title: str) -> go.Figure:
    series = hist[column].dropna()
    step = _year_tick_step(series.index)
    tick0 = (int(series.index.min()) // step) * step
    fig = go.Figure(go.Scatter(x=series.index, y=series.values, mode="lines", line=dict(color=AURORA["accent"], width=1.5)))
    fig.update_layout(
        height=160, margin=dict(l=50, r=10, t=28, b=35),
        title=dict(text=label, font=SPARKLINE_TITLE_FONT),
        plot_bgcolor=AURORA["paper_2"], paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            visible=True, title=dict(text="Fiscal year", font=CHART_FONT), gridcolor=AURORA["paper_3"],
            tickmode="linear", tick0=tick0, dtick=step, tickformat="d",
        ),
        yaxis=dict(visible=True, title=dict(text=y_title, font=CHART_FONT), gridcolor=AURORA["paper_3"]),
    )
    return fig


def _quick_range(min_date: date, choice: str) -> tuple[date, date]:
    today = date.today()
    if choice == "ALL":
        return min_date, today
    return max(min_date, today - timedelta(days=DATE_RANGE_LOOKBACK_DAYS[choice])), today


def _render_date_range_picker(min_date: date, key_prefix: str) -> tuple[date, date]:
    """Segmented-control quick-range picker plus a 'Custom' date_input
    fallback -- the shared widget orchestration behind both Historicals'
    and Peer Analysis's date-range controls. `key_prefix` scopes each
    section's widget keys so their choices persist independently (not
    scoped to the current ticker/peer-set, the way a real terminal's
    range picker would -- only the underlying dates recompute).
    """
    range_choice = st.segmented_control(
        "Date range", DATE_RANGE_OPTIONS, default=DEFAULT_DATE_RANGE,
        required=True, key=f"{key_prefix}_range_choice",
    )
    if range_choice == "Custom":
        picked = st.date_input(
            "Custom range", value=_quick_range(min_date, DEFAULT_DATE_RANGE),
            min_value=min_date, max_value=date.today(), key=f"{key_prefix}_custom_range",
        )
        if isinstance(picked, tuple) and len(picked) == 2:
            return picked
        # The user has only picked one end so far -- keep the range on
        # its last valid value instead of erroring on the incomplete
        # selection.
        return _quick_range(min_date, DEFAULT_DATE_RANGE)
    return _quick_range(min_date, range_choice)


def render_historicals_section(ticker: str, min_date: date) -> None:
    st.markdown("<div class='te-group-title'>Historicals</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        start_date, end_date = _render_date_range_picker(min_date, "historicals")
    with c2:
        chart_type = st.radio("Chart type", ["Line", "Candlestick"], horizontal=True)

    df = fetch_or_none(
        cached_get_historicals, ticker, start_date, end_date,
        error_message="Price data is temporarily unavailable for this ticker. Try again shortly.",
    )
    if df is None:
        return

    st.plotly_chart(price_chart(df, chart_type), width="stretch", config={"displayModeBar": False})
    # The on-page preview is sorted most-recent-first for readability,
    # unlike df's own chronological (oldest-first) order -- an intentional
    # difference in row order, not content. See spec.md's "Historicals CSV
    # preview" decision. CSV export lives in the dataframe's own toolbar
    # (hover it -- no separate download button needed).
    st.dataframe(df.sort_index(ascending=False), width="stretch")


def _render_pivot_table(pivot: pd.DataFrame) -> None:
    """A hand-built HTML table, not st.dataframe -- st.dataframe renders
    to a canvas-backed grid that can't host a real per-cell hover tooltip,
    which is what the Revenue/Net income cross-source caveat needs (see
    FUNDAMENTALS_ROW_NOTES): a tiny (*) on the row label, expanded only on
    hover/focus, instead of a permanent caption under the table.
    """
    header_cells = "".join(f"<th>{col}</th>" for col in pivot.columns)
    body_rows = []
    for label, row in pivot.iterrows():
        label = str(label)
        note = FUNDAMENTALS_ROW_NOTES.get(label)
        if note:
            label_html = (
                f"<span class='te-note-marker' tabindex='0' aria-label='{label}. {note}'>"
                f"{label}<sup>*</sup>"
                f"<span class='te-tooltip-bubble' aria-hidden='true'>{note}</span>"
                f"</span>"
            )
        else:
            label_html = label
        value_cells = "".join(f"<td>{value}</td>" for value in row)
        body_rows.append(f"<tr><td>{label_html}</td>{value_cells}</tr>")

    st.markdown(
        f"<div class='te-pivot-wrap'><table class='te-pivot-table'>"
        f"<thead><tr><th></th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )


def render_fundamentals_section(ticker: str, cik: str | None, price_history: pd.DataFrame) -> None:
    st.markdown("<div class='te-group-title'>Fundamentals</div>", unsafe_allow_html=True)

    pivot = fetch_or_none(
        build_fundamentals_pivot, ticker, cik, price_history,
        fetch_snapshot=cached_get_fundamentals_snapshot,
        fetch_history=cached_get_fundamentals_history,
        fetch_finnhub=cached_get_fundamentals_from_finnhub,
        fetch_alpha_vantage=cached_get_fundamentals_from_alpha_vantage,
        error_message="Fundamentals are temporarily unavailable for this ticker.",
    )
    if pivot is not None:
        if pivot.empty:
            st.markdown("<div class='te-note'>No Fundamentals sources returned data for this ticker.</div>", unsafe_allow_html=True)
        else:
            _render_pivot_table(pivot)

    st.markdown("<div class='te-group-title'>Trends</div>", unsafe_allow_html=True)
    unavailable_note = "Historical depth isn't available for this ticker."

    # No CIK at all (the query didn't resolve against SEC's own ticker
    # directory) is the same "EDGAR has nothing for this one" case as a
    # CIK that resolves but has no companyfacts (e.g. an ETF, which files
    # no 10-K) -- both skip straight to the note rather than attempting
    # a call SEC's own directory has already told us can't succeed.
    if cik is None:
        st.markdown(f"<div class='te-note'>{unavailable_note}</div>", unsafe_allow_html=True)
        return

    history = fetch_or_none(
        cached_get_fundamentals_history, cik, price_history,
        error_message=unavailable_note, show=lambda msg: st.markdown(f"<div class='te-note'>{msg}</div>", unsafe_allow_html=True),
    )
    if history is None or history.empty:
        if history is not None:
            st.markdown(f"<div class='te-note'>{unavailable_note}</div>", unsafe_allow_html=True)
        return

    for metric in SPARKLINE_METRICS:
        if metric in history.columns and history[metric].notna().any():
            st.plotly_chart(
                sparkline(history, metric, SPARKLINE_LABELS[metric], SPARKLINE_UNITS[metric]),
                width="stretch", config={"displayModeBar": False},
            )


def resolve_and_render_hero(query: str) -> tuple[str, str | None, pd.DataFrame] | None:
    """Resolves `query` (the ticker/company search bar's current value) and
    renders the hero (ticker, company name, price, day change, sector/
    industry byline) -- called from `main` *above* st.tabs so it's visible
    regardless of which tab is active, not just Historicals. Returns
    (ticker, cik, full_history) on success so every tab can seed itself
    from the same resolved ticker, or None on any failure -- each failure
    point here `return`s rather than `st.stop()`s, since a hard stop would
    also blank the tabs sitting below this (their code runs on every
    rerun; only their visibility is tab-scoped).
    """
    if not query.strip():
        return None

    tickers = fetch_or_none(
        cached_load_company_tickers,
        error_message="Couldn't reach the ticker directory (SEC EDGAR). Try again shortly.",
    )
    if tickers is None:
        return None

    matches = resolve_ticker(query, tickers)
    if matches:
        ticker, cik, company_name = matches[0]["ticker"], matches[0]["cik"], matches[0]["name"]
    else:
        # Not in SEC's own ticker directory -- try it as a raw yfinance
        # symbol anyway (a real, if unusual, ticker yfinance recognizes
        # but SEC doesn't) rather than failing immediately. If that also
        # comes up empty, get_historicals raises and the block below
        # reports "no match" either way. cik stays None either way, which
        # render_fundamentals_section treats the same as an
        # EDGAR-no-CIK-match -- a snapshot with no historical depth (see
        # spec.md). No SEC match also means no directory-sourced company
        # name -- the hero just shows the ticker alone in this case.
        ticker, cik, company_name = query.strip().upper(), None, None

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
        return None

    snapshot = fetch_or_none(
        cached_get_fundamentals_snapshot, ticker,
        error_message="Fundamentals snapshot temporarily unavailable.",
    )

    last_close = full_history["Close"].iloc[-1]
    prev_close = full_history["Close"].iloc[-2]
    change_pct = (last_close - prev_close) / prev_close * 100
    move_word = "up" if change_pct >= 0 else "down"
    move_class = "move-up" if change_pct >= 0 else "move-down"
    # Direction is never color-only (color.md bans red/green as the sole
    # signal) -- the glyph carries the same information for anyone who
    # can't distinguish the accent from the loss color.
    move_glyph = "▲" if change_pct >= 0 else "▼"

    company_html = f" <span class='te-hero-company'>{company_name}</span>" if company_name else ""
    st.markdown(f"<div class='te-hero-ticker'>{ticker}{company_html}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='te-hero-line'>${last_close:,.2f} — "
        f"<span class='{move_class}'>{move_glyph} {move_word} {abs(change_pct):.2f}%</span> on the day</div>",
        unsafe_allow_html=True,
    )
    if snapshot and (snapshot.get("sector") or snapshot.get("industry")):
        byline = " — ".join(v for v in (snapshot.get("industry"), snapshot.get("sector")) if v)
        st.markdown(f"<div class='te-byline'>{byline}</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    return ticker, cik, full_history


def render_historicals_tab(ticker: str, cik: str | None, full_history: pd.DataFrame) -> None:
    """The Historicals tab's own content -- the hero above it (ticker,
    company, price) is rendered once by resolve_and_render_hero, above
    st.tabs, so it stays visible on every tab rather than just this one.
    """
    render_historicals_section(ticker, full_history.index.min().date())
    st.markdown("<hr>", unsafe_allow_html=True)
    render_fundamentals_section(ticker, cik, full_history)


def _peer_top_n_by_market_cap(candidates: list[dict], n: int) -> list[str]:
    """Best-effort ranking of `candidates` (S&P 500 constituent dicts) by
    current market cap, used only to pre-check a sensible default peer set
    on first load of a sector/sub-industry group. A candidate whose
    snapshot fails to fetch just sorts last rather than raising -- a
    slightly-off default ordering isn't worth failing the whole picker
    over. See .scratch/peer-analysis/spec.md.
    """
    ranked = []
    for candidate in candidates:
        try:
            snapshot = cached_get_fundamentals_snapshot(candidate["ticker"])
            market_cap = snapshot.get("market_cap") or 0
        except Exception:
            logger.exception("Market-cap lookup failed for peer candidate %s", candidate["ticker"])
            market_cap = 0
        ranked.append((market_cap, candidate["ticker"]))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [ticker for _, ticker in ranked[:n]]


def _normalize_to_pct_return(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Rebase each column to % change from its own first available value
    in `price_frame` -- not a single shared start date across all peers,
    since selected peers can have uneven listing histories. Pure, no I/O.
    """

    def rebase(series: pd.Series) -> pd.Series:
        first_valid = series.first_valid_index()
        if first_valid is None:
            return series
        base = series.loc[first_valid]
        return (series / base - 1) * 100

    return price_frame.apply(rebase)


def peer_price_chart(display_frame: pd.DataFrame, color_by_ticker: dict[str, str], y_title: str) -> go.Figure:
    fig = go.Figure()
    for ticker in display_frame.columns:
        fig.add_trace(
            go.Scatter(
                x=display_frame.index, y=display_frame[ticker], mode="lines", name=ticker,
                line=dict(color=color_by_ticker.get(ticker, AURORA["ink_muted"]), width=2),
                connectgaps=False,
            )
        )
    fig.update_layout(
        height=460, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
        plot_bgcolor=AURORA["paper_2"], paper_bgcolor="rgba(0,0,0,0)", font=CHART_FONT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=False, linecolor=AURORA["paper_3"], rangeslider=dict(visible=True)),
        yaxis=dict(showgrid=True, gridcolor=AURORA["paper_3"], title=dict(text=y_title, font=CHART_FONT)),
    )
    return fig


def render_peer_analysis_tab(historicals_seed: tuple[str, str | None, pd.DataFrame] | None) -> None:
    st.markdown("<div class='te-group-title'>Peer Analysis</div>", unsafe_allow_html=True)

    constituents = fetch_or_none(
        cached_load_sp500_constituents,
        error_message="Couldn't reach the S&P 500 constituents list. Try again shortly.",
    )
    if constituents is None:
        return

    sectors = sorted({c["sector"] for c in constituents})

    # Re-seed from the Historicals tab's searched ticker whenever that
    # ticker actually changes (not just once per session) -- comparing
    # against the last-seeded ticker, not a one-shot flag, so searching a
    # new stock re-syncs Sector/Sub-Industry/peers each time, while the
    # user's own picks are left alone on reruns where the ticker hasn't
    # changed (widget interactions, tab switches, etc).
    current_ticker = historicals_seed[0] if historicals_seed is not None else None
    should_reseed = current_ticker != st.session_state.get("peer_last_seeded_ticker")
    seed_match = None
    if should_reseed:
        st.session_state["peer_last_seeded_ticker"] = current_ticker
        if current_ticker is not None:
            seed_match = next((c for c in constituents if c["ticker"] == current_ticker), None)

    default_sector = seed_match["sector"] if seed_match else PEER_DEFAULT_SECTOR
    if default_sector not in sectors:
        default_sector = sectors[0]
    if should_reseed:
        st.session_state["peer_sector"] = default_sector
    else:
        st.session_state.setdefault("peer_sector", default_sector)

    c1, c2 = st.columns(2)
    with c1:
        sector = st.selectbox("Sector", sectors, key="peer_sector")

    sector_constituents = [c for c in constituents if c["sector"] == sector]
    sub_industries = ["All"] + sorted({c["sub_industry"] for c in sector_constituents})

    default_sub_industry = seed_match["sub_industry"] if (seed_match and seed_match["sector"] == sector) else "All"
    if should_reseed:
        st.session_state["peer_sub_industry"] = default_sub_industry
    else:
        st.session_state.setdefault("peer_sub_industry", default_sub_industry)
    if st.session_state["peer_sub_industry"] not in sub_industries:
        # A sub-industry left over from a previously-selected sector that
        # doesn't exist in this one -- fall back rather than let the
        # widget raise on a stale value not in its options.
        st.session_state["peer_sub_industry"] = "All"

    with c2:
        sub_industry = st.selectbox("Sub-Industry", sub_industries, key="peer_sub_industry")

    group = (
        sector_constituents if sub_industry == "All"
        else [c for c in sector_constituents if c["sub_industry"] == sub_industry]
    )
    if not group:
        st.markdown("<div class='te-note'>No S&P 500 companies found for this selection.</div>", unsafe_allow_html=True)
        return

    plural = "y" if len(group) == 1 else "ies"
    with st.expander(f"{len(group)} compan{plural} in this group"):
        st.dataframe(
            pd.DataFrame([{"Ticker": c["ticker"], "Company": c["name"]} for c in group]),
            width="stretch", hide_index=True,
        )

    # Changing sector/sub-industry resets the peer multiselect to this
    # group's top 5 by market cap -- computed once per group change, not
    # every rerun. See spec.md's Ticket 03.
    group_key = (sector, sub_industry)
    if st.session_state.get("peer_group_key") != group_key:
        st.session_state["peer_group_key"] = group_key
        seed_in_group = (
            seed_match["ticker"]
            if seed_match and seed_match["sector"] == sector
            and (sub_industry == "All" or seed_match["sub_industry"] == sub_industry)
            else None
        )
        default_peers = [seed_in_group] if seed_in_group else []
        remaining = PEER_PRECHECK_COUNT - len(default_peers)
        if remaining > 0:
            candidates = [c for c in group if c["ticker"] not in default_peers]
            with st.spinner("Ranking companies by market cap…"):
                default_peers += _peer_top_n_by_market_cap(candidates, remaining)
        st.session_state["peer_selected_tickers"] = default_peers

    ticker_labels = {c["ticker"]: f"{c['ticker']} — {c['name']}" for c in group}
    cik_by_ticker = {c["ticker"]: c["cik"] for c in group}

    selected = st.multiselect(
        "Peers", list(ticker_labels), key="peer_selected_tickers",
        format_func=lambda t: ticker_labels.get(t, t), max_selections=PEER_MAX_PEERS,
    )
    if not selected:
        st.markdown("<div class='te-note'>Pick at least one company to compare.</div>", unsafe_allow_html=True)
        return

    # Color assignment is keyed off the *selected* set's own alphabetical
    # order, not the whole group's -- a group can exceed 8 members (the
    # palette's size), and keying off group position would wrap two
    # selected peers onto the same color via modulo. Keying off `selected`
    # (capped at PEER_MAX_PEERS == len(PEER_LINE_COLORS)) guarantees every
    # selected peer gets a distinct slot; the tradeoff is a peer's color
    # can shift if an alphabetically-earlier peer is added or removed from
    # the selection, which is preferable to two peers sharing a color.
    color_by_ticker = {ticker: PEER_LINE_COLORS[i % len(PEER_LINE_COLORS)] for i, ticker in enumerate(sorted(selected))}

    # A wide window per peer, purely to discover how far back the date
    # range can usefully go -- the earliest date across ALL selected peers
    # (i.e. as far back as the longest-listed peer goes), not truncated to
    # the newest peer's start date. See spec.md's Ticket 03.
    wide_histories = get_multi_ticker_historicals(
        selected, date.today() - timedelta(days=FULL_HISTORY_FETCH_DAYS), date.today(),
        fetch_historicals=cached_get_historicals,
    )
    missing = sorted(set(selected) - set(wide_histories))
    if missing:
        st.markdown(f"<div class='te-note'>Couldn't load data for: {', '.join(missing)}.</div>", unsafe_allow_html=True)
    if not wide_histories:
        return
    min_date = min(history.index.min().date() for history in wide_histories.values())

    r1, r2 = st.columns([3, 1])
    with r1:
        start_date, end_date = _render_date_range_picker(min_date, "peer")
    with r2:
        view_choice = st.radio("View", ["Normalized % return", "Raw price"], key="peer_view_choice")

    histories = {ticker: history.loc[str(start_date):str(end_date)] for ticker, history in wide_histories.items()}
    price_frame = build_peer_price_frame(histories)

    display_frame = _normalize_to_pct_return(price_frame) if view_choice == "Normalized % return" else price_frame
    y_title = "% return" if view_choice == "Normalized % return" else "Price (USD)"
    st.plotly_chart(peer_price_chart(display_frame, color_by_ticker, y_title), width="stretch", config={"displayModeBar": False})

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download chart data (CSV)", display_frame.to_csv().encode("utf-8"),
            file_name="peer_analysis_chart.csv", mime="text/csv",
        )
    with dl2:
        long_format = pd.concat([history.assign(Ticker=ticker) for ticker, history in histories.items()]).reset_index()
        long_format = long_format[["Ticker", "Date"] + [c for c in long_format.columns if c not in ("Ticker", "Date")]]
        st.download_button(
            "Download raw OHLCV (CSV)", long_format.to_csv(index=False).encode("utf-8"),
            file_name="peer_analysis_ohlcv.csv", mime="text/csv",
        )

    st.markdown("<div class='te-group-title'>Performance</div>", unsafe_allow_html=True)
    stats = compute_peer_performance_stats(price_frame)
    st.dataframe(stats.style.format("{:.2f}", na_rep="—"), width="stretch")

    st.markdown("<div class='te-group-title'>Fundamentals</div>", unsafe_allow_html=True)
    pivot = fetch_or_none(
        build_peer_fundamentals_pivot, selected, cik_by_ticker, histories,
        fetch_snapshot=cached_get_fundamentals_snapshot, fetch_history=cached_get_fundamentals_history,
        fetch_finnhub=cached_get_fundamentals_from_finnhub, fetch_alpha_vantage=cached_get_fundamentals_from_alpha_vantage,
        error_message="Peer fundamentals are temporarily unavailable.",
    )
    if pivot is not None:
        # Explicit height sized to the row count -- st.dataframe's default
        # height caps well short of this table's typical row count (one
        # row per Fundamentals metric), forcing an internal scrollbar.
        st.dataframe(pivot, width="stretch", height=(len(pivot) + 1) * 35 + 3)


# The three core 10-K statements, in display order -- shared by both the
# Exact statement-type picker and the Normalized tab's table order, so
# the two can't drift apart.
STATEMENT_TYPES = ["Income Statement", "Balance Sheet", "Cash Flow Statement"]
# Downloaded-CSV filename suffix per statement type -- {TICKER}-{YY}-{YY}-{suffix}.csv,
# e.g. "ADBE-21-25-IS.csv".
STATEMENT_TYPE_CSV_SUFFIX = {"Income Statement": "IS", "Balance Sheet": "BS", "Cash Flow Statement": "CFS"}


def _statement_csv_filename(ticker: str, start_year: str, end_year: str, statement_type: str) -> str:
    suffix = STATEMENT_TYPE_CSV_SUFFIX[statement_type]
    return f"{ticker}-{start_year[-2:]}-{end_year[-2:]}-{suffix}.csv"


def _render_one_as_filed_table(ticker: str, cik: str, filing: dict, statement_type: str) -> None:
    """Renders one filing's as-filed table for `statement_type`, plus its
    own named CSV download -- the default single-filing view goes through
    this path.
    """
    statements = fetch_or_none(
        cached_map_filing_statements, cik, filing["accession_number"],
        error_message="Couldn't reach SEC EDGAR for this filing's statements.",
    )
    if statements is None:
        return

    r_file = statements.get(statement_type)
    if r_file is None:
        st.markdown(
            "<div class='te-note'>Exact-as-filed view isn't available for this filing "
            "(it may predate SEC's XBRL tagging requirement).</div>",
            unsafe_allow_html=True,
        )
        return

    table = fetch_or_none(
        cached_fetch_as_filed_statement, cik, filing["accession_number"], r_file,
        error_message="Couldn't load this statement's as-filed table.",
    )
    if table is None:
        return

    st.markdown(
        f"<div class='te-note'>As filed in the 10-K for fiscal year ended {filing['report_date']} "
        f"(filed {filing['filing_date']}).</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(table, width="stretch", hide_index=True)

    fy = filing["report_date"][:4]
    st.download_button(
        "Download CSV", table.to_csv(index=False).encode("utf-8"),
        file_name=_statement_csv_filename(ticker, fy, fy, statement_type), mime="text/csv",
        key=f"10k_exact_dl_{statement_type}_{filing['accession_number']}",
    )


def _render_merged_as_filed_table(ticker: str, cik: str, filings: list[dict], statement_type: str) -> None:
    """The "show all years" view: each filing's own as-filed figures for
    `statement_type`, merged into one table (see merge_as_filed_statements)
    -- one column per fiscal year, one row per unique line item, blank
    where a given filing didn't report it. Replaces the old approach of
    stacking each filing's own 2-year comparative table separately, which
    produced overlapping, confusing year spans down the page (filing N
    showing years [Y, Y-1], filing N+1 showing [Y-1, Y-2], and so on).
    """
    tables: list[pd.DataFrame] = []
    year_labels: list[str] = []
    for filing in filings:
        statements = fetch_or_none(
            cached_map_filing_statements, cik, filing["accession_number"],
            error_message="Couldn't reach SEC EDGAR for this filing's statements.",
        )
        if statements is None:
            continue
        r_file = statements.get(statement_type)
        if r_file is None:
            continue
        table = fetch_or_none(
            cached_fetch_as_filed_statement, cik, filing["accession_number"], r_file,
            error_message="Couldn't load this statement's as-filed table.",
        )
        if table is None:
            continue
        tables.append(table)
        year_labels.append(filing["report_date"][:4])

    if not tables:
        st.markdown(
            "<div class='te-note'>Exact-as-filed view isn't available for these filings "
            "(they may predate SEC's XBRL tagging requirement).</div>",
            unsafe_allow_html=True,
        )
        return

    merged = merge_as_filed_statements(tables, year_labels)
    st.markdown(
        f"<div class='te-note'>Each of the last {len(tables)} 10-Ks' own as-filed figures, "
        "one column per fiscal year -- blank where a filing didn't report that line item.</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(merged, width="stretch")

    st.download_button(
        "Download CSV", merged.to_csv().encode("utf-8"),
        file_name=_statement_csv_filename(ticker, year_labels[-1], year_labels[0], statement_type),
        mime="text/csv", key=f"10k_exact_merged_dl_{statement_type}",
    )


def render_10k_exact_tab(ticker: str, cik: str, filings: list[dict]) -> None:
    statement_type = st.radio("Statement", STATEMENT_TYPES, key="10k_statement_type", horizontal=True)
    show_details = st.checkbox(
        f"Show all {len(filings)} available years" if len(filings) > 1 else "Show all available years",
        key="10k_show_details",
        help="Merges each filing's own as-filed figures into one table, one column per fiscal "
        "year -- blank where a filing didn't report that line item.",
    )

    # Same stale-download-button race as render_10k_normalized_tab (see
    # its comment) -- these tables' CSV buttons sit behind their own slow
    # SEC EDGAR fetches, so they need their own leaf-level st.empty()
    # loading barrier too, keyed separately since a user can be on a
    # different statement_type/show_details combination than Normalized.
    slot = st.empty()
    cache_key = f"_10k_exact_last_rendered_{statement_type}_{show_details}"
    if ticker != st.session_state.get(cache_key):
        with slot.container():
            st.markdown(f"<div class='te-note'>Loading {ticker}'s filings…</div>", unsafe_allow_html=True)

    with slot.container():
        if not show_details:
            _render_one_as_filed_table(ticker, cik, filings[0], statement_type)
        else:
            _render_merged_as_filed_table(ticker, cik, filings, statement_type)

    st.session_state[cache_key] = ticker


NORMALIZED_YEAR_RANGE_OPTIONS = ["5Y", "10Y", "ALL"]
NORMALIZED_YEARS_BY_OPTION: dict[str, int | None] = {"5Y": 5, "10Y": 10, "ALL": None}
# Per-share line items need 2-decimal formatting; everything else in
# these tables is a whole-dollar figure -- applied as a Styler subset
# override, not a per-metric formatter map, since it's the one exception.
NORMALIZED_PER_SHARE_ROWS = ["EPS Basic", "EPS Diluted"]


def render_10k_normalized_tab(ticker: str, cik: str) -> None:
    year_range = st.segmented_control(
        "Years", NORMALIZED_YEAR_RANGE_OPTIONS, default="5Y", required=True, key="10k_normalized_year_range",
    )
    years = NORMALIZED_YEARS_BY_OPTION[year_range]

    # These tables and their "Download CSV" buttons sit behind a slow SEC
    # EDGAR fetch (cached_get_normalized_10k_financials). Streamlit only
    # replaces a widget's DOM node -- a download button's embedded bytes
    # included -- once script execution reaches its position in a new
    # rerun; until then, the *previous* ticker's button here stays fully
    # live and clickable. A dedicated st.empty() at a *leaf* position
    # (not wrapping st.tabs itself, which has its own persistence
    # semantics for keeping the inactive tab's content around) reliably
    # tears down that stale content the instant the ticker changes,
    # before the slow fetch even starts -- confirmed via
    # tests/e2e/test_download_ticker_consistency.py.
    slot = st.empty()
    if ticker != st.session_state.get("_10k_normalized_last_rendered_ticker"):
        with slot.container():
            st.markdown(f"<div class='te-note'>Loading {ticker}'s financials…</div>", unsafe_allow_html=True)

    with slot.container():
        financials = fetch_or_none(
            cached_get_normalized_10k_financials, cik, years,
            error_message="Couldn't reach SEC EDGAR for this company's financial history.",
        )
        if financials is None:
            return

        for statement_name in STATEMENT_TYPES:
            st.markdown(f"<div class='te-group-title'>{statement_name}</div>", unsafe_allow_html=True)
            table = financials[statement_name]
            if table.empty:
                st.markdown("<div class='te-note'>No data available.</div>", unsafe_allow_html=True)
                continue

            # format_money abbreviates to $B/$T for on-screen readability;
            # the Styler only changes display -- table itself (and the
            # dataframe toolbar's own CSV export) still carries the exact
            # underlying digits, per spec.md's "human readable on screen,
            # exact in CSV" decision.
            styled = table.style.format(format_money, na_rep="—")  # type: ignore[arg-type]
            per_share_rows = [row for row in NORMALIZED_PER_SHARE_ROWS if row in table.index]
            if per_share_rows:
                # A plain list here is ambiguous to Styler.format and gets
                # read as column labels, not row labels -- pd.IndexSlice[rows, :]
                # is the unambiguous "these rows, every column" form.
                styled = styled.format(
                    lambda v: f"${v:,.2f}", subset=pd.IndexSlice[per_share_rows, :], na_rep="—"  # type: ignore[arg-type]
                )
            st.dataframe(styled, width="stretch")

            fiscal_years = [str(y) for y in table.columns]
            st.download_button(
                "Download CSV", table.to_csv().encode("utf-8"),
                file_name=_statement_csv_filename(ticker, fiscal_years[-1], fiscal_years[0], statement_name),
                mime="text/csv", key=f"10k_normalized_dl_{statement_name}",
            )

    st.session_state["_10k_normalized_last_rendered_ticker"] = ticker


def render_10k_reader_tab(historicals_seed: tuple[str, str | None, pd.DataFrame] | None) -> None:
    st.markdown("<div class='te-group-title'>Financial Statements</div>", unsafe_allow_html=True)

    if historicals_seed is None:
        st.markdown("<div class='te-note'>Search a ticker in Historicals to see its 10-K filings.</div>", unsafe_allow_html=True)
        return

    ticker, cik, _ = historicals_seed
    if cik is None:
        st.markdown(f"<div class='te-note'>No 10-K found for {ticker}.</div>", unsafe_allow_html=True)
        return

    filings = fetch_or_none(
        cached_list_10k_filings, cik,
        error_message="Couldn't reach SEC EDGAR's filing history. Try again shortly.",
    )
    if filings is None:
        return
    if not filings:
        st.markdown(f"<div class='te-note'>No 10-K found for {ticker}.</div>", unsafe_allow_html=True)
        return

    tab_normalized, tab_exact = st.tabs(["Normalized", "Exact"])
    with tab_normalized:
        render_10k_normalized_tab(ticker, cik)
    with tab_exact:
        render_10k_exact_tab(ticker, cik, filings)

    st.session_state["_10k_last_rendered_ticker"] = ticker


def main() -> None:
    inject_theme()

    # Wrapped in a keyed container so THEME_CSS can pin it (position:
    # sticky) below Streamlit's own header -- always reachable to switch
    # tickers without scrolling back to the top. Sits above both tabs
    # (global chrome, not scoped to Historicals) since Peer Analysis reads
    # the same resolved ticker to seed itself.
    with st.container(key="ticker_search_bar"):
        st.markdown("<div class='te-eyebrow'>Ticker Explorer — a daily reading on one company</div>", unsafe_allow_html=True)
        query = st.text_input(
            "Ticker or company name", value="AAPL",
            label_visibility="collapsed", placeholder="Ticker or company name — e.g. AAPL, or Apple",
        )

    # Rendered above the tabs (not inside Historicals) so the ticker/
    # company/price hero stays visible no matter which tab is active.
    historicals_seed = resolve_and_render_hero(query)

    tab_historicals, tab_peer_analysis, tab_10k_reader = st.tabs(["Historicals", "Peer Analysis", "Financial Statements"])
    with tab_historicals:
        if historicals_seed is not None:
            render_historicals_tab(*historicals_seed)
    with tab_peer_analysis:
        render_peer_analysis_tab(historicals_seed)
    with tab_10k_reader:
        render_10k_reader_tab(historicals_seed)


if __name__ == "__main__":
    main()

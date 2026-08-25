"""
Data-service layer for the Ticker Explorer app.

Isolated from Streamlit on purpose (see spec.md's Testing Decisions):
every function here is a pure fetch/shape operation over a real external
API, callable and testable without a Streamlit runtime. The Streamlit page
is the only caller, and wraps these with st.cache_data itself.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import requests
import yfinance as yf
from rapidfuzz import fuzz

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# SEC EDGAR requires a descriptive User-Agent identifying the requester;
# a blank or generic one gets a 403. See spec.md's Implementation Decisions.
_SEC_USER_AGENT = "ticker-explorer contact@example.com"

_EXACT_MATCH_SCORE = 1000.0
_MIN_FUZZY_SCORE = 75.0

# Stripped before fuzzy-matching company names so a generic corporate
# suffix ("Corp", "Inc") shared between an unrelated query and a real
# company doesn't inflate the match score.
_CORPORATE_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|plc|group|holdings?|n\.?a\.?)\b\.?"
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]")
_EXTRA_SPACE_RE = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    s = name.lower()
    s = _CORPORATE_SUFFIX_RE.sub("", s)
    s = _NON_ALNUM_RE.sub(" ", s)
    return _EXTRA_SPACE_RE.sub(" ", s).strip()


def load_company_tickers() -> list[dict]:
    """Fetch SEC EDGAR's company_tickers.json: the free, keyless master
    list mapping every SEC-registered ticker to its CIK and company name.
    Callers should fetch this once (e.g. behind st.cache_data) and pass
    the result into resolve_ticker per query, rather than re-fetching.
    """
    response = requests.get(
        COMPANY_TICKERS_URL,
        headers={"User-Agent": _SEC_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    raw = response.json()
    return [
        {
            "ticker": entry["ticker"],
            "name": entry["title"],
            "cik": str(entry["cik_str"]).zfill(10),
        }
        for entry in raw.values()
    ]


EDGAR_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Tag-fallback chains, highest priority first, decided in
# .scratch/ticker-explorer/issues/02-edgar-tag-fallback-mapping.md against
# live companyfacts data for AAPL, MSFT, KSS, ZION, and T.
_REVENUE_CHAIN = [
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "Revenues"),
    ("us-gaap", "SalesRevenueNet"),
    ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
]
# Depository institutions (banks): the chain above captures only
# noninterest fee income for them (a 5-6x undercount, confirmed on Zions
# Bancorp) -- if this tag has any annual data at all, the filer is a bank
# and this tag replaces the whole standard chain, not just fills gaps in it.
_BANK_REVENUE_TAG = ("us-gaap", "RevenuesNetOfInterestExpense")
_NET_INCOME_CHAIN = [
    ("us-gaap", "NetIncomeLoss"),
    ("us-gaap", "ProfitLoss"),
]
_EPS_CHAIN = [
    ("us-gaap", "EarningsPerShareDiluted"),
    ("us-gaap", "EarningsPerShareBasic"),
]
_DIVIDENDS_CHAIN = [
    ("us-gaap", "CommonStockDividendsPerShareDeclared"),
    ("us-gaap", "CommonStockDividendsPerShareCashPaid"),
]
_SHARES_CHAIN = [
    ("us-gaap", "CommonStockSharesOutstanding"),
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesIssued"),
]


def _fetch_companyfacts(cik: str) -> dict:
    response = requests.get(
        EDGAR_COMPANYFACTS_URL.format(cik=cik),
        headers={"User-Agent": _SEC_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _tag_units(facts: dict, taxonomy: str, tag: str) -> list[dict]:
    node = facts.get("facts", {}).get(taxonomy, {}).get(tag)
    if node is None:
        return []
    for unit_entries in node.get("units", {}).values():
        return unit_entries  # a tag has exactly one relevant unit in practice
    return []


def _annual_facts(facts: dict, taxonomy: str, tag: str) -> dict[int, tuple[str, float]]:
    """Annual (10-K, full fiscal year) entries for one XBRL tag, keyed by
    fiscal year. Quarterly and partial-period entries are excluded here --
    a chain that didn't would badly under-fill a filer whose "new" tag is
    only ever used for quarterly disaggregation disclosures (AT&T's case).
    """
    result: dict[int, tuple[str, float]] = {}
    for entry in _tag_units(facts, taxonomy, tag):
        if entry.get("form") == "10-K" and entry.get("fp") == "FY" and "fy" in entry:
            result[entry["fy"]] = (entry["end"], entry["val"])
    return result


def _quarterly_facts_by_fy(facts: dict, taxonomy: str, tag: str) -> dict[int, list[float]]:
    result: dict[int, list[float]] = {}
    for entry in _tag_units(facts, taxonomy, tag):
        if entry.get("form") == "10-Q" and "fy" in entry:
            result.setdefault(entry["fy"], []).append(entry["val"])
    return result


def _fallback_per_period(
    series_list: list[dict[int, tuple[str, float]]],
) -> dict[int, tuple[str, float]]:
    """series_list ordered highest-priority first. For each fiscal year
    appearing in any series, use the first series that has it -- evaluated
    per period, not by picking one tag globally for the whole company.
    """
    all_fys: set[int] = set()
    for series in series_list:
        all_fys.update(series.keys())
    result: dict[int, tuple[str, float]] = {}
    for fy in all_fys:
        for series in series_list:
            if fy in series:
                result[fy] = series[fy]
                break
    return result


def _positive_only(series: dict[int, tuple[str, float]]) -> dict[int, tuple[str, float]]:
    # Shares outstanding can't legitimately be zero/negative -- unlike
    # revenue or net income, a non-positive value here is a filing error
    # (a real case: a spurious 0-share cover-page entry), not a valid fact.
    return {fy: (end, val) for fy, (end, val) in series.items() if val is not None and val > 0}


def _resolve_chain(facts: dict, chain: list[tuple[str, str]]) -> dict[int, tuple[str, float]]:
    return _fallback_per_period([_annual_facts(facts, taxonomy, tag) for taxonomy, tag in chain])


def _price_near(price_history: pd.DataFrame, target: pd.Timestamp, max_lookback_days: int = 10) -> float | None:
    if price_history.empty:
        return None
    window = price_history.loc[:target]
    if window.empty:
        return None
    last_date = window.index[-1]
    if (target - last_date).days > max_lookback_days:
        return None
    return float(window["AdjClose"].iloc[-1])


def get_fundamentals_history(cik: str, price_history: pd.DataFrame) -> pd.DataFrame:
    """Multi-year revenue, net income, EPS, dividends/share, and shares
    outstanding for `cik`, via SEC EDGAR's XBRL companyfacts API -- plus
    market cap and trailing P/E, derived by combining shares/EPS with
    `price_history` (see get_historicals). Quarterly/annual only, never
    daily: this is filing-derived data, not a price series. `cik` must
    already be zero-padded to 10 digits (as returned by
    load_company_tickers).
    """
    facts = _fetch_companyfacts(cik)

    # The bank tag is the highest-priority entry in a single per-period
    # chain, not a whole-company either/or switch -- a filer with
    # RevenuesNetOfInterestExpense for most years but a gap the standard
    # chain happens to cover should still get that year filled in, per
    # spec.md's "evaluated per fiscal period" rule.
    bank_taxonomy, bank_tag = _BANK_REVENUE_TAG
    revenue = _fallback_per_period(
        [_annual_facts(facts, bank_taxonomy, bank_tag)]
        + [_annual_facts(facts, taxonomy, tag) for taxonomy, tag in _REVENUE_CHAIN]
    )

    net_income = _resolve_chain(facts, _NET_INCOME_CHAIN)
    eps = _resolve_chain(facts, _EPS_CHAIN)
    dividends = _resolve_chain(facts, _DIVIDENDS_CHAIN)

    # Last resort: a fiscal year the company clearly reported (present in
    # net income or revenue) but with no annual figure under either
    # dividend tag -- reconstruct from quarterly facts. Best-effort only
    # (assumes the quarterly values sum rather than being cumulative
    # year-to-date figures); see spec.md's Testing Decisions.
    known_fys = set(net_income) | set(revenue)
    missing_dividend_fys = known_fys - set(dividends)
    if missing_dividend_fys:
        for taxonomy, tag in _DIVIDENDS_CHAIN:
            quarterly = _quarterly_facts_by_fy(facts, taxonomy, tag)
            for fy in list(missing_dividend_fys):
                if quarterly.get(fy):
                    dividends[fy] = (f"{fy}-12-31", sum(quarterly[fy]))
                    missing_dividend_fys.discard(fy)

    shares = _fallback_per_period(
        [_positive_only(_annual_facts(facts, taxonomy, tag)) for taxonomy, tag in _SHARES_CHAIN]
    )

    all_fys = sorted(set(revenue) | set(net_income) | set(eps) | set(dividends) | set(shares))

    rows = []
    for fy in all_fys:
        eps_end, eps_val = eps.get(fy, (None, None))
        shares_end, shares_val = shares.get(fy, (None, None))

        market_cap = None
        if shares_val is not None and shares_end is not None:
            price = _price_near(price_history, pd.Timestamp(shares_end))
            if price is not None:
                market_cap = shares_val * price

        trailing_pe = None
        if eps_val:
            price = _price_near(price_history, pd.Timestamp(eps_end)) if eps_end else None
            if price is not None:
                trailing_pe = price / eps_val

        rows.append(
            {
                "FiscalYear": fy,
                "Revenue": revenue.get(fy, (None, None))[1],
                "NetIncome": net_income.get(fy, (None, None))[1],
                "EPS": eps_val,
                "DividendsPerShare": dividends.get(fy, (None, None))[1],
                "SharesOutstanding": shares_val,
                "MarketCap": market_cap,
                "TrailingPE": trailing_pe,
            }
        )

    if not rows:
        columns = ["Revenue", "NetIncome", "EPS", "DividendsPerShare", "SharesOutstanding", "MarketCap", "TrailingPE"]
        return pd.DataFrame(columns=columns, index=pd.Index([], name="FiscalYear"))

    return pd.DataFrame(rows).set_index("FiscalYear")


_HISTORICALS_COLUMNS = ["Open", "High", "Low", "Close", "AdjClose", "Volume", "Dividends", "StockSplits"]


def get_historicals(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Daily OHLCV, adjusted close, and dividend/split events for `ticker`
    over [start, end], via yfinance.
    """
    raw = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if raw.empty:
        raise ValueError(f"No historicals data returned for {ticker!r}")

    df = raw.rename(columns={"Adj Close": "AdjClose", "Stock Splits": "StockSplits"})
    if df.index.tz is not None:
        # yfinance returns a tz-aware index (localized to the exchange's
        # timezone); EDGAR's dates are plain dates with no timezone at
        # all. Left tz-aware, comparing the two (e.g. in _price_near)
        # raises TypeError. Daily bars don't need intraday precision, so
        # normalize to tz-naive here rather than downstream everywhere.
        df.index = df.index.tz_localize(None)
    df.index.name = "Date"
    return df[_HISTORICALS_COLUMNS]


_SNAPSHOT_FIELDS = {
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "eps_ttm": "trailingEps",
    "dividend_yield": "dividendYield",
    "sector": "sector",
    "industry": "industry",
    "fifty_two_week_high": "fiftyTwoWeekHigh",
    "fifty_two_week_low": "fiftyTwoWeekLow",
}


def get_fundamentals_snapshot(ticker: str) -> dict:
    """Current Fundamentals snapshot for `ticker`, via yfinance's
    Ticker.info. Missing fields (yfinance omits keys inconsistently
    depending on the ticker) come back as None rather than raising.
    """
    info = yf.Ticker(ticker).info
    return {our_key: info.get(yf_key) for our_key, yf_key in _SNAPSHOT_FIELDS.items()}


def resolve_ticker(query: str, tickers: list[dict], limit: int = 8) -> list[dict]:
    """Resolve a symbol or company-name query against an already-loaded
    ticker list (see load_company_tickers). An exact ticker-symbol match
    (case-insensitive) always ranks first; otherwise entries are ranked by
    fuzzy match against both ticker and name, best first.
    """
    query_norm = query.strip().lower()
    if not query_norm:
        return []
    query_name_norm = _normalize_name(query)

    scored: list[tuple[float, dict]] = []
    for entry in tickers:
        ticker_norm = entry["ticker"].lower()
        if ticker_norm == query_norm:
            score = _EXACT_MATCH_SCORE
        else:
            name_norm = _normalize_name(entry["name"])
            # Plain ratio (whole-string edit distance), not WRatio, for the
            # ticker side: WRatio's partial-ratio component gives a real
            # short ticker a near-perfect score whenever it happens to
            # appear as a substring of a much longer, unrelated query (a
            # garbage "NOTATICKERXYZ123" query scored 90 against the real
            # ticker "XYZ"). Company names still want WRatio -- that's
            # exactly the partial-credit behavior "Appl" -> "Apple Inc."
            # needs -- but gated by a length-ratio check for the same
            # reason: a short normalized name (a short company name, or
            # one hollowed out by suffix-stripping, e.g. "KE Holdings
            # Inc." -> "ke") can trivially appear as a substring of a long
            # garbage query and still score ~90 via partial-ratio.
            name_score = fuzz.WRatio(query_name_norm, name_norm)
            shorter, longer = sorted((len(query_name_norm), len(name_norm)))
            if longer == 0 or shorter / longer < 0.5:
                name_score = 0.0
            score = max(fuzz.ratio(query_norm, ticker_norm), name_score)
        if score >= _MIN_FUZZY_SCORE:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]

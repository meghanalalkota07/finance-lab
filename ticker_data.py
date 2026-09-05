"""
Data-service layer for the Ticker Explorer app.

Isolated from Streamlit on purpose (see spec.md's Testing Decisions):
every function here is a pure fetch/shape operation over a real external
API, callable and testable without a Streamlit runtime. The Streamlit page
is the only caller, and wraps these with st.cache_data itself.
"""

from __future__ import annotations

import io
import logging
import os
import re
from collections import Counter
from datetime import date
from xml.etree import ElementTree

import lxml.html
import pandas as pd
import requests
import yfinance as yf
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

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


SP500_CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)


def load_sp500_constituents() -> list[dict]:
    """Fetch the free, keyless S&P 500 constituents CSV (GICS Sector/Sub-
    Industry per ticker, plus a CIK column that plugs directly into
    get_fundamentals_history) -- the sector/industry -> ticker-list source
    for Peer Analysis. Callers should fetch this once (e.g. behind
    st.cache_data) rather than re-fetching per interaction, same as
    load_company_tickers.
    """
    response = requests.get(SP500_CONSTITUENTS_URL, timeout=10)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text))
    return [
        {
            "ticker": row["Symbol"],
            "name": row["Security"],
            "sector": row["GICS Sector"],
            "sub_industry": row["GICS Sub-Industry"],
            "cik": str(row["CIK"]).zfill(10),
        }
        for _, row in df.iterrows()
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


EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def list_10k_filings(cik: str) -> list[dict]:
    """The filer's most recent 10-K filings (up to 5), most-recent-first --
    the filing-discovery step behind 10-K Reader's Exact-as-filed view.
    Free, keyless SEC EDGAR endpoint. A filer with no 10-K on record (an
    ETF, a foreign private issuer filing 20-F instead) returns an empty
    list rather than raising, so the caller can degrade to a "no 10-K
    found" message. See .scratch/10k-reader/spec.md.
    """
    response = requests.get(
        EDGAR_SUBMISSIONS_URL.format(cik=cik),
        headers={"User-Agent": _SEC_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    recent = response.json()["filings"]["recent"]
    filings = [
        {
            "accession_number": recent["accessionNumber"][i],
            "primary_document": recent["primaryDocument"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
        }
        for i, form in enumerate(recent["form"])
        if form == "10-K"
    ]
    return filings[:5]


EDGAR_ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


def _archives_base_url(cik: str, accession_number: str) -> str:
    # The Archives path uses the CIK *without* leading zeros and the
    # accession number with its dashes stripped -- unlike the
    # submissions/companyfacts APIs, which use the zero-padded CIK. See
    # .scratch/ticker-explorer/research/03-edgar-as-filed-statements-findings.md.
    return EDGAR_ARCHIVES_BASE_URL.format(cik=int(cik), accession=accession_number.replace("-", ""))


def _classify_statement_type(short_name: str) -> str | None:
    """Classify a FilingSummary.xml report's ShortName into one of the
    three core statements 10-K Reader's Exact-as-filed view supports, or
    None if it's some other report in the same "Statements" bucket (e.g.
    a Balance Sheet Parenthetical, or Statement of Shareholders' Equity).
    Keyword-matched on the filer's own wording since ShortName casing and
    phrasing (e.g. "Operations" vs "Income") varies by filer -- see
    .scratch/ticker-explorer/research/03-edgar-as-filed-statements-findings.md.
    """
    text = short_name.upper()
    if "PARENTHETICAL" in text:
        return None
    if "BALANCE SHEET" in text:
        return "Balance Sheet"
    if "CASH FLOW" in text:
        return "Cash Flow Statement"
    if "COMPREHENSIVE" in text:
        return None
    if "OPERATIONS" in text or "INCOME" in text:
        return "Income Statement"
    return None


def map_filing_statements(cik: str, accession_number: str) -> dict[str, str]:
    """Which R*.htm file is the Income Statement / Balance Sheet / Cash
    Flow Statement for a given 10-K, discovered via that filing's own
    FilingSummary.xml rather than hardcoded R-numbers -- these differ per
    filer and even per filing year for the same filer. A filing with no
    FilingSummary.xml at all (pre-XBRL, or the pre-2011 XML-report
    format) returns an empty dict rather than raising; callers should
    treat that as "exact-as-filed view isn't available for this filing."
    See .scratch/10k-reader/spec.md.
    """
    response = requests.get(
        _archives_base_url(cik, accession_number) + "FilingSummary.xml",
        headers={"User-Agent": _SEC_USER_AGENT},
        timeout=10,
    )
    if response.status_code == 404:
        return {}
    response.raise_for_status()

    root = ElementTree.fromstring(response.content)
    result: dict[str, str] = {}
    for report in root.iter("Report"):
        # Older FilingSummary.xml versions don't have MenuCategory at all
        # -- only filter on it when present, and rely on ShortName
        # keyword matching as the durable signal across filing eras.
        menu_category = report.findtext("MenuCategory")
        if menu_category is not None and menu_category != "Statements":
            continue
        html_file_name = report.findtext("HtmlFileName")
        short_name = report.findtext("ShortName")
        if not html_file_name or not short_name:
            continue
        statement_type = _classify_statement_type(short_name)
        if statement_type and statement_type not in result:
            result[statement_type] = html_file_name
    return result


# SEC's R.htm rendering (itself generated from the filing's own XBRL data)
# puts each row's underlying XBRL concept in a javascript handler on the
# label cell's <a> tag, e.g. onclick="top.Show.showAR(this,
# 'defref_us-gaap_Revenues', window)" -- a stable convention across all
# EDGAR XBRL filers' R.htm output, confirmed present on value rows and
# abstract/header rows alike. This is what makes rows identifiable beyond
# their display text: two rows can render the identical label ("Subscription"
# under both Revenue and Cost of Revenue is a real example) while tagging
# different concepts -- see .scratch/10k-exact-concept-ids/spec.md.
_CONCEPT_REF_RE = re.compile(r"showAR\(\s*this\s*,\s*'(defref_[^']+)'")


def _cell_text(cell) -> str:
    return cell.text_content().replace("\xa0", " ").strip()


def _row_concept(label_cell) -> str | None:
    for anchor in label_cell.iter("a"):
        onclick = anchor.get("onclick") or ""
        match = _CONCEPT_REF_RE.search(onclick)
        if match:
            return match.group(1)
    return None


def _disambiguate_repeated_concepts(concepts: list[str], labels: list[str]) -> list[str]:
    """A single instant-in-time XBRL concept (e.g. a cash balance) is
    routinely reported twice on the same Cash Flow Statement -- once as
    the period's beginning balance, once as its ending balance -- since
    XBRL has no separate concept for "beginning" vs "ending", only a
    different context (period) for the same tag, which isn't visible
    from the R.htm markup this parser reads. Confirmed on Apple's actual
    10-K Cash Flow Statement, and the same shape as the dimensional-axis
    collision this parser already resolves, just without an axis marker
    to key off of.

    Any concept appearing more than once within this one table's own
    rows gets its differing label folded into the key (labels do differ
    in every real case observed: "beginning balances" vs "ending
    balances"); if even that still collides, an occurrence count is
    appended so two rows within one table can never end up sharing a
    key. A concept appearing exactly once is left untouched, so the
    common case keeps matching across filings by concept alone (a filer
    rewording a label between years shouldn't stop it matching).
    """
    concept_counts = Counter(concepts)
    occurrence_counts: dict[tuple[str, str], int] = {}
    disambiguated: list[str] = []
    for concept, label in zip(concepts, labels):
        if concept_counts[concept] == 1:
            disambiguated.append(concept)
            continue
        occurrence = occurrence_counts.get((concept, label), 0)
        occurrence_counts[(concept, label)] = occurrence + 1
        suffix = label if occurrence == 0 else f"{label}#{occurrence + 1}"
        disambiguated.append(f"{concept}::{suffix}")
    return disambiguated


def fetch_as_filed_statement(cik: str, accession_number: str, r_file: str) -> pd.DataFrame:
    """The exact as-filed table for one statement of one filing -- the
    filer's own row labels, order, and subtotals, parsed directly from
    SEC's own rendered R*.htm, not re-labeled or remapped. See
    .scratch/10k-reader/spec.md.

    Parses the raw HTML directly (rather than pandas.read_html, which
    only sees display text) so each row's XBRL concept identifier can be
    captured as that row's true identity -- returned as the DataFrame's
    row index. A row with no parseable concept reference (rare) falls
    back to a synthetic, position-based key that can't collide with a
    real concept, so it's never dropped. Callers that need to merge rows
    across filings should match on this index, not on the label column
    -- see merge_as_filed_statements and
    .scratch/10k-exact-concept-ids/spec.md.
    """
    response = requests.get(
        _archives_base_url(cik, accession_number) + r_file,
        headers={"User-Agent": _SEC_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    return _parse_as_filed_statement_html(response.text)


def _parse_as_filed_statement_html(html: str) -> pd.DataFrame:
    root = lxml.html.fromstring(html)
    tables = root.xpath('//table[contains(@class, "report")]') or root.xpath("//table")
    if not tables:
        raise ValueError("No statement table found in as-filed HTML")
    table_el = tables[0]

    all_rows = table_el.xpath(".//tr")
    header_rows = [row for row in all_rows if row.xpath("./th") and not row.xpath("./td")]
    body_rows = [row for row in all_rows if row.xpath("./td")]

    if len(header_rows) >= 2:
        title = _cell_text(header_rows[0].xpath("./th")[0])
        periods = [_cell_text(th) for th in header_rows[-1].xpath("./th")]
    else:
        header_cells = header_rows[0].xpath("./th") if header_rows else []
        title = _cell_text(header_cells[0]) if header_cells else ""
        periods = [_cell_text(th) for th in header_cells[1:]]

    concepts: list[str] = []
    labels: list[str] = []
    value_rows: list[list[object]] = []
    # Some filers append a "broken down by X" disaggregation directly
    # inside the same statement table (e.g. Adobe's Income Statement
    # R.htm reports Subscription/Product/Services-and-other revenue this
    # way) -- SEC renders the start of each group as its own row whose
    # concept reference has the shape `defref_<Axis>=<Member>` rather
    # than a plain concept, confirmed on Adobe's actual FY2025 10-K. Rows
    # under that group reuse the *same* base concepts as the top-level
    # statement (e.g. "Revenue" tagged us-gaap:Revenues appears once per
    # group, not just once overall) -- without folding the active group
    # into their key, those repeats collide across groups exactly the
    # same way same-labeled-different-concept rows did, and the last
    # group processed silently wins. See .scratch/10k-exact-concept-ids
    # for the investigation that found this.
    current_axis_context: str | None = None
    for i, row in enumerate(body_rows):
        cells = row.xpath("./td")
        label_cell = cells[0]
        label = _cell_text(label_cell)
        raw_concept = _row_concept(label_cell)

        if raw_concept is not None and "=" in raw_concept:
            current_axis_context = raw_concept
            concept = raw_concept
        else:
            base_concept = raw_concept or f"__unlabeled_row_{i}__{label}"
            concept = f"{current_axis_context}::{base_concept}" if current_axis_context else base_concept

        concepts.append(concept)
        labels.append(label)

        raw_values = [_cell_text(cell) for cell in cells[1:]]
        row_values: list[object] = []
        for j in range(len(periods)):
            value = raw_values[j] if j < len(raw_values) else ""
            row_values.append(float("nan") if value == "" else value)
        value_rows.append(row_values)

    concepts = _disambiguate_repeated_concepts(concepts, labels)

    df = pd.DataFrame(value_rows, columns=periods)
    df.insert(0, title, labels)
    df.index = pd.Index(concepts, name="concept")
    return df


def merge_as_filed_statements(tables: list[pd.DataFrame], year_labels: list[str]) -> pd.DataFrame:
    """Merge multiple as-filed statement tables (one per filing, see
    fetch_as_filed_statement) into a single wide table: one column per
    `year_labels` entry (same order/length as `tables`), one row per
    unique XBRL concept across all of them. Only each filing's own
    primary column (`table.columns[1]`, its most-recently-reported
    period) is used -- a filing's own table already repeats 1-2 prior
    years for comparison, and including those would duplicate the same
    figures across overlapping filings, which is what produced the
    confusing overlapping-year display this replaces (5 separate tables,
    each with its own 2-year span, reading like "12 23 34 45" down the
    page instead of 5 distinct years).

    Rows are matched by each table's row index (the XBRL concept
    identifier fetch_as_filed_statement now returns), not by display
    label text -- two rows can render the identical label while tagging
    different concepts (e.g. a company reporting "Subscription" under
    both Revenue and Cost of Revenue), and matching on label text alone
    let the later one silently overwrite the earlier one's value. The
    label shown for a merged row is taken from whichever filing was
    processed first (see row-order note below) -- a filer rewording a
    line's label between years no longer risks a value collision, at
    most an older year's value appears under newer wording. A genuine
    XBRL tag migration for what reads as "the same" line (e.g. adopting
    a new revenue-recognition tag) is intentionally left as two separate
    rows rather than heuristically re-merged: a visible split of
    still-correct data beats a silent, possibly-wrong merge. See
    .scratch/10k-exact-concept-ids/spec.md.

    A concept missing from a given filing gets "" (blank), not NaN or 0
    -- these are as-filed figures, not computed ones, so there's no
    meaningful zero to fill in. Row order follows first-seen order
    scanning `tables` in the order given (callers pass most-recent-
    filing-first), so a concept unique to an older filing still gets a
    place, appended after the newer filings' own row order.
    """
    if not tables:
        return pd.DataFrame()

    labels_by_concept: dict[str, str] = {}
    values_by_concept: dict[str, dict[str, object]] = {}
    concept_order: list[str] = []
    for table, year_label in zip(tables, year_labels):
        if table.shape[1] < 2:
            continue
        label_col, value_col = table.columns[0], table.columns[1]
        for raw_concept, entry in table.iterrows():
            concept = str(raw_concept)
            if concept not in labels_by_concept:
                labels_by_concept[concept] = str(entry[label_col])
                concept_order.append(concept)
            value = entry[value_col]
            values_by_concept.setdefault(concept, {})[year_label] = "" if pd.isna(value) else value

    merged = pd.DataFrame(
        {
            year_label: [values_by_concept.get(concept, {}).get(year_label, "") for concept in concept_order]
            for year_label in year_labels
        }
    )
    merged.index = pd.Index([labels_by_concept[concept] for concept in concept_order])
    merged.index.name = str(tables[0].columns[0])
    return merged


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


def _resolve_revenue(facts: dict) -> dict[int, tuple[str, float]]:
    # The bank tag is the highest-priority entry in a single per-period
    # chain, not a whole-company either/or switch -- a filer with
    # RevenuesNetOfInterestExpense for most years but a gap the standard
    # chain happens to cover should still get that year filled in, per
    # spec.md's "evaluated per fiscal period" rule.
    bank_taxonomy, bank_tag = _BANK_REVENUE_TAG
    return _fallback_per_period(
        [_annual_facts(facts, bank_taxonomy, bank_tag)]
        + [_annual_facts(facts, taxonomy, tag) for taxonomy, tag in _REVENUE_CHAIN]
    )


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
    revenue = _resolve_revenue(facts)

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


# Tag-fallback chains for 10-K Reader's Normalized sub-tab, decided in
# .scratch/10k-reader/research/01-normalized-tag-mapping-findings.md
# against live companyfacts data for AAPL, MSFT, JPM, and SPG. Revenue,
# Net Income, EPS, Dividends/share, and Shares Outstanding reuse the
# chains already defined above for get_fundamentals_history.
_COST_OF_REVENUE_CHAIN = [
    ("us-gaap", "CostOfGoodsAndServicesSold"),
    ("us-gaap", "CostOfRevenue"),
    ("us-gaap", "CostOfGoodsSold"),
]
_GROSS_PROFIT_CHAIN = [("us-gaap", "GrossProfit")]
_OPERATING_EXPENSES_CHAIN = [("us-gaap", "OperatingExpenses"), ("us-gaap", "CostsAndExpenses")]
# Banks don't tag OperatingExpenses/CostsAndExpenses at all -- same
# per-period-priority pattern as _BANK_REVENUE_TAG, not a whole-company
# either/or switch.
_BANK_OPERATING_EXPENSES_TAG = ("us-gaap", "NoninterestExpense")
_OPERATING_INCOME_CHAIN = [("us-gaap", "OperatingIncomeLoss")]
_INTEREST_EXPENSE_CHAIN = [("us-gaap", "InterestExpense"), ("us-gaap", "InterestExpenseNonoperating")]
_PRETAX_INCOME_CHAIN = [
    ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
    ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
]
_INCOME_TAX_CHAIN = [("us-gaap", "IncomeTaxExpenseBenefit")]
_EPS_BASIC_CHAIN = [("us-gaap", "EarningsPerShareBasic")]
_EPS_DILUTED_CHAIN = [("us-gaap", "EarningsPerShareDiluted")]

_CASH_CHAIN = [
    ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
    ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
]
_CURRENT_ASSETS_CHAIN = [("us-gaap", "AssetsCurrent")]
_PPE_CHAIN = [("us-gaap", "PropertyPlantAndEquipmentNet"), ("us-gaap", "RealEstateInvestmentPropertyNet")]
_GOODWILL_TAG = ("us-gaap", "Goodwill")
_INTANGIBLES_COMBINED_TAG = ("us-gaap", "IntangibleAssetsNetExcludingGoodwill")
_INTANGIBLES_FINITE_TAG = ("us-gaap", "FiniteLivedIntangibleAssetsNet")
_INTANGIBLES_INDEFINITE_TAG = ("us-gaap", "IndefiniteLivedIntangibleAssetsExcludingGoodwill")
_TOTAL_ASSETS_CHAIN = [("us-gaap", "Assets")]
_CURRENT_LIABILITIES_CHAIN = [("us-gaap", "LiabilitiesCurrent")]
_LONG_TERM_DEBT_CHAIN = [
    ("us-gaap", "LongTermDebtNoncurrent"),
    ("us-gaap", "LongTermDebt"),
    ("us-gaap", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"),
    ("us-gaap", "DebtAndCapitalLeaseObligations"),
]
_TOTAL_LIABILITIES_CHAIN = [("us-gaap", "Liabilities")]
_STOCKHOLDERS_EQUITY_CHAIN = [
    ("us-gaap", "StockholdersEquity"),
    ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
]

_OPERATING_CASH_FLOW_CHAIN = [("us-gaap", "NetCashProvidedByUsedInOperatingActivities")]
_CAPEX_CHAIN = [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"), ("us-gaap", "PaymentsToAcquireProductiveAssets")]
_INVESTING_CASH_FLOW_CHAIN = [("us-gaap", "NetCashProvidedByUsedInInvestingActivities")]
_FINANCING_CASH_FLOW_CHAIN = [("us-gaap", "NetCashProvidedByUsedInFinancingActivities")]
_NET_CHANGE_IN_CASH_CHAIN = [
    ("us-gaap", "CashAndCashEquivalentsPeriodIncreaseDecrease"),
    (
        "us-gaap",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
    ),
    (
        "us-gaap",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect",
    ),
]


def _resolve_operating_expenses(facts: dict) -> dict[int, tuple[str, float]]:
    bank_taxonomy, bank_tag = _BANK_OPERATING_EXPENSES_TAG
    return _fallback_per_period(
        [_annual_facts(facts, bank_taxonomy, bank_tag)]
        + [_annual_facts(facts, taxonomy, tag) for taxonomy, tag in _OPERATING_EXPENSES_CHAIN]
    )


def _resolve_pretax_income(
    facts: dict, net_income: dict[int, tuple[str, float]], income_tax: dict[int, tuple[str, float]]
) -> dict[int, tuple[str, float]]:
    pretax = _resolve_chain(facts, _PRETAX_INCOME_CHAIN)
    # REITs (and any filer without a direct pre-tax subtotal tag) get an
    # exact-identity derived fallback -- Net Income + Income Tax -- only
    # for periods the direct chain didn't already resolve.
    for fy in set(net_income) & set(income_tax):
        if fy not in pretax:
            net_end, net_val = net_income[fy]
            _, tax_val = income_tax[fy]
            pretax[fy] = (net_end, net_val + tax_val)
    return pretax


def _resolve_intangibles(facts: dict) -> dict[int, tuple[str, float]]:
    combined = _annual_facts(facts, *_INTANGIBLES_COMBINED_TAG)
    finite = _annual_facts(facts, *_INTANGIBLES_FINITE_TAG)
    indefinite = _annual_facts(facts, *_INTANGIBLES_INDEFINITE_TAG)
    # The combined tag, where present, already includes both finite- and
    # indefinite-lived intangibles -- summing the component tags on top
    # of it would double-count, so it wins outright for any period it
    # covers.
    result = dict(combined)
    for fy in set(finite) | set(indefinite):
        if fy in result:
            continue
        if fy in finite and fy in indefinite:
            end, finite_val = finite[fy]
            _, indef_val = indefinite[fy]
            result[fy] = (end, finite_val + indef_val)
        elif fy in finite:
            result[fy] = finite[fy]
        else:
            result[fy] = indefinite[fy]
    return result


def _resolve_goodwill_and_intangibles(facts: dict) -> dict[int, tuple[str, float]]:
    # No filer in the research sample reports a single combined
    # "goodwill and intangibles" tag -- always a derived sum of two
    # components.
    goodwill = _annual_facts(facts, *_GOODWILL_TAG)
    intangibles = _resolve_intangibles(facts)
    result: dict[int, tuple[str, float]] = {}
    for fy in set(goodwill) | set(intangibles):
        g_end, g_val = goodwill.get(fy, (None, 0.0))
        i_end, i_val = intangibles.get(fy, (None, 0.0))
        end = g_end or i_end
        assert end is not None  # fy is in goodwill's or intangibles' keys, so one of these is real
        result[fy] = (end, g_val + i_val)
    return result


def _to_metric_by_year_frame(metrics: dict[str, dict[int, tuple[str, float]]], years: int | None) -> pd.DataFrame:
    """Reshape {metric_label: {fiscal_year: (period_end, value)}} into one
    DataFrame -- metric rows, fiscal-year columns, most-recent year first
    -- matching how the Exact-as-filed tables and real 10-K statements
    present, the opposite orientation from get_fundamentals_history's
    fiscal-year-rows shape. `years=None` returns the company's full
    available history; otherwise the most recent `years` columns. A
    metric absent for a given year is simply missing from that column
    (NaN), not zero -- the caller renders that as the dash placeholder.
    """
    all_fys = sorted({fy for series in metrics.values() for fy in series}, reverse=True)
    selected_fys = all_fys if years is None else all_fys[:years]
    df = pd.DataFrame(
        {fy: {label: series[fy][1] for label, series in metrics.items() if fy in series} for fy in selected_fys}
    )
    df.index.name = "Metric"
    return df


def get_normalized_10k_financials(cik: str, years: int | None = 5) -> dict[str, pd.DataFrame]:
    """Curated multi-year Income Statement / Balance Sheet / Cash Flow
    tables for `cik` via SEC EDGAR's XBRL companyfacts API -- metric rows
    x fiscal-year columns. `years` bounds how many of the most recent
    fiscal years are included; pass None to reach the company's full
    available EDGAR history. Kept separate from get_fundamentals_history
    (not a modification of it) so that function's existing callers
    (Historicals, Peer Analysis) can't regress. See
    .scratch/10k-reader/spec.md and
    .scratch/10k-reader/research/01-normalized-tag-mapping-findings.md.
    """
    facts = _fetch_companyfacts(cik)

    net_income = _resolve_chain(facts, _NET_INCOME_CHAIN)
    income_tax = _resolve_chain(facts, _INCOME_TAX_CHAIN)

    income_statement = {
        "Revenue": _resolve_revenue(facts),
        "Cost of Revenue": _resolve_chain(facts, _COST_OF_REVENUE_CHAIN),
        "Gross Profit": _resolve_chain(facts, _GROSS_PROFIT_CHAIN),
        "Operating Expenses": _resolve_operating_expenses(facts),
        "Operating Income": _resolve_chain(facts, _OPERATING_INCOME_CHAIN),
        "Interest Expense": _resolve_chain(facts, _INTEREST_EXPENSE_CHAIN),
        "Pre-tax Income": _resolve_pretax_income(facts, net_income, income_tax),
        "Income Tax": income_tax,
        "Net Income": net_income,
        "EPS Basic": _resolve_chain(facts, _EPS_BASIC_CHAIN),
        "EPS Diluted": _resolve_chain(facts, _EPS_DILUTED_CHAIN),
    }
    balance_sheet = {
        "Cash & Equivalents": _resolve_chain(facts, _CASH_CHAIN),
        "Total Current Assets": _resolve_chain(facts, _CURRENT_ASSETS_CHAIN),
        "PP&E (net)": _resolve_chain(facts, _PPE_CHAIN),
        "Goodwill & Intangible Assets": _resolve_goodwill_and_intangibles(facts),
        "Total Assets": _resolve_chain(facts, _TOTAL_ASSETS_CHAIN),
        "Total Current Liabilities": _resolve_chain(facts, _CURRENT_LIABILITIES_CHAIN),
        "Long-term Debt": _resolve_chain(facts, _LONG_TERM_DEBT_CHAIN),
        "Total Liabilities": _resolve_chain(facts, _TOTAL_LIABILITIES_CHAIN),
        "Total Stockholders' Equity": _resolve_chain(facts, _STOCKHOLDERS_EQUITY_CHAIN),
    }
    cash_flow = {
        "Operating Cash Flow": _resolve_chain(facts, _OPERATING_CASH_FLOW_CHAIN),
        "Capital Expenditures": _resolve_chain(facts, _CAPEX_CHAIN),
        "Investing Cash Flow": _resolve_chain(facts, _INVESTING_CASH_FLOW_CHAIN),
        "Financing Cash Flow": _resolve_chain(facts, _FINANCING_CASH_FLOW_CHAIN),
        "Net Change in Cash": _resolve_chain(facts, _NET_CHANGE_IN_CASH_CHAIN),
    }

    return {
        "Income Statement": _to_metric_by_year_frame(income_statement, years),
        "Balance Sheet": _to_metric_by_year_frame(balance_sheet, years),
        "Cash Flow Statement": _to_metric_by_year_frame(cash_flow, years),
    }


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


def get_multi_ticker_historicals(
    tickers: list[str], start: date, end: date, *, fetch_historicals=get_historicals
) -> dict[str, pd.DataFrame]:
    """Daily historicals (see get_historicals) for each of `tickers`,
    keyed by ticker. A ticker whose fetch fails (bad symbol, transient
    yfinance error) is logged and simply omitted from the result rather
    than failing the whole batch -- see Peer Analysis spec.md's per-peer
    graceful degradation decision.
    """
    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            result[ticker] = fetch_historicals(ticker, start, end)
        except Exception:
            logger.exception("Historicals fetch failed for peer %s", ticker)
    return result


def build_peer_price_frame(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Reshape per-ticker historicals (see get_multi_ticker_historicals)
    into one wide DataFrame -- index the union of every peer's dates,
    one column per ticker holding its AdjClose. A peer with a shorter
    history has NaN before its first available date rather than the
    whole frame being truncated down to the shortest peer -- see
    Peer Analysis spec.md's "peers just start later" decision. Pure
    reshape, no I/O.
    """
    if not histories:
        return pd.DataFrame()
    return pd.DataFrame({ticker: history["AdjClose"] for ticker, history in histories.items()}).sort_index()


_TRADING_DAYS_PER_YEAR = 252


def compute_peer_performance_stats(price_frame: pd.DataFrame) -> pd.DataFrame:
    """Total return, annualized volatility, and max drawdown per ticker
    column of `price_frame` (see build_peer_price_frame), computed over
    whatever range the caller has already restricted the frame to. Pure
    computation, no I/O. A ticker with fewer than 2 valid (non-NaN)
    prices in range gets NaN for every stat rather than a crash or a
    misleading number -- see Peer Analysis spec.md's Ticket 04.
    """
    rows = []
    for ticker in price_frame.columns:
        series = price_frame[ticker].dropna()
        if len(series) < 2:
            rows.append(
                {"Ticker": ticker, "Total Return (%)": float("nan"), "Volatility (%)": float("nan"), "Max Drawdown (%)": float("nan")}
            )
            continue

        total_return = (series.iloc[-1] - series.iloc[0]) / series.iloc[0] * 100
        daily_returns = series.pct_change().dropna()
        volatility = daily_returns.std() * (_TRADING_DAYS_PER_YEAR**0.5) * 100
        max_drawdown = (series / series.cummax() - 1).min() * 100

        rows.append(
            {
                "Ticker": ticker,
                "Total Return (%)": total_return,
                "Volatility (%)": volatility,
                "Max Drawdown (%)": max_drawdown,
            }
        )

    return pd.DataFrame(rows).set_index("Ticker")


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


_FINNHUB_METRIC_URL = "https://finnhub.io/api/v1/stock/metric"


def get_fundamentals_from_finnhub(ticker: str) -> dict:
    """Current Fundamentals snapshot for `ticker` from Finnhub's free-tier
    basic-financials endpoint (stock/metric?metric=all), shaped to the
    same keys build_fundamentals_pivot's other sources use. Requires
    FINNHUB_API_KEY; raises if it's unset, so build_fundamentals_pivot
    catches that the same way it catches any other per-source failure
    (see spec.md's "API keys" decision).

    marketCapitalization, 52WeekHigh/Low, peTTM, and
    dividendYieldIndicatedAnnual are confirmed against Finnhub's
    documented example responses. epsInclExtraItemsTTM (Finnhub's "EPS
    TTM including extra items" figure) and the assumption that its
    dividend yield is already a percent, matching yfinance's convention,
    are the best-available reading and not confirmed against a live
    response -- if either looks off, check here first.
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("FINNHUB_API_KEY is not set")

    response = requests.get(
        _FINNHUB_METRIC_URL,
        params={"symbol": ticker, "metric": "all", "token": api_key},
        timeout=10,
    )
    response.raise_for_status()
    metric = response.json().get("metric") or {}

    market_cap = metric.get("marketCapitalization")  # Finnhub reports this in millions
    return {
        "market_cap": market_cap * 1e6 if market_cap is not None else None,
        "trailing_pe": metric.get("peTTM"),
        "eps": metric.get("epsInclExtraItemsTTM"),
        "dividend_yield": metric.get("dividendYieldIndicatedAnnual"),
        "fifty_two_week_high": metric.get("52WeekHigh"),
        "fifty_two_week_low": metric.get("52WeekLow"),
    }


_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def get_fundamentals_from_alpha_vantage(ticker: str) -> dict:
    """Current Fundamentals snapshot for `ticker` from Alpha Vantage's
    free-tier OVERVIEW endpoint, shaped to build_fundamentals_pivot's
    metric keys. Requires ALPHAVANTAGE_API_KEY; raises if it's unset (see
    get_fundamentals_from_finnhub). Also raises on a rate-limited or
    invalid-key response -- Alpha Vantage returns HTTP 200 with an
    {"Information": ...} or {"Note": ...} body instead of real fields in
    that case, which has no "Symbol" key to key off of.
    """
    api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY is not set")

    response = requests.get(
        _ALPHA_VANTAGE_URL,
        params={"function": "OVERVIEW", "symbol": ticker, "apikey": api_key},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if "Symbol" not in data:
        raise ValueError(f"Alpha Vantage returned no OVERVIEW data for {ticker!r}: {data}")

    def num(key: str) -> float | None:
        # Every field comes back as a string, and a missing one as the
        # literal string "None" rather than an absent key.
        raw = data.get(key)
        if raw in (None, "None", "-", ""):
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def text(key: str) -> str | None:
        raw = data.get(key)
        return raw if raw not in (None, "None", "") else None

    dividend_yield = num("DividendYield")
    return {
        "market_cap": num("MarketCapitalization"),
        "trailing_pe": num("PERatio"),
        "forward_pe": num("ForwardPE"),
        "eps": num("EPS"),
        # Reported as a fraction of price (e.g. 0.0057 = 0.57%);
        # normalized here to the percent convention the other sources use.
        "dividend_yield": dividend_yield * 100 if dividend_yield is not None else None,
        "sector": text("Sector"),
        "industry": text("Industry"),
        "fifty_two_week_high": num("52WeekHigh"),
        "fifty_two_week_low": num("52WeekLow"),
        "revenue_fy": num("RevenueTTM"),
    }


# One row per metric, in display order; the key is what each source
# function above (and _snapshot/_history below) populates its dict with.
_PIVOT_METRICS: list[tuple[str, str]] = [
    ("sector", "Sector"),
    ("industry", "Industry"),
    ("market_cap", "Market cap"),
    ("trailing_pe", "Trailing P/E"),
    ("forward_pe", "Forward P/E"),
    ("eps", "EPS"),
    ("dividend_yield", "Dividend yield (%)"),
    ("fifty_two_week_high", "52-week high"),
    ("fifty_two_week_low", "52-week low"),
    # Not FY-only despite the key name -- Alpha Vantage's RevenueTTM lands
    # here too (see get_fundamentals_from_alpha_vantage), which is why the
    # label stays plain and the FY-vs-TTM distinction is called out in
    # app.py's Fundamentals caption instead of in this label.
    ("revenue_fy", "Revenue"),
    ("net_income_fy", "Net income"),
]

_PIVOT_PLACEHOLDER = "—"


def format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1e12:
        return f"{sign}${magnitude / 1e12:.2f}T"
    if magnitude >= 1e9:
        return f"{sign}${magnitude / 1e9:.2f}B"
    if magnitude >= 1e6:
        return f"{sign}${magnitude / 1e6:.1f}M"
    return f"{sign}${magnitude:,.2f}"


def _format_pivot_value(key: str, value):
    if key in ("sector", "industry"):
        return str(value)
    if key in ("market_cap", "revenue_fy", "net_income_fy"):
        return format_money(value)
    if key in ("trailing_pe", "forward_pe"):
        return f"{value:.1f}×"
    if key == "eps":
        return f"${value:.2f}"
    if key == "dividend_yield":
        return f"{value:.2f}%"
    if key in ("fifty_two_week_high", "fifty_two_week_low"):
        return f"${value:,.2f}"
    return str(value)


def _pivot_cell(row: dict, key: str):
    value = row.get(key)
    if value is None or pd.isna(value):
        return _PIVOT_PLACEHOLDER
    return _format_pivot_value(key, value)


def build_fundamentals_pivot(
    ticker: str,
    cik: str | None,
    price_history: pd.DataFrame,
    *,
    fetch_snapshot=get_fundamentals_snapshot,
    fetch_history=get_fundamentals_history,
    fetch_finnhub=get_fundamentals_from_finnhub,
    fetch_alpha_vantage=get_fundamentals_from_alpha_vantage,
) -> pd.DataFrame:
    """One row per Fundamentals metric, one column per source that
    responded -- see spec.md's Multi-source Fundamentals decision. Each
    source is fetched and shaped independently; a failure in one (missing
    key, timeout, rate-limit, bad response) drops only that column, never
    the whole table. A metric a given source doesn't report is "—", not a
    blank cell or zero.

    The `fetch_*` parameters default to this module's own fetchers but
    accept overrides so app.py can pass in its st.cache_data-wrapped
    versions (each with its own TTL -- Alpha Vantage needs a much longer
    one than the others, per spec.md's rate-limit decision) without this
    function importing Streamlit.
    """
    columns: dict[str, dict] = {}

    try:
        snapshot = fetch_snapshot(ticker)
        columns["yfinance"] = {
            "sector": snapshot.get("sector"),
            "industry": snapshot.get("industry"),
            "market_cap": snapshot.get("market_cap"),
            "trailing_pe": snapshot.get("trailing_pe"),
            "forward_pe": snapshot.get("forward_pe"),
            "eps": snapshot.get("eps_ttm"),
            "dividend_yield": snapshot.get("dividend_yield"),
            "fifty_two_week_high": snapshot.get("fifty_two_week_high"),
            "fifty_two_week_low": snapshot.get("fifty_two_week_low"),
        }
    except Exception:
        logger.exception("yfinance fundamentals fetch failed for %s", ticker)

    if cik is not None:
        try:
            history = fetch_history(cik, price_history)
            if not history.empty:
                latest = history.loc[history.index.max()]
                # Revenue already carries the bank-appropriate substitution
                # (RevenuesNetOfInterestExpense) from get_fundamentals_history
                # itself -- this row inherits it automatically, per spec.md's
                # "stays source-scoped" decision.
                columns["SEC EDGAR"] = {
                    "market_cap": latest.get("MarketCap"),
                    "trailing_pe": latest.get("TrailingPE"),
                    "eps": latest.get("EPS"),
                    "revenue_fy": latest.get("Revenue"),
                    "net_income_fy": latest.get("NetIncome"),
                }
        except Exception:
            logger.exception("SEC EDGAR fundamentals fetch failed for CIK %s", cik)

    if os.environ.get("FINNHUB_API_KEY"):
        try:
            columns["Finnhub"] = fetch_finnhub(ticker)
        except Exception:
            logger.exception("Finnhub fundamentals fetch failed for %s", ticker)

    if os.environ.get("ALPHAVANTAGE_API_KEY"):
        try:
            columns["Alpha Vantage"] = fetch_alpha_vantage(ticker)
        except Exception:
            logger.exception("Alpha Vantage fundamentals fetch failed for %s", ticker)

    index = pd.Index([label for _, label in _PIVOT_METRICS], name="Metric")
    data = {
        source: [_pivot_cell(row, key) for key, _ in _PIVOT_METRICS]
        for source, row in columns.items()
    }
    return pd.DataFrame(data, index=index)


# Fixed fallback order for collapsing a peer's per-source pivot row into a
# single value -- yfinance first (fastest, no daily cap), then SEC EDGAR
# (free, keyless, but snapshot fields only reach market cap/trailing P/E),
# then Finnhub, then Alpha Vantage last (25 requests/day free-tier cap,
# shared app-wide with the single-ticker Fundamentals section). See Peer
# Analysis spec.md's fundamentals-table decision.
_PEER_FUNDAMENTALS_SOURCE_PRIORITY = ["yfinance", "SEC EDGAR", "Finnhub", "Alpha Vantage"]


def build_peer_fundamentals_pivot(
    tickers: list[str],
    cik_by_ticker: dict[str, str | None],
    histories: dict[str, pd.DataFrame],
    *,
    fetch_snapshot=get_fundamentals_snapshot,
    fetch_history=get_fundamentals_history,
    fetch_finnhub=get_fundamentals_from_finnhub,
    fetch_alpha_vantage=get_fundamentals_from_alpha_vantage,
) -> pd.DataFrame:
    """One row per Fundamentals metric, one column per peer ticker -- the
    Peer Analysis comparison table. For each ticker, reuses the existing
    build_fundamentals_pivot (the same 4-source cross-check the
    single-ticker Fundamentals section uses) to get a metric x source
    table, then collapses each metric to a single value by trying sources
    in _PEER_FUNDAMENTALS_SOURCE_PRIORITY order and taking the first
    non-placeholder value. A ticker missing from `histories` (its own
    historicals fetch failed upstream) falls back to an empty price
    history rather than raising -- SEC EDGAR's revenue/net income/EPS
    rows are unaffected, only its market-cap/trailing-P/E derivation
    (which needs a price series) comes back empty for that ticker.
    """
    columns: dict[str, pd.Series] = {}

    for ticker in tickers:
        price_history = histories.get(ticker, pd.DataFrame(columns=["AdjClose"]))
        try:
            per_source = build_fundamentals_pivot(
                ticker, cik_by_ticker.get(ticker), price_history,
                fetch_snapshot=fetch_snapshot, fetch_history=fetch_history,
                fetch_finnhub=fetch_finnhub, fetch_alpha_vantage=fetch_alpha_vantage,
            )
        except Exception:
            logger.exception("Peer fundamentals fetch failed for %s", ticker)
            per_source = pd.DataFrame(index=pd.Index([label for _, label in _PIVOT_METRICS], name="Metric"))

        collapsed = []
        for label in per_source.index:
            value = _PIVOT_PLACEHOLDER
            for source in _PEER_FUNDAMENTALS_SOURCE_PRIORITY:
                if source in per_source.columns and per_source.loc[label, source] != _PIVOT_PLACEHOLDER:
                    value = per_source.loc[label, source]
                    break
            collapsed.append(value)
        columns[ticker] = pd.Series(collapsed, index=per_source.index)

    index = pd.Index([label for _, label in _PIVOT_METRICS], name="Metric")
    return pd.DataFrame(columns, index=index)

"""
Live validation for the as-filed statement parser (see
_parse_as_filed_statement_html and merge_as_filed_statements) against
the current top 20 S&P 500 companies by market cap -- not just Adobe,
where the underlying bug (a display label reused across different XBRL
concepts, and the same base concept reused across a dimensional
breakdown embedded in one statement table) was originally found and
fixed.

This is a genuine data-layer check, so unlike tests/e2e/'s browser tests
it calls ticker_data.py directly -- no browser needed -- but it still
needs live SEC EDGAR + yfinance access and ranks all ~500 S&P 500
constituents by market cap, so it's slow and lives outside the fast,
offline unit suite. Marked so it's excluded from the default `pytest`
run (per pytest.ini's `-m "not e2e"`); run explicitly with `pytest -m e2e`.
"""

import concurrent.futures

import lxml.html
import pytest
import requests

import ticker_data as td

pytestmark = pytest.mark.e2e

# Adobe is the company where the original bug was found and fixed (see
# .scratch/10k-exact-concept-ids) -- checked unconditionally, in addition
# to whichever 20 companies currently rank largest by market cap, since
# Adobe itself isn't guaranteed to still be one of them.
KNOWN_REGRESSION_TICKER = "ADBE"


def _top_20_sp500_by_market_cap() -> list[dict]:
    constituents = td.load_sp500_constituents()

    def market_cap_for(constituent: dict) -> float:
        try:
            snapshot = td.get_fundamentals_snapshot(constituent["ticker"])
            return snapshot.get("market_cap") or 0.0
        except Exception:
            return 0.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        market_caps = list(executor.map(market_cap_for, constituents))

    ranked = sorted(zip(market_caps, constituents), key=lambda pair: pair[0], reverse=True)
    return [constituent for market_cap, constituent in ranked[:20] if market_cap > 0]


def _count_source_body_rows(html: str) -> int:
    """Counts statement rows directly in the raw HTML (re-parsed here,
    not reading fetch_as_filed_statement's own output) -- used to confirm
    the parser never silently drops or collapses a row. Deliberately the
    stricter of the two counts ticket 03 describes (all body rows, not
    just ones carrying a concept reference): every row gets a key in the
    output either way -- a real concept reference or a synthetic
    fallback -- so this bound never has false negatives.
    """
    root = lxml.html.fromstring(html)
    tables = root.xpath('//table[contains(@class, "report")]') or root.xpath("//table")
    return len([row for row in tables[0].xpath(".//tr") if row.xpath("./td")])


def _latest_10k_statement_r_files(ticker: str, cik: str) -> dict[str, tuple[str, str]]:
    """Maps each recognized statement type to (accession_number, r_file)
    for the filer's most recent 10-K.
    """
    filings = td.list_10k_filings(cik)
    if not filings:
        raise ValueError(f"{ticker}: no 10-K filings found")
    filing = filings[0]
    statements = td.map_filing_statements(cik, filing["accession_number"])
    if not statements:
        raise ValueError(f"{ticker}: filing {filing['accession_number']} has no recognized statements")

    return {
        statement_type: (filing["accession_number"], r_file)
        for statement_type, r_file in statements.items()
    }


def _validate_one_company(ticker: str, cik: str) -> tuple[list[str], str | None]:
    """Returns (parsing failures, a discovery-skip reason or None).

    Discovery failures (no 10-K found for this CIK, or none of its
    reports resolve to a recognized statement) are reported separately
    from parsing failures rather than counted as the same thing: they
    reflect on filing discovery / the S&P 500 constituent data's CIKs
    (e.g. a company that recently reorganized under a new holding-company
    CIK with no filing history of its own yet -- observed live for XOM),
    not on the as-filed statement parser this test exists to validate.
    """
    failures: list[str] = []
    try:
        r_files_by_statement = _latest_10k_statement_r_files(ticker, cik)
    except Exception as exc:
        return [], f"{ticker}: couldn't discover filings/statements ({exc})"

    for statement_type, (accession, r_file) in r_files_by_statement.items():
        try:
            df = td.fetch_as_filed_statement(cik, accession, r_file)
        except Exception as exc:
            failures.append(f"{ticker} {statement_type}: fetch/parse raised {exc!r}")
            continue

        if len(df.index) != len(set(df.index)):
            failures.append(f"{ticker} {statement_type}: row index has duplicate keys -- a collision slipped through")

        html = requests.get(
            td._archives_base_url(cik, accession) + r_file,
            headers={"User-Agent": td._SEC_USER_AGENT},
            timeout=10,
        ).text
        source_row_count = _count_source_body_rows(html)
        if len(df) != source_row_count:
            failures.append(
                f"{ticker} {statement_type}: parsed {len(df)} rows but source HTML has {source_row_count} "
                "body rows -- a row was silently dropped or collapsed"
            )

    return failures, None


def test_top_20_sp500_as_filed_statements_parse_cleanly():
    top_20 = _top_20_sp500_by_market_cap()
    assert len(top_20) >= 15, "expected to successfully rank at least 15 of the S&P 500 by market cap"

    all_failures: list[str] = []
    discovery_skips: list[str] = []
    for constituent in top_20:
        failures, skip_reason = _validate_one_company(constituent["ticker"], constituent["cik"])
        all_failures.extend(failures)
        if skip_reason:
            discovery_skips.append(skip_reason)

    validated_count = len(top_20) - len(discovery_skips)
    if discovery_skips:
        print(f"\nSkipped (filing discovery, not a parser concern): {discovery_skips}")
    assert validated_count >= 15, (
        f"too few companies were actually validated ({validated_count}/{len(top_20)}) -- "
        f"discovery skips: {discovery_skips}"
    )
    assert not all_failures, "As-filed statement parsing problems found:\n" + "\n".join(all_failures)


def test_adobe_revenue_breakdown_resolves_correctly_live():
    """The specific, known regression case: Adobe's real, current 10-K
    Income Statement embeds a revenue-by-type breakdown reusing the same
    base concepts as the top-level statement. Confirms live (not just via
    the hand-built fixtures in test_ticker_data_as_filed_statements.py)
    that the total and every breakdown group resolve to distinct,
    correctly-summing values.
    """
    tickers = td.load_company_tickers()
    matches = td.resolve_ticker(KNOWN_REGRESSION_TICKER, tickers)
    assert matches, f"couldn't resolve {KNOWN_REGRESSION_TICKER} against SEC's own ticker directory"
    cik = matches[0]["cik"]

    filings = td.list_10k_filings(cik)
    assert filings, f"no 10-K filings found for {KNOWN_REGRESSION_TICKER}"
    accession = filings[0]["accession_number"]
    r_file = td.map_filing_statements(cik, accession)["Income Statement"]
    df = td.fetch_as_filed_statement(cik, accession, r_file)

    revenue_rows = df[df.iloc[:, 0] == "Revenue"]
    assert len(revenue_rows) >= 2, (
        "expected Adobe's latest 10-K to still show a top-level Revenue figure plus at least one "
        "breakdown group's own Revenue figure as distinct rows"
    )
    assert len(set(revenue_rows.index)) == len(revenue_rows), "duplicate concept keys among Revenue rows"

    def _to_number(raw) -> float:
        return float(str(raw).replace("$", "").replace(",", "").strip())

    values = sorted((_to_number(v) for v in revenue_rows.iloc[:, 1]), reverse=True)
    total, *groups = values
    assert sum(groups) == pytest.approx(total, rel=0.01), (
        f"breakdown groups {groups} don't sum to the top-level total {total} -- "
        "a group may still be colliding with another"
    )


def test_adobe_merged_5_year_view_shows_correct_historical_breakdown_live():
    """Ticket 02's specific acceptance criterion: "viewing Adobe's merged
    5-year Income Statement: Subscription and Product show Adobe's actual
    reported revenue for FY2021-FY2022 ... and blank cells for
    FY2023-FY2025 ... confirmed by fetching Adobe's real filings, not a
    synthetic fixture alone." This exercises merge_as_filed_statements
    itself (not just the single-filing fetch, which the test above
    already covers live) against Adobe's five most recent real 10-Ks.
    """
    tickers = td.load_company_tickers()
    cik = td.resolve_ticker(KNOWN_REGRESSION_TICKER, tickers)[0]["cik"]
    filings = td.list_10k_filings(cik)
    assert len(filings) >= 5, f"expected at least 5 10-Ks on record for {KNOWN_REGRESSION_TICKER}"

    recent_filings = filings[:5]
    year_labels = [filing["report_date"][:4] for filing in recent_filings]
    tables = [
        td.fetch_as_filed_statement(cik, filing["accession_number"], td.map_filing_statements(cik, filing["accession_number"])["Income Statement"])
        for filing in recent_filings
    ]

    merged = td.merge_as_filed_statements(tables, year_labels)

    def _to_number(raw) -> float | None:
        text = str(raw).replace("$", "").replace(",", "").strip()
        return None if text == "" else float(text)

    # Adobe's own reporting changed over this window: FY2023-FY2025's own
    # filings report a single consolidated "Revenue" line, plus a separate
    # revenue-by-type breakdown appended to the same statement table (see
    # test_fetch_as_filed_statement_disambiguates_axis_breakdown...);
    # FY2021-FY2022's own filings instead break Subscription/Product/
    # Services out directly on the face of the statement. Both eras
    # produce their own "Subscription"-labeled row (a different concept
    # each), so there are two here -- find the one with real, older-year
    # values rather than assuming there's only one.
    subscription_rows = merged.loc[merged.index == "Subscription"]
    assert len(subscription_rows) >= 1
    older_years = year_labels[3:]  # FY2022, FY2021
    subscription = max(
        (row for _, row in subscription_rows.iterrows()),
        key=lambda row: sum(1 for y in older_years if row[y] != ""),
    )
    for recent_year in year_labels[:3]:  # FY2025, FY2024, FY2023
        assert subscription[recent_year] == "", (
            f"this Subscription row should be blank for {recent_year} (a different concept/era's row), "
            f"got {subscription[recent_year]!r}"
        )
    for older_year in older_years:
        value = _to_number(subscription[older_year])
        # Figures are reported in $ millions (per the statement's own "$
        # in Millions" header) -- 1000 here means $1B.
        assert value is not None and value > 1000, (
            f"Subscription should show a real, revenue-scale figure for {older_year}, got {subscription[older_year]!r}"
        )

    # The top-level Revenue total must stay correct across every year,
    # including the years where breakdown rows also exist alongside it.
    revenue_rows = merged.loc[merged.index == "Revenue"]
    total_row = max(
        (row for _, row in revenue_rows.iterrows()),
        key=lambda row: sum(v for v in (_to_number(row[y]) for y in year_labels) if v is not None),
    )
    for year in year_labels:
        value = _to_number(total_row[year])
        # Same $-millions units as above -- 10000 here means $10B.
        assert value is not None and value > 10000, (
            f"Adobe's top-level Revenue for {year} should be a multi-billion-dollar figure, got {total_row[year]!r}"
        )

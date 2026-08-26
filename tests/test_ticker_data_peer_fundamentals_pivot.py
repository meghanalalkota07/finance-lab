import pandas as pd

from ticker_data import build_peer_fundamentals_pivot

CIK_BY_TICKER = {"AAPL": "0000320193", "MSFT": "0000789019", "FAILCO": "0000000099"}

FAKE_SNAPSHOTS = {
    "AAPL": {
        "market_cap": 3_000_000_000_000.0, "trailing_pe": 30.5, "forward_pe": 28.0,
        "eps_ttm": 6.08, "dividend_yield": 0.5, "sector": "Technology",
        "industry": "Consumer Electronics", "fifty_two_week_high": 250.0, "fifty_two_week_low": 164.0,
    },
    "MSFT": {
        "market_cap": 2_500_000_000_000.0, "trailing_pe": 32.0, "forward_pe": 30.0,
        "eps_ttm": 11.8, "dividend_yield": 0.7, "sector": "Technology",
        "industry": "Software", "fifty_two_week_high": 470.0, "fifty_two_week_low": 380.0,
    },
}

FAKE_EDGAR_HISTORY = {
    CIK_BY_TICKER["AAPL"]: pd.DataFrame(
        [{"FiscalYear": 2024, "Revenue": 391_035_000_000.0, "NetIncome": 93_736_000_000.0,
          "EPS": 6.08, "MarketCap": 3_000_000_000_000.0, "TrailingPE": 30.5}]
    ).set_index("FiscalYear"),
    CIK_BY_TICKER["MSFT"]: pd.DataFrame(
        [{"FiscalYear": 2024, "Revenue": 245_122_000_000.0, "NetIncome": 88_136_000_000.0,
          "EPS": 11.8, "MarketCap": 2_500_000_000_000.0, "TrailingPE": 32.0}]
    ).set_index("FiscalYear"),
}


def fake_snapshot(ticker):
    if ticker == "FAILCO":
        raise RuntimeError("boom")
    return FAKE_SNAPSHOTS[ticker]


def fake_history(cik, price_history):
    if cik not in FAKE_EDGAR_HISTORY:
        raise RuntimeError("boom")
    return FAKE_EDGAR_HISTORY[cik]


def _price_history():
    return pd.DataFrame({"AdjClose": [100.0, 101.0]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))


def test_one_column_per_peer_priority_prefers_yfinance_over_edgar(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_peer_fundamentals_pivot(
        ["AAPL", "MSFT"], CIK_BY_TICKER,
        {"AAPL": _price_history(), "MSFT": _price_history()},
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )

    assert list(pivot.columns) == ["AAPL", "MSFT"]
    # Market cap is reported by both yfinance and SEC EDGAR for AAPL --
    # yfinance should win per the fixed priority order.
    assert pivot.loc["Market cap", "AAPL"] == "$3.00T"
    assert pivot.loc["Market cap", "MSFT"] == "$2.50T"


def test_falls_back_to_a_lower_priority_source_when_yfinance_lacks_the_metric(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_peer_fundamentals_pivot(
        ["AAPL"], CIK_BY_TICKER, {"AAPL": _price_history()},
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )

    # yfinance doesn't report Revenue at all -- SEC EDGAR's value should
    # surface instead of the placeholder.
    assert pivot.loc["Revenue", "AAPL"] == "$391.04B"


def test_metric_with_no_source_coverage_shows_placeholder(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_peer_fundamentals_pivot(
        ["AAPL"], {"AAPL": None}, {"AAPL": _price_history()},
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )
    # No CIK -> no SEC EDGAR column at all for this ticker; yfinance doesn't
    # report Revenue either.
    assert pivot.loc["Revenue", "AAPL"] == "—"


def test_one_peers_total_failure_does_not_blank_other_peers_columns(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_peer_fundamentals_pivot(
        ["AAPL", "FAILCO"], CIK_BY_TICKER,
        {"AAPL": _price_history(), "FAILCO": _price_history()},
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )

    assert list(pivot.columns) == ["AAPL", "FAILCO"]
    assert pivot.loc["Market cap", "AAPL"] == "$3.00T"
    assert (pivot["FAILCO"] == "—").all()


def test_missing_price_history_for_a_peer_does_not_crash(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_peer_fundamentals_pivot(
        ["AAPL"], CIK_BY_TICKER, {},  # AAPL's own historicals fetch failed upstream
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )
    # yfinance-sourced fields still populate even without a price history.
    assert pivot.loc["Sector", "AAPL"] == "Technology"

import pandas as pd

from ticker_data import build_fundamentals_pivot


def fake_snapshot(ticker):
    return {
        "market_cap": 3_000_000_000_000.0,
        "trailing_pe": 30.5,
        "forward_pe": 28.2,
        "eps_ttm": 6.08,
        "dividend_yield": 0.51,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "fifty_two_week_high": 250.0,
        "fifty_two_week_low": 164.0,
    }


def fake_history(cik, price_history):
    return pd.DataFrame(
        [
            {
                "FiscalYear": 2023, "Revenue": 383_285_000_000.0, "NetIncome": 96_995_000_000.0,
                "EPS": 6.13, "MarketCap": 2_900_000_000_000.0, "TrailingPE": 29.0,
            },
            {
                "FiscalYear": 2024, "Revenue": 391_035_000_000.0, "NetIncome": 93_736_000_000.0,
                "EPS": 6.08, "MarketCap": 3_000_000_000_000.0, "TrailingPE": 30.5,
            },
        ]
    ).set_index("FiscalYear")


def empty_history(cik, price_history):
    columns = ["Revenue", "NetIncome", "EPS", "DividendsPerShare", "SharesOutstanding", "MarketCap", "TrailingPE"]
    return pd.DataFrame(columns=columns, index=pd.Index([], name="FiscalYear"))


def failing_fetch(*args, **kwargs):
    raise RuntimeError("boom")


def test_yfinance_and_edgar_columns_only_by_default(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )

    assert list(pivot.columns) == ["yfinance", "SEC EDGAR"]
    assert pivot.loc["Market cap", "yfinance"] == "$3.00T"
    assert pivot.loc["Revenue", "SEC EDGAR"] == "$391.04B"
    assert pivot.loc["Net income", "SEC EDGAR"] == "$93.74B"
    # yfinance doesn't report the EDGAR-only fields; EDGAR doesn't report
    # sector -- both show the placeholder, not blank or zero.
    assert pivot.loc["Revenue", "yfinance"] == "—"
    assert pivot.loc["Sector", "SEC EDGAR"] == "—"


def test_one_source_failing_does_not_blank_the_others(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=failing_fetch, fetch_history=fake_history,
    )

    assert list(pivot.columns) == ["SEC EDGAR"]
    assert pivot.loc["Trailing P/E", "SEC EDGAR"] == "30.5×"


def test_no_cik_omits_edgar_column(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", None, pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
    )

    assert list(pivot.columns) == ["yfinance"]


def test_empty_edgar_history_omits_edgar_column(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=empty_history,
    )

    assert list(pivot.columns) == ["yfinance"]


def test_finnhub_and_alpha_vantage_columns_added_when_keys_present(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "key")
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "key")

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
        fetch_finnhub=lambda ticker: {"trailing_pe": 31.0},
        fetch_alpha_vantage=lambda ticker: {"trailing_pe": 29.5},
    )

    assert list(pivot.columns) == ["yfinance", "SEC EDGAR", "Finnhub", "Alpha Vantage"]
    assert pivot.loc["Trailing P/E", "Finnhub"] == "31.0×"
    assert pivot.loc["Trailing P/E", "Alpha Vantage"] == "29.5×"


def test_missing_api_keys_silently_omit_those_columns(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
        fetch_finnhub=failing_fetch, fetch_alpha_vantage=failing_fetch,
    )

    assert list(pivot.columns) == ["yfinance", "SEC EDGAR"]


def test_finnhub_failure_does_not_affect_other_columns(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "key")
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
        fetch_finnhub=failing_fetch,
    )

    assert "Finnhub" not in pivot.columns
    assert list(pivot.columns) == ["yfinance", "SEC EDGAR"]


def test_cells_are_formatted_human_readable_per_metric_type(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    def noisy_snapshot(ticker):
        row = fake_snapshot(ticker)
        row["dividend_yield"] = 0.0034 * 100  # binary-float noise: 0.33999999999999997
        row["fifty_two_week_high"] = 250.0
        row["eps_ttm"] = 6.08
        return row

    pivot = build_fundamentals_pivot(
        "AAPL", None, pd.DataFrame(),
        fetch_snapshot=noisy_snapshot, fetch_history=fake_history,
    )

    # .2f formatting collapses binary-float noise (0.33999999999999997) as
    # a side effect of formatting for display, not via a separate rounding step.
    assert pivot.loc["Dividend yield (%)", "yfinance"] == "0.34%"
    assert pivot.loc["EPS", "yfinance"] == "$6.08"
    assert pivot.loc["52-week high", "yfinance"] == "$250.00"
    assert pivot.loc["Sector", "yfinance"] == "Technology"


def test_alpha_vantage_failure_does_not_affect_other_columns(monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "key")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    pivot = build_fundamentals_pivot(
        "AAPL", "0000320193", pd.DataFrame(),
        fetch_snapshot=fake_snapshot, fetch_history=fake_history,
        fetch_alpha_vantage=failing_fetch,
    )

    assert "Alpha Vantage" not in pivot.columns
    assert list(pivot.columns) == ["yfinance", "SEC EDGAR"]

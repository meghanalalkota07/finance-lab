from unittest.mock import MagicMock, patch

from ticker_data import get_fundamentals_snapshot

FULL_INFO = {
    "marketCap": 3_000_000_000_000,
    "trailingPE": 30.5,
    "forwardPE": 28.2,
    "trailingEps": 6.1,
    "dividendYield": 0.51,
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "fiftyTwoWeekHigh": 250.0,
    "fiftyTwoWeekLow": 164.0,
}


@patch("ticker_data.yf.Ticker")
def test_extracts_all_fields(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.info = FULL_INFO
    mock_ticker_cls.return_value = mock_ticker

    snap = get_fundamentals_snapshot("AAPL")

    assert snap == {
        "market_cap": 3_000_000_000_000,
        "trailing_pe": 30.5,
        "forward_pe": 28.2,
        "eps_ttm": 6.1,
        "dividend_yield": 0.51,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "fifty_two_week_high": 250.0,
        "fifty_two_week_low": 164.0,
    }


@patch("ticker_data.yf.Ticker")
def test_missing_fields_become_none(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.info = {"sector": "Technology"}
    mock_ticker_cls.return_value = mock_ticker

    snap = get_fundamentals_snapshot("AAPL")

    assert snap["sector"] == "Technology"
    assert snap["market_cap"] is None
    assert snap["forward_pe"] is None

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ticker_data import get_historicals

# yfinance's own HTTP layer (curl_cffi browser impersonation + a
# cookie/crumb dance, per the map's research on ticker 01) is unstable
# enough that yfinance itself has broken and been re-patched across
# releases. Mocking at that raw HTTP layer would make these tests as
# fragile as the thing they're testing. Instead we mock at the
# yfinance.Ticker boundary -- our actual external dependency -- which
# still exercises all of get_historicals' own shaping logic.

RAW_YF_HISTORY = pd.DataFrame(
    {
        "Open": [100.0, 101.0],
        "High": [102.0, 103.0],
        "Low": [99.0, 100.0],
        "Close": [101.5, 102.5],
        "Adj Close": [101.0, 102.0],
        "Volume": [1_000_000, 1_200_000],
        "Dividends": [0.0, 0.24],
        "Stock Splits": [0.0, 0.0],
    },
    index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date"),
)


@patch("ticker_data.yf.Ticker")
def test_shapes_columns_and_index(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = RAW_YF_HISTORY
    mock_ticker_cls.return_value = mock_ticker

    df = get_historicals("AAPL", date(2024, 1, 1), date(2024, 1, 4))

    assert list(df.columns) == ["Open", "High", "Low", "Close", "AdjClose", "Volume", "Dividends", "StockSplits"]
    assert df.index.name == "Date"
    assert df.loc["2024-01-03", "AdjClose"] == 102.0
    assert df.loc["2024-01-03", "Dividends"] == 0.24


@patch("ticker_data.yf.Ticker")
def test_passes_date_range_to_yfinance(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = RAW_YF_HISTORY
    mock_ticker_cls.return_value = mock_ticker

    get_historicals("AAPL", date(2024, 1, 1), date(2024, 1, 4))

    _, kwargs = mock_ticker.history.call_args
    assert kwargs["start"] == date(2024, 1, 1)
    assert kwargs["end"] == date(2024, 1, 4)
    assert kwargs["auto_adjust"] is False


@patch("ticker_data.yf.Ticker")
def test_strips_timezone_from_index(mock_ticker_cls):
    # yfinance returns a tz-aware index (localized to the exchange's
    # timezone). EDGAR's dates are plain, tz-naive dates -- comparing the
    # two later (see get_fundamentals_history's price lookups) raises
    # TypeError unless this is normalized here.
    tz_aware = RAW_YF_HISTORY.copy()
    tz_aware.index = tz_aware.index.tz_localize("America/New_York")
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = tz_aware
    mock_ticker_cls.return_value = mock_ticker

    df = get_historicals("AAPL", date(2024, 1, 1), date(2024, 1, 4))

    assert df.index.tz is None


@patch("ticker_data.yf.Ticker")
def test_raises_on_empty_history(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    with pytest.raises(ValueError, match="AAPL"):
        get_historicals("AAPL", date(2024, 1, 1), date(2024, 1, 4))

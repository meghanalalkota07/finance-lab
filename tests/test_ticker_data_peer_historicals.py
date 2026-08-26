from datetime import date

import pandas as pd

from ticker_data import get_multi_ticker_historicals

START, END = date(2024, 1, 1), date(2024, 1, 31)


def _frame(close: float) -> pd.DataFrame:
    return pd.DataFrame({"AdjClose": [close, close + 1]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))


def test_fetches_each_ticker():
    frames = {"AAPL": _frame(100.0), "MSFT": _frame(200.0)}

    def fake_fetch(ticker, start, end):
        assert (start, end) == (START, END)
        return frames[ticker]

    result = get_multi_ticker_historicals(["AAPL", "MSFT"], START, END, fetch_historicals=fake_fetch)
    assert set(result) == {"AAPL", "MSFT"}
    pd.testing.assert_frame_equal(result["AAPL"], frames["AAPL"])


def test_omits_a_failing_ticker_without_failing_the_batch(caplog):
    def fake_fetch(ticker, start, end):
        if ticker == "BADTICKER":
            raise ValueError(f"No historicals data returned for {ticker!r}")
        return _frame(50.0)

    result = get_multi_ticker_historicals(["AAPL", "BADTICKER", "MSFT"], START, END, fetch_historicals=fake_fetch)
    assert set(result) == {"AAPL", "MSFT"}
    assert any("BADTICKER" in record.message for record in caplog.records)


def test_empty_ticker_list_returns_empty_dict():
    assert get_multi_ticker_historicals([], START, END, fetch_historicals=lambda t, s, e: _frame(1.0)) == {}

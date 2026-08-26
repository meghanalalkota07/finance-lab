import numpy as np
import pandas as pd

from ticker_data import build_peer_price_frame


def _history(dates: list[str], closes: list[float]) -> pd.DataFrame:
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes, "AdjClose": closes, "Volume": [0] * len(closes)},
        index=idx,
    )


def test_combines_tickers_with_matching_dates_into_wide_frame():
    histories = {
        "AAPL": _history(["2024-01-02", "2024-01-03"], [100.0, 101.0]),
        "MSFT": _history(["2024-01-02", "2024-01-03"], [200.0, 202.0]),
    }
    frame = build_peer_price_frame(histories)
    assert list(frame.columns) == ["AAPL", "MSFT"]
    assert frame.loc["2024-01-02", "AAPL"] == 100.0
    assert frame.loc["2024-01-03", "MSFT"] == 202.0


def test_uneven_histories_leave_nan_before_a_peers_first_date_without_truncating_others():
    histories = {
        "OLD": _history(["2024-01-02", "2024-01-03", "2024-01-04"], [10.0, 11.0, 12.0]),
        "NEW": _history(["2024-01-04"], [50.0]),
    }
    frame = build_peer_price_frame(histories)
    # OLD's full range is preserved, not truncated down to NEW's single date.
    assert list(frame.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert np.isnan(frame.loc["2024-01-02", "NEW"])
    assert frame.loc["2024-01-04", "NEW"] == 50.0
    assert frame.loc["2024-01-02", "OLD"] == 10.0


def test_empty_histories_returns_empty_frame():
    frame = build_peer_price_frame({})
    assert frame.empty

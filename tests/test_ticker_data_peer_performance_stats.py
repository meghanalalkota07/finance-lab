import math

import pandas as pd
import pytest

from ticker_data import compute_peer_performance_stats


def test_known_answer_total_return_volatility_and_drawdown():
    # Prices chosen so daily returns are exactly +10%, -10%, +10%, -10%:
    # 100 -> 110 -> 99 -> 108.9 -> 98.01
    prices = pd.Series([100.0, 110.0, 99.0, 108.9, 98.01])
    frame = pd.DataFrame({"AAPL": prices})

    stats = compute_peer_performance_stats(frame)

    assert stats.loc["AAPL", "Total Return (%)"] == pytest.approx(-1.99, abs=1e-6)
    # sample std (ddof=1) of [0.1, -0.1, 0.1, -0.1] is sqrt(0.04/3); annualized *sqrt(252)*100
    expected_volatility = math.sqrt(0.04 / 3) * math.sqrt(252) * 100
    assert stats.loc["AAPL", "Volatility (%)"] == pytest.approx(expected_volatility, rel=1e-6)
    # trough at 98.01 against the running peak of 110: 98.01/110 - 1
    assert stats.loc["AAPL", "Max Drawdown (%)"] == pytest.approx((98.01 / 110 - 1) * 100, abs=1e-6)


def test_flat_series_has_zero_volatility_and_drawdown():
    frame = pd.DataFrame({"FLAT": [50.0, 50.0, 50.0]})
    stats = compute_peer_performance_stats(frame)
    assert stats.loc["FLAT", "Total Return (%)"] == pytest.approx(0.0)
    assert stats.loc["FLAT", "Volatility (%)"] == pytest.approx(0.0)
    assert stats.loc["FLAT", "Max Drawdown (%)"] == pytest.approx(0.0)


def test_insufficient_data_yields_placeholder_not_a_crash():
    frame = pd.DataFrame({"SHORT": [50.0, float("nan"), float("nan")]})
    stats = compute_peer_performance_stats(frame)
    assert math.isnan(stats.loc["SHORT", "Total Return (%)"])
    assert math.isnan(stats.loc["SHORT", "Volatility (%)"])
    assert math.isnan(stats.loc["SHORT", "Max Drawdown (%)"])


def test_multiple_peers_computed_independently():
    frame = pd.DataFrame({"AAPL": [100.0, 110.0], "FLAT": [50.0, 50.0]})
    stats = compute_peer_performance_stats(frame)
    assert set(stats.index) == {"AAPL", "FLAT"}
    assert stats.loc["AAPL", "Total Return (%)"] == pytest.approx(10.0)
    assert stats.loc["FLAT", "Total Return (%)"] == pytest.approx(0.0)

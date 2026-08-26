import pytest

from ticker_data import get_fundamentals_from_finnhub

FINNHUB_METRIC_URL = "https://finnhub.io/api/v1/stock/metric"


def test_shapes_response_to_pivot_keys(requests_mock, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    requests_mock.get(
        FINNHUB_METRIC_URL,
        json={
            "metric": {
                "marketCapitalization": 3_000_000.0,  # millions
                "peTTM": 30.5,
                "epsInclExtraItemsTTM": 6.08,
                "dividendYieldIndicatedAnnual": 0.51,
                "52WeekHigh": 250.0,
                "52WeekLow": 164.0,
            }
        },
    )

    result = get_fundamentals_from_finnhub("AAPL")

    assert result == {
        "market_cap": 3_000_000_000_000.0,
        "trailing_pe": 30.5,
        "eps": 6.08,
        "dividend_yield": 0.51,
        "fifty_two_week_high": 250.0,
        "fifty_two_week_low": 164.0,
    }
    assert requests_mock.last_request.qs["symbol"] == ["aapl"]
    assert requests_mock.last_request.qs["token"] == ["test-key"]


def test_missing_metrics_come_back_as_none(requests_mock, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    requests_mock.get(FINNHUB_METRIC_URL, json={"metric": {"peTTM": 30.5}})

    result = get_fundamentals_from_finnhub("AAPL")

    assert result["trailing_pe"] == 30.5
    assert result["market_cap"] is None
    assert result["dividend_yield"] is None


def test_raises_when_api_key_unset(monkeypatch, requests_mock):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        get_fundamentals_from_finnhub("AAPL")

    assert not requests_mock.request_history


def test_raises_on_http_error(requests_mock, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    requests_mock.get(FINNHUB_METRIC_URL, status_code=429)

    with pytest.raises(Exception):
        get_fundamentals_from_finnhub("AAPL")

import pytest

from ticker_data import get_fundamentals_from_alpha_vantage

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def test_shapes_overview_response(requests_mock, monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
    requests_mock.get(
        ALPHA_VANTAGE_URL,
        json={
            "Symbol": "AAPL",
            "MarketCapitalization": "3000000000000",
            "PERatio": "30.5",
            "ForwardPE": "28.2",
            "EPS": "6.08",
            "DividendYield": "0.0051",
            "Sector": "TECHNOLOGY",
            "Industry": "CONSUMER ELECTRONICS",
            "52WeekHigh": "250.0",
            "52WeekLow": "164.0",
            "RevenueTTM": "391035000000",
        },
    )

    result = get_fundamentals_from_alpha_vantage("AAPL")

    assert result == {
        "market_cap": 3_000_000_000_000.0,
        "trailing_pe": 30.5,
        "forward_pe": 28.2,
        "eps": 6.08,
        "dividend_yield": pytest.approx(0.51),
        "sector": "TECHNOLOGY",
        "industry": "CONSUMER ELECTRONICS",
        "fifty_two_week_high": 250.0,
        "fifty_two_week_low": 164.0,
        "revenue_fy": 391_035_000_000.0,
    }


def test_missing_fields_as_the_string_none(requests_mock, monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
    requests_mock.get(
        ALPHA_VANTAGE_URL,
        json={"Symbol": "XYZ", "ForwardPE": "None", "DividendYield": "None", "Sector": "None"},
    )

    result = get_fundamentals_from_alpha_vantage("XYZ")

    assert result["forward_pe"] is None
    assert result["dividend_yield"] is None
    assert result["sector"] is None


def test_raises_when_api_key_unset(monkeypatch, requests_mock):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        get_fundamentals_from_alpha_vantage("AAPL")

    assert not requests_mock.request_history


def test_raises_on_rate_limit_response(requests_mock, monkeypatch):
    # Alpha Vantage returns HTTP 200 with no "Symbol" key when rate-limited
    # or given a bad key.
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
    requests_mock.get(
        ALPHA_VANTAGE_URL,
        json={"Information": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."},
    )

    with pytest.raises(ValueError):
        get_fundamentals_from_alpha_vantage("AAPL")

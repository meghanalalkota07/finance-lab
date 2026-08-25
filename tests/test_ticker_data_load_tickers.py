import pytest
import requests

from ticker_data import load_company_tickers, COMPANY_TICKERS_URL

RAW_RESPONSE = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}


def test_parses_and_pads_cik(requests_mock):
    requests_mock.get(COMPANY_TICKERS_URL, json=RAW_RESPONSE)
    tickers = load_company_tickers()
    assert {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193"} in tickers
    assert {"ticker": "MSFT", "name": "Microsoft Corp", "cik": "0000789019"} in tickers


def test_sends_descriptive_user_agent(requests_mock):
    requests_mock.get(COMPANY_TICKERS_URL, json=RAW_RESPONSE)
    load_company_tickers()
    sent_headers = requests_mock.last_request.headers
    assert "User-Agent" in sent_headers
    assert sent_headers["User-Agent"] != ""


def test_raises_on_http_error(requests_mock):
    requests_mock.get(COMPANY_TICKERS_URL, status_code=403)
    with pytest.raises(requests.exceptions.HTTPError):
        load_company_tickers()

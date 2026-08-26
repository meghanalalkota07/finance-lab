import pytest
import requests

from ticker_data import SP500_CONSTITUENTS_URL, load_sp500_constituents

RAW_CSV = (
    "Symbol,Security,GICS Sector,GICS Sub-Industry,Headquarters Location,Date added,CIK,Founded\n"
    "AAPL,Apple Inc.,Information Technology,Technology Hardware Storage & Peripherals,"
    "\"Cupertino, California\",1982-11-30,320193,1976\n"
    "NVDA,NVIDIA Corp.,Information Technology,Semiconductors,"
    "\"Santa Clara, California\",2001-11-30,1045810,1993\n"
    "MMM,3M,Industrials,Industrial Conglomerates,"
    "\"Saint Paul, Minnesota\",1957-03-04,66740,1902\n"
)


def test_parses_and_pads_cik(requests_mock):
    requests_mock.get(SP500_CONSTITUENTS_URL, text=RAW_CSV)
    constituents = load_sp500_constituents()
    assert {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Information Technology",
        "sub_industry": "Technology Hardware Storage & Peripherals",
        "cik": "0000320193",
    } in constituents
    assert {
        "ticker": "MMM",
        "name": "3M",
        "sector": "Industrials",
        "sub_industry": "Industrial Conglomerates",
        "cik": "0000066740",
    } in constituents


def test_raises_on_http_error(requests_mock):
    requests_mock.get(SP500_CONSTITUENTS_URL, status_code=404)
    with pytest.raises(requests.exceptions.HTTPError):
        load_sp500_constituents()


def test_raises_on_malformed_csv(requests_mock):
    requests_mock.get(SP500_CONSTITUENTS_URL, text="not,a,valid,sp500,csv\nfoo,bar\n")
    with pytest.raises(Exception):
        load_sp500_constituents()

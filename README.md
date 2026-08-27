# Ticker Explorer

A Streamlit app for researching individual stocks and comparing them against
their sector peers, built on free, mostly keyless data sources (SEC EDGAR,
yfinance, and optionally Finnhub / Alpha Vantage).

## Tabs

- **Historicals** — daily price chart (line or candlestick) for a searched
  ticker over any date range, plus a current-snapshot Fundamentals table
  (market cap, P/E, EPS, dividend yield, sector/industry, 52-week range) and
  multi-year Revenue/Net Income/EPS trend sparklines, cross-checked across
  yfinance, SEC EDGAR, Finnhub, and Alpha Vantage where available.
- **Peer Analysis** — pick an S&P 500 sector and sub-industry, select up to 8
  peer companies, and compare their price performance on an interactive
  normalized-return or raw-price chart, with total return/volatility/max
  drawdown stats and a peer-by-peer Fundamentals comparison table. Automatically
  seeds from whichever ticker is searched on the Historicals tab.
- **Financial Statements** — a company's 10-K financials two ways:
  **Normalized** (curated line items across the Income Statement, Balance
  Sheet, and Cash Flow Statement, five years by default, expandable to full
  history) and **Exact** (the filing's own as-reported table, byte-faithful
  to what SEC EDGAR shows, with an option to browse the last 5 fiscal years
  side by side).

Every data table has CSV export via its own toolbar.

## Setup

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

Two Fundamentals cross-check sources (Finnhub, Alpha Vantage) need free API
keys. Create a `.env` file in the project root if you want them enabled —
without it, the app just omits those two columns:

```
FINNHUB_API_KEY=your-key-here
ALPHAVANTAGE_API_KEY=your-key-here
```

## Running

```bash
streamlit run app.py
```

## Testing

```bash
pytest
mypy .
```

## Project structure

- `app.py` — Streamlit UI, layout, and caching. Not unit-tested directly.
- `ticker_data.py` — the data-service layer: every external fetch (yfinance,
  SEC EDGAR, Finnhub, Alpha Vantage, S&P 500 constituents) as a pure,
  Streamlit-free function, unit-tested via `requests-mock`.
- `tests/` — the test suite for `ticker_data.py`.

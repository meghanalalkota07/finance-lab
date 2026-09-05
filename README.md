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
pip install -r requirements-dev.txt   # or requirements.txt to just run the app
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
pytest          # fast, offline unit suite (default -- excludes the e2e-marked tests below)
mypy .
```

A slower, network-dependent `e2e`-marked set is excluded by default (see
`pytest.ini`'s `-m "not e2e"`) and run explicitly:

```bash
pytest -m e2e
```

This covers two kinds of check the fast suite can't: `tests/e2e/` drives a
real browser against a locally-running instance of the app (needs
Chromium via Playwright) to catch UI-timing issues that don't exist when
calling a function directly; other `test_*` files marked `e2e` (alongside
their fast, offline siblings) hit live SEC EDGAR / yfinance to validate
data-layer parsing against real, current filings rather than fixtures
alone.

## Project structure

- `app.py` — Streamlit UI, layout, and caching. Not unit-tested directly,
  except for a handful of browser-driven `e2e` tests under `tests/e2e/`
  that check UI-timing behavior a direct function call can't exercise.
- `ticker_data.py` — the data-service layer: every external fetch (yfinance,
  SEC EDGAR, Finnhub, Alpha Vantage, S&P 500 constituents) as a pure,
  Streamlit-free function, unit-tested via `requests-mock`; a few `e2e`-marked
  tests also validate it live against real SEC EDGAR data.
- `tests/` — the test suite: fast, offline unit tests by default, plus the
  `e2e`-marked tests described above.

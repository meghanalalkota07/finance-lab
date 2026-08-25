# Finance Lab

A single-ticker financial data explorer: view historical price behavior and current company fundamentals, with charts and CSV export.

## Language

**Historicals**:
The daily price/volume time series for a single ticker over a user-selected date range: Open/High/Low/Close/Volume, adjusted close, and dividend/split events.
_Avoid_: Price history, OHLCV data (use "Historicals" as the umbrella term; OHLCV is fine as a field-set shorthand within it)

**Fundamentals**:
Company-level metrics for a single ticker: market cap, P/E (trailing and forward), EPS, dividend yield, sector/industry, 52-week high/low, and latest revenue/net income. Distinct from Historicals — it describes the company, not a price time series. A current snapshot by default; a subset (revenue, net income, EPS, dividends, shares outstanding, and the market cap/trailing P/E derived from them) also carries multi-year historical depth. Forward P/E, sector/industry, and 52-week hi/lo stay snapshot-only — no free source tracks their history over time.
_Avoid_: Company data, stats

**Ticker**:
The single stock symbol a user selects; both Historicals and Fundamentals are scoped to one ticker at a time in v1 (no multi-ticker comparison).

# 05: Add Finnhub as a pivot source

**What to build:** Finnhub's free-tier basic-financials data becomes a third column in the Fundamentals pivot table.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] A `get_fundamentals_from_finnhub(ticker)` function in `ticker_data.py` fetches Finnhub's free-tier basic-financials data and shapes it to the pivot table's metric rows
- [ ] Tests mock Finnhub's HTTP endpoint directly (not `ticker_data.py`'s own functions), matching the seam confirmed for this project
- [ ] Finnhub's values appear as a third column in the pivot table for the metrics it covers
- [ ] The Finnhub API key is read from the `FINNHUB_API_KEY` environment variable
- [ ] If `FINNHUB_API_KEY` is unset, the Finnhub column is silently omitted from the pivot table, not an error
- [ ] A Finnhub request failure (timeout, 401, 429) doesn't affect the yfinance or SEC EDGAR columns

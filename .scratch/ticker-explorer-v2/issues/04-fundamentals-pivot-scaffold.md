# 04: Reshape Fundamentals into a pivot table (yfinance + SEC EDGAR)

**What to build:** The Fundamentals section's current single-source ledger becomes a metric-by-source pivot table, using the two sources already integrated today (yfinance, SEC EDGAR). This establishes the scaffold that tickets 05 and 06 add new source columns to.

**Blocked by:** 03 (needs the full-width Fundamentals section to render into)

**Status:** ready-for-agent

- [ ] The Fundamentals section shows a table with one row per metric (market cap, trailing P/E, forward P/E, EPS, dividend yield, sector, industry, 52-week high, 52-week low, plus the EDGAR-derived historical fields) and one column per source
- [ ] yfinance and SEC EDGAR each populate their own column for the metrics they cover
- [ ] A metric a given source doesn't report shows "—", not a blank cell or zero
- [ ] A failure fetching one source doesn't prevent the other source's column from rendering (per-source failure isolation)
- [ ] The existing Trends charts (Revenue/Net Income/EPS, from ticket 02) still render alongside the pivot table
- [ ] The bank-revenue substitution decision from v1 (`RevenuesNetOfInterestExpense` for depository institutions) still applies specifically to the SEC-EDGAR column
- [ ] `build_fundamentals_pivot(ticker, cik, price_history)` in `ticker_data.py` is the function assembling this table, structured so tickets 05/06 can add a source by adding a column, not by restructuring this function

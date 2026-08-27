# 05: Normalized financials — Income Statement

**What to build:** The Normalized sub-tab's Income Statement table: curated line items as rows, fiscal years as columns, 5 years by default with a control to expand to the company's full available EDGAR history.

**Blocked by:** 01, 04

**Status:** ready-for-agent

- [ ] A new `get_normalized_10k_financials(cik, years=5, *, fetch=requests.get) -> dict[str, pd.DataFrame]` function (or an Income-Statement-scoped equivalent reused by tickets 06/07) in `ticker_data.py` fetches the same `companyfacts` endpoint `get_fundamentals_history` already uses, but derives the Income Statement line items using the tag-fallback chains from ticket 04: Revenue, Cost of Revenue, Gross Profit, Operating Expenses, Operating Income, Interest Expense, Pre-tax Income, Income Tax, Net Income, EPS Basic, EPS Diluted. Kept as a new function, not a modification of the existing `get_fundamentals_history`, so Historicals' and Peer Analysis's existing Fundamentals behavior can't regress.
- [ ] Output is shaped metric-rows × fiscal-year-columns (the opposite orientation from `get_fundamentals_history`'s existing fiscal-year-rows shape), matching how the Exact-as-filed tables and real 10-K statements naturally present.
- [ ] The Normalized sub-tab renders the Income Statement table with 5 fiscal years by default.
- [ ] A control lets the user expand the year range beyond 5, up to however many years of history the company's EDGAR `companyfacts` record actually has.
- [ ] A line item with no reliable tag for a given company (per ticket 04's findings, or an industry gap discovered here) shows the existing dash placeholder for that cell, not a blank or zero.
- [ ] A CSV download button is present for the Income Statement table.
- [ ] `get_normalized_10k_financials`'s Income Statement derivation is unit-tested via `requests-mock` against a fixture `companyfacts` payload, the same style `get_fundamentals_history`'s existing tests use — covering a normal multi-year response and at least one line item falling back to a secondary tag.

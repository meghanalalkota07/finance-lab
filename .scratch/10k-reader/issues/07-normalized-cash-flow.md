# 07: Normalized financials — Cash Flow Statement

**What to build:** The Normalized sub-tab's Cash Flow Statement table: curated line items as rows, fiscal years as columns, 5 years by default with the same year-range expansion control as the other two normalized tables.

**Blocked by:** 01, 04

**Status:** ready-for-agent

- [ ] Extends `get_normalized_10k_financials` (or its equivalent from ticket 05) to derive the Cash Flow line items using the tag-fallback chains from ticket 04: Operating Cash Flow, Capital Expenditures, Investing Cash Flow, Financing Cash Flow, Net Change in Cash.
- [ ] Same metric-rows × fiscal-year-columns orientation as the other two normalized tables.
- [ ] The Normalized sub-tab renders the Cash Flow Statement table with 5 fiscal years by default, using the same year-range expansion control introduced in ticket 05.
- [ ] A line item with no reliable tag for a given company shows the existing dash placeholder, not a blank or zero.
- [ ] A CSV download button is present for the Cash Flow Statement table.
- [ ] The Cash Flow derivation is unit-tested via `requests-mock` against a fixture `companyfacts` payload, covering a normal multi-year response and at least one line item falling back to a secondary tag.

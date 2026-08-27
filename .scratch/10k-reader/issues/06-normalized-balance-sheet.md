# 06: Normalized financials — Balance Sheet

**What to build:** The Normalized sub-tab's Balance Sheet table: curated line items as rows, fiscal years as columns, 5 years by default with the same year-range expansion control as the Income Statement table.

**Blocked by:** 01, 04

**Status:** ready-for-agent

- [ ] Extends `get_normalized_10k_financials` (or its equivalent from ticket 05) to derive the Balance Sheet line items using the tag-fallback chains from ticket 04: Cash & Equivalents, Total Current Assets, PP&E (net), Goodwill & Intangible Assets, Total Assets, Total Current Liabilities, Long-term Debt, Total Liabilities, Total Stockholders' Equity.
- [ ] Same metric-rows × fiscal-year-columns orientation as the Income Statement table.
- [ ] The Normalized sub-tab renders the Balance Sheet table with 5 fiscal years by default, using the same year-range expansion control introduced in ticket 05 (not a separate/duplicate control).
- [ ] A line item with no reliable tag for a given company shows the existing dash placeholder, not a blank or zero.
- [ ] A CSV download button is present for the Balance Sheet table.
- [ ] The Balance Sheet derivation is unit-tested via `requests-mock` against a fixture `companyfacts` payload, covering a normal multi-year response and at least one line item falling back to a secondary tag.

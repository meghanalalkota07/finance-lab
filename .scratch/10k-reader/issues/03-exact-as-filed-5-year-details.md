# 03: Exact as-filed — 5-year details expansion

**What to build:** A "details" control on the Exact sub-tab that expands the currently-selected statement type into up to 5 separate as-filed tables, one per fiscal year's own 10-K, shown side by side — not merged into one table, since a company can reword or restructure line items between years and forcing them into shared rows risks silently misaligning data.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A "details" action on the Exact sub-tab expands the view from the single most-recent-filing table (ticket 02) to up to 5 separate as-filed tables — one per fiscal year, using each fiscal year's own 10-K filing (via `list_10k_filings`) and that filing's own `map_filing_statements`/`fetch_as_filed_statement` for the currently-selected statement type.
- [ ] Each of the 5 tables is rendered independently, with its own filer-as-reported labels/order/subtotals — no attempt to merge rows across years by matching label text or any other heuristic.
- [ ] If the filer has fewer than 5 10-Ks on record (e.g. a recent IPO), the details view shows however many are actually available rather than erroring or padding with empty tables.
- [ ] A filing among the 5 that predates the `R.htm`/XBRL convention (or otherwise fails to resolve a statement) shows its own "not available for this filing" note in its slot, without preventing the other years' tables from rendering.
- [ ] Switching the statement-type picker (Income Statement / Balance Sheet / Cash Flow) while the details view is open re-fetches and re-renders all 5 years for the newly selected statement.
- [ ] Each of the up to 5 tables has its own CSV download button.
- [ ] A regression test or explicit note confirms one year's fetch failure doesn't blank out the other years' tables in the details view.

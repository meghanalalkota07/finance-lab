# 03: Split Historicals and Fundamentals into separate full-width sections

**What to build:** The page reflows from the v1 side-by-side hero + left-rail + right-column layout into two full-width stacked sections, Historicals then Fundamentals, so Fundamentals has room to become a pivot table in later tickets.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Historicals renders as its own full-width section: chart, date-range and chart-type controls, CSV download (and the ticket-01 preview table, if that ticket has already landed)
- [ ] Fundamentals renders as its own full-width section below Historicals, separated by a hairline rule, replacing the narrow left-rail layout
- [ ] The hero price line (ticker, last price, day change) still renders once at the top of the page, above both sections — it is a whole-page fact, not scoped to either section
- [ ] All existing v1 behavior still works unchanged in the new layout: transient-failure error states, and the EDGAR-no-match graceful degradation (snapshot shown, trends omitted, note shown)

# 01: Historicals CSV tabular preview

**What to build:** A table appears directly below the Historicals price chart showing the same rows the CSV download contains, so a user can inspect the data before deciding to download it.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A table renders directly below the Historicals price chart, showing Open/High/Low/Close/AdjClose/Volume/Dividends/StockSplits for the currently selected date range
- [ ] The on-page preview is sorted most-recent-date-first
- [ ] The downloaded CSV file's row order is unchanged from v1 (oldest-first) regardless of the preview's sort order — the two are allowed to differ in order, not in content
- [ ] Changing the date-range slider or chart-type toggle updates the chart and the preview table together

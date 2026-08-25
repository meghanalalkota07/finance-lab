# Ticker page layout prototype

Type: prototype
Status: resolved

## Question

What should the single-ticker Streamlit page actually look like? Resolve:

- Tabs vs. stacked panels for Historicals vs. Fundamentals
- Placement of the ticker search box (symbol or company name) and the Historicals date-range picker
- Chart controls: line/candlestick toggle
- Where the Historicals CSV download button sits
- How the Fundamentals snapshot fields and the EDGAR-derived historical time series are presented together on the page (e.g. metric tiles for the snapshot fields, a separate chart or table for the historical series)

## Answer

**Dashboard: hero + side-by-side.** No tabs — Historicals and Fundamentals share one screen, split by dominance rather than by tab:

- A one-line **hero** at the top: ticker, last price, and day change (color-coded, explicit +/- sign, no arrow glyphs) — the single most-glanced-at fact, given top billing above everything else.
- **Left rail** (narrow column): the Fundamentals current snapshot as plain label:value lines (no card/tile chrome), followed by small single-line sparkline trends (no fill/gradient under the line) for Revenue, Net Income, and EPS — the EDGAR-derived historical series shown as glanceable shape, not a full chart.
- **Right column** (dominant, ~2x the left rail's width): the Historicals chart — date-range picker and line/candlestick toggle directly above it, CSV download directly below it. This is the page's primary object; the layout should make that obvious at a glance.
- Ticker input sits at the very top, above the hero line, free-text as already decided (Q18 was answered as "search by ticker and name," resolved via SEC EDGAR's `company_tickers.json`, not a live autocomplete widget).

Two other directions were explored and rejected: a tabbed "Ledger" (financial-statement register, serif+monospace, warm paper background) and a tabbed "Terminal" (Bloomberg-style monospace-on-black). Both lost to the dashboard layout on the actual question asked — Historicals and Fundamentals visible together beats switching between them.

Full prototype (all three variants, runnable): [prototypes/03-ticker-page-layout-all-variants.py](../prototypes/03-ticker-page-layout-all-variants.py) — run `streamlit run` on it, `?variant=C` for the winner.

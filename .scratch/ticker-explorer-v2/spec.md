# Ticker Explorer v2: separated sections, multi-source Fundamentals, labeled trends

Status: ready-for-agent

Source: user request, synthesized directly (skipping the grilling session in progress). Builds on and revises [Ticker Explorer v1's spec](../ticker-explorer/spec.md) and its [map](../ticker-explorer/map.md) — two v1 decisions are explicitly reopened below, not silently overridden.

## Problem Statement

Four gaps in the shipped v1 app: the Historicals CSV can only be inspected by downloading it, there's no way to preview it on the page first. Fundamentals is squeezed into a narrow left rail beside the price chart, which caps how much it can show. Fundamentals comes from a single source (yfinance), so a user has no way to tell if a number looks off because the company is unusual or because that one provider is wrong. And the Trends charts (Revenue, Net Income, EPS) have no axis labels, so a user can see the shape of a trend but not read an actual value or year off it.

## Solution

Add an on-page tabular preview of the Historicals data beneath its chart. Split the page into two full-width stacked sections, Historicals then Fundamentals, instead of the current side-by-side rail-and-column layout. Pull Fundamentals from multiple free sources (yfinance, SEC EDGAR, Finnhub, Alpha Vantage) and show them side by side in a pivot table, one row per metric, one column per source, so a user can cross-check figures instead of trusting a single provider blind. Label the Trends chart axes, and fix the "NetIncome" display bug (a raw column name leaking into the UI) while touching that code.

## User Stories

1. As a user, I want to see a table of the exact daily rows behind the Historicals chart, directly on the page, so that I can check the data before deciding to download it.
2. As a user, I want that table to show the most recent days first, so that I don't have to scroll past years of old data to see what happened recently.
3. As a user, I want the downloaded CSV to keep its existing chronological (oldest-first) row order regardless of how the on-page preview is sorted, so that anything I've already built against that file doesn't break.
4. As a user, I want Historicals and Fundamentals to live in their own clearly separated, full-width sections, so that each has room to be dense without cramping the other.
5. As a user, I want Fundamentals to be pulled from more than one data source, so that I'm not relying on a single provider's numbers.
6. As a user, I want to see, for each Fundamentals metric, what value each source reports, so that I can spot when sources disagree and judge which to trust.
7. As a user, I want the pivot table to clearly mark when a source doesn't cover a given metric, so that I don't mistake "not available" for zero.
8. As a developer maintaining this app, I want a failure in one Fundamentals source to not blank out the whole pivot table, so that one flaky or rate-limited provider doesn't take down the rest.
9. As a developer setting this up, I want a clear one-time setup step for any new provider API keys this feature needs, so that I'm not surprised by a silently broken feature after pulling the latest code.
10. As a user, I want the app to keep working for Fundamentals even if not every provider's API key is configured, so that the pivot table shows whatever sources are actually available rather than failing outright.
11. As a user, I want the pivot table to stay legible as more sources get added, so that density doesn't turn into noise.
12. As a user, I want to see the fiscal year and the value's unit on the axes of the Revenue, Net Income, and EPS trend charts, so that I can read actual values off them, not just eyeball the shape.
13. As a user, I want "Net Income" to display with a space between the words, so that it reads as a label, not a variable name.
14. As a user, I want the existing multi-year trend sparklines to remain part of the Fundamentals section even though the current-value fields move into the new pivot table, so that I don't lose the trend view I already had.
15. As a user researching a bank or depository institution, I want the pivot table's SEC-EDGAR-sourced revenue row to still reflect the bank-appropriate figure established in v1 (net interest income plus noninterest income), not a raw tag that undercounts it, so that this fix isn't lost in the move to a pivot table.

## Implementation Decisions

- **Historicals CSV preview**: `st.dataframe()` showing the same data as the download, placed directly below the price chart, sorted most-recent-first. The downloaded CSV keeps the chart's existing chronological (oldest-first) order unchanged — only the on-screen preview is reversed, so the two intentionally differ in row order for readability, not in content.
- **Page structure**: replaces v1's side-by-side hero + left-rail + right-column Dashboard layout (see the v1 map's Prototype ticket) with two full-width stacked sections — Historicals first, a hairline rule, then Fundamentals. The hero price line stays above both, since it's a whole-page fact, not scoped to one section. **This reopens a v1 decision**: the rail-and-column layout was chosen specifically so Historicals and Fundamentals were visible together without scrolling. The reason to revise it now: a metric-by-source pivot table needs real width to stay legible, which a narrow rail structurally can't give it.
- **Multi-source Fundamentals**: extend `ticker_data.py` with `get_fundamentals_from_finnhub(ticker) -> dict` and `get_fundamentals_from_alpha_vantage(ticker) -> dict`, alongside the existing `get_fundamentals_snapshot` (yfinance) and `get_fundamentals_history` (SEC EDGAR, the only source of multi-year depth — unchanged). A new `build_fundamentals_pivot(ticker, cik, price_history) -> DataFrame` calls every source whose API key is configured, catches each source's failures independently, and assembles a DataFrame: one row per metric, one column per source that responded, `"—"` for a metric a given source doesn't report. **This reopens a v1 decision**: v1 deliberately dropped Finnhub once yfinance's own `.info` was found to cover the whole snapshot field set (map ticket, Q15), to avoid a third data source and its own key/rate-limit/failure mode. The reason to revise it now: the goal has changed from "cover every field" (which yfinance alone already did) to "let the user cross-check one source against another," which by definition needs more than one source.
- **API keys**: Finnhub and Alpha Vantage both require a free signup. Read from `FINNHUB_API_KEY` and `ALPHAVANTAGE_API_KEY` environment variables; a missing key means that source's column is silently omitted from the pivot table, not an error — consistent with v1's "plain degradation, no fallback" decision.
- **Alpha Vantage rate limit**: its free tier is 25 requests/day, 5/minute (per the original map's provider research) — cache its result at least 24 hours via `st.cache_data`, longer than the other snapshot sources, so repeat views of the same ticker don't burn the daily quota.
- **Bank-revenue handling stays source-scoped**: the v1 decision to substitute `RevenuesNetOfInterestExpense` for depository institutions applies only to the SEC-EDGAR-sourced row, since that's the only source whose tag selection we control. Finnhub/Alpha Vantage/yfinance report whatever their own API calls "revenue," which may not carry the same adjustment — the pivot table surfaces that as a visible cross-source disagreement rather than trying to silently normalize other providers' numbers.
- **Trends chart axes**: un-hide them (`xaxis_visible=True, yaxis_visible=True`), set `xaxis_title="Fiscal year"` and a per-metric `yaxis_title` ("USD" for Revenue/Net Income, "USD per share" for EPS).
- **Label leak fix**: introduce a display-label mapping (e.g. `{"Revenue": "Revenue", "NetIncome": "Net Income", "EPS": "EPS"}`) used everywhere `SPARKLINE_METRICS` values reach the UI, instead of using the raw DataFrame column name as the label directly.

## Testing Decisions

- Same seam as v1 (confirmed in the v1 spec): `get_fundamentals_from_finnhub` and `get_fundamentals_from_alpha_vantage` are pure fetch/shape functions, tested by mocking their HTTP endpoints directly (e.g. via `requests_mock`), not by mocking `ticker_data.py`'s own functions.
- `build_fundamentals_pivot` needs tests with each source independently failing (timeout, 401 from a missing/bad key, 429 rate-limit) to confirm the pivot degrades to whichever sources are left, rather than raising or blanking the whole table.
- The CSV-preview-vs-download ordering split (preview reversed, download unchanged) is easy to accidentally couple later — worth an explicit regression test once built.

## Out of Scope

- Any Fundamentals provider beyond yfinance, SEC EDGAR, Finnhub, and Alpha Vantage. These four are the free, already-evaluated candidates from the original map research (Twelve Data, Financial Modeling Prep, Polygon, etc. were considered and set aside there) — adding more providers is a future pass, not this one.
- Automatically reconciling disagreeing source values into one "best" figure. The pivot table surfaces disagreement; it doesn't resolve it.
- Historical (multi-year) pivot rows for Finnhub or Alpha Vantage. Both are current-snapshot-only sources — SEC EDGAR remains the only source of multi-year depth, unchanged from v1.

## Further Notes

- Two v1 decisions are explicitly reopened here, both called out above where they're revised: the rail-and-column page layout (v1 map, Prototype ticket), and the single-source-is-enough call on Fundamentals (v1 map, Q15). Neither is being silently overridden.
- Before this ships, someone needs to sign up for two free API keys (Finnhub, Alpha Vantage) and set `FINNHUB_API_KEY` / `ALPHAVANTAGE_API_KEY` — neither exists in this project yet.
- This spec was written directly from the user's request without a grilling/domain-modeling pass (per `/to-spec`'s "don't interview, synthesize" instruction), interrupting a grilling session that was already in progress on the same screenshot. If any of the calls above (pivot table shape, which four sources, stacked-vs-tabbed sections) don't match what was actually wanted, that's the most likely place to correct.

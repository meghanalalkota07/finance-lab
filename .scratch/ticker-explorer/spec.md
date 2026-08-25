# Ticker Explorer

Status: ready-for-agent

Source: [Ticker Explorer wayfinder map](map.md) — all decisions below were resolved through that map's tickets; see it for full rationale and evidence.

## Problem Statement

Someone researching a stock has to piece together its price history and its fundamentals from separate places — a charting site for the price, a filings site or a paid data terminal for the financials — and even then, "how has this actually performed and grown over the years" (not just "what is it worth right now") is hard to see in one place for free. They want to type in a ticker or company name and immediately see both how the price has moved and how the underlying business has grown, side by side, with the ability to pull the raw price data out as CSV for their own analysis.

## Solution

A single-page Streamlit app: type a ticker symbol or company name, and see a dashboard for that one company — a hero line with its current price and today's change, an interactive daily price/volume chart with a selectable date range and a CSV download, and a Fundamentals rail showing current company metrics (market cap, P/E, EPS, dividend yield, sector, 52-week range) alongside multi-year trend sparklines for the metrics that have real historical depth (revenue, net income, EPS, dividends, shares outstanding, and derived market cap/trailing P/E) — sourced for free by combining Yahoo Finance data with SEC EDGAR's public filings API.

## User Stories

1. As a user, I want to type a ticker symbol (e.g. "AAPL") into a single input and see that company's page, so that I can look up a stock I already know the symbol for.
2. As a user, I want to type a company name (e.g. "Apple") into the same input and have it resolve to the right ticker, so that I don't need to already know the symbol.
3. As a user, I want the page to default to a sensible ticker on first load (e.g. AAPL), so that I see a populated example immediately rather than a blank state.
4. As a user, I want to see the ticker's current price and today's percentage change prominently at the top of the page, so that I get the single most important fact at a glance.
5. As a user, I want the day's price change to be shown with an explicit + or − sign and a color, not color alone, so that the direction is unambiguous even on a grayscale screen or for a colorblind viewer.
6. As a user, I want an interactive daily price chart for the selected ticker, so that I can see how the price has moved over time.
7. As a user, I want to toggle the price chart between a line view and a candlestick view, so that I can choose the level of detail I want (trend vs. open/high/low/close per day).
8. As a user, I want to pick the date range for the price chart, so that I can zoom into a period I care about.
9. As a user, I want the price chart to default to a 5-year lookback on load, so that I see a meaningful amount of history without having to configure anything first.
10. As a user, I want to be able to extend the date range back to the full history available for that ticker, so that I'm not artificially capped at some shorter window.
11. As a user, I want the price chart to support zoom and pan and hover tooltips, so that I can inspect specific days without leaving the chart.
12. As a user, I want to download the exact daily price data behind the chart as a CSV, so that I can analyze it myself outside the app.
13. As a user, I want the downloaded CSV to include Open/High/Low/Close/Volume, adjusted close, and dividend/split events for the selected ticker and date range, so that the export is a complete, self-contained record of that period.
14. As a user, I want to see current fundamental metrics for the ticker — market cap, trailing and forward P/E, EPS, dividend yield, sector, industry, and 52-week high/low — so that I understand the company at a glance without leaving the page.
15. As a user, I want to see how a company's revenue has changed over many years, not just its current value, so that I can judge growth trends, not just a snapshot.
16. As a user, I want to see historical trends for net income, EPS, dividends per share, and shares outstanding as well as revenue, so that I can evaluate profitability and capital-structure changes over time, not just top-line growth.
17. As a user, I want to see a historical trend for market cap and trailing P/E, so that I can see how the market's valuation of the company has moved over time, not just where it stands today.
18. As a user, I want the Fundamentals trend data to go back as many years as are actually available for that company, so that I get the deepest free view possible rather than an artificially short window.
19. As a user, I want to understand that Fundamentals history is quarterly/annual, not daily, so that I don't mistake it for the same granularity as the price chart.
20. As a user, I want the Fundamentals section and the price chart visible on the same screen without switching tabs, so that I can relate a price move to the underlying financials without losing my place.
21. As a user, I want the price chart to be the visually dominant element on the page, so that the layout reflects that it's usually the primary thing I came to look at.
22. As a user, I want to see a clear, readable error message if I enter a ticker that doesn't exist or has no data, so that I understand why nothing loaded instead of seeing a blank page or a crash.
23. As a user, I want the app to keep working (with a clear error, not a crash) if the underlying price-data source is temporarily unavailable or rate-limited, so that a transient third-party outage doesn't make the whole app unusable.
24. As a user, I want to still see the current Fundamentals snapshot for a ticker even when the deeper historical trend data isn't available for it (e.g. a non-US ticker, an ETF, or a delisted company), so that a gap in one data source doesn't hide data I could otherwise see.
25. As a user, I want a clear indication (not a silent gap) when historical Fundamentals trends aren't available for the ticker I searched, so that I know the absence is expected, not a bug.
26. As a user researching a bank or other depository institution, I want its revenue figure to reflect what's conventionally reported as bank revenue (net interest income + noninterest income), not just its noninterest fee income, so that the number isn't misleadingly small.
27. As a developer maintaining this app, I want the price/fundamentals data-fetching logic isolated from the Streamlit rendering code, so that the data logic can be tested without needing to drive the UI.
28. As a developer maintaining this app, I want the SEC EDGAR XBRL tag-fallback logic (for revenue, net income, dividends, shares outstanding) centralized in one place with documented fallback order, so that the per-filer tag-drift issues already discovered don't need to be rediscovered by whoever extends this later.
29. As a user, I do not want to be offered comparison against a second ticker in this version, so that the page stays focused on one company at a time (out of scope for now, but worth the app not actively working against a future version supporting it).
30. As a user, I do not expect intraday price data (only daily bars) in this version, so that the app's scope is clear when I look for finer granularity and don't find it.

## Implementation Decisions

- **Stack**: Streamlit (single-page app), Plotly (`st.plotly_chart`) for both the price chart and the Fundamentals trend sparklines, `st.download_button` for the Historicals CSV.
- **Data-service module** (the confirmed testing seam): a module, e.g. `ticker_data.py`, exposing four functions the Streamlit page calls into and nothing else touches the external APIs directly:
  - `get_historicals(ticker, start, end) -> DataFrame` — daily OHLCV, adjusted close, and dividend/split events, via yfinance.
  - `get_fundamentals_snapshot(ticker) -> dict` — market cap, trailing P/E, forward P/E, EPS, dividend yield, sector, industry, 52-week high/low, via yfinance's `Ticker.info`.
  - `get_fundamentals_history(ticker) -> DataFrame` — revenue, net income, EPS, dividends/share, shares outstanding (and market cap/trailing P/E derived by combining shares/EPS with `get_historicals`' price series), via SEC EDGAR's XBRL `companyfacts` API.
  - `resolve_ticker(query) -> list[dict]` — resolves a symbol or company-name query against a cached copy of SEC EDGAR's `company_tickers.json`, fuzzy-matched locally (e.g. `rapidfuzz`); not `yfinance.Search` (rejected — see below).
- **SEC EDGAR tag-fallback chains**, evaluated **per fiscal period** (take the highest-priority tag with data for that specific period, not a single tag chosen once per company):
  - Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax` → `Revenues` → `SalesRevenueNet` → `RevenueFromContractWithCustomerIncludingAssessedTax`. Depository institutions (banks) need a separate path via `RevenuesNetOfInterestExpense`, since the generic chain captures only noninterest fee income for them (confirmed on Zions Bancorp: a 5-6x undercount).
  - Net income: `NetIncomeLoss` → `ProfitLoss`. Do not substitute `NetIncomeLossAvailableToCommonStockholdersBasic/Diluted` — that's a different (smaller, preferred-dividend-adjusted) figure.
  - EPS: `EarningsPerShareDiluted` / `EarningsPerShareBasic` — confirmed stable across sampled filers, no fallback needed.
  - Dividends per share: `CommonStockDividendsPerShareDeclared` → `CommonStockDividendsPerShareCashPaid` → last-resort sum of four quarterly 10-Q facts for a fiscal year with no annual figure under either tag.
  - Shares outstanding: `CommonStockSharesOutstanding` (period-end aligned) → `EntityCommonStockSharesOutstanding` (cover-page date; present for filers where the first tag is entirely absent) → `CommonStockSharesIssued` (gross, flag as approximate — not net of treasury shares).
  - Apply an outlier/zero-value check regardless of which tag is used (a known real case: a spurious zero-share entry in one filer's cover-page tag).
- **Ticker/name resolution**: cache SEC EDGAR's `company_tickers.json` (a single static file) client-side on app start; resolve free-text input against it with local fuzzy matching. `yfinance.Search` was evaluated and rejected as the primary resolver — its Yahoo bot-detection workaround has broken and been re-patched repeatedly across recent releases, and its fuzzy mode over-matches (mixes in options/ETF results ahead of the intended equity).
- **Input model**: free-text entry validated on submit (attempt resolution/fetch, show an error if it fails) — no live autocomplete/search-as-you-type in this version.
- **Page layout** — no tabs, one screen (see the map's Prototype ticket for the two rejected alternatives, a tabbed "Ledger" and a tabbed "Terminal" layout):
  - A hero line at the top: ticker, last price, day change (colored, explicit sign).
  - A left rail: the Fundamentals snapshot as plain label/value lines, followed by trend sparklines (line only, no area fill) for Revenue, Net Income, and EPS.
  - A dominant right column (roughly twice the width of the left rail): the Historicals price chart, with the date-range picker and line/candlestick toggle directly above it and the CSV download button directly below it.
- **Historicals CSV**: mirrors the plotted daily bars exactly (Open/High/Low/Close/Volume, adjusted close, dividend/split events) for the selected ticker and date range. There is no CSV export for the Fundamentals section in this version.
- **Date range**: defaults to a 5-year lookback on load; the user can widen it up to the ticker's full available history with no artificial cap.
- **EDGAR-no-match behavior**: when SEC EDGAR has no CIK/filing match for the entered ticker (non-US tickers, ETFs/funds, delisted companies) but yfinance's snapshot still returns data, show the Fundamentals snapshot as normal, omit the historical trend sparklines, and show a small explicit note that historical depth isn't available for this ticker — not a blocking error.
- **yfinance reliability**: yfinance is unofficial and can break or rate-limit without notice. This version handles that as a plain error state on the affected section ("data temporarily unavailable") with no automatic fallback data source.
- **Caching**: use Streamlit's `st.cache_data` for all four data-service calls (no external persistence/database in this version) — the EDGAR-derived historical series changes only on new filings and can be cached longer than the daily-refreshing snapshot/price data.
- **Forward P/E**: current snapshot only, sourced from yfinance. No free source tracks forward P/E (an analyst estimate, not a filed fact) historically, so it never appears in the Fundamentals trend section — this is a hard data-availability limit, not a scope choice.

## Testing Decisions

- Good tests here assert on the **shaped output of the data-service functions** (the DataFrame/dict each one returns), not on Streamlit rendering or internal HTTP call mechanics — Streamlit UI is a poor unit-test target, and the module boundary confirmed above is the seam.
- Mock at the HTTP boundary (the yfinance library's underlying requests, and SEC EDGAR's `data.sec.gov` / `company_tickers.json` endpoints) rather than mocking `ticker_data.py`'s own functions, so the tests exercise the real parsing/fallback logic against fixture responses.
- The EDGAR tag-fallback logic in `get_fundamentals_history` is the highest-value thing to test directly: the map's research already surfaced concrete, real fixtures worth encoding as regression cases — a filer with a multi-year gap in `NetIncomeLoss` requiring the `ProfitLoss` fallback (observed on Zions Bancorp), a filer that switches dividend tags mid-history (observed on Kohl's), a filer that never adopted the ASC-606 revenue tag at all (observed on AT&T), and a depository institution needing the `RevenuesNetOfInterestExpense` substitution (Zions Bancorp again).
- `resolve_ticker` should be tested against both exact-symbol and company-name-substring/fuzzy queries, including a query with no reasonable match, using a small fixture slice of `company_tickers.json` rather than the full live file.
- No prior art exists in this repo yet (it's a fresh project) — recommend `pytest` with a request-mocking library (e.g. `responses` or `requests-mock`) as the convention going forward, since no existing pattern is being overridden.

## Out of Scope

- Multi-ticker comparison or overlay charts (single ticker only)
- Intraday granularity (daily bars only, never intraday)
- Technical indicators (moving averages, RSI, etc.)
- Historical forward P/E or other analyst-estimate time series (no free source tracks these over time)
- An automatic fallback price-data source if yfinance becomes unavailable
- CSV download for the Fundamentals section
- Live autocomplete/search-as-you-type for the ticker input (free-text, validated on submit, instead)

## Further Notes

- All decisions above trace back to the [Ticker Explorer wayfinder map](map.md) and its three resolved tickets — consult those for the full evidence trail (e.g. exact per-filer XBRL figures behind the tag-fallback chains) if a decision here needs revisiting.
- The domain glossary for this feature ("Historicals", "Fundamentals", "Ticker") lives in [CONTEXT.md](../../CONTEXT.md) at the repo root.
- A runnable design prototype for the page layout (all three explored variants, including the two rejected ones) is archived at [prototypes/03-ticker-page-layout-all-variants.py](prototypes/03-ticker-page-layout-all-variants.py); the winning variant is `?variant=C`.
- yfinance's unofficial nature is a standing risk worth monitoring post-launch, not just a one-time caveat — its bot-detection workaround has broken and been re-patched multiple times across recent releases per the map's research.

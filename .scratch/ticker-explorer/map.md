# Ticker Explorer

## Destination

A feature spec for a Streamlit app's single-ticker page, covering two clearly divided sections — **Historicals** (interactive daily price/volume chart over a selectable date range, CSV export) and **Fundamentals** (current snapshot, extended with SEC-EDGAR-derived historical depth for a subset of fields) — detailed enough to hand off to an implementation session.

## Notes

- Domain glossary: see [CONTEXT.md](../../CONTEXT.md) at the repo root for "Historicals", "Fundamentals", "Ticker" definitions. Consult `domain-modeling` if new terms surface while resolving tickets.
- Stack: **Streamlit** app. **yfinance** supplies Historicals (daily OHLCV, adjusted close, dividends/splits) and the Fundamentals current snapshot (market cap, trailing/forward P/E, EPS, dividend yield, sector, industry, 52-week hi/lo). **SEC EDGAR's XBRL `companyfacts` API** (free, keyless, 10 req/sec) supplies Fundamentals' historical depth (revenue, net income, EPS, dividends per share, shares outstanding — multi-year, quarterly/annual only) plus the market cap/trailing-P-E derived by combining EDGAR shares/EPS with our own Historicals price series. **Ticker/company-name input resolves against SEC EDGAR's `company_tickers.json`** (cached client-side, fuzzy-matched locally), not `yfinance.Search` — see Decisions so far. **Plotly** (`st.plotly_chart`) renders charts; `st.download_button` handles Historicals CSV.
- Single ticker, single page, two sections, no tabs: hero price line, Fundamentals left rail, dominant Historicals chart on the right — see [Ticker page layout prototype](issues/03-ticker-page-layout-prototype.md).
- Historicals CSV mirrors the plotted daily bars exactly. No CSV for the Fundamentals section.
- Default Historicals view: 5-year lookback on load; user can pick any range back to the ticker's full available history.
- yfinance is unofficial and can break/rate-limit without notice — v1 handles this as a plain error state, no fallback data source.

## Decisions so far

- [EDGAR tag-fallback mapping](issues/02-edgar-tag-fallback-mapping.md): revenue needs a 4-tag chain plus a separate bank/depository path; net income and dividends turned out to have their own tag-drift gaps too (not just revenue); EPS is stable, no fallback needed; shares outstanding resolved to a 3-tag order with an outlier check.
- [yfinance ticker/company-name search](issues/01-yfinance-ticker-name-search.md): `yfinance.Search` works but is a reliability risk (its bot-detection workaround breaks and gets re-patched repeatedly) and needs fuzzy-mode tuning to avoid noise; resolve input against SEC EDGAR's `company_tickers.json` instead, cached client-side.
- [Ticker page layout prototype](issues/03-ticker-page-layout-prototype.md): no tabs — one screen, hero price line up top, Fundamentals as a compact left rail (plain label:value + sparkline trends), dominant Historicals chart on the right with its controls directly above/below it.

## Not yet specified

_(none — the last open item, EDGAR-no-match behavior, was resolved directly in the spec rather than as a separate ticket: see [spec.md](spec.md#implementation-decisions).)_

## Out of scope

- Multi-ticker comparison / overlay charts (single ticker only for v1)
- Intraday granularity (daily bars only)
- Technical indicators (moving averages, RSI, etc.)
- Historical forward P/E / analyst-estimate time series (no free source tracks this over time; current snapshot only)
- Automatic fallback price-data source if yfinance becomes unavailable
- CSV download for the Fundamentals section

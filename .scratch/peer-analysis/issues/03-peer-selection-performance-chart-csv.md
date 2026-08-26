# 03: Peer selection + performance chart + CSV downloads

**What to build:** The core end-to-end Peer Analysis experience: select up to 8 companies from the chosen sector/sub-industry, pick a date range, and see an interactive multi-line chart comparing their price performance (normalized % return by default, toggleable to raw price), with both a plotted-series CSV and a full raw-OHLCV CSV downloadable.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A multiselect lets the user choose companies from the currently-picked sector/sub-industry group (ticker + company name shown), capped at 8 selections.
- [ ] Changing the Sector or Sub-Industry selection resets the peer multiselect to that new group's top 5 companies by market cap, pre-checked (market cap fetched per candidate via the existing `get_fundamentals_snapshot`).
- [ ] New `get_multi_ticker_historicals(tickers, start, end, *, fetch_historicals=get_historicals) -> dict[str, pd.DataFrame]` calls the existing `get_historicals` once per selected ticker; a per-ticker failure is caught, logged, and that ticker is simply omitted from the result rather than failing the whole call.
- [ ] The Peer Analysis tab shows a note listing any selected peers that couldn't be loaded (diffing requested tickers against the returned dict's keys), without blocking the rest of the view from rendering.
- [ ] New `build_peer_price_frame(histories) -> pd.DataFrame` (pure, no I/O) reshapes the per-ticker histories into a wide DataFrame indexed by Date, one column per ticker holding `AdjClose`. Peers with shorter histories have `NaN`/absent rows before their first available date; other peers' ranges are not truncated to match.
- [ ] Date-range controls reuse the existing Historicals pattern (quick presets + custom `st.date_input`), scoped to Peer Analysis's own widget keys. The usable minimum date is the *earliest* available date across all selected peers (as far back as any peer's data goes), not the latest-listed peer's start.
- [ ] The main chart is a multi-trace Plotly line chart, one line per selected peer, defaulting to normalized % return (each peer's series rebased to its own first available value within the selected range — not a single shared start date across all peers). A toggle switches the same chart to raw (unnormalized) price for the same peers/range.
- [ ] The chart uses `hovermode="x unified"`, Plotly's default legend click-to-toggle, and `rangeslider_visible=True`.
- [ ] The chart reuses the existing Aurora theme constants (`AURORA`, `CHART_FONT`) for visual consistency with the Historicals tab.
- [ ] A download button exports the currently-displayed chart series (whichever of normalized-% or raw-price is active) as CSV, one column per peer, one row per date.
- [ ] A second download button exports full raw OHLCV for every selected peer as CSV in long format (one row per ticker+date).
- [ ] `get_multi_ticker_historicals` is unit-tested by injecting a fake `fetch_historicals` that succeeds for some tickers and raises for others, asserting the failing ticker is omitted and logged rather than the whole call raising.
- [ ] `build_peer_price_frame` is unit-tested directly against small hand-built DataFrames covering both even histories and uneven/staggered start dates — no mocking needed.
- [ ] A regression test confirms uneven peer histories render as "later-starting lines," not a chart truncated to the shortest history.

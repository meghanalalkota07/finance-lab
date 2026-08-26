# 05: Peer fundamentals comparison table

**What to build:** A fundamentals comparison table in the Peer Analysis tab, one row per metric and one column per selected peer, cross-checked across the same four sources (yfinance, SEC EDGAR, Finnhub, Alpha Vantage) the single-ticker Fundamentals section already uses.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] New `build_peer_fundamentals_pivot(tickers, cik_by_ticker, histories, *, fetch_snapshot=get_fundamentals_snapshot, fetch_history=get_fundamentals_history, fetch_finnhub=get_fundamentals_from_finnhub, fetch_alpha_vantage=get_fundamentals_from_alpha_vantage) -> pd.DataFrame` calls the existing `build_fundamentals_pivot` once per peer ticker (passing that ticker's own entry from `histories`), then collapses each ticker's metric×source row to a single value per metric by trying sources in priority order — yfinance, then SEC EDGAR, then Finnhub, then Alpha Vantage — taking the first non-placeholder value found.
- [ ] Output has one row per `_PIVOT_METRICS` entry (reusing that existing list and its labels) and one column per selected peer ticker.
- [ ] A metric with no source coverage for a given peer shows the same placeholder (`"—"`) the existing single-ticker pivot table uses, not a blank cell or zero.
- [ ] One peer's total fetch failure (e.g. an invalid ticker or a total outage across all four sources for that ticker) does not blank out other peers' columns.
- [ ] Alpha Vantage's existing 25-requests/day cap is not specially rationed or reserved for this table — it's shared app-wide including with the Historicals tab's own Fundamentals section, and is allowed to silently drop out for the rest of the day once exhausted, consistent with the app's existing degrade-without-fallback philosophy.
- [ ] The table renders in the Peer Analysis tab using the app's existing pivot-table styling conventions (or a straightforward `st.dataframe`, implementer's choice, as long as the placeholder-for-missing-data behavior is preserved).
- [ ] `build_peer_fundamentals_pivot` is unit-tested by injecting fake `fetch_snapshot`/`fetch_history`/`fetch_finnhub`/`fetch_alpha_vantage`, in the same pattern `build_fundamentals_pivot`'s existing tests use, covering: (a) the priority-order fallback picks the right source when more than one has a value for the same metric, (b) a metric with no source coverage for a peer renders the placeholder, and (c) one ticker's total fetch failure doesn't blank out other peers' columns.

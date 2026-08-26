# 02: Sector/sub-industry picker over S&P 500 data

**What to build:** A new `load_sp500_constituents()` data function plus a dependent Sector → Sub-Industry picker in the Peer Analysis tab that lists the matching companies. No peer selection, chart, or downstream feature yet — this ticket's job is "pick a group, see who's in it."

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `load_sp500_constituents()` fetches and parses the `datasets/s-and-p-500-companies` GitHub raw CSV into a list of `{"ticker", "name", "sector", "sub_industry", "cik"}` dicts, with `cik` zero-padded to 10 digits (matching `load_company_tickers`'s existing convention).
- [ ] The fetch is wrapped in `st.cache_data` in `app.py` at roughly the same TTL as `load_company_tickers` (24h), following the existing caching block's pattern.
- [ ] A fetch failure degrades the same way the existing ticker-directory failure does today: a plain error message, no fallback data source.
- [ ] The Peer Analysis tab shows a Sector dropdown listing all 11 GICS sectors present in the data.
- [ ] Choosing a sector shows a Sub-Industry dropdown scoped to that sector's own sub-industries, plus an "All" option that keeps the group at the whole sector.
- [ ] The chosen group's constituent companies (ticker + name) are visibly listed on the page (a simple list/table is enough for this ticket — the actual multiselect for building a peer set is the next ticket).
- [ ] `load_sp500_constituents` is unit-tested via `requests-mock` against the GitHub raw CSV URL, covering both a normal response and a malformed/unreachable one, in the same style as `load_company_tickers`'s existing tests.

# 04: Peer performance stats table

**What to build:** A summary stats table beneath the Peer Analysis chart showing total return %, volatility %, and max drawdown % for each selected peer over the currently-selected date range.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] New `compute_peer_performance_stats(price_frame: pd.DataFrame) -> pd.DataFrame` (pure, no I/O) takes the wide price frame already restricted to the user's selected date range and returns one row per ticker with columns Total Return (%), Volatility (%, annualized standard deviation of daily returns), and Max Drawdown (%, peak-to-trough decline within the range).
- [ ] The table renders beneath the chart in the Peer Analysis tab, styled consistently with the app's existing table conventions.
- [ ] A peer with insufficient data in the selected range (e.g. fewer than 2 data points) shows a clear placeholder for the affected stat(s) rather than a crash or a misleading number.
- [ ] `compute_peer_performance_stats` is unit-tested directly against small hand-built DataFrames — no mocking needed — including at least one known-answer case (e.g. a simple monotonic series with a hand-computed expected drawdown).

# 06: Historicals → Peer Analysis pre-seeding

**What to build:** When a user switches to the Peer Analysis tab, it should start pre-seeded from whatever ticker is currently searched in Historicals — its sector/sub-industry pre-selected and the ticker itself pre-checked as a peer — when that ticker is an S&P 500 member. Also covers the tab's own default state before any search or manual pick has happened.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] On first render of the Peer Analysis tab in a session, if the currently-searched Historicals ticker is present in `load_sp500_constituents()`'s result, its sector and sub-industry are pre-selected and it is included among the (up to 5) initially-checked peers.
- [ ] If the currently-searched ticker is not present in the S&P 500 list, Peer Analysis falls back to its own independent default (Technology sector, top 5 by market cap pre-checked) with no attempt at fuzzy or sector-text matching.
- [ ] Before any ticker has been searched in Historicals at all (e.g. very first load of the app), Peer Analysis shows the same independent default (Technology sector, top 5 pre-checked).
- [ ] Manually changing the sector/sub-industry or peer selection in Peer Analysis after the initial seed behaves exactly as it does today (ticket 03's reset-to-top-5-on-group-change behavior) — pre-seeding only affects the tab's very first render per session, not every re-render.
- [ ] A test or manual verification confirms both branches: a searched ticker that is an S&P 500 member seeds correctly, and one that isn't falls back cleanly without error.

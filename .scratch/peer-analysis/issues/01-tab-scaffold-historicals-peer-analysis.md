# 01: Tab scaffold — split into Historicals / Peer Analysis

**What to build:** Restructure the app's single page into two tabs, "Historicals" and "Peer Analysis," with all existing content moved into the first tab unchanged and the second tab present but empty (a placeholder is fine — its content is built out by later tickets). This is pure prefactoring: no new data, no new visuals, no behavior change to what already exists.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The app renders two tabs labeled "Historicals" and "Peer Analysis."
- [ ] Everything that renders today (ticker search bar, hero price line, Historicals section, Fundamentals section) still renders exactly as it does now, inside the "Historicals" tab.
- [ ] The ticker search bar and its sticky positioning remain global chrome above the tabs (not scoped inside the Historicals tab), since a later ticket needs Peer Analysis to read the currently-searched ticker.
- [ ] Switching to the "Peer Analysis" tab shows a placeholder (e.g. "Coming soon") with no errors.
- [ ] Existing tests continue to pass unmodified; no test currently covering Historicals/Fundamentals behavior needs to change.

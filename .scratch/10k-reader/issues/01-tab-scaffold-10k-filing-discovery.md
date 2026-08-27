# 01: Tab scaffold + 10-K filing discovery

**What to build:** A third tab, "10-K Reader," alongside the existing "Historicals" and "Peer Analysis" tabs, driven by the same globally-searched ticker/CIK. It has two empty sub-tabs ("Normalized" and "Exact") for now, plus the filing-discovery data function that later tickets build on. This ticket's job is "does this ticker have 10-Ks, and if so what are the last few," not rendering any statement yet.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A new `list_10k_filings(cik, *, fetch=requests.get) -> list[dict]` function in `ticker_data.py` fetches `https://data.sec.gov/submissions/CIK{cik}.json`, filters `filings.recent` to `form == "10-K"`, and returns the most recent 5 as `{"accession_number", "primary_document", "filing_date", "report_date"}` dicts, most-recent-first. Sends the same descriptive `User-Agent` header this app's other SEC EDGAR calls already send.
- [ ] An empty result (no 10-K in the filer's history) and a `cik` of `None` are both handled without raising.
- [ ] The app renders a "10-K Reader" tab (`st.tabs`) alongside Historicals and Peer Analysis, reading the same resolved ticker/CIK the other two tabs use.
- [ ] Inside the 10-K Reader tab, two empty sub-tabs are visible: "Normalized" and "Exact."
- [ ] If no ticker is currently resolved (empty search, or a ticker with no SEC CIK match) or the resolved ticker has no 10-K filings on record (ETF, foreign private issuer filing 20-F, etc.), the tab shows a plain "No 10-K found for this ticker" message instead of the sub-tabs — no crash, no traceback shown to the user.
- [ ] `list_10k_filings` is unit-tested via `requests-mock` against the submissions endpoint, covering: a normal multi-filing response, a filer with fewer than 5 10-Ks, a filer with zero 10-Ks (e.g. only 10-Q/8-K forms present), and an unreachable/error response.

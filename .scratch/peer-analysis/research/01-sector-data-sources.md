# Free sources for "companies in sector/industry X" + multi-ticker historicals — research findings

Feeds the Peer Analysis feature design (sector/industry picker → ticker multi-select → normalized-return overlay).

## Verdict

**Bundle a static, periodically-refreshed S&P 500 constituents file (GICS Sector/Sub-Industry columns) as the sector/industry → ticker-list source, and reuse this repo's existing yfinance daily-OHLCV path for the actual multi-ticker historicals once tickers are picked. Do not add FMP, Twelve Data, or Polygon/Massive as a new keyed dependency for this feature, and do not use `yf.Sector`/`yf.Industry`/`yf.EquityQuery`/`yf.screen` as the sector→constituent lookup.**

Key reasons:

- `yf.Sector`/`Industry`/`screen` technically work today (verified live, 2026-08-25) and do return sector/industry-scoped ticker data, but they hit the same family of undocumented Yahoo endpoints, protected the same way (`curl_cffi` Chrome-TLS impersonation), as `yfinance.Search` — already flagged in this repo's prior research (`.scratch/ticker-explorer/research/01-yfinance-ticker-name-search.md`) as "unofficial, can break/rate-limit without notice." A GitHub issue titled "Screener Is Broken" (a GET/POST mismatch that broke `size`/`offset`) and two separate changelog fixes for the same predefined-screen offset/size bug confirm this isn't hypothetical.
- Even when working, `Sector.top_companies`/`Industry.top_performing_companies` are capped at the **top 50** by market weight — not the full constituent list. Getting an exhaustive list requires driving the raw `EquityQuery` screener with manual pagination (Yahoo caps each page at 250 results; a live test for Technology+US returned `total: 2063`, i.e. ~9 pages needed).
- FMP, Twelve Data, and Polygon/Massive free tiers are real and keyless-friction-free (FMP needs no credit card), but each is a **new key + new rate limit + new failure mode** for a job a single static, already-maintained CSV solves for the S&P 500 case — which is very likely sufficient coverage for a 5–10-ticker peer-comparison feature. Polygon/Massive's free tier in particular (5 requests/minute) is impractical for any multi-ticker fetch pattern.
- The chosen static dataset already carries a `CIK` column, which slots directly into this project's existing SEC EDGAR companyfacts fetch with zero extra ticker→CIK resolution work.

---

## 1. yfinance — `Sector`, `Industry`, `EquityQuery`, `screen`

**Version context**: PyPI's current version is **1.6.0**, uploaded 2026-08-13 (`https://pypi.org/pypi/yfinance/json`, confirmed live, `total releases: 149`). This machine has an older `0.2.62` installed (a different environment than the earlier ticker-search research, which was also on 0.2.62) — consistent with this repo's existing note that installed environments lag current PyPI.

**API surface** — confirmed exported: `yf.Sector`, `yf.Industry`, `yf.EquityQuery`, `yf.FundQuery`, `yf.screen`, `yf.PREDEFINED_SCREENER_QUERIES` (checked via `dir(yf)` against the installed package; also present in the freshly-`pip install --target`-ed 1.6.0 tree at `/opt/anaconda3/lib/python3.12/site-packages/yfinance/{domain,screener}`).

Source read directly (`yfinance/domain/domain.py`, `sector.py`, `industry.py`, `screener/screener.py`, `screener/query.py`):

- `Sector(key)` / `Industry(key)` (`yfinance/domain/{sector,industry}.py`) both subclass `Domain` (`domain.py`) and hit:
  ```
  GET https://query1.finance.yahoo.com/v1/finance/sectors/{key}
  GET https://query1.finance.yahoo.com/v1/finance/industries/{key}
  ```
  `Domain._parse_top_companies` builds a DataFrame from the response's `topCompanies` field — **hardcoded to whatever Yahoo returns there**, no size parameter exposed. `Sector` additionally exposes `top_etfs`, `top_mutual_funds`, `industries` (child industries); `Industry` additionally exposes `top_performing_companies`, `top_growth_companies` — all separate curated Top-N lists, not one exhaustive constituent list.
- `EquityQuery`/`FundQuery` (`yfinance/screener/query.py`) are pure query-builder objects (`.to_dict()` produces a nested `{"operator":..., "operands":[...]}` JSON body); they validate field/value names against `EQUITY_SCREENER_EQ_MAP`/`EQUITY_SCREENER_FIELDS` in `const.py` but perform no network I/O themselves.
- `screen(query, offset, size, count, sortField, sortAsc, ...)` (`yfinance/screener/screener.py`) is the actual network call:
  ```
  GET  https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved   (string/predefined query)
  POST https://query1.finance.yahoo.com/v1/finance/screener                    (custom EquityQuery/FundQuery)
  ```
  The module does `import curl_cffi` directly at the top of `screener.py` and calls `curl_cffi.requests.exceptions.HTTPError` — i.e. it goes through the same TLS-impersonating HTTP client (`YfData`) as `Search`/`Lookup`, not a plain `requests` session. The docstring itself states: *"size: number of results to return. Default 100, maximum 250 (Yahoo)"* and the code raises `ValueError` above 250 — confirming Yahoo enforces a hard per-page cap.

**Live test results (2026-08-25, this session, yfinance 0.2.62)**:

```python
s = yf.Sector('technology')
s.overview['companies_count']   # -> 1088
s.top_companies.shape           # -> (50, 3)   <- capped at 50, sorted by market weight
s.top_companies.head(3)
#         name                    rating       market weight
# NVDA    NVIDIA Corporation      Strong Buy   0.187055
# AAPL    Apple Inc.              Buy          0.163821
# MSFT    Microsoft Corporation   Strong Buy   0.132253
s.industries.shape               # -> (12, 3)  <- child industries of the sector, not companies
```

```python
from yfinance import EquityQuery
q = EquityQuery('and', [EquityQuery('eq', ['sector','Technology']), EquityQuery('eq', ['region','us'])])
res = yf.screen(q, size=250, sortField='intradaymarketcap', sortAsc=False)
res['total']              # -> 2063   (Yahoo's count of all matching equities)
len(res['quotes'])        # -> 250    (one page; would need `offset` pagination for the rest)
```

Both calls completed in well under a second with no rate-limit error in this session — a live, single-call, single-session data point, not a durability guarantee.

**Reliability / fragility — same pattern as `Search`, verified via GitHub**:

- Changelog (`https://raw.githubusercontent.com/ranaroussi/yfinance/main/CHANGELOG.rst`), screener/sector-relevant entries: `Fix predefined screen offset #2440`, `Fix predefined screen size/count #2425`, `Improve Screener & docs #2207`, `Screener tweaks #2168`, `Screener #2066`, `fetch sector & industry #2058`, `Allow region scoping for Sector and Industry (closes #2601) #2803`, `Fix missing comma splitting two equity screener EPS fields #2867` — a steady stream of screener-specific bugfixes, not a one-time feature landing.
- **GitHub issue #2419, "Screener Is Broken"** (`https://github.com/ranaroussi/yfinance/issues/2419`): reported that `size`/`offset` stopped working because the library sent a GET where Yahoo's API now expected a POST — a concrete instance of Yahoo silently changing an undocumented endpoint's contract underneath yfinance.
- **GitHub issue #2601 / #2218**: `Sector`/`top_companies` assumed US-only market scope until patched (#2803); screener filtering by exchange was reported unreliable (results included exchanges the filter should have excluded).
- **Net assessment**: this is the same risk class as `Search` — an actively-patched wrapper around a non-public Yahoo endpoint, protected by browser-impersonation machinery that itself has broken and been re-patched repeatedly (per the prior ticker-search research's changelog citations: 0.2.32, 0.2.52, 0.2.58/59, 0.2.60, 1.2.1, 1.4.0, 1.5.2). Nothing here suggests the screener surface is any more stable than `Search` — if anything, the confirmed GET→POST breakage is a more severe failure mode (total outage of the feature, not degraded relevance).

**Verdict for this sub-question**: usable as a live, free "what's popular in this sector today" widget, not as the backbone of a feature the app depends on working every time.

---

## 2. Financial Modeling Prep (FMP) — free tier, 2025/2026

Checked live against `https://site.financialmodelingprep.com/developer/docs/pricing` (fetched 2026-08-25).

- **Free plan limits**: **250 API calls/day**, "End of Day Historical Data", "Profile and Reference Data", "150+ Endpoints", trailing-30-day bandwidth cap of **500MB** (vs 20GB/50GB/100GB/150GB on Starter/Premium/Build/Enterprise).
- **Credit card**: **not required.** Per FMP's own "Do You Need a Credit Card for Financial Modeling Prep?" page and sign-up how-to docs — account creation (email + password) is decoupled from billing; a free API key is issued immediately on email verification.
- **Stock screener endpoint**: exists and supports `sector`/`industry` string filters — confirmed from the live screener docs page's own example parameter list: `["sector","string","Technology"],["industry","string","Consumer Electronics"]`, alongside market-cap/beta/price filters. **Flagged as uncertain**: the page's navigation groups "Stock Screener" near a "Legacy" API section on FMP's docs site, and a direct fetch of `site.financialmodelingprep.com/developer/docs/stock-screener-api` returned HTTP 403 with a default user agent (succeeded with a browser UA) — I could not conclusively confirm from documentation alone whether this specific endpoint is free-tier-accessible or gated to a paid plan. Verify against a real free API key before depending on it.
- **Bulk/batch historical endpoint**: **confirmed not available on the free plan.** FMP's "Batch EOD Prices" / `batch-request-end-of-day-prices` endpoint (all tickers, one date, one call) is explicitly Professional/Enterprise-only per FMP's own docs page. The free tier's per-symbol historical-price endpoint still works, but a 5–10-ticker peer view means 5–10 separate calls against the 250/day cap — fine for occasional single-user use, not fine at any real traffic volume.

---

## 3. Twelve Data — free tier, 2025/2026

Checked live against `https://twelvedata.com/pricing` and `https://twelvedata.com/docs`.

- **Free "Basic" plan limits**: **8 API credits/minute, 800 credits/day** (consistent with Twelve Data's long-standing documented Basic-plan limits).
- **Symbol list / sector filter**: the `/stocks` endpoint (symbol list) is on the Basic plan at "1 credit per request," but its documented filters are **exchange, country, type, and identifier (symbol/FIGI/ISIN/CUSIP) only** — no `sector`/`industry` filter parameter was found. Getting sector/industry per symbol would require a separate per-symbol call (e.g. `/quote` or a statistics-type endpoint), burning one credit per candidate ticker — not independently verified further in this pass since the static-file recommendation makes it moot.
- **`/time_series` historical endpoint**: confirmed on the Basic plan, "1 credit per symbol" per request, `start_date`/`end_date` params, intervals from `1min` to `1month`. A 5–10-ticker overlay fetch = 5–10 credits, feasible within the 8/minute ceiling if paced, comfortably within 800/day for light use.

---

## 4. Polygon.io / Massive.com — free tier, 2025/2026

**Important, easy-to-miss finding**: `polygon.io/pricing` now returns an HTTP **301 redirect to `massive.com/pricing`** (confirmed live, 2026-08-25). This is a real company rebrand, not a broken link or acquisition rumor — confirmed via multiple independent sources: The National Law Review's press release repost (`natlawreview.com/press-releases/polygonio-now-massive`), Massive's own blog post "Polygon.io is Now Massive" (`massive.com/blog/polygon-is-now-massive`), and an FISD industry note — the rebrand took effect **2025-10-30**, with both domains kept live in parallel during a migration window and existing Polygon API keys/accounts continuing to work unchanged. Any reference to "Polygon.io" from before late 2025 should be read as now-Massive.

- **Free tier ("Stocks Basic", $0/month)**, confirmed live at `massive.com/pricing`: **5 API calls/minute**, 2 years of historical data, end-of-day only (no real-time or 15-minute-delayed data), "individual use" licensing only.
- **"All Tickers" reference endpoint** (`massive.com/docs/rest/stocks/tickers/all-tickers`): included on the free Stocks Basic plan, returns the full ticker universe (paginated, default 100/page, max 1000/page) — but **does not support filtering by SIC code as a query parameter** (documented filters: ticker, type, market, exchange, CUSIP, CIK). SIC code is only exposed as a field on the *per-ticker* detail/overview endpoint, so "all tickers in SIC code X" would mean pulling the whole universe and filtering client-side, or one detail call per candidate ticker.
- **"Daily Market Summary" (grouped-daily) endpoint**: also included on the free Stocks Basic plan, same 2-year/end-of-day constraints.
- **The obvious dealbreaker**: **5 calls/minute** on the free tier. This is severe enough on its own to explain — without needing to reconstruct the original reasoning — why `ticker-explorer-v2/spec.md`'s "Twelve Data, Financial Modeling Prep, Polygon, etc. were considered and set aside" note landed the way it did for the original single-ticker Fundamentals feature; the same ceiling applies at least as strongly here, since a peer-analysis view inherently wants several tickers' worth of data per page load.

---

## 5. Static/curated S&P 500 + GICS source

- **`datasets/s-and-p-500-companies`** (GitHub, raw CSV at `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv`): fetched live 2026-08-25, HTTP 200, columns **`Symbol, Security, GICS Sector, GICS Sub-Industry, Headquarters Location, Date added, CIK, Founded`**. Sample rows confirmed (MMM/Industrials/Industrial Conglomerates, ABT/Health Care/Health Care Equipment, etc.).
  - **Actively maintained**: GitHub API (`api.github.com/repos/datasets/s-and-p-500-companies`) shows `pushed_at: 2026-08-20` (5 days before today), `archived: false`, only 3 open issues — this is not an abandoned dataset.
  - **Bonus**: the `CIK` column maps directly onto this project's existing SEC EDGAR companyfacts fetch, so an S&P 500 name picked through this file needs no separate ticker→CIK resolution step for Fundamentals cross-checks.
- **Wikipedia's "List of S&P 500 companies"** (`en.wikipedia.org/wiki/List_of_S%26P_500_companies`) is the ultimate upstream source the GitHub dataset mirrors (confirmed live, HTTP 200). Scraping Wikipedia's HTML table directly is a viable fallback but more fragile (markup/table-structure changes over time) than consuming the dataset repo's already-parsed CSV — the CSV is the better integration point.
- **Explicit tradeoff**: a static file gives you exactly the **S&P 500** (~500 large/mid-cap US names), refreshed only as often as the dataset repo re-scrapes Wikipedia (index reconstitutions could lag by an unverified amount of time), versus a live screener (yfinance's unofficial one, or a keyed provider) which reaches the full listed-company universe with current constituent membership at the cost of a live, rate-limited, and in yfinance's case unofficial/fragile, network dependency. For a sector/industry picker feeding a 5–10-ticker peer comparison, S&P 500 coverage is very likely sufficient — every GICS sector has ample representation — and the reliability tradeoff strongly favors the static file.

---

## Recommendation

1. **Sector/industry → ticker list**: bundle/cache the `datasets/s-and-p-500-companies` CSV (fetch-and-cache with a periodic refresh, e.g. weekly, falling back to a locally committed snapshot if the live fetch fails — mirroring this repo's existing keyless-first, plain-degradation pattern). Group by `GICS Sector` for the top-level picker, `GICS Sub-Industry` for a finer industry picker.
2. **Multi-ticker historicals**: once tickers are selected, reuse the existing yfinance daily-OHLCV path already used for the Historicals section — no new provider needed for the price side of this feature.
3. **Do not add FMP, Twelve Data, or Massive/Polygon** as a new keyed dependency for this feature specifically. Each is legitimately free and low-friction to sign up for, but each adds its own key/rate-limit/failure surface for a problem the static file already solves for the S&P 500 case.
4. **Do not use `yf.Sector`/`Industry`/`EquityQuery`/`screen`** as the sector→constituent source. Confirmed live and functional today, but on the same unofficial, `curl_cffi`-dependent, repeatedly-repatched foundation as `yfinance.Search` — with the added wrinkle of a confirmed full-outage bug class (GET/POST endpoint-contract mismatch in issue #2419), and capped at Top-50 curated lists unless the raw paginated screener is driven manually.
5. **If S&P-500-only coverage later proves too narrow** (e.g. wanting small-caps or a truly "all listed companies" picker), the next-best free option is Twelve Data's Basic plan for a live symbol list cross-referenced against sector via per-symbol calls, paced within its 8-credit/minute budget — not FMP (bulk endpoint is paid-only) and not Massive/Polygon (5 calls/minute free-tier ceiling is prohibitive for any multi-ticker flow).

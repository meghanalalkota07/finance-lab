# yfinance ticker/company-name search — research findings

Ticket: `../issues/01-yfinance-ticker-name-search.md`

## Verdict

**`yfinance.Search` works and does resolve company names to tickers ("Apple" → AAPL), but it should not be the sole/primary lookup for the ticker-input box, and if used it needs `enable_fuzzy_query=True` plus post-filtering on `quoteType`.**

Key reasons:

- It's a thin wrapper around Yahoo's undocumented `/v1/finance/search` endpoint. Getting a response at all requires yfinance's cookie/crumb dance and a Chrome-TLS-impersonating HTTP client (`curl_cffi`) — hitting the endpoint directly with a plain HTTP client and a normal browser `User-Agent` string got an immediate **HTTP 429** in testing here (see §3). This is inherent fragility, not a testing artifact.
- Without `enable_fuzzy_query=True`, misspelled/typo'd names return **zero results** ("Microsft" → 0 quotes). With fuzzy on, results degrade in relevance — for "Gooogle" the top 5 results were derivative ETFs and even an **options contract**, with the actual GOOGL equity absent from the top 5 entirely. So fuzzy mode is necessary for typo tolerance but actively hurts precision and makes the "stocks only" filtering requirement more important, not less.
- Results mix EQUITY, ETF, CRYPTOCURRENCY, FUTURE, OPTION, MUTUALFUND in one flat list ranked by a Yahoo-internal `score` — filtering on `quoteType == "EQUITY"` is required if the box should resolve to a stock.
- yfinance's own changelog shows the cookie/crumb/rate-limit machinery has broken and been re-patched repeatedly across releases (see §3) — it is a moving target, consistent with the map.md's existing decision to treat yfinance breakage as a plain error state with no fallback for Historicals/Fundamentals.

**Recommendation:** Use **SEC EDGAR's `company_tickers.json`** (already used elsewhere in this project for Fundamentals, per `map.md`) as the primary source for the ticker-or-name input box: it's a single static ~800KB JSON file, free, keyless, no crumb/cookie/TLS games, and can be loaded once, cached, and searched client-side with any matching logic (including fuzzy matching) the app wants — no per-keystroke network dependency on a fragile third party. Reserve `yfinance.Search` (if used at all) as a secondary/enrichment source, not the box's core resolver. Details and trade-offs below.

---

## 1. Exact API surface

Source: installed package `yfinance==0.2.62`, file `yfinance/search.py` (read directly from `/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/yfinance/search.py`), confirmed exported in `yfinance/__init__.py` (`from .search import Search`, in `__all__`).

```python
class Search:
    def __init__(self, query, max_results=8, news_count=8, lists_count=8, include_cb=True,
                 include_nav_links=False, include_research=False, include_cultural_assets=False,
                 enable_fuzzy_query=False, recommended=8, session=None, proxy=_SENTINEL_,
                 timeout=30, raise_errors=True):
        ...
    def search(self) -> 'Search': ...   # called automatically by __init__

    @property
    def quotes(self) -> list: ...       # ticker/company matches — the relevant one
    @property
    def news(self) -> list: ...
    @property
    def lists(self) -> list: ...
    @property
    def research(self) -> list: ...
    @property
    def nav(self) -> list: ...
    @property
    def all(self) -> dict: ...          # {"quotes":..., "news":..., "lists":..., "research":..., "nav":...}
    @property
    def response(self) -> dict: ...     # raw, unfiltered Yahoo JSON response
```

It hits:

```
GET https://query2.finance.yahoo.com/v1/finance/search
params: q, quotesCount, enableFuzzyQuery, newsCount, quotesQueryId=tss_match_phrase_query,
        newsQueryId=news_cie_vespa, listsCount, enableCb, enableNavLinks,
        enableResearchReports, enableCulturalAssets, recommendedCount, (+ crumb, injected by data.py)
```

`self._quotes` is `[q for q in data.get("quotes", []) if "symbol" in q]` — i.e. yfinance itself already drops any quote-search hit lacking a symbol, but does **no other filtering**.

**Fields actually observed per quote** (live test output, see §2 for full dumps): `symbol`, `shortname`, `longname` (often `None` for non-primary listings), `exchange` (Yahoo's internal exchange code, e.g. `NMS`, `NYQ`, `PCX`, `CCC`, `BUE`, `FRA`, `SET` — not a standard MIC), `quoteType` (`EQUITY`, `ETF`, `CRYPTOCURRENCY`, `FUTURE`, `OPTION`, `MUTUALFUND`, ...), `typeDisp` (human label, e.g. "Equity", "Futures"), `score` (a Yahoo relevance score, unbounded float — top hit for an exact ticker match can be `16403000.0` vs `~20000` for tangential matches, so it's usable as a rough confidence signal but has no fixed scale), `index` (always `"quotes"` in this section).

There is also a separate, related class, `yfinance.Lookup` (`yfinance/lookup.py`), hitting a different endpoint:

```
GET https://query1.finance.yahoo.com/v1/finance/lookup
params: query, type, start, count, formatted=False, fetchPricingData=True, lang=en-US, region=US
```

`Lookup(query).stock` / `.etf` / `.get_stock(count)` etc. return a **pandas DataFrame indexed by symbol**, with `type` pre-selectable server-side (`LOOKUP_TYPES = ["all","equity","mutualfund","etf","index","future","currency","cryptocurrency"]`) — this is arguably a *better* fit than `Search` for "stocks only" since you can pass `type="equity"` and skip client-side filtering. It appears to be a straight prefix/name lookup rather than a fuzzy full-text search though; it wasn't the class named in the ticket, but worth knowing it exists as an alternative within yfinance itself if `Search`'s noisier fuzzy mode is a problem.

## 2. Match quality — tested empirically

Test environment: yfinance 0.2.62, live calls against Yahoo on 2026-08-24 (see raw output below, captured via `Bash`).

**Exact ticker (`"AAPL"`)** — resolves cleanly, top hit is the correct US equity with a dominant score:
```
AAPL   Apple Inc.                              EQUITY  score=16403000.0
AAPL19.BK  AAPL19_DR AAPL#YUANTA (Thai depositary receipt)  EQUITY  score=20004.0
AAPW   Roundhill AAPL WeeklyPay ETF            ETF     score=20004.0
AAPU   Direxion Daily AAPL Bull 2X ETF         ETF     score=20004.0
AAPLC.BA  Apple Inc CEDEAR                     EQUITY  score=20003.0
AAPLX-USD  Apple tokenized stock (xStock) USD  CRYPTOCURRENCY score=20002.0
```

**Exact company name (`"Apple"`)** — top hit correct, but several international listings/near-homonyms crowd the rest:
```
AAPL   Apple Inc.                        EQUITY  score=32806.0
APC.F  Apple Inc. (Frankfurt)            EQUITY  score=20012.0
APLE   Apple Hospitality REIT, Inc.      EQUITY  score=20012.0
APC.DE Apple Inc. (Xetra)                EQUITY  score=20012.0
D90.F  Apple International Co. Ltd.      EQUITY  score=20005.0
```

**Partial name, no typo (`"Appl"`)** — top hit still correct even without fuzzy mode (this is prefix/phrase matching, not a misspelling):
```
AAPL  Apple Inc.                    EQUITY  score=32806.0
AMAT  Applied Materials, Inc.       EQUITY  score=20793.0
AAOI  Applied Optoelectronics, Inc. EQUITY  score=20287.0
APLD  Applied Digital Corporation   EQUITY  score=20166.0
APP   Applovin Corporation          EQUITY  score=20077.0
```

**Misspelled (`"Microsft"`, `enable_fuzzy_query=False`, the default)** — **zero results**:
```
QUERY: Microsft
  num quotes: 0
```

**Same misspelling with `enable_fuzzy_query=True`** — now returns results, but MSFT is buried among noise:
```
MSFT  Microsoft Corporation           EQUITY  score=22566.0
ALGM  Allegro MicroSystems, Inc.      EQUITY  score=20021.0
MBOT  Microbot Medical Inc.           EQUITY  score=20017.0
GDXU  MicroSectors Gold Miners 3X Lev ETF  score=20009.0
BULZ  MicroSectors FANG & Innovation  ETF  score=20009.0
```

**Worse misspelling (`"Gooogle"`, fuzzy=True)** — the actual GOOGL equity does **not appear at all** in the top 5; results include an **options contract**:
```
GOGL   Corgi GOOGL 2x Daily ETF                    ETF     score=20008.0
GOOW   Roundhill GOOGL WeeklyPay ETF                ETF     score=20006.0
GOOGL261218C00345000  GOOGL Dec 2026 345.000 call   OPTION  score=20006.0
GGLL   Direxion Daily GOOGL Bull 2X ETF              ETF     score=20005.0
DEPW   Google DeepMind AI Lab Ecosystem ETF          ETF     score=20004.0
```

**Multi-word name (`"Berkshire Hathway"`, missing "a", fuzzy=True)** — correct top hit:
```
BRK-B  Berkshire Hathaway Inc. New   EQUITY  score=20866.0
BRK-A  Berkshire Hathaway Inc.       EQUITY  score=20152.0
```

**Bare ticker for a non-equity-heavy term (`"Bitcoin"`)** — as expected, dominated by non-equity types:
```
BTC-USD  Bitcoin USD              CRYPTOCURRENCY  score=36160.0
BCH-USD  Bitcoin Cash USD         CRYPTOCURRENCY  score=32009.6
MBT=F    Micro Bitcoin Futures    FUTURE          score=30001.0
BTC=F    Bitcoin Futures          FUTURE          score=30001.0
GBTC     Grayscale Bitcoin Trust  ETF             score=20104.0
```

**Conclusion:** Exact tickers and exact/near-exact company names resolve reliably. Real misspellings need `enable_fuzzy_query=True`, and turning that on trades recall for precision — it can surface derivative ETFs and even options contracts ahead of (or instead of) the actual equity. For a Streamlit ticker box, this means fuzzy mode is necessary for a good UX but the result list absolutely must be filtered/re-ranked (see §4), and even then correctness for typo'd multi-word names isn't guaranteed (Google case above).

## 3. Rate limits / reliability

**Direct evidence of fragility, gathered here:** a bare `curl` (no cookie, no crumb, standard browser `User-Agent`, no TLS impersonation) against the exact endpoint `yfinance.Search` uses returned an immediate rate-limit/bot-block:
```
$ curl -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ..." \
    "https://query2.finance.yahoo.com/v1/finance/search?q=Apple&quotesCount=5&newsCount=0"
Too Many Requests
HTTP_CODE:429
```
This confirms Yahoo is actively distinguishing "real browser" traffic from generic HTTP clients — it isn't just IP-based rate limiting. `yfinance` works around this specifically via:

- `curl_cffi` with `impersonate="chrome"` for the HTTP session (`yfinance/data.py:80`, `from curl_cffi import requests` at the top of the file) — this fakes TLS/HTTP2 fingerprints to look like a real Chrome browser, not just a `User-Agent` header swap.
- A cookie+crumb acquisition dance with **two fallback strategies** (`'basic'` via `https://fc.yahoo.com` + `/v1/test/getcrumb`, and `'csrf'` via `https://guce.yahoo.com/consent`), each of which is retried and the strategy is toggled if one fails (`data.py:346-366`).
- Explicit `YFRateLimitError` raised when Yahoo returns 429 either during crumb fetch or during the actual request (`data.py:226-228`, `334-336`, `420-421`; class defined in `yfinance/exceptions.py:51-53`: `"Too Many Requests. Rate limited. Try after a while."`).

**In this session's own testing**, 15 rapid, distinct-query calls to `yf.Search(...)` (different tickers each time, to defeat yfinance's internal `lru_cache` on identical params) completed in 2.2s with 0 rate-limit errors — so a moderate query rate worked fine right now, using yfinance's full cookie/crumb/curl_cffi machinery. That's a live, single-IP, single-session data point, not a guarantee at Streamlit-app-with-many-users scale.

**History of breakage, from the yfinance changelog** (`https://raw.githubusercontent.com/ranaroussi/yfinance/main/CHANGELOG.rst`; installed version here is 0.2.62, current PyPI/GitHub `main` is **1.6.0** — confirmed via `https://pypi.org/pypi/yfinance/json`, `total releases: 149`, latest `1.6.0`, so this environment is several releases behind current):

- `0.2.32`: "Add cookie & crumb to requests" — crumb/cookie auth wasn't originally needed; Yahoo started requiring it.
- `0.2.33`: "Cookie fixes: fix backup strategy" / "fix Ticker(ISIN)" — the fix itself needed fixing.
- `0.2.52`: "raise YfRateLimitError if rate limited" — rate-limit handling was added as a distinct feature, i.e. rate-limiting was common/severe enough to need a dedicated exception type.
- `0.2.53`: "Stop CSRF-cookie-fetch fail killing yfinance" — a broken cookie fetch was previously capable of crashing the whole library.
- `0.2.58`: "Fix false rate-limit problem" — then **`0.2.59`: "Fix the fix for rate-limit"** — two consecutive releases patching rate-limit false positives/regressions.
- `0.2.60`: "Fix cookie reuse, and handle DNS blocking fc.yahoo.com" — some networks/DNS blocklists block the cookie-fetch host outright (yfinance now catches `requests.exceptions.DNSError` around this, per `data.py:200-202`).
- `0.2.62` (installed version): "Detect rate-limit during crumb fetch" — even the *authentication* step can get rate-limited, not just the data call.
- `1.2.1`: "Force curl_cffi>=0.15, because CVE" and "Block curl_cffi version 0.14" — a security vulnerability in the impersonation library itself forced a version pin.
- `1.4.0`: "Make curl_cffi optional with fallback to requests" — suggests curl_cffi was itself a source of install/compat friction for some users.
- `1.5.1`: "Preserve user login cookies across cookie-strategy switches".
- `1.5.2`: "Fix yfinance breaking with curl_cffi>=0.16" — a newer curl_cffi release broke yfinance again.

**Search-specific GitHub issues** (via `https://github.com/ranaroussi/yfinance/issues`): the `Search` class itself is relatively young — first added per issue **#837** ("Add ticker symbol and news search", closed Jan 2023) and expanded in **#2160**/**#2191** ("Search", "add more options to Search", both landing in the `0.2.51`/`0.2.52` changelog entries). A concrete correctness bug was reported and closed-as-not-planned in **#2657**: "`yf.Search()` returns wrong symbol suffix `.SG` (Singapore) for Stuttgart exchange instruments" — an exchange-mapping bug in the search results that the maintainers didn't fix.

**Net assessment:** this is a real, actively-maintained wrapper around an endpoint Yahoo does not officially support for third parties, protected by TLS fingerprinting and bot-detection that yfinance works around with browser impersonation + a two-strategy cookie/crumb dance, and the changelog shows that dance has broken and been re-patched on a roughly semi-regular cadence for years. This matches the map.md's existing framing ("yfinance is unofficial and can break/rate-limit without notice — v1 handles this as a plain error state, no fallback data source") — the same caveat applies to `Search`, not just Historicals/Fundamentals.

## 4. Filtering needs

Confirmed empirically (see §2 dumps): a single `Search(...).quotes` call for a common word can return `EQUITY`, `ETF`, `CRYPTOCURRENCY`, `FUTURE`, and even `OPTION` results interleaved and ranked together by Yahoo's opaque `score`, not grouped by type. The field to filter on is **`quoteType`**, e.g. `[q for q in search.quotes if q.get("quoteType") == "EQUITY"]`. Observed `quoteType` / `typeDisp` values in testing: `EQUITY`/"Equity", `ETF`/"ETF", `CRYPTOCURRENCY`/"Cryptocurrency", `FUTURE`/"Futures", `OPTION`/(a specific option contract, e.g. `GOOGL261218C00345000`). `yfinance.Lookup` (§1) supports server-side type filtering instead (`type="equity"`), which avoids this problem entirely for a "stocks only" box, at the cost of (apparently) less typo tolerance than `Search`'s fuzzy mode — not verified empirically here since it wasn't the class named in the ticket, but worth a follow-up spike if `Search` is pursued further.

Note also that even after filtering to `quoteType == "EQUITY"`, results can include foreign listings/ADRs of the same company (Frankfurt/Xetra Apple listings, Thai depositary receipts, Buenos Aires CEDEARs) and unrelated equities that merely share a word (Apple Hospitality REIT for "Apple"). A ticker box aimed at US equities would likely also want to filter/prefer `exchange` values corresponding to US markets (`NMS`, `NYQ`, `NGM`, `PCX` were the US-market codes observed above) and/or prefer the highest `score` within the equity subset.

## 5. Fallback: SEC EDGAR `company_tickers.json`

Per `map.md`, SEC EDGAR is already the project's chosen source for Fundamentals' historical depth, so reusing it here avoids adding a second unofficial dependency.

**API surface** — a single static file, no query parameters, no auth, no rate-limit-sensitive per-query call:
```
GET https://www.sec.gov/files/company_tickers.json
GET https://www.sec.gov/files/company_tickers_exchange.json   (adds an `exchange` column)
```
Tested live in this session:
```
$ curl -H "User-Agent: finance-lab-2-research bhatia.shashwat@gmail.com" \
    https://www.sec.gov/files/company_tickers.json
HTTP 200, size=796148 bytes, 10403 entries
```
Shape of `company_tickers.json` (a dict keyed by arbitrary integer index, not by ticker):
```json
{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
```
Shape of `company_tickers_exchange.json` (tabular form):
```json
{"fields": ["cik", "name", "ticker", "exchange"],
 "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], ...]}
```
10,403 entries in both, confirmed identical row count. **No `quoteType`/security-type field in either file** — SEC-registered ETFs and trusts appear alongside operating companies with no way to distinguish them from the file alone (confirmed `SPY`, `QQQ`, and `GBTC` are all present, tested via `ticker in tickers` lookup) — so if "stocks only" filtering matters, this fallback is actually *weaker* than yfinance's `quoteType` field on that one specific dimension, and would need a supplementary equity/ETF classification source (e.g. cross-reference against yfinance `Ticker(...).info["quoteType"]` lazily, only for the user's final selection, not the whole list).

**Match quality** — tested empirically with naive Python substring matching over the loaded JSON (no external library, `q.lower() in title.lower() or q.lower() in ticker.lower()`):
```
"Apple"      -> AAPL Apple Inc.; APLE Apple Hospitality REIT; MLP Maui Land & Pineapple; PAPL Pineapple Financial; AAPI Apple iSports Group
"Appl"       -> AAPL Apple Inc.; AMAT Applied Materials; APP AppLovin; AIT Applied Industrial Tech; AAOI Applied Optoelectronics
"Berkshire"  -> BRK-B Berkshire Hathaway; BRK-A Berkshire Hathaway
"Tesla"      -> TSLA Tesla, Inc.
"AAPL"       -> AAPL Apple Inc.
"Microsft"   -> []   (no fuzzy tolerance out of the box — plain substring match)
```
So: correct exact-ticker and correct exact/partial-name matches work well with trivial client-side logic (results are notably *cleaner* than Yahoo's fuzzy search for "Apple"/"Appl" — no ETFs/crypto/futures mixed in, since the file only contains SEC-registered issuers). Typo tolerance (`"Microsft"`) requires adding real fuzzy matching (e.g. `difflib.get_close_matches`, `rapidfuzz`) on top — but because the whole 10k-row dataset is a static file loadable once and cached in-process, this is a one-time client-side decision, not something that has to survive an unreliable remote fuzzy-search API on every keystroke. This is the core structural advantage over yfinance's `Search`: match-quality tuning happens locally and deterministically instead of depending on Yahoo's undocumented relevance ranking.

**Rate limits / reliability** — SEC publishes a fair-access policy requiring a descriptive `User-Agent` (this is also the header the project's existing EDGAR-based Fundamentals fetch presumably already sets, per `map.md`'s "10 req/sec" note). Confirmed empirically in this session:
```
$ curl -A "" https://www.sec.gov/files/company_tickers.json      -> HTTP 403
$ curl -H "User-Agent: research-agent contact@example.com" \
       https://www.sec.gov/files/company_tickers.json            -> HTTP 200
```
No crumb, no cookie, no TLS impersonation needed — a blank/absent `User-Agent` is rejected but any descriptive one works. Because the ticker-name lookup only needs to fetch this file once (e.g. at app startup, refreshed daily/weekly) rather than per keystroke, the effective request rate against SEC is negligible — this sidesteps rate-limit risk almost entirely, in contrast to `yfinance.Search`, which is a live network call every time a user types a query (even with client-side debouncing).

**Filtering needs** — as noted above, this file has no security-type field, so "stocks only" isn't directly filterable from it; in practice this may not matter much since the file is already scoped to SEC-registered issuers (a narrower universe than Yahoo's global multi-asset search) and doesn't surface options/futures/crypto at all.

**Gaps relative to yfinance**: `company_tickers.json` only covers SEC filers, i.e. **US-listed securities with EDGAR filings** — no foreign-exchange-only listings, no pure-crypto, no futures. For this project's stated scope (map.md's "how Fundamentals behaves when SEC EDGAR has no CIK/filing match... non-US tickers, ETFs/funds, delisted companies" is already flagged as "not yet specified"), this is likely an acceptable and arguably *desirable* scope limitation for a ticker-input box feeding a workflow that already depends on EDGAR for Fundamentals — a ticker the box resolves is close to guaranteed to also have an EDGAR CIK, reducing the "no Fundamentals match" edge case rather than expanding it.

### Fallback recommendation

Use `company_tickers.json` (or `company_tickers_exchange.json` if the `exchange` column is useful for disambiguation/display) as the **primary** resolver for the ticker-input box:
1. Fetch once, cache (e.g. `st.cache_data` with a TTL of a day), load into memory (~10k rows, trivial).
2. Match user input against both `ticker` and `title`/`name` — exact match first, then substring/prefix, then fuzzy (e.g. `difflib.get_close_matches` or `rapidfuzz.process.extractOne`) for typo tolerance.
3. On the user's final selection, hand the resolved ticker symbol to `yfinance.Ticker(symbol)` for Historicals/Fundamentals as already planned — `yfinance.Search` doesn't need to be in the request path at all.

This keeps the box's live, per-keystroke behavior entirely independent of Yahoo's unofficial, historically fragile search endpoint, while still landing on exactly the ticker symbols yfinance needs downstream.

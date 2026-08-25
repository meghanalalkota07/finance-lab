# yfinance ticker/company-name search

Type: research
Status: resolved

## Question

The ticker input needs to accept both a ticker symbol and a company name (e.g. typing "Apple" should resolve to AAPL). Does `yfinance` support this via its `Search` feature (or equivalent), hitting Yahoo's search/autocomplete endpoint? Confirm:

- The exact API surface (class/method, e.g. `yfinance.Search(query).quotes`) and what it returns (symbol, name, exchange, security type)
- Whether it reliably matches on partial/misspelled company names, not just exact tickers
- Rate limits / reliability, given yfinance's unofficial nature
- Whether it needs filtering (e.g. excluding non-equity results like options/futures/crypto if only stocks are wanted)

If yfinance doesn't cover this adequately, identify a free, keyless fallback.

## Answer

`yfinance.Search` works (`Search(query).quotes`, wraps Yahoo's search endpoint) but shouldn't be the primary resolver: it needs `quoteType == "EQUITY"` filtering to drop ETF/crypto/options noise, true misspellings return zero results unless fuzzy mode is enabled, and fuzzy mode then over-matches (a "Gooogle" query ranked an options contract ahead of GOOGL). Its underlying bot-detection workaround (`curl_cffi` browser impersonation + cookie/crumb dance) has broken and been re-patched repeatedly across recent yfinance releases — a live reliability risk, not just a hypothetical one.

**Recommendation: resolve ticker/name input against SEC EDGAR's `company_tickers.json`** — a free, keyless, static ~800KB file (10,403 rows) we can cache client-side once, no cookie/crumb/TLS games (confirmed: blank `User-Agent` → 403, descriptive `User-Agent` → 200). Naive substring matching against it already beats Yahoo fuzzy search on cleanliness (no ETF/crypto mixed in for "Apple"); add a local fuzzy-match pass (`rapidfuzz`/`difflib`) for typo tolerance since the dataset is fully cached. One gap: no security-type field, so ETFs aren't distinguishable from equities within the file alone — acceptable for v1 since we're not trying to exclude them, just resolving name→symbol. The resolved symbol still goes to `yfinance.Ticker()` for the actual Historicals/Fundamentals pull as already planned; keep `yfinance.Search` out of the input path entirely.

Full detail: [research/01-yfinance-ticker-name-search.md](../research/01-yfinance-ticker-name-search.md)

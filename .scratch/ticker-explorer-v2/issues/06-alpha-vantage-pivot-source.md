# 06: Add Alpha Vantage as a pivot source

**What to build:** Alpha Vantage's free-tier OVERVIEW data becomes a fourth column in the Fundamentals pivot table, cached hard given its tight rate limit.

**Blocked by:** 04 (not 05 — can be worked in parallel with it)

**Status:** ready-for-agent

- [ ] A `get_fundamentals_from_alpha_vantage(ticker)` function in `ticker_data.py` fetches Alpha Vantage's free-tier `OVERVIEW` endpoint and shapes it to the pivot table's metric rows
- [ ] Tests mock Alpha Vantage's HTTP endpoint directly (not `ticker_data.py`'s own functions), matching the seam confirmed for this project
- [ ] Alpha Vantage's values appear as a fourth column in the pivot table for the metrics it covers
- [ ] The Alpha Vantage API key is read from the `ALPHAVANTAGE_API_KEY` environment variable
- [ ] If `ALPHAVANTAGE_API_KEY` is unset, the Alpha Vantage column is silently omitted, not an error
- [ ] Alpha Vantage's result is cached for at least 24 hours (`st.cache_data` ttl), given its 25-request/day free-tier limit
- [ ] An Alpha Vantage request failure (timeout, 401, 429) doesn't affect the other columns

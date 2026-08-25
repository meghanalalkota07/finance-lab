from ticker_data import resolve_ticker

FIXTURE_TICKERS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193"},
    {"ticker": "MSFT", "name": "Microsoft Corp", "cik": "0000789019"},
    {"ticker": "KSS", "name": "Kohl's Corp", "cik": "0000885639"},
    {"ticker": "T", "name": "AT&T Inc.", "cik": "0000732717"},
    {"ticker": "APLE", "name": "Apple Hospitality REIT, Inc.", "cik": "0001574596"},
]


def test_exact_ticker_match_ranks_first():
    results = resolve_ticker("AAPL", FIXTURE_TICKERS)
    assert results[0]["ticker"] == "AAPL"


def test_exact_company_name_match():
    results = resolve_ticker("Microsoft Corp", FIXTURE_TICKERS)
    assert results[0]["ticker"] == "MSFT"


def test_partial_name_prefix_resolves():
    results = resolve_ticker("Appl", FIXTURE_TICKERS)
    tickers = [r["ticker"] for r in results]
    assert "AAPL" in tickers


def test_exact_ticker_beats_partial_name_match_on_a_different_company():
    # "APLE" is a real ticker (Apple Hospitality REIT) and also fuzzy-close
    # to "Apple" the query -- an exact ticker match must win.
    results = resolve_ticker("APLE", FIXTURE_TICKERS)
    assert results[0]["ticker"] == "APLE"


def test_no_match_returns_empty_list():
    results = resolve_ticker("Zzyzxqqq Nonexistent Corp", FIXTURE_TICKERS)
    assert results == []


def test_garbage_query_does_not_match_a_real_ticker_it_happens_to_contain():
    # A real ticker appearing as a bare substring of an unrelated garbage
    # query must not resolve -- WRatio's partial-ratio component used to
    # score "notatickerxyz123" at 90 against the real ticker "XYZ".
    tickers_with_xyz = FIXTURE_TICKERS + [{"ticker": "XYZ", "name": "Block, Inc.", "cik": "0001512673"}]
    results = resolve_ticker("NOTATICKERXYZ123", tickers_with_xyz)
    assert results == []


def test_garbage_query_does_not_match_a_short_name_it_happens_to_contain():
    # Real bug found via live SEC data: "KE Holdings Inc." normalizes to
    # just "ke" (after suffix-stripping "Holdings" and "Inc"), which then
    # scores ~90 via WRatio against "NOTATICKERXYZ123" purely because "ke"
    # appears inside "notatiCKErxyz123" -- a length-ratio gate should
    # reject this the same way the ticker-side fix does.
    tickers = FIXTURE_TICKERS + [{"ticker": "BEKE", "name": "KE Holdings Inc.", "cik": "0001809587"}]
    results = resolve_ticker("NOTATICKERXYZ123", tickers)
    assert results == []


def test_respects_limit():
    results = resolve_ticker("A", FIXTURE_TICKERS, limit=2)
    assert len(results) <= 2


def test_case_insensitive():
    results = resolve_ticker("aapl", FIXTURE_TICKERS)
    assert results[0]["ticker"] == "AAPL"

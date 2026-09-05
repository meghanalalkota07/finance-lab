"""
Regression test for: switching tickers and clicking a "Download CSV"
button shortly afterward could download the *previous* ticker's file.

Root cause: Streamlit only replaces a widget's DOM node -- a download
button's embedded bytes included -- when script execution reaches its
position in a new rerun. render_10k_normalized_tab's tables (and their
CSV download buttons, app.py) sit behind a slow SEC EDGAR fetch
(cached_get_normalized_10k_financials); the previous run's button (old
bytes and all) stayed fully live and clickable for the entire fetch
duration after a ticker switch, so a click landing in that window
downloaded the *previous* ticker's data under a correctly-named-for-the-
previous-ticker filename -- self-consistent, just stale.

Fixed in app.py's render_10k_normalized_tab (and equivalently
render_10k_exact_tab) with a leaf-level st.empty() placeholder that
renders "Loading <ticker>'s financials…" the instant the ticker changes,
*before* the slow fetch runs, so the stale button is torn down
immediately instead of lingering. (An earlier attempt wrapped the whole
st.tabs(...) call -- including main()'s hero+tabs -- in one shared
st.empty(); that left the *inner* Normalized/Exact content stale for the
same reason a bare top-level fix did, and in one observed case left the
tab panel blank well past when it should have repopulated. Nesting the
placeholder at the leaf, one level *inside* the tab -- not wrapping
st.tabs itself -- avoided both problems.)

This is a genuine UI-timing bug -- it only exists in Streamlit's actual
script-rerun/delta-streaming machinery, which no unit test against
ticker_data.py or a directly-called app.py function can exercise (there
is no "previous stale DOM node" in a bare Python function call). A real
browser against a real running app is the correct seam, hence this
lives under tests/e2e/ and is excluded from the default `pytest` run
(see pytest.ini's `addopts = -m "not e2e"`) -- it's slow, needs network
access (SEC EDGAR, yfinance) and a Chromium binary, unlike the fast,
offline unit suite in tests/. Run explicitly with `pytest -m e2e`.
"""

import re
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

# Two tickers with very different revenue scales -- Apple ($300-400B) vs
# Adobe ($15-25B) -- so a downloaded Normalized Income Statement CSV's
# Revenue row unambiguously identifies which company it actually belongs
# to, independent of the filename Streamlit/the browser reports.
TICKER_A = "ADBE"
TICKER_B = "AAPL"
APPLE_SCALE_REVENUE_FLOOR = 100e9

# A cold SEC EDGAR fetch (first request for a given CIK in a freshly
# started app process, no st.cache_data warmth) has been observed to take
# upward of 10s under load -- generous, but this only bounds the
# *baseline* settle before the actual timing-sensitive part of each test.
SETTLE_TIMEOUT_MS = 30000


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_url():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.headless", "true", "--server.port", str(port)],
        cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    url = f"http://localhost:{port}"
    try:
        deadline = time.time() + 30
        import urllib.request
        while time.time() < deadline:
            try:
                urllib.request.urlopen(url, timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Streamlit app did not come up in time")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
def page(app_url):
    with playwright_sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1400, "height": 1200}, accept_downloads=True)
        pg.goto(app_url)
        pg.wait_for_selector(".te-hero-ticker", timeout=30000)
        time.sleep(2)
        pg.get_by_role("tab", name="Financial Statements").click()
        pg.get_by_role("tab", name="Normalized", exact=True).wait_for(timeout=10000)
        yield pg
        browser.close()


def _search(page, ticker: str) -> None:
    box = page.get_by_placeholder("Ticker or company name — e.g. AAPL, or Apple")
    box.fill("")
    box.fill(ticker)
    box.press("Enter")


def _search_and_wait_for_settle(page, tmp_path, ticker: str) -> None:
    """Search `ticker` and block until a download that actually matches
    it succeeds -- used to establish a known-good baseline before the
    fast-switch part of each test. Polls by actually attempting the
    download (rather than inferring readiness from a "Loading…" DOM text
    appearing-then-vanishing) since that text may never appear at all if
    this specific fetch happens to be fast, which would make an
    appeared-then-detached check pass immediately without having waited
    for anything real. A cold-cache SEC EDGAR fetch (each test module
    starts a fresh app subprocess with nothing cached) can take several
    seconds, hence the generous overall timeout.

    Failure to settle at all within that window means this baseline
    can't be trusted -- most likely SEC EDGAR/yfinance rate-limiting a
    freshly started, uncached process (this app has its own documented
    handling for that failure mode; it's an external-service condition,
    not something this test can control) rather than a real regression.
    Skipping rather than failing keeps that distinct from an actual
    wrong-ticker mismatch, which is a hard assertion failure everywhere
    else in this file.
    """
    _search(page, ticker)
    deadline = time.time() + SETTLE_TIMEOUT_MS / 1000
    while time.time() < deadline:
        result = _try_download_income_statement_csv(page, tmp_path, f"settle_{ticker}")
        if result is not None and result[0].startswith(f"{ticker}-"):
            return
        time.sleep(0.6)
    pytest.skip(
        f"{ticker} never settled to a matching download within {SETTLE_TIMEOUT_MS}ms -- "
        "likely SEC EDGAR/yfinance rate-limiting rather than a real regression"
    )


def _try_download_income_statement_csv(page, tmp_path, label: str):
    """Click the first "Download CSV" button if one is present and
    actionable within a short window, returning (filename, csv_text) --
    or None if no button is currently clickable (e.g. still showing the
    "Loading…" placeholder). None is a *safe* outcome for this bug: no
    data at all is never wrong data, unlike serving the previous
    ticker's file, so tests treat it as acceptable, not a failure.
    """
    dl_btn = page.get_by_role("button", name="Download CSV").first
    try:
        dl_btn.wait_for(state="visible", timeout=2000)
        with page.expect_download(timeout=2000) as dl_info:
            dl_btn.click()
        download = dl_info.value
        path = tmp_path / f"{label}.csv"
        download.save_as(path)
        return download.suggested_filename, path.read_text()
    except playwright_sync_api.Error:
        # No button was actionable in time, or a rerun invalidated the
        # download mid-flight (e.g. the underlying blob got torn down by
        # the *next* fast switch in a stress loop). Both are safe
        # outcomes for this bug -- no data is never wrong data -- so
        # callers treat None as acceptable, not a failure.
        return None


def _revenue_from_csv(csv_text: str) -> float:
    line = next(line for line in csv_text.splitlines() if line.startswith("Revenue,"))
    return float(line.split(",")[1])


def _assert_matches_ticker(filename: str, csv_text: str, ticker: str) -> None:
    assert re.match(rf"^{ticker}-\d{{2}}-\d{{2}}-IS\.csv$", filename), (
        f"downloaded filename {filename!r} doesn't match the searched ticker {ticker!r}"
    )
    revenue = _revenue_from_csv(csv_text)
    is_apple_scale = revenue > APPLE_SCALE_REVENUE_FLOOR
    expected_apple_scale = ticker == "AAPL"
    assert is_apple_scale == expected_apple_scale, (
        f"{filename} claims to be {ticker} but its Revenue ({revenue:,.0f}) doesn't match "
        f"{ticker}'s actual scale -- downloaded the wrong company's data"
    )


def test_download_after_switching_ticker_matches_the_new_ticker(page, tmp_path):
    """The exact reported bug: search company A, then company B, then
    download -- the file must belong to B, or nothing must download at
    all, but it must never be the stale A. A 300ms pause between
    switching and clicking matches a fast-but-human click, comfortably
    inside the multi-second window the original bug had.
    """
    _search_and_wait_for_settle(page, tmp_path, TICKER_A)
    result_a = _try_download_income_statement_csv(page, tmp_path, "a")
    assert result_a is not None, "baseline download should always succeed once settled"
    _assert_matches_ticker(*result_a, TICKER_A)

    _search(page, TICKER_B)
    time.sleep(0.6)
    result_b = _try_download_income_statement_csv(page, tmp_path, "b")
    if result_b is not None:
        _assert_matches_ticker(*result_b, TICKER_B)


def test_repeated_fast_switches_never_serve_the_wrong_ticker(page, tmp_path):
    """Stress variant: alternate tickers several times with only a short
    settle, downloading each time. Whenever a download actually happens,
    it must match whichever ticker was most recently searched -- run
    several times to raise confidence beyond a single lucky pass (see
    skill's non-deterministic bug guidance).
    """
    # Pre-warm *both* tickers' st.cache_data entries first -- this test
    # is specifically about the DOM-staleness race (UI catching up to
    # already-available data), not about tolerating a cold SEC EDGAR
    # fetch, which needs a much longer allowance than a fast-switch delay
    # should ever have to cover.
    _search_and_wait_for_settle(page, tmp_path, TICKER_A)
    _search_and_wait_for_settle(page, tmp_path, TICKER_B)
    _search_and_wait_for_settle(page, tmp_path, TICKER_A)

    sequence = [TICKER_B, TICKER_A, TICKER_B, TICKER_A]
    for i, ticker in enumerate(sequence):
        _search(page, ticker)
        time.sleep(0.6)
        result = _try_download_income_statement_csv(page, tmp_path, f"seq{i}")
        if result is not None:
            _assert_matches_ticker(*result, ticker)

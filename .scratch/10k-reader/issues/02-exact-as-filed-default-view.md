# 02: Exact as-filed — default single-statement view

**What to build:** The "Exact" sub-tab renders the most recent 10-K's own as-filed financial statement table — the company's own line-item labels, order, indentation, and subtotals, not remapped to any standard layout — with a picker to choose which of the three core statements to view.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A new `_classify_statement_type(short_name) -> str | None` pure function in `ticker_data.py` maps a `FilingSummary.xml` report's `ShortName` text to one of `"Income Statement"`, `"Balance Sheet"`, or `"Cash Flow Statement"`, or `None` if it doesn't recognize it (e.g. "Balance Sheet Parenthetical", "Statement of Shareholders' Equity" are not one of the three and should not be misclassified as one).
- [ ] A new `map_filing_statements(cik, accession_number, *, fetch=requests.get) -> dict[str, str]` function fetches that filing's `FilingSummary.xml`, filters to `MenuCategory == "Statements"`, and uses `_classify_statement_type` to return a dict of the three recognized statement names to their `R*.htm` filenames.
- [ ] A new `fetch_as_filed_statement(cik, accession_number, r_file, *, fetch=requests.get) -> pd.DataFrame` function fetches the given `R*.htm` and parses it (e.g. via `pandas.read_html`) into a DataFrame preserving the filer's own row labels, order, and subtotal rows.
- [ ] The "Exact" sub-tab shows a statement-type picker (Income Statement / Balance Sheet / Cash Flow Statement), defaulting to Income Statement, and renders the selected statement from the most recent 10-K as-filed.
- [ ] A filing whose `FilingSummary.xml` doesn't resolve one of the three statement types (e.g. a pre-XBRL filing that predates the `R.htm` convention entirely) shows a plain message explaining the exact-as-filed view isn't available for this filing, rather than crashing.
- [ ] A CSV download button is present for the currently-displayed as-filed table.
- [ ] `_classify_statement_type` is unit-tested directly against sample `ShortName` strings (no mocking needed) covering Income Statement, Balance Sheet, Cash Flow Statement, and at least one string that should classify as `None`.
- [ ] `map_filing_statements` is unit-tested via `requests-mock` with a small hand-built `FilingSummary.xml` fixture.
- [ ] `fetch_as_filed_statement` is unit-tested via `requests-mock` with a small hand-built `R.htm`-style fixture, asserting row labels/order are preserved exactly as given.

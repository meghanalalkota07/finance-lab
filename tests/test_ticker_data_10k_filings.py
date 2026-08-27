import pytest
import requests

from ticker_data import EDGAR_SUBMISSIONS_URL, list_10k_filings

CIK = "0000320193"


def _submissions(forms, accessions, filing_dates, report_dates, primary_docs):
    return {
        "filings": {
            "recent": {
                "form": forms,
                "accessionNumber": accessions,
                "filingDate": filing_dates,
                "reportDate": report_dates,
                "primaryDocument": primary_docs,
            }
        }
    }


def test_filters_to_10k_and_shapes_fields(requests_mock):
    payload = _submissions(
        forms=["10-Q", "10-K", "8-K", "10-K"],
        accessions=["0000320193-25-000050", "0000320193-25-000079", "0000320193-25-000060", "0000320193-24-000081"],
        filing_dates=["2025-08-01", "2025-10-31", "2025-09-01", "2024-11-01"],
        report_dates=["2025-06-28", "2025-09-27", "2025-08-15", "2024-09-28"],
        primary_docs=["aapl-10q.htm", "aapl-20250927.htm", "aapl-8k.htm", "aapl-20240928.htm"],
    )
    requests_mock.get(EDGAR_SUBMISSIONS_URL.format(cik=CIK), json=payload)

    filings = list_10k_filings(CIK)

    assert filings == [
        {
            "accession_number": "0000320193-25-000079",
            "primary_document": "aapl-20250927.htm",
            "filing_date": "2025-10-31",
            "report_date": "2025-09-27",
        },
        {
            "accession_number": "0000320193-24-000081",
            "primary_document": "aapl-20240928.htm",
            "filing_date": "2024-11-01",
            "report_date": "2024-09-28",
        },
    ]


def test_truncates_to_five(requests_mock):
    n = 7
    payload = _submissions(
        forms=["10-K"] * n,
        accessions=[f"0000320193-2{i}-000001" for i in range(n)],
        filing_dates=[f"202{i}-10-31" for i in range(n)],
        report_dates=[f"202{i}-09-27" for i in range(n)],
        primary_docs=[f"aapl-{i}.htm" for i in range(n)],
    )
    requests_mock.get(EDGAR_SUBMISSIONS_URL.format(cik=CIK), json=payload)

    filings = list_10k_filings(CIK)

    assert len(filings) == 5
    # Order (most-recent-first, as EDGAR's own `filings.recent` arrays are
    # already ordered) is preserved, just truncated.
    assert filings[0]["accession_number"] == "0000320193-20-000001"


def test_no_10k_returns_empty_list(requests_mock):
    payload = _submissions(
        forms=["10-Q", "8-K"],
        accessions=["a", "b"],
        filing_dates=["2025-01-01", "2025-02-01"],
        report_dates=["2024-12-31", "2025-01-31"],
        primary_docs=["x.htm", "y.htm"],
    )
    requests_mock.get(EDGAR_SUBMISSIONS_URL.format(cik=CIK), json=payload)

    assert list_10k_filings(CIK) == []


def test_raises_on_http_error(requests_mock):
    requests_mock.get(EDGAR_SUBMISSIONS_URL.format(cik=CIK), status_code=404)
    with pytest.raises(requests.exceptions.HTTPError):
        list_10k_filings(CIK)


def test_sends_descriptive_user_agent(requests_mock):
    requests_mock.get(EDGAR_SUBMISSIONS_URL.format(cik=CIK), json=_submissions([], [], [], [], []))
    list_10k_filings(CIK)
    sent_headers = requests_mock.last_request.headers
    assert "User-Agent" in sent_headers
    assert sent_headers["User-Agent"] != ""

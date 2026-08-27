from ticker_data import (
    _classify_statement_type,
    fetch_as_filed_statement,
    map_filing_statements,
)

CIK = "0000320193"
ACCESSION = "0000320193-25-000079"
BASE_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/"

FILING_SUMMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<FilingSummary>
  <Version>3.25.3</Version>
  <MyReports>
    <Report>
      <HtmlFileName>R3.htm</HtmlFileName>
      <ShortName>CONSOLIDATED STATEMENTS OF OPERATIONS</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>3</Position>
    </Report>
    <Report>
      <HtmlFileName>R4.htm</HtmlFileName>
      <ShortName>CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>4</Position>
    </Report>
    <Report>
      <HtmlFileName>R5.htm</HtmlFileName>
      <ShortName>CONSOLIDATED BALANCE SHEETS</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>5</Position>
    </Report>
    <Report>
      <HtmlFileName>R6.htm</HtmlFileName>
      <ShortName>CONSOLIDATED BALANCE SHEETS (Parenthetical)</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>6</Position>
    </Report>
    <Report>
      <HtmlFileName>R7.htm</HtmlFileName>
      <ShortName>CONSOLIDATED STATEMENTS OF SHAREHOLDERS EQUITY</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>7</Position>
    </Report>
    <Report>
      <HtmlFileName>R8.htm</HtmlFileName>
      <ShortName>CONSOLIDATED STATEMENTS OF CASH FLOWS</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>8</Position>
    </Report>
    <Report>
      <HtmlFileName>R100.htm</HtmlFileName>
      <ShortName>Stock-Based Compensation (Details)</ShortName>
      <MenuCategory>Notes</MenuCategory>
      <Position>100</Position>
    </Report>
  </MyReports>
</FilingSummary>
"""

R_HTM_FIXTURE = """<html><body>
<table class="report">
<tr><th>CONSOLIDATED BALANCE SHEETS</th><th>Sep. 27, 2025</th><th>Sep. 28, 2024</th></tr>
<tr><td>Cash and cash equivalents</td><td>$ 35,934</td><td>$ 29,943</td></tr>
<tr><td>Total current assets</td><td>$ 147,957</td><td>$ 152,987</td></tr>
</table>
</body></html>
"""


def test_classify_statement_type():
    assert _classify_statement_type("CONSOLIDATED STATEMENTS OF OPERATIONS") == "Income Statement"
    assert _classify_statement_type("CONSOLIDATED STATEMENTS OF INCOME") == "Income Statement"
    assert _classify_statement_type("CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME") is None
    assert _classify_statement_type("CONSOLIDATED BALANCE SHEETS") == "Balance Sheet"
    assert _classify_statement_type("CONSOLIDATED BALANCE SHEETS (Parenthetical)") is None
    assert _classify_statement_type("CONSOLIDATED STATEMENTS OF CASH FLOWS") == "Cash Flow Statement"
    assert _classify_statement_type("CONSOLIDATED STATEMENTS OF SHAREHOLDERS EQUITY") is None


def test_map_filing_statements_isolates_the_three_core_statements(requests_mock):
    requests_mock.get(BASE_URL + "FilingSummary.xml", text=FILING_SUMMARY_XML)

    result = map_filing_statements(CIK, ACCESSION)

    assert result == {
        "Income Statement": "R3.htm",
        "Balance Sheet": "R5.htm",
        "Cash Flow Statement": "R8.htm",
    }


def test_map_filing_statements_sends_descriptive_user_agent(requests_mock):
    requests_mock.get(BASE_URL + "FilingSummary.xml", text=FILING_SUMMARY_XML)
    map_filing_statements(CIK, ACCESSION)
    sent_headers = requests_mock.last_request.headers
    assert "User-Agent" in sent_headers
    assert sent_headers["User-Agent"] != ""


def test_map_filing_statements_returns_empty_dict_for_missing_filing_summary(requests_mock):
    requests_mock.get(BASE_URL + "FilingSummary.xml", status_code=404)
    assert map_filing_statements(CIK, ACCESSION) == {}


def test_fetch_as_filed_statement_preserves_labels_and_order(requests_mock):
    requests_mock.get(BASE_URL + "R5.htm", text=R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R5.htm")

    first_column = df.iloc[:, 0].astype(str).tolist()
    assert first_column.index("Cash and cash equivalents") < first_column.index("Total current assets")
    assert "35,934" in str(df.iloc[0, 1])

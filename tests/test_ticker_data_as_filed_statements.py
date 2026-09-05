import math

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

# A plain fixture with no XBRL concept references at all -- exercises the
# fallback path for filers/rows whose markup doesn't carry a `defref_`
# reference (or, historically, this test's own original shape).
R_HTM_FIXTURE_NO_CONCEPT_REFS = """<html><body>
<table class="report">
<tr><th>CONSOLIDATED BALANCE SHEETS</th><th>Sep. 27, 2025</th><th>Sep. 28, 2024</th></tr>
<tr><td>Cash and cash equivalents</td><td>$ 35,934</td><td>$ 29,943</td></tr>
<tr><td>Total current assets</td><td>$ 147,957</td><td>$ 152,987</td></tr>
</table>
</body></html>
"""

# Shaped after Adobe's actual FY2021 10-K Income Statement R.htm (fetched
# and inspected directly from SEC EDGAR): a two-row header, and -- the
# exact pattern that caused the reported bug -- "Subscription" appearing
# twice with the *same displayed label* but under two different XBRL
# concepts: defref_adbe_SubscriptionRevenues (a revenue line) and
# defref_adbe_CostofSubscriptionRevenue (a cost-of-revenue line).
REALISTIC_R_HTM_FIXTURE = """<html><body>
<table class="report" border="0" cellspacing="2" id="idm1">
<tr>
<th class="tl" colspan="1" rowspan="2"><div style="width: 200px;"><strong>Consolidated Statements of Income - USD ($)<br> shares in Millions, $ in Millions</strong></div></th>
<th class="th" colspan="2">12 Months Ended</th>
</tr>
<tr>
<th class="th"><div>Nov. 28, 2025</div></th>
<th class="th"><div>Nov. 29, 2024</div></th>
</tr>
<tr class="re">
<td class="pl" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_RevenuesAbstract', window );"><strong>Revenue:</strong></a></td>
<td class="text">&#160;<span></span>
</td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_adbe_SubscriptionRevenues', window );">Subscription</a></td>
<td class="nump">$ 14,573<span></span>
</td>
<td class="nump">$ 11,626<span></span>
</td>
</tr>
<tr class="re">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_Revenues', window );">Total revenue</a></td>
<td class="nump">$ 15,785<span></span>
</td>
<td class="nump">$ 12,868<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_CostOfRevenueAbstract', window );"><strong>Cost of revenue:</strong></a></td>
<td class="text">&#160;<span></span>
</td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="re">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_adbe_CostofSubscriptionRevenue', window );">Subscription</a></td>
<td class="nump">1,374<span></span>
</td>
<td class="nump">1,285<span></span>
</td>
</tr>
</table>
</body></html>
"""

# Shaped after Adobe's actual FY2025 10-K Income Statement R.htm (fetched
# and inspected directly from SEC EDGAR): a revenue-by-type breakdown
# appended *inside the same statement table*, each group introduced by a
# dimensional axis-member header row (concept shape
# `defref_<Axis>=<Member>`, distinct from a plain concept reference).
# Rows under each group reuse the *same* base concepts (us-gaap:Revenues,
# us-gaap:CostOfRevenue) as the top-level statement -- this is the
# complete root cause of the reported bug: $22,904 (Subscription) +
# $325 (Product) + $540 (Services and other) = $23,769 (top-level Total),
# but a concept-only key (no axis awareness) collapses all four "Revenue"
# rows onto one, and the last one processed (Services and other's $540)
# silently wins -- which is exactly the wrong number the user reported
# seeing.
AXIS_BREAKDOWN_R_HTM_FIXTURE = """<html><body>
<table class="report" border="0" cellspacing="2" id="idm1">
<tr>
<th class="tl" colspan="1" rowspan="2"><div style="width: 200px;"><strong>Consolidated Statements of Income - USD ($)<br> shares in Millions, $ in Millions</strong></div></th>
<th class="th" colspan="1">12 Months Ended</th>
</tr>
<tr>
<th class="th"><div>Nov. 28, 2025</div></th>
</tr>
<tr class="re">
<td class="pl" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_RevenuesAbstract', window );"><strong>Revenue:</strong></a></td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_Revenues', window );">Revenue</a></td>
<td class="nump">$ 23,769<span></span>
</td>
</tr>
<tr class="re">
<td class="pl" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_srt_ProductOrServiceAxis=adbe_SubscriptionRevenueMember', window );">Subscription</a></td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_RevenuesAbstract', window );"><strong>Revenue:</strong></a></td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="re">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_Revenues', window );">Revenue</a></td>
<td class="nump">$ 22,904<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_srt_ProductOrServiceAxis=us-gaap_ServiceOtherMember', window );">Services and other</a></td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="re">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_RevenuesAbstract', window );"><strong>Revenue:</strong></a></td>
<td class="text">&#160;<span></span>
</td>
</tr>
<tr class="ro">
<td class="pl custom" style="border-bottom: 0px;" valign="top"><a class="a" href="javascript:void(0);" onclick="top.Show.showAR( this, 'defref_us-gaap_Revenues', window );">Revenue</a></td>
<td class="nump">540<span></span>
</td>
</tr>
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
    requests_mock.get(BASE_URL + "R5.htm", text=R_HTM_FIXTURE_NO_CONCEPT_REFS)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R5.htm")

    first_column = df.iloc[:, 0].astype(str).tolist()
    assert first_column.index("Cash and cash equivalents") < first_column.index("Total current assets")
    assert "35,934" in str(df.iloc[0, 1])


def test_fetch_as_filed_statement_falls_back_to_synthetic_key_without_a_concept_reference(requests_mock):
    """A row whose label cell carries no `defref_` reference (e.g. this
    fixture's plain, un-tagged markup) must still appear in the table --
    not be dropped -- keyed by a synthetic identifier that can't collide
    with a real concept.
    """
    requests_mock.get(BASE_URL + "R5.htm", text=R_HTM_FIXTURE_NO_CONCEPT_REFS)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R5.htm")

    assert len(df) == 2
    assert len(set(df.index)) == 2  # both synthetic keys are distinct
    for key in df.index:
        assert "defref_" not in str(key)


def test_fetch_as_filed_statement_disambiguates_duplicate_labels_by_concept(requests_mock):
    """The exact reported bug: two rows in the same statement both
    display "Subscription" but tag different XBRL concepts (one under
    Revenue, one under Cost of Revenue) -- both must survive as distinct
    rows with their own correct values, not collapse into one.
    """
    requests_mock.get(BASE_URL + "R3.htm", text=REALISTIC_R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R3.htm")

    subscription_rows = df[df.iloc[:, 0] == "Subscription"]
    assert len(subscription_rows) == 2
    assert len(set(subscription_rows.index)) == 2

    revenue_row = df.loc["defref_adbe_SubscriptionRevenues"]
    cost_row = df.loc["defref_adbe_CostofSubscriptionRevenue"]
    assert revenue_row.iloc[0] == "Subscription"
    assert cost_row.iloc[0] == "Subscription"
    assert "14,573" in str(revenue_row.iloc[1])
    assert str(cost_row.iloc[1]).strip() == "1,374"


def test_fetch_as_filed_statement_abstract_row_has_no_value(requests_mock):
    requests_mock.get(BASE_URL + "R3.htm", text=REALISTIC_R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R3.htm")

    header_row = df.loc["defref_us-gaap_RevenuesAbstract"]
    assert header_row.iloc[0] == "Revenue:"
    assert all(math.isnan(v) for v in header_row.iloc[1:])


def test_fetch_as_filed_statement_disambiguates_axis_breakdown_reusing_the_same_concept(requests_mock):
    """The complete reported bug: a revenue-by-type breakdown appended
    inside the same statement table repeats the *same* base concept
    ("Revenue" / us-gaap:Revenues) once per dimensional group (top-level
    total, plus one per breakdown group). All occurrences must survive as
    distinct rows with their own correct values -- the exact case where
    the reported "$540 million services and other" figure came from
    silently overwriting the top-level total and the other group.
    """
    requests_mock.get(BASE_URL + "R3.htm", text=AXIS_BREAKDOWN_R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R3.htm")

    revenue_rows = df[df.iloc[:, 0] == "Revenue"]
    assert len(revenue_rows) == 3
    assert len(set(revenue_rows.index)) == 3
    values = sorted(str(v).strip() for v in revenue_rows.iloc[:, 1])
    assert values == sorted(["$ 23,769", "$ 22,904", "540"])


def test_fetch_as_filed_statement_axis_header_rows_are_distinct_by_their_own_member(requests_mock):
    requests_mock.get(BASE_URL + "R3.htm", text=AXIS_BREAKDOWN_R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R3.htm")

    subscription_header = df.loc["defref_srt_ProductOrServiceAxis=adbe_SubscriptionRevenueMember"]
    services_header = df.loc["defref_srt_ProductOrServiceAxis=us-gaap_ServiceOtherMember"]
    assert subscription_header.iloc[0] == "Subscription"
    assert services_header.iloc[0] == "Services and other"


def test_fetch_as_filed_statement_row_count_matches_source_rows(requests_mock):
    """No row should ever be silently dropped or collapsed by the fetch
    itself -- deduplication (if any) is the merge step's job, not the
    single-filing fetch's.
    """
    requests_mock.get(BASE_URL + "R3.htm", text=REALISTIC_R_HTM_FIXTURE)

    df = fetch_as_filed_statement(CIK, ACCESSION, "R3.htm")

    assert len(df) == 5  # Revenue:, Subscription, Total revenue, Cost of revenue:, Subscription

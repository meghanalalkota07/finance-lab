import math

from ticker_data import EDGAR_COMPANYFACTS_URL, get_normalized_10k_financials

CIK = "0000320193"


def fact(end, val, fy, fp="FY", form="10-K"):
    return {"end": end, "val": val, "fy": fy, "fp": fp, "form": form}


def usd_block(entries):
    return {"units": {"USD": entries}}


def usd_per_share_block(entries):
    return {"units": {"USD/shares": entries}}


def companyfacts(us_gaap=None):
    return {"facts": {"us-gaap": us_gaap or {}, "dei": {}}}


def mock_companyfacts(requests_mock, cik, **kwargs):
    requests_mock.get(EDGAR_COMPANYFACTS_URL.format(cik=cik), json=companyfacts(**kwargs))


def test_standard_filer_returns_three_statements_metric_rows_by_year_columns(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd_block(
                [fact("2023-12-31", 1000.0, 2023), fact("2024-12-31", 1100.0, 2024)]
            ),
            "CostOfGoodsAndServicesSold": usd_block([fact("2024-12-31", 600.0, 2024)]),
            "Assets": usd_block([fact("2023-12-31", 5000.0, 2023), fact("2024-12-31", 5500.0, 2024)]),
            "NetCashProvidedByUsedInOperatingActivities": usd_block([fact("2024-12-31", 300.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert set(result) == {"Income Statement", "Balance Sheet", "Cash Flow Statement"}
    income_statement = result["Income Statement"]
    assert income_statement.index.name == "Metric"
    assert "Revenue" in income_statement.index
    assert income_statement.loc["Revenue", 2024] == 1100.0
    assert income_statement.loc["Revenue", 2023] == 1000.0
    # 2023 has no Cost of Revenue fact -- absent (NaN), not zero.
    assert income_statement.loc["Cost of Revenue", 2024] == 600.0
    assert math.isnan(income_statement.loc["Cost of Revenue", 2023])

    assert result["Balance Sheet"].loc["Total Assets", 2024] == 5500.0
    assert result["Cash Flow Statement"].loc["Operating Cash Flow", 2024] == 300.0


def test_cost_of_revenue_falls_back_through_the_chain(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "CostOfRevenue": usd_block([fact("2020-12-31", 500.0, 2020)]),
            "CostOfGoodsAndServicesSold": usd_block([fact("2024-12-31", 600.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK, years=None)

    assert result["Income Statement"].loc["Cost of Revenue", 2020] == 500.0
    assert result["Income Statement"].loc["Cost of Revenue", 2024] == 600.0


def test_capital_expenditures_falls_back_through_the_chain(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            # SPG-shaped: only ever tags the older "productive assets"
            # variant, never the primary PP&E-specific tag.
            "PaymentsToAcquireProductiveAssets": usd_block([fact("2014-12-31", 796.0, 2014)]),
        },
    )

    result = get_normalized_10k_financials(CIK, years=None)

    assert result["Cash Flow Statement"].loc["Capital Expenditures", 2014] == 796.0


def test_bank_operating_expenses_uses_noninterest_expense(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "NoninterestExpense": usd_block([fact("2024-12-31", 900.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert result["Income Statement"].loc["Operating Expenses", 2024] == 900.0


def test_pretax_income_derived_from_net_income_plus_tax_when_no_direct_tag(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "NetIncomeLoss": usd_block([fact("2024-12-31", 80.0, 2024)]),
            "IncomeTaxExpenseBenefit": usd_block([fact("2024-12-31", 20.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert result["Income Statement"].loc["Pre-tax Income", 2024] == 100.0


def test_pretax_income_prefers_direct_tag_over_derivation(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": usd_block(
                [fact("2024-12-31", 105.0, 2024)]
            ),
            "NetIncomeLoss": usd_block([fact("2024-12-31", 80.0, 2024)]),
            "IncomeTaxExpenseBenefit": usd_block([fact("2024-12-31", 20.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert result["Income Statement"].loc["Pre-tax Income", 2024] == 105.0


def test_goodwill_and_intangibles_sums_components(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "Goodwill": usd_block([fact("2024-12-31", 50.0, 2024)]),
            "FiniteLivedIntangibleAssetsNet": usd_block([fact("2024-12-31", 10.0, 2024)]),
            "IndefiniteLivedIntangibleAssetsExcludingGoodwill": usd_block([fact("2024-12-31", 5.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert result["Balance Sheet"].loc["Goodwill & Intangible Assets", 2024] == 65.0


def test_goodwill_and_intangibles_uses_combined_tag_without_double_counting(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "Goodwill": usd_block([fact("2024-12-31", 50.0, 2024)]),
            "IntangibleAssetsNetExcludingGoodwill": usd_block([fact("2024-12-31", 15.0, 2024)]),
            "FiniteLivedIntangibleAssetsNet": usd_block([fact("2024-12-31", 10.0, 2024)]),
            "IndefiniteLivedIntangibleAssetsExcludingGoodwill": usd_block([fact("2024-12-31", 5.0, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    # The combined tag already covers finite + indefinite -- must not
    # also add the component tags on top of it.
    assert result["Balance Sheet"].loc["Goodwill & Intangible Assets", 2024] == 65.0


def test_years_parameter_limits_to_most_recent_n_columns(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "Assets": usd_block(
                [fact(f"{y}-12-31", float(y), y) for y in range(2015, 2025)]
            ),
        },
    )

    result = get_normalized_10k_financials(CIK, years=5)

    assert list(result["Balance Sheet"].columns) == [2024, 2023, 2022, 2021, 2020]


def test_years_none_returns_full_available_history(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "Assets": usd_block(
                [fact(f"{y}-12-31", float(y), y) for y in range(2015, 2025)]
            ),
        },
    )

    result = get_normalized_10k_financials(CIK, years=None)

    assert len(result["Balance Sheet"].columns) == 10


def test_eps_basic_and_diluted_are_separate_rows(requests_mock):
    mock_companyfacts(
        requests_mock,
        CIK,
        us_gaap={
            "EarningsPerShareBasic": usd_per_share_block([fact("2024-12-31", 6.50, 2024)]),
            "EarningsPerShareDiluted": usd_per_share_block([fact("2024-12-31", 6.40, 2024)]),
        },
    )

    result = get_normalized_10k_financials(CIK)

    assert result["Income Statement"].loc["EPS Basic", 2024] == 6.50
    assert result["Income Statement"].loc["EPS Diluted", 2024] == 6.40

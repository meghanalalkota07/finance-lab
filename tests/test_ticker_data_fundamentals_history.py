import pandas as pd
import pytest

from ticker_data import get_fundamentals_history, EDGAR_COMPANYFACTS_URL


def fact(end, val, fy, fp="FY", form="10-K", start=None):
    entry = {"end": end, "val": val, "fy": fy, "fp": fp, "form": form}
    if start is not None:
        entry["start"] = start
    return entry


def usd_block(entries):
    return {"units": {"USD": entries}}


def shares_block(entries):
    return {"units": {"shares": entries}}


def usd_per_share_block(entries):
    return {"units": {"USD/shares": entries}}


def companyfacts(us_gaap=None, dei=None):
    return {"facts": {"us-gaap": us_gaap or {}, "dei": dei or {}}}


def price_history(rows):
    # rows: {"YYYY-MM-DD": adj_close}
    idx = pd.DatetimeIndex(sorted(rows.keys()), name="Date")
    return pd.DataFrame({"AdjClose": [rows[d] for d in sorted(rows.keys())]}, index=idx)


def mock_companyfacts(requests_mock, cik, **kwargs):
    """Register the companyfacts fixture at the real EDGAR URL, so tests
    exercise get_fundamentals_history's actual HTTP call and JSON parsing
    (per spec.md: mock at the HTTP boundary, not ticker_data.py's own
    functions).
    """
    requests_mock.get(EDGAR_COMPANYFACTS_URL.format(cik=cik), json=companyfacts(**kwargs))


def test_clean_single_tag_filer(requests_mock):
    # AAPL-shaped: one tag per metric, no drift.
    mock_companyfacts(
        requests_mock,
        "0000320193",
        us_gaap={
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd_block([
                fact("2023-09-30", 383_285_000_000, 2023, start="2022-10-01"),
                fact("2024-09-28", 391_035_000_000, 2024, start="2023-10-01"),
            ]),
            "NetIncomeLoss": usd_block([
                fact("2023-09-30", 96_995_000_000, 2023, start="2022-10-01"),
                fact("2024-09-28", 93_736_000_000, 2024, start="2023-10-01"),
            ]),
            "EarningsPerShareDiluted": usd_per_share_block([
                fact("2023-09-30", 6.13, 2023, start="2022-10-01"),
                fact("2024-09-28", 6.08, 2024, start="2023-10-01"),
            ]),
            "CommonStockDividendsPerShareDeclared": usd_per_share_block([
                fact("2023-09-30", 0.94, 2023, start="2022-10-01"),
                fact("2024-09-28", 0.98, 2024, start="2023-10-01"),
            ]),
            "CommonStockSharesOutstanding": shares_block([
                fact("2023-09-30", 15_550_061_000, 2023),
                fact("2024-09-28", 15_115_823_000, 2024),
            ]),
        },
    )

    df = get_fundamentals_history("0000320193", price_history({}))

    assert list(df.index) == [2023, 2024]
    assert df.loc[2024, "Revenue"] == 391_035_000_000
    assert df.loc[2024, "NetIncome"] == 93_736_000_000
    assert df.loc[2024, "EPS"] == 6.08
    assert df.loc[2024, "DividendsPerShare"] == 0.98
    assert df.loc[2024, "SharesOutstanding"] == 15_115_823_000


def test_net_income_falls_back_to_profit_loss_for_gap_years(requests_mock):
    # Zions-shaped: NetIncomeLoss has a hole in FY2015-2016 that ProfitLoss fills.
    mock_companyfacts(
        requests_mock,
        "0000109380",
        us_gaap={
            "NetIncomeLoss": usd_block([
                fact("2014-12-31", 200_000_000, 2014),
                # FY2015, FY2016 missing from this tag
                fact("2017-12-31", 592_000_000, 2017),
            ]),
            "ProfitLoss": usd_block([
                fact("2014-12-31", 200_000_000, 2014),
                fact("2015-12-31", 309_000_000, 2015),
                fact("2016-12-31", 469_000_000, 2016),
                fact("2017-12-31", 592_000_000, 2017),
            ]),
        },
    )

    df = get_fundamentals_history("0000109380", price_history({}))

    assert df.loc[2015, "NetIncome"] == 309_000_000
    assert df.loc[2016, "NetIncome"] == 469_000_000
    assert df.loc[2014, "NetIncome"] == 200_000_000


def test_bank_revenue_uses_net_of_interest_expense_not_generic_chain(requests_mock):
    # Zions-shaped: Revenues/ASC-606 tag captures only noninterest income;
    # RevenuesNetOfInterestExpense is the real bank revenue figure.
    mock_companyfacts(
        requests_mock,
        "0000109380",
        us_gaap={
            "Revenues": usd_block([fact("2018-12-31", 508_000_000, 2018)]),
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd_block([
                fact("2018-12-31", 412_000_000, 2018),
            ]),
            "RevenuesNetOfInterestExpense": usd_block([
                fact("2018-12-31", 2_783_000_000, 2018),
            ]),
        },
    )

    df = get_fundamentals_history("0000109380", price_history({}))

    assert df.loc[2018, "Revenue"] == 2_783_000_000


def test_bank_tag_still_falls_through_to_generic_chain_for_years_it_lacks(requests_mock):
    # Same bank, but RevenuesNetOfInterestExpense only starts in 2019 --
    # 2018 should still be filled from the generic chain, not dropped.
    # Guards against treating "is a bank" as a whole-company either/or
    # switch instead of a per-period fallback (spec.md: "evaluated per
    # fiscal period ... not a single tag chosen once per company").
    mock_companyfacts(
        requests_mock,
        "0000109380",
        us_gaap={
            "Revenues": usd_block([fact("2018-12-31", 508_000_000, 2018)]),
            "RevenuesNetOfInterestExpense": usd_block([
                fact("2019-12-31", 2_900_000_000, 2019),
            ]),
        },
    )

    df = get_fundamentals_history("0000109380", price_history({}))

    assert df.loc[2018, "Revenue"] == 508_000_000
    assert df.loc[2019, "Revenue"] == 2_900_000_000


def test_dividends_fall_back_to_cash_paid_tag_after_a_mid_history_switch(requests_mock):
    # Kohl's-shaped: Declared covers only 2012-2016, CashPaid covers 2012-2025.
    mock_companyfacts(
        requests_mock,
        "0000885639",
        us_gaap={
            "CommonStockDividendsPerShareDeclared": usd_per_share_block([
                fact("2013-02-02", 1.00, 2012),
                fact("2017-02-03", 1.68, 2016),
            ]),
            "CommonStockDividendsPerShareCashPaid": usd_per_share_block([
                fact("2013-02-02", 1.00, 2012),
                fact("2017-02-03", 1.68, 2016),
                fact("2018-02-03", 1.76, 2017),
            ]),
        },
    )

    df = get_fundamentals_history("0000885639", price_history({}))

    assert df.loc[2017, "DividendsPerShare"] == 1.76


def test_revenue_prefers_current_standard_tag_when_both_present_for_same_period(requests_mock):
    # AT&T-shaped: Revenues is continuous and never dropped; the ASC-606 tag
    # only has sparse quarterly (non-10-K) entries and must be ignored.
    mock_companyfacts(
        requests_mock,
        "0000732717",
        us_gaap={
            "Revenues": usd_block([
                fact("2018-12-31", 170_756_000_000, 2018),
                fact("2019-12-31", 181_193_000_000, 2019),
            ]),
            "RevenueFromContractWithCustomerExcludingAssessedTax": usd_block([
                fact("2018-06-30", 39_000_000_000, 2018, fp="Q2", form="10-Q", start="2018-04-01"),
            ]),
        },
    )

    df = get_fundamentals_history("0000732717", price_history({}))

    assert df.loc[2018, "Revenue"] == 170_756_000_000
    assert df.loc[2019, "Revenue"] == 181_193_000_000


def test_shares_outstanding_falls_back_to_dei_tag_when_primary_absent(requests_mock):
    mock_companyfacts(
        requests_mock,
        "0000885639",
        dei={
            "EntityCommonStockSharesOutstanding": shares_block([
                fact("2026-05-29", 127_000_000, 2025),
            ]),
        },
    )

    df = get_fundamentals_history("0000885639", price_history({}))

    assert df.loc[2025, "SharesOutstanding"] == 127_000_000


def test_shares_outstanding_skips_spurious_zero_and_falls_through(requests_mock):
    mock_companyfacts(
        requests_mock,
        "0000732717",
        us_gaap={
            "CommonStockSharesOutstanding": shares_block([
                fact("2010-12-31", 0, 2010),  # spurious filing-error zero
            ]),
        },
        dei={
            "EntityCommonStockSharesOutstanding": shares_block([
                fact("2011-01-15", 6_495_231_088, 2010),
            ]),
        },
    )

    df = get_fundamentals_history("0000732717", price_history({}))

    assert df.loc[2010, "SharesOutstanding"] == 6_495_231_088


def test_dividends_last_resort_sums_quarterly_facts_when_no_annual_figure_exists(requests_mock):
    mock_companyfacts(
        requests_mock,
        "0000109380",
        us_gaap={
            "NetIncomeLoss": usd_block([fact("2017-12-31", 592_000_000, 2017)]),
            "CommonStockDividendsPerShareCashPaid": usd_per_share_block([
                fact("2017-03-31", 0.08, 2017, fp="Q1", form="10-Q", start="2017-01-01"),
                fact("2017-06-30", 0.08, 2017, fp="Q2", form="10-Q", start="2017-04-01"),
                fact("2017-09-30", 0.08, 2017, fp="Q3", form="10-Q", start="2017-07-01"),
                fact("2017-12-31", 0.08, 2017, fp="Q4", form="10-Q", start="2017-10-01"),
            ]),
        },
    )

    df = get_fundamentals_history("0000109380", price_history({}))

    assert df.loc[2017, "DividendsPerShare"] == pytest.approx(0.32)


def test_derives_market_cap_and_trailing_pe_from_shares_eps_and_price(requests_mock):
    mock_companyfacts(
        requests_mock,
        "0000320193",
        us_gaap={
            "EarningsPerShareDiluted": usd_per_share_block([
                fact("2024-09-28", 6.08, 2024, start="2023-10-01"),
            ]),
            "CommonStockSharesOutstanding": shares_block([
                fact("2024-09-28", 15_000_000_000, 2024),
            ]),
        },
    )
    prices = price_history({"2024-09-27": 227.79, "2024-09-30": 233.0})

    df = get_fundamentals_history("0000320193", prices)

    assert df.loc[2024, "MarketCap"] == pytest.approx(15_000_000_000 * 227.79)
    assert df.loc[2024, "TrailingPE"] == pytest.approx(227.79 / 6.08)


def test_fetches_from_correct_cik_padded_url_with_descriptive_user_agent(requests_mock):
    mock_companyfacts(requests_mock, "0000320193")

    get_fundamentals_history("0000320193", price_history({}))

    assert requests_mock.last_request.url == EDGAR_COMPANYFACTS_URL.format(cik="0000320193")
    assert requests_mock.last_request.headers.get("User-Agent")


def test_edgar_url_template_has_cik_placeholder():
    assert "{cik}" in EDGAR_COMPANYFACTS_URL

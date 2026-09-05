import pandas as pd

from ticker_data import merge_as_filed_statements


def _table(rows: list[tuple[str, str, str, str]], headers=("Label", "Primary", "Prior")) -> pd.DataFrame:
    """Build a table shaped like fetch_as_filed_statement's return value:
    a label column plus value columns, indexed by XBRL concept. `rows` is
    (concept, label, *values) -- concept and label are decoupled on
    purpose, since real filings can render two different concepts with
    the identical label (the exact bug this merge logic guards against).
    """
    concepts = [row[0] for row in rows]
    data = [row[1:] for row in rows]
    df = pd.DataFrame(data, columns=list(headers))
    df.index = pd.Index(concepts)
    return df


def test_merges_into_one_column_per_year_no_overlap():
    fy25 = _table([
        ("Cash", "Cash and cash equivalents", "$ 35,934", "$ 29,943"),
        ("TotalCurrentAssets", "Total current assets", "$ 147,957", "$ 152,987"),
    ])
    fy24 = _table([
        ("Cash", "Cash and cash equivalents", "$ 29,943", "$ 24,978"),
        ("TotalCurrentAssets", "Total current assets", "$ 152,987", "$ 143,566"),
    ])

    merged = merge_as_filed_statements([fy25, fy24], ["2025", "2024"])

    assert list(merged.columns) == ["2025", "2024"]
    assert merged.loc["Cash and cash equivalents", "2025"] == "$ 35,934"
    assert merged.loc["Cash and cash equivalents", "2024"] == "$ 29,943"


def test_line_item_only_in_older_filing_gets_blank_in_newer_year():
    fy25 = _table([("Cash", "Cash and cash equivalents", "$ 35,934", "$ 29,943")])
    fy24 = _table([
        ("Cash", "Cash and cash equivalents", "$ 29,943", "$ 24,978"),
        ("DiscontinuedOps", "Discontinued Operations", "$ 100", "$ 90"),
    ])

    merged = merge_as_filed_statements([fy25, fy24], ["2025", "2024"])

    assert merged.loc["Discontinued Operations", "2025"] == ""
    assert merged.loc["Discontinued Operations", "2024"] == "$ 100"


def test_duplicate_label_under_different_concepts_both_survive_the_merge():
    """The exact reported bug: a filing renders the same label ("Subscription")
    for two different XBRL concepts (revenue vs. cost of revenue) within
    one statement. Both must appear as distinct rows across every year,
    never overwriting each other.
    """
    fy25 = _table([
        ("SubscriptionRevenue", "Subscription", "$ 14,573", "$ 11,626"),
        ("CostOfSubscriptionRevenue", "Subscription", "1,374", "1,108"),
    ])
    fy24 = _table([
        ("SubscriptionRevenue", "Subscription", "$ 11,626", "$ 9,634"),
        ("CostOfSubscriptionRevenue", "Subscription", "1,108", "926"),
    ])

    merged = merge_as_filed_statements([fy25, fy24], ["2025", "2024"])

    subscription_rows = merged.loc[merged.index == "Subscription"]
    assert len(subscription_rows) == 2
    revenue_values = sorted(subscription_rows["2025"].tolist())
    assert revenue_values == ["$ 14,573", "1,374"]


def test_row_order_follows_newest_filing_then_appends_older_only_rows():
    fy25 = _table([("B", "B", "1", "1"), ("A", "A", "1", "1")])
    fy24 = _table([("A", "A", "1", "1"), ("C", "C", "1", "1")])

    merged = merge_as_filed_statements([fy25, fy24], ["2025", "2024"])

    assert list(merged.index) == ["B", "A", "C"]


def test_a_relabeled_concept_keeps_the_newest_filings_wording():
    """A filer rewording a line's label between years shouldn't cause a
    value collision (the label-text-keyed version's failure mode) -- the
    concept is what's matched, and the displayed label comes from
    whichever filing (newest-first) was processed first.
    """
    fy25 = _table([("NetRevenue", "Total net revenue", "100", "90")])
    fy24 = _table([("NetRevenue", "Net revenues", "90", "80")])

    merged = merge_as_filed_statements([fy25, fy24], ["2025", "2024"])

    assert list(merged.index) == ["Total net revenue"]
    assert merged.loc["Total net revenue", "2025"] == "100"
    assert merged.loc["Total net revenue", "2024"] == "90"


def test_empty_tables_returns_empty_frame():
    assert merge_as_filed_statements([], []).empty


def test_index_name_taken_from_first_tables_label_column():
    fy25 = _table([("Cash", "Cash", "1", "1")], headers=("CONSOLIDATED BALANCE SHEETS", "Sep. 27, 2025", "Sep. 28, 2024"))
    merged = merge_as_filed_statements([fy25], ["2025"])
    assert merged.index.name == "CONSOLIDATED BALANCE SHEETS"

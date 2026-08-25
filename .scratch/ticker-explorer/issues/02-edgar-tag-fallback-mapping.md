# EDGAR tag-fallback mapping

Type: research
Status: resolved

## Question

Build the concrete tag-fallback chain(s) needed to reliably pull historical revenue, net income, EPS, dividends per share, and shares outstanding from SEC EDGAR's XBRL `companyfacts` API across the tag variants different filers/periods actually use, so the spec can state exactly which XBRL concepts to query and in what fallback order.

## Findings so far (from prior research this session)

Verified directly against AAPL's live `companyfacts` JSON:

- `NetIncomeLoss` and `EarningsPerShareDiluted`/`EarningsPerShareBasic`: stable single tags, data back to FY2007.
- `CommonStockDividendsPerShareDeclared`: stable single tag, data back to 2010.
- Shares outstanding: **two candidate tags** — `us-gaap:CommonStockSharesOutstanding` (from 2008) and `dei:EntityCommonStockSharesOutstanding` (cover-page count, from 2009). Needs a decided preference/fallback order.
- Revenue is the problem child: `us-gaap:Revenues` only has AAPL data 2016–2018; `RevenueFromContractWithCustomerExcludingAssessedTax` takes over 2017+ due to the 2018 ASC 606 transition. A single-tag pull will silently produce gaps or wrong results.
- Foreign private issuers/ADRs: annual XBRL is required, but interim (quarterly) 6-K filings are largely XBRL-exempt — expect sparse/inconsistent quarterly data outside US domestic filers.

## Answer

Confirmed against live `companyfacts` JSON for AAPL, MSFT, KSS, ZION, and T. Net income and dividends turn out to have their own drift problems, not just revenue. Decided fallback chains (evaluate **per fiscal period**, not per company — take the highest-priority tag with an entry for that period):

- **Revenue:** `RevenueFromContractWithCustomerExcludingAssessedTax` → `Revenues` → `SalesRevenueNet` → `RevenueFromContractWithCustomerIncludingAssessedTax`. AT&T never adopted tag 1 for its consolidated top line (19 years straight under `Revenues` alone) — proves tag 2 can't be dropped. **Banks are a separate case**: ZION's `Revenues`/tag-1 values capture only noninterest income (~$500-660M), a 5-6x undercount vs. true revenue via `RevenuesNetOfInterestExpense` (~$2.8-3.1B) — needs its own path for depository institutions.
- **Net income:** `NetIncomeLoss` → `ProfitLoss`. ZION has a real 4-year hole in `NetIncomeLoss` (FY2014–2017) that only `ProfitLoss` fills — the same shape of problem as revenue's ASC-606 transition, just later-discovered.
- **EPS:** `EarningsPerShareDiluted` / `EarningsPerShareBasic` alone — stable across all 5 filers, no fallback needed.
- **Dividends/share:** `CommonStockDividendsPerShareDeclared` → `CommonStockDividendsPerShareCashPaid` → last-resort sum of 4 quarterly 10-Q facts. KSS switches tags entirely in FY2017; ZION has a fiscal year (2017) with no annual figure under either tag, only quarterlies.
- **Shares outstanding:** `us-gaap:CommonStockSharesOutstanding` (period-end aligned) → `dei:EntityCommonStockSharesOutstanding` (cover-page date, present for all 5 filers vs. only 3/5 for the first tag) → `us-gaap:CommonStockSharesIssued` (gross, flag as approximate). Apply an outlier/zero check regardless of tag chosen — AT&T's dei tag has a spurious `0`-share entry for 2010-12-31.

Full evidence, per-filer figures, and reasoning: [research/02-edgar-tag-fallback-mapping-findings.md](../research/02-edgar-tag-fallback-mapping-findings.md)

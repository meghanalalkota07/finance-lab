# Normalized Line-Item Tag Mapping — Findings

Extends `.scratch/ticker-explorer/research/02-edgar-tag-fallback-mapping-findings.md` (which covers Revenue, Net Income, EPS, Dividends/share, Shares Outstanding) with the ~19 additional line items needed for the 10-K Reader's Normalized sub-tab: 9 income-statement items, 9 balance-sheet items, and 5 cash-flow items (one, EPS-adjacent Pre-tax Income, spans both; totals to 19 unique line items as listed in the ticket).

## Method / sample

Pulled live `companyfacts` JSON directly from `data.sec.gov` (`User-Agent: Research research@example.com` header, required or SEC returns 403) for four filers spanning the three required industry categories:

| Ticker | Entity | CIK (10-digit) | Fiscal year end | Why sampled |
|---|---|---|---|---|
| AAPL | Apple Inc. | 0000320193 | ~late Sept | Standard tech mega-cap baseline |
| MSFT | Microsoft Corp | 0000789019 | June 30 | Standard tech mega-cap, non-calendar FY (stress-tests period alignment) |
| JPM | JPMorgan Chase & Co. | 0000019617 | Dec 31 | Bank/depository institution — unclassified balance sheet, different income-statement structure |
| SPG | Simon Property Group | 0001063761 | Dec 31 | REIT — unclassified balance sheet, UPREIT structure (minority interest), real-estate-specific asset tags |

Source fetched for each: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`.

All figures below are from `form: "10-K"` entries. For flow (duration) concepts I filtered to periods spanning 330–380 days (full fiscal year) to exclude quarterly/YTD noise; for instant (balance-sheet-date) concepts all 10-K entries are shown. Where two candidate tags cover the same fiscal period with identical values, that is called out explicitly as confirmation the filer re-tagged the same underlying line item rather than reporting two different things. `end` dates are XBRL period-end dates as filed, not calendar years. Data reflects what SEC had on file as of this research date (2026-08-26); some filers show FY2025/2026 10-K data already filed.

Following the existing research's convention: **fallback chains are merged by period, not by company** — for each fiscal period, take the highest-priority tag that has an entry for that specific period, don't let "found a match anywhere in the company's history" short-circuit the whole series.

---

## Income Statement

### Cost of Revenue

**Chain:** `CostOfGoodsAndServicesSold` → `CostOfRevenue` → `CostOfGoodsSold`
**Gap:** Not applicable to banks or REITs (no cost-of-revenue concept in their income statement — dash placeholder only, do not attempt fetch/derive).

Evidence:
- AAPL: `CostOfGoodsAndServicesSold` present continuously FY2007 (15,852,000,000) → FY2025 (220,960,000,000), 19 years. `CostOfRevenue` not present for AAPL at all.
- MSFT: used `CostOfRevenue` FY2008–FY2017 (11,598,000,000 → 34,261,000,000), then switched to `CostOfGoodsAndServicesSold` FY2016 onward — **identical value in the overlap year** (FY2017: both tags = 34,261,000,000), confirming a straight re-tag, not a definitional change. `CostOfGoodsAndServicesSold` continues through FY2026 (106,374,000,000).
- `CostOfGoodsSold` (no "AndServices") also briefly present for MSFT FY2014–FY2017 with values matching `CostOfRevenue`/`CostOfGoodsAndServicesSold` for the same periods — redundant duplicate tag, kept as tertiary fallback only for completeness.
- JPM: `CostOfRevenue`, `CostOfGoodsAndServicesSold`, `CostOfGoodsSold` all **NOT PRESENT** — confirmed genuine industry gap.
- SPG: same three tags all **NOT PRESENT** — confirmed genuine industry gap.

### Gross Profit

**Chain:** `GrossProfit` (directly reported — no derivation needed for filers that report it at all).
**Gap:** Not applicable to banks or REITs. Do **not** derive as Revenue − Cost of Revenue for these industries even though both operands might independently exist for some filers — a "gross profit" subtotal is not a meaningful/reported concept for financial institutions or real estate operators, and forcing the subtraction would produce a number the company itself never presents.

Evidence:
- AAPL: `GrossProfit` present continuously FY2007 (8,154,000,000) → FY2025 (195,201,000,000), reported directly every year — no need to derive from Revenue − CostOfGoodsAndServicesSold, since the direct tag exists and is presumably what feeds the printed income statement.
- MSFT: `GrossProfit` present continuously FY2008 → FY2026 (highest FY2026 = 225,465,000,000), directly reported.
- JPM: `GrossProfit` **NOT PRESENT**.
- SPG: `GrossProfit` **NOT PRESENT**.

### Operating Expenses

**Chain:** `OperatingExpenses` → `CostsAndExpenses`; **banks use a separate tag: `NoninterestExpense`.**
**Note:** This line item is not a uniform concept across industries — what counts as "operating expenses" differs structurally by industry, so the chain below should be read as "best available proxy for the operating-expense subtotal a normal 10-K reader would expect," not a single universal XBRL concept.

Evidence:
- AAPL: `OperatingExpenses` present continuously FY2007 (3,745,000,000) → FY2025 (62,151,000,000) — this is AAPL's R&D + SG&A subtotal, directly reported.
- MSFT: `OperatingExpenses` present FY2011 (27,205,000,000) → FY2026 (70,228,000,000).
- JPM: `OperatingExpenses` and `CostsAndExpenses` both **NOT PRESENT**. JPM instead reports `NoninterestExpense` continuously FY2007 (41,703,000,000) → FY2025 (95,640,000,000) — the standard bank-industry analog (compensation, occupancy, technology, etc., excluding interest expense and provision for credit losses). Recommend a bank-specific substitution here, same pattern as the existing research's revenue special-case for banks.
- SPG: `OperatingExpenses` **NOT PRESENT**, but `CostsAndExpenses` present continuously FY2007 (2,116,767,000) → FY2025 (3,189,109,000) — SPG's total-costs-and-expenses line (property operating, depreciation, G&A, etc., but note this excludes interest expense which SPG reports as a separate line below operating income — see SPG's `OperatingIncomeLoss` evidence below, which is consistent with Revenue − CostsAndExpenses).

### Operating Income

**Chain:** `OperatingIncomeLoss` (directly reported for filers that present a classified income statement with an operating-income subtotal).
**Gap:** Not applicable to banks — a bank's income statement doesn't have a conventional "operating income" subtotal (interest income/expense and noninterest income/expense are structured differently, without a single operating-income line before taxes). Dash placeholder only for banks.

Evidence:
- AAPL: `OperatingIncomeLoss` present continuously FY2007 (4,409,000,000) → FY2025 (133,050,000,000).
- MSFT: `OperatingIncomeLoss` present continuously FY2008 (22,271,000,000) → FY2026 (155,237,000,000).
- JPM: `OperatingIncomeLoss` **NOT PRESENT** — confirmed genuine bank-industry gap.
- SPG: `OperatingIncomeLoss` **is** present and continuous FY2007 (1,534,032,000) → FY2025 (3,175,396,000) — REITs, unlike banks, do report a conventional operating-income subtotal (interest expense sits below it as a separate financing cost). No REIT-specific gap here.

### Interest Expense

**Chain:** `InterestExpense` → `InterestExpenseNonoperating` (for filers that migrate to the "nonoperating" concept).
**Flag — recent-vintage gap for large filers:** both AAPL and JPM stopped tagging a bare, non-dimensional `InterestExpense` fact as of their FY2024 10-Ks in this sample. This looks like further income-statement/footnote condensation (e.g., Apple's income statement has folded interest into "Other income/expense, net" for years and by FY2024 may no longer tag total interest expense outside of a dimensional debt-footnote table, which the companyfacts default-facts view doesn't surface) rather than a true "this industry doesn't report it" gap — flag as an open risk for the most recent 1–2 fiscal years of any large-cap filer, not just AAPL/JPM specifically.

Evidence:
- AAPL: `InterestExpense` present FY2011 (0, i.e., explicitly reported as zero — AAPL had no debt yet) through FY2013 (136,000,000) → FY2023 (3,933,000,000); **no entry for FY2024 or FY2025** despite AAPL having grown its interest expense-generating debt load. No successor tag found among AAPL's other `Interest*` concepts (checked `InterestExpenseDebt`, `InterestExpenseNonoperating`, `InterestIncomeExpenseNet` — none present for AAPL in FY2024/2025).
- MSFT: `InterestExpense` present FY2008 (106,000,000) → FY2024 (2,935,000,000), then MSFT switches to `InterestExpenseNonoperating` starting FY2023 (**identical values in the FY2023/FY2024 overlap**: both tags = 1,968,000,000 for FY2023, 2,935,000,000 for FY2024) — confirms `InterestExpenseNonoperating` is the live successor tag for MSFT, continuing through FY2026 (3,051,000,000). This is the one filer in the sample where the fallback resolves the "current" figure cleanly.
- JPM: `InterestExpense` present FY2007 (44,981,000,000) → FY2023 (81,321,000,000, note the sharp jump from FY2022's 26,097,000,000 — consistent with the 2023 rate-hiking cycle sharply raising bank funding costs); **no entry for FY2024 or FY2025**. No successor tag found among JPM's interest tags (`InterestExpenseDeposits`, `InterestExpenseShortTermBorrowings`, `InterestExpenseLongTermDebt` all exist as *components* but summing components was out of scope for this pass — flagged as a possible future fallback if the aggregate gap persists).
- SPG: `InterestExpense` present continuously FY2007 (945,852,000) → FY2025 (974,835,000) — **no gap for SPG**, REITs keep reporting this cleanly since debt service is central to their income statement.

### Pre-tax Income

**Chain:** `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` → `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`.
**Gap / derived fallback for REITs:** Neither tag is present for SPG. Recommend a **derived** fallback of `NetIncome + IncomeTaxExpenseBenefit` when no direct pre-tax tag exists — this is an exact accounting identity (not an approximation) as long as there are no discontinued operations or NCI complications in the specific period, which is a reasonable default assumption for a normalized summary view.

Evidence:
- AAPL: `...MinorityInterestAndIncomeLossFromEquityMethodInvestments` covers FY2007 (5,008,000,000) → FY2012 (55,763,000,000); `...ExtraordinaryItemsNoncontrollingInterest` covers FY2011 (34,205,000,000) → FY2025 (132,729,000,000) — **identical values in the FY2011/FY2012 overlap** (34,205,000,000 and 55,763,000,000 respectively), confirming the same underlying subtotal under a renamed tag.
- MSFT: same two-tag pattern, overlap at FY2020 (53,036,000,000 both tags) confirms the same identity.
- JPM: same two-tag pattern, overlap at FY2018/FY2019/FY2020 confirms the same identity (e.g. FY2020 = 35,407,000,000 both tags).
- SPG: **neither tag present**. Checked SPG's full `us-gaap` key list for any "BeforeIncomeTax" variant — none found. SPG does report `IncomeTaxExpenseBenefit` directly (small values, consistent with REIT tax-exempt-at-the-entity-level status) and `NetIncomeLoss`/`ProfitLoss` (per the existing research), so the derived sum is available as a fallback.

### Income Tax (Provision)

**Chain:** `IncomeTaxExpenseBenefit` — no fallback needed, confirmed stable across all 4 sampled filers across all 3 industries.

Evidence:
- AAPL: continuous FY2007 (1,512,000,000) → FY2025 (20,719,000,000).
- MSFT: continuous FY2008 (6,133,000,000) → FY2026 (32,185,000,000).
- JPM: continuous FY2007 (7,440,000,000, note FY2008 = −926,000,000, i.e. a net tax *benefit* during the financial crisis) → FY2025 (15,547,000,000).
- SPG: continuous FY2007 (−11,322,000) → FY2025 (20,279,000) — values are characteristically small/near-zero for a REIT (some years even negative, i.e. a tax benefit) since REITs are largely pass-through entities for federal tax purposes and only owe tax on any taxable-REIT-subsidiary income; this is expected behavior, not a data-quality problem.

### EPS Basic

**Chain:** `EarningsPerShareBasic` — no fallback needed, confirmed stable across all 4 filers/3 industries (consistent with the existing research's finding for the original 5-metric set).

Evidence: continuous, one entry per fiscal year, for AAPL (FY2007 4.04 → FY2025 7.49), MSFT (FY2008 1.90 → FY2026 18.00), JPM (FY2007 4.38 → FY2025 20.05), SPG (FY2007 1.96 → FY2025 14.17). No alternate tags encountered as necessary; SPG also has a distinct `IncomeLossFromContinuingOperationsPerBasicShare` tag but only for 3 early years (FY2007–FY2009) with values that differ slightly from `EarningsPerShareBasic` in the same periods (2.09/1.88/1.06 vs. 1.96/1.88/1.06) — this is a different, narrower concept (excludes discontinued operations) and should not be used as a substitute.

### EPS Diluted

**Chain:** `EarningsPerShareDiluted` — no fallback needed, same stability as EPS Basic.

Evidence: continuous for all 4 filers, e.g. AAPL FY2007 3.93 → FY2025 7.46; MSFT FY2008 1.87 → FY2026 17.95; JPM FY2007 4.33 → FY2025 20.02; SPG FY2007 1.95 → FY2025 14.17.

---

## Balance Sheet

### Cash & Cash Equivalents

**Chain:** `CashAndCashEquivalentsAtCarryingValue` → `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`.
**Rationale:** This mirrors the same 2018-era ASU-driven tag transition (restricted cash folded into the cash-flow-statement cash balance) seen elsewhere; the newer combined tag is the one filers switch to going forward.

Evidence:
- AAPL: `CashAndCashEquivalentsAtCarryingValue` continuous FY2006 (6,392,000,000) → FY2025 (35,934,000,000) — AAPL never actually needed the fallback in this sample (both tags present with identical values for overlapping periods, e.g. FY2025 = 35,934,000,000 under both).
- MSFT: same pattern, `CashAndCashEquivalentsAtCarryingValue` continuous through FY2026, values match `CashCashEquivalentsRestrictedCash...` in overlap.
- JPM: `CashAndCashEquivalentsAtCarryingValue` only covers FY2015–FY2018 (4 periods) — **genuine gap** without the fallback. `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` covers FY2016–FY2025 continuously, with **identical values in the FY2016/FY2017/FY2018 overlap** (e.g. FY2016 = 391,154,000,000 under both tags) — confirms JPM needs the fallback to get pre-2016 and post-2018 coverage in one series (note: FY2015 itself would still be missing from *either* tag alone in this sample — worth a spot-check against JPM's actual FY2015 10-K face if that year matters).
- SPG: `CashAndCashEquivalentsAtCarryingValue` continuous FY2006 → FY2025, fallback tag also present FY2015 onward with matching values — same pattern as AAPL/MSFT.

### Total Current Assets

**Chain:** `AssetsCurrent` — no fallback found or needed for filers that report a classified balance sheet.
**Gap:** **Not applicable to banks or REITs.** Both JPM and SPG show `AssetsCurrent` **NOT PRESENT** — banks and real-estate companies use an unclassified (non-current/current) balance sheet presentation, so there is no "total current assets" concept to report at all. This should render as the existing dash placeholder for these industries, not attempt any derived computation (there's no reliable way to reconstruct a current/non-current split from an unclassified balance sheet's tags).

Evidence: AAPL continuous FY2008 (32,311,000,000) → FY2025 (147,957,000,000); MSFT continuous FY2009 (49,280,000,000) → FY2026 (207,710,000,000); JPM and SPG both confirmed absent.

### Property/Plant/Equipment (net)

**Chain:** `PropertyPlantAndEquipmentNet`; **REITs need a different tag: `RealEstateInvestmentPropertyNet`** (with `RealEstateInvestmentPropertyAtCost` as the gross/pre-depreciation figure, not a substitute for the net figure).
**Flag — recent-vintage gap for banks:** JPM's `PropertyPlantAndEquipmentNet` stops after FY2022 — no entry for FY2023, FY2024, or FY2025 despite JPM plainly still owning premises and equipment. No successor tag found among JPM's other "Premises"/"PropertyPlant" concepts. This looks like JPM folded PP&E into a combined "other assets" balance-sheet line starting with its FY2023 10-K and stopped tagging it as a standalone XBRL fact — flag as an open, recent-vintage gap for banks specifically (not a REIT/tech issue).

Evidence:
- AAPL: `PropertyPlantAndEquipmentNet` present FY2011 (7,777,000,000) → FY2025 (49,834,000,000) — note no entries found before FY2011 in this sample (early-2010s XBRL tagging maturity, not treated as a gap worth a fallback given it predates the app's likely useful history window).
- MSFT: continuous FY2009 (7,535,000,000) → FY2026 (313,076,000,000 — the huge recent jump reflects MSFT's AI-datacenter capex buildout).
- JPM: FY2008 (10,045,000,000) → FY2022 (27,734,000,000), then **gap** FY2023–FY2025.
- SPG: `PropertyPlantAndEquipmentNet` **NOT PRESENT** at all. `RealEstateInvestmentPropertyNet` present and continuous instead, FY2008 (19,021,430,000) → FY2025 (30,244,557,000) — this is SPG's real-estate-specific "PP&E" analog (investment property net of accumulated depreciation). `RealEstateInvestmentPropertyAtCost` also present (gross figure, e.g. FY2025 = 50,946,067,000) — useful as a cross-check but not a substitute for the net figure.

### Goodwill & Intangible Assets

**Derived — no single tag reports this combined line for any sampled filer.** Compute as `Goodwill + Intangibles`, where Intangibles chain = `IntangibleAssetsNetExcludingGoodwill` → `FiniteLivedIntangibleAssetsNet` (+ `IndefiniteLivedIntangibleAssetsExcludingGoodwill` additively, if both finite- and indefinite-lived intangibles are separately tagged for a given filer/period — check for double-counting if `IntangibleAssetsNetExcludingGoodwill` already represents the combined total, which it does for AAPL in the years it's present).
**Flag — recent-vintage gap for AAPL specifically:** both `Goodwill` and `IntangibleAssetsNetExcludingGoodwill` stop for AAPL after FY2017. AAPL is well known for an extremely condensed balance sheet; from FY2018 on it appears AAPL folds goodwill and intangibles into "Other non-current assets" and no longer tags them as standalone XBRL facts (its footnote acquisition disclosures may still tag `Goodwill` but only within a dimensional context this default-facts pull doesn't surface). This is a real, current-day gap for AAPL, not a historical-data artifact — flag clearly since AAPL is the most likely test filer for this app.
**Gap:** Intangibles specifically are not meaningfully present for SPG (REIT) — `IntangibleAssetsNetExcludingGoodwill`, `FiniteLivedIntangibleAssetsNet`, and `IndefiniteLivedIntangibleAssetsExcludingGoodwill` are all **NOT PRESENT** for SPG, though SPG does carry a small, constant `Goodwill` balance (20,098,000 unchanged every year FY2009–FY2025 — an acquisition-era holdover, immaterial). Treat REIT intangibles as effectively a dash/zero, not a fetch failure.

Evidence:
- AAPL: `Goodwill` FY2008 (207,000,000) → FY2017 (5,717,000,000), then gap. `IntangibleAssetsNetExcludingGoodwill` FY2008 (285,000,000) → FY2017 (2,298,000,000), then gap. `FiniteLivedIntangibleAssetsNet` also present FY2012–FY2017 with values matching `IntangibleAssetsNetExcludingGoodwill` in the same periods (e.g. FY2017 both = 2,298,000,000/2,198,000,000 — close but not identical, likely `IntangibleAssetsNetExcludingGoodwill` = finite-lived + a small indefinite-lived residual, confirmed by `IndefiniteLivedIntangibleAssetsExcludingGoodwill` = 100,000,000 flat for AAPL FY2013–FY2017, i.e. 2,198,000,000 + 100,000,000 = 2,298,000,000 exactly).
- MSFT: `Goodwill` continuous FY2008 (12,108,000,000) → FY2026 (119,651,000,000). `IntangibleAssetsNetExcludingGoodwill` present as a tag but **zero full-year 10-K entries** for MSFT — MSFT instead uses `FiniteLivedIntangibleAssetsNet` directly, continuous FY2009 (1,759,000,000) → FY2026 (18,609,000,000). No `IndefiniteLivedIntangibleAssetsExcludingGoodwill` for MSFT (not present) — so for MSFT the intangibles chain resolves to `FiniteLivedIntangibleAssetsNet` alone.
- JPM: `Goodwill` continuous FY2007 (45,270,000,000) → FY2025 (52,731,000,000). `IntangibleAssetsNetExcludingGoodwill` **NOT PRESENT**; `FiniteLivedIntangibleAssetsNet` present but only FY2022–FY2025 (707,000,000 → 1,300,000,000); `IndefiniteLivedIntangibleAssetsExcludingGoodwill` present and continuous FY2010 (600,000,000) → FY2025 (1,300,000,000) — for JPM, both finite- and indefinite-lived tags need to be summed for years both exist (FY2022–2025), and only the indefinite-lived tag is available for FY2010–2021 (finite-lived intangibles for JPM in that window presumably immaterial/untagged).
- SPG: `Goodwill` = 20,098,000 flat FY2009–FY2025; all three intangibles tags absent.

### Total Assets

**Chain:** `Assets` — no fallback needed, confirmed stable across all 4 filers/3 industries (already established as reliable in the existing research's context for Revenue cross-checks; re-confirmed here directly).

Evidence: AAPL continuous FY2008 (36,171,000,000) → FY2025 (359,241,000,000); MSFT continuous FY2009 (77,888,000,000) → FY2026 (758,376,000,000); JPM continuous FY2008 (2,175,052,000,000) → FY2025 (4,424,900,000,000); SPG continuous FY2008 (23,422,749,000) → FY2025 (40,606,466,000).

### Total Current Liabilities

**Chain:** `LiabilitiesCurrent` — no fallback found or needed for classified-balance-sheet filers.
**Gap:** **Not applicable to banks or REITs**, same reasoning as Total Current Assets — both JPM and SPG show `LiabilitiesCurrent` **NOT PRESENT**. Dash placeholder only.

Evidence: AAPL continuous FY2008 (14,092,000,000) → FY2025 (165,631,000,000); MSFT continuous FY2009 (27,034,000,000) → FY2026 (168,825,000,000); JPM and SPG both confirmed absent.

### Long-term Debt

**Chain:** `LongTermDebtNoncurrent` → `LongTermDebt` → `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` → `DebtAndCapitalLeaseObligations`.
**Note:** This is the longest fallback chain found in this research — four tags are genuinely needed to get continuous coverage across the sample's three industries, each filer settling on a different combination.

Evidence:
- AAPL: `LongTermDebtNoncurrent` present FY2014 (28,987,000,000) → FY2025 (78,328,000,000); `LongTermDebt` also present FY2012 (0) → FY2025 (90,678,000,000) with a **different, larger value in the same periods** (e.g. FY2025: `LongTermDebtNoncurrent` = 78,328,000,000 vs. `LongTermDebt` = 90,678,000,000) — `LongTermDebt` appears to include the current portion of long-term debt for AAPL, so `LongTermDebtNoncurrent` is the more precise "long-term" figure when both exist; keep it as the higher-priority tag.
- MSFT: same two-tag pattern; `LongTermDebtNoncurrent` continuous FY2009–FY2026, `LongTermDebt` also continuous but consistently includes current maturities (e.g. FY2026: `LongTermDebtNoncurrent` = 31,067,000,000 vs. `LongTermDebt` = 40,294,000,000).
- JPM: `LongTermDebtNoncurrent` **NOT PRESENT** at all. `LongTermDebt` covers only FY2008–FY2013 (270,683,000,000 → 267,889,000,000), then **stops**. `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` picks up FY2013 (267,889,000,000 — **identical value to `LongTermDebt`'s last FY2013 entry**, confirming a straight re-tag) through FY2025 (435,206,000,000).
- SPG: `LongTermDebtNoncurrent` **NOT PRESENT**. `LongTermDebt` covers FY2010–FY2011 and then FY2015–FY2025, with a **genuine 3-year hole for FY2012–FY2014**. `DebtAndCapitalLeaseObligations` covers FY2008–FY2015 (18,042,532,000 → 22,502,173,000), filling exactly the FY2012–FY2014 hole (FY2012/2013/2014 values not identical to a same-period `LongTermDebt` figure since `LongTermDebt` has no entry for those years to compare against, but the tag's values are continuous with the surrounding years' `LongTermDebt` trend, e.g. FY2011 `LongTermDebt` = 18,421,368,000 vs. FY2011 `DebtAndCapitalLeaseObligations` = 17,473,760,000 — close but not identical, likely a scope difference of ~$1B possibly related to capital lease obligations being included/excluded slightly differently; treat as "close enough to bridge the gap" rather than an exact identity).

### Total Liabilities

**Chain:** `Liabilities` — no fallback needed, confirmed stable across all 4 filers/3 industries.

Evidence: AAPL continuous FY2008 (18,542,000,000) → FY2025 (285,508,000,000); MSFT continuous FY2010 (39,938,000,000) → FY2026 (315,989,000,000); JPM continuous FY2008 (2,008,168,000,000) → FY2025 (4,062,462,000,000); SPG continuous FY2008 (19,664,661,000) → FY2025 (33,901,073,000).

### Total Stockholders' Equity

**Chain:** `StockholdersEquity` — no fallback needed for any of the 4 sampled filers, present and continuous in every case.
**Caveat — UPREIT/NCI structures:** for SPG specifically, `StockholdersEquity` (parent-only) diverges materially from `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (parent + minority interest in the operating partnership) — e.g. FY2025: `StockholdersEquity` = 5,208,268,000 vs. the NCI-inclusive figure = 6,472,087,000, a ~$1.26B/24% gap. This is analogous to the existing research's ZION preferred-stock EPS-numerator finding: **do not substitute the NCI-inclusive tag for "total stockholders' equity"** — it answers a different question (total equity capital of the consolidated entity including minority holders, not the parent company's own equity). Recommend keeping `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` only as a last-resort fallback for the rare filer (typically an LP/UPREIT umbrella entity) that doesn't report a parent-only `StockholdersEquity` figure at all — none of the 4 sampled filers actually needed this fallback, but it's cheap to keep in the chain.

Evidence: AAPL continuous FY2006 (9,984,000,000) → FY2025 (73,733,000,000); MSFT continuous FY2008 (36,286,000,000) → FY2026 (442,387,000,000); JPM continuous FY2008 (166,884,000,000) → FY2025 (362,438,000,000); SPG continuous FY2008 (2,612,998,000) → FY2025 (5,208,268,000).

---

## Cash Flow Statement

### Operating Cash Flow

**Chain:** `NetCashProvidedByUsedInOperatingActivities` — no fallback needed, confirmed stable and continuous across all 4 filers/3 industries (the cleanest single-tag chain found in this entire research pass).

Evidence: AAPL continuous FY2007 (5,470,000,000) → FY2025 (111,482,000,000); MSFT continuous FY2008 (21,612,000,000) → FY2026 (182,935,000,000); JPM continuous FY2007 (−110,560,000,000, a large financing-crisis-era outflow) → FY2025 (−147,782,000,000, note JPM's operating cash flow is frequently negative in recent years due to trading-securities/loan-portfolio movements — this is normal for a bank, not a data error); SPG continuous FY2007 (1,559,432,000) → FY2025 (4,136,551,000).

### Capital Expenditures

**Chain:** `PaymentsToAcquirePropertyPlantAndEquipment` → `PaymentsToAcquireProductiveAssets`.
**Gap:** **Not applicable to banks.** JPM shows both candidate tags **NOT PRESENT**, and a broader search of JPM's `us-gaap` facts for any "PaymentsFor.../PaymentsTo..." concept related to premises/equipment/capital turned up nothing — banks in this sample simply don't tag purchases of premises/equipment as a discrete cash-flow line (likely folded into "other investing activities, net"). Dash placeholder only for banks.

Evidence:
- AAPL: `PaymentsToAcquirePropertyPlantAndEquipment` present FY2013 (8,165,000,000) → FY2025 (12,715,000,000); `PaymentsToAcquireProductiveAssets` covers the earlier years FY2007 (735,000,000) → FY2014 (9,571,000,000), with an **identical value in the FY2012/FY2013 overlap** (both tags = 8,295,000,000 for FY2012, 8,165,000,000 for FY2013) confirming a straight re-tag.
- MSFT: `PaymentsToAcquirePropertyPlantAndEquipment` present and continuous FY2008 (3,182,000,000) → FY2026 (115,948,000,000, reflecting MSFT's AI-datacenter buildout) — no fallback needed for MSFT.
- JPM: both tags absent, confirmed gap.
- SPG: `PaymentsToAcquirePropertyPlantAndEquipment` **NOT PRESENT**; SPG instead uses `PaymentsToAcquireProductiveAssets` exclusively, continuous FY2014 (796,736,000) → FY2025 (934,346,000) — the REIT's real-estate-development/improvement capex line. (No pre-2014 data found for SPG under any capex-shaped tag in this sample; treat FY2007–FY2013 SPG capex as unavailable rather than force a fallback that doesn't exist.)

### Investing Cash Flow

**Chain:** `NetCashProvidedByUsedInInvestingActivities` — no fallback needed, confirmed stable and continuous across all 4 filers/3 industries.

Evidence: AAPL continuous FY2007 (−3,249,000,000) → FY2025 (15,195,000,000, a rare positive/net-inflow year); MSFT continuous FY2008 (−4,587,000,000) → FY2026 (−139,500,000,000); JPM continuous FY2007 (−74,188,000,000) → FY2025 (−265,565,000,000); SPG continuous FY2007 (−2,049,576,000) → FY2025 (−1,600,704,000).

### Financing Cash Flow

**Chain:** `NetCashProvidedByUsedInFinancingActivities` — no fallback needed, confirmed stable and continuous across all 4 filers/3 industries.

Evidence: AAPL continuous FY2007 (739,000,000) → FY2025 (−120,686,000,000, reflecting AAPL's large buyback/dividend outflows); MSFT continuous FY2008 (−12,934,000,000) → FY2026 (−52,546,000,000); JPM continuous FY2007 (184,056,000,000) → FY2025 (269,533,000,000); SPG continuous FY2007 (62,766,000) → FY2025 (−3,113,045,000).

### Net Change in Cash

**Chain:** `CashAndCashEquivalentsPeriodIncreaseDecrease` → `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect` → `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect`.
**Note:** The 3-tag chain reflects the same 2018-era restricted-cash ASU transition as the balance-sheet "Cash & Cash Equivalents" chain, plus a further split between filers with and without meaningful foreign-currency cash exposure.

Evidence:
- AAPL: `CashAndCashEquivalentsPeriodIncreaseDecrease` covers FY2007 (2,960,000,000) → FY2018 (5,624,000,000); `...IncludingExchangeRateEffect` picks up FY2017 (−195,000,000) → FY2025 (5,991,000,000) — **identical values in the FY2017/FY2018 overlap** (−195,000,000 and 5,624,000,000 respectively) confirming the re-tag.
- MSFT: same two-tag pattern, overlap at FY2018/FY2019 confirms identity (4,283,000,000 and −590,000,000 respectively under both tags).
- JPM: same two-tag pattern, overlap at FY2017/FY2018 confirms identity (40,150,000,000 and −152,511,000,000 respectively under both tags).
- SPG: `CashAndCashEquivalentsPeriodIncreaseDecrease` covers FY2007–FY2017; but the "...IncludingExchangeRateEffect" tag has **zero full-year 10-K entries for SPG** — SPG instead uses the "...ExcludingExchangeRateEffect" variant (unsurprising for a purely domestic U.S. REIT with no FX exposure), continuous FY2016 (−141,075,000) → FY2025 (−577,198,000), with an **identical value in the FY2016/FY2017 overlap** against the older tag (−141,075,000 and 922,250,000 respectively) confirming the re-tag. This third tag variant must be in the chain or SPG-like domestic-only filers will silently lose all post-2015 net-change-in-cash data.

---

## Summary table

| # | Line item | Primary tag | Fallback chain (in order) | Derived? | Known gaps |
|---|---|---|---|---|---|
| 1 | Cost of Revenue | `CostOfGoodsAndServicesSold` | → `CostOfRevenue` → `CostOfGoodsSold` | No | Banks, REITs: not applicable |
| 2 | Gross Profit | `GrossProfit` | (none needed) | No — do not derive for banks/REITs | Banks, REITs: not applicable |
| 3 | Operating Expenses | `OperatingExpenses` | → `CostsAndExpenses`; banks → `NoninterestExpense` | No | None (industry-specific tag, not a true gap) |
| 4 | Operating Income | `OperatingIncomeLoss` | (none needed) | No | Banks: not applicable |
| 5 | Interest Expense | `InterestExpense` | → `InterestExpenseNonoperating` | No | **Flag:** AAPL & JPM missing FY2024/FY2025 in sample — likely broader large-filer disclosure condensation, not industry-specific |
| 6 | Pre-tax Income | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` | → `...MinorityInterestAndIncomeLossFromEquityMethodInvestments` | REITs: yes — `NetIncome + IncomeTaxExpenseBenefit` | REITs: no direct tag, use derived fallback |
| 7 | Income Tax (Provision) | `IncomeTaxExpenseBenefit` | (none needed) | No | None — small/near-zero values for REITs are expected, not a gap |
| 8 | EPS Basic | `EarningsPerShareBasic` | (none needed) | No | None |
| 9 | EPS Diluted | `EarningsPerShareDiluted` | (none needed) | No | None |
| 10 | Cash & Cash Equivalents | `CashAndCashEquivalentsAtCarryingValue` | → `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` | No | None |
| 11 | Total Current Assets | `AssetsCurrent` | (none found) | No | Banks, REITs: not applicable (unclassified balance sheet) |
| 12 | PP&E (net) | `PropertyPlantAndEquipmentNet` | REITs → `RealEstateInvestmentPropertyNet` | No | **Flag:** banks (JPM) missing FY2023–FY2025 in sample — recent-vintage gap |
| 13 | Goodwill & Intangible Assets | — | `Goodwill` + (`IntangibleAssetsNetExcludingGoodwill` → `FiniteLivedIntangibleAssetsNet` [+ `IndefiniteLivedIntangibleAssetsExcludingGoodwill` if both present]) | Yes — sum of two components, no combined tag observed | **Flag:** AAPL missing both components FY2018+ (condensed balance sheet); REITs: intangibles component effectively absent/immaterial |
| 14 | Total Assets | `Assets` | (none needed) | No | None |
| 15 | Total Current Liabilities | `LiabilitiesCurrent` | (none found) | No | Banks, REITs: not applicable (unclassified balance sheet) |
| 16 | Long-term Debt | `LongTermDebtNoncurrent` | → `LongTermDebt` → `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` → `DebtAndCapitalLeaseObligations` | No | None (4-tag chain resolves all 3 industries) |
| 17 | Total Liabilities | `Liabilities` | (none needed) | No | None |
| 18 | Total Stockholders' Equity | `StockholdersEquity` | → `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (last resort only) | No | None — do not prefer the NCI-inclusive variant when the parent-only tag exists (UPREITs like SPG diverge materially) |
| 19a | Operating Cash Flow | `NetCashProvidedByUsedInOperatingActivities` | (none needed) | No | None |
| 19b | Capital Expenditures | `PaymentsToAcquirePropertyPlantAndEquipment` | → `PaymentsToAcquireProductiveAssets` | No | Banks: not applicable |
| 19c | Investing Cash Flow | `NetCashProvidedByUsedInInvestingActivities` | (none needed) | No | None |
| 19d | Financing Cash Flow | `NetCashProvidedByUsedInFinancingActivities` | (none needed) | No | None |
| 19e | Net Change in Cash | `CashAndCashEquivalentsPeriodIncreaseDecrease` | → `...RestrictedCash...IncludingExchangeRateEffect` → `...RestrictedCash...ExcludingExchangeRateEffect` | No | None (3-tag chain needed for domestic-only filers like SPG) |

### Items to treat as dash-placeholder-only for specific industries (no fetch attempt should be made)

- **Banks/depository institutions:** Cost of Revenue, Gross Profit, Operating Income, Total Current Assets, Total Current Liabilities, Capital Expenditures.
- **REITs:** Cost of Revenue, Gross Profit, Total Current Assets, Total Current Liabilities. (Note: unlike banks, REITs in this sample *do* report Operating Income and Capital Expenditures.)

### Items needing an explicit recent-data-gap warning (not an industry rule — flag and move on, don't build special-case logic around it)

- **Interest Expense** — AAPL and JPM both lack a bare `InterestExpense`/successor fact for FY2024–FY2025 in this sample.
- **PP&E (net)** — JPM lacks `PropertyPlantAndEquipmentNet` for FY2023–FY2025.
- **Goodwill & Intangible Assets** — AAPL lacks both `Goodwill` and any intangibles tag for FY2018 onward.

These three are presented as "gaps in the most recent 1–3 fiscal years for otherwise well-covered mega-cap filers," distinct from the clean, permanent industry-level gaps (current assets/liabilities for banks/REITs, cost of revenue for banks/REITs, etc.). Tickets 05–07 should treat the industry-level gaps as expected/permanent (dash placeholder, no retry logic needed) and the recent-vintage gaps as "may reappear for any large filer that further condenses its financial statement presentation" — i.e., the fallback chains above should degrade gracefully to a dash rather than error when even the full chain comes up empty for a recent period.

# EDGAR XBRL Tag Fallback Mapping — Findings

Resolves the three "Remaining work" items in `.scratch/ticker-explorer/issues/02-edgar-tag-fallback-mapping.md`.

## Method / sample

Pulled live `companyfacts` JSON directly from `data.sec.gov` (User-Agent header required) for six filers, chosen to stress-test AAPL's pattern against a non-calendar-fiscal-year mega-cap, a mid-cap retailer, a regional bank (very different revenue structure), and a filer that never adopted the "new" revenue tag at all:

| Ticker | Entity | CIK (10-digit) | Fiscal year end | Why sampled |
|---|---|---|---|---|
| AAPL | Apple Inc. | 0000320193 | ~late Sept | Baseline (from prior session) |
| MSFT | Microsoft Corp | 0000789019 | June 30 | Non-calendar FY, mega-cap |
| KSS | Kohl's Corp | 0000885639 | ~late Jan/early Feb | Mid-cap retailer, calendar-ish FY |
| ZION | Zions Bancorporation, N.A. | 0000109380 | Dec 31 | Regional bank — different revenue/NI structure |
| T | AT&T Inc. | 0000732717 | Dec 31 | Large filer that never fully migrated its revenue tag |

Sources fetched (all with `User-Agent: research <contact>`):
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` (AAPL)
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json` (MSFT)
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000885639.json` (KSS)
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000109380.json` (ZION)
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000732717.json` (T)
- `https://www.sec.gov/files/company_tickers.json` (ticker → CIK lookup)

All figures below are annual (`form: "10-K"`, `fp: "FY"`, duration ≥ ~300 days) unless noted. `end` dates are the XBRL period-end/instant dates as reported by SEC, not calendar years.

---

## Decision 1 — Net income / EPS / dividends: NOT uniformly stable; needs its own fallback chain

**Decided chain:**
- **Net income:** try `us-gaap:NetIncomeLoss` first, then `us-gaap:ProfitLoss`, merged **by period** (take whichever tag has an entry for a given fiscal-year end; don't pick one tag globally for the whole company). Do **not** substitute `NetIncomeLossAvailableToCommonStockholdersBasic`/`...Diluted` for "net income" — that's a different, smaller number (net of preferred dividends/NCI), useful only as an EPS-numerator cross-check.
- **EPS (basic/diluted):** `EarningsPerShareBasic` / `EarningsPerShareDiluted` alone are sufficient — no fallback needed, confirmed stable across all 5 non-AAPL-adjacent filers checked.
- **Dividends per share:** try `us-gaap:CommonStockDividendsPerShareDeclared` first, then `us-gaap:CommonStockDividendsPerShareCashPaid`, merged **by period** — this is *not* as stable as AAPL suggested; two of five sampled filers switch tags mid-history.

**Evidence:**

*Net income — clean single-tag filers:*
- AAPL `NetIncomeLoss`: 19 continuous annual entries, FY2007-09-29 → FY2025-09-27, no `ProfitLoss` tag exists at all.
- MSFT `NetIncomeLoss`: 19 continuous annual entries, FY2008-06-30 → FY2026-06-30, no `ProfitLoss` tag exists at all.
- KSS `NetIncomeLoss`: 139 total entries / continuous annual coverage FY2007-02-04→2008-02-02 through FY2025-02-02→2026-01-31, no gaps. `ProfitLoss` *also* appears for KSS but only FY2016–FY2025, with **identical values** to `NetIncomeLoss` for every overlapping year (e.g. FY2017 both = 859,000,000) — a harmless redundant duplicate tag, not a gap risk for KSS.

*Net income — genuine gap requiring the fallback (the analogue to revenue's ASC-606 problem):*
- **ZION** `NetIncomeLoss` has a **real 4-year hole**: covers FY2008–FY2013 (e.g. FY2008 = ‑266,269,000; FY2013 = 263,791,000), then **nothing for FY2014, FY2015, FY2016, FY2017**, then resumes FY2018 (884,000,000) through FY2025.
- ZION `ProfitLoss` covers FY2008–FY2019 **continuously**, including exactly the FY2014–FY2017 years `NetIncomeLoss` is missing (FY2014=398,462,000; FY2015=309,000,000; FY2016=469,000,000; FY2017=592,000,000), then stops after FY2019.
- FY2018 and FY2019 are dual-tagged with identical values under both tags (FY2018: both = 884,000,000; FY2019: both = 816,000,000), confirming they're the same underlying figure — Zions just changed which XBRL tag its filing agent used, twice, over 12 years. A single-tag (`NetIncomeLoss`-only) pull for a regional bank like Zions would silently drop 4 fiscal years of net income.
- T (AT&T): both `NetIncomeLoss` and `ProfitLoss` present and fully continuous/identical for all 19 years FY2007–FY2025 — another case of harmless dual-tagging, no gap.

*Distinct "available to common" concept (ZION, relevant because of TARP-era preferred stock):*
- ZION `NetIncomeLossAvailableToCommonStockholdersBasic` diverges materially from `NetIncomeLoss`/`ProfitLoss` in preferred-stock years, e.g. FY2010: `NetIncomeLoss` = ‑292,728,000 vs `NetIncomeLossAvailableToCommonStockholdersBasic` = ‑412,505,000 (~$120M gap = preferred dividends/accretion). Confirms this tag is not interchangeable with "net income" — it's the EPS numerator, not the headline figure.

*EPS — stable across all 5 filers, no gaps observed:*
- AAPL, MSFT, KSS, ZION, T: `EarningsPerShareBasic` and `EarningsPerShareDiluted` each show one entry per fiscal year, full history, no missing years, no alternate tags encountered.

*Dividends — genuine tag-switch gaps, comparable in kind to the revenue problem:*
- AAPL: `CommonStockDividendsPerShareDeclared` only, continuous FY2010–FY2025 (FY2010 = 0, i.e. dividend reinstated that year); `CommonStockDividendsPerShareCashPaid` doesn't exist for AAPL.
- MSFT: `CommonStockDividendsPerShareDeclared` only, continuous FY2008–FY2026 (0.44 → 3.64); `CashPaid` doesn't exist for MSFT.
- T: `CommonStockDividendsPerShareDeclared` only, continuous FY2007–FY2025 (1.61 → 1.11); `CashPaid` doesn't exist for T.
- **KSS**: `CommonStockDividendsPerShareDeclared` covers only FY2012–FY2016 (5 years) then **stops entirely**. `CommonStockDividendsPerShareCashPaid` covers FY2012–FY2026 (15 years) continuously, with identical values to `Declared` in the overlap years (e.g. FY2013 both = 1.28; FY2015 both = 1.56). A `Declared`-only pull would miss all KSS dividend data from FY2017 onward.
- **ZION**: `CommonStockDividendsPerShareCashPaid` covers FY2008–FY2016 (dividend cut to $0 FY2013–FY2016 post-financial-crisis, consistent with Fed distribution restrictions), gap for FY2017 (see below), then `CommonStockDividendsPerShareDeclared` takes over FY2018–FY2021, both tags overlap and agree FY2022–FY2023 (both = 1.58 and 1.64), then `CashPaid` alone resumes FY2024–FY2025. Neither tag alone spans the full history.
- **Genuine annual-fact gap, not just a tag-name issue**: ZION FY2017 has **no full-year 10-K entry under either dividend tag** — only three quarterly 10-Q entries exist (Q1=0.08, Q2 cumulative=0.16, Q3 cumulative=0.28, no Q4/annual figure filed under either tag). This is a case where even the two-tag chain needs a last-resort fallback of summing quarterly `10-Q` facts to reconstruct the annual figure.

---

## Decision 2 — Revenue fallback chain (extends AAPL's 2-tag version to 4 tags + a bank-specific exception)

**Decided priority order** (evaluate **per fiscal period**, not per company — take the highest-priority tag that has an entry for that specific period; don't let "found a match anywhere" short-circuit the whole series):

1. `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` — the ASC-606-era tag, present for essentially all recent (~FY2017/2018 onward) filers in the sample.
2. `us-gaap:Revenues` — the generic aggregate-revenue tag. Needed even when tag 1 exists, because some large filers (AT&T) use `Revenues` as their *sole, continuous* total-revenue tag across the entire ASC-606 transition and never adopted tag 1 for the consolidated top line.
3. `us-gaap:SalesRevenueNet` — the dominant pre-ASC-606 tag, needed to extend history back before ~2017–2018 for filers that deprecated it after adopting the new standard.
4. `us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax` — **not observed** in any of the 6 sampled filers, but it's a real taxonomy concept for filers presenting revenue inclusive of pass-through/excise taxes; keep as a low-priority fallback rather than omitting it, since it costs nothing to check.
5. **Exclude** component/segment-level tags from this "total revenue" chain even though they're common: `SalesRevenueGoodsNet`, `SalesRevenueServicesNet`/`SalesRevenueServicesGross`, `OtherSalesRevenueNet`. These represent a slice of the business (product-only or service-only), not consolidated revenue — using one alone understates total revenue. (Observed: MSFT `SalesRevenueGoodsNet` FY2014–FY2017 ≈ $57–76B vs. true total revenue ≈ $87–90B that period; AAPL `SalesRevenueServicesGross` present but with zero full-year entries.)
6. **Special-case depository institutions / banks separately** — the chain above does not produce a sensible "total revenue" for a bank. See ZION evidence below; recommend detecting SIC/industry (or just noting `RevenuesNetOfInterestExpense` presence) and using that tag instead, or falling back to a computed `InterestAndDividendIncomeOperating + NoninterestIncome` figure.

**Merge-value nuance:** where two tags both cover the same period, their *values can differ* due to ASC-606 retrospective restatement — prefer the higher-priority (more current-standard) tag's value, since that's the one consistent with how the company reports comparatives today.

**Evidence:**

*AAPL — full chain confirmed, and values agree across tags in the overlap:*
- `SalesRevenueNet`: 11 years, FY2007-09-29→2008-09-27 (24,006,000,000) through FY2016-09-25→2017-09-30 (229,234,000,000).
- `Revenues`: 3 years, FY2016 (215,639,000,000) → FY2018 (265,595,000,000) — a transitional dual-tag window.
- `RevenueFromContractWithCustomerExcludingAssessedTax`: 9 years, FY2017 (229,234,000,000) → FY2025-09-27 (416,161,000,000).
- Values agree exactly across tags where periods overlap (FY2016 `SalesRevenueNet` = `Revenues` = 215,639,000,000; FY2017 all three tags = 229,234,000,000) — AAPL had no ASC-606 restatement of prior-year comparatives.

*MSFT — same 3-tag pattern, but with a restatement divergence:*
- `SalesRevenueNet`: 9 years, FY2009-06-30 (58,437,000,000) → FY2017-06-30 (89,950,000,000).
- `Revenues`: only 3 years, FY2008–FY2010 (an early/legacy tagging window, values match `SalesRevenueNet` for FY2009 and FY2010 exactly).
- `RevenueFromContractWithCustomerExcludingAssessedTax`: 11 years, FY2016-06-30 (91,154,000,000) → FY2026-06-30 (331,839,000,000).
- **Restatement divergence**: for FY2016 (period 2015-07-01→2016-06-30), `SalesRevenueNet` reports 85,320,000,000 but `RevenueFromContractWithCustomerExcludingAssessedTax` reports 91,154,000,000 for the *same period* — MSFT retrospectively restated FY2016/17 revenue under the new standard, so the two tags legitimately disagree by ~$5.8B for identical dates. Confirms picking the higher-priority (current-standard) tag matters, not just picking "any tag with data."

*KSS — confirms the chain, `Revenues` tag unused:*
- `SalesRevenueNet`: 11 years, FY2007-02-04→2008-02-02 (16,474,000,000) → FY2017-01-29→2018-02-03 (19,095,000,000).
- `RevenueFromContractWithCustomerExcludingAssessedTax`: 10 years, FY2016-01-31→2017-01-28 (19,681,000,000) → FY2025-02-02→2026-01-31 (15,527,000,000).
- `Revenues`: exists as a tag key but **zero full-year 10-K entries** — KSS never used it for the annual total-revenue line at all. Restatement divergence again visible: FY2018 (2017-01-29→2018-02-03) `SalesRevenueNet` = 19,095,000,000 vs `RevenueFromContractWithCustomerExcludingAssessedTax` = 20,084,000,000 for the identical period.

*AT&T (T) — the case that proves tag 2 (`Revenues`) must stay in the chain, not just tag 1/3:*
- `Revenues`: 19 continuous years, FY2007 (118,928,000,000) → FY2025 (125,648,000,000) — used as the sole total-revenue tag straight through the ASC-606 transition, no gap, no switch.
- `RevenueFromContractWithCustomerExcludingAssessedTax`: exists in AT&T's facts but has **only 3 raw entries total**, all quarterly (`10-Q`, Q1/Q2/Q3 2018), **zero full-year 10-K entries** — a one-time transitional/disaggregation disclosure, not the consolidated revenue line. A chain that tries tag 1 first, sees "some data exists," and stops without checking full-year coverage would badly under-fill AT&T's revenue history.
- `SalesRevenueNet` doesn't exist for T at all; instead `OtherSalesRevenueNet` appears FY2007–FY2012 only (11,550,000,000 → 12,782,000,000) — a component tag, not total revenue (AT&T's real revenue that period was ~$120B), reinforcing point 5 above (don't blindly grab any "...Revenue..." tag).
- `RevenueFromContractWithCustomerIncludingAssessedTax` — checked, not present for T either.

*ZION — the bank exception, confirms `Revenues` and the ASC-606 tag are both wrong for banks:*
- `Revenues`: 8 years, FY2018 (508,000,000) → FY2025 (662,000,000).
- `RevenueFromContractWithCustomerExcludingAssessedTax`: 8 years, FY2018 (412,000,000) → FY2025 (529,000,000).
- `RevenuesNetOfInterestExpense`: 6 years, FY2018 (2,783,000,000) → FY2023 (3,115,000,000).
- These three figures for the *same fiscal years* differ by 5-6x ($500-660M vs $400-530M vs $2.78-3.1B). `Revenues` and the ASC-606 tag both capture only **noninterest fee income**; interest income (the majority of a bank's revenue) is governed by ASC 310/326, not ASC 606, so it's excluded from both. `RevenuesNetOfInterestExpense` (net interest income + noninterest income) is the figure that matches what's conventionally reported as a bank's "total revenue." Recommend flagging bank/depository-institution filers for this substitution rather than trusting the generic chain.

---

## Decision 3 — Shares outstanding: prefer `us-gaap:CommonStockSharesOutstanding`, fall back to `dei:EntityCommonStockSharesOutstanding`, then `us-gaap:CommonStockSharesIssued`

**Decided order:**
1. **`us-gaap:CommonStockSharesOutstanding`** (balance-sheet date, i.e. the XBRL `end` instant equals the fiscal period end) — use when present, because it's date-aligned with the rest of that period's financial statement facts (revenue, net income, EPS all share the same period end), which matters when joining shares-outstanding to other metrics for the same period.
2. **`dei:EntityCommonStockSharesOutstanding`** (cover-page count, dated at/near the filing date — typically 2-7 weeks after the fiscal period end) — use as the fallback whenever tag 1 is absent for that filer/period. In the sample this was necessary for 2 of 5 filers where tag 1 doesn't exist **at all**.
3. **`us-gaap:CommonStockSharesIssued`** — last-resort tertiary fallback, only if both of the above are absent. This is gross issued shares (not net of treasury stock), so it will overstate true outstanding count for any filer holding treasury shares — flag results derived from this tag as approximate.

**Evidence:**

| Filer | `us-gaap:CommonStockSharesOutstanding` | `dei:EntityCommonStockSharesOutstanding` | `us-gaap:CommonStockSharesIssued` |
|---|---|---|---|
| AAPL | Present. FY-end instants 2008-09-27 → 2026-06-27 (70 distinct dates) | Present. 2009-06-27 → 2026-07-17 | n/a (not needed) |
| MSFT | Present. 2007-06-30 → 2026-06-30 (71 distinct dates) | Present. 2009-10-19 → 2026-07-23 | n/a (not needed) |
| KSS | **Absent entirely** | Present. 2009-08-28 → 2026-05-29 | Present. 351,000,000 (2009-01-31) → 127,000,000 (2026-01-31) |
| ZION | Present. 2009-06-30 → 2026-06-30 (69 distinct dates) | Present. 2010-07-31 → 2026-07-31 | (present but not needed) |
| T | **Absent entirely** | Present. 2009-06-30 → 2026-07-16 (69 distinct dates) | Present. 6,495,231,088 (2008-12-31) → 7,620,748,598 (2025-12-31) |

- **Coverage**: `dei:EntityCommonStockSharesOutstanding` was present for **all 5** sampled filers back to ~2009; `us-gaap:CommonStockSharesOutstanding` was present for only **3 of 5** (missing entirely for KSS and T, which instead report gross `CommonStockSharesIssued` on their balance-sheet face). This makes the dei tag the more universally *available* one — but per-period date alignment still favors us-gaap when it exists, hence the ordering above (try the better-aligned tag first, but don't assume it exists).
- **Timing/precision difference** (AAPL FY2025, illustrating cover-page vs balance-sheet-date drift): `us-gaap:CommonStockSharesOutstanding` at period end 2025-09-27 = 14,773,260,000 shares, vs `dei:EntityCommonStockSharesOutstanding` at cover-page date 2025-10-17 (20 days later, filed 2025-10-31) = 14,776,353,000 shares — a small but real difference from buyback/issuance activity in the intervening ~3 weeks. Confirms the two tags answer genuinely different questions ("as of period end" vs "as of filing date") and callers should pick deliberately based on what date they're trying to align to, not treat them as interchangeable.
- **Data-quality caveat found in the dei tag** (motivates keeping a sanity check regardless of which tag is used): T's `dei:EntityCommonStockSharesOutstanding` includes an entry `{'end': '2010-12-31', 'val': 0, filed: '2011-03-01'}` — an evident filing error (AT&T obviously didn't have zero shares outstanding). A naive "use whatever the tag returns" implementation would need an outlier/zero filter here regardless of tag choice.
- **`CommonStockSharesIssued` as tertiary**: confirmed necessary for KSS and T since they lack the primary tag; values are gross-issued (KSS 127,000,000 issued as of 2026-01-31 will be higher than true float-adjusted outstanding once treasury shares are netted out — worth a caveat in any UI surfacing this number, though not independently re-derived here).

---

## Summary for the ticket

Replace the "Remaining work" bullets with these three resolved fallback chains (merge by period, not by company):

- **Net income:** `NetIncomeLoss` → `ProfitLoss`. (Do not conflate with `NetIncomeLossAvailableToCommonStockholdersBasic/Diluted`.)
- **EPS:** `EarningsPerShareDiluted` / `EarningsPerShareBasic` — no fallback needed.
- **Dividends/share:** `CommonStockDividendsPerShareDeclared` → `CommonStockDividendsPerShareCashPaid` → (last resort) sum four quarterly 10-Q facts.
- **Revenue:** `RevenueFromContractWithCustomerExcludingAssessedTax` → `Revenues` → `SalesRevenueNet` → `RevenueFromContractWithCustomerIncludingAssessedTax`; banks/depository institutions need a separate path via `RevenuesNetOfInterestExpense` (or computed interest income + noninterest income) since the generic chain systematically undercaptures bank revenue.
- **Shares outstanding:** `us-gaap:CommonStockSharesOutstanding` → `dei:EntityCommonStockSharesOutstanding` → `us-gaap:CommonStockSharesIssued` (flag as approximate — gross, not net of treasury).

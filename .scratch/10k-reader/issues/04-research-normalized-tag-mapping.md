# 04: Research — normalized line-item tag mapping

**What to build:** A documented, verified XBRL tag-fallback mapping for the ~19 new normalized line items the 10-K Reader's Normalized sub-tab needs, beyond the 5 metrics this app already maps (Revenue, Net Income, EPS, Dividends per share, Shares Outstanding — see `.scratch/ticker-explorer/research/02-edgar-tag-fallback-mapping-findings.md` for the existing methodology and findings to extend, not duplicate).

**Blocked by:** None (can start immediately, independent of the UI work in tickets 01-03)

**Status:** ready-for-agent

- [ ] For each of the following line items, identify the primary `us-gaap` XBRL tag and any fallback tags needed to cover common reporting variation, following the same research methodology as the existing tag-fallback research (checking actual `companyfacts` responses across a handful of real filers spanning at least: a standard industrial/tech company, a bank or depository institution, and one other industry where common tags are known to diverge, e.g. a REIT or insurer):
  - Income Statement: Cost of Revenue, Gross Profit, Operating Expenses, Operating Income, Interest Expense, Pre-tax Income, Income Tax (Provision), EPS Basic, EPS Diluted
  - Balance Sheet: Cash & Cash Equivalents, Total Current Assets, Property/Plant/Equipment (net), Goodwill & Intangible Assets, Total Assets, Total Current Liabilities, Long-term Debt, Total Liabilities, Total Stockholders' Equity
  - Cash Flow Statement: Operating Cash Flow, Capital Expenditures, Investing Cash Flow, Financing Cash Flow, Net Change in Cash
- [ ] For each line item, the findings note: the primary tag, the fallback chain (if more than one tag is needed), any known industry-specific gaps (e.g. a tag that a bank/REIT/insurer doesn't report at all, which should render as the existing dash placeholder rather than erroring), and any derived/computed line items (e.g. Gross Profit as Revenue minus Cost of Revenue, if no direct tag reliably reports it).
- [ ] Findings are written to `.scratch/10k-reader/research/01-normalized-tag-mapping-findings.md`, in the same format/level of detail as the existing EDGAR tag-fallback research this extends.
- [ ] The findings explicitly flag any line item where no reliable tag (or fallback chain) was found across the sample filers, so tickets 05-07 can treat that item as dash-placeholder-only rather than attempting a fetch that will silently fail industry-wide.

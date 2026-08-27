# EDGAR As-Filed Statement Tables — Findings

Scoping input for a proposed "10-K Reader" tab: can we get SEC EDGAR's own rendered financial-statement tables (filer's own labels/order/indentation, not remapped to a standard taxonomy) for free, keyless, on a per-filing basis — as an alternative to scraping raw 10-K HTML?

All requests below used `User-Agent: Research research@example.com` against live `sec.gov`/`data.sec.gov` endpoints on 2026-08-26. Test filer: **Apple Inc., CIK 0000320193** (cross-checked against Microsoft, Nvidia, and Toyota where noted).

---

## 1. R*.htm rendered statement files

### 1a. Do they exist as fetchable, well-formed HTML preserving filer labels/order/indentation?

Yes. Fetched `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/R5.htm` (Apple FY2025 10-K, "CONSOLIDATED BALANCE SHEETS"). `HEAD` gives `content-type: text/html`, 200 OK. Body is wrapped in an EDGAR SGML-style `<DOCUMENT><TYPE>XML...<TEXT><html>...` envelope, but the actual payload is a plain `<table class="report">`:

```html
<th class="tl" colspan="1" rowspan="1"><div style="width: 200px;"><strong>CONSOLIDATED BALANCE SHEETS - USD ($)<br> shares in Thousands, $ in Millions</strong></div></th>
<th class="th"><div>Sep. 27, 2025</div></th>
<th class="th"><div>Sep. 28, 2024</div></th>
...
<tr class="re">
<td class="pl" ...><a ... onclick="Show.showAR( this, 'defref_us-gaap_AssetsCurrentAbstract', window );"><strong>Current assets:</strong></a></td>
...
<tr class="ro">
<td class="pl" ...><a ... onclick="Show.showAR( this, 'defref_us-gaap_CashAndCashEquivalentsAtCarryingValue', window );">Cash and cash equivalents</a></td>
<td class="nump">$ 35,934<span></span></td>
<td class="nump">$ 29,943<span></span></td>
</tr>
```

This is exactly the filer's own presentation: label text is Apple's own wording ("Cash and cash equivalents", "Vendor non-trade receivables"), section headers ("Current assets:") are bold, non-value rows, and appear in the filer's own order; subtotal rows ("Total current assets") are present inline; the same concept ("Marketable securities") legitimately appears twice (current vs non-current section) exactly as filed. Indentation is CSS-driven (`class="pl"`) rather than literal whitespace, but row order/nesting is preserved.

**Directly parseable with existing deps, no new dependency needed**: `pandas.read_html("R5.htm")` (no auth, no preprocessing) parsed it straight out of the box into a clean DataFrame:

```
   CONSOLIDATED BALANCE SHEETS - USD ($)  shares in Thousands, $ in Millions Sep. 27, 2025 Sep. 28, 2024
0                                                            Current assets:           NaN           NaN
1                                                  Cash and cash equivalents      $ 35,934      $ 29,943
2                                                      Marketable securities         18763         35228
...
7                                                       Total current assets        147957        152987
```
(pandas is already a project dependency; no `lxml`/`html5lib` issues encountered locally, though note `pd.read_html` does require one of those parser backends to be installed — worth confirming it's present transitively, e.g. via a `beautifulsoup4`/`lxml` transitive dep, since it's not in `pyproject.toml`'s explicit list.)

### 1b. Discovering which R-file is which statement: FilingSummary.xml

Yes — `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/FilingSummary.xml` exists and is exactly the index needed. Real structure (current format, `Version 3.25.3`):

```xml
<FilingSummary>
  <Version>3.25.3</Version>
  <ReportFormat>html</ReportFormat>
  <MyReports>
    <Report instance="aapl-20250927.htm">
      <IsDefault>false</IsDefault>
      <HasEmbeddedReports>false</HasEmbeddedReports>
      <HtmlFileName>R5.htm</HtmlFileName>
      <LongName>9952153 - Statement - CONSOLIDATED BALANCE SHEETS</LongName>
      <ReportType>Sheet</ReportType>
      <Role>http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS</Role>
      <ShortName>CONSOLIDATED BALANCE SHEETS</ShortName>
      <MenuCategory>Statements</MenuCategory>
      <Position>5</Position>
    </Report>
    ...
```

Filtering `<Report>` elements where `MenuCategory == "Statements"` cleanly isolates exactly the 6 core statement tables for Apple's filing, no per-company hardcoding needed:

| HtmlFileName | ShortName |
|---|---|
| R3.htm | CONSOLIDATED STATEMENTS OF OPERATIONS |
| R4.htm | CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME |
| R5.htm | CONSOLIDATED BALANCE SHEETS |
| R6.htm | CONSOLIDATED BALANCE SHEETS (Parenthetical) |
| R7.htm | CONSOLIDATED STATEMENTS OF SHAREHOLDERS' EQUITY |
| R8.htm | CONSOLIDATED STATEMENTS OF CASH FLOWS |

To pick Balance Sheet / Income Statement / Cash Flow specifically out of the `Statements` bucket, keyword-match `ShortName` (e.g. `"BALANCE SHEET"`, `"OPERATIONS"` or `"INCOME"`, `"CASH FLOWS"`) — `MenuCategory` alone gets you to "it's a primary statement," but doesn't disambiguate P&L/comprehensive-income/equity/cash-flow from each other, and (see 1e) `MenuCategory`/`Position` don't exist in older FilingSummary schema versions, so ShortName text matching is the more durable signal across filing eras.

### 1c. Rate limits

SEC's own FAQ (`https://www.sec.gov/about/webmaster-frequently-asked-questions`, the current location — the URL given in the task, `/os/webmaster-faq`, 301-redirects here) states plainly and without carving out an exception for Archives vs API hosts:

> "Note that our current maximum access rate is 10 requests per second. This is carefully monitored to preserve equitable access for all users."

This is one unified sec.gov-wide policy, not documented as API-host-specific, and empirically Archives enforces the same UA gate as the API host (see 1d) — treat 10 req/s as the ceiling for `www.sec.gov/Archives/...` requests too, not just `data.sec.gov`.

### 1d. User-Agent requirement — confirmed enforced on Archives, not just the API

Same FAQ page: *"Please declare your user agent in request headers: Sample Declared Bot Request Headers: `User-Agent: Sample Company Name AdminContact@<sample company domain>.com`"* — and separately documents an "Undeclared Automated Tool" error for missing/generic UAs.

Empirically confirmed by omitting the header entirely:

```
$ curl -sI "https://data.sec.gov/submissions/CIK0000320193.json"
HTTP/2 403
$ curl -sI "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/R5.htm"
HTTP/2 403
```

Both hosts reject the no-UA request identically; both succeed with a descriptive UA. Confirms the requirement applies uniformly, not just to `data.sec.gov`.

### 1e. Consistency across filers/years — XBRL mandate timeline and format drift

Walked Apple's own 10-K history back from 2025 using `https://data.sec.gov/submissions/CIK0000320193.json` (recent) and `.../CIK0000320193-submissions-001.json` (`filings.files`, pre-2015 archive):

| Filing (filed date) | `FilingSummary.xml` | R-file format |
|---|---|---|
| 2025-10-31 (FY2025) | 200, HTML R*.htm, has `MenuCategory`/`Position` | `<HtmlFileName>R5.htm</HtmlFileName>` |
| 2011-10-26 (FY2011) | 200, HTML R*.htm, no `MenuCategory`/`Position` | `<HtmlFileName>R2.htm</HtmlFileName>` |
| 2010-10-27 (FY2010) | 200, but **old XML report format** | `<XmlFileName>R3.xml</XmlFileName>` (not `.htm`!) |
| 2009-10-27 (FY2009) | 200, same old XML format (`Version 1.0.0.3`) | `<XmlFileName>R1.xml</XmlFileName>`, no `Role`/`MenuCategory` |
| 2008-11-05 (FY2008) | **404** | none — pre-XBRL |
| 2007, 2005 | **404** | none — pre-XBRL |

Two important nuances beyond a hard on/off switch:
- **2009–2010 filings use an older `InstanceReport` XML schema, not HTML tables.** Fetching `R4.htm` on the 2010 filing 404s (only `R4.xml` exists); fetching that XML gives a structured but *differently-shaped* document (`<InstanceReport><ReportName>CONSOLIDATED BALANCE SHEETS...</ReportName><Columns>...`) that still carries as-filed labels/order but needs a separate XML parser, not `pd.read_html`. A robust integration should try `HtmlFileName` first and fall back to `XmlFileName` per the `<Report>` entry's own field, rather than assuming `R{n}.htm` always exists.
- **2008 and earlier: no XBRL at all** (`FilingSummary.xml` 404s) — consistent with the SEC's phase-in schedule (largest filers, ≥$5B float, first required for periods ending on/after June 15 2009; all other large accelerated filers by June 15 2010; all remaining filers, including smaller reporting companies and IFRS foreign private issuers, by June 15 2011). Practical takeaway: **for 10-Ks filed before ~2009 (2011 for smaller filers), there is no R.htm/FilingSummary route at all** — must fall back to raw HTML/plain-text document scraping for old filings regardless of which route is chosen for recent ones.

---

## 2. Financial_Report.xlsx

Confirmed it *can* exist and be a real xlsx — but **it no longer exists on current (2025-2026) filings**, which is a significant, somewhat surprising finding:

| Filing | `HEAD Financial_Report.xlsx` |
|---|---|
| Apple FY2024 10-K (filed 2024-11-01, `0000320193-24-000123`) | 200 |
| Apple FY2023 10-K (filed 2023-11-03) | 200 |
| Apple FY2020 10-K (filed 2020-10-30) | 200, `content-type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `content-length: 126469` — a genuine xlsx |
| **Apple FY2025 10-K (filed 2025-10-31, `0000320193-25-000079`)** | **404** |
| Nvidia FY2025 10-K (filed 2025-02-26) | 200 |
| **Nvidia FY2026 10-K (filed 2026-02-25)** | **404** |

The Apple FY2025 filing's `index.json` directory listing confirms the file is simply absent (93 items total: `R1.htm`…`R70.htm`, `FilingSummary.xml`, `MetaLinks.json`, XBRL instance/schema/label/calc/def files, exhibits — but no `Financial_Report.xlsx`). Two independent filers (Apple, Nvidia) both stopped having this file sometime between their filings dated Nov 2024/Feb 2025 and Oct 2025/Feb 2026 respectively — consistent with a global EDGAR system change in 2025, not filer-specific. Could not find an official SEC announcement confirming this via web search; it's an empirically observed fact, not a documented deprecation.

**Implication for scoping**: Financial_Report.xlsx is not a reliable route for *current* filings at all right now — it may work for 10-Ks filed before ~mid-2025 but returns 404 for filings from roughly Q2/Q3 2025 onward across at least two large filers. Building a feature around it today would be building on something already broken for new filings. It also would require adding `openpyxl` (confirmed not currently a dependency in `pyproject.toml`) purely to read a format that appears to no longer be generated. Not recommended.

---

## 3. SEC Financial Statement and Notes Data Sets — poor fit, as expected

The task's landing-page URL (`https://www.sec.gov/dera/data/financial-statement-and-notes-data-sets.html`) now 404s; current location is `https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets`. Fetched it and confirmed: it's exclusively **bulk, all-filer, monthly ZIP downloads** (`2026_07_notes.zip`, `2026_06_notes.zip`, ... back to `2009q1_notes.zip`), each containing every registrant's XBRL facts for that period in flattened TSV form, updated monthly (quarterly before Nov 2020). There is no per-filing or per-ticker on-demand endpoint — to get one company's one filing you'd download and locally filter a multi-gigabyte archive covering every filer in that period. Not viable for an on-demand single-filing "10-K Reader" feature; confirmed poor fit as expected.

---

## 4. Filing discovery via submissions JSON

`https://data.sec.gov/submissions/CIK0000320193.json` (10-digit zero-padded CIK) returns entity metadata plus `filings.recent`, a columnar (struct-of-arrays) object:

```
recent keys: ['accessionNumber', 'filingDate', 'reportDate', 'acceptanceDateTime', 'act', 'form',
 'fileNumber', 'filmNumber', 'items', 'core_type', 'size', 'isXBRL', 'isInlineXBRL',
 'isXBRLNumeric', 'primaryDocument', 'primaryDocDescription']
```

Filtering `form == "10-K"` and taking the first (most recent) match gives, for Apple:

```
accessionNumber: 0000320193-25-000079
primaryDocument: aapl-20250927.htm
filingDate: 2025-10-31
reportDate: 2025-09-27
```

From `accessionNumber` (dashes stripped: `000032019325000079`) and CIK, the Archives base directory is `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/`, containing `FilingSummary.xml`, `R*.htm`, and the primary 10-K document (`aapl-20250927.htm`).

Only ~1000 most-recent filings live in `filings.recent`; older ones are paginated via `filings.files` (e.g. `CIK0000320193-submissions-001.json`, covering 1994-01-26 to 2015-06-02 for Apple) — needed to reach pre-2015 filings.

Same rate-limit/UA rules apply to `data.sec.gov` as to Archives (see 1c/1d; both hosts 403 identically without a UA).

---

## 5. Form-type filterability (10-K vs variants vs 20-F)

Apple's older filings (pre-2015 archive) show the raw `form` field distinguishes variants as literal distinct strings, e.g. `10-K405` appears for filings from 1998 and 2001 alongside plain `10-K` for all other years — so a naive `form == "10-K"` filter is *not* enough for full historical coverage; a real implementation should check `form in {"10-K", "10-K405", "10-KSB", "10-K/A", ...}` if it needs to reach that far back. For current/recent-only use, plain `10-K` suffices (Apple's own history has been unadorned `10-K` since 2002). Separately, fetched Toyota Motor Corp's submissions (`CIK0001094517`, a foreign private issuer) and confirmed its `form` array contains `20-F`/`20-F/A` and **no `10-K` at all** — cleanly detectable by simply checking whether `"10-K"` (or the historical-variant set) appears anywhere in the filer's `form` array, with no ambiguous overlap.

---

## Recommendation

**The R.htm + FilingSummary.xml route is solid and is the recommended approach for current filings (roughly 2011-onward, HTML-format era)**, with these caveats baked into the design:

1. Use `FilingSummary.xml`'s `<Report>` list (`MenuCategory == "Statements"`, then `ShortName` keyword match) to find the right `HtmlFileName`/`XmlFileName` per filing — never hardcode R-numbers, they differ per filer and even per filing year for the same filer (R3/R4/R5 in the 2025 Apple filing vs R2/R3 in 2011).
2. `R*.htm` is directly fetchable, well-formed enough for `pandas.read_html()` out of the box (already a project dependency — no new dependency needed), and preserves the filer's exact labels, order, section headers, and subtotals.
3. Handle the **2009-2010 old-format window** (`XmlFileName` instead of `HtmlFileName`, `InstanceReport` XML schema) as a distinct, lower-priority code path if historical depth into that window matters; otherwise treat filings from that era as unsupported and fall back to raw-HTML scraping or simply not offering the as-filed-table view for them.
4. **Pre-XBRL filings (roughly pre-2009 for large filers, pre-2011 for smaller ones) have no R.htm/FilingSummary route at all** — `FilingSummary.xml` 404s outright. For these, either scrape the primary 10-K HTML/text document directly or scope the "10-K Reader" feature to XBRL-era filings only (a reasonable, explicit scoping decision given the era most users will care about).
5. **Do not build on `Financial_Report.xlsx`.** It's real when present, but it is *already 404ing on current 2025/2026-dated filings* for both Apple and Nvidia — it appears to have been discontinued globally sometime in 2025, so a new feature relying on it would not work for filings going forward. It would also require adding `openpyxl`, which isn't justified given it's not even being generated for new filings.
6. The bulk **Financial Statement and Notes Data Sets** are, as anticipated, not viable for on-demand single-filing/per-ticker use — confirmed strictly monthly all-filer ZIPs, no per-filing endpoint.
7. UA header and the shared 10 req/s ceiling apply uniformly across `data.sec.gov` and `www.sec.gov/Archives` — reuse whatever request-throttling/UA logic `ticker_data.py` already has for the `companyfacts` API rather than building a second one.

Net: R.htm scraping (discovered via FilingSummary.xml, parsed with `pandas.read_html`, no new dependencies) is the right foundation for an "exact as-filed" 10-K Reader for filings from the last ~15 years; raw HTML/text scraping remains necessary only as an explicit fallback for pre-XBRL filings if those need to be supported at all.

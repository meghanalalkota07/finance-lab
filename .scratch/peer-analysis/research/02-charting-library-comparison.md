# Charting library comparison — multi-ticker normalized-return overlay in Streamlit

Feeds the Peer Analysis feature design (5–10 ticker line overlay, custom date range, hover, ideally range slider/zoom, ideally CSV export tied to the chart).

## Verdict

**Stick with Plotly (`st.plotly_chart`).** It already meets every stated interaction requirement out of the box (synced multi-series hover, click-to-toggle legend, drag zoom/pan, an optional range slider — each a one-line configuration call), needs zero new dependencies since this repo already uses it, and is — as of a live check on 2026-08-25 — the most actively maintained of the four candidates by a wide margin (a new PyPI release literally the same day this research was done). None of the three alternatives offers a capability this feature needs that Plotly lacks; two of them (`streamlit-lightweight-charts`, Bokeh) come with real, currently-live maintenance or dependency-coupling problems that Plotly doesn't have.

**Note on CSV export**: none of the four libraries ties a "download the underlying data" button natively into the chart widget itself — Plotly's chart toolbar only exports a PNG/SVG *image*, not data, and the same is true of the others. CSV export is implemented at the Streamlit app level via a separate `st.download_button` against the source DataFrame, so this requirement doesn't actually discriminate between the four options — it's the same amount of app code regardless of which one renders the chart.

---

## Plotly (`st.plotly_chart`) — the incumbent

- **PyPI**: latest **7.0.0**, uploaded **2026-08-25T17:47:24** — the same day this research was conducted — 320 total releases (`https://pypi.org/pypi/plotly/json`).
- **GitHub** (`plotly/plotly.py`): `pushed_at: 2026-08-25`, **18,753 stars**, 778 open issues, not archived — active by every measure checked.
- **Capabilities, out of the box, no custom JS**:
  - Multi-series overlay: one `go.Scatter`/`px.line` trace per ticker on a shared figure — this repo's existing pattern.
  - Synced multi-series hover: `fig.update_layout(hovermode='x unified')` — a single kwarg.
  - Legend click-to-toggle a series's visibility: **default behavior** of any Plotly figure with a legend (single-click hides/shows one trace, double-click isolates it) — no configuration needed at all.
  - Zoom/pan: drag-to-zoom and double-click-to-reset are default behavior on every figure.
  - Range slider: `fig.update_xaxes(rangeslider_visible=True)` — one kwarg.
- **Installation**: pure `pip install plotly`, already a direct dependency of this repo (used elsewhere in `app.py`) — adopting it for Peer Analysis adds no new dependency surface at all.

## streamlit-lightweight-charts (wraps TradingView's `lightweight-charts`)

- **PyPI** (the package name matching the library's description, `streamlit-lightweight-charts`): latest **0.7.20**, uploaded **2023-05-22** — over three years stale, only 10 total releases (`https://pypi.org/pypi/streamlit-lightweight-charts/json`).
- Its own PyPI metadata points to `home_page: https://github.com/freyastreamlit/streamlit-lightweight-charts` — checked live via GitHub API: `pushed_at: 2023-07-24`, 225 stars, 4 open issues, not formally archived but no meaningful activity in ~3 years — de facto unmaintained.
- **The ecosystem is fragmented, which is itself a red flag for "installation footprint"**: rather than one canonical package receiving updates, the community has split into multiple incompatible forks that *are* actively maintained instead — e.g. `streamlit-lightweight-charts-v5` (a rewrite targeting TradingView's newer v5 JS library, with releases into 2026) and `nandkapadia/streamlit-lightweight-charts-pro`. Picking this option for a new feature means picking one of these forks rather than `pip install`-ing the well-known name and getting current code — a materially different (and worse) decision than installing Plotly or streamlit-echarts.
- **Fit for this use case**: TradingView's `lightweight-charts` is designed primarily around single-symbol candlestick/OHLC + volume panes, not multi-series normalized-return line overlays with legend-driven show/hide across many tickers — this is a characterization based on the library's documented design intent, not a hands-on test performed in this session, and is flagged as such.
- **Installation**: pure `pip install` (the JS bundle ships inside the wheel, standard for Streamlit custom components) — no separate Node/build step for the app author, but see above regarding which package name is actually trustworthy to depend on.

## streamlit-echarts (wraps Apache ECharts)

- **PyPI**: latest **0.7.0**, uploaded **2026-06-08** — about 2.5 months before this research, 8 total releases (`https://pypi.org/pypi/streamlit-echarts/json`).
- **GitHub** (`andfanilo/streamlit-echarts`): `pushed_at: 2026-08-09` (16 days before this research), 631 stars, 11 open issues, not archived — actively maintained.
- **Capabilities**: ECharts natively supports synced cross-series tooltips (`tooltip.trigger: 'axis'` + `axisPointer`), legend click-to-toggle (default ECharts legend behavior), and zoom/pan via `dataZoom` (slider and/or click-drag) — all real, all achievable "without custom JavaScript" in the literal sense that the Python API takes a nested dict (ECharts' `option` object) rather than requiring you to write `.js` files. In practice, though, building that `option` dict by hand for a multi-series overlay with all of the above wired up is materially more verbose/declarative work than Plotly's `px.line(...)` plus two or three `update_*` calls — closer to authoring raw chart configuration than calling a high-level chart function.
- **Installation**: pure `pip install`, no build step.
- **Assessment**: the only alternative here that's genuinely current and healthy, but it doesn't offer anything this feature needs that Plotly is missing, at the cost of more verbose chart-config code and one more dependency this repo doesn't already carry.

## Bokeh (`st.bokeh_chart`)

- **Bokeh itself** is healthy: PyPI latest **3.10.0**, uploaded 2026-08-18; GitHub (`bokeh/bokeh`) `pushed_at: 2026-08-25`, 20,435 stars — a well-maintained project in its own right.
- **But `st.bokeh_chart` no longer exists in current Streamlit.** Confirmed directly against Streamlit's own documentation (`https://docs.streamlit.io/develop/api-reference/charts/st.bokeh_chart`, fetched live): the page itself displays the notice **"This method does not exist in version `1.62.0` of Streamlit."** It has been removed from Streamlit core. Community reports (Streamlit GitHub issue `#10574`, Streamlit forum threads including "Streamlit is Broken! Streamlit MUST support Bokeh v3.0 ASAP" and a "StreamlitAPIException: Streamlit only supports Bokeh version 2.4.3" thread) describe the underlying history: `st.bokeh_chart` was long pinned to the old Bokeh 2.4.3 JSON model format, which broke for any app using Bokeh 3.x, and rather than keep chasing Bokeh's breaking changes inside Streamlit core, the maintainers extracted the integration into a separate installable component.
- **The replacement, `streamlit-bokeh`** (PyPI, latest **3.10.0**, uploaded **2026-08-25T18:39:37** — the same day as this research): actively maintained, but its declared dependency is `bokeh==3.10.0` — an **exact-version pin**, not a range (`requires_dist` confirmed via PyPI JSON). Adopting Bokeh today for this feature would mean taking on a second charting library *and* a component that hard-locks the app to one specific Bokeh point release, with every future Bokeh upgrade gated on a matching `streamlit-bokeh` release landing first.
- **Assessment**: disqualified. Using Bokeh in a Streamlit app today isn't "add one well-known package" the way it might read from older tutorials — it's "add a component that Streamlit's own team spun out specifically because of recurring version-compatibility breakage, currently mitigated by an exact-version pin."

---

## Recommendation

Stick with Plotly. It is the incumbent (already used elsewhere in this app), requires no new dependency, satisfies every stated requirement (synced hover, legend toggle, zoom/pan, range slider) with minimal one-line configuration, and — checked live rather than assumed — is comfortably the most actively maintained and widely adopted of the four projects as of 2026-08-25. `streamlit-echarts` is the only alternative worth a second look if some future feature specifically wants an ECharts visual, but it isn't a decisive improvement here and adds a dependency plus more verbose chart-config code for no net capability gain. `streamlit-lightweight-charts` is disqualified on ecosystem-health grounds: its canonical PyPI package is three years stale, and the community has moved to competing, mutually-incompatible forks instead of one current package. Bokeh is disqualified because the Streamlit integration this feature would actually use, `st.bokeh_chart`, has been removed from Streamlit core, and its replacement component hard-pins an exact Bokeh version — a coupling problem none of the other three options have.

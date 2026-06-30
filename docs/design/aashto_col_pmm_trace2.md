# AASHTO.COL.PMM.TRACE2 — Compact PMM Trace UI and Plot Legend Layout

## Purpose

TRACE1 added explicit AASHTO LRFD PMM traceability to the PMM Visual Review. User testing showed that the trace text was too verbose for the two-column dashboard layout and the Plotly legend could overlap the graph axis/title region.

TRACE2 keeps the PMM route trace visible but reduces first-screen text density.

## UI changes

- PMM summary cards are reduced to compact cards:
  - Code Basis
  - PMM Route
  - Prestress
- Full method details remain available in a collapsed **Code / solver trace details** expander.
- Selected Case Details now shows compact code/route wording only on the main panel.
- Plotly PMM titles use one short trace line, for example:

```text
AASHTO LRFD 9th · Column/Pier PMM · SI-safe
```

Instead of the previous long line:

```text
Code basis: AASHTO LRFD 9th Edition · Route: AASHTO LRFD Column/Pier PMM · φ: AASHTO strain-controlled φ transition
```

## Plot layout changes

- PMM Mux-Muy and 3D PMM figures place the legend below the plotting area.
- Bottom margin is increased to prevent legend/axis overlap.
- Previous verbose trace subtitle is replaced rather than appended again to avoid duplicated code-basis lines after reruns.

## Engineering traceability

The full trace remains stored in `fig.layout.meta["pmm_code_trace"]` and in the collapsed selected-case details panel:

- Code basis
- Code edition
- PMM route
- Flexural basis
- Phi basis
- Units trace
- Prestress status
- Unbonded ignored count

## Regression coverage

`tests/test_aashto_col_pmm_trace1.py` now includes TRACE2 checks for:

- Compact summary cards.
- Compact Plotly title trace.
- Removal/replacement of the previous verbose title line.
- Legend placement below the plot area.
- Minimum bottom margin to avoid overlap.

# IGIRDER.ARROWDISPLAY4 — Mixed audit-column rendering

Date: 2026-10-05

Baseline: `concrete-section-pro_IGIRDER-MEMBERCHARTS3.zip`

Baseline SHA-256: `8501e40dfc2ad68561dabf468e8046b1c7a2a7045b659e3b6f24029225d1b542`

## Problem and cause

The collection Torsion workspace passed the raw stored result frame directly to
`st.dataframe`. A calculated station has a list in `Deck development trace`
(empty for no credited deck layers, or a complete list of layer dictionaries).
Below-threshold, zero-demand and source-blocked stations can have `"-"` instead.
Arrow cannot serialize a column containing both list and scalar values.
Streamlit 1.61.0's automatic fix examines the first non-null value; when that
value is a list, this mixed column is left unconverted. The second conversion
then raises `ArrowInvalid: cannot mix list and non-list, non-null values`.

Mixed confirmation fields such as `Closed loop confirmed` also contain booleans
and placeholders. These fields are normalized on the display copy as well.

This failure was reproduced in the real collection UI on Python 3.14.7,
pandas 3.0.6, Streamlit 1.61.0 and pyarrow 24.0.0. It also reproduces with
Python 3.12.14 / pandas 2.2.3; changing Python alone does not repair the data mix.

## Change

`concrete_pmm_pro/ui/result_table_display.py` creates a separate display frame.
Mixed object/audit columns become text; lists and dictionaries retain their
complete contents as JSON text. Numeric columns, homogeneous booleans,
nulls, rows, case names and row order retain their values and types.

The collection source-audit, calculation-trace and definition tables use the
display adapter. The shared combined V+T detailed audit uses it too, including
when that workspace is opened for a selected girder.

No engineering equations or ULS/SLS solver logic changed. The adapter's output
is never used for calculations, governing decisions, input hashes, caches,
Project JSON, Result Summary or Report/QA. Dependency settings and the
MEMBERCHARTS3 limits on shared model parameters/report scope remain unchanged.

## Validation

- Compiled `app.py` and all three changed/new production modules on Python 3.14.7.
- 670 scoped regression tests passed across 54 I-girder, Beam ULS, Girder and
  Project test files on Python 3.14.7 / pandas 3.0.6. This is not the complete
  repository test suite.
- 105 targeted tests passed with real Streamlit imported on the Cloud-matching
  Python/pandas stack; 17 of these are the new mixed-audit regressions.
- 27 targeted tests passed on Python 3.12.14 / pandas 2.2.3.
- Real Streamlit AppTest on both environments: Exterior Girder and Interior
  Girder 2, two cases each, calculated/below-threshold/zero-demand stations.
  The original ArrowInvalid was reproduced with the adapter removed. With the
  adapter, all four checks display both named graphs and audit tables; case/view
  changes make no solver calls, and changed member results are hidden as STALE.
- Arrow conversion of every DataFrame returned by all four member engines
  passed. Numeric result columns, source inputs and stored frames were checked
  for exact equality after creating their display copies.

Reproduce the UI verification from the project root:

```bash
python qa/igird_arrowdisplay4_ui_verify.py
```

Evidence is in `qa/evidence/igird_arrowdisplay4/`.

## Update the deployment

Use the contents of the ZIP's `concrete-section-pro` folder as the repository
root, retaining `app.py` in the existing deployment path. The production fix
requires both updated UI modules and the new `result_table_display.py` helper.
After committing the update, calculate Torsion again for the imported collection.

Repo summary: Fix Arrow serialization of mixed I-girder audit columns while preserving stored ULS results and separate member charts.

# CROSSBEAM.ANALYSIS4C7D25 — Deflection/Camber stage-source + chart UX closeout

Date: 2026-08-13 (Asia/Bangkok)
Baseline: `CROSSBEAM.ANALYSIS4C7D24 — Deflection import editor dtype fix`

## Scope

This milestone improves the Portal Frame Prestressed Crossbeam `Analysis → SLS Deflection / Camber` workflow without changing the adopted external-FEA displacement engineering route.

### Stage-owned source UX

- Split the source workspace into `At Transfer source` and `At Final Service source` tabs.
- Each stage has its own Excel/CSV template, upload control, replace button, and editable table.
- Replacing one stage preserves the other stage in the dedicated Analysis-owned Project JSON source.
- Imported rows are pinned to the selected stage so a mislabeled Stage cell in a stage-specific file cannot replace the other stage.
- Final Service remains runnable without Transfer rows; missing Transfer remains a warning and camber response is simply unavailable.

### Final Service criterion UX

- `Review only` remains the conservative default; no hidden deflection ratio is introduced.
- The UI now states explicitly that Review only has no deflection limit and therefore no automatic PASS/FAIL.
- When `L/240`, `L/360`, `L/480`, `L/1000`, or Custom `L/n` is selected, the UI states that span-specific limits/utilization are active.

### Chart UX

The Deflection/Camber figure now follows the established Concrete Section Pro chart language:

- blue = absolute external-FEA displacement context;
- teal = relative span deflection/camber used for the support-chord check;
- red dashed = span-specific downward deflection limit when an adopted Final Service L/n criterion is active;
- dark diamond = governing response marker;
- grey dotted = zero line and column centerlines;
- pale column footprints remain geometry context;
- relative traces across multiple spans use one concise legend item rather than one legend item per span;
- each active span limit is annotated with its adopted L/n and limit in mm.

The solver result now stores `Span start m` / `Span end m` so the chart can draw each support-to-support limit honestly. The preparation/result schemas were bumped to v2 so D24 cached Deflection/Camber results are rebuilt before review.

## Engineering behavior unchanged

- Verified external-FEA vertical displacement remains the source of truth.
- Positive displacement = upward/camber; negative = downward/deflection.
- Final Service deflection remains relative to the chord joining adjacent column-centre movements.
- Column/support translation is not silently assumed zero.
- No generic Crossbeam M/EI simple-span displacement is fabricated.
- Overhang movement remains visible but has no L/n acceptance limit.
- ULS, SLS Stress & Cracking, prestress-loss, reinforcement, and physical-joint stress equations are unchanged.

## Regression

- `py_compile`: PASS for `app.py`, `analysis_page.py`, `crossbeam_sls_deflection.py`, and `project_io.py`.
- D22–D25 focused regression: 15 passed.
- D17–D25 SLS focused regression: 37 passed.
- D13–D16 Result Summary / Report-QA regression: 17 passed (run in smaller groups).
- Total focused checks reported for this milestone: 54 passed.

Visual QA in deployed Streamlit remains required for the new source tabs and chart appearance.

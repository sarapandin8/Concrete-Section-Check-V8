# CROSSBEAM.ANALYSIS4C3 — Shear/Torsion Decision and Visual Closeout

## Scope

This milestone closes the decision-first presentation and graph semantics for the Portal Frame Prestressed Crossbeam standalone Torsion and combined Shear + Torsion workspaces. It starts from the accepted `CROSSBEAM.ANALYSIS4C2` solver-adoption baseline and does not modify the engineering solvers.

## Engineering decisions made visible

- Overall `FAIL` now names the exact controlling check rather than using a generic `LONGITUDINAL` or `V+T` label.
- The current project reports minimum longitudinal torsion reinforcement as the controlling reason:
  - `Aℓ,min required = 22,741 mm²`
  - `Aℓ provided = 10,053 mm²`
  - `Shortfall = 12,688 mm²`
  - `D/C = 2.262`
- Torsional strength `Tu/φTn` remains a separate component result and is no longer presented as the overall governing result when `Aℓ,min` controls.
- Sectional PASS/FAIL, physical-joint transfer REVIEW, and continuation/anchorage REVIEW remain separate decisions.

## Graph closeout

### Standalone Torsion

- Uses a specific `Gov. torsional-strength D/C` marker for the plotted `Tu/φTn` component.
- Adds an explicit decision annotation for the true overall controlling check.
- Adds compact `S1–S6` Segment labels.
- Replaces artificial physical-joint utilization markers with dotted `J1–J5 REVIEW` reference lines.
- Keeps Segment-owned traces and one-sided physical-joint values without interpolating across a physical joint.

### Combined Shear + Torsion

- Uses Segment-owned Stress, Transverse, and Longitudinal utilization traces.
- Uses a horizontal step envelope for Segment-owned longitudinal `Aℓ` utilization.
- Splits traces at physical joints and support interiors.
- Adds shaded support footprints and visible Column Face / ACI `h/2` generated-check markers.
- Adds `S1–S6` labels and `J1–J5 REVIEW` lines.
- Uses a specific `Gov. Aℓ,min D/C` marker and an explicit Required / Provided / Shortfall decision annotation.
- Does not create a false joint D/C value at zero.

## Result workspace closeout

- Corrects check-row taxonomy into retained section rows, generated support rows, and one-sided joint audit rows.
- Adds decision cards for exact governing check, governing D/C, required action, required, provided, and shortfall.
- Adds a print-safe `Why this result` table.
- Splits combined result evidence into imported/Segment checks, Column Face / ACI `h/2` checks, and physical-joint one-sided audit.
- Uses `st.table` for the principal support-check evidence so browser printing is not limited to a scrolling dataframe viewport.
- Expands the displayed code route to include the minimum torsional reinforcement route that actually governs the current result.

## Solver protection

The following files are byte-for-byte unchanged from `CROSSBEAM.ANALYSIS4C2`:

- `app.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_shear.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_torsion.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py`
- `concrete_pmm_pro/analysis/crossbeam_uls.py`
- `concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py`

No Shear, Torsion, combined V+T, Direct P–M3, prestress, or Project JSON equation/source contract was changed.

## Changed files

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis3_uls_torsion.py`
- `tests/test_crossbeam_analysis3b_joint_capacity_plot.py`
- `tests/test_crossbeam_analysis4c3_decision_visual.py` — new
- `README_CROSSBEAM_ANALYSIS4C3.md` — new

## QA completed

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS
- Crossbeam ULS adapter / Shear / compact Loads-Shear / Torsion / joint plot: **52 passed**
- Direct Crossbeam uniaxial Flexure: **4 passed**
- Torsion source contract and As/Aℓ role summary: **9 passed**
- ANALYSIS4C2 solver-adoption regression: **7 passed**
- ANALYSIS4C3 decision/visual tests: **3 passed**
- Crossbeam transverse rebar / combined preview / Project JSON / navigation: **42 passed**
- Shared Beam/Girder ULS chart/workspace regression: **83 passed**
- Generic RC / Prestressed / benchmark / AASHTO PMM regression: **81 passed**

Completed targeted and cross-workflow regression: **281 passed**.

The full repository suite was not completed and is not claimed green. HTML chart previews were generated for internal inspection; a full deployed Streamlit screenshot was not produced in the sandbox because the available browser-render path did not complete.

## Repo summary

Clarify Crossbeam torsion and combined V+T failures with exact required/provided evidence, standardized Segment-owned graphs, visible support checks, and print-safe joint-aware result tables without changing the accepted solvers.

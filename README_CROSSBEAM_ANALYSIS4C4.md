# CROSSBEAM.ANALYSIS4C4 — Combined V+T Workflow Standardization

## Scope

This milestone standardizes the Portal Frame Prestressed Crossbeam combined Shear + Torsion review workspace so it follows the same one-check / one-figure decision language used by the other Concrete Section Pro member workflows. It starts from `CROSSBEAM.ANALYSIS4C3` and does not modify any accepted engineering solver, reinforcement source contract, Project JSON route, or Direct P–M3 calculation.

## Why the prior combined chart was replaced

The ANALYSIS4C3 chart placed three different utilization meanings on one axis:

- ACI 22.7.7 section-size stress interaction,
- ACI 9.5.4.3 combined transverse reinforcement,
- longitudinal torsion reinforcement / detailing / flexure-plus-torsional-tension.

Although every trace used a D/C ratio, the checks did not represent the same physical quantity. The resulting chart was visually dense, difficult to read, and inconsistent with the accepted Flexure, Shear, and Torsion demand/capacity workspaces.

## Standardized review selector

The combined workspace now renders only the selected review view:

1. `Section-size stress`
2. `Transverse reinforcement`
3. `Longitudinal reinforcement`
4. `Joint review`

A horizontal selector is used instead of rendering every chart simultaneously. This preserves the app's selected-workspace rendering policy and avoids generating three large static chart images on every rerun.

## One view, one engineering meaning

### Section-size stress

- Plots only ACI 22.7.7 concurrent V/T section-size utilization.
- Uses one blue Segment-owned trace and the standard red `Limit = 1.0` line.
- Shows component-specific governing D/C, status, code route, and station.
- Shows Column Face and ACI `h/2` generated checks when finite component values exist.

### Transverse reinforcement

- Plots only required `(Av/s + 2At/s)` versus the unique physical vertical-leg pool as D/C.
- Uses one green Segment-owned trace and the standard red limit line.
- Preserves the ANALYSIS4C2 no-double-counting adoption rule.
- Reports exact required, provided, shortfall, governing station, and action.

### Longitudinal reinforcement

- Plots only the longitudinal torsion adoption D/C.
- Uses one amber Segment-owned horizontal step trace.
- Resolves the controlling subtype explicitly:
  - minimum `Aℓ`,
  - perimeter detailing, or
  - direct flexure plus torsional longitudinal tension.
- States that `Aℓ` is a cage-associated subset of physical `As`, not additional duplicate steel.

### Joint review

- Replaces utilization plotting with a clean physical-joint member map.
- Creates no artificial joint D/C.
- Shows `J1–Jn REVIEW` locations, Segment labels, support footprints, and the physical Crossbeam axis.
- Keeps one-sided adjacent-section demand/capacity evidence in a dedicated visible table.
- States that keys, interface friction, anchorage, local D-regions, and transfer remain separate engineering verification.

## Decision-first layout

The existing overall cards and `Why this result` table remain at the top. Each selected component adds its own compact cards for:

- component status,
- governing D/C and station,
- required value,
- provided value / code limit,
- shortfall and required action.

Detailed station/support evidence is placed in a check-specific expander. Full combined station results and ACI audit terms remain available in separate collapsed audit expanders.

## Graph standardization

Every component figure now uses the accepted wide ULS figure standard:

- one primary engineering trace,
- standard `Limit = 1.0` line,
- compact legend,
- `S1–S6` labels,
- Segment-owned trace breaks at physical joints,
- shaded support footprints,
- component-specific Column Face / ACI `h/2` markers,
- one component-specific governing marker,
- no decision banner inside the plot area.

Physical joints are shown as subtle `J1–Jn` references in component charts and as explicit `J1–Jn REVIEW` locations only in the Joint review map.

## Solver and persistence protection

The following files are byte-for-byte unchanged from ANALYSIS4C3:

- `app.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_shear.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_torsion.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py`
- `concrete_pmm_pro/analysis/crossbeam_uls.py`
- `concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py`
- `concrete_pmm_pro/io/project_io.py`

No Shear, Torsion, combined V+T, Direct P–M3, prestress, rebar source, or Project JSON numerical result was changed.

## Changed files

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis4c4_component_views.py` — new
- `README_CROSSBEAM_ANALYSIS4C4.md` — new

## QA completed

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS
- ANALYSIS4C4 component-view tests: **6 passed**
- ANALYSIS4C3 decision/visual regression: **3 passed**
- ANALYSIS4C2 solver-adoption regression: **7 passed**
- Torsion source contract and As/Aℓ summary: **9 passed**
- Crossbeam Shear / compact Loads-Shear / Torsion / joint capacity: **45 passed**
- Direct Crossbeam uniaxial Flexure: **4 passed**
- Shared Beam/Girder ULS workspace: **74 passed**
- Shared Beam/Girder chart semantics and navigation: **30 passed**
- Generic PMM benchmarks: **21 passed**

Completed targeted and cross-workflow regression: **199 passed**.

The full repository suite was not completed and is not claimed green. HTML component previews were generated for internal semantic inspection; a full deployed Streamlit screenshot still requires visual QA after deployment.

## Repo summary

Standardize Crossbeam combined V+T review into selective one-check views for section stress, transverse steel, longitudinal steel, and physical-joint audit without changing the accepted solvers.

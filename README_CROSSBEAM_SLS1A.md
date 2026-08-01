# CROSSBEAM.SLS1A — Transfer-Stage Concrete Stress Check

## Outcome

Adds a complete Portal Frame Crossbeam `SLS At Transfer` Analysis workspace at
the same decision-review level as Crossbeam Flexure: guarded source readiness,
explicit calculation action, stored current/stale result, decision cards,
governing result, required actions, full-length chart, compact result table, and
calculation audit.

## Calculation contract

- Source: active `Crossbeam Loads → SLS Loads → At Transfer` rows only.
- Row coupling: `P`, `V2`, `T`, and `M3` remain from the same imported FEA row.
- Signs: `P` compression-positive; `M3` sagging-positive; displayed concrete
  stress compression-negative and tension-positive.
- Gross-section stresses:

  ```text
  sigma_top    = -P/A - M3/Ztop
  sigma_bottom = -P/A + M3/Zbottom
  ```

- Imported Transfer resultants are used exactly once. Prestress force, primary
  prestress moment, and secondary prestress are not added again.
- `f'ci = (f'ci/f'c) × f'c` uses the existing Crossbeam stressing-strength ratio
  and each Section ID's concrete material.

## Limit basis

- ACI 318-19 Table 24.5.3.1, all other locations: compression not greater than
  `0.60f'ci`.
- ACI 318-19 Table 24.5.3.2, all other locations: tension not greater than
  `0.25sqrt(f'ci)` in the app's MPa basis.
- The simply-supported-member end limits are not applied to the Portal Frame
  Crossbeam.
- ACI 318-19 24.5.3.2.1 bonded-reinforcement relief is not credited by SLS1A;
  it requires a separate total tensile-force design check.
- Precast Segmental physical joints: every active Transfer Load Case must cover
  every physical joint; both `LEFT LIMIT (s-)` and `RIGHT LIMIT (s+)` top and
  bottom fibers must remain at least `0.70 MPa` in compression.

## UI / QA behavior

- Crossbeam routes to SLS1A before the generic SLS workflow.
- Run button is enabled only when the Transfer source, Section/Material/f'ci
  sources, and required joint-face coverage are complete.
- Stored results become `STALE` when station forces, Section Library, concrete
  materials, stressing ratio, construction method, joints, or column chart
  geometry change.
- Overall status covers every active Transfer Load Case; the chart selector
  displays one case at a time for readability.
- Full-length chart includes top/bottom stress, section-specific ACI limit
  traces, governing compression/tension/joint markers, physical-joint markers,
  and actual column footprints/centerlines.
- Chart lines are visualization only; no compliance is inferred between
  unverified imported stations.
- FAIL states produce criterion-specific required actions. A joint tension
  failure can report both the physical-joint and ACI tension failures.

## Scope exclusions

SLS1A does not calculate V2/T principal stress, shear/torsion, cracking,
anchorage-zone or D-region behavior, transfer/development length, local bearing,
or the ACI 318-19 24.5.3.2.1 reinforcement exception. Final Service stress,
Result Summary, Report/QA, and Project JSON analysis-result persistence remain
separate milestones.

## Files

- `concrete_pmm_pro/analysis/crossbeam_sls_transfer.py`
- `concrete_pmm_pro/analysis/__init__.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_sls1a_transfer_stress.py`

## Verification

- Hand-calculated rectangular section sign/equation benchmark.
- ACI compression/tension limit benchmark.
- Precast every-case/every-joint `s-/s+` coverage tests.
- Physical-joint top/bottom compression and multi-failure action tests.
- Cast-in-Place routing test.
- External-FEA once-only/no-generic-load-case test.
- Stable/stale fingerprint tests.
- Full-length Plotly chart and actual column-footprint test.
- Streamlit AppTest source-ready and calculation-button smoke tests.
- Bare app smoke test.

## Repo summary

Complete Crossbeam SLS transfer concrete-stress checks with ACI limits, two-sided physical-joint compression gates, full-length decision charts, required actions, and stale-safe external-FEA routing.

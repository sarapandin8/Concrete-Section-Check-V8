# CROSSBEAM.ANALYSIS3D — Flexure Segment Trace Continuity

## Baseline

This milestone starts from the accepted working baseline:

`concrete-section-pro_CROSSBEAM-ANALYSIS3C-torsion-demand-flexure-trace-fix.zip`

## Scope

This is a plotting/semantics cleanup for Portal Frame Crossbeam ULS Flexure only.
It does not change the ACI 318-19 PMM strain-compatibility solver, imported demand,
section/rebar/tendon sources, or any calculated capacity/utilization value.

## Change

The Crossbeam `φMn` chart now uses Segment-owned traces:

- PMM capacity remains solved at the actual station-specific `Pu`, Section/Rebar source,
  bonded-tendon geometry, and bending side.
- When all solved `φMn` values inside one physical Segment are numerically identical,
  that solved value is displayed continuously to the exact Segment start/end limits.
- Opposite sides of every physical joint remain separate Plotly traces; no Solid/Hollow
  value is linearly interpolated across a joint.
- If solved `φMn` genuinely varies inside a Segment, only actual solved station values
  are connected. The chart does not invent Segment-boundary capacities.
- Hover text distinguishes an actual `SOLVED STATION` from a `STABLE SEGMENT LIMIT`
  used only to complete a constant solved Segment interval.

## Engineering semantics

A constant trace is shown only after the calculated capacities in that Segment agree
within a tight numerical tolerance. This is appropriate where `Pu`, section geometry,
ordinary reinforcement source, bonded tendon source/geometry, and bending side produce
the same solved capacity. A varying station-capacity set is not flattened.

Physical-joint flexural transfer and ordinary-rebar discontinuity rules are unchanged.
This milestone does not certify any new physical-joint capacity or transfer mechanism.

## Files changed

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis3b_joint_capacity_plot.py`
- `README_CROSSBEAM_ANALYSIS3D.md`

## QA executed

- `python -m compileall -q concrete_pmm_pro` — PASS
- `tests/test_crossbeam_analysis3b_joint_capacity_plot.py` — 6 passed
- `tests/test_crossbeam_analysis1a_uls_adapter.py` — 7 passed
- `tests/test_crossbeam_analysis2_uls_shear.py` — 21 passed
- `tests/test_crossbeam_analysis2a_compact_loads_shear_cleanup.py` — 5 passed
- `tests/test_crossbeam_analysis3_uls_torsion.py` — 13 passed
- Shared Beam/Girder ULS chart/workspace selection — 78 passed
- Crossbeam navigation — 7 passed

An attempted wildcard run of all `test_crossbeam_*.py` files did not finish within the
available execution window, so this package does not claim the full Crossbeam suite is green.

## Repo summary

Extend stable Crossbeam flexural capacities continuously to their exact Segment limits while preserving station-specific variation and preventing interpolation across physical joints.

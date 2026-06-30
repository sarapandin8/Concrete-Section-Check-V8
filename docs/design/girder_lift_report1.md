# GIRDER.LIFT.REPORT1 — Generic Precast Lifting Report Integration

## Purpose

Promote the existing non-Railway generic precast lifting-stage preview into report/export outputs without adding a new lifting solver.

## Scope

The report package is active for the same generic precast girder family locked by `GIRDER.LIFT.QA1`:

- Precast / parametric I-Girder
- Precast box beam / box-section beam family
- Plank girder interior/exterior
- Voided plank girder interior/exterior

Railway U-Girder is excluded from the generic package and remains routed through its dedicated Railway U-Girder report workflow.

## Report tables

`concrete_pmm_pro.reporting.generic_precast_lifting_report` generates:

- `generic_precast_lifting_scope`
- `generic_precast_lifting_settings`
- `generic_precast_lifting_load_basis`
- `generic_precast_lifting_station_stress_rows`
- `generic_precast_lifting_governing_rows`
- `generic_precast_lifting_closeout_guard`

These tables are added to the report table registry, report section plan, Analysis → Pre-Report QA panel, and draft Word export.

## Engineering basis

- Load basis: individual precast unit self-weight × lifting impact factor only.
- Excluded auto loads: wet slab/topping, barrier, wearing surface, other SDL, building SDL/LL, and additional service loads.
- Action model: symmetric two-point lifting using the existing `two_point_lifting_moment_kNm` and `two_point_lifting_shear_kN` helpers.
- Stress basis: precast gross section.
- Prestress force state: transfer Pe at each station when the girder strand layout table is available.

## Report boundary

The package is engineering-review report evidence only. It does not perform or certify:

- lifting insert/local hardware design,
- rigging/spreader beam design,
- local concrete breakout around lifting inserts,
- end-zone bursting/splitting reinforcement design,
- transfer/development length certification,
- torsion from skewed or unsymmetrical lifting,
- final code-certified design approval.

## Regression evidence

`tests/test_girder_lift_report1_generic_precast_report.py` locks package availability, table generation, report manifest/table registry integration, Analysis QA-panel wiring, Word export section inclusion, and Railway route separation.

# CROSSBEAM.RB1 — Segment-Based Rebar Templates and Joint Participation

Adds a workflow-scoped ordinary-reinforcement foundation for `Portal Frame Crossbeam — Prestressed Concrete` without changing any existing solver or non-Crossbeam workflow.

## Engineering rule locked by this milestone

- No ordinary reinforcing bar crosses any segment joint.
- Ordinary rebar strength contribution at every joint plane is fixed at `0 mm²`.
- Post-tensioning tendons are the only global flexural-continuity system across segment joints.
- Ordinary reinforcement may be credited only within its assigned precast segment or cast-in-place solid zone in a future station solver.

## What changed

- Routes the Crossbeam `Rebar` subpage to a dedicated workflow-scoped workspace; all other workflows continue to use the existing generic Rebar page.
- Adds a Crossbeam Rebar Template Library for:
  - factory-cast hollow-segment minimum/detailing reinforcement;
  - cast-in-place solid column-region reinforcement;
  - local anchorage/end-block reinforcement.
- Adds segment/zone assignment using Segment Layout as the geometry source of truth.
- Supports multiple rebar zones inside one segment while preventing a zone from crossing a segment boundary.
- Adds a rebar elevation review figure whose schematic ordinary-rebar lines terminate inside each zone.
- Adds locked joint-continuity and calculated station-audit tables.
- Adds Crossbeam-only, namespaced Streamlit state keys.

## Deliberately not changed

- No ULS flexure, PMM, SLS stress, shear, torsion, anchorage-zone, D-region, or report solver consumes RB1 state.
- No generic `rebar_table`, Railway U-Girder, Bridge/Building Beam-Girder, or Column/Pier behavior was modified.
- No Project JSON schema or result persistence was added.
- Tendon geometry and tendon data remain owned by `Tendon System` and `Tendon Profile`.

## Validation

```bash
python -m py_compile app.py \
  concrete_pmm_pro/crossbeam/rebar.py \
  concrete_pmm_pro/ui/crossbeam_pages.py \
  concrete_pmm_pro/ui/crossbeam_rebar_page.py

pytest -q tests/test_crossbeam_rb1_segment_rebar.py \
  tests/test_crossbeam_ui1_workspaces.py \
  tests/test_crossbeam_ui1a_segment_assignment.py \
  tests/test_crossbeam_ui1b_hollow_elevation.py \
  tests/test_crossbeam_ui1c_elevation_polish.py \
  tests/test_crossbeam_wf1_workflow.py \
  tests/test_crossbeam_wf1a_routing_safety.py
```

Crossbeam RB1 and lineage tests: **30 passed**.

Crossbeam plus navigation, Project JSON, design-code, workflow-routing, and selected Rebar regression gate: **142 passed**.

Broader Rebar/Prestress/Analysis/Result Summary/Report cross-workflow gate: **420 passed, 2 deselected**. The two deselected tests fail unchanged in the accepted UI1C baseline and assert older behavior for Bridge Precast-Girder rebar defaults and a legacy Railway U-Girder callback name.

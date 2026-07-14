# CROSSBEAM.UI1 — Workflow-scoped Segment Layout and Tendon Profile views

This milestone starts from the accepted `CROSSBEAM.WF1A` ZIP and changes only the Portal Frame Prestressed Crossbeam Sections navigation.

## Added

- Crossbeam-only Sections subpages: `Tendon System`, `Segment Layout`, and `Tendon Profile`.
- Existing workflows retain `Section Builder | Rebar | Prestress` unchanged.
- Segment Layout elevation with solid/hollow role bands, station boundaries, dimensions, Section IDs, and end-anchor markers.
- Tendon Profile source table using local section axes `x-y`, longitudinal station `s`, and top-referenced `dtop`.
- Plan (`s-x`), Profile (`s-dtop`), and interactive 3D (`s-x-y`) figures from one geometry source.
- Workflow-namespaced state and one-way in-session migration from accepted WF1/WF1A keys.
- Tendon System table for internal/external type, strands, Aps/strand, fpu, fpj/fpu, jacking end, and both end anchor locations.

## Explicitly unchanged

- Existing workflow navigation and solver routing.
- Project JSON schema and result persistence.
- Prestress losses, SLS, ULS, shear/torsion, anchorage zones, deviator forces, and D-region checks.

## Validation

- `python -m py_compile app.py concrete_pmm_pro/ui/crossbeam_pages.py concrete_pmm_pro/ui/section_builder.py`
- Crossbeam UI1 plus accepted cross-workflow regression gate: **200 passed**.
- The accepted WF1A baseline already contains unrelated legacy test conflicts for an old README closeout lock and an obsolete Railway U-Girder callback source assertion; UI1 does not alter those paths.

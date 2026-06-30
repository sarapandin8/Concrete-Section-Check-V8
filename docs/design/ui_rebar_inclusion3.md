# UI.REBAR.INCLUSION3 — Building Beam/Girder rebar exclusion default alignment

## Scope
Extend the rebar inclusion-state fix so Building Beam/Girder shared prestressed girder presets behave like Bridge Beam/Girder presets when the explicit ordinary-rebar checkbox state has not yet been materialized in the current page rerun.

## Included
- Workflow-aware fallback defaults in `ordinary_rebar_enabled` and `prestressing_steel_enabled`.
- Building Beam/Girder + shared Precast I-Girder defaults to ordinary rebar excluded and prestressing enabled when no explicit checkbox state is present.
- Explicit top-level checkbox state and project-metadata state still override workflow defaults.
- Basic RC Building Beam/Girder defaults remain ordinary rebar enabled and prestress disabled.

## Out of scope
- No rebar table deletion.
- No rebar area/parser changes.
- No solver equation changes.
- No project schema changes.

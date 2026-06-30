# REBAR.RAIL.UGIRDER3 — Section Builder to Rebar Immediate UI Sync

## Scope

This hotfix improves the Railway U-Girder ordinary longitudinal rebar workflow after `REBAR.RAIL.UGIRDER2`.

The issue was UX/state-routing related: Section Builder could show `Include ordinary rebar / longitudinal Al` as enabled, but the Rebar page could still enter the disabled/stored branch and ask the user to press `Enable ordinary rebar / longitudinal Al` again. That duplicate action is not acceptable for a commercial workflow.

## Fix

- Section Builder now writes non-widget mirror keys for the steel-system switches:
  - `section_builder_ordinary_rebar_enabled`
  - `section_builder_prestressing_steel_enabled`
  - `section_builder_steel_systems_preset_key`
- Rebar page reconciles the ordinary rebar state before deciding whether to render the disabled/stored branch.
- If Section Builder enabled ordinary rebar for the active preset, the Rebar page opens the Longitudinal Rebar input workspace immediately.
- The existing in-page Enable button remains only as a recovery path for old/stale project states; it should not appear after a valid Section Builder enable action.

## Non-scope

No solver equations, rebar parsing equations, SLS/ULS calculations, prestress logic, debond logic, project schema, or report certification wording were changed.

# SLS.RAIL.UGIRDER4 — Service Load Handoff Preview

## Scope

Adds a guarded Railway U-Girder service-load handoff from active Loads-tab SLS cases into the staged Prestress workflow.

## What changed

- Active SLS load cases from `st.session_state["load_cases"]` are consumed as service-level resultants.
- The preview evaluates `Pu` and `Mux` on the full Railway U-Girder gross basis.
- Station-based `Pe_final(x)` from the debonding participation handoff is added at a user-selected station.
- A service-load stress-limit preview uses `min(f'c web, f'c slab)` for a conservative review-layer check.
- `Muy` is explicitly reported as stored but not included in the 1D top/bottom U-Girder stress preview.

## Guardrails

This milestone does **not** transform and sum web-stage locked-in stress into the full-U service rows. It also does not add:

- transfer-length force ramping,
- development length,
- anchorage / end-zone bursting,
- creep/shrinkage redistribution,
- ULS coupling,
- final code-certified service stress certification.

The feature is a service-load handoff and review preview, not a final certified staged SLS design.

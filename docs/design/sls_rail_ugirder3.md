# SLS.RAIL.UGIRDER3 — Locked-In Staged Stress Accumulation Handoff

## Scope

Adds a guarded Railway U-Girder locked-in staged stress accumulation handoff to the Prestress → Rail U-Girder stages workspace.

This milestone keeps the construction mechanics explicit:

1. **Transfer locked-in web stress** uses one precast web only and includes web self-weight plus `Pe_transfer`.
2. **Wet slab casting locked-in web stress** uses one precast web only and adds the wet slab/formwork load increment plus `(Pe_construction - Pe_transfer)`.
3. **Final Pe handoff on full U-section** uses the full Railway U-Girder gross reference for `(Pe_final - Pe_construction)` only.

The final full-U Pe handoff is intentionally **not** algebraically summed with web-locked top/bottom fibers because the locked web stresses and the full U-section service reference do not share the same section basis/fiber coordinates in this preview layer.

## Engineering guardrails

This is a staged stress **preview / engineering-review handoff**, not a final code-certified SLS design check. It does not model:

- transfer-length force ramping,
- development length,
- anchorage / end-zone bursting,
- creep/shrinkage redistribution,
- final locked-in service-load superposition,
- ULS coupling.

Service loads remain in the Loads/Analysis workflow.

## Files changed

- `concrete_pmm_pro/serviceability/railway_u_girder_stages.py`
- `concrete_pmm_pro/ui/prestress_page.py`
- `tests/test_railway_u_girder_sls_locked_in.py`
- `docs/design/sls_rail_ugirder3.md`
- `README.md`

## Tests

Targeted regression tests cover:

- one-web locked-in rows versus full-U Pe handoff rows,
- station-based debond participation in the locked-in handoff,
- compact governing-row extraction,
- UI guardrail wording.

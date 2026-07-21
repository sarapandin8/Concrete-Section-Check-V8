# CROSSBEAM.PTLOSS2A - Prestress Loss Runtime Settings Hotfix

## Scope

Hotfix only. Repairs the PTLOSS2 Prestress Loss page startup failure caused by malformed `st.session_state.get(...)` argument wiring in `_loss_setting_defaults_from_state()`.

## Change

- Restores `external_inadvertent_angle_rad` to a normal two-argument session-state lookup.
- Adds separate lookups for `anchorage_set_mm` and `ep_mpa`.
- Adds an AST regression guard that verifies every `st.session_state.get(...)` call in the defaults function uses valid two-argument arity and that all six loss-setting fields are present.

## Engineering Boundary

No prestress-loss equation, anchorage-set compatibility solver, friction/wobble solver, `Pj`, `Pe`, `Pe_eff`, PMM, SLS/ULS, rebar, report, Project JSON schema, or other member workflow behavior is changed.

## Verification

- `python -m compileall -q app.py concrete_pmm_pro` — PASS.
- PTLOSS1 + PTLOSS2 targeted regression — 19 passed.
- Crossbeam regression — 207 passed.
- Routing/workflow smoke subset — 14 passed.
- Live Streamlit render was not executed in this runtime because Streamlit is not installed.

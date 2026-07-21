# CROSSBEAM.PTLOSS2 - Anchorage Set / Draw-in Loss Foundation

## Scope

Adds an isolated Crossbeam anchorage-set / wedge draw-in preview downstream of the accepted PTLOSS1 friction/wobble force diagram. The milestone solves a local zero-movement influence length by tendon-strain compatibility, reports lock-off force/stress and station-level additional loss, and keeps `Pe / Pe_eff` plus all later loss/stage solvers locked.

## Engineering method

- Source force diagram: accepted PTLOSS1 `P after friction` / `Stress after friction` station trace.
- Seating input: one adopted `Δa` value in mm applied to each active stressing anchorage.
- Prestressing-steel modulus: editable `Ep`, initialized to 195,000 MPa for the app preview and required to be verified against the project/PT steel basis.
- Default anchorage set is intentionally `0.0 mm`; the component reports `INPUT REQUIRED` until the engineer adopts a positive project/PT supplier value.
- The accepted post-friction force diagram is linearly interpolated between traced stations for the compatibility-area audit.
- The affected length `La` is solved so the integrated strain reduction produced by the mirrored force diagram equals the adopted anchorage movement.
- Within the solved influence zone, the preview uses the mirrored accepted force diagram about the zero-movement point. Outside `La`, the accepted friction/wobble force remains unchanged.

## Guardrails / limitations

- This is a **component-scoped engineering preview**, not a final code-certified effective-prestress result.
- No generic anchorage-loss percentage is introduced.
- `P after anchorage set` is not promoted to `Pe` or `Pe_eff`.
- One-end jacking currently models final seating at the active stressing end only. Dead-end anchorage seating/history remains an explicit PT procedure review item.
- Both-end jacking is treated as independent local seating branches only while each solved influence zone remains inside its half-length branch. If the required seating movement exceeds that isolated branch capacity, the result is `REVIEW REQUIRED`; the solver does not silently superimpose overlapping end effects.
- Cases that require full-length redistribution, opposing-end interaction, or stressing-sequence history are intentionally deferred to a later named solver milestone.
- Friction/wobble blocking issues propagate into PTLOSS2 review status instead of being hidden.
- Elastic shortening, creep, shrinkage, relaxation, SLS/ULS, anchorage-zone, deviator-force, and D-region checks remain outside PTLOSS2.

## UI

The existing `Anchorage Set / Draw-in` subtab is activated with:

- adopted `Δa` input;
- editable `Ep`;
- component status cards;
- per-tendon/per-seating-end compatibility audit;
- solved influence length and maximum isolated compatible set;
- zero-movement stress, anchorage lock-off stress/force, and local anchorage-set loss;
- station trace after the isolated anchorage-set component;
- explicit review/limitation table and calculation-basis expander.

`Overview` and `Audit` now report the anchorage-set component state while keeping overall prestress-loss assembly incomplete and `Pe / Pe_eff` locked.

## Persistence

The existing Crossbeam prestress-loss Project JSON metadata block is advanced to schema version 2 and adds only:

- `anchorage_set_mm`
- `ep_mpa`

Legacy schema-1 projects remain loadable: missing PTLOSS2 values normalize to `Δa = 0.0 mm` and `Ep = 195,000 MPa`, so anchorage-set calculation stays locked until explicitly adopted.

## Changed production files

- `concrete_pmm_pro/crossbeam/anchorage_set.py` — new isolated anchorage-set compatibility solver/audit module.
- `concrete_pmm_pro/crossbeam/prestress_loss.py` — extends Crossbeam-only loss metadata/settings with `Δa` and `Ep`; accepted friction/wobble equations are unchanged.
- `concrete_pmm_pro/ui/crossbeam_pages.py` — activates the Anchorage Set / Draw-in subtab and connects it to the accepted friction profile.

No changes were made to `app.py`, PMM solver, SLS/ULS solvers, rebar logic, reports, shared workflow routing, or other member-workflow production modules.

## Validation

### PTLOSS2 hand-check benchmark

A linear accepted post-friction stress diagram `f(x) = 1400 - 10x MPa` over 20 m with `Ep = 200,000 MPa` and `Δa = 5.0 mm` has the closed-form compatibility solution:

- `La = 10.000 m`
- zero-movement stress = `1300 MPa`
- anchorage lock-off stress = `1200 MPa`
- local anchorage-set loss = `200 MPa`

The PTLOSS2 solver reproduces these values and closes the displacement compatibility residual to numerical tolerance.

Additional regression coverage verifies:

- zero `Δa` remains `INPUT REQUIRED`;
- seating loss is applied only inside `La`;
- a seating value beyond the isolated branch capacity becomes `REVIEW REQUIRED` instead of forcing a false solution;
- both-end local branches are kept isolated inside their half-length boundary;
- PTLOSS2 settings round-trip through the existing Project JSON metadata path;
- UI source keeps `Pe / Pe_eff` locked.

## Verification results

- `python -m compileall -q app.py concrete_pmm_pro`: PASS.
- PTLOSS1 + PTLOSS2 targeted regression: 18 passed.
- Complete Crossbeam suite (`tests/test_crossbeam_*.py`): 206 passed.
- Non-Crossbeam suite run in split batches: 1,834 passed / 4 failed.
- The same four failures reproduce unchanged on the accepted PTLOSS1G baseline and are therefore pre-existing QA debt, not PTLOSS2 regressions:
  1. `tests/test_railway_u_girder_rebar_enable_routing.py::test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change`
  2. `tests/test_rebar_inclusion_visual_regression.py::test_inclusion4_bridge_precast_girder_defaults_store_rebars_but_publish_none`
  3. `tests/test_regression_controls.py::test_app_does_not_reintroduce_sidebar_geometry_parameters`
  4. `tests/test_results_ws2_beam_uls_dashboard.py::test_results_source_blocked_is_treated_as_danger_status`
- A one-process full-suite run timed out at approximately 42%; the suite was then completed in split batches as reported above.
- Live Streamlit render/import smoke was not run because `streamlit` is not installed in the execution runtime.

## Repo summary

Add Crossbeam PTLOSS2 isolated anchorage-set/draw-in compatibility preview that derives influence length and lock-off force from the accepted friction profile while keeping Pe/Pe_eff and other member workflows unchanged.

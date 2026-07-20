# CROSSBEAM.PTLOSS1G - Prestress Loss Subtab Architecture

## Scope

Reorganizes the Crossbeam `Prestress Loss` workspace into component-scoped subtabs without changing accepted prestress-loss equations or downstream solver behavior.

## UI architecture

The Prestress Loss page now contains:

- `Overview` — decision-level status showing only calculations that currently exist and explicitly marking the overall loss state incomplete.
- `Friction & Wobble` — preserves the accepted PTLOSS1A–PTLOSS1E AASHTO friction/wobble assumptions, summary, station trace, review notes, and per-tendon trace output.
- `Anchorage Set / Draw-in` — guarded placeholder for the next validated solver milestone.
- `Elastic Shortening` — guarded placeholder; no calculation is activated.
- `Time-Dependent` — guarded placeholder for creep, shrinkage, and relaxation; no lump-sum approximation is introduced.
- `Audit` — shows the calculation dependency chain and keeps `Pe / Pe_eff` assembly explicitly locked until later loss/stage milestones are validated.

## Engineering guardrails

- Subtab separation is a UI architecture decision only; it does not imply that loss components are mathematically independent.
- Friction/wobble remains the only active Crossbeam prestress-loss calculation.
- Anchorage set must consume the accepted friction-force profile rather than being treated as a generic independent percentage deduction.
- `Pe` and `Pe_eff` are not assembled or released to downstream SLS/ULS checks in this milestone.

## Production-code boundary

Production changes are limited to `concrete_pmm_pro/ui/crossbeam_pages.py`. No equation changes are made in `concrete_pmm_pro/crossbeam/prestress_loss.py`, `tendon_analysis.py`, PMM, SLS/ULS, rebar, reporting, Project JSON schema, shared workflow routing, or other member workflows.

## Regression intent

The existing friction/wobble regression suite remains authoritative for calculation behavior. PTLOSS1G adds source-level regression coverage for the six-subtab architecture and guarded future-component wording.

## Repo summary

Add Crossbeam PTLOSS1G component-scoped Prestress Loss subtabs with guarded future-loss placeholders and a dependency audit while preserving the accepted friction/wobble solver behavior.

## Verification results

- `python -m compileall -q app.py concrete_pmm_pro tests`: PASS.
- Targeted PTLOSS1/PTA1/Crossbeam UI regression set: 26 passed.
- Crossbeam regression suite (`tests/test_crossbeam_*.py`): 199 passed.
- Cross-workflow routing/service smoke set: 50 passed.
- The four known pre-existing failures documented in PTLOSS1F were rerun and remain unchanged; none is caused by PTLOSS1G.

Known pre-existing QA debt retained unchanged:

1. `tests/test_railway_u_girder_rebar_enable_routing.py::test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change`
2. `tests/test_rebar_inclusion_visual_regression.py::test_inclusion4_bridge_precast_girder_defaults_store_rebars_but_publish_none`
3. `tests/test_regression_controls.py::test_app_does_not_reintroduce_sidebar_geometry_parameters`
4. `tests/test_results_ws2_beam_uls_dashboard.py::test_results_source_blocked_is_treated_as_danger_status`

The full all-tests suite was not rerun end-to-end in one process for PTLOSS1G; validation used the complete Crossbeam suite plus targeted cross-workflow smoke coverage and explicit reproduction of the four accepted pre-existing failures.

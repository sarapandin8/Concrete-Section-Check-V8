# SLS.RAIL.UGIRDER2 — Stage Stress-Limit Preview

## Purpose

This milestone extends the Railway U-Girder staged SLS workflow from stress preview into a guarded, stage-aware stress-limit preview.

The work deliberately keeps the Railway U-Girder calculation as a **preview / engineering-review workflow**, not a final code-certified design check.

## Scope

Added:

- Stage-aware stress-limit handoff for the existing Railway U-Girder staged stress preview.
- Transfer and lifting limit checks use one precast web and `f'ci(web)`.
- Wet slab casting limit checks use one precast web and `f'c(web)`.
- Full-U service Pe reference uses `min(f'c web, f'c slab)` as a conservative preview strength until the final locked-in/transformed service workflow is implemented.
- Compact governing limit table in the `Prestress → Rail U-Girder stages` tab.
- Station-by-station stress + limit table in an expander.

## Guardrails

This milestone does **not** implement:

- final locked-in staged stress superposition for all service load components;
- service live-load / SDL integration from the Loads tab;
- transfer-length force ramping;
- development length;
- end-zone bursting / anchorage checks;
- ULS coupling;
- final AASHTO/ACI code certification.

## Changed files

- `concrete_pmm_pro/serviceability/railway_u_girder_stages.py`
- `concrete_pmm_pro/ui/prestress_page.py`
- `tests/test_railway_u_girder_sls_stage_limits.py`
- `docs/design/sls_rail_ugirder2.md`
- `README.md`

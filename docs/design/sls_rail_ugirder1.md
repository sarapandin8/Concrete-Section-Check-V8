# SLS.RAIL.UGIRDER1 — Railway U-Girder Staged Stress Preview

## Scope

This milestone adds a preview-only staged stress handoff for the Railway U-Girder preset.

The preview is intentionally conservative about stage basis selection:

- Transfer: one precast web only
- Lifting: one precast web only
- Wet slab casting: one precast web only
- Service Pe reference: full Railway U-Girder gross reference

## Engineering assumptions

- Concrete unit weight and construction settings are read from `railway_u_girder_stage_settings`.
- Wet slab casting is Case B: wet slab and formwork load are split 50/50 to the two precast webs.
- Transfer/lifting/wet casting prestress uses one-web strand groups only for web-stage stresses.
- Full-U service Pe reference uses both webs.
- Debonded strand participation is station-based and step-function only.

## Not included

This milestone does not implement locked-in staged stress superposition, transfer-length force ramping, development length, anchorage, end-zone bursting, final stress-limit certification, or ULS coupling.

## Changed files

- `concrete_pmm_pro/serviceability/railway_u_girder_stages.py`
- `concrete_pmm_pro/ui/prestress_page.py`
- `tests/test_railway_u_girder_sls_stage_preview.py`
- `docs/design/sls_rail_ugirder1.md`
- `README.md`

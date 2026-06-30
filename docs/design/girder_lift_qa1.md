# GIRDER.LIFT.QA1 — Generic Precast Lifting Stage Audit

## Purpose

Audit the existing non-Railway precast girder lifting-stage workflow and lock the observed engineering boundaries with regression tests. This is not a new lifting solver. The feature already exists and is routed through the Beam/Girder SLS staged workflow.

## Existing behavior confirmed

- Railway U-Girder remains on its dedicated one-web lifting route.
- Generic precast lifting is exposed for:
  - parametric I-girder
  - precast box beam / box-section beam family
  - plank girder interior/exterior
  - voided plank girder interior/exterior
- Generic lifting stage uses an individual precast unit basis.
- Auto load for generic lifting is limited to `Precast unit self-weight × lifting IF`.
- Wet slab/topping, barrier/sidewalk, wearing surface, other SDL, building SDL, building LL, and additional SDL are excluded from lifting auto load.
- Full-length SLS preview uses two-point lifting moment and shear functions for the Lifting stage.
- Lifting stage uses transfer prestress force state (`pe_transfer_eff_kN`) for station-based stress preview.
- Section Builder exposes generic lifting inputs without Railway-only wording:
  - `Lifting a/L`
  - `Lifting impact factor`
  - `Individual precast unit`

## Engineering boundary

This preview checks global top/bottom stresses for the precast unit during handling. It does not replace project-specific lifting insert design, local anchorage/hardware checks, end-zone bursting/splitting design, transfer/development length design, or certified lifting method statements.

## QA status

`tests/test_girder_lift_qa1_generic_precast_closeout.py` locks the routing, load basis, two-point lifting diagram handoff, transfer prestress force selection, and UI wording boundaries.

## GIRDER.LIFT.QA2 station-sync follow-up

The Analysis SLS Lifting-stage station grid now explicitly injects the current two-point lifting stations from Section Builder (`a` and `L-a`). This fixes the previous stale-station behavior where Analysis could keep using an old station grid after `Lifting a/L` changed in Section Builder, especially when the stage already had multiple generated rows.

Implementation guard:
- Generic precast lifting reads `beam_girder_system_settings.lifting_point_ratio`.
- Railway U-Girder lifting reads `railway_u_girder_stage_settings.lifting_point_ratio`.
- Lifting-stage rows no longer early-return solely because two or more stations already exist; the current lifting points are regenerated/merged into the grid.

## GIRDER.LIFT.QA3 live-widget and visual-marker follow-up

The prior QA2 station-grid sync still allowed a Streamlit rerun edge case where the visible Section Builder number-input value could be newer than the persisted settings dictionary read by Analysis. Analysis now merges the live Section Builder widget keys before computing lifting stations, moments, and Railway U-Girder staged-stress previews.

Implementation guard:
- Railway U-Girder Analysis reads live keys such as `rail_ugirder_assembly_lifting_ratio_input`, `rail_ugirder_assembly_lifting_impact_input`, and `rail_ugirder_assembly_span_length_m_input` before falling back to `railway_u_girder_stage_settings`.
- Generic bridge/building precast girder Analysis similarly merges live section-assembly widget keys before using `beam_girder_system_settings`.
- Lifting-stage stress graphs now draw vertical markers at the current lifting points `a` and `L-a`, so the user can visually separate true lifting locations from governing stress locations caused by debonding or code-limit effects.
- The SLS stage-context card now displays the current Section Builder lifting points for Lifting stage.

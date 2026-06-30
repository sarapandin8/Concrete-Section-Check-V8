# UI.REBAR.COMPACT1 — Rebar Workspace Commercial Layout Polish

## Scope

Polish the Rebar workspace after the inclusion-state regression milestone so the page reads like a compact decision/input workspace instead of a loose sequence of headings.

## Changes

- Added compact panel title/subtitle styling for Rebar input, status, and preview cards.
- Added explicit active `Analysis Participation: Included` summary chip when ordinary rebar is enabled.
- Reworked the ordinary-rebar disabled branch into a two-column stored/excluded layout:
  - left: stored longitudinal rebar source and collapsed stored table preview
  - right: analysis participation gate and stored/excluded section preview
- Collapsed detailed longitudinal summary tables below the decision view.
- Reduced Rebar preview heights to reduce vertical scroll.

## Preserved behavior

- Stored rebar rows are still preserved when ordinary rebar is disabled.
- Disabled ordinary rebar still publishes zero active analysis rebars.
- Rebar and prestress default previews remain separated; combined reinforcement remains a collapsed coordination view.
- Dimension guides remain hidden on the Rebar page; Section Builder remains the dimension source.

## Out of scope

- PMM solver
- Prestress solver or force logic
- Section geometry or section-property calculations
- SLS workflows
- Shear/torsion calculation logic
- Project schema and report export

## Tests

Targeted tests for this milestone should include `tests/test_rebar_compact_workspace.py` plus the existing rebar inclusion, rebar layout, prestress preview policy, project IO, analysis mode, workflow alignment, commercial tab, and widget-key regression groups.

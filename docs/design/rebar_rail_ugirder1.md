# REBAR.RAIL.UGIRDER1 — Railway U-Girder Ordinary Rebar Enable Routing Hotfix

## Purpose

This hotfix addresses a Railway U-Girder workflow regression where the engineer can enable `Include ordinary rebar / longitudinal Al` in Section Builder but the Rebar workspace can still show the disabled `Stored Longitudinal Rebar` review state, preventing input of ordinary longitudinal rebar.

## Scope

- Keep Section Builder as the owner of the section-level ordinary-rebar / prestress participation switches.
- Synchronize the Section Builder checkbox state into `project_metadata` via an explicit `on_change` callback.
- Add an in-page recovery action in `Sections → Rebar → Longitudinal Rebar` so a stale disabled state can be corrected without navigating back to Section Builder.
- Publish ordinary-rebar enable state consistently to:
  - `section_has_ordinary_rebar`
  - `project_metadata.section_has_ordinary_rebar`
  - `reinforcement_flags_preset_key`
  - `project_metadata.reinforcement_flags_preset_key`

## Non-scope

This milestone does not change:

- rebar parsing equations,
- SLS stress equations,
- ULS flexure/shear/torsion equations,
- prestress or debonding participation logic,
- geometry generation,
- project schema,
- report certification wording.

## User-facing behavior

When ordinary rebar is enabled in Section Builder, the Longitudinal Rebar input table should be available in the Rebar workspace. If the Rebar page is reached with a stale disabled flag, the disabled panel now includes an `Enable ordinary rebar / longitudinal Al` action that synchronizes state and opens the input table on rerun.

## Validation

Added regression tests in:

```text
tests/test_railway_u_girder_rebar_enable_routing.py
```

The tests verify that:

- the Section Builder ordinary-rebar checkbox synchronizes metadata on change,
- the Rebar disabled panel includes an in-page enable recovery action,
- the publish helper aligns top-level state and project metadata for `railway_u_girder`.

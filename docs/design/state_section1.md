# STATE.SECTION1 — Section Builder Durable Parameter Restore

## Scope

This milestone fixes a Streamlit widget-state lifecycle issue where Section Builder geometry inputs could return to preset defaults after the user navigated through Setup, Loads, or Analysis and then reopened Section Builder.

The change is state-management only. It does not change PMM, prestress, shear, torsion, V+T, SLS stress, deflection, report, material, or geometry-generator equations.

## Root cause

`PERF.RERUN1` intentionally avoids rendering inactive workspaces. That is the correct performance architecture, but Streamlit widget-owned keys may be removed when widgets are not rendered. Section Builder number inputs were seeded directly from preset defaults when their widget keys were absent.

The durable project model (`section_parameters`, `section_geometry`, and `section_preset_key`) still retained the user-edited section, but the next Section Builder render could rebuild geometry from preset defaults and overwrite the durable model.

## Fix

- Add a durable owner key: `section_parameters_preset_key`.
- Backfill the owner for existing sessions/project loads from `section_preset_key`.
- Restore geometry parameter widget defaults from durable `section_parameters` when the stored parameters belong to the active preset.
- Restore composite metadata number/select/checkbox defaults from durable `section_parameters`.
- Prevent durable parameters from leaking across preset changes.
- Preserve Setup as the owner of locked girder span metadata; Section Builder still mirrors span from Setup by design.

## QA notes

Added tests confirm:

- geometry number inputs restore from `section_parameters` after simulated widget cleanup,
- durable values do not leak when a different preset is selected,
- composite metadata inputs restore from durable parameters after navigation.

## Engineering boundary

This milestone protects user intent and model state. It does not certify or alter any engineering calculation.

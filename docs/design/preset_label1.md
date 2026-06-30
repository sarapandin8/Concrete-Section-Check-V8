# PRESET.LABEL1 — Workflow Preset Label De-duplication Hotfix

## Scope

Fixes the Section Builder preset selector label for workflow-specific aliases that already include the preset category.

## Problem

`PRESET.ROUTING1` introduced workflow-specific aliases for shared presets such as the Precast I-Girder:

- `Precast I-Girder: Building · Precast Composite Girder`
- `Precast I-Girder: Bridge · Precast Composite Girder`

The selector option label then appended the preset category again, producing a duplicated UI label such as:

`Precast I-Girder: Bridge · Precast Composite Girder  ·  Precast Composite Girder`

This was a display-label bug only.  The stable preset key, generator, routing metadata, and calculation logic were not changed.

## Change

`_preset_option_label()` now returns the workflow-specific alias directly when the alias already contains the category text.  Otherwise, it continues to show the normal `Display name · Category` label for generic presets such as `Rectangle · Basic Solid`.

## Out of scope

- No section preset routing changes.
- No geometry generator changes.
- No solver, PMM, SLS, prestress, rebar, report, or project-schema calculation changes.

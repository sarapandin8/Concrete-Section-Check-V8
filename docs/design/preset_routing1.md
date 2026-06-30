# PRESET.ROUTING1 — Workflow-Specific Preset Filtering and Naming

## Scope

This milestone hardens the Section Builder preset selector as the library grows.
It adds explicit workflow metadata to section presets so Building Beam/Girder,
Bridge Beam/Girder, and Column/Pier workflows see only presets that belong to
their engineering context.

## Engineering intent

- `Setup → Materials` remains a material library, not a per-section assignment
  source.
- `Sections → Section Builder` remains the source for section/preset selection.
- Building Beam/Girder must not show infrastructure-only presets such as:
  - `Slab Bridge`
  - `Railway U-Girder`
  - future bridge/railway/highway-only presets
- Filtering is driven by explicit `allowed_workflows` preset metadata, not by
  brittle keyword matching against display names.

## Precast I-Girder naming

The existing `parametric_i_girder` key and geometry generator are preserved for
backward compatibility.  The UI now applies workflow-specific display aliases:

- Bridge Beam/Girder: `Precast I-Girder: Bridge · Precast Composite Girder`
- Building Beam/Girder: `Precast I-Girder: Building · Precast Composite Girder`

This avoids duplicating geometry code while making the workflow context clear to
the user.

## Out of scope

No solver, PMM, SLS, prestress loss, rebar, geometry-generator, section-property,
load-import, report, or project-schema calculation logic is changed.

## QA notes

Regression tests check that:

- Building Beam/Girder hides bridge/railway-only presets.
- Bridge Beam/Girder still shows bridge and railway presets.
- Precast I-Girder labels change by workflow while its stable key remains
  unchanged.
- Preset filtering reads `allowed_workflows` metadata rather than display-name
  keywords.

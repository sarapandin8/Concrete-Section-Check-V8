# SECTION.ASSEMBLY1 — Move Beam/Girder System Settings to Section Assembly

## Scope

This milestone moves user-facing Beam/Girder system settings out of Setup and into Section Builder as workflow-specific assembly controls.

- Bridge Beam/Girder shows **Bridge Section Assembly**.
- Building Beam/Girder shows **Building Member Assembly**.
- Existing metadata key `beam_girder_system_settings` remains the persistence and downstream-consumer source so saved projects and Loads/Prestress/SLS previews stay compatible.

## Engineering intent

Setup is now reserved for project identity, active workflow, and design-code routing. Assembly inputs are section-specific because I-girders, box beams, plank girders, and Railway U-girders have different unit counts, spacing/module-width concepts, and staged behavior.

## Guardrails

- No solver equations changed.
- No geometry generator changed.
- No load-component equation changed.
- No report logic changed.
- Legacy project metadata remains readable through the existing metadata key.

## UI policy

- Bridge workflow: use **Bridge Section Assembly** wording.
- Building workflow: use **Building Member Assembly** wording.
- Loads page captions now direct users back to Section Builder rather than Setup for assembly values.

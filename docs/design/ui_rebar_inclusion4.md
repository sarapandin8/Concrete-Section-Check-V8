# UI.REBAR.INCLUSION4 — Rebar Inclusion Visual Regression Check

## Scope
Add a focused regression gate for the ordinary-rebar inclusion visual/state contract across the active workflows. This milestone is intentionally QA-heavy and does not change solver behavior.

## Included
- Column/Pier defaults: ordinary rebar enabled, prestress disabled, stored ordinary bars publish as active analysis bars.
- Bridge Beam/Girder precast composite defaults: ordinary rebar excluded, prestress enabled, stored ordinary bars publish as zero active analysis bars until explicitly enabled.
- Building Beam/Girder shared prestressed girder defaults: ordinary rebar excluded, prestress enabled, matching the UI.REBAR.INCLUSION3 contract.
- Building basic RC beam defaults: ordinary rebar enabled, prestress disabled.
- Explicit checkbox state remains the source of truth over workflow defaults.
- Rebar page disabled-state source check confirms the user-facing cards say stored/excluded and publish zero active analysis rebars.

## Out of scope
- No solver equation changes.
- No section-geometry or section-property changes.
- No rebar parser/table schema changes.
- No prestress force, SLS, shear, torsion, report, or project-JSON schema changes.

## QA notes
This milestone deliberately verifies the gap that can break commercial trust: stored rows may exist, but disabled ordinary rebar must not leak into active PMM/SLS/shear/torsion assembly. The visual state and analysis participation state must agree.

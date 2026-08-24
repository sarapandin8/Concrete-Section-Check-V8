# IGIRDER.ULS6C1 — Torsion Rebar Runtime Hotfix

Hotfix for the Precast I-Girder Sections → Rebar → Transverse Rebar runtime error introduced in ULS6C.

## Fix
- Removed an accidental zero-argument call to `_render_igird_torsion_layout_settings()`.
- The torsion layout renderer requires the normalized provided shear-zone table and is now invoked only by the existing correct call `_render_igird_torsion_layout_settings(normalized)` after the shear-zone editor has normalized/stored the current layout.
- No engineering equations, torsion/shear result versions, Project JSON schema, or solver behavior were changed.

## Regression guard
A ULS6C regression assertion now prevents reintroducing a zero-argument torsion-layout renderer call.

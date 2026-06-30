# MATERIAL.ROUTING1 — Material Library and Assignment Source-of-Truth

## Scope

This milestone tightens material routing before further Railway U-Girder staged-stress work.

## Changes

- Setup → Materials is now treated as a library page only.
- Active section concrete assignment remains in Sections → Section Builder.
- Railway U-Girder Section Builder material assignment now captures:
  - precast web concrete material,
  - precast web f'ci at transfer,
  - CIP slab concrete material,
  - ACI auto Ec/Eci display through the assignment summary,
  - synchronized `railway_u_girder_stage_settings` material metadata.
- Standard DB rebar sizes now enforce material/fy routing by bar size:
  - DB10, DB12, DB16, DB20, DB25, DB28 → SD40 / fy 390 MPa,
  - DB32 → SD50 / fy 490 MPa.
- Imported or legacy standard-bar rows with mismatched material are corrected during parsing and warned.
- Prestress Product remains the source of truth for product material properties:
  - Area,
  - fpy,
  - fpu,
  - Ep.

## Explicitly unchanged

- PMM solver equations.
- SLS stress equations.
- Prestress force/loss / Pe_eff equations.
- Shear/torsion logic.
- Geometry generators and section-property kernel.
- Report logic.

## Engineering note

This milestone intentionally avoids using Setup → Materials as a global assignment page because different section presets can require different concrete material routing. Railway U-Girder staged construction requires web f'c/f'ci and CIP slab f'c to be section-specific before stress stages are calculated.

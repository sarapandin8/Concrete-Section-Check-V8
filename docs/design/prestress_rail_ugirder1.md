# PRESTRESS.RAIL.UGIRDER1 — Railway U-Girder Default Strand Layout

## Scope

Add a drawing-based default prestressing strand layout for the `Railway U-Girder` Bridge Beam/Girder preset.

## Implemented

- Enables the dedicated girder strand/debonding workflow for `railway_u_girder`.
- Seeds 72 strands total: 36 strands per side.
- Uses 12.7 mm low-relaxation strand as the default product basis, consistent with ASTM A416 Grade 270 / 1860 MPa drawing notes.
- Row elevations from bottom fiber: 95, 150, 205, 260, and 315 mm.
- Horizontal drawing grid per side: outside edge 130 mm, 8 spaces @ 55 mm, inside edge 80 mm.
- Row counts per side: 9, 9, 7, 7, and 4 strands from bottom to top.
- Adds optional `Debond pattern mm` metadata for per-strand drawing symbols: 0, 1000, 2000, 3000, 4000, 5000 mm.
- Renders drawing debond symbols in the cross-section strand plot when the pattern field is populated.
- Preserves strand x positions, individual debond strand numbers, and debond symbol pattern in project metadata.

## Deliberate limits

- `Debond pattern mm` is preview/drawing metadata only.
- Station-based effective prestress still uses the existing row-based `Left debond m`, `Right debond m`, and `Debonded strand nos` fields.
- No PMM, SLS stress, loss, shear/torsion, geometry, rebar, report, or project-schema solver changes.
- Project-specific debond mapping is not guessed from the drawing; the field is ready for the user-provided pattern.

## Validation

Targeted tests cover:

- Railway U-Girder dedicated strand workflow enablement.
- 72-strand default layout, row counts, x positions, y positions, and validation.
- Preview-only debond symbol rendering for 1000/2000/3000/4000/5000 mm.
- Project IO source preservation of x positions and debond metadata.

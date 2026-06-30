# DESIGN.CODE.ROUTE2 — Column/Pier AASHTO display and capability guard

## Purpose

Column / Pier / Wall / Pylon workflow may use either ACI 318 or AASHTO LRFD as the project design-code basis. The Analysis page must preserve and display the selected project code rather than falling back to ACI 318.

## Confirmed solver scope

Current Column/Pier/Wall/Pylon solver capability is still ACI-oriented:

- PMM: ACI-oriented RC/PSC interaction preview; AASHTO LRFD PMM is not implemented.
- Shear: ACI 318 RC scoped shear gate only.
- Torsion: ACI 318 RC scoped torsion gate only.
- Shear + Torsion: ACI 318 RC nonprestressed interaction gate only.

When AASHTO LRFD is selected for Column/Pier/Wall/Pylon, Analysis must show AASHTO LRFD as the project code but keep the result status as REVIEW / planned / not implemented, with no AASHTO PASS/FAIL capacity claim.

## Implementation note

Analysis cards, settings, summary strips, and Column/Pier strength guards read workflow-compatible project code/edition helpers. This prevents stale ACI labels when Setup selects AASHTO LRFD for the Column/Pier workflow.

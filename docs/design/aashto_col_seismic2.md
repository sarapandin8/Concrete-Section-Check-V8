# AASHTO.COL.SEISMIC2 — transverse detailing UX and clear-height assistant

## Purpose

Clarify the Column/Pier/Wall/Pylon transverse reinforcement workflow after the
AASHTO LRFD seismic advisor was introduced.  The previous UI could make users
think a shear-strength PASS meant the transverse reinforcement was acceptable for
seismic confinement.  This milestone separates:

1. the **Control section row** used by shear/torsion strength checks, and
2. the **AASHTO seismic bridge-column advisor** used to review expected
   plastic-hinge confinement detailing.

## AASHTO basis

The advisor remains scoped to Section 5.11.4 input/detailing support.  For
plastic-hinge confinement length, the advisor reports the controlling value from:

- maximum cross-sectional member dimension,
- one sixth of the entered clear height, and
- 18.0 in, converted to 457.2 mm.

For spacing, the advisor keeps the AASHTO Section 5.11.4.1.5 limit as the lesser
of 0.25 times the minimum member dimension and 4.0 in.  For hoop/spiral area, it
continues to use the Section 5.11.4.1.4 area/volumetric-ratio checks from the
current control-section row.

## UX changes

- Renamed the selectable option from the old manual-review label to
  `AASHTO LRFD seismic bridge-column advisor`.
- Legacy saved projects using the old label are still normalized to the new
  option.
- Added a Plastic-hinge confinement length assistant card with:
  - clear-height input status,
  - 1/6 clear-height value,
  - maximum section dimension,
  - 18 in minimum,
  - recommended confinement length to use for special transverse reinforcement.
- Added explicit status cards for:
  - seismic spacing check,
  - Ash/rho check,
  - overall seismic detailing.
- If the AASHTO advisor FAILs, the UI now states that shear strength may pass but
  seismic confinement must be revised before treating the transverse detail as
  final.

## Limitations

The advisor does not certify the seismic system, R-factor selection, plastic
hinge location, overstrength column shear demand, splice restriction/location,
hook anchorage/shop-drawing geometry, pile-bent special cases, or wall-type pier
special provisions.  These remain engineering review items.

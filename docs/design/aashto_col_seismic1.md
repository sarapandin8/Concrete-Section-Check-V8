# AASHTO.COL.SEISMIC1 — Column/Pier seismic transverse detailing advisor

## Purpose

This milestone replaces the previous manual-review-only AASHTO seismic message in
Sections → Rebar → Column/Pier Shear and Torsion Reinforcement with a bounded
AASHTO LRFD 9th Section 5.11.4 transverse detailing advisor.

The advisor is intentionally an input/detailing check, not a full seismic design
certification.  It does not create overstrength shear demand, select the bridge
seismic system/R-factor, qualify splice locations, or certify shop-drawing hook
anchorage.

## Implemented scope

The advisor evaluates the current Column/Pier control-section transverse row for:

1. AASHTO LRFD 5.11.4.1.5 maximum confinement spacing:
   - `s <= 0.25 * minimum member dimension`
   - `s <= 4.0 in`
2. AASHTO LRFD 5.11.4.1.5 plastic-hinge confinement length:
   - maximum cross-section dimension
   - one sixth of clear height when clear height is entered
   - 18.0 in
3. AASHTO LRFD 5.11.4.1.4 rectangular hoop confinement area:
   - `Ash >= 0.30*s*hc*(fc/fyh)*(Ag/Ac - 1)`
   - `Ash >= 0.12*s*hc*(fc/fyh)`
4. AASHTO LRFD 5.11.4.1.4 circular spiral/seismic hoop ratio:
   - `rho_s >= 0.12*fc/fyh`
   - also checks the Article 5.6.4.6 spiral minimum when it governs
5. Seismic hook note:
   - 135-degree hook extension larger of `6db` or `3 in`
   - `fyh <= 75 ksi` warning for seismic hooks

## Unit policy

AASHTO Section 5 uses ksi/in units.  The app remains SI internally.

For the confinement area equations used in this milestone, `fc/fyh` is a stress
ratio.  Therefore the same stress unit can be used in the numerator and
denominator.  The implementation uses MPa/MPa consistently and converts only the
explicit inch limits, such as `4 in`, `18 in`, and `3 in`, into mm.

## UI behavior

When the user selects `AASHTO LRFD seismic bridge-column advisor`, the
old warning is replaced by an expanded advisor panel showing:

- advisor status,
- maximum spacing,
- suggested spacing rounded down to the project spacing increment,
- governing spacing criterion,
- criteria table,
- warnings and notes,
- an action button to apply the suggested spacing to the first control-section
  transverse row.

The option label is intentionally retained for backward compatibility with
existing saved project metadata, but the route is no longer manual-only.

## Analysis page behavior

The Shear tab now displays the AASHTO seismic advisor row when this option is
selected, instead of only saying that seismic detailing is unimplemented.  The
shear strength calculation still uses the control-section row; the seismic
advisor is a detailing/input review layer.

## Guarded exclusions

The following remain engineering review/future milestones:

- bridge seismic system/R-factor selection,
- overstrength column shear demand per Section 3 seismic provisions,
- full splice qualification and layout checking,
- actual hook/cross-tie geometry verification,
- pile bent/pile-specific confinement below mudline,
- wall-type pier special provisions,
- hollow-wall local buckling and local wall confinement,
- shop drawing certification.

## Tests

Added `tests/test_aashto_col_seismic1.py` covering:

- spacing and confinement length conversion to SI,
- rectangular hoop `Ash` equations with MPa/MPa ratios,
- circular spiral `rho_s`/`Asp` requirement,
- Rebar page advisor behavior,
- Analysis page advisor summary row.

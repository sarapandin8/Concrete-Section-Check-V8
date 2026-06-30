# AASHTO.COL.SEISMIC4 — Seismic Ash/rho fail-reason summary

## Purpose

AASHTO.COL.SEISMIC4 clarifies the Rebar-page AASHTO LRFD bridge-column seismic advisor when the spacing check passes but the confinement area check fails.

The previous UI exposed `Ash / rho check = FAIL D/C ...` but did not explain enough of the engineering reason. Users could see a passing spacing check and still not understand that the transverse confinement area was insufficient.

## UI changes

The AASHTO seismic advisor now includes a `Recommended seismic detailing summary` panel with compact engineering cards:

- Current spacing
- Spacing action
- Provided Ash
- Required Ash
- Confinement length
- Required action

When the spacing check fails, the app reports the current spacing, the AASHTO limit, and the D/C ratio.

When the Ash/rho check fails, the app reports:

- Provided Ash from the selected control-section row
- Governing required Ash
- Governing axis (`x/core width` or `y/core depth`)
- Area D/C ratio
- Required action: increase effective hoop/cross-tie legs, increase bar size, or reduce spacing

## Table wording

The advisor criteria table previously used the column label `Limit (mm)` for rows that also contained area values such as `Ash`. The display table now renames this column to `Value` inside the AASHTO advisor so mixed spacing, length, and area rows are not mislabeled as all being millimeter limits.

## Engineering scope

This milestone does not change any AASHTO calculation. It only improves communication of the existing seismic spacing, confinement length, and Ash/rho results.

The advisor remains a design/detailing aid. Final seismic zone, plastic-hinge locations, hook anchorage, cross-tie arrangement, lap-splice restrictions, and drawing details remain engineer-review items.

## Tests

Added:

- `tests/test_aashto_col_seismic4_fail_reason.py`

Coverage includes:

- Governing required Ash axis selection
- Fail-reason wording with provided vs required Ash and D/C
- Summary metrics that call for added confinement steel when spacing passes but Ash fails

# SHEAR.GOVERNING1 — Beam/Girder ULS Shear Governing-Station Selection Hotfix

## Purpose

This hotfix corrects the Beam/Girder ULS shear governing-row selection used by the compact ULS table, summary cards, shear chart marker, and shear audit table.

A user review of the Railway U-Girder ULS screen showed a confusing shear result: the peak shear demand and plotted critical-section demand were much higher than the compact governing shear row, but the compact table reported a low-demand row because all rows shared the same failing detailing D/C.  The previous ranking mixed two different concepts:

- sectional strength governing station, which should be selected from shear strength D/C and demand; and
- detailing acceptance, which is a zone/detailing gate and can fail independently of the governing strength station.

## Change

The displayed governing shear row now ranks non-boundary rows by:

1. `Strength D/C value`,
2. absolute shear demand `|Vu|`, and
3. critical-section marker priority as a tie-breaker.

It does not rank the displayed governing station by the zone-wide detailing D/C alone.  A separate overall shear status scan still fails the check if any non-boundary row has a failing detailing or strength gate.

## Preserved behavior

- Minimum Av/s and maximum spacing failures still produce an overall shear `FAIL`.
- The Detailing guard card remains the place where Av/s and spacing failure are displayed explicitly.
- Critical-section rows remain visible in the diagram.
- No shear equation, torsion equation, flexure equation, SLS equation, prestress/debonding logic, section geometry, or project schema is changed.

## User-visible result

For cases where a low-demand row and a critical-section row share the same detailing failure, the compact table and governing marker now report the critical/highest strength-D/C row, while the row/status still communicates that the overall shear check fails because of detailing.

## Validation

Regression tests added in `tests/test_uls_girder_compact_workspace.py` verify that:

- the governing shear row uses the highest strength D/C instead of an arbitrary detailing-only row;
- the compact ULS table keeps the overall shear status as `FAIL` when detailing fails;
- the shear audit marks the strength-governing station, not the low-demand detailing-only station.

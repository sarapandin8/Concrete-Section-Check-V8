# AASHTO.COL.TORSION1 — Column/Pier AASHTO LRFD scoped torsion route

## Purpose

This milestone adds an AASHTO LRFD 9th Edition scoped torsion route for the **Column / Pier / Wall / Pylon — RC / Prestressed Member** workflow when the project design code is AASHTO LRFD.

The route is intentionally limited to **nonprestressed B-region closed-transverse torsion**. It does not replace the later combined shear + torsion interaction milestone.

## Basis and route

The implemented route reads active case-based `Tu` rows from the Column/Pier ULS load table and active closed transverse reinforcement from the Rebar page control-section row.

Implemented checks:

- AASHTO torsion investigation threshold: `Tu` compared with `0.25 φTcr`.
- AASHTO closed-transverse torsional resistance: `Tn = 2 Ao At fy cot(theta) / s`.
- Simplified theta policy aligned with AASHTO.COL.SHEAR1: `theta = 45°`.
- AASHTO shear/torsion resistance factor: `φ = 0.90`.
- Closed tie/hoop/spiral requirement; open ties remain shear-only review input.
- `At/s` transverse torsion demand and D/C.
- Torsion-only longitudinal reinforcement preview `Al` from the Section 5.7.3.6.3 relationship, with ordinary active rebar as the current source of provided `Al`.
- Torsion spacing gate `s <= min(ph/8, 12 in)`.

## Unit handling

AASHTO Section 5 formulas are written with `ksi`, `kip`, and `in`. Concrete Section Pro uses SI internally.

The torsion helper evaluates the `0.126 sqrt(f'c)` cracking-torsion stress through the shared AASHTO unit-safe helper before multiplying by SI geometry. Geometry remains in `mm` and areas in `mm²`; capacities are returned in `N-mm` and displayed in `kN-m`.

## Guarded scope

The following remain guarded and are not final PASS/FAIL scope in this milestone:

- Prestressed torsion and tendon contribution to torsion longitudinal reinforcement.
- AASHTO general shear/torsion procedure with refined `β`, `θ`, and strain effects.
- Combined shear + torsion interaction.
- Multi-cell hollow torsion and engineer-defined multi-cell shear-flow path validation.
- Seismic overstrength torsion demand.
- Anchorage, hooks, lap splices, development length, and shop-drawing details.

## UI changes

The Column/Pier Torsion tab now reports AASHTO route labels, `φTn`, `0.25φTcr`, `At/s`, `Al`, spacing, and D/C values when AASHTO LRFD is selected. The previous "AASHTO torsion not implemented" messages were replaced by scope-accurate AASHTO.COL.TORSION1 route wording. The Shear + Torsion tab remains guarded for AASHTO until the V+T milestone is validated.

## Regression coverage

`tests/test_aashto_col_torsion1.py` covers:

- SI-safe AASHTO torsion helper behavior.
- AASHTO dataframe routing not using ACI labels/methods.
- Open ties staying REVIEW.
- Active prestress staying REVIEW.
- Decision view text no longer calling AASHTO torsion not implemented.

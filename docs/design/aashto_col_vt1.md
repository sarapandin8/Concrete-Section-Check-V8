# AASHTO.COL.VT1 — Column/Pier Combined Shear + Torsion Route

## Purpose

Add a scoped AASHTO LRFD 9th Section 5.7.3.6 combined shear + torsion route for the Column / Pier / Wall / Pylon workflow.

The route is intentionally limited to nonprestressed B-region review using the already validated AASHTO source gates:

- `AASHTO.COL.SHEAR1` for simplified Section 5.7 shear source terms.
- `AASHTO.COL.TORSION1` for Section 5.7.3.6 torsion source terms.
- `AASHTO.COL.SEISMIC5` remains a separate seismic transverse-detailing advisor and does not certify V+T.

## Engineering basis

AASHTO LRFD Section 5.7.3.6 requires combined V+T sections to provide transverse reinforcement not less than the sum of reinforcement required for shear and for concurrent torsion. The implemented scoped route therefore checks:

```text
Provided transverse source = Av/s + 2At/s
Required transverse source = shear demand reinforcement + concurrent torsion demand reinforcement
Governing transverse requirement = max(combined transverse demand, minimum transverse Av/s gate)
```

This matches the app's established control-section source model:

- `Av/s` is read from the active Column/Pier transverse reinforcement row using the effective shear legs.
- `At/s` is read as one closed-tie/hoop torsion leg per spacing for solid members.
- Ordinary longitudinal rebar is used for the `Al` review.
- Prestress strands, tendons, and PT bars are not counted as `Al` in this scoped nonprestressed route.

## Unit policy

The route keeps all solver values in SI:

- forces in N or kN,
- moments in N-mm or kN-m,
- stresses in MPa,
- dimensions in mm,
- reinforcement ratios in mm²/mm.

The AASHTO source shear and torsion helpers already perform the needed ksi/in to SI conversions for AASHTO coefficients; this V+T route consumes their SI-safe results.

## Implemented behavior

When Project Design Code is `AASHTO LRFD` and the active workflow is Column / Pier / Wall / Pylon:

- Shear + Torsion tab now issues AASHTO scoped rows instead of `not implemented`.
- Each active `Tu` row is checked with both `Vux` and `Vuy` directions.
- If `Tu` is below the torsion investigation threshold, the row delegates to the source shear gate.
- If `Tu` requires torsion design, the row checks:
  - source shear strength D/C,
  - source torsion strength D/C,
  - combined transverse D/C,
  - ordinary longitudinal `Al` review.
- Decision view route/scope wording now identifies AASHTO LRFD 5.7.3.6 scoped V+T rather than saying AASHTO V+T is not implemented.

## Guarded scope

The following remain review items:

- prestressed/general-procedure V+T,
- beta/theta iteration beyond the simplified source-route values,
- multi-cell hollow torsion validation,
- seismic overstrength V/T demand generation,
- second-order/slenderness effects,
- hook anchorage, lap splice, development length, and shop-drawing certification,
- wall-type pier and hollow-pier special detailing provisions.

## Files changed

- `concrete_pmm_pro/code_checks/aashto_lrfd.py`
- `concrete_pmm_pro/code_checks/__init__.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_aashto_col_vt1.py`
- `tests/test_design_code_source_of_truth.py`
- `tests/test_aashto_col_pmm_qa1.py`

## Regression coverage

The milestone adds regression tests for:

- SI-safe AASHTO combined V+T helper behavior.
- AASHTO route separation from stale ACI widget state.
- Decision view wording no longer saying AASHTO V+T is not implemented.
- Below-threshold torsion rows delegating to the shear source gate.

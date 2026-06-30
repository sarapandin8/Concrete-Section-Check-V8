# AASHTO.COL.SHEAR1 — Column/Pier simplified shear route

## Scope

This milestone adds an AASHTO LRFD 9th Edition Section 5.7 simplified sectional shear route for the `Column / Pier / Wall / Pylon — RC / Prestressed Member` workflow when the Project Design Code is `AASHTO LRFD`.

Implemented scope:

- Column/Pier case-based ULS shear rows from `Loads -> Column/Pier ULS` using active `Vux` and `Vuy` demands.
- Active transverse reinforcement source from `Sections -> Rebar -> Transverse Rebar`.
- Conservative region selection: because current Column/Pier ULS cases do not own a station/height coordinate, the active transverse region with the lowest `Av/s` is used.
- AASHTO Section 5.7 simplified shear parameters for nonprestressed B-regions:
  - `beta = 2.0`
  - `theta = 45 deg`
- Nominal shear check:
  - `Vn = min(Vc + Vs + Vp, 0.25 fc bv dv + Vp)`
  - current Column/Pier route uses `Vp = 0` until prestressed/general-procedure shear is validated.
- AASHTO minimum transverse reinforcement gate.
- AASHTO maximum transverse spacing gate.
- SI-safe treatment of AASHTO `sqrt(fc)` coefficients.

## Unit policy

AASHTO LRFD Section 5 is written in kips, inches, and ksi. Concrete Section Pro stores solver values in `mm`, `MPa`, `N`, and `N-mm`. Therefore, all AASHTO expressions of the form:

```text
C * sqrt(fc')
```

are evaluated through `aashto_sqrt_fc_stress_mpa(...)`, which converts `fc_MPa -> fc_ksi`, evaluates the expression in ksi, and converts the resulting stress back to MPa before multiplying by SI areas.

Do not substitute `MPa` directly into AASHTO ksi-based square-root expressions.

## Guarded items

The route intentionally leaves the following in REVIEW / future milestones:

- prestressed/general procedure shear with `epsilon_s`, `beta`, and `theta` from Article 5.7.3.4.2 or Appendix B5;
- inclined tendon shear component `Vp` and vertical prestress effects;
- axial tension cases;
- seismic column special shear and confinement requirements;
- torsion and combined shear + torsion;
- direction-specific station/height ownership of transverse reinforcement zones;
- development length, tie anchorage, hooks, lap splices, and shop-drawing detailing.

## Files changed

- `concrete_pmm_pro/code_checks/aashto_lrfd.py`
- `concrete_pmm_pro/code_checks/__init__.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `concrete_pmm_pro/core/design_code.py`
- `tests/test_aashto_col_shear1.py`
- `tests/test_aashto_col_pmm_qa1.py`
- `tests/test_design_code_source_of_truth.py`

## Acceptance tests

Targeted relevant suite:

```text
tests/test_aashto_col_shear1.py
tests/test_aashto_col_pmm_qa1.py
tests/test_design_code_source_of_truth.py
tests/test_aashto_col_pmm1_solver.py
tests/test_aashto_col_pmm1_code_sync.py
tests/test_aashto_col_pmm_basis1_units.py
tests/test_aashto_col_pmm_trace1.py
tests/test_design_code_sync3_setup_widget.py
tests/test_pmm_final_audit.py
```

Expected result at milestone closeout: `51 passed` plus `py_compile / compileall` clean.

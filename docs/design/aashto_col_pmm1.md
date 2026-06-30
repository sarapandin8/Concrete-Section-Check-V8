# AASHTO.COL.PMM1 — AASHTO LRFD 9th Column/Pier PMM route

## Scope

This milestone adds an AASHTO LRFD 9th Edition PMM route for the **Column / Pier / Wall / Pylon — RC / Prestressed Member** workflow when Project Design Code is **AASHTO LRFD**.

Implemented scope:

- Column/Pier/Wall/Pylon axial-flexure PMM surface for B-regions.
- Ordinary reinforcing steel and bonded prestressing steel in the same strain-compatible section sweep.
- SI internal units: mm, MPa, N, N-mm.
- AASHTO stress-block coefficients evaluated from concrete strength in ksi and then applied to SI stresses.
- AASHTO LRFD Section 5 strength strain classification and phi transition for nonprestressed and bonded prestressed sections.
- AASHTO-style maximum factored axial resistance cap for compression display/checking.

Guarded / not included in PMM1:

- Shear, torsion, and combined shear + torsion AASHTO solvers.
- Slenderness / second-order moment magnification.
- Seismic special provisions and extreme-event plastic-hinge provisions.
- Hollow rectangular wall local buckling strain adjustment and phi_w reduction.
- Development length, splices, confinement detailing, and transverse reinforcement design.
- Unbonded tendon global displacement compatibility.

## AASHTO basis used

The implementation maps the following Section 5 topics into code:

| Topic | Implemented location |
|---|---|
| Concrete ultimate strain for strength | `AASHTO_ECU_STRENGTH = 0.003` |
| Rectangular stress block alpha1/beta1 | `code_checks/aashto_lrfd.py` |
| Net tensile strain compression/tension limits | `aashto_compression_controlled_strain_limit`, `aashto_tension_controlled_strain_limit` |
| phi transition for nonprestressed RC | `aashto_phi_and_strain_condition(... prestressed_member=False)` |
| phi transition for bonded prestressed concrete | `aashto_phi_and_strain_condition(... prestressed_member=True)` |
| Nominal PMM surface | shared strain-compatibility engine in `analysis/pmm_solver.py` |
| Maximum axial resistance cap | `aashto_nominal_po_rc_prestressed` + `aashto_max_phiPn` |

## Unit policy

AASHTO LRFD Section 5 uses kips, inches, and ksi. Concrete Section Pro keeps solver internals in SI units. PMM1 therefore uses this rule:

```text
Do not substitute MPa directly into an equation or breakpoint written in ksi.
```

Examples:

- alpha1 uses the 10 ksi breakpoint, so `fc_MPa` is converted to `fc_ksi` first.
- beta1 uses the 4 ksi breakpoint, so `fc_MPa` is converted to `fc_ksi` first.
- reinforcement yield-strength breakpoints for strain limits use ksi, so `fy_MPa` is converted to `fy_ksi` first.
- force and moment results remain N and N-mm internally, then display as kN and kN-m.

## Solver routing

`run_pmm_solver(analysis_input)` now routes by `analysis_input.settings.code`:

```text
ACI 318      -> run_rc_pmm_solver(...)
AASHTO LRFD  -> run_aashto_lrfd_column_pmm_solver(...)
```

The Analysis page now calls `run_pmm_solver` for Column/Pier PMM and RC-only comparison, so selecting AASHTO in Setup activates the AASHTO PMM route rather than the old ACI-oriented route.

## QA acceptance

Tests added:

- `tests/test_aashto_col_pmm1_solver.py`

Checks covered:

- alpha1/beta1 use ksi breakpoints from SI inputs.
- AASHTO strain-limit helpers match 60/75/100 ksi transition basis.
- AASHTO nonprestressed phi reaches 0.90; bonded prestressed phi reaches 1.00.
- `run_pmm_solver` routes AASHTO code to the AASHTO engine and ACI code to the ACI engine.
- AASHTO bonded prestress PMM uses prestressed phi and keeps axial cap metadata.
- AASHTO and ACI routes are not numerically identical for high-strength concrete.

## Engineering caution

PMM1 is intended to stop the dangerous state where the UI says AASHTO LRFD but the internal PMM engine is still ACI-oriented. It does not complete all AASHTO Column/Pier design checks. PMM results should be used with the remaining guarded checks listed above.

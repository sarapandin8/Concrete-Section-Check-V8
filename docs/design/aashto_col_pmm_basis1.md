# AASHTO.COL.PMM.BASIS1 — Column / Pier / Wall / Pylon PMM basis mapping

## Purpose

This milestone prepares the AASHTO LRFD 9th Edition axial-flexure PMM route for
Column / Pier / Wall / Pylon workflows before implementing the final solver.
It is intentionally a basis/traceability milestone, not a completed PMM engine.

The immediate risk being controlled is **showing AASHTO LRFD in the UI while
still using ACI-oriented PMM logic internally**.  The second major risk is
**using AASHTO imperial coefficients directly with SI input values**.

## Source sections to map first

The uploaded AASHTO LRFD Section 5 table of contents identifies the governing
implementation areas for PMM:

| Topic | Section 5 article group | Solver impact |
|---|---:|---|
| Material properties | 5.4 | Concrete, reinforcing steel, prestressing steel inputs |
| Strength limit state and resistance factors | 5.5.4 | `phi` layer for factored resistance |
| Flexural and axial force effects — B-regions | 5.6 | Main PMM route |
| Strength / extreme-event assumptions | 5.6.2 | Plane-section strain compatibility and concrete stress distribution |
| Prestressing steel stress at nominal flexural resistance | 5.6.3.1 | Bonded/unbonded tendon treatment |
| Flexural resistance and strain-compatibility approach | 5.6.3.2 | Nominal section force integration and moment resistance |
| Compression members | 5.6.4 | Column/pier axial-flexure, reinforcement limits, slenderness, biaxial flexure |
| Reinforcement details for compression members | 5.10 | Detailing/QA guards, not the first numerical PMM kernel |
| Shear and torsion | 5.7 | Future AASHTO.COL.SHEAR1 / TORSION1 / VT1, not PMM1 |

## Solver-unit policy

Concrete Section Pro solver internals remain SI:

- Length: mm
- Stress: MPa = N/mm²
- Force: N or kN for display
- Moment: N-mm internally, kN-m for display
- Area: mm²

AASHTO LRFD Section 5 is written in kips, inches, and ksi.  Therefore all
imperial equations must be evaluated through a conversion layer or through a
clearly documented SI coefficient derivation.

### Mandatory unit guard

Do **not** substitute MPa directly into AASHTO expressions written for ksi.
For expressions of the form:

```text
C * sqrt(f'c)
```

where `f'c` is specified in ksi and the resulting stress is in ksi, the app
must do this:

```text
fc_ksi = fc_MPa / 6.894757293168361
stress_ksi = C * sqrt(fc_ksi)
stress_MPa = stress_ksi * 6.894757293168361
```

The helper `concrete_pmm_pro.core.aashto_units.aashto_sqrt_fc_stress_mpa()` is
added for this purpose.

## Intended implementation route for AASHTO.COL.PMM1

1. Keep the existing geometry and strain-compatibility discretization, because
   the general PMM calculation already works in SI.
2. Add an AASHTO-specific code-basis layer for:
   - concrete compression block assumptions,
   - maximum usable concrete strain,
   - beta / rectangular block parameters,
   - steel stress limits,
   - prestressing steel treatment,
   - resistance factor `phi`, and
   - factored resistance output.
3. Do not reuse ACI phi functions in the AASHTO route.
4. Do not let AASHTO analysis cards display completed capacity if the solver
   route falls back to ACI logic.
5. Keep shear, torsion, and shear+torsion guarded until their own AASHTO
   milestones are implemented.

## Prestress scope for PMM1

PMM1 should include:

- ordinary rebar only when prestress is not selected;
- bonded prestressing steel through section strain compatibility;
- unbonded tendon handling only when the AASHTO basis is explicitly mapped.
  Until then, unbonded tendon strength should be guarded or conservatively
  limited rather than silently treated as bonded.

## Verification strategy

AASHTO.COL.PMM1 should not be merged as a final solver until it has:

- route tests proving AASHTO does not call ACI phi helpers;
- unit tests for ksi/MPa, kip/N, in/mm, and moment conversion;
- a simple rectangular RC column benchmark;
- a prestressed section benchmark;
- biaxial PMM route test for at least two bending-axis angles;
- report/QA traceability showing AASHTO LRFD 9th Edition, not ACI 318.

## Current BASIS1 deliverables

- Adds `concrete_pmm_pro/core/aashto_units.py` for audited conversion helpers.
- Adds regression tests for critical imperial-to-SI conversions and sqrt(f'c)
  coefficient handling.
- Adds this design note as the implementation checklist for AASHTO.COL.PMM1.

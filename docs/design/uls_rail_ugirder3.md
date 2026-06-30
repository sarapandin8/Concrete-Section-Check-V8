# ULS.RAIL.UGIRDER3 — Railway U-Girder PSC Shear Route Evidence

## Purpose

Add guarded Railway U-Girder PSC shear route evidence to the existing ULS framework. This milestone is an engineering-review route, not final code-certified design.

## Implemented scope

- Read active ULS `Vuy` station-resultant rows from the Loads table.
- Read active Beam/Girder provided-stirrup zones from Sections → Rebar.
- Estimate Railway U-Girder total web width `bv` from the section side-wall material intercept.
- Estimate effective shear depth `d` and `dv` from the active section and station reinforcement/debonding handoff, with a manual d/dv override path when present.
- Compute a guarded AASHTO LRFD-compatible sectional shear route:
  - `Vc = 0.083 β sqrt(f'c) bv dv`
  - `β = 2.0`
  - `θ = 45°`
  - `Vs = Av/s fy dv cotθ`
  - `φ = 0.90`
  - `Vn ≤ 0.25 f'c bv dv`
- Check provided stirrup minimum `Av/s` and maximum spacing gate.
- Add report-table and Word-report evidence.

## Guardrails

This milestone does not claim final code-certified shear design. The report wording is limited to Engineering Review PASS / FAIL for shear route evidence only.

Final certification is still blocked by:

- refined PSC shear `Vci / Vcw / Vp`,
- critical-section/end-region validation,
- development length and debonded strand anchorage,
- anchorage/end-zone bursting and spalling,
- independent benchmark validation,
- Engineer-of-Record review.

## Changed areas

- `concrete_pmm_pro/analysis/railway_u_girder_uls.py`
- `concrete_pmm_pro/reporting/__init__.py`
- `concrete_pmm_pro/reporting/report_tables.py`
- `concrete_pmm_pro/reporting/word_export.py`
- `tests/test_uls_railway_u_girder3.py`

## Explicit non-scope

No SLS solver equations, PMM solver equations, flexure equations, prestress/debond participation logic, geometry generator, torsion equation, V+T equation, load-combination equation, or project schema were modified.

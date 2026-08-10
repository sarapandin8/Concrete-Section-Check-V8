# CROSSBEAM.ANALYSIS4C7D12 — CIP ULS visual semantics closeout

## Scope
Close the Cast-in-Place Crossbeam ULS visual/traceability issues identified during D11 visual QA without changing ACI equations, capacities, demand routing, or construction-mode ownership.

## Changes
- Flexure summary now distinguishes imported source rows from retained calculation rows before adding Column Face and auxiliary checks, preventing misleading arithmetic in the Total Check Rows card.
- CIP Shear scope/limitations now state that physical segment-joint transfer is NOT APPLICABLE for monolithic Cast-in-Place Zones; Precast keeps its separate physical-joint REVIEW semantics.
- CIP Torsion scope/limitations no longer require physical-joint transfer completion; Cast-in-Place Zone boundaries are explicitly monolithic property boundaries.
- CIP Combined V+T scope, source summary, failure caption, and review caption no longer claim one-sided physical-joint audit evidence applies when the active workflow is Cast-in-Place.
- Precast Segmental wording and audit-only physical-joint behavior are preserved.

## Verification
- Python compile: PASS for app.py, Flexure/Shear/Torsion/Combined analysis modules, and analysis_page.py.
- D12/D11/D10/D9/D7 closeout regressions: 17 passed.
- Shear + Torsion core regressions: 34 passed.
- Flexure + Combined solver/adoption regressions: 14 passed.
- Total targeted tests executed: 65 passed.

## Engineering impact
Presentation/source-traceability cleanup only. No ACI strength equation, resistance value, demand value, prestress handling rule, rebar-credit rule, or station-routing equation was changed.

# CROSSBEAM.ULS1A1 — Mu versus φMn Flexure Chart

## Scope

This milestone changes only the Portal Frame Crossbeam ULS Flexure result figure. The accepted ACI 318-19 P–M3 solver, row-coupled demand contract, status logic, station mapping, Project JSON behavior, SLS workflows, and all non-Crossbeam workflows remain unchanged.

## Result figure

The main full-length Flexure figure now follows the accepted Bridge Beam/Girder chart language:

- `Mu` is the signed imported `M3` demand.
- `φMn` is the available uniaxial M3 capacity evaluated at the concurrent imported `Pu` from the same ULS row.
- Capacity is plotted with the demand sign so positive and negative bending directions are visually comparable.
- The governing capacity point is marked `Gov. flexure` and labelled with the governing P–M3 D/C.
- Column footprints, Column centerlines, and physical segment joints remain visible.
- P–M3 D/C remains available in the decision cards, compact table, hover data, and calculation audit.

At an exact zero-Mu station, the chart plots `φMn = 0` because no positive or negative bending direction is defined. Any axial-only `P/φPn` utilization remains visible in the result cards and audit and must not be inferred from the overlapping zero-moment traces.

## Exclusions

This milestone does not change:

- ACI strain-compatibility capacity calculations
- prestress credit or effective-prestress handoff rules
- ordinary rebar credit at Precast physical segment joints
- ULS Shear, Torsion, or Shear + Torsion
- Result Summary or Report / QA
- Project JSON schema or analysis-result persistence

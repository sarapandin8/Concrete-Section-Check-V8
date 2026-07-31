# CROSSBEAM.SLS1B — At Service Concrete Stress and Segment-Joint Compression

## Scope

This milestone connects the accepted compact Crossbeam SLS workspace to a Crossbeam-owned ACI 318-19 final-service concrete stress solver.

- consumes validated `SLS At Service` station rows from the Crossbeam Analysis foundation;
- uses imported row-coupled `P` and `M3` directly from external FEA;
- maps every row to its active Section ID, gross section properties, and concrete material;
- calculates top- and bottom-fiber stress with elastic theory;
- evaluates ACI 318-19 Class U service tension and service compression limits;
- distinguishes engineer-identified prestress-plus-sustained cases from total-service cases;
- evaluates the project-specific physical segment-joint compression gate for every service case;
- displays one compact full-length engineering chart using the accepted Beam/Girder chart language;
- labels the dashed stress-limit traces with equations, substituted concrete strength, and MPa values;
- preserves the engineer-selected sustained service case names in Project JSON;
- keeps calculated Analysis results session-only.

## Sign convention and equations

Result charts use:

- compression negative;
- tension positive;
- imported `P` compression positive;
- imported `M3` sagging positive.

For each mapped section:

```text
f_axial  = -P / A
f_top    = f_axial - M3 / Ztop
f_bottom = f_axial + M3 / Zbottom
```

External FEA is the sole demand source. Effective prestress, primary prestress response, and secondary prestress response are not added again by this solver.

## ACI 318-19 final-service basis

The first production service route adopts conservative Class U behavior:

```text
Class U tension criterion:
ft <= 0.62 sqrt(f'c)
```

Compression limits follow ACI 318-19 Table 24.5.4.1:

```text
Prestress + sustained load: compression magnitude <= 0.45 f'c
Prestress + total load:     compression magnitude <= 0.60 f'c
```

The engineer identifies sustained service cases in the collapsed `Service stress basis` control. Unselected imported service cases are treated as total-load cases.

A non-failing result remains `REVIEW` if either sustained or total service compression coverage is absent. This prevents the app from issuing a false complete ACI service PASS from only one load condition.

## Precast Segmental joint gate

For every imported At Service case at every physical segment joint:

```text
s- top and bottom compression >= 0.70 MPa
s+ top and bottom compression >= 0.70 MPa
```

Missing one-sided joint rows produce `INCOMPLETE`. Compression below 0.70 MPa or any joint-face tension produces `FAIL`.

For Cast-in-Place construction, Section/Analysis zone boundaries are not physical joints and the joint gate is `NOT REQUIRED`.

## Chart standard

The full-length At Service chart shows:

- top total stress;
- bottom total stress;
- the case-appropriate compression limit;
- the Class U tension limit;
- governing compression and tension markers;
- actual Column footprints and centerlines;
- physical segment-joint markers;
- equation/substitution labels on both dashed limit traces.

Lines connect imported stations only for visualization. No compliance is inferred between unverified stations.

## Project persistence

Project JSON now preserves:

```text
crossbeam input metadata / sls_service_sustained_cases
```

This is an engineering input and is restored when an older saved project is reopened. Calculated SLS1B result caches are intentionally not persisted.

## Conservative guards and limitations

- Class U tension screening is applied conservatively to any extreme fiber in tension because the compact external-FEA handoff does not separately identify the precompressed tension zone.
- Class T/Class C cracked-section, crack-control, and deflection checks are not included in SLS1B.
- Gross Section ID properties are used. Active Internal Tendon duct voids require adopted net-section properties before final PASS.
- Anchorage zones, beam-column joints, D-regions, shear, torsion, and seismic detailing remain separate checks.
- Result Summary and Report / QA are not connected in this milestone.

## Files changed

- `concrete_pmm_pro/crossbeam/sls_service.py`
- `concrete_pmm_pro/crossbeam/analysis_charts.py`
- `concrete_pmm_pro/ui/crossbeam_analysis_page.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `concrete_pmm_pro/io/project_io.py`
- `tests/test_crossbeam_sls1b_service_stress.py`
- `tests/test_crossbeam_sls1a_transfer_stress.py`
- `tests/test_crossbeam_analysis_ui1_compact_workspace.py`
- `tests/test_crossbeam_analysis1a_navigation_status_chart_qa.py`
- `README_CROSSBEAM_SLS1B.md`

## Repo summary

`Add ACI 318-19 Crossbeam final-service Class U stress checks with sustained/total compression routing, full-length equation-labeled charts, and persisted segment-joint QA inputs.`

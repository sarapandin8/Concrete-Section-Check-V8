# CROSSBEAM.SLS1A — At Transfer Concrete Stress

## Scope

This milestone connects the accepted compact Crossbeam SLS workspace to a Crossbeam-owned ACI 318-19 transfer-stage concrete stress solver.

- consumes validated `SLS At Transfer` station rows from the Crossbeam Analysis foundation;
- uses imported row-coupled `P` and `M3` directly from external FEA;
- maps every row to its active Section ID, gross section properties, and concrete material;
- calculates top- and bottom-fiber stress with elastic theory;
- evaluates ACI 318-19 transfer-stage concrete stress limits;
- evaluates the project-specific physical segment-joint compression gate;
- displays one compact full-length engineering result chart using the accepted Beam/Girder chart language;
- adds actual Column footprints/centerlines and physical segment-joint markers without cluttering the main chart;
- keeps detailed station calculations and source mapping inside collapsed audit expanders.

## Sign convention and equations

Result charts use:

- compression negative;
- tension positive;
- imported `P` compression positive;
- imported `M3` sagging positive.

For each mapped section:

```text
f_axial = -P / A
f_top   = f_axial - M3 / Ztop
f_bottom= f_axial + M3 / Zbottom
```

Internal calculations use N, mm, N-mm, and MPa.

## ACI 318-19 transfer limits

The Portal Frame Crossbeam is not treated as a simply supported member. The solver therefore uses the `all other locations` limits from ACI 318-19 Tables 24.5.3.1 and 24.5.3.2:

```text
Compression magnitude <= 0.60 f'ci
Tension              <= 0.25 sqrt(f'ci) MPa
```

No credit is taken for additional bonded reinforcement under ACI 318-19 24.5.3.2.1 in this milestone.

## Precast Segmental joint gate

For every imported Transfer case at every physical segment joint:

```text
s- top and bottom compression >= 0.70 MPa
s+ top and bottom compression >= 0.70 MPa
```

Missing one-sided joint rows produce `INCOMPLETE`, not a false PASS. An actual stress or joint-compression exceedance produces `FAIL`.

For Cast-in-Place construction, Section/Analysis zone boundaries are not physical joints and the joint gate is `NOT REQUIRED`.

## Result lifecycle

- The calculated SLS1A result is session-only and is invalidated by an input fingerprint when relevant inputs change.
- Project JSON input persistence remains unchanged and continues to preserve Section, material, Loads, construction-type, and confirmation inputs.
- Analysis result caches are intentionally not added to Project JSON.

## Internal-tendon duct-void guard

ACI 318R-19 R24.5.2.1 states that section-property calculations should account for voids created by sheathing or ducts for unbonded prestressing. At transfer, the current Crossbeam Section Library does not yet contain adopted internal-duct geometry. Therefore:

- active Internal Tendons + non-failing gross-section stress result → `REVIEW`, not `PASS`;
- active External Tendons only + complete/non-failing checks may produce `PASS`;
- an actual ACI stress exceedance or joint-compression failure remains `FAIL`.

This guard prevents the gross-section preview from being over-certified while retaining the compact result graph and station audit.

## Explicit limitations

- Gross Section ID properties are used; a separate net-section deduction for ungrouted tendon ducts is not included in SLS1A.
- Lines connect imported stations for visualization only; compliance is not inferred between unverified stations.
- Anchorage zones, beam-column joints, D-regions, shear, torsion, seismic detailing, and At Service stress remain separate milestones.
- Result Summary and Report / QA are not connected in this milestone.

## Files changed

- `concrete_pmm_pro/crossbeam/sls_transfer.py`
- `concrete_pmm_pro/crossbeam/analysis_charts.py`
- `concrete_pmm_pro/ui/crossbeam_analysis_page.py`
- `tests/test_crossbeam_sls1a_transfer_stress.py`
- `tests/test_crossbeam_analysis_ui1_compact_workspace.py`
- `README_CROSSBEAM_SLS1A.md`

## Repo summary

`Add ACI 318-19 Crossbeam transfer-stage top/bottom stress checks with compact full-length charts, Column landmarks, and strict one-sided segment-joint compression QA.`

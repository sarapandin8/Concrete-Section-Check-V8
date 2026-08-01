# CROSSBEAM.ULS1A — ACI 318-19 P–M3 Interaction Strength

## Scope

This milestone connects the **Flexure** action in the Portal Frame Crossbeam ULS workspace. It checks every validated `ULS Final Stage` station/case using the simultaneous row-coupled axial force `P` and bending moment `M3` imported from the external FEA model.

- Design code: **ACI 318-19**
- Demand signs: `P` compression positive; `M3` sagging positive
- Capacity method: strain-compatible, phi-reduced uniaxial `P–M3` interaction
- Pass limit: `D/C <= 1.00`
- Main result: full-length `P–M3 interaction D/C` chart with Columns and physical segment joints
- Result storage: session-only, protected by an input fingerprint and `STALE` detection

## Capacity assembly

At each mapped station the solver uses:

1. the adopted Crossbeam Section ID and concrete material;
2. the adopted longitudinal-rebar template and generated bar-center layout;
3. bonded internal tendon groups at their interpolated profile coordinates when an Engineer-adopted effective-prestress handoff is ready; and
4. the exact `P` and `M3` values from one imported ULS row, without adding prestress or secondary prestress to demand again.

The dedicated Crossbeam check extracts the exact uniaxial M3 slices from the shared ACI strain-compatibility PMM sweep instead of routing through a generic biaxial directional-envelope fallback.

## Precast segment joints

For `Precast Segmental`, ordinary longitudinal reinforcement is not credited across a physical segment joint. Adjacent Section contexts are evaluated internally and the largest D/C is reported as one governing result at the joint; values are not averaged.

## Guarded status

A numerical exceedance is `FAIL`. A non-failing result remains `REVIEW` when the adopted strength source is incomplete or approximate, including:

- external or permanently unbonded tendons not included in bonded section strain compatibility;
- missing adopted effective-prestress source;
- system-average rather than tendon/station-specific effective stress; or
- duct/sheathing area `Apd` not represented in the axial compression cap.

The result is a B-region sectional check only. Beam-column joints, anchorage zones, deviators, concentrated-load regions, abrupt transitions, development/anchorage, global second-order effects, seismic detailing, shear, and torsion remain separate checks.

## Files

- `concrete_pmm_pro/crossbeam/uls_flexure.py`
- `concrete_pmm_pro/crossbeam/analysis_charts.py`
- `concrete_pmm_pro/ui/crossbeam_analysis_page.py`
- `tests/test_crossbeam_uls1a_flexure_pm3.py`
- `tests/test_crossbeam_analysis_ui1_compact_workspace.py`

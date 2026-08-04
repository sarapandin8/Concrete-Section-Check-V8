# CROSSBEAM.ANALYSIS4C5 — Combined V+T Check Guidance and Trace Continuity

## Scope

This milestone starts from the accepted `CROSSBEAM.ANALYSIS4C4` package and improves only the Portal Frame Prestressed Crossbeam **Shear + Torsion** review presentation. It does not modify the accepted Shear, Torsion, Combined V+T, Direct P–M3, prestress, reinforcement-source, or Project JSON calculations.

## User-facing objective

Every selected Combined V+T review now explains:

1. what the selected check verifies,
2. how to read its D/C result,
3. what the selected view does not certify.

The explanatory panel remains visible above the decision cards and chart so the user does not need to open a QA expander to understand the engineering meaning.

## Review names

The four separate review meanings remain intentionally separate:

- `Section-size interaction`
- `Transverse reinforcement`
- `Longitudinal reinforcement`
- `Joint review`

`Section-size stress` was renamed to `Section-size interaction` to avoid confusion with SLS concrete stress checks.

## Trace-continuity policy

The charts now connect every evaluated station result that can be connected without inventing a structural result.

### Section-size interaction

- Connects imported, Column Face, and ACI `h/2` evaluated results in station order.
- Keeps distinct marker shapes for generated Column Face and `h/2` checks.
- Breaks the trace across physical Segment joints and excluded Column/support footprints.
- The connecting line is visual interpolation between evaluated checks, not a continuous FEA solution.

### Transverse reinforcement

- Connects imported, Column Face, and ACI `h/2` evaluated results in station order.
- Continues through regions below the torsion threshold because the torsion `At` demand becomes zero while the concurrent shear contribution remains eligible.
- Counts additional cage legs once and never duplicates shared cage legs.
- Breaks the trace across physical joints and excluded support interiors.

### Longitudinal reinforcement

- Retains the Segment-owned step trace only where torsion reinforcement design applies.
- Does not create an artificial D/C = 0 where `Tu < phiTth`.
- Adds pale `Aℓ N/A — below torsion threshold` bands to show full member coverage without inventing a numerical utilization.
- Keeps physical joints as trace breaks.

### Joint review

- Remains a member map and one-sided evidence table.
- No artificial physical-joint D/C is generated.

## Files changed

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis4c4_component_views.py`
- `tests/test_crossbeam_analysis4c5_guidance_trace_continuity.py`
- `README_CROSSBEAM_ANALYSIS4C5.md`

## Solver protection

The following calculation sources are unchanged from ANALYSIS4C4:

- `concrete_pmm_pro/analysis/crossbeam_uls_shear.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_torsion.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py`
- `concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py`
- `concrete_pmm_pro/analysis/crossbeam_uls.py`
- `concrete_pmm_pro/io/project_io.py`
- `app.py`

## QA completed

- Python compileall: PASS
- ANALYSIS4C5 guidance and trace-continuity tests: PASS
- ANALYSIS4C4 component-view regression: PASS
- ANALYSIS4C3 decision/visual regression: PASS
- Crossbeam Shear, Torsion, physical-joint plotting, and compact Loads/Shear tests: PASS
- ANALYSIS4C1/4C1A source-contract and As/Aℓ tests: PASS
- ANALYSIS4C2 solver-adoption regression: PASS
- Crossbeam navigation regression: PASS
- Shared Beam/Girder V+T chart tests: PASS

A pre-existing `test_results_ws2_beam_uls_dashboard.py` source-string assertion remains failing in the ANALYSIS4C4 baseline and is not caused by this milestone. No full-repository green claim is made.

## Repo summary

Add visible engineering explanations to every Crossbeam combined V+T review and connect evaluated Section-size and transverse D/C points while preserving physical-joint, support-footprint, and below-threshold semantics.

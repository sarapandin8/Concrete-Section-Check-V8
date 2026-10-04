# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.FLEXDEP1

Date: 2026-10-04. Active design basis: **AASHTO LRFD Bridge Design Specifications, 9th Edition (2020)**.

## Baseline and authorization

Continue `concrete-section-pro_IGIRDER-PERF4-equivalent-fast-flexure.zip`, SHA-256 `3b13e2f68b6a64c0ce7f377e9af9f84d46c048502f197f1a94106d9007413fe7`. This preserves the ULS6F → ULS7 → DBQA1/PERF3 → PERF4 lineage. No baseline file is removed.

The user expressly requested correcting φMn to the project's current code and explaining end development. The original ULS6F handoff's deferred development work is therefore authorized for this milestone. Do not switch the project to ACI 318-14/19 or a newer AASHTO edition because the user's Concise Beam screenshot uses another code.

The unchanged supplied `I_Girder_20m.json` has 44,911 bytes and SHA-256 `c27a27278fef69b5347e7216f5b3c9324f723a9a0ca2d5b52a8956c1fe765799`. It contains a 300 mm effective deck; the previously supplied Final results PDF shows 250 mm. The published numerical verification uses the original 300 mm JSON and must not be described as reproducing the 250 mm PDF.

## Concrete problem and resulting behavior

The prior dedicated layout filtered out sleeved strands but granted full section strength to the remaining 19 bonded strands at the end and immediate full credit to each debonded family after its sleeve. It did not enforce the gradual end force development required by 5.9.4.3.1–3. Construction also called the shared ACI stress-block path, and Bridge flexure used fixed φ=1.0.

The active Construction and Final Composite Calculate buttons now use a dedicated fixed-axis I-Girder section equilibrium solver. It limits the force of each strand family by its available bond distance, recalculates concrete/ordinary-steel equilibrium, and uses the AASHTO net-strain resistance factor. It retains every original external station Nu and never sets Nu=0 for performance or closes the resistance diagram at a support just because demand is zero.

## Normative basis and implementation

Primary source: supplied `03-SECTION-5-CONCRETE-STRUCTURES.pdf`, printed pages 5-143–5-145 (5.9.4.3), Article 5.5.4.2, 5.6.2.1/5.6.3.2.5–6/5.6.3.3, and 5-180–5-182 (5.10.8.2.1).

- Transfer length: lt=60db under 5.9.4.3.1; a 12.7 mm strand gives 762 mm.
- Full development: ld=κ(fps−2fpe/3)db in ksi/in. Exact SI: ld_mm=κ[(fps_MPa−2fpe_MPa/3)/6.894757293168]db_mm.
- Bonded κ=1.0 for member depth≤24 in (609.6 mm), 1.6 above 24 in. The depth is the original precast depth, not composite depth.
- Under 5.9.4.3.3F, partially debonded strands require κ=2.0 when service tension exists in the precompressed tensile zone. Unknown service classification conservatively uses 2.0. The lower depth branch requires an explicit no-service-tension declaration.
- Available bonded distance is the shorter distance to the family's left/right bond starts. Sleeve lengths are measured from physical cut ends; each family's transfer/development starts at its sleeve exit.
- The allowable stress fpx rises linearly from zero to fpe through lt, then to the full-development reference fps through ld. The solver caps each family's actual compatible stress by fpx. Initial effective prestress is reduced through transfer once; Pe is not added as another external Nu.
- Full-development reference fps is calculated for all physical strands at the same original Nu and bending direction using the existing bilinear strand law. A sleeve boundary cannot change another family's development-length reference. The reference curve is audit-only.
- Actual section equilibrium requires φPn(c)=Nu, applying the same φ to axial and moment resistance. Concrete uses AASHTO α1/β1, ecu≤0.003, actual polygon clipping, the current steel laws and ordinary-bar displaced-concrete subtraction. φ uses net geometric tensile strain excluding initial prestress: 0.75 at εt≤0.002, 1.00 for bonded PSC at εt≥0.005, linear transition between them.
- A failed equilibrium has **no valid Mn**. Store capacity as NaN, issue FAIL/NO EQUILIBRIUM, show a red demand marker and a gap in the capacity line. Never plot a fictitious zero capacity for that failure.

Ordinary longitudinal bars remain sourced from the single existing Rebar table. The automatic normal-weight bar route uses 5.10.8.2.1a–c, ld=max(12 in, 1.7×2.4db fy/√f'c) in ksi/in, without confinement/excess reductions to the full-yield reference length. Partial straight-bar force uses the excess-reinforcement provision and retains the 12-in minimum. No bar force is credited below 12 in unless full end anchorage is verified. Using the tension length for compression is conservative. The scope is f'c≤10 ksi, fy≤75 ksi and bars≤No.11; otherwise a verified governing ld is required. Deck layers use actual entered bar diameter and deck f'c, not the smeared equivalent diameter.

Ordinary-bar full-span continuity/cutoffs and end anchorage are explicit declarations. Unconfirmed continuity keeps numeric PASS rows at REVIEW. Missing material names also keep them at REVIEW; existing fallback fy/Es remains visible in the bar trace. In the original JSON, SD40 is named but the rebar-material list is empty, so numerical verification uses the existing 390 MPa / 200,000 MPa fallback. Defining SD40 in Materials resolves the material-source issue; it does not confirm a drawing.

The 5.6.3.3 minimum-flexure gate passes through the 1.33Mu branch when sufficient and is not applicable to compression-controlled sections. Other passing rows remain REVIEW if the cracking-resistance branch is needed; no fabricated Mcr is introduced.

## Production files

| File | Change |
|---|---|
| `concrete_pmm_pro/analysis/igird_flexure_development.py` | New family bond-distance/stress caps, bar-development limits and fixed-axis section equilibrium. |
| `concrete_pmm_pro/ui/igird_flexure_development.py` | New physical-end/development input expander and stored Calculation trace / Equations. |
| `concrete_pmm_pro/ui/analysis_page.py` | Enable new route for both dedicated stages, numeric station ordering, new stage hashes/versions, source/minimum gates and unavailable-equilibrium graph/card handling. |
| `concrete_pmm_pro/io/project_io.py` | Persist settings in existing project metadata and clear old development widget state on project load. |
| `tests/test_igird_flexure_development.py` | Independent hand calculation, code boundaries, supplied-model integration, source gates, version invalidation and graph-failure semantics. |
| `tests/test_igird_uls5_shear_general_procedure.py` | Update the selective-cache fixture to contain a current versioned Final Flexure result; obsolete unversioned flexure now correctly remains stale. |
| `qa/igird_flexdep1_verify.py` | Reproducible supplied-JSON station/strand/bar traces and benchmark. |

The shared PMM engine, Crossbeam, Segmental Box Girder, SLS, Shear/Torsion solvers and interface-shear calculation are not modified. Generic private Flexure preview calls retain their prior route unless the dedicated development flag is supplied; both real I-Girder stage Calculate buttons supply it.

## Settings and state authority

Metadata key: `igird_flexure_development_settings`. Defaults: both physical cut-end extensions=0 m, unknown debonded service condition (κ=2), no ordinary-bar continuity/anchorage confirmations, verified ld=0 (automatic).

The extension means the distance from a physical cut end to the station-axis end/bearing. If x=0 is a bearing with concrete beyond it, enter its actual drawing distance; do not fabricate it. The supplied `I-girder.pdf` is an application section/strand-layout printout and does not establish that longitudinal datum.

Result versions:

- `IGIRDER.FLEXDEP1.aashto-developed-flexure.construction`
- `IGIRDER.FLEXDEP1.aashto-developed-flexure.final-composite`

Version and settings changes invalidate older stage resistance. Construction and Final results remain separate cache owners. Trace rendering reads stored result rows and performs no hidden solve. Original project geometry, strand forces/layout and demand rows remain unchanged. Existing project JSON schema is preserved.

## Verified supplied-model behavior

Default physical cut ends at x=0/20 m; no verified ordinary-bar end anchorage. Numerical values use the source material fallback described above.

| Stage/station | Original Nu (kN) | Available φMn (kN-m) | Interpretation |
|---|---:|---:|---|
| Construction, x=0/20 | 0 | 0 | No developed strand/bar strength and no external compression. |
| Construction, x=10 | 0 | 7,682.527967 | Fully developed plateau; Mu=4,078 kN-m, D/C=0.530815. |
| Final, x=0 | +575.159 | 398.394518 | Strand force=0; compression-only section equilibrium, φ=0.75. |
| Final, x=10 | +25.940 | 10,363.289825 | Fully developed positive composite section; D/C=0.693283. |
| Final, x=20 | −1.492 | Unavailable | Applied axial tension has no resisting developed end steel; NO EQUILIBRIUM/FAIL. |

Final Row 1 reference at x=10: fpe=1115.997974 MPa, fps=1726.718100 MPa; bonded ld=2.896238 m and debonded κ=2 ld=3.620298 m. A 5 m left sleeve places transfer completion at x=5.762 m and full reference development at x≈8.620 m. Other stations use their own Nu/reference fps, so these are explanatory reference positions rather than a forced constant ld for the whole graph.

Construction retains 41 original automatic stations; Final retains all 21 original coupled FEA stations. Numeric sorting is verified. Maximum force residuals are 0.019222 N / 0.017566 N. Every actual strand stress is checked against its cap and fully developed reference. Fully developed test sections recover the reference resistance. Source JSON and project geometry remain unchanged.

Engine timings on the local fixture: Construction 1.895 s, Final 1.941 s. Actual production-page Calculate clicks took approximately 3 s including UI rendering; measured values are stored in `qa/evidence/igird_flexdep1/browser_result.json`. These are local observations, not a deployment guarantee. The speed comes from two scalar section-equilibrium solves and exact-Nu reference reuse rather than a 72×120 angular PMM sweep; Nu is retained.

## Validation and release

Fresh clean extraction: **375 tests passed across 37 selected modules**, with zero failures/errors/skips; compileall and the complete `app.py` Streamlit startup also passed. This selected scope covers I-Girder ULS1–7, DBQA/PERF, prestress/station/loss checks, AASHTO PMM, composite preparation, plots, Result Summary and cache signatures; it is not the entire repository suite. The dedicated engineering module contains 18 tests. Local browser verification exercises both real Calculate buttons and both trace expanders, with zero page/console/Streamlit errors. Measured Calculate click times: Construction 3.372 s, Final 2.977 s. The agent-browser IPC socket was unavailable in this environment; a local Chromium/Playwright fallback completed UI verification.

The final ZIP contains the same Python production/test files as the tested extraction; code-file hashes are compared before final release. The final evidence additions and delivery documentation do not change the tested code.

Reproduce:

```bash
python -m pytest -q tests/test_igird_flexure_development.py
python qa/igird_flexdep1_verify.py --out /absolute/path/to/qa-output
streamlit run qa/igird_dbqa_perf_runtime.py
```

Full clean release: `concrete-section-pro_IGIRDER-FLEXDEP1-aashto-developed-flexure.zip`. Its external `RELEASE_MANIFEST_IGIRDER_FLEXDEP1_2026-10-04.json` records SHA-256, byte size, entries, absence of caches, preserved baseline files, selected tests and fresh-extract validation. QA evidence and numerical diagrams are included in the full project; no browser executables, virtual environments, node modules, caches or temporary logs are packed.

## Remaining engineering gates

This milestone corrects primary section φMn and end development within its stated normal-weight, fixed-axis I-Girder scope. Final positive flexure retains the lower-f'c effective composite section and separate effective-width/interface-action acceptance. Negative composite flexure, actual concurrent biaxial checks, the existing debonding-detailing FAIL, drawing-specific bar cutoffs/hook/anchorage and unverified force/datum source conditions remain separate. Do not mark these accepted because a numerical section D/C is below one.

Previously observed interface centroid/stirrup-count issues are not repaired by FLEXDEP1. Segmental Box Girder files are unrelated and were not edited.

# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.VTQA1

Date: 2026-10-04. Code basis: supplied AASHTO LRFD Ninth Edition (2020), Section 5. Continue the accepted Precast I-Girder project; the user's App Style and source gates remain applicable.

Accepted baseline: **IGIRDER.CHART2** full project, SHA-256 `59e726b75ccefb5a969fa70090a44ef1422ba7cfca9ed404dcc20c55e8f75ab6`, 1,125 entries. No baseline file is removed. This is a complete project ZIP, not an overlay.

## Resulting behavior

- Shear/Torsion/Combined default to one maximum original D/C curve, limit=1.0 and governing marker. Source-paired selected-case demand/resistance diagrams remain available. Shared Plotly/style defaults, full physical span, missing gaps and raw force coordinates remain.
- Three principal result cards replace the dense parameter card groups. Engineering equations, audit tables, original cases and component charts are collapsed below the main workspace.
- Analysis exposes missing longitudinal material and development inputs beside V/T. fy starts at zero; no SD40 grade property is inferred. Existing verified Flexure bar development is reused unless an explicit V/T source exists. No ordinary bar identity/geometry is replaced.
- Calculate Shear + Torsion updates the standalone Shear and Torsion caches too. Review, chart selection, Summary and Report read stored results and do not rerun solvers.
- Combined retains independently available Veff/spacing/transverse checks when a later longitudinal source is missing. PARTIAL is visible, overall D/C is unavailable and final PASS is withheld. A known failure still remains FAIL and its actual component reason is shown separately from the missing input.
- The photographed hoop confirmations are honored. The release does not tell the user to reselect confirmed hoops or auto-confirm any design input.

## Calculation corrections

See **IGIRDER_VTQA1_CALCULATION_REVIEW_2026-10-04.md** for equations, assumptions, source provisions, numerical examples and limitations.

Automatic I-girder dv uses the intentionally conservative **0.72h** basis, because the former area-centroid d cannot substitute for force-weighted de in 5.7.2.8-2. Verified manual dv remains available; a value greater than h blocks the check. Undefined longitudinal materials receive zero elastic stiffness. Ordinary As development is applied once in εs for all three checks. Shear design fc is capped at 15 ksi; torsion/required combined fc at 10 ksi. M2/V3 remain references and cannot drive torsion K or primary combined biaxial rejection.

Retain the already validated General Procedure equations, SI conversion of US coefficients, Ao=solid-section shear-flow area using be=Acp/pc, physical hoop ph, Tn equation, φ and transverse fy policy, 5.7.2.6 spacing, single-hoop reinforcement sum and concurrent longitudinal equation. No ph/8 spacing rule is added to the supplied solid I-girder route. The existing combined Veff/compression guard remains explicitly conservative.

**V/T still uses precast geometry.** Composite deck torsion needs its own verified flow/cage/interface model and is not implemented or certified. Nominal positive-flexure fps uses the existing composite preparation separately. Negative composite flexure, bearing/D-regions, fatigue, shop execution and unsupported material/model branches remain outside this sectional certification scope.

## User workflow

1. Import the user's unchanged native CSI workbook using the existing single uploader. The user edits P=0 in Excel; the app does not impose axial force zero. Retain all 80 rows, six signed force quantities and Max/Min occurrences. M2 and V3 are raw references.
2. Keep the verified transverse zone layout and cage confirmations. Analysis → Shear + Torsion shows any missing longitudinal material; define the actual verified fy/Es there. Enter true bar continuity/development/end-anchorage details in the same workspace.
3. Press Calculate Shear + Torsion once. Read Max D/C and the actual governing component; open one selected case or an equation trace when needed. Repair real insufficiency or incomplete sources before acceptance. Native component envelopes retain the final coupled source REVIEW gate.

Changing longitudinal material/development invalidates **all three V/T** results. Torsion qualification remains selective: it changes Torsion and Combined, not standalone Shear. Flexure retains its own accepted hashes and development handling. New V/T result versions are `IGIRDER.VTQA1.*`; stale results are not promoted by navigation. Project JSON persists material definitions and V/T development through the existing schema. No new persisted calculation cache is added.

## Verification

- Full `app.py` Streamlit AppTest exercises actual Calculate, inline material definition, development inputs and both chart views. Photographed-cage reproduction has 88 partial combined rows/84 numeric transverse rows; missing overall D/C remains missing.
- Explicitly hypothetical verified-input QA supplies fy=390 MPa/ld=1000 mm only in memory, with unanchored cut ends. It yields 84 numeric overall combined rows. Raw 80-row/480-component source and all original 34 bar identities/coordinates remain unchanged. Material/development JSON roundtrip passes. Native coupled PASS remains withheld.
- Independent source-unit equation substitution passes 1,723 scalar comparisons, with maximum relative error below 8×10⁻¹³. Source code caps, ordinary development, unknown material stiffness, reference-only M2/V3, invalid dv and preserved source/missingness have focused regressions.
- Fresh extraction passed **621 tests across 51 modules** in 47.744 seconds, with no failures/errors/skips. Compile/startup, native import actions (480 exact components), prior Flexure/Interface actions, and new V/T controls all passed. Final production/test Python fingerprint must match that extraction. Details appear in `qa/evidence/igird_vtqa1/fresh_validation_summary.json` and the release manifest.

Evidence files are under `qa/evidence/igird_vtqa1/`. Existing milestone evidence is retained as historical evidence. PNGs use Matplotlib with production Plotly coordinates and HTML embeds JS. Browser screenshots/print-layout verification are not claimed.

## Run / continue

```bash
streamlit run app.py
python -m pytest -q tests/test_igird_vtqa1.py tests/test_igird_uls5_shear_general_procedure.py tests/test_igird_uls6_torsion_general_procedure.py tests/test_igird_uls7_concurrent_vt.py
python qa/igird_vtqa1_ui_verify.py
python qa/igird_vtqa1_equation_verify.py
```

Do not replace the user's JSON or workbook with hypothetical QA inputs. Do not use a transverse-only PASS to certify combined resistance, silently add composite deck area to Tn, extrapolate missing end stiffness or assume bar material/development to close a graph. Any future composite torsion route requires verified sectional mechanics and source fixtures before final acceptance.

Repo summary: Simplify I-girder V/T charts, correct conservative shear depth and longitudinal development sources, and retain actionable partial combined checks.

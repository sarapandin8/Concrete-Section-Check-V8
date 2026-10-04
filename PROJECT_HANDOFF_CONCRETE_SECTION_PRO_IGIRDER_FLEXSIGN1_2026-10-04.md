# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.FLEXSIGN1

Date: 2026-10-04. Active design code: **AASHTO LRFD Bridge Design Specifications, 9th Edition (2020)**.

## Baseline, source authority and user confirmation

Continue the complete `concrete-section-pro_IGIRDER-FLEXDEP1-aashto-developed-flexure.zip`, SHA-256 `8af880c6e44e2017b91a8a110114067de805335cfcffd29717ba0ed945b124f8`. Preserve every baseline file and the ULS6F → ULS7 → DBQA1/PERF3 → PERF4 → FLEXDEP1 lineage. Earlier handoffs and QA evidence remain historical records, not the active sign interpretation for the user's source.

The user confirmed that x=0 and x=20 m are the physical concrete beam ends and strand cut ends, and **all force signs remain as CSiBridge output**. Both cut-end extensions must be 0 m for this model. Do not invent bearing offsets, discard Nu, remove failed stations, or confirm bar anchorage without drawing evidence. User authorization to correct φMn to the current project code remains active; ACI screenshots and Segmental Box Girder attachments are unrelated to this release.

Unchanged original fixture: `qa/fixtures/I_Girder_20m.json`, 44,911 bytes, SHA-256 `c27a27278fef69b5347e7216f5b3c9324f723a9a0ca2d5b52a8956c1fe765799`. It has a 300 mm deck. The latest Final Composite PDF shows a 250 mm deck. The new ready-to-load fixture explicitly changes deck thickness to 250 mm and declares CSI signs plus the confirmed physical ends:

`qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json`, SHA-256 `c59a8405ba0d96b6827fda4d54e28a90ebfccc4c5e543a2df4b9bea675f816d6`.

All `workflow_load_tables` are identical to the original JSON. No force value or sign, material definition, reinforcement layout or anchorage confirmation was changed. A separate 300 mm QA run isolates the geometry difference.

## Problem and resulting behavior

The previous I-Girder ULS readers assumed a compression-positive Nu table. CSI frame P is tension-positive. Therefore the previous supplied-model result incorrectly treated +575.159 kN at x=0 as compression and −1.492 kN at x=20 as tension. **Those endpoint interpretations and their numerical φMn values are superseded for this unchanged CSI source.** The correction belongs at the raw axial-input boundary, not in the strand transfer/development laws.

Loads and Analysis now share an explicit source-convention selector. For unchanged CSI output choose **CSiBridge / CSI frame P — positive tension, negative compression**. The raw table is immutable; each formula reader obtains canonical compression-positive Nu once. Interpolated loads and synthetic diagram boundary rows remain raw-signed until read. Canonical `LoadCase.Pu_N` is never converted again.

| Declared input | Raw table P / Nu | Solver Nu (compression-positive) | AASHTO tension-positive Nu |
|---|---:|---:|---:|
| CSI tension-positive | +575.159 kN | −575.159 kN: tension | +575.159 kN |
| CSI tension-positive | −1.492 kN | +1.492 kN: compression | −1.492 kN |
| Already converted compression-positive | Nu | Nu | −Nu |

Mux, Muy, Vuy, Vux and Tu retain their entered signs and the existing axis mapping. This release addresses the axial convention; correct local-axis and moment-reference mapping remains required. Effective initial prestress stays inside the strand law and is not separately added as another external Nu.

Legacy projects without a declaration retain the old numeric behavior and show a warning. Do not silently infer CSI signs from unrelated Crossbeam metadata. The corrected fixture includes the declaration. Selecting another convention changes the input hash of every I-Girder ULS check, including zero-Nu rows, and makes stored results stale. JSON save/load persists the declaration and clears obsolete selector widgets. A retained I-Girder setting cannot change another known section preset's legacy convention.

## Production changes

| File | Responsibility |
|---|---|
| `analysis/girder_axial_convention.py` | Validate explicit source convention; return raw/canonical/AASHTO signs without mutating source rows. |
| `ui/girder_axial_convention.py` | Shared source selector and concise sign explanation in Loads and Analysis. |
| `ui/analysis_page.py` | Convert raw Nu for generic I-Girder analysis input, developed flexure, General Shear and Torsion; add convention/version to input hashes; expose Final failing-station summary. |
| `ui/igird_combined_vt.py` | Apply the same conversion to the actual ULS7 concurrent branch and its longitudinal/strain equations. |
| `analysis/igird_flexure_development.py` | Version the changed input contract; mechanical strength equations are unchanged from FLEXDEP1. |
| `ui/igird_flexure_development.py` | Stored trace fields for raw/canonical Nu and force action; direct explanations of failed end stations without hidden solves. |
| `io/project_io.py` | Persist/restore source declaration; clear stale convention widget state on load. |
| `tests/test_igird_axial_convention.py` | Independent preconverted-force comparisons, raw-data preservation, interpolation, JSON roundtrip, selective-cache invalidation and supplied-model end behavior. |
| `qa/igird_flexdep1_verify.py` | Verify raw Nu preservation separately from canonical Nu and record the chosen convention. |

Production paths in the table are relative to `concrete_pmm_pro/`. Crossbeam and Segmental Box Girder source-sign policies are unchanged. This is the I-Girder ULS route; SLS source handling is not migrated by this declaration.

## Current numerical result and interpretation

The following uses a 250 mm deck, all original station forces, x=0/20 physical cut ends, no confirmed ordinary-bar anchorage, and the existing missing-SD40 fallback (fy=390 MPa, Es=200,000 MPa). Numerical PASS rows are still REVIEW until source/details are verified.

| Stage / x (m) | Raw CSI P (kN) | Canonical Nu (kN) | Mu (kN-m) | Available φMn (kN-m) | Numerical result |
|---|---:|---:|---:|---:|---|
| Construction / 0, 20 | 0 | 0 | 0 | 0 | SECTION PREVIEW |
| Construction / 10 | 0 | 0 | 4,004.500 | 7,682.527967 | PASS; D/C=0.521248, acceptance REVIEW |
| Final / 0 | +575.159 | −575.159 | 334.5637 | Unavailable | NO EQUILIBRIUM / FAIL |
| Final / 10 | +25.940 | −25.940 | 7,184.6936 | 9,964.073205 | PASS; D/C=0.721060, acceptance REVIEW |
| Final / 20 | −1.492 | +1.492 | 4.4723 | 1.048919 | FAIL; D/C=4.263722 |

At x=0, every strand family has zero developed stress cap and ordinary-bar credit is zero under the entered straight-bar/anchorage assumptions. Applied axial tension therefore cannot be balanced by the model, which neglects concrete tensile strength at ultimate. There is no valid section Mn to plot. Store NaN, show FAIL and a red demand marker, and retain the gap; do not fabricate a zero point.

At x=20, the canonical axial force is small **compression**. A concrete compression block can balance it, giving φ=0.75 and a small but nonzero moment resistance. The red resistance line now reaches x=20 at **1.049 kN-m**, but that is below the actual 4.4723 kN-m demand. The two ends remain distinct failures. A beam-theory section result alone does not certify the anchorage / load-transfer D-region; review the real FEA force source/reference and actual end detail before accepting the end region.

The 300 mm comparison keeps the same force table and CSI convention: Final x=10 φMn=10,340.131363 kN-m and x=20 φMn=1.049458 kN-m. Construction x=10 Mu=4,078 kN-m with φMn=7,682.527967. The wet-deck demand change at Construction follows the explicit deck-thickness change, not the axial convention.

## Code basis and limits

Source sign: [CSI Frame Element Internal Forces Output Conventions](https://docs.csiamerica.com/help-files/sap/Output/Frame_Element_Internal_Forces_Output_Conventions.htm). Positive frame P acts outward on the positive and negative faces: tension.

Normative structural basis remains the supplied `03-SECTION-5-CONCRETE-STRUCTURES.pdf`: AASHTO 5.6.2.1 equilibrium / strain compatibility with concrete tension neglected, 5.9.4.3.1–3 strand transfer/development, 5.5.4.2 strain-based resistance factors, and 5.5.1.2.1/3 for separate B-/D-region analysis (printed pp. 5-25–26). Transfer length remains 60db=762 mm for a 12.7 mm strand, measured from each family's bond start. The FLEXDEP1 bonded-distance, κ, conservative bar-development and φ equations are unchanged. Do not reinterpret this release as an anchorage-detail design or move to ACI 318-14/19.

Unresolved acceptance gates are visible: missing SD40 material definition, ordinary-bar continuity/cutoffs/anchorage, unconfirmed Construction load factors, effective composite width, girder/deck interface shear, and the existing debonding-detailing QA. Imported Muy is retained but a concurrent biaxial strength check is outside this fixed-axis positive-flexure route. The previously reported interface centroid/stirrup-count issues are not repaired here. No current engineering FAIL was hidden or relabeled PASS.

The supplied PDF's chart clipping near x≈13 m is a separate print-layout issue. This release provides a verified standalone full 0–20 m PNG and does not claim to fix browser print CSS.

## Verification and clean delivery

See `qa/evidence/igird_flexsign1/` for numerical CSV/JSON traces, browser evidence and fresh-extract validation. Local engine observations: Construction 1.833 s (41 source stations), Final 1.929 s (21 source stations). Maximum balanced-station force residuals are 0.019222 N and 0.016945 N. All actual strand stresses are checked against their applicable stress cap. All station force values remain unchanged.

Clean extracted candidate: **423 tests passed across 41 selected modules**, zero failures/errors/skips; complete `app.py` Streamlit startup and compileall also passed. Details are in `fresh_validation_summary.json`. This scope covers I-Girder ULS/development/DBQA/PERF, prestress, composite preparation, AASHTO PMM, charts, result/cache handling and project JSON IO; it is not the full repository suite. Browser verification operated both real Calculate buttons, expanded both stored traces, changed the source convention, checked stale-result invalidation, restored CSI and recalculated. Calculate clicks took 2.434 s Construction / 2.903 s Final including local UI rendering, with zero page/console/Streamlit errors. The current environment cannot run agent-browser IPC; local Chromium/Playwright provided the UI verification fallback. Final delivery Python hashes must match this tested extraction; final documentation/evidence additions do not change tested code.

Reproduce:

```bash
python -m pytest -q tests/test_igird_axial_convention.py tests/test_igird_flexure_development.py
python qa/igird_flexdep1_verify.py --input qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json --out /absolute/path/to/qa-output
streamlit run app.py
```

Full release: `concrete-section-pro_IGIRDER-FLEXSIGN1-csi-axial-convention.zip`. The external manifest records the final SHA-256, size, entries, preserved baseline files, fresh checks and matching Python fingerprints. No caches, browser binaries, node_modules or virtual environments are included. Old baseline QA logs are preserved only to retain the accepted complete project; no new runtime logs are packed.

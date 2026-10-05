# Project handoff — IGIRDER.SHEARCOMP1

Date: 2026-10-05 (Asia/Bangkok). Complete app milestone; no external deployment.

## Baseline and task

Authoritative baseline: concrete-section-pro_IGIRDER-CHART3-full-span-source-capacity-diagrams.zip; SHA-256 e982467fd9aa14b85fb7b544b811222afb4f4e42b6233a8e90a43371f290fd4a; 1,237 entries. The workspace initially contained a reverted VTQA1 checkout; CHART3 was restored before all production edits. Preserve all historical files/handoffs and raw user fixture/workbooks.

User requested correction of phiVn for Final-Composite, then confirmed the bearings are 0.4 m from each physical end. Interpret as CL: x=0.4/19.6 m. An optional CL/inside-face clarification returned no answer; this CL interpretation remains an explicit assumption. Bearing lengths/internal faces remain unknown, not guessed. Governing source is the user's AASHTO LRFD 9th (2020) Section 5, not ACI or the older FHWA example. Follow CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md.

## Implementation

- analysis/igird_flexure_development.py adds force_resultants to an already solved response. Existing evaluate/solve/Flexure results are unchanged. Correctly remove displaced ordinary-bar concrete before classifying physical C/T and reconstruct Pn/Mn for nonzero Nu.
- analysis/igird_shear_depth.py owns station-developed C/T, force-weighted de, and dv=max(lever,0.9de,0.72h). Debonded dv uses kappa=2 per C5.7.2.8; strand cut-end coordinates are 0/L with no fictitious extension. No lower-bound-only numeric fallback when developed resultants do not exist.
- ui/igird_shear_section.py prepares the existing conservative uniform-lower-fc composite section for flexural depth/epsilon. It retains precast web fc/bv and raw torsion geometry; optional deck bars receive no unowned V/T development credit. Cache contexts/references/depths only within Calculate using an ephemeral dictionary. Review/hash/trace never solve. Canonical physical polygon signature ignores display names/vertex order, with actual dimensions hashed.
- code_checks/aashto_lrfd.py corrects spacing stress to (abs(Vu)-phi*Vp)/(phi*bv*dv), carries phi/Vp into simplified shear too, and introduces the source-qualified general shear fy cap (75 ksi default, optional verified Article 5.4.3.3 API branch only; no automatic UI exception).
- analysis/igird_combined_vt.py aligns partial ordinary straight-bar credit with the 304.8-mm minimum already used by FLEXDEP1. Unconfirmed material/continuity/development receives no certified depth credit; full end anchors are declarations at physical x=0/L.
- ui/analysis_page.py and ui/igird_combined_vt.py use the staged composite input in S/T/Combined, developed depth trace, composite-height tension half, and actual phi in spacing. Numeric failures take priority, while source/composite action gates withhold PASS. Torsion Ao/ph/Acp/Pcp/K/Tcr concrete remain the qualified solid precast section; no composite torsional strength certification.
- analysis/igird_shear_support.py + ui/igird_vt_workspace.py own bearing CL/internal-face coordinates and optional along-beam lengths. No invented face. Known faces allow supplemental face+local-dv station interpolation; geometry alone never adopts 5.7.3.2 exemption. Keep every original force row, including overhangs. No bearing-span substitution in Construction auto-loads or strand development.
- io/project_io.py saves/reloads support settings and clears previous project's support widgets, preventing geometry leakage. S/T/Combined hashes include canonical support/development/material/geometry/equation/interface source; Flexure hash unaffected by bearing offsets.
- ui/igird_vt_workspace.py provides one collapsed bearing editor, visible coordinates, current composite-action gate and existing input completion. Physical-end anchor checkbox labels distinguish inset bearings from 0/L. CHART3 case diagrams/end provenance/compact legends remain intact.

## Cache contracts

S/T result versions: IGIRDER.SHEARCOMP1.developed-composite-depth.shear.chart3 / .torsion.chart3. Concurrent kernel RESULT_VERSION remains IGIRDER.VTQA1.concurrent-vt-partial-results because Summary interprets that schema; updated check input signature stales old Combined results. Preserve separate diagram_capacity_df payloads in the S/T source caches populated by Combined. No persistent solver cache or automatic recalculation on review.

## Source model and limits

examples/I_Girder_20m_IGIRDER_SHEARCOMP1_FinalComposite_bearing400.json uses the original project/deck 250 mm and imports all 80 unchanged latest Left Exterior Excel rows. Raw P is NOT zeroed: the user elected to edit P in their own workbook. The fixture's raw P values remain and CSI sign conversion is unchanged. No inferred SD40 properties, continuity, anchors, closed hoop, 135-degree hook, perimeter/corner details, Be or interface verification are enabled. This is a source example, not a certified passing design. The P=0/verified fy=390/ld=1000/anchors models in UI QA are explicitly hypothetical, never user confirmations.

Composite depth uses the accepted conservative uniform lower deck/girder fc compression block; web resistance fc stays girder. Native Max/Min concurrency and negative-composite acceptance remain unproved. Below-minimum General Procedure sx/ag -> sxe, composite torsion force-flow, bearing D-region/STM/confinement and execution details remain outside current automatic acceptance. Unknown endpoint depth/strain remains unavailable with chart-foot source explanation; never copy interior capacity or force Mn=0 to hide a failure.

## Validation and resuming

661 tests / 53 modules passed. Full app Streamlit AppTest covers 16 case charts with real Calculate/anchorage/bearing controls, both Flexure stages, Interface and Combined; zero exceptions, zero review solver calls. 1,811 independent V/T/Combined scalar substitutions +336 diagram substitutions +1,312 independent depth/spacing/epsilon comparisons passed. Code compile passed. See qa/evidence/igird_shearcomp1/*.json and CSV/PNG/HTML. Read the Thai review in docs for practical setup and source qualifications. These previews are scientific plots, not browser screenshots.

Run qa/igird_shearcomp1_source_verify.py for unchanged-P original input; qa/igird_shearcomp1_ui_verify.py for P=0 controlled UI assumptions; qa/igird_vtqa1_equation_verify.py with CSP_QA_OUT pointing at this release evidence; qa/igird_shearcomp1_depth_spacing_verify.py for additional substitutions. QA bearing width=400 mm is hypothetical and is not in the user example, which stores width=0 (unknown).

Deliver full clean ZIP plus one-sentence English Repo summary. No source ZIP deletion or raw user data changes. The final manifest records clean packaging, baseline-entry preservation, raw source identity, tested Python fingerprint and fresh-extraction checks.

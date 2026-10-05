# Concrete Section Pro — IGIRDER.SHEARCOMP1

Final-Composite V/T now uses developed flexural C/T resultants and force-weighted de for dv, with precast web properties retained. Stirrup spacing stress includes phi. Bearing centerlines/internal faces are distinct from physical strand cut ends; unknown bearing lengths do not create fictitious support faces or near-support exemptions.

Run `streamlit run app.py`. See the new handoff and `docs/CONCRETE_SECTION_PRO_IGIRDER_SHEARCOMP1_REVIEW_2026-10-05.md`. The `examples/` model records bearing CL x=0.4/19.6 m and the unchanged latest Excel forces, including original P; import your own P=0 Excel if that is the intended source. No material/anchorage/interface confirmation is inferred. Recalculate Interface/Shear/Torsion/Combined for the current inputs. Full-span diagrams retain genuine missing-source markers.

## Previous milestone

# Concrete Section Pro — IGIRDER.VTQA1

Shear, Torsion and Combined V+T show one maximum original D/C curve and limit=1.0 by default. Choose a single case for the signed force/resistance diagram. Three main cards and collapsed traces reduce workspace clutter; detailed source checks remain available.

Analysis exposes missing longitudinal material and development inputs. Define actual verified fy/Es, confirm real continuity/anchorage/ld, then Calculate Shear + Torsion once to refresh all three V/T results. Independently known partial checks stay visible when another source is missing; missing overall acceptance stays unresolved.

Automatic I-girder dv now uses conservative 0.72h instead of treating an area centroid as the code's force-weighted de. Verified manual dv remains available. Unknown bar materials receive zero stiffness, developed As is credited once, fc design limits are 15 ksi for shear and 10 ksi for torsion/required combined checks, and M2/V3 remain raw references. V/T geometry is precast; composite deck torsion is not certified. The user supplies P=0 in Excel. Native Max/Min source coupling gates remain.

Run `streamlit run app.py`. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_VTQA1_2026-10-04.md`, `IGIRDER_VTQA1_CALCULATION_REVIEW_2026-10-04.md` and `qa/evidence/igird_vtqa1/` for source provisions, assumptions and verification. Hypothetical QA materials/development are not production inputs.

## Historical milestones

# Concrete Section Pro — IGIRDER.CHART2

Shear and Torsion legends identify native Max/Min occurrences and show resistance/reference quantities once. Exact finite copies are drawn once, while genuinely different case-dependent paths and gaps remain. Precast I-Girder V/T Analysis uses the established browser Plotly renderer with full source hover.

Combined V+T now reports completed check rows and finite-D/C rows, with a visible required-input/source-action table. Missing torsion-qualified cage inputs or unresolved longitudinal materials retain their engineering gates; no capacity is assumed to make a graph. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CHART2_2026-10-04.md` for verification and input guidance.

# Concrete Section Pro — IGIRDER.CHART1

Final Composite charts now use short, distinct Max/Min/occurrence labels and show φMn once in the legend. Exact coincident resistance paths are drawn once; genuinely different capacity paths and missing-equilibrium gaps remain. Interface shear shows one blue maximum scalar demand envelope and one dashed-red minimum available resistance curve, with original source cases on hover. All original row-based calculations and D/C remain in the audit.

Run `streamlit run app.py`, open Analysis → ULS → Flexure → Final Composite and calculate the required checks. Hover shows full source identity. The user's P=0 decision is entered in their Excel; no automatic axial override is added. Import, signs, material/development rules and all engineering equations are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CHART1_2026-10-04.md`, `tests/test_igird_chart_display.py` and `qa/evidence/igird_chart1/`. `python qa/igird_chart_ui_verify.py` exercises full app.py and exports exact trace previews. PNGs use Matplotlib; standalone Plotly HTML is interactive. These are not browser screenshots, and browser print-layout verification is not completed.

## Previous milestone

# Concrete Section Pro — IGIRDER.CSIIMPORT2

The Precast I-Girder ULS panel now accepts the user's unchanged latest single-sheet CSiBridge Excel through one uploader with automatic format detection. All 80 rows, both Max/Min, repeated stations and all six signed force components are retained. Existing app-column CSV/XLSX tables use the same uploader. The previous format radio is removed.

Run `streamlit run app.py`. On Loads → ULS → Final Composite import, use kN / kN-m, upload the original Excel, confirm Left Exterior Girder and the actual FEA envelope name, then **Replace current rows**. No header changes, units-row deletion or manual force edits are required. Existing native multi-sheet imports still select the largest |M3| girder demand by default.

**M2→Muy and V3→Vux are reference only**, as confirmed by the user. P→Nu, V2→Vuy, T→Tu and M3→Mux feed the existing relevant checks. All six source quantities are retained in Analysis inputs and in the stored result trace. CSI signs and the existing internal Nu = −P conversion remain intact. Engineering equations and source-coupling REVIEW/FAIL gates are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CSIIMPORT2_2026-10-04.md`, `tests/test_igird_csi_import_auto.py` and `qa/evidence/igird_csiimport2/`. `python qa/igird_csi_import_ui_verify.py` exercises the full app.py using original workbook upload bytes, including a persisted old legacy-format selection, all 480 force values, actual Final Calculate, reference trace and legacy compatibility. This is Streamlit AppTest verification; browser visual verification is not completed.

## Previous milestone instructions (historical)

The CSIIMPORT1 format-radio steps below are superseded by automatic detection above.

# Concrete Section Pro — IGIRDER.CSIIMPORT1

The Precast I-Girder Loads importer now reads native multi-sheet CSiBridge member forces with a units row and both Max/Min bounds. Select **Left Exterior Girder**, the largest |M3| in the supplied workbook. All 80 original rows remain, including repeated stations; no force component or sign is mixed across rows. The default critical-member comparison ranks |M3| demand, with separate |V2| and |T| leaders. It does not establish the critical member by capacity ratio for every check.

Run `streamlit run app.py`. On Loads → ULS → Final Composite import, keep **CSiBridge girder forces**, upload the native workbook, check the selected worksheet and FEA envelope name, then **Replace current rows**. Download the new Excel template from the same panel. The existing **App columns (legacy)** import remains available. Native imports normalize declared units to kN/kN-m and preserve raw CSI signs; the FLEXSIGN1 Nu conversion remains inside the solver.

Final Composite screens all 80 imported rows, including the negative Mux bound. Negative composite acceptance and concurrent Mu/Nu/Vu/Tu are not established by this worksheet. Numerical screening and failures remain visible; coupled PASS is REVIEW. Use CSiBridge Correspondence / governing load-case actions for final coupled acceptance. M2/Muy is preserved but the developed flexure route remains primary-axis Mux only. The current AASHTO development, φ, prestress, geometry and detailing rules are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CSIIMPORT1_2026-10-04.md`, `tests/test_igird_csi_import.py` and `qa/evidence/igird_csiimport1/`. The shipped Excel asset is static; the app needs no spreadsheet-authoring dependency. `python qa/igird_csi_import_ui_verify.py` runs the production Streamlit import and Calculate controls using fixture upload bytes. This is an AppTest check, not a browser visual verification.

## Previous accepted milestone

# Concrete Section Pro — IGIRDER.FLEXSIGN1

Precast I-Girder ULS now accepts unchanged CSiBridge frame P signs through an explicit Loads / Analysis convention selector. Raw P is positive in tension; solver Nu is positive in compression and equals −P. Flexure, Shear, Torsion and concurrent Shear + Torsion share this conversion. All imported table values are preserved. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_FLEXSIGN1_2026-10-04.md` and `docs/CONCRETE_SECTION_PRO_FLEXSIGN1_REVIEW_2026-10-04.md`.

Run the complete application with `streamlit run app.py`. For the user's unchanged CSiBridge table select **CSiBridge / CSI frame P — positive tension, negative compression**, then Analysis → ULS → Flexure → Construction / Final Composite → Calculate. The supplied corrected JSON already declares this convention and uses a 250 mm deck matching the latest PDF. Legacy JSON files retain the old compression-positive interpretation until explicitly selected; review the selector before Calculate.

The FLEXDEP1 AASHTO LRFD 9th Edition (2020) transfer/development and strain-based φ solver remains active. Physical beam / strand cut ends are confirmed at x=0 and 20 m, with zero extensions. Under the current unverified bar anchorage, the corrected Final result still fails at both ends: no equilibrium at x=0; φMn=1.049 < Mu=4.472 kN-m at x=20. The new handoff supersedes earlier compression/tension interpretations for this CSiBridge source. Numeric section PASS does not close material, detailing or composite-action acceptance gates.

## Earlier Crossbeam milestone

Eliminates the deployed Crossbeam ULS trace-owner `NameError` by removing the runtime helper lookup and resolving `Zone-owned` versus `Segment-owned` directly at every render site. All ANALYSIS4C7C engineering and chart behavior remains unchanged. See `README_CROSSBEAM_ANALYSIS4C7C2.md`.

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

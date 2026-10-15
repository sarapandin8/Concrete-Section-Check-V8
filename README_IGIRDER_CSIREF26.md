# Concrete Section Pro — IGIRDER.CSIREF26

This milestone binds CSI reporting origins to native Loads source records and transports analysis moments to the actual resistance origin at each station. Raw Loads remain unchanged. The current-project JSON records the CSI reporting point 0.615600 m below deck top, with horizontal output at each girder web center.

Run `streamlit run app.py`, open the prepared Project JSON and recalculate Analysis. The optional `CSI force output reference` expander is shared by ULS and SLS imports. New native files retain independent source snapshots; an explicit Save applies a new source location to current files. Geometry changes recalculate resistance origins while preserving the source snapshot.

Native independent Max/Min components are transported as interval bounds and cannot establish concurrent acceptance. Existing declared correspondence is labeled as a source contract. Full Girder torsion and combined V+T remain partial I-hoop resistance checks with REVIEW qualification; complete composite shear–torsion and biaxial strength are not implemented by this milestone.

See `IGIRDER_CSIREF26_HANDOFF_TH.md`, `tests/test_igird_csiref26.py`, and `qa/evidence/igird_csiref26/`. Latest selected tests: 77 passed, including 19 CSIREF26 tests. Real DL/U2A files and configured-project AppTest were checked. Browser visual verification remains unavailable. Wider prior regression has seven unchanged baseline failures; full-suite PASS is not claimed.

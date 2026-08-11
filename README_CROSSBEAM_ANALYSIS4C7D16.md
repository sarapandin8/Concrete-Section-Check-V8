# CROSSBEAM.ANALYSIS4C7D16 — Report / QA traceability artifact-state closeout

## Purpose
Close the Report / QA Traceability semantic defect where a never-generated Draft Design Report could be shown as `Out of date`, even while Model and Analysis were current.

## Changes
- Replace the legacy generic `Report status` display on Crossbeam Report / QA → Traceability with explicit Draft Design Report artifact freshness:
  - `NOT GENERATED`
  - `CURRENT`
  - `OUT OF DATE`
- Add a deterministic report-source fingerprint derived from:
  - active Crossbeam construction type,
  - last Analysis input fingerprint,
  - stored Flexure / Shear / Torsion / Shear + Torsion package fingerprints.
- Store the report-source fingerprint when the Draft Design Report DOCX is built.
- Prevent export of a previously built Draft DOCX when its stored source fingerprint no longer matches the current stored Analysis source; the user must rebuild the draft first.
- Rename truncated UI/report `Result hash` wording to `Result fingerprint` so the 16-character display is not mistaken for a full cryptographic digest.
- Clarify pending SLS report scope to include both `SLS Stress & Cracking` and `SLS Deflection / Camber`.
- Update the missing-SLS required action wording to `before final report issue`, which is correct both inside and outside the Report / QA workspace.

## Engineering contract preserved
- Report / QA remains read-only with respect to Analysis.
- No PMM, ULS, SLS, or verification solver is rerun from Report / QA.
- No ACI equations, demand/capacity routing, rebar credit, prestress credit, or physical-joint engineering semantics changed.
- Draft export remains `DRAFT — NOT FOR ISSUE`.
- Final Design Report export remains disabled pending SLS/report-template closeout.

## Files changed
- `app.py`
- `concrete_pmm_pro/reporting/crossbeam_report_qa.py`
- `tests/test_crossbeam_analysis4c7d15_report_qa_foundation.py`
- `tests/test_crossbeam_analysis4c7d16_report_qa_traceability_artifact_state.py` (new)
- `tests/test_results_ws4_summary_dashboard.py`
- `README_CROSSBEAM_ANALYSIS4C7D16.md` (new)

## Verification
- `python -m py_compile app.py concrete_pmm_pro/reporting/crossbeam_report_qa.py` — PASS
- D16 artifact-state / SLS wording tests — PASS
- D15 stored-package traceability test — PASS
- D15 Draft DOCX report-build test — PASS
- Result Summary dashboard wording tests — PASS
- D14 Result Summary visual-semantics regression — PASS

## Engineering change statement
This milestone changes Report / QA traceability and export provenance semantics only. Engineering solver outputs are unchanged.

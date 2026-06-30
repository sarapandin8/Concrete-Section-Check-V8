# QA.CODE.AUDIT1 — Full-code audit and duplicate ULS D/C download-key hotfix

## Scope
- Audit the latest baseline with compile and broad targeted pytest checks.
- Fix one confirmed Streamlit duplicate-element risk found during the audit.

## Confirmed bug found
Two `st.download_button()` calls used the same label `Download ULS D/C Result CSV` without explicit keys in Analysis / Flexural PMM rendering paths. If both the summary D/C export and detailed ranking export were rendered in the same Streamlit rerun, Streamlit could raise a duplicate element ID error.

## Change
- Add explicit unique keys:
  - `uls_dc_summary_result_csv`
  - `uls_dc_ranking_result_csv`
- Add source-audit regression test to keep the two buttons keyed.

## Out of scope
- No solver changes.
- No PMM demand/capacity equation changes.
- No shear/torsion/SLS/report calculation changes.
- No geometry or section-property formula changes.

## Remaining QA note
The audit found many UI widgets without explicit keys. Most are currently safe because they render in mutually exclusive contexts or unique call sites, but this remains technical debt for future Streamlit hardening.

# STATE.RESULT4 — PMM Dashboard Duplicate Download Key Hotfix

`STATE.RESULT4` fixes a Streamlit `StreamlitDuplicateElementId` regression introduced while restoring the PMM visual review tabs in `STATE.RESULT3`.

## Root cause

The Flexural (PMM) workspace rendered the same ULS demand/capacity transparency panel twice in the same Streamlit rerun:

1. the stored PMM result snapshot above the PMM dashboard; and
2. the Summary tab inside the PMM Visual Review dashboard.

Both panels contained a `st.download_button` with the same label and same implicit identity. Recent Streamlit versions reject this duplicate implicit element ID and stop the app.

## Change

The transparency panel now accepts a `widget_key_prefix` argument. The two PMM render locations pass separate prefixes so their CSV download widgets have stable unique IDs:

- `stored_pmm_snapshot_uls_dc_trace_csv`
- `pmm_dashboard_summary_uls_dc_trace_csv`

## Scope guard

This is a UI/runtime hotfix only. It does not change PMM solver equations, demand/capacity checks, shear/torsion/V+T gates, prestress logic, SLS checks, report calculations, saved project schema, or section geometry.

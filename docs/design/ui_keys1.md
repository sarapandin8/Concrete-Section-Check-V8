# UI.KEYS1 — Streamlit button/download-button key hardening

## Scope
Harden Streamlit widget identity for action widgets that are commonly repeated in large pages:

- `st.button()` / column button variants
- `st.download_button()` / column download-button variants

## Change
- Add explicit unique keys to every button and download button in `app.py` and `concrete_pmm_pro/ui/*.py` that did not already have one.
- Add source-audit tests that require explicit keys for these widget types and reject duplicate literal keys.

## Why this matters
The Analysis workspace now renders multiple summary, detail, report, and export panels in the same Streamlit rerun. Relying on Streamlit's implicit widget IDs is fragile when labels, parameters, or repeated helper functions overlap. Explicit keys make the app more stable as UI panels are reused.

## Out of scope
- No solver changes.
- No PMM/shear/torsion/SLS/report calculation changes.
- No input-widget key migration in this milestone; input widgets are more state-sensitive and require page-by-page migration.

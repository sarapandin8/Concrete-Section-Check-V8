# CROSSBEAM.ANALYSIS4C7D24 — Deflection import editor dtype fix

## Scope
Hotfix the Analysis → SLS Deflection / Camber displacement-source replacement path after a verified CSV/XLSX import could trigger `streamlit.errors.StreamlitAPIException` when the persistent `st.data_editor` was rebuilt.

## Root cause
Pandas can infer completely blank optional text columns such as `Source point` / `Note` as `float64` (all `NaN`) and integer-looking numeric columns as `int64`. The D23 editor then configured those columns as Streamlit `TextColumn` / floating `NumberColumn`, so the uploaded dataframe schema could be incompatible with the editor column configuration after `Replace displacement source` and rerun.

## Fix
- Pin `Active` to boolean.
- Pin `Station s (m)` and `Vertical displacement (mm)` to float, preserving invalid/blank values as `NaN` for downstream validation.
- Pin `Case Name`, `Stage`, `Source point`, and `Note` to text and normalize blank/NaN text to an empty string.
- Give an empty source table the same explicit editor-facing schema.
- Preserve all D22/D23 source ownership, Project JSON migration, fingerprint, and engineering-evaluation behavior.

## Engineering impact
None. No deflection/camber equations, support-chord evaluation, sign convention, acceptance ratio, ULS/SLS stress logic, prestress logic, or report aggregation was changed.

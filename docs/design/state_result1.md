# STATE.RESULT1 — Persist PMM Result Cache Across Navigation and Project Save/Load

## Purpose

Prevent valid Flexural (PMM) analysis results from being treated as missing after normal workspace navigation or after a saved project is reopened. This milestone addresses application state and project serialization only; it does not change any PMM solver equation, demand/capacity equation, sign convention, prestress logic, shear/torsion formula, SLS formula, or report calculation.

## Problem observed

Streamlit reruns the script whenever the user changes workspace. That UI rerender is normal, but it can look like the app is rerunning the PMM solver if cache status is not explicit. Separately, project save/load previously stored engineering inputs but not the heavy PMM result objects and demand/capacity summary, so reopening a project required the user to run Flexural (PMM) again even when no engineering input had changed.

## Implementation boundary

- Keep the existing PMM solver and D/C checker untouched.
- Reuse the stored in-session PMM result when `analysis_input_hash` is unchanged.
- Serialize PMM result cache metadata in project JSON under `metadata.analysis_results`.
- Restore saved PMM result and D/C summary only when the saved PMM input hash matches the loaded project inputs and accuracy preset.
- Reject stale saved analysis metadata and leave Analysis status as `Not run` when loaded inputs do not match the saved hash.
- Keep dirty-state status `Current` only for a restored valid cache; otherwise loaded projects start with analysis `Not run`.

## Engineering guardrails

Saved analysis results are cache artifacts, not new engineering inputs. The app must never use a saved PMM result when the current section, material, reinforcement, prestress, loads, analysis settings, or accuracy preset produce a different input hash. In that case the user must rerun analysis.

## Files touched

- `app.py`
- `README.md`
- `concrete_pmm_pro/io/project_io.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_project_io.py`
- `tests/test_analysis_runtime.py`

## Tests

Targeted tests cover PMM cache reuse without solver calls, valid saved PMM cache restore, stale saved PMM cache rejection, project dirty-state behavior, and existing analysis runtime hash behavior.

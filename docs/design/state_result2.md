# STATE.RESULT2 — PMM Navigation Render Cache / Detail Gate

## Purpose

`STATE.RESULT2` fixes the user-visible slowdown where returning to Analysis → ULS Strength → Flexural (PMM) after a completed run felt like the application reran analysis even when engineering inputs had not changed.

The PMM solver cache from `STATE.RESULT1` already protected `run_rc_pmm_solver()` behind the engineering input hash. The remaining problem was UI rendering cost: Streamlit reruns the page script during navigation, and the Flexural workspace rebuilt PMM display DataFrames, D/C presentation artifacts, dashboard tabs, plots, and raw tables on every return. Closed expanders and inactive tabs still execute their Python bodies, so the page could be slow without a real solver recalculation.

## Scope

This milestone is UI/state/performance only.

- No PMM solver equation changes.
- No demand/capacity equation changes.
- No prestress `Pe_eff` behavior changes.
- No shear, torsion, V+T, SLS, deflection, or report calculation changes.
- No project JSON schema change is required.

## Changes

1. Add a PMM display-artifact cache keyed by the stored PMM result identity.
   - `rc_pmm_display_dataframe`
   - `rc_pmm_display_summary`
   - `rc_pmm_numeric_summary`
   - `rc_pmm_display_cache_hash`
   - `pmm_result_display_cache_status`

2. Keep the decision snapshot visible after navigation.
   - Stored PMM result and ULS D/C summary remain visible.
   - The app reports solver-cache and display-cache status explicitly.

3. Gate expensive PMM dashboard rendering behind an explicit checkbox.
   - Detailed PMM dashboard tabs, plots, and raw tables are not rendered automatically on page return.
   - Enabling the detail gate renders the same stored result; it does not rerun the PMM solver.

## Engineering intent

A normal Streamlit navigation rerun is not an engineering analysis rerun. The application must distinguish:

- **solver recalculation**: only after the user presses Run/Recalculate and the cache is invalid or forced;
- **display-artifact rebuild**: only when the stored PMM result identity changes;
- **UI rerender**: normal Streamlit behavior during navigation, kept lightweight by default.

## QA notes

Added tests verify that cached PMM display artifacts are reused without rebuilding the display DataFrame and that source wording explicitly gates detailed dashboard/plot rendering.

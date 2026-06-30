# STATUS.COLPIER2 — Column/Pier Decision Summary Fresh PMM State

## Purpose

Fix a Streamlit render-order issue where the Column/Pier ULS Decision Summary could remain on `NOT READY` for Flexural (PMM) during the same rerun that successfully calculated PMM demand/capacity.

## Root cause

The decision summary was rendered above the ULS check selector and above the Flexural (PMM) runtime panel.  When the user pressed **Run / Recalculate Analysis**, Streamlit reran the script top-to-bottom: the summary read the old session state first, then the Flexural workspace later calculated and stored `rc_demand_capacity_result`.  The stored result was correct, but the already-rendered summary did not refresh until a later rerun.

## Fix

`render_analysis_uls_pmm()` now creates a `st.container()` placeholder where the decision summary should appear, renders the active ULS workspace so it can update session state, and then fills the placeholder with `_render_column_pier_analysis_decision_view()`.

This preserves the decision-first visual layout while making the summary read the latest stored PMM, shear, torsion, and V+T states.

## Engineering boundary

No solver equations, PMM capacity logic, shear/torsion formulas, prestress logic, or code-check thresholds were changed.

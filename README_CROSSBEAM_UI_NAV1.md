# CROSSBEAM.UI.NAV1 — Workflow-Stable Analysis Navigation

## Outcome

Fixes the Portal Frame Crossbeam Analysis navigation so `SLS / Stress &
Cracking` remains selectable after Streamlit reruns and opens the existing
SLS1A workspace even when its Transfer source is blocked.

## Navigation contract

- `analysis_mode_settings` is the canonical workflow source and accepts both
  `AnalysisModeSettings` objects and validated dictionaries.
- The saved Project selector member type/label is recovery-only when the
  canonical state is temporarily absent or invalid.
- Project JSON restore wins over stale Project selector widget values.
- Workflow is resolved before `_nav_analysis_subpage` is validated or reset.
- Sidebar and main Analysis tabs use one shared workflow-scoped subpage list.
- Portal Frame Crossbeam, Bridge Girder, and Building Girder retain ULS, SLS
  Stress, and SLS Deflection/Camber navigation.
- Column/Pier retains ULS Strength only and does not expose SLS subpages.

## Protected behavior

- No Transfer Stress, PMM, Flexure, Prestress Loss, load, or section equation
  changed.
- Navigation does not run a solver or mutate stored engineering results.
- No Project JSON schema or analysis-result persistence change was introduced.
- Existing SLS1A source readiness and `TRANSFER SOURCE BLOCKED` behavior remain
  unchanged.

## Files

- `app.py`
- `concrete_pmm_pro/ui/navigation.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_ui_nav1_workflow_navigation.py`

## Repo summary

Stabilize Crossbeam Analysis navigation with canonical workflow recovery, shared workflow-scoped subpages, persistent SLS selection across reruns, and safe Column/Pier guards.

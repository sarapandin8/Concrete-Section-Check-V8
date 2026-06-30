### STATE.PERSIST1 — Persist Steel-System Flags and Stored Analysis Caches

Fixed navigation and project save/load persistence for steel-system enable flags and stored analysis results.

#### What changed
- Bridge Beam/Girder workflows now default ordinary rebar / longitudinal Al to enabled.
- Prestressed/precast girder presets still default prestressing steel to enabled.
- Section Builder steel-system switches are treated as engineering inputs, not transient UI state.
- Returning to Section Builder no longer silently resets:
  - Include ordinary rebar / Longitudinal Al
  - Include prestressing steel
- Steel-system flags are included in dirty-state Section input hashing.
- Project save/load now serializes and restores Beam/Girder ULS cached result entries, including cached pandas DataFrames.
- Project save/load now serializes and restores SLS serviceability summary cache.
- Added JSON-safe DataFrame serialization helpers for analysis cache metadata.
- Updated regression tests for current ULS/V+T wording and below-threshold Al behavior.

#### Behavior preserved
- Disabling ordinary rebar or prestressing steel does not delete stored input tables.
- Results remains read-only and does not rerun solvers.
- Beam/Girder ULS cache entries retain their per-check input hashes for Analysis-page reuse/stale handling.
- PMM cache restore remains analysis-input-hash aware.

#### Not changed
- No ULS / SLS / PMM calculation equations changed.
- No flexure/shear/torsion/V+T design equations changed.
- No report data model changes beyond restored stored-result visibility.
- No project input tables are deleted.
- No solver rerun is triggered by Results or save/load restore.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/io/project_io.py concrete_pmm_pro/core/reinforcement_system.py concrete_pmm_pro/ui/section_builder.py concrete_pmm_pro/state/dirty_state.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_state_persist1_reinforcement_and_results.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_analysis_modes.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_uls_girder_compact_workspace.py
```

Targeted tests passed: 150 passed.

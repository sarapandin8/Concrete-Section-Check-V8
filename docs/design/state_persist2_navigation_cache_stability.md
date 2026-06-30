### STATE.PERSIST2 — Stabilize Steel-System Defaults and ULS Cache Across Navigation

Fixed the remaining navigation-state issue where returning to Section Builder could materialize steel-system keys and change the project input hash, causing Beam/Girder ULS cached results to look stale when returning to Analysis.

#### Root cause
Beam/Girder ULS cache entries are keyed by `project_input_hash(st.session_state)`. Some section steel-system flags were materialized only when Section Builder rendered:
- `section_has_ordinary_rebar`
- `section_has_prestressing_steel`
- `reinforcement_flags_preset_key`
- Section Builder mirror keys

When a user calculated ULS results, then visited Section Builder, the newly materialized keys changed the raw project hash even though the effective engineering inputs had not changed. Analysis then treated prior results as not calculated for current inputs.

In addition, legacy sessions/projects could still carry the old `ordinary rebar = False` Beam/Girder default, so the Section Builder checkbox could remain unchecked even though the new Bridge Beam/Girder default should be ON.

#### What changed
- Normalize steel-system flags inside dirty-state input hashing:
  - hash effective `ordinary_rebar_enabled(...)`
  - hash effective `prestressing_steel_enabled(...)`
- Remove redundant `reinforcement_flags_preset_key` from the Section input hash so a page-navigation marker does not invalidate analysis caches.
- Add navigation regression test proving project hash is stable before/after Section Builder materializes default steel-system flags.
- Add Section Builder legacy-upgrade behavior:
  - Bridge Beam/Girder presets that default ordinary rebar ON will auto-upgrade legacy false values unless the user explicitly overrides the steel-system switches.
- Add explicit user override marker for steel-system switches:
  - user can still intentionally turn ordinary rebar or prestress off
  - the app will preserve that explicit override
- Save the steel-system user-override marker into project metadata.
- Keep Beam/Girder ordinary rebar / longitudinal Al default enabled.
- Keep prestressed/precast girder prestressing default enabled.

#### Not changed
- No ULS/SLS/PMM calculation equations changed.
- No flexure/shear/torsion/V+T equations changed.
- No result dataframe schema changed.
- No rebar/prestress rows are deleted when a steel system is disabled.
- Results remains read-only.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/io/project_io.py concrete_pmm_pro/core/reinforcement_system.py concrete_pmm_pro/ui/section_builder.py concrete_pmm_pro/state/dirty_state.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_state_persist2_navigation_cache_stability.py tests/test_state_persist1_reinforcement_and_results.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_analysis_modes.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_uls_girder_compact_workspace.py
```

Targeted tests passed: 153 passed.

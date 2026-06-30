### STATE.PERSIST3 — Dedicated Beam/Girder ULS Cache Signature

Fixed the remaining issue where Beam/Girder ULS results disappeared after navigating Analysis → Section Builder → Analysis.

#### Root cause
Beam/Girder ULS result entries were keyed by the full `project_input_hash(st.session_state)`. Even after normalizing steel-system flags in dirty-state, the full project hash was still too broad for the Beam/Girder ULS manual calculation cache. Section Builder can materialize UI/source markers and metadata that are not the actual ULS engineering model, causing the cached entries to miss when the user returns to Analysis.

#### What changed
- Added a dedicated Beam/Girder ULS cache signature:
  - `_BEAM_ULS_INPUT_HASH_KIND = "beam_girder_uls_v2"`
  - `_beam_uls_cache_input_hash(...)`
- Beam/Girder ULS manual results now use this dedicated signature instead of the full project hash.
- Signature includes only ULS-relevant engineering inputs:
  - active ULS station demand rows
  - ULS route/code basis
  - section preset/category/family/geometry/parameters
  - effective steel-system flags
  - materials
  - ordinary rebar inputs and shear reinforcement tables
  - prestress/strand/stage/loss settings relevant to girder ULS
  - analysis settings
- Signature deliberately ignores Section Builder navigation/widget mirror keys.
- Store `input_hash_kind = beam_girder_uls_v2` in Beam/Girder ULS cache entries.
- Added regression tests proving:
  - cache signature is stable before/after Section Builder materializes navigation/default keys
  - cache signature changes when an actual ULS load changes
  - Beam/Girder ULS no longer uses `project_input_hash(st.session_state)` as the manual cache key

#### Not changed
- No ULS/SLS/PMM calculation equations changed.
- No flexure/shear/torsion/V+T equations changed.
- No rebar/prestress rows are deleted.
- Results remains read-only.
- Project save/load cache serialization from STATE.PERSIST1 remains in place.
- Steel-system default/override handling from STATE.PERSIST2 remains in place.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py concrete_pmm_pro/state/dirty_state.py concrete_pmm_pro/ui/section_builder.py concrete_pmm_pro/io/project_io.py

pytest -q tests/test_state_persist3_beam_uls_cache_signature.py tests/test_state_persist2_navigation_cache_stability.py tests/test_state_persist1_reinforcement_and_results.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_analysis_modes.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_uls_girder_compact_workspace.py
```

Targeted tests passed: 156 passed.

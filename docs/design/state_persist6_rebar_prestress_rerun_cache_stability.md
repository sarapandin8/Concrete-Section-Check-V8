### STATE.PERSIST6 — Preserve ULS Cache Across Rebar/Prestress Page Reruns

Fixed the remaining Beam/Girder ULS cache invalidation caused by Rebar and Prestress subpage reruns/materialization.

#### Root cause
Streamlit reruns the app whenever the user changes navigation pages. That is normal and unavoidable. The bug was not the rerun itself; the bug was that the Beam/Girder ULS cache signature still included values that are created by rendering the Rebar/Prestress pages, not values directly edited by the engineer.

When the user opened Section Builder, Rebar, and Prestress, the app materialized derived/runtime state such as:
- `rebars`
- `rebars_valid_for_analysis`
- `rebar_input_mode`
- `prestress_elements`
- `prestress_valid_for_analysis`
- `section_properties`

Those values are parser outputs or preview/validation outputs. They should not invalidate a completed ULS result if the editable source tables did not change.

#### What changed
- Beam/Girder ULS cache signature now ignores derived Rebar/Prestress parser/runtime outputs.
- Signature now uses source-of-truth editable input tables instead:
  - `rebar_table`
  - `prestress_table`
  - `beam_girder_shear_reinforcement_table`
  - `girder_strand_layout_table`
  - `girder_prestress_force_states_table`
  - prestress system/stage/loss settings
- Missing source tables are normalized as empty lists so simply rendering Rebar/Prestress does not change the signature.
- Removed `section_properties` from the Beam/Girder ULS signature because it is a derived output of Section Builder, not a direct source input.
- Added regression tests for the exact user workflow:
  - calculate ULS
  - visit Section Builder + Rebar + Prestress
  - return to Analysis
  - cache signature remains stable
- Added regression test proving the signature still changes when the actual source rebar table changes.

#### Not changed
- Streamlit still reruns on navigation. That is normal.
- No ULS/SLS/PMM calculation equations changed.
- No flexure/shear/torsion/V+T equations changed.
- No rebar/prestress rows are deleted.
- Results remains read-only.
- Project save/load cache serialization remains in place.
- Steel-system default/override handling remains in place.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py concrete_pmm_pro/state/dirty_state.py concrete_pmm_pro/ui/section_builder.py concrete_pmm_pro/io/project_io.py

pytest -q tests/test_state_persist3_beam_uls_cache_signature.py tests/test_state_persist2_navigation_cache_stability.py tests/test_state_persist1_reinforcement_and_results.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_analysis_modes.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_uls_girder_compact_workspace.py
```

Targeted tests passed: 160 passed.

### STATE.PERSIST5 — Preserve ULS Cache After Visiting All Section Subpages

Fixed the remaining Beam/Girder ULS cache loss after navigating through all three Sections subpages: Section Builder, Rebar, and Prestress.

#### Root cause
STATE.PERSIST3/4 created a dedicated Beam/Girder ULS cache signature, but the signature still included derived parser/runtime outputs:
- `rebars`
- `rebars_valid_for_analysis`
- `rebar_input_mode`
- `prestress_elements`
- `prestress_valid_for_analysis`
- `section_properties`

Those keys are materialized when the user opens the Rebar and Prestress subpages. Visiting one subpage alone may not always change enough state to invalidate the current result, but visiting Section Builder + Rebar + Prestress materializes the full set of derived outputs. The cache signature then changes even though the editable engineering source inputs did not change, so Analysis shows the prior ULS results as NOT CALCULATED.

#### What changed
- Beam/Girder ULS cache signature now uses editable/source-of-truth inputs, not derived parser outputs.
- Removed derived runtime/parser outputs from the Beam/Girder ULS signature:
  - `rebars`
  - `rebars_valid_for_analysis`
  - `rebar_input_mode`
  - `prestress_elements`
  - `prestress_valid_for_analysis`
  - `section_properties`
- Use source tables instead:
  - `rebar_table`
  - `beam_girder_shear_reinforcement_table`
  - `prestress_table`
  - `girder_strand_layout_table`
  - `girder_prestress_force_states_table`
  - prestress system/stage/loss settings
- Normalize missing source tables as empty tables/lists so opening a subpage and materializing an unchanged empty source table does not invalidate cache.
- Added regression test proving the Beam/Girder ULS cache signature remains stable after all three Sections subpages materialize their derived outputs.
- Added regression test proving the signature still changes when the actual source rebar table changes.

#### Not changed
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

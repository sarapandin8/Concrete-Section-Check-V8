### STATE.PERSIST4 — Beam/Girder ULS Cache Signature Hang Hotfix

Hotfixed the dedicated Beam/Girder ULS cache signature introduced in STATE.PERSIST3.

#### Root cause
STATE.PERSIST3 correctly stopped using the full project hash for Beam/Girder ULS manual-cache lookup. However, the new dedicated signature still included the raw `section_geometry` object. For complex generated sections, raw geometry objects may contain heavyweight nested structures or nontrivial object internals. That made the hash step expensive/unstable enough that pressing Calculate could appear to run indefinitely before the selected result was stored.

#### What changed
- Remove raw `section_geometry` from the Beam/Girder ULS cache signature payload.
- Use source-of-truth section parameters/properties instead:
  - `section_preset_key`
  - `section_category`
  - `girder_section_family`
  - `section_parameters`
  - `section_properties`
  - composite/effective-width settings
- Add a recursion/depth guard to `_beam_uls_stable_value(...)`.
- Keep the dedicated `beam_girder_uls_v2` signature so Section Builder navigation/widget keys still do not invalidate cached ULS results.
- Add regression test proving raw `section_geometry` is not part of the Beam/Girder ULS cache signature.
- Add regression test proving the signature still changes when actual ULS load demand changes.

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

Targeted tests passed: 157 passed.

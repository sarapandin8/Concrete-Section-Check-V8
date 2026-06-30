### STATE.PERSIST7 — Source-Table Sync Before Beam/Girder ULS Hashing

Fixed the root cause behind Beam/Girder ULS results disappearing after visiting Rebar/Prestress and the apparent Flexure slowdown after the prior cache-signature milestones.

#### What actually happened
Streamlit reruns the app on navigation. That is normal. The bug was that Rebar and Prestress subpages materialize parser outputs during those reruns. Previous fixes removed some derived outputs from the Beam/Girder ULS cache signature, but Analysis still did not synchronize source tables into those parser outputs before hashing/calculation. Therefore the effective Analysis state before visiting Rebar/Prestress and after visiting them could still diverge.

This made cached ULS results miss after navigation, and users saw:
- Flexure / Shear / Torsion results return to NOT CALCULATED
- Flexure appeared slow because the app was no longer reusing the previously calculated result

#### What changed
- Analysis now synchronizes editable Rebar source table into parser outputs before Beam/Girder ULS hash/calculation:
  - `rebar_table` → `rebars`
  - validates against section geometry
  - updates `rebars_valid_for_analysis`
- Analysis now synchronizes editable Prestress source table into parser outputs before Beam/Girder ULS hash/calculation:
  - `prestress_table` → `prestress_elements`
  - validates against section geometry
  - updates `prestress_valid_for_analysis`
- Dirty-state input groups for Rebar/Prestress now track source-of-truth tables/settings, not parser outputs:
  - Rebar group uses `rebar_table`, shear reinforcement table, shear depth settings
  - Prestress group uses `prestress_table`, strand layout, force-state, system/stage/loss settings
- Added regression tests proving:
  - dirty-state Rebar/Prestress groups exclude parser outputs
  - Analysis calls source-table sync before Beam/Girder ULS review
  - rebar source table sync materializes active Rebar objects
  - Beam/Girder ULS cache hash remains stable before/after source sync for unchanged source tables

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

pytest -q tests/test_state_persist7_analysis_source_sync.py tests/test_state_persist3_beam_uls_cache_signature.py tests/test_state_persist2_navigation_cache_stability.py tests/test_state_persist1_reinforcement_and_results.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_analysis_modes.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_uls_girder_compact_workspace.py
```

Targeted tests passed: 164 passed.

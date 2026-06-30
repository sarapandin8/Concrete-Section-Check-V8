### UI.PLOT8.2 — Beam/Girder ULS Combined V+T Diagram and Action Wording Polish

Polished the static Beam/Girder ULS Combined Shear + Torsion result presentation.

#### What changed
- Shortened Combined V+T diagram legend labels:
  - `Stress interaction D/C` → `Stress D/C`
  - `Transverse reinforcement D/C` → `Transverse D/C`
  - `Longitudinal Al D/C` → `Long. Al D/C`
  - `Limit D/C = 1.0` → `Limit = 1.0`
  - `Governing V+T check` → `Gov. V+T`
- Shortened the governing V+T annotation from status-heavy text to `Gov. D/C ...`.
- Moved high-utilization governing V+T annotation below the point to avoid collision with the D/C = 1.0 limit line.
- Changed Combined Interaction card wording to show `SOURCE BLOCKED` when separate shear/torsion source gate blocks acceptance.
- Improved Compact ULS table Required Action for Shear + Torsion blocked/data-required states.

#### Not changed
- No shear calculation changes.
- No torsion calculation changes.
- No combined V+T interaction equations changed.
- No Beam/Girder ULS result dataframes changed.
- No solver, load routing, report data model, project schema, or save/load contract changed.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_beam_uls_vt_plot_action_polish.py tests/test_beam_uls_static_plot_size_hotfix.py tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.

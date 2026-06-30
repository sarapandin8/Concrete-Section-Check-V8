### RESULTS.WS1.3 / UI.PLOT8.1 — Compact Static Beam/Girder ULS Diagram Size

Fixed oversized static Beam/Girder ULS diagrams introduced by the PlotlyChart dynamic-import hotfix.

#### Root cause
The previous static PNG fallback used full-container image scaling. The Plotly export had a relatively tall aspect ratio, so Streamlit scaled it to the full dashboard width and made the graph look abnormally large.

#### What changed
- Added compact static Beam/Girder ULS figure dimensions:
  - width = 980 px
  - height = 460 px
- Rendered static Beam/Girder ULS images at fixed review width instead of full-container width.
- Added compact static layout overrides for margins, title font, axis font, legend font, and legend placement.
- Kept the static PNG workaround for Streamlit Cloud PlotlyChart dynamic-import failures.
- Added regression tests to prevent full-container/poster scaling from returning.

#### Not changed
- No flexure/shear/torsion/V+T calculations changed.
- No Beam/Girder ULS result cards, compact table, audit tables, or dataframes changed.
- No solver, load routing, report data model, project schema, or save/load contract changed.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_beam_uls_static_plot_size_hotfix.py tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.

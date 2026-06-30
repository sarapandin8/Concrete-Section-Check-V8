### RESULTS.WS1.2 / UI.PLOT8 — Static Beam/Girder ULS Diagram Rendering Hotfix

Mitigated Streamlit Cloud frontend `PlotlyChart` dynamic-import failures in the Beam/Girder ULS workspace.

#### Root cause
The calculation completed successfully, but Streamlit Cloud failed to fetch the lazily imported frontend PlotlyChart JavaScript chunk when the Beam/Girder ULS diagram was rendered. This is a browser/CDN/frontend chunk-load issue, not a Python solver failure.

#### What changed
- Added a Beam/Girder ULS static Plotly rendering helper.
- Rendered Beam/Girder ULS diagrams as static PNG images using Plotly/Kaleido instead of `st.plotly_chart`.
- Applied the static rendering path to:
  - Flexure diagram
  - Shear diagram
  - Torsion diagram
  - Shear + Torsion utilization diagram
- Kept result cards, compact ULS table, audit tables, and calculated values unchanged.
- Added a safe message if static chart export is not available in the environment.

#### Not changed
- No flexure/shear/torsion/V+T calculations changed.
- No Beam/Girder ULS dataframes changed.
- No solver, load routing, report data model, project schema, or save/load contract changed.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.

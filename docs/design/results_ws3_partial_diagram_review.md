### RESULTS.WS3 — Partial Result State and Stored Beam/Girder ULS Diagram Review

Improved Results workspace safety messaging for partial result sets and added read-only stored Beam/Girder ULS diagram review.

#### What changed
- Executive result state now distinguishes partial Beam/Girder ULS result sets:
  - No stored result set
  - Partial results available
  - Design review required
  - Stored results need review
  - Full stored results available
- Governing Results Dashboard wording now states that it lists calculated checks only.
- Diagram availability now counts diagrams generated from cached Beam/Girder ULS result dataframes, not only stored Plotly figure objects.
- Diagram Review now supports read-only static diagrams from cached Beam/Girder ULS results:
  - Flexure
  - Shear
  - Torsion
  - Shear + Torsion
- Diagram Review continues to support stored PMM figures when available.
- Diagram rendering remains static PNG to avoid Streamlit Cloud PlotlyChart dynamic-import issues.
- Results remains read-only and does not rerun solvers.

#### Not changed
- No Beam/Girder ULS calculation logic.
- No flexure/shear/torsion/V+T equations.
- No stored dataframe schema.
- No solver, load routing, report data model, project schema, or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_results_ws3_partial_diagram_review.py tests/test_results_ws2_beam_uls_dashboard.py tests/test_beam_uls_vt_plot_action_polish.py tests/test_beam_uls_static_plot_size_hotfix.py tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.

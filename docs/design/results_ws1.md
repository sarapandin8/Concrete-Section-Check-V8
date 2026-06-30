### RESULTS.WS1 — Stored-Results Executive Dashboard Foundation

Built the Results workspace into a read-only executive engineering dashboard.

#### What changed
- Replaced the Results placeholder with a stored-results dashboard.
- Added Results Availability cards:
  - ULS stored results
  - SLS stored results
  - Diagram review
  - Report handoff
- Added Governing Results Dashboard:
  - executive status card
  - consolidated governing table for stored PMM / Beam-Girder ULS / SLS results
  - status pills
  - governing case/station/demand/capacity/utilization/source columns
- Added Stored Result Modules drill-down:
  - cached Beam/Girder ULS result dataframes
  - stored SLS stress summary
- Added Diagram Review for stored Plotly figures:
  - PMM Mux-Muy slice
  - PMM 3D interaction
- Added Result traceability / cache state expander.

#### Results workspace behavior
- Results reads stored outputs only.
- Opening Results does not rerun PMM, ULS, or SLS.
- Solver, report, project schema, load routing, and analysis equations are unchanged.

#### Validation run
```bash
python -m py_compile app.py
pytest -q tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py
```

Targeted tests passed.

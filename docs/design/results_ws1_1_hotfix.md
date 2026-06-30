### RESULTS.WS1.1 — Hotfix Results Traceability AttributeError

Fixed a Results workspace crash in the traceability/cache-state expander.

#### Root cause
`_render_results_traceability()` called a non-existent `AnalysisModeSettings.from_session_state(state)` factory. `AnalysisModeSettings` is a Pydantic model and does not expose that classmethod, so opening Results → traceability raised `AttributeError`.

#### What changed
- Replaced the invalid `AnalysisModeSettings.from_session_state(state)` call with the existing app chrome helper `_analysis_mode_from_session_for_chrome()`.
- Added regression tests to ensure the invalid factory call does not return.
- Kept Results as a read-only stored-results dashboard.

#### Not changed
- No Results dashboard data logic changed except the traceability workflow label source.
- No solver / PMM / ULS / SLS equations changed.
- No load routing, report data model, project schema, or save/load contract changed.

#### Validation run
```bash
python -m py_compile app.py
pytest -q tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py
```

Targeted tests passed.

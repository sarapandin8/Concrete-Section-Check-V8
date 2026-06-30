### UI.COMMERCIAL4.8 — Beam/Girder ULS Decision Workspace + Command Workflow Polish

Polished **Analysis → ULS Strength** for Beam/Girder workflows into a clearer commercial decision workspace.

#### What changed
- Shortened the Beam/Girder ULS summary text and moved detailed assumptions into a collapsed scope expander.
- Replaced the full-width Calculate button with a command-style action panel:
  - selected ULS check
  - current calculation state
  - primary action button
- Replaced the heavy warning alert with a softer engineering notice.
- Upgraded the Compact ULS Check Table with:
  - status pills
  - clearer technical notes
  - required-action column
  - cleaner commercial table styling
- Replaced the uncalculated workspace placeholder with a premium empty-state card.
- Kept existing lazy calculation behavior and widget keys.

#### Not changed
- No solver equations.
- No flexure, shear, torsion, or combined V+T calculations.
- No data model, project schema, save/load, report, or widget-key contract changes.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_analysis_modes.py tests/test_app_commercial_tabs.py
```

Targeted tests passed.

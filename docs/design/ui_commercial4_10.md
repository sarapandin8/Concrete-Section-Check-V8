### UI.COMMERCIAL4.10 — Compact Loads Workspace Summary and Stage Cards

Polished the Loads workspace card scale after the commercial blue-accent redesign.

#### What changed
- Replaced large `st.metric` hero-style cards in Beam/Girder Loads with compact load dashboard cards.
- Reduced font size, padding, and visual weight for:
  - Beam/Girder / ULS + SLS / Preview selectable / Future cards
  - Span / Girder spacing / Number of girders / Tributary width cards
  - Transfer / Construction / Service stage routing cards
- Applied the same compact style to Building Beam/Girder load context cards for consistency.
- Kept the blue-accent commercial language while making input tables and editable controls visually dominant.

#### Not changed
- No load calculation changes.
- No auto-load component equations.
- No SLS stage routing logic changes.
- No ULS/SLS data schema, save/load contract, or analysis solver changes.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/ui/loads_page.py
pytest -q tests/test_app_commercial_tabs.py tests/test_loads.py
```

Targeted tests passed.

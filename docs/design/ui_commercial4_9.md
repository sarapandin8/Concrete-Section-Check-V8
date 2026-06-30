### UI.COMMERCIAL4.9 — Beam/Girder ULS Command State and Flexure Plot Label Polish

Polished the Beam/Girder ULS command workflow after UI.COMMERCIAL4.8.

#### What changed
- Removed the large post-calculation success strip from the Beam/Girder ULS workflow.
- Updated the command panel with the current selected-check calculation state in the same rerun using a status placeholder.
- Kept the stored `calculated_at` timestamp available through the command-panel status text.
- Refined Compact ULS check table action wording for clearer product-style action language.
- Reduced the governing flexure D/C plot label text size.
- Shortened the flexure graph label from `PASS · D/C ...` to `D/C ...`.
- Moved the governing flexure label inside the plot area and disabled axis clipping to avoid cropped text.

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

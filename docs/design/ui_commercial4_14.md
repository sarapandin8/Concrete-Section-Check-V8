### UI.COMMERCIAL4.14 — Shared Section Preview Canvas QA Polish

Polished the shared Plotly section preview canvas used by Section Builder, Rebar, and Prestress pages.

#### What changed
- Hardened the shared preview legend after the undefined-label hotfix:
  - blank legend title remains forced
  - invisible title font added as a second renderer guard
  - compact legend font, border, and background applied
- Refined shared preview canvas styling:
  - slightly safer top/bottom margins
  - consistent light grid colors
  - clearer zero-line colors
  - smaller axis fonts
  - clean hover label styling
- Added regression tests across:
  - all section presets from `section_presets.json`
  - geometry-only preview
  - rebar preview
  - prestress preview
  - combined rebar + prestress preview

#### Not changed
- No geometry generation logic.
- No section property calculation.
- No rebar/prestress data model.
- No solver, SLS, ULS, PMM, report, or project schema logic.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/visualization/section_plot.py
pytest -q tests/test_section_preview_holes.py tests/test_section_preview_legend.py tests/test_section_preview_canvas_qa.py tests/test_rebar_layout.py tests/test_prestress.py
```

Targeted tests passed.

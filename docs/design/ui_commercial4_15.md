### UI.COMMERCIAL4.15 — Root Fix for Section Preview Undefined Plot Title

Fixed the remaining `undefined` text shown in the shared section preview canvas.

#### Root cause
The previous fix correctly blanked the Plotly legend title, but the screenshot showed the stray text at the top-left of the Plotly SVG. That position corresponds to the top-level Plotly figure title, not the legend title. In this Streamlit/Plotly renderer combination, an omitted top-level `layout.title.text` can render as a literal `undefined` text node.

#### What changed
- Added an explicit blank top-level Plotly figure title in the shared `create_section_preview` helper.
- Kept the legend title blank as a separate guard.
- Made the forced blank figure title effectively invisible for renderer versions that still allocate title space.
- Expanded regression tests to assert both:
  - `fig.layout.title.text == ""`
  - `fig.layout.legend.title.text == ""`
- Regression coverage remains shared across:
  - all section presets from `section_presets.json`
  - Section Builder geometry preview
  - Rebar preview
  - Prestress preview
  - combined rebar + prestress preview

#### Not changed
- No geometry generation logic.
- No section property calculations.
- No rebar/prestress models.
- No solver, SLS, ULS, PMM, report, or project schema logic.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/visualization/section_plot.py
pytest -q tests/test_section_preview_holes.py tests/test_section_preview_legend.py tests/test_section_preview_canvas_qa.py tests/test_rebar_layout.py tests/test_prestress.py
```

Targeted tests passed.

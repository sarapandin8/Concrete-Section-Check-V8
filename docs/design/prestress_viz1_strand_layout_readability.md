### PRESTRESS.VIZ1 — Clean Railway U-Girder Strand Layout Preview

Improved the Prestress → Cross-section layout preview for dense Railway U-Girder strand layouts.

#### Problem
The previous plot looked cluttered for 72-strand Railway U-Girder layouts:
- each strand was drawn twice: once as a Plotly shape circle and again as a marker trace
- dense row labels were tied to actual y-coordinates, so they overlapped near the strand block and clipped at the right edge
- the top-left plot title could display as `undefined`
- debonding/drawing symbols were too visually heavy for the inspection view

#### What changed
- Replaced per-strand shape circles with a single marker-layer approach
- Reduced strand marker size and line thickness for dense layouts
- Kept Bonded / Debonded legend traces
- Moved row information into a compact right-side `Strand row summary` panel
- Removed y-coordinate-tied row labels and leader lines that caused overlapping/clipping
- Added explicit plot title: `Prestress strand cross-section layout`
- Made drawing debond symbols smaller and lighter
- Kept the true section geometry aspect ratio and actual strand coordinates

#### Not changed
- No prestress calculation logic changed
- No debonding logic changed
- No strand layout table logic changed
- No ULS/SLS/PMM equations changed
- No rebar/prestress rows are deleted
- Results remains read-only

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/prestress_page.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_prestress_viz1_strand_layout_readability.py tests/test_state_persist7_analysis_source_sync.py tests/test_state_persist3_beam_uls_cache_signature.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_analysis_modes.py
```

Targeted tests passed: 40 passed.

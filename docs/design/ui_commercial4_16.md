### UI.COMMERCIAL4.16 — Rebar Auto Perimeter Default Offset Update

Updated the Rebar workspace Auto perimeter layout default bar-center offset.

#### What changed
- Changed `Bar center offset (mm)` default from 75 mm to 50 mm.
- Updated the Auto perimeter layout guidance text from `75 mm to bar center` to `50 mm to bar center`.
- Added a regression test to guard the 50 mm default in the Rebar page source.

#### Not changed
- No perimeter layout generation algorithm changes.
- No manual rebar table behavior changes.
- No rebar material routing changes.
- No section geometry, preview, solver, SLS, ULS, PMM, report, or project schema logic changes.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/ui/rebar_page.py
pytest -q tests/test_rebar_auto_perimeter_apply_hotfix.py tests/test_rebar_layout.py tests/test_rebar_inclusion_visual_regression.py
```

Targeted tests passed.

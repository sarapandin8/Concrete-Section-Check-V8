### UI.COMMERCIAL4.11 — Materials Workspace Commercial Library Dashboard

Polished the Materials workspace after the commercial blue-accent redesign.

#### What changed
- Added a Materials workspace commercial page header.
- Added a compact material library dashboard at the top of the page.
- Converted concrete/rebar/prestress guidance bars into lighter compact guidance cards.
- Reworked library sections with commercial section bars.
- Converted the prestress catalog product action into a command-style panel.
- Moved selected prestress product details into a collapsed audit expander.
- Converted Material Library Summary into compact dashboard cards.
- Moved rebar and prestress summary audit tables into collapsed audit expanders.

#### Not changed
- No material data model changes.
- No concrete Ec/fc/beta1 formula changes.
- No rebar material routing changes.
- No prestress force/loss logic changes.
- No section material assignment logic changes.
- No save/load schema changes.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/ui/materials_page.py
pytest -q tests/test_material_routing1_source_of_truth.py tests/test_materials.py tests/test_app_commercial_tabs.py
```

Targeted tests passed.

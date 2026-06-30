# SECTION.SLAB.BRIDGE1 — Slab Bridge Preset

## Scope

Add a new `Slab Bridge` section preset for the Bridge Beam/Girder workflow.
The section is generated from the user-provided drawing dimensions:

- total width `B = 5100 mm`
- half widths `B/2 = 2550 mm` each side of bridge centerline
- edge depth `He = 400 mm` at both outside edges
- centerline depth `Hc = 450 mm`

## Geometry basis

The preset is modeled as a solid five-point polygon:

1. flat bottom soffit,
2. vertical outside edges,
3. linearly crowned top surface from each edge to the centerline.

No bottom corner chamfer, fillet, wearing surface, curb, barrier, void, or separate deck/topping component is inferred because those features are not dimensioned in the provided drawing.

## Product / workflow decision

The preset is categorized as `General / Non-composite Girder`, making it available in the Bridge Beam/Girder section-preset list without activating precast-composite deck/topping metadata. This is intentional: a slab bridge is a solid gross section in this milestone, not a composite-girder workflow.

## Changed files

- `data/section_presets.json`
- `concrete_pmm_pro/geometry/generators.py`
- `tests/test_slab_bridge_preset.py`
- `docs/design/section_slab_bridge1.md`
- `README.md`

## QA gate

Targeted validation confirms:

- the preset loads from JSON,
- it is available to the Bridge Beam/Girder workflow,
- generated geometry is valid,
- default vertices match the drawing dimensions,
- gross area matches independent rectangle-plus-triangle calculation,
- dimension guides expose `B`, `B/2 L`, `B/2 R`, `Hc`, `He L`, `He R`, and `CL`,
- invalid geometry with edge depth greater than center depth is rejected.

## Out of scope

This milestone does **not** change PMM, shear, torsion, service-stress, deflection/camber, prestress, rebar, report, project schema, or composite-section solver logic.

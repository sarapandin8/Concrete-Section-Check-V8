# CROSSBEAM.PTLOSS3B1C — Construction/Support Source Relocation + Segment Elevation Overlay

This milestone relocates the Portal Frame Crossbeam member-level construction type and Column / support-line layout editor from Prestress Loss → Elastic Shortening to Sections → Section Builder, while preserving one canonical session/Project JSON source for downstream Segment Layout and Prestress Loss use.

Key changes:
- New practical default column seed: C1 at s=0 and C2 at s=L; Height 10 m; Rectangular equal chamfer; Btrans=2000 mm; Blong=2000 mm; chamfer=200 mm; f'c=35 MPa. Dormant circular Diameter D defaults to 2000 mm.
- Precast Segmental default specified minimum joint/closure strength at stressing = 50 MPa, editable.
- Section Builder now owns `Crossbeam construction type` and Column/support-line geometry editing.
- Elastic Shortening consumes the same construction/support source read-only and retains stressing-strength, temporary-support, and stressing-pair-sequence controls.
- Column preview remains compact and is constrained to a medium-width card; preview labels explicitly show Btrans normal to the Crossbeam axis and Blong along the Crossbeam axis.
- Segment Layout longitudinal elevation overlays real support widths: Blong for rectangular columns and D for circular columns. Vertical column height is schematic/not to scale in this review figure.
- Scaling Crossbeam member length with the existing Scale policy also scales column/support centerline stations.

No Friction/Wobble, Anchorage Set, Elastic Shortening formula, f_cgp, Primary/Secondary Prestress, contact/lift-off, Pe/Pe_eff, PMM, SLS/ULS, Rebar, or Report solver equations are changed.

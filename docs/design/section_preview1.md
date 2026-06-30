# SECTION.PREVIEW1 — Rectangular Chamfered dimension-guide clarity

## Scope
- Fix the Live Section Preview dimension-guide layout for `Rectangular Chamfered · Basic Solid`.
- Keep section geometry, section properties, and all analysis solvers unchanged.

## Root cause
The overall `H` dimension guide and the local chamfer `cy` guide were both drawn at the same right-side x-offset. With nonzero `chamfer_y_mm`, the two vertical guides visually merged, making the displayed `H` guide appear incorrect even though the stored value remained correct.

## Change
- Rebuild `rectangular_chamfered_dimensions()` with explicit guide placement.
- Keep `H` spanning the full section height.
- Push the global `H` guide farther outward whenever a local `cy` guide is active.
- Keep `cy` on the inner right offset for local chamfer indication.

## Out of scope
- No geometry-generator equation changes.
- No PMM / shear / torsion / SLS / report changes.

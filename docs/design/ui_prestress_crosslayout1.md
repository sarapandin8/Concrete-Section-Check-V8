# UI.PRESTRESS.CROSSLAYOUT1 — Cross-section Layout Scale and Padding Polish

## Scope

This milestone improves the readability of the **Prestress → Cross-section layout** plot used by the girder strand/debonding workflow.

The change is intentionally limited to plot presentation. It does not modify strand coordinates, section geometry, debonding metadata, Pe/force-state logic, prestress losses, PMM, SLS, shear/torsion, reports, or project schema.

## Changes

- Increased the cross-section layout plot height from 410 px to 560 px.
- Kept equal aspect ratio so the concrete geometry and strand positions remain true-scale.
- Reduced data-range expansion caused by row labels.
- Moved row labels into the right paper margin rather than extending the x-axis range.
- Consolidated left/right symmetric row labels by elevation so Railway U-Girder rows display as Row 1 through Row 5 instead of overlapping L/R labels.
- Added explicit x/y viewport padding around the concrete outline.
- Moved the legend to a horizontal top legend to avoid consuming right-side plot space.

## Railway U-Girder verification

For the default 5500 mm × 1600 mm Railway U-Girder:

- x-axis range is held near the concrete outline plus inspection padding: `-3190 mm` to `+3190 mm`.
- y-axis range is held near the concrete outline plus inspection padding: `-1056 mm` to `+1056 mm`.
- row annotations are placed in paper coordinates and no longer force the plotted section to shrink.
- strand coordinates remain unchanged.

## Out of scope

- No strand spacing or strand count change.
- No debonding analysis change.
- No solver or section-property kernel change.
- No Section Builder dimension guide change.

# UI.PLOT3 — Railway U-Girder Service Multi-Fiber Plot Label Cleanup

## Purpose

Polish the Railway U-Girder service-stage multi-fiber SLS stress plot after UI.PLOT1/UI.PLOT2.  The service plot has more series than transfer/lifting/construction plots, so the shared plot layout could crowd the x-axis label and right-side web/slab limit labels.

## Scope

Display-only UI changes:

- increase Railway U-Girder service multi-fiber plot height,
- increase bottom and right plot margins,
- move the service legend lower and give it more space,
- shorten limit trace names in the legend while preserving full labels in annotations/hover text,
- move limit labels just outside the plot area using paper coordinates,
- stagger limit label y-shifts to reduce overlap,
- render SLS actual-vs-limit cards with comparison symbols such as `3.791 MPa > 3.354 MPa` when appropriate.

## Non-scope

No solver or engineering equation changes:

- no SLS stress equation changes,
- no Pe(x), debonding, or prestress logic changes,
- no material strength routing changes,
- no limit formula changes,
- no load table or stage routing changes,
- no ULS changes.

## QA Notes

Regression tests check that:

- the Railway U-Girder service plot uses larger margins/height,
- limit labels are outside the plotting area,
- shortened legend names are used for compression limits,
- actual-vs-limit cards show comparison symbols instead of an ambiguous slash.

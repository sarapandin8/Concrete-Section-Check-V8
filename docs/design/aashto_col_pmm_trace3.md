# AASHTO.COL.PMM.TRACE3 — PMM chart legend clearance

## Purpose
The TRACE2 PMM Visual Review made AASHTO code-basis text compact, but the initial Plotly render could still overlap the x-axis title with the horizontal legend until the user clicked Auto scale.

## Change
- Reserve a larger bottom margin on the PMM Mux-Muy slice chart.
- Move the horizontal legend further below the plotting area.
- Set an explicit PMM slice chart height for first-render stability.
- Enable axis automargin and title standoff to keep the x-axis title clear of the legend.
- Hide technical helper traces from the legend while keeping them visible in the plot and available in hover/trace data:
  - Raw Pu slice points
  - Capacity ray

## Scope
This is a visualization-only correction. It does not change PMM capacity, D/C, AASHTO routing, phi factors, or demand/capacity calculations.

## Expected behavior
The PMM slice chart should render cleanly on first load without requiring the user to click Plotly Auto scale to separate the legend, x-axis title, and plot area.

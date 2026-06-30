# UI.PLOT5 — Global Plot Readability Polish

## Purpose
Improve plot text readability across Concrete Section Pro without changing any engineering calculations.

## Scope
- Apply a global Plotly readability layer when figures are rendered with `st.plotly_chart`.
- Strengthen figure font color, tick labels, axis titles, legend text, annotation text, hover labels, grid contrast, and 3D scene axis labels.
- Cover plots in Analysis, Sections, Rebar, Prestress, Reports, and future pages because the patch is installed once at app startup.

## Non-scope
- No solver changes.
- No result dataframe changes.
- No trace coordinate changes.
- No widget key changes.
- No layout/page routing changes.
- No project schema changes.

## Implementation note
The helper `concrete_pmm_pro.visualization.plot_readability.apply_global_plot_readability()` is called by a one-time wrapper around `st.plotly_chart`. It only updates Plotly layout presentation properties.

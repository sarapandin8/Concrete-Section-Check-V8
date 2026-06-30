# UI.PLOT7 — Dashed-Line Legend Visibility Polish

## Purpose

Improve readability of dashed engineering limit/capacity traces in Plotly legends. Before this milestone, traces such as `φVn`, `-φVn`, `φVc`, compression limits, tension limits, and torsion thresholds could appear as very short legend samples, making dashed traces look almost solid.

## Scope

This is a presentation-only global Plotly readability layer.

Implemented changes:

- Increase Plotly legend symbol swatch width through the global plot readability wrapper.
- Increase horizontal legend entry width so dashed samples have enough room to show the dash pattern.
- Enforce a minimum line width for non-solid dashed line traces to improve visibility in the plot and legend.
- Preserve trace coordinates, names, visibility, calculated values, and solver outputs.

## Affected figures

The change is global for figures rendered through `st.plotly_chart`, including SLS stress diagrams, ULS shear/torsion diagrams, PMM/interaction figures, section/rebar/prestress previews, and report/QA Plotly previews.

## Non-goals

No engineering calculations were changed:

- no shear equation changes,
- no torsion equation changes,
- no SLS stress equation changes,
- no capacity/result dataframe changes,
- no widget key or project schema changes.

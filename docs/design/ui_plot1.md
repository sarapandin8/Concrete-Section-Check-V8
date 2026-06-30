# UI.PLOT1 — Engineering Stress Diagram Plot Style

## Purpose

Improve Concrete Section Pro's SLS stress diagrams so they read like professional engineering report figures rather than default Streamlit/Plotly charts.

This milestone is display-only. It does not change any stress calculation, prestress station logic, loads, section basis, material limit formula, ULS route, data editor behavior, widget key, project schema, or geometry generator.

## Scope

Applied to:

- Beam/Girder full-length SLS stress diagrams.
- Railway U-Girder service multi-fiber SLS stress diagram.

## Visual updates

- Larger centered report-style title and subtitle.
- Clear x-axis: `Distance from left end of member (m)`.
- Clear y-axis: `Stress (MPa) — compression negative / tension positive`.
- Dark blue top-fiber stress curve and light-blue bottom-fiber stress curve.
- Dashed red compression-limit line.
- Dashed pink tension-limit line.
- Visible dotted 0 MPa reference line.
- Open-circle governing markers for tension/compression.
- Bottom horizontal legend inside a light bordered box.
- Framed axes with light engineering grid lines.

## Guardrails

The following were deliberately not changed:

- SLS stress equations.
- Prestress `Pe(x)` and debonding participation logic.
- Load tables and stage load routing.
- Concrete stress-limit equations.
- Railway U-Girder web/slab material routing.
- ULS flexure, shear, torsion, V+T, development, or anchorage logic.
- Report certification wording.

## QA

Regression tests check that the plot style helper exists, governing markers remain visible, compression/tension limit lines are explicit, and legacy SLS diagram strings remain preserved for compatibility.

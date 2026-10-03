# IGIRDER.ULS6F — Torsion Full-Span Capacity Trace Closeout

## Scope

This milestone is a display/QA closeout for the accepted IGIRDER.ULS6E standalone Precast I-Girder torsion solver. It fixes a chart-assembly defect where a synthetic `DIAGRAM BOUNDARY` row at the same x-coordinate as a physical support-face station could insert a `NaN` `phiTn` value into the Plotly series and visually break the red dashed `±phiTn` line even though the physical station had a valid finite torsion capacity.

No AASHTO torsion equation, reinforcement source, coverage gate, result version, or stored engineering result is changed.

## 1. Physical station takes precedence at identical Case/x

The Torsion chart now coalesces duplicate `(Case, x)` plot rows before drawing capacity/reference traces.

Priority is:

1. physical engineering station with a finite result;
2. synthetic diagram-boundary/reference row only when no physical finite result exists.

A threshold-only diagram row can therefore no longer interrupt a valid physical `phiTn` result at `x=0` or `x=L`.

## 2. Full-span `±phiTn` trace

When every design-required station is covered by a capacity-ready torsion zone, the plotted `+phiTn` and `-phiTn` series use one finite row per physical analysis station over the active member domain. Zone changes may change the capacity value, but they do not create artificial chart gaps.

The plot remains faithful to the stored torsion audit dataframe; no interpolation or fabricated capacity is introduced between not-ready physical stations.

## 3. Real source gaps remain visible

If a physical station is genuinely not capacity-ready (for example, an uncovered torsion-required zone), its `phiTn` remains `NaN` and the chart intentionally shows a gap. The ULS6E coverage gate remains the source of truth for that engineering deficiency.

ULS6F only removes false gaps caused by duplicate synthetic boundary rows.

## 4. Result/cache ownership

Stored result versions remain unchanged:

- Torsion: `IGIRDER.ULS6E.torsion-coverage-detailing-closeout`
- Shear + Torsion dependency: `IGIRDER.ULS6E.combined-vt-longitudinal-pending`

This is intentional because ULS6F changes presentation/trace assembly only and must not stale already accepted Torsion, Shear, Flexure, or Interface Shear calculations.

## 5. Regression contract

Dedicated tests verify that:

- a finite physical `phiTn` at `x=0` is not broken by a threshold-only synthetic boundary row at the same x;
- a fully capacity-ready 0–L station grid produces a unique, finite full-span `±phiTn` series;
- real not-ready physical stations still retain a `NaN` gap rather than being silently bridged.

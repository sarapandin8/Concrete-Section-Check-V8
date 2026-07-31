# CROSSBEAM.SLS1B1A — Explicit Signed-Stress Display Polish

## Purpose

Make tensile stress unmistakable in the compact Crossbeam SLS result table by displaying an explicit leading plus sign for positive stress values.

## Display convention

- Tension is displayed with `+`, for example `+6.789 MPa`.
- Compression is displayed with a true minus sign, for example `−6.789 MPa`.
- Exact zero is displayed as `0.000 MPa` to avoid implying either tension or compression.
- Governing concrete-stress actual and limit values use the same signed format.
- The Precast Segmental joint row now reads, for example, `+6.789 / ≤ −0.700 MPa`.

## Engineering boundary

This is display-only polish. It does not change:

- At Transfer or At Service stress calculations;
- ACI 318-19 stress limits;
- the project-specific `fjoint ≤ −0.70 MPa` joint criterion;
- Precast Segmental versus Cast-in-Place routing;
- source loads, Project JSON, or any non-Crossbeam workflow.

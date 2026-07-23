# CROSSBEAM.PTLOSS3B1D — Support Geometry QA, Column Axis Lock & Segment-Layout State Reliability

This milestone starts from the accepted `CROSSBEAM.PTLOSS3B1C` baseline and remains source-model/UI/QA only. It does not release Primary Prestress, Secondary Prestress, contact analysis, source-derived `f_cgp`, Time-Dependent Losses, or `Pe/Pe_eff`.

## Scope

- Hardens the Crossbeam Segment Layout editor with callback-based first-patch persistence so a single edit is committed immediately instead of being overwritten by a stale dataframe rerun.
- Treats `Section ID` as the only editable section assignment source. `Section name`, `Role`, and `Preset family` are regenerated from the Project Section Definition Library and remain read-only.
- Adds explicit column inertia aliases for the future 2D `s`–vertical Portal-Frame solver:
  - `I_perp_s`: inertia about the transverse axis; this is the in-plane frame-bending inertia.
  - `I_parallel_s`: inertia about the axis parallel to `s`.
  Existing `I22/I33` fields are retained for backward compatibility.
- Adds Column/support footprint QA against Segment Layout using `Blong` for rectangular columns and `Diameter D` for circular columns. Positive overlap with Hollow segments, footprint outside the modeled member extent, or missing recognized segment overlap returns `REVIEW`.
- Moves the member-level Crossbeam Member Geometry and Construction/Support source blocks ahead of section-specific geometry/properties in Section Builder so source ownership is visually unambiguous.

## Solver boundary

No accepted Friction/Wobble, Anchorage Set, PTLOSS3 Elastic Shortening equations, PMM/SLS/ULS, rebar/report, or non-Crossbeam workflow solver equations are changed.

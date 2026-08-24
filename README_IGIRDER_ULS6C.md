# IGIRDER.ULS6C — Torsion Rebar-Source Engineering Closeout

## Scope
Closes the remaining Precast I-Girder standalone Torsion source/semantics gaps before the full Shear + Torsion concurrent longitudinal milestone.

## Engineering changes
- Physical ULS torsion load stations at `x=0` and `x=L` remain eligible design stations. Only synthetic rows explicitly tagged `DIAGRAM BOUNDARY` are plotting-only. The AASHTO shear `dv` critical-section exclusion is not reused for standalone torsion.
- The physical transverse reinforcement source remains the existing Beam/Girder provided-zone table. ULS6C adds station-qualified torsion metadata keyed to those same zones rather than creating a duplicate reinforcement layout.
- Each provided transverse zone can now explicitly state:
  - `Use for Torsion`
  - `Closed Loop`
  - `135° Hook`
  - actual `ph` centerline perimeter
  - torsion detailing note
- Shear and torsion intentionally interpret the same physical bar differently:
  - Shear: `Av/s = n_legs * Abar / s`
  - Torsion: `At/s = Abar / s` using one closed-loop leg area.
- Above the AASHTO `0.25φTcr` investigation threshold, `φTn` is blocked unless the station is covered by an active provided transverse zone that is qualified for torsion, confirmed closed, confirmed with 135° hook anchorage, and has positive `ph`.
- The existing ULS6 global closed-loop/ph source remains a backward-compatible migration fallback for older project files.

## Longitudinal reinforcement policy
- No ordinary longitudinal bar is classified as “flexure-only” or “torsion-only”.
- The existing Longitudinal Rebar table remains the single source of truth.
- Precast I-Girder flexural `Mn` continues to use active ordinary rebar at actual coordinates together with prestressing steel in the sectional strain-compatibility route.
- The future Shear + Torsion concurrent longitudinal check will reuse the same active ordinary bars plus developed prestressing steel under concurrent `Mu/Nu/Vu/Tu`; it will not create or require a second torsion-Al table.
- Corner bar/tendon confirmation remains a detailing audit input for the concurrent V+T stage.

## UI changes
- `Sections → Rebar → Transverse Rebar` now exposes a visible `Beam/Girder Torsion Reinforcement Definition` section.
- The torsion qualification table mirrors zone name, active status, x-range, and provided stirrup source from the physical transverse table, and shows read-only `At/s` alongside the editable torsion qualification fields.
- The Torsion status card gives an actionable path to `Sections → Rebar → Transverse Rebar` when the layout source is incomplete.
- Longitudinal Rebar notes now explicitly explain that Flexure and Combined V+T reuse the same active longitudinal reinforcement instead of classifying individual bars by design purpose.

## Solver policy retained
- `|Tu| > 0.25φTcr` threshold under AASHTO LRFD 5.7.2.1.
- Torsion-modified `Veff` in the 5.7.3.4.2 longitudinal-strain calculation.
- Station-dependent `εs → β → θ`.
- `Tn = 2Ao(At/s)fy cotθ λduct` for the transverse torsion component.
- Standalone Torsion above threshold does not issue final member PASS solely from transverse `φTn`; final longitudinal acceptance remains owned by the concurrent 5.7.3.6.3-1 Shear + Torsion milestone.

## Cache / persistence
- Torsion and dependent Shear + Torsion result versions are advanced to ULS6C.
- Shear, Flexure, and Interface Shear result versions are unchanged.
- Torsion zone qualification metadata is stored in project metadata and is included in the Torsion / Shear + Torsion input hash.

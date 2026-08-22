# IGIRDER.ULS6B — Torsion Visual-QA Closeout

## Scope
Presentation-only closeout of the accepted Precast I-Girder AASHTO LRFD torsion route introduced in IGIRDER.ULS6/6A. No engineering resistance equation, stored-result schema, cache version, or project JSON format is changed.

## Changes
- Shortens the torsion-chart demand legend to `Tu demand` and governing marker legend to `Gov. Tu` while retaining the on-chart governing annotation.
- Retains the ULS6A threshold hierarchy: orange dashed `±φTcr`, purple dotted `±0.25φTcr`, and red dashed `±φTn` only when the verified closed-loop torsion layout is ready.
- Makes the default Analysis torsion audit decision-focused: status/threshold/transverse/longitudinal/detailing gates, Tu, φTn, φTcr, 0.25φTcr, D/C, Veff, θ, and φ.
- Moves the full K/strain/reinforcement/shear-flow geometry/source trace to a separate `Torsion detailed engineering audit` expander and retains the full derivation in Report / QA.
- Uses the same compact decision columns for end-boundary audit values.

## Engineering policy unchanged
- Torsion investigation threshold remains `|Tu| > 0.25φTcr` under AASHTO LRFD 5.7.2.1.
- Solid I-Girder torsion continues to use torsion-modified `Veff` in the 5.7.3.4.2 longitudinal-strain route and station-dependent θ.
- `Tn = 2Ao(At/s)fy cotθ λduct` remains the transverse torsion resistance route.
- A verified fully continuous closed torsion loop and its centerline perimeter `ph` remain explicit source inputs.
- Standalone Torsion above threshold does not issue final PASS from transverse φTn alone; the concurrent longitudinal Article 5.7.3.6.3-1 acceptance remains owned by Shear + Torsion.

## Visual-QA basis
The ULS6A chart threshold-clarity state was reviewed from `torsion(2).pdf` on 2026-08-22. The threshold color/dash separation, conditional φTn subtitle/caption, and overall torsion workspace were accepted. ULS6B closes only the remaining compact-legend and audit-density polish.

## Cache / persistence
- `_IGIRDER_TORSION_RESULT_VERSION` intentionally remains `IGIRDER.ULS6.prestressed-torsion-general-procedure` because ULS6B is presentation-only.
- Shear, Flexure, Interface Shear, and stored Torsion engineering results are not invalidated by this closeout.
- No project JSON migration is required.

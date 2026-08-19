# IGIRDER.ULS2P — Flexure Performance Optimization

## Scope

Performance-only closeout for **Precast I-Girder: Bridge · Precast Composite Girder → ULS Strength → Flexure → Construction — Noncomposite**. The engineering demand/capacity semantics from IGIRDER.ULS2 are preserved.

## Changes

- Reuse the already-solved PMM point cloud to derive nominal `Mn` for the AASHTO prestressed flexure `φ = 1.00` route instead of running a second neutral-axis PMM sweep with `use_phi_factor=False`.
- Keep the existing unique physical capacity-state cache and full-span physical `φMn` station trace.
- Render the Construction Flexure chart directly with Plotly in the browser as a static-looking chart (`staticPlot=True`, mode bar hidden) instead of exporting a 1440×560, scale-2 PNG through Kaleido on every Analysis rerun.
- Keep the existing server-side static PNG renderer available for other workflows/report/export routes; this milestone changes only the I-Girder Construction Flexure Analysis chart path.
- Bump the Construction Flexure result version so persisted audits reflect the optimized route.

## Engineering invariants

No changes to:

- automatic Construction ULS line-load generation,
- `Mu(x)` equations,
- Construction-stage effective prestress force,
- strand participation/debonding state logic,
- full-span physical `φMn(x)` behavior,
- governing station, D/C, PASS/FAIL logic,
- ULS factor gate,
- Final Composite guard.

A dedicated parity test confirms nominal `Mn` from the reused point cloud matches the former two-sweep route to numerical tolerance.

## QA

- Dedicated IGIRDER.ULS2P tests: 3 PASS.
- Focused I-Girder / PMM / prestress / project IO / Loads regression: 295 PASS.
- Representative 36×60 local benchmark: one PMM sweep ≈0.215 s; nominal interpolation from the solved cloud ≈0.145 s versus ≈0.350 s for the legacy second PMM sweep, with zero nominal-capacity delta in the benchmark.
- Kaleido is not installed in the sandbox runtime, so server-side image-export timing was not benchmarked here; the production Analysis path now avoids Kaleido for this chart entirely.

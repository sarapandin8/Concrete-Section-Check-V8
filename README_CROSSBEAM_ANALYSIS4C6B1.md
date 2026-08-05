# CROSSBEAM.ANALYSIS4C6B1 — Full-span sectional ULS restoration

## Scope

- Restored every valid Crossbeam ULS station from `s = 0` through `s = L` to Flexure, Shear, Torsion, and Combined V+T sectional envelopes.
- Removed automatic PT end-zone row exclusion, governing exclusion, trace clipping, chart bands, repeated `REVIEW` labels, and engineer-length controls.
- Retained Column/support-interior trace breaks, beam-side Column Face checks, prestressed `h/2` checks where applicable, and Precast physical-joint one-sided trace breaks.
- Kept historical PT end-zone Project JSON fields readable for backward compatibility, but they no longer affect ULS results or fingerprints.
- Reframed PT anchorage local-zone/general-zone behavior as a separate project verification rather than a reason to omit sectional results.

## Engineering behavior

- End-station demand and sectional resistance remain visible and may govern when their D/C is critical.
- Sectional `PASS/FAIL` does not certify anchorage bearing, bursting, spalling/edge tension, confinement, or general-zone D-region behavior.
- No ACI Flexure, Shear, Torsion, or Combined V+T resistance equation changed.
- No strength-reduction factor, prestress-loss equation, rebar-credit rule, Column Face rule, or physical-joint rule changed.

## UI / chart behavior

- ULS charts show complete full-member traces except across support interiors and Precast physical joints.
- PT end-zone shading and repeated left/right review labels were removed.
- The shared station-routing expander now states the full-member sectional policy and the separate anchorage-design scope.

## Repo summary

Restore full-span Crossbeam sectional ULS checks and charts through both PT end stations while preserving support and physical-joint trace breaks and keeping anchorage local/general-zone design as a separate project verification.

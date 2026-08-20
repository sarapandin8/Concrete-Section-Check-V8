# IGIRDER.ULS4A — Interface Shear Full-Span & Audit Clarity Closeout

This milestone closes the visual/audit QA items found after the first AASHTO 5.7.4 girder–deck interface-shear deployment. It starts from the accepted `IGIRDER.ULS4-aashto-interface-shear-si` baseline and does not change the AASHTO resistance or demand equations.

## Full-span chart / source ownership

- Beam/Girder browser Plotly charts now prefer Streamlit `width="stretch"` so narrow Analysis columns and print/PDF review layouts do not retain a stale pre-sidebar chart width and clip the right-hand stations.
- Final Composite Flexure and Girder–Deck Interface Shear explicitly expose the configured physical member domain on the x-axis. Imported stations beyond the configured span are not hidden.
- Final Composite flexure plots the full imported `Mux` trace for QA, while its governing +M marker and `φMn` solver remain owned by the accepted positive-flexure scope.
- Interface shear now owns **all Final ULS station rows**, independent of the +Mux flexure scope guard. `Vuy` interface demand is therefore not truncated if a station has negative `Mux`.
- The interface result fingerprint is bumped to `IGIRDER.ULS4A.full-span-audit-clarity`, so the expanded full-span interface source is recalculated after deployment.

## Audit wording clarity

- The interface reinforcement card now reports the actual steel stress used by the solver and the separate AASHTO 60 ksi cap, e.g. `fy used = 390.0 MPa · AASHTO cap = 413.7 MPa`.
- The interface audit stores an explicit `Minimum basis`.
- When `Avf minimum = 0` because the 1.33-demand cap is already satisfied by cohesion, the card states that reason and clarifies that the special low-stress 5.7.4.2 waiver is not needed for that result.

## Engineering scope unchanged

- No change to `vui`, `Vni`, `φVni`, `c`, `μ`, `K1`, `K2`, `φ`, weaker-side `f'c`, `Pc = 0`, or the 60 ksi `fy` cap.
- No change to Final Composite `Mu`, `Mn`, `φMn`, neutral-axis solution, effective width, prestress, or deck-rebar-credit policy.
- Negative Final Composite flexure remains outside the current certified section-strength route; only the demand trace is shown full-span for QA.

## Verification

- Dedicated ULS4A tests cover full-member x-domain, full Final ULS interface-source ownership independent of `Mux` sign, positive-flexure governing-marker ownership, and clarified interface-reinforcement card wording.

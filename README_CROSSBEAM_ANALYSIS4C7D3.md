# CROSSBEAM.ANALYSIS4C7D3 — Segmental Tendon-Only Flexure

## Decision
For **Precast Segmental Crossbeam ULS Flexure only**, adopt a conservative flexural strength basis of:

- concrete compression, plus
- bonded prestressing Tendons with station-dependent effective prestress `fpe(s)`.

Ordinary longitudinal reinforcement is deliberately excluded from `Mn` at every Segmental station. This is a project-adopted strength-credit policy; it does not remove ordinary rebar from Shear, Torsion, Combined V+T, detailing, crack-control, or other applicable workflows.

Cast-in-Place Flexure remains unchanged and may continue to credit eligible ordinary rebar together with bonded Tendons.

## Solver changes
- Precast Segmental Flexure no longer requires a valid ordinary-rebar source to calculate `phiMn`.
- Rebar source changes do not stale the Precast Segmental Flexure result fingerprint.
- Ordinary rebar count/area credited to Segmental `Mn` is always zero.
- The result records `Flexure credit basis = TENDON-ONLY`.
- Exact physical-joint left/right rows remain independently solved.
- Approximately `J ± 100 mm` near-joint sectional checks remain available.
- Flexural development-boundary capacity rows are no longer generated because ordinary-rebar development does not affect the adopted Segmental `Mn` basis.
- Available rebar development-length metadata is retained only for separate Combined V+T/detailing audits and does not affect Segmental Flexure capacity or readiness.

## Chart changes
For Precast Segmental Flexure:
- `Demand Mux` remains one continuous full-member global-analysis trace.
- `Adopted tendon-only phiMn` is one continuous full-member sectional-capacity trace.
- Support footprints and physical joints remain visible as geometry/review context but do not clip the Demand or tendon-only capacity traces.
- At a physical joint, both exact one-sided capacities are plotted at the same joint station. If adjacent Segment sections differ, the capacity curve shows a vertical step instead of a gap or averaged capacity.
- Legacy no-rebar-credit development bands and binary flexural-credit steps are removed from Segmental Flexure.
- Physical-joint transfer, PT anchorage/end-zone D-regions, and beam-column-joint D-regions remain separate engineering checks.

## Regression notes
- Shear, standalone Torsion, and Combined V+T equations are unchanged.
- Combined V+T retains its own ordinary-rebar and development/anchorage requirements.
- Project JSON schema is unchanged.
- Deployment pins remain unchanged.

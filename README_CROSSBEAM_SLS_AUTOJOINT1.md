# CROSSBEAM.SLS.AUTOJOINT1

Improves the Precast Segmental SLS At Transfer source workflow without changing
the concrete-stress equations or physical-joint acceptance criterion.

- Missing exact physical-joint resultants are linearly interpolated from the
  nearest active, unambiguous Transfer rows that bracket each joint.
- One derived joint resultant is checked against both left and right Section
  faces, so users do not need to duplicate station-force rows manually.
- Exact imported joint rows and explicit left/right rows remain authoritative.
- Extrapolation and ambiguous duplicate bracket rows remain blocked.
- The audit table identifies every derived row as `AUTO-INTERPOLATED JOINT` and
  records its two source stations.
- The Precast physical-joint minimum compression requirement remains 0.70 MPa
  at both top and bottom fibers on both faces.
- Cast-in-Place continues to treat Section/Zone boundaries as monolithic
  property boundaries with no physical-joint gate.

No ULS equations, prestress-loss equations, Project JSON schema, or other
member-workflow solvers are changed.

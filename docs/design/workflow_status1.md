# WORKFLOW.STATUS1 — Workflow Capability Wording Alignment

This milestone aligns the user-facing workflow status wording after the QA.BASELINE1 clean-repo baseline.

## Scope

- Align Setup, Analysis, Project Design Code guard, and draft report wording with the current implemented Beam/Girder guarded preview capabilities.
- Keep Column/Pier AASHTO PMM described as implemented engineering-review after AASHTO.COL.PMM1, with shear/torsion/slenderness/seismic/detailing still guarded.
- Keep all Beam/Girder ULS/SLS outputs described as preview / engineering-review workflows unless a later named code-certified milestone exists.
- Do not change PMM, prestress, shear, torsion, SLS stress, deflection/camber, load, or report calculation formulas.

## Engineering boundary

Current Beam/Girder tools include guarded preview workflows for flexure, SHEAR.CODE2, TORSION.CODE2, combined V+T, staged SLS stress, deflection/camber, prestress, and debonding context. They are not final code-certified design outputs.

Final design still requires project-specific review for development length, anchorage, end-zone/bursting, interface shear, fatigue, seismic/detailing, constructability, and independent benchmark evidence.

## QA intent

The milestone removes stale “future placeholder / not implemented” statements where guarded Beam/Girder checks now exist, without promoting those checks beyond their validation status.

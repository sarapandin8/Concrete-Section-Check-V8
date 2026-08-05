# CROSSBEAM.ANALYSIS4C6A — Construction-mode-aware ULS reinforcement source contract

## Scope

- Added one explicit, on-demand ULS reinforcement source contract for Portal Frame Crossbeams.
- Cast-in-Place ULS uses only the active Solid longitudinal/transverse Template and Section/Zone assignments.
- Precast Segmental ULS uses only the active Segment-local longitudinal/transverse Template and Rebar Zone assignments.
- Dormant Cast-in-Place data does not block or stale Precast ULS; dormant Precast data does not block or stale Cast-in-Place ULS.
- Only assigned active-mode templates participate in the ULS source fingerprint; editing an unassigned library row does not stale a valid result.
- Invalid or incomplete active assignments report `SOURCE BLOCKED`; Flexure, Shear, Torsion, and Combined V+T receive no reinforcement credit until the source is ready.
- The Rebar workspace now shows `ULS solver handoff — READY / SOURCE BLOCKED` instead of the obsolete blanket CIP solver lock.

## Engineering guards preserved

- Cast-in-Place Zone boundaries remain monolithic property boundaries, not physical joints.
- Precast physical-joint and development-zone ordinary longitudinal credit remains tendon-only / zero ordinary-rebar credit under the existing route.
- Missing or mismatched torsion-cage detailing remains a Torsion/Combined engineering result (`LAYOUT REQUIRED` / `REVIEW REQUIRED`), not a blanket source-blocking error for valid shear ties.
- SLS/PMM, prestress-loss, Result Summary, and Report/QA handoffs are not enabled by this milestone.

## Engineering impact

- No ACI Flexure, Shear, Torsion, or Combined V+T equation changed.
- No station generation, support-face/h/2 recovery, joint routing, or development-length logic changed.
- No Project JSON schema or migration behavior changed.
- Existing ULS cache fingerprints now include the active ULS reinforcement source fingerprint.

## Repo summary

Add a construction-mode-aware Crossbeam ULS reinforcement source contract that authorizes only active assigned CIP or Precast templates, isolates dormant mode data, and blocks reinforcement credit when the active source is incomplete.

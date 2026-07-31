# CROSSBEAM.SLS1B1 — Segment-Joint Sign, Single-Result, and CIP Applicability Hotfix

## Purpose

Correct and simplify the project-specific physical segment-joint compression gate used by Crossbeam SLS At Transfer and At Service.

## Locked engineering convention

- Concrete stress chart convention: Compression = negative; Tension = positive.
- Project minimum joint compression magnitude: 0.70 MPa.
- Equivalent signed criterion at every physical Precast Segmental joint:

  ```text
  Joint Top stress    <= -0.70 MPa
  Joint Bottom stress <= -0.70 MPa
  ```

- A value numerically greater than `-0.70 MPa` is closer to zero/tension and fails the gate.
- Both Top and Bottom must pass.

## Single displayed joint result

The UI no longer reports separate left/right (`s-` / `s+`) joint results.

When adjacent Segment section properties differ, both adjacent Section IDs are evaluated internally using the same row-coupled imported force state. The app reports:

- one governing Top stress; and
- one governing Bottom stress

per physical joint and load case. The governing value is the numerically greatest signed stress, meaning the least-compressive / most-tensile value. Values are never averaged.

## Construction-type routing

- **Precast Segmental:** physical segment-joint gate is required.
- **Cast-in-Place:** gate is `NOT REQUIRED` because Section/Zone boundaries are monolithic and are not physical segment joints.
- General ACI 318-19 Top/Bottom concrete stress checks remain active for both construction types.

## UI changes

- Adds a visible sign-convention callout near the Calculate action and result cards.
- States the signed joint criterion directly as `fjoint <= -0.70 MPa`.
- Compact table reports signed actual stress against the signed limit.
- Adds one compact joint audit row per joint/case with separate Top and Bottom results.
- Removes user-facing instructions requiring separate `s-` / `s+` rows.

## Regression boundary

No ACI stress-limit equation, Loads contract, Project JSON schema, Prestress Loss solver, ULS solver, Result Summary, Report/QA route, or non-Crossbeam workflow is changed.

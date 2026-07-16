# Concrete Section Pro — CROSSBEAM.PT1A

## Milestone

`CROSSBEAM.PT1A — Tendon geometry view completeness`

## Delivered

- Tendon Profile now provides five review tabs: Plan, Elevation, Cross Section,
  3D Orthographic, and Calculated Audit.
- Elevation retains the shared top-referenced `s–dtop` source and shows the
  Section-ID bottom and centroid context along the member.
- Cross Section selects a station and, at a Segment joint, either adjacent
  Section face. It builds the exact assigned Section ID polygon, interpolates
  each visible tendon from the shared `s–x–dtop` points, and reports whether an
  Internal tendon center is in concrete or outside/in a void. Inputs are never
  moved automatically.
- The 3D review uses Plotly orthographic projection, so parallel member edges
  remain parallel without perspective distortion. Hollow segments retain a
  visible void through four schematic wall prisms.

## Scope guards

- This milestone is geometry/detailing review only. It adds no tendon force,
  friction, wobble, loss, curvature, SLS, ULS, anchorage-zone, deviator-force,
  D-region, or FEA calculation.
- PT continuity at every Segment joint remains `REQUIRED — NOT VERIFIED` until
  PTQA1.
- The accepted Project-JSON tendon source, reinforcement workflows, and all
  other member workflows remain unchanged.

## Validation

- Focused PT1/PT1A view tests: 12 passed.
- Complete Crossbeam plus Project-IO regression suite: 154 passed.
- Full repository suite: 1,955 passed; the same 6 unrelated baseline failures
  remain in Railway U-Girder/legacy source-audit tests.
- Streamlit AppTest rendered five tabs and four Plotly geometry figures without
  exceptions.
- Live browser QA reached the Tendon Profile page, rendered Elevation, Cross
  Section, and WebGL 3D Orthographic, and reported zero page errors.

## Repo summary

Add station-aware Elevation, exact Section-ID Cross Section tendon-fit review,
and orthographic 3D to the Crossbeam tendon source of truth while preserving
one `s–x–dtop` input model and all existing solver/workflow boundaries.

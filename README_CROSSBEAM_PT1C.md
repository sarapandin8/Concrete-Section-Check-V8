# Concrete Section Pro — CROSSBEAM.PT1C

## Milestone

`CROSSBEAM.PT1C — Crossbeam member-length source of truth`

## Delivered

- Section Builder now owns the only editable `Crossbeam total length L (m)`
  control in a separate **Crossbeam Member Geometry** card above the
  Section-ID-specific Geometry Parameters.
- Segment Layout and Tendon Profile show `L` as a read-only reference and
  direct the user back to Section Builder / Member Geometry.
- Changing `L` is a guarded two-step action. The user must explicitly choose:
  - **Keep existing stations — review required**: preserves absolute Segment,
    Tendon, and Rebar Zone station coordinates and lets the existing geometry
    gates report endpoint inconsistencies.
  - **Scale longitudinal stations proportionally**: multiplies Segment,
    Tendon, existing Rebar Zone, and cross-section review stations by
    `L_new / L_old`.
- Proportional scaling refreshes Segment, Tendon, and Rebar Zone editor
  revisions and synchronizes the stored Segment signature so the Rebar page
  does not report a false layout-change warning.
- Tendon lateral coordinates and top-referenced depth, section dimensions,
  material inputs, rebar quantities, and every solver remain unchanged.

## Scope guards

- `L` is member-level project state; it is not owned by the selected Section
  ID and is not duplicated in Section Definition records.
- No length edit silently moves engineering coordinates. The pending value is
  not committed until the user selects a policy and presses Apply.
- Keep mode preserves absolute station inputs; only derived tendon `s/L` values
  are recalculated against the new `L`.
- Other member workflows, analysis routing, Project-JSON schemas, and solver
  calculations are unchanged.

## Validation

- PT1C and adjacent PT1/Section Builder regression: **67 passed**.
- Full repository regression: **1,962 passed**; the same **6 unrelated
  baseline failures** remain in Railway U-Girder and legacy source-audit tests.
- Live-browser QA changed `L` from 20.000 m to 30.000 m with proportional
  scaling, confirmed one editor in Section Builder and zero editors on Segment
  Layout/Tendon Profile, and found zero geometry or browser errors.

## Repo summary

Make Section Builder the single editable source for Crossbeam member length
`L`; keep Segment Layout and Tendon Profile read-only, and require an explicit
Keep-or-Scale decision that synchronizes all longitudinal station sources
without changing section inputs, reinforcement quantities, or solvers.

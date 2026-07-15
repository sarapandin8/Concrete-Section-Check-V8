# CROSSBEAM.RB2 — Segment Section Rebar Preview and Subnavigation Polish

This milestone extends the Crossbeam-only RB1 input foundation with a graphical, segment-specific rebar review workspace while preserving the locked rule that no ordinary reinforcing bar crosses any post-tensioned segment joint.

## What changed

- Replaces the crowded text-like Rebar subtabs with four separated full-width action tabs:
  - `Templates`
  - `Segment / Zone`
  - `Section Rebar Preview`
  - `Joint & Station Audit`
- Splits the Rebar Template Library into clearer groups:
  - template identity and participation
  - auto section-layout controls
  - provided reinforcement quantities
- Adds template-level auto-layout settings for:
  - outer-face bars
  - outer bar size, bar-center offset, and target spacing
  - hollow-section inner-face bars
  - inner bar size, void-face bar-center offset, and target spacing
- Adds a segment/zone selector that resolves:
  - Segment Layout assignment
  - project Section ID from the Crossbeam Section Definition Library
  - assigned Rebar Template
- Adds true-scale section reinforcement figures:
  - Solid sections: outer perimeter layout
  - Hollow sections: independent outer perimeter and inner void-face layouts
- Adds generated-bar count, generated preview As, layer spacing, and readiness summaries.
- Keeps the generated layout explicitly identified as a detailing preview; it does not populate ULS/SLS solver inputs or provided-As quantities.

## Locked engineering rule preserved

```text
Ordinary rebar crossing every segment joint = 0 mm²
Global continuity across each joint = post-tensioning tendons only
```

The generated section preview applies only inside the selected segment/zone. Joint shear transfer, opening/decompression, shear keys, anchorage zones, solid-to-hollow transitions, and column D-regions remain separate checks.

## Not changed

- No ULS flexure, shear, torsion, PMM, SLS stress, prestress-loss, Result Summary, or Report/QA solver handoff.
- No Project JSON schema change.
- No result-cache persistence.
- No change to Railway U-Girder, Bridge/Building Beam-Girder, or Column/Pier Rebar workflows.

## Repo summary

```text
Add Crossbeam segment-specific Solid/Hollow rebar previews with outer and inner-face auto layouts, clearer template controls, and separated commercial subnavigation while preserving tendon-only continuity at segment joints.
```

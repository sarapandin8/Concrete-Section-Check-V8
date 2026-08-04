# CROSSBEAM.ANALYSIS4C1 — Torsion Reinforcement Source Contract

## Baseline

Started only from the accepted milestone:

`concrete-section-pro_CROSSBEAM-ANALYSIS4A-flexure-step-envelope-visual-closeout.zip`

`ANALYSIS4B` was treated as a rejected QA reference and was not used as the release baseline.

## Scope

This milestone establishes a user-owned outer torsion-cage source for Portal Frame Crossbeam reinforcement. It does not change the ACI torsion equations, shear equations, Direct P–M3 Flexure solver, or any other member workflow solver.

## Implemented

### Rebar → Transverse / Shear

Each Crossbeam Transverse Template now stores:

- Use outer torsion cage
- Torsion-cage bar size
- Torsion-cage spacing
- Torsion-cage centerline offset from the outer concrete face
- Cage relationship: additional outer cage or shared with the existing outer shear loop
- Closure status: verified closed loop or review required

Legacy and default Hollow templates intentionally migrate to `LAYOUT REQUIRED`; the app no longer assumes that web loops, flange U-bars, chamfer bars, or the concrete outline form a global closed torsion cage.

Default Solid multi-leg tie templates retain a verified shared outer cage only when torsion bar size, spacing, and closure match the existing physical outer shear loop.

### Source audit helpers

The Crossbeam reinforcement source model now reports:

- `Av/s` from all shear-effective legs
- `At/s` and `2At/s` from the verified outer torsion cage
- source status: `MATCH`, `USER DEFINED`, `LAYOUT REQUIRED`, `REVIEW REQUIRED`, or `MISMATCH`
- geometric provided versus solver-adopted meaning

### Combined reinforcement preview

The Section Rebar Preview → Combined review now shows decision-first cards for:

- Shear reinforcement `Av`
- Outer torsion cage `At`
- Longitudinal torsion reinforcement `Aℓ`

For Hollow sections:

- outer-face longitudinal bars are the only bars eligible for the single outer-cage `Aℓ` source;
- inner-face longitudinal bars remain visible but are explicitly excluded by rule unless a future separately verified inner-cage/multi-cell model is implemented.

A verified outer cage is drawn as a separate purple closed centerline without altering the established web-loop/U-bar/chamfer topology or longitudinal-bar placement.

### Torsion analysis source gate

The existing ACI torsion formulas are unchanged. The torsion calculation now reads bar size, spacing, and cage offset from the verified user-defined source. When the source is missing, unverified, or inconsistent, design-required rows return `LAYOUT REQUIRED` rather than calculating `φTn` from a cage inferred from the concrete outline.

Below-threshold torsion screening remains available because ACI threshold routing does not require a detailed torsion cage.

### Project JSON

The Crossbeam reinforcement schema is advanced from version 1 to version 2. The new cage fields save/load with the existing Crossbeam-namespaced reinforcement block. Older projects migrate without silently enabling a Hollow torsion cage.

## Default source summary

- `TR-SOLID-COLUMN`: 6DB16 @ 100 for shear, `Av/s = 12.0637 mm²/mm`; shared outer DB16 @ 100 torsion cage, `At/s = 2.0106 mm²/mm`, source `MATCH`.
- `TR-HOLLOW-MIN`: 4DB12 @ 200 for shear, `Av/s = 2.26195 mm²/mm`; outer torsion cage `LAYOUT REQUIRED` until entered and verified by the user.

## Files changed

- `concrete_pmm_pro/crossbeam/transverse.py`
- `concrete_pmm_pro/crossbeam/rebar_persistence.py`
- `concrete_pmm_pro/ui/crossbeam_transverse_page.py`
- `concrete_pmm_pro/ui/crossbeam_rebar_page.py`
- `concrete_pmm_pro/analysis/crossbeam_uls_torsion.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- focused tests for source contract, persistence, torsion routing, and joint plotting

## QA completed

- Compileall: PASS
- Crossbeam source-contract / Transverse / Project JSON / Torsion / joint-chart / CIP / shared Beam-Girder ULS targeted regression: 106 passed
- Generic RC, prestressed, directional, and AASHTO PMM regression: 94 passed
- Total completed non-overlapping reported regression: 200 passed

The full `tests/test_crossbeam_*.py` run was started but did not complete within the execution window. The first observed failure is a baseline-existing Prestress-Loss source-string assertion in `test_crossbeam_ptloss4b2b1_semantic_cleanup.py`, unrelated to this milestone.

## Explicit non-scope

- No correction yet to Combined V+T transverse adoption.
- No torsion-specific `b_t + d` extension/development implementation yet.
- No Shear/Torsion row-count, status, chart-joint, action-card, or print-layout closeout yet.
- No multi-cell or inner-cage torsion model.
- No change to Flexure, Shear formulas, PMM solvers, prestress losses, SLS, Loads, Result Summary, or Report/QA.

## Repo summary

Add a user-defined outer torsion-cage source to Crossbeam transverse templates, persist it in Project JSON, gate torsion capacity when the cage is unverified, and show automatic Av, At, and outer-associated Aℓ summaries in the reinforcement preview.

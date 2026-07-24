# CROSSBEAM.RB-CIP1 — Construction-Type-Aware Continuous Rebar Topology Foundation

## Scope

This milestone establishes the solver-neutral longitudinal reinforcement data foundation for **Cast-in-Place Portal Frame Crossbeams** without changing the accepted Precast Segmental reinforcement workflow.

### Added

- A dedicated CIP station-based longitudinal **bar-run topology** with canonical fields for:
  - `Run ID`, `s_start`, `s_end`, bar group and layer/face,
  - bar size/diameter,
  - material/fy,
  - exact-count or target-spacing definition basis,
  - explicit start/end termination intent metadata.
- Validation that preserves unsupported/unknown engineering labels for explicit `REVIEW REQUIRED` instead of silently substituting them.
- No station clamping: out-of-member ranges remain visible and are reported for review.
- A separate Project JSON block: `crossbeam_cip_rebar_input_model`.
- Independent CIP state keys so CIP bar runs never overwrite or reinterpret Precast Segmental template/zone reinforcement.
- Cast-in-Place Rebar guard UI now reports the continuous-topology foundation state while keeping the editor and all solver handoff locked.

## Locked engineering semantics

- Cast-in-Place Crossbeam = one monolithic continuously cast **Solid-only** member.
- CIP Section/Zone boundaries are geometry/property/analysis boundaries, **not physical joints**.
- A longitudinal bar run may cross any number of Section/Zone boundaries.
- RB-CIP1 does **not** assume every bar runs from `s=0` to `L`; intentional starts/stops remain permitted subject to future development/splice QA.
- RB-CIP1 does not invent default reinforcement.
- Precast Segmental physical-joint rule remains unchanged: ordinary longitudinal rebar crossing a physical segment joint = `As = 0 mm²`.

## Explicitly not included

- No released CIP bar-run editor (`RB-CIP2`).
- No development length, splice, curtailment, termination, anchorage, congestion, or code-minimum certification (`RB-CIP3`).
- No CIP bar-run participation in PMM, ULS, SLS, shear, torsion, prestress loss, Result Summary, or Report/QA.
- No changes to Friction/Wobble, Anchorage Set, Elastic Shortening, `fcgp`, Primary/Secondary Prestress, or construction-stage solver equations.

## Repo summary

`Add a solver-neutral station-based continuous longitudinal rebar topology foundation for Cast-in-Place Crossbeams with separate Project JSON persistence, explicit REVIEW validation, and no change to Precast Segmental reinforcement or engineering solvers.`

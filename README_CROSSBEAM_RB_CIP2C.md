# CROSSBEAM.RB-CIP2C — CIP Rebar Semantic and Preview Cleanup

## Baseline

- Starting ZIP: `concrete-section-pro_CROSSBEAM-RB-CIP2B-canonical-zone-rebar-assignment.zip`
- Starting SHA-256: `02451f0a2cb6befd80c163331f4fb8a00dff1391713a822d2e7bd0a2421768dd`

## Scope

Targeted production UI/semantic cleanup for the Cast-in-Place Crossbeam Rebar workflow after RB-CIP2B visual QA.

### Changes

- Replaced the blank Plotly title path that rendered `undefined` with the explicit title `Cast-in-Place Reinforcement Template Assignment`.
- Added a `cip_mode` rendering route to the shared full-length transverse-reinforcement elevation.
- In Cast-in-Place mode, the transverse elevation now shows `Solid zone`, removes Hollow/hidden-void legend entries, and draws internal Zone boundaries as neutral dotted property boundaries.
- Preserved the original Precast Segmental legend and physical-segment semantics when `cip_mode=False`.
- Removed Hollow/segment-joint scope wording from Cast-in-Place combined and transverse previews.
- Changed Cast-in-Place captions from `segment-local` to `Zone-local` and added a CIP-specific Zone note.
- Replaced developer-style `item(s)` completeness wording with professional singular/plural messaging and surfaced the specific assigned-template warning(s).

## Protected behavior

- No engineering equations changed.
- No PMM, ULS, SLS, shear/torsion, prestress-loss, Elastic Shortening, `fcgp`, or construction-stage solver logic changed.
- No Project JSON schema or persistence behavior changed.
- No CIP Template/Zone canonical assignment logic changed.
- Precast Segmental physical-joint semantics and legends remain unchanged.
- CIP solver handoff remains locked.

## QA

- Targeted RB-CIP2A/B/C + CIP visual semantics: `22 passed`.
- Complete Crossbeam regression: `301 passed`.
- Selected cross-workflow smoke: `84 passed, 1 pre-existing failure`.
- Pre-existing failure reproduced on untouched RB-CIP2B baseline:
  - `test_inclusion4_bridge_precast_girder_defaults_store_rebars_but_publish_none`
- Full repository suite attempted and reached approximately 53% with no failures shown before timeout; full repository green is not claimed.
- `py_compile`: passed.
- `compileall`: passed.

## Repo summary

`Clean up Cast-in-Place Crossbeam Rebar previews with explicit assignment titles, Zone-only transverse semantics, CIP-specific scope wording, clearer completeness guidance, and preserved Precast behavior.`

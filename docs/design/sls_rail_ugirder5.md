# SLS.RAIL.UGIRDER5 — Final Staged Service Accumulation Preview

This milestone adds a guarded final staged service-stress accumulation preview for the Railway U-Girder workflow.

## Scope

- Combine locked-in one-web stresses from transfer and wet slab casting with later full-U incremental service actions at the same top/bottom physical web fibers.
- Use `Pe_final - Pe_construction` as the final prestress loss increment on the full Railway U-Girder basis.
- Consume active SLS rows from the Loads tab as additional service increments after composite action.
- Provide governing rows and stress-limit preview for engineering review.

## Guardrails

- The preview does not model transfer-length force ramping, development length, anchorage/end-zone bursting, creep/shrinkage redistribution, or code-certified staged composite behavior.
- Loads tab SLS actions are assumed to be additional service increments; users must avoid double-counting self-weight already generated in the automatic staged-load preview.
- The result remains a review workflow, not final certified design output.

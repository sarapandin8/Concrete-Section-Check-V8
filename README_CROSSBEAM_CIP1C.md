# CROSSBEAM.CIP1C — Unknown Section-ID Review Preservation

This hotfix closes a CIP1B QA blocker without changing any structural or
prestress-loss equation.

## Fixed behavior

- An explicit project `Section ID` that no longer resolves in the Crossbeam
  Section Library is preserved exactly.
- Segment/Zone validation can therefore report `REVIEW` instead of silently
  replacing the unresolved assignment with the first Section definition or a
  role-based fallback.
- Project JSON round-trip preserves the unresolved ID for post-load review.

## Backward compatibility

- Known legacy Solid/Hollow preset keys still migrate to project Section IDs.
- Legacy rows without an explicit Section ID may still use their preset or role
  metadata to resolve a compatible project definition.

## Locked / unchanged

- No Section geometry is auto-converted.
- No Rebar topology or assignment rule is changed.
- No Friction/Wobble, Anchorage Set, Elastic Shortening, `f_cgp`,
  Primary/Secondary Prestress, PMM, SLS, ULS, or stage-solver equation is
  changed.

# CROSSBEAM.TDSTATE2 — Navigation-Safe Temporary Widget State

## Scope

Close the runtime navigation defect in `CROSSBEAM.TDSTATE1` where returning from
`Analysis` to Time-Dependent Loss recreated the inputs at their widget minima:
RH = 1 and schedule ages at or near zero.

## Root cause

The first fix separated a durable TD mapping from the visible values, but the
visible controls still used the established project-input keys as Streamlit
widget keys. Streamlit widget identity includes the page where the widget is
rendered. When the TD controls were mounted again, the new widget instance
could overwrite those keys with its minimum/default value before the durable
mapping was restored.

## Changes

- Make the durable TD input mapping the authoritative cross-page source.
- Render TD controls with separate underscore-prefixed temporary widget keys.
- Copy durable values into temporary keys immediately before widget rendering.
- Use `on_change` callbacks to copy only genuine user edits back to durable
  state.
- Keep legacy flat session keys synchronized for the existing Project JSON
  contract and downstream source readers.
- Keep adoption confirmation and reset actions synchronized with the durable
  owner.
- Ignore stale/minimum widget values when Project JSON is saved from another
  workspace.

## Runtime regression

The Streamlit AppTest sequence now performs the reported workflow directly:

1. Open TD with RH 75%, curing 7 d, ti/tg 28 d, tr 35 d, tf 18,250 d.
2. Change RH to 70%.
3. Navigate to Analysis, where the TD controls are unmounted.
4. Return to TD.
5. Verify RH remains 70% and all other TD values remain unchanged.

## Preserved behavior

- No Prestress Loss, SLS, ULS, construction-stage, or FEA equation changed.
- No Project JSON schema version changed.
- Reset still preserves imported FEA rows and permanent-load event mappings.
- Merely materializing temporary TD widget keys does not mark Analysis stale.
- A genuine TD input edit still marks Prestress/Analysis out of date.

## Repo summary

Make Crossbeam Time-Dependent inputs navigation-safe with Streamlit temporary widget keys, durable callbacks, and minimum-value overwrite regression coverage.

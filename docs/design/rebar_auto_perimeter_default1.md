# REBAR.AUTO.PERIMETER.DEFAULT1 — Rebar input mode default

## Purpose

Make the Rebar page open in `Auto perimeter layout` mode by default, because this is the preferred starting workflow for generated longitudinal ordinary rebar around accepted section geometry.

## Behavior

- New sessions default `Rebar input mode` to `Auto perimeter layout`.
- Existing valid session selections are preserved.
- Invalid or missing `rebar_input_mode` values are reset to the default.
- Applying a generated layout still returns to the manual table review mode so the applied rows are immediately visible and editable.

## Guardrail

The editable rebar table remains the single source of truth for PMM/SLS/flexure and torsion-Al review after generated bars are applied. Auto perimeter remains a preview/apply workflow, not a hidden silent overwrite of manual bars.

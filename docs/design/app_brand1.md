# APP.BRAND1 — Rename visible application brand and fix compact header crop

## Scope
- Rename the visible app/page title from `Concrete PMM Pro` to `Concrete Section Pro`.
- Keep the engineering positioning broad enough for section geometry, rebar/prestress input, PMM, scoped ULS checks, SLS previews, and reports without implying full final code certification.
- Fix the compact-header clipping introduced during navigation density polish.

## Rationale
`Concrete PMM Pro` is now too narrow because the application has grown beyond PMM into a broader concrete section analysis/design-review workflow. `Concrete Section Pro` is concise, commercial, and better aligned with the current feature set while avoiding overclaiming final authority approval or code certification.

## Changes
- Page title and main `st.title()` changed to `Concrete Section Pro`.
- App subtitle changed to a product/workspace description instead of an old milestone label.
- Header CSS line-height/top padding relaxed so the title is not cropped.
- Default report title aligned with the new visible app name.

## Out of scope
- No navigation behavior changes.
- No solver, geometry, rebar, prestress, loads, SLS, or report calculation changes.

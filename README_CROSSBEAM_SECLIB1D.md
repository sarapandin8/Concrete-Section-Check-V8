# CROSSBEAM.SECLIB1D — Section naming and active-row polish

This milestone reduces effort in the Crossbeam project-section library while preserving stable Section IDs and table-driven geometry synchronization.

## Added

- Role-based section-name suggestions for Hollow and Solid project sections.
- A `Custom project name` option so suggestions never constrain project-specific naming.
- One-click suggestion fill followed by explicit `Save section name` confirmation.
- Duplicate-name guard to prevent different Section IDs from carrying an ambiguous identical display name.
- A compact `ACTIVE PROJECT SECTION` line showing Section ID, name, family, and assigned segments.
- Active-row highlighting in the Project Section Summary table.
- Removal of the redundant `Active` data column; native row selection remains the interaction control.
- `Quick section switch` remains as an optional fallback while the summary table stays the primary visual selector.

## Suggested names

Hollow:
- Hollow typical
- Hollow heavy web
- Hollow near column
- Hollow near anchorage
- Hollow transition

Solid:
- Solid column region
- Solid anchorage block
- Solid transition region
- Solid end block
- Solid typical

## Safety

- Suggestions affect only the user-facing section name; Section ID remains the stable internal reference.
- No Segment Layout, geometry calculation, Project JSON schema, ULS/SLS, prestress-loss, rebar-capacity, or report solver changes.
- Existing non-Crossbeam workflows remain unchanged.

## Repo summary

Polish the Crossbeam section library with optional role-based naming suggestions, duplicate-name protection, a clear active-section badge, and highlighted table-driven selection.

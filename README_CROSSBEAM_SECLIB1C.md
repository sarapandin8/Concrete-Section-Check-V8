# CROSSBEAM.SECLIB1C — Table-driven active section synchronization

This milestone makes the Crossbeam Project Section Summary the primary visual selector for project section definitions.

## Added

- Single-row selection on the Project Section Summary table.
- Clicking a row stages that Section ID as the active definition and safely reruns before Section Builder widgets are instantiated.
- The selected section now drives the geometry editor, calculated gross properties, live section preview, and section-management controls.
- The active Section ID remains visible with the existing Active marker in the summary table.
- A per-active-section dataframe key prevents stale table selection from overriding later section changes from the selector or library actions.

## Safety

- Uses the existing pending-active-selection mechanism; no widget-owned Session State key is mutated after widget creation.
- No ULS/SLS, prestress-loss, rebar-capacity, or report solver changes.
- No Project JSON schema changes.
- Existing workflows remain on their prior section and rebar behavior.

## Repo summary

Make the Crossbeam project-section summary table drive the active section so row selection updates the preview, geometry editor, properties, and management panel in sync.

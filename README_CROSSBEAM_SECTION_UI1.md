# CROSSBEAM.SECTION-UI1 — Project Sections Action Placement and Simplified Rename Workflow

This milestone improves the Crossbeam Project Sections workspace without changing section geometry, assignment, Project JSON, or engineering solver behavior.

## Scope

- Move `Selected section`, `Duplicate current`, `New Solid`, and Precast-only `New Hollow` controls directly above the Project Section Summary table.
- Keep one-click table `Edit` selection and active-row highlighting.
- Replace the large `Manage Selected Section` area with a compact `Selected Section Name` editor directly below the table.
- Rename with one text field and one `Rename section` button.
- Keep common-name suggestions available only in a collapsed optional expander.
- Move deletion and Section-ID changes into one collapsed `Delete or change Section ID` expander.
- Keep assigned-section deletion guards and stable Section-ID reference updates unchanged.

## Protected behavior

- Cast-in-Place remains Solid-only; dormant Hollow definitions remain preserved for Precast Segmental mode.
- Precast Segmental continues to support both Solid and Hollow Section IDs.
- Section IDs remain the stable internal reference for Segment/Zone assignments and Project JSON.
- Renaming a section changes only its project-facing name.
- No section geometry, gross-property, reinforcement, prestress-loss, PMM, ULS, SLS, construction-stage, or solver equation changes.
- No Project JSON schema change.

## Repo summary

Place Crossbeam section creation actions beside the Project Section Summary table and simplify selected-section renaming while preserving stable IDs, assignment guards, and all engineering behavior.

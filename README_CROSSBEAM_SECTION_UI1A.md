# CROSSBEAM.SECTION-UI1A — Rename Row Polish

This milestone polishes the Crossbeam Project Sections rename workflow without changing section identity, assignments, geometry, persistence, or engineering solvers.

## Changes

- Group the `Section name` field and `Rename section` action inside one compact row instead of spanning the full page width.
- Use a borderless Streamlit form so Enter submits the rename as well as the primary button.
- Keep the stable Section ID visible beside the editor and state that Segment/Zone references remain unchanged.
- Add direct validation for blank and unchanged names while preserving duplicate-name checks.
- Keep optional name suggestions and advanced ID/delete operations in their existing collapsed sections.

## Scope guards

- Section IDs remain stable unless the separate advanced ID tool is used.
- Segment Layout / Section-Zone Layout references are unchanged by renaming.
- No Project JSON schema, section geometry, rebar, prestress, PMM, ULS/SLS, or solver equation changes are included.

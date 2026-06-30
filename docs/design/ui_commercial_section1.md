# UI.COMMERCIAL.SECTION1 — Commercial Section Builder layout polish

## Scope
Polish the Section Builder visual hierarchy toward a commercial engineering-software layout while keeping all engineering state and calculation paths unchanged.

## Included
- Add a professional Section Builder hero/header with workflow tabs: Definition, Analysis, Report / QA.
- Add reusable commercial panel title markup for Section Definition, Geometry Parameters, Live Section Preview, and Section Properties.
- Add compact status/pill styling and a canvas-style preview note.
- Preserve the existing two-column definition/preview workflow.

## Out of scope
- No geometry generator changes.
- No section-property formula changes.
- No PMM, shear, torsion, SLS, report, rebar, or prestress logic changes.
- No project schema changes.
- No React/native UI rewrite.

## QA note
This milestone is a UI polish layer only. Streamlit still reruns the script normally; this milestone does not change solver caching or analysis execution.

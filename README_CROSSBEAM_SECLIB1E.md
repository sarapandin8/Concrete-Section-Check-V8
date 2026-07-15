# CROSSBEAM.SECLIB1E — One-click project-section table selection

This hotfix removes the extra click previously required when selecting a Crossbeam project section from the summary-table checkbox/row.

## Changed

- Replaces the post-render `on_select="rerun"` handling with a callable dataframe selection callback.
- The callback stages the clicked Section ID before the next full Streamlit render.
- The existing pre-render section-library preparation then loads the selected geometry before the quick switch, geometry controls, properties, preview, and management widgets are instantiated.
- Uses a revision-scoped dataframe key so the old checkbox selection is cleared after the active section changes.
- Keeps single-row selection, active-row highlighting, and the optional Quick section switch.

## Safety

- No geometry equations or section properties changed.
- No Segment Layout, Rebar, Tendon, ULS/SLS, prestress-loss, Project JSON schema, Result Summary, or Report / QA behavior changed.
- The change remains scoped to the Portal Frame Crossbeam project-section summary table.

## Repo summary

Make Crossbeam project-section table selection respond on the first click by staging the selected Section ID in a pre-rerun callback before geometry and preview widgets render.

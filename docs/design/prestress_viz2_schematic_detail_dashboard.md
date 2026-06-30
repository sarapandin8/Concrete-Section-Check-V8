# PRESTRESS.VIZ2 — Split Schematic + Strand Detail Dashboard

This milestone replaces the former single prestress cross-section chart with a split dashboard for the girder prestress workspace.

## Scope

- Adds a full-section **Overall section schematic** for locating the strand blocks without forcing the user to read every strand at full-section scale.
- Adds an external **Strand row summary** table with row, side groups, total strands, bonded count, debonded count, left/right debond length, and selection mode.
- Adds zoomed **Left strand block detail** and **Right strand block detail** panels only for Railway U-Girder-style separated strand pockets. Non-U-girder layouts such as Precast I-Girder use one merged **Strand block detail** panel.
- Keeps bonded/debonded interpretation tied to existing PS6A row metadata and the station-effective prestress handoff.

## Visual policy

- Concrete outline is intentionally low contrast.
- Bonded strands are blue.
- Debonded/sleeved strand selections are red.
- Row summaries are not placed as floating text inside the plot.
- Plot mode bars are hidden in the dashboard renderer to reduce raw Plotly/debug-chart appearance.
- Overall schematic strand markers are intentionally small; detailed reading is handled in the zoomed panel.
- Zoomed strand details show representative horizontal strand spacing, horizontal edge clearances, bottom edge distance, and vertical row spacing without changing any calculation data.

## Non-scope

- No solver equation changes.
- No change to force-state, loss, SLS/ULS, report, project schema, or debonding station-participation logic.
- No attempt to resolve the known Analysis-result persistence/cache issue.

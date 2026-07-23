# CROSSBEAM.CIP1A — Member Configuration Relocation & Construction-Type State Routing

This milestone hardens the Crossbeam construction-type master switch and places member-level controls at the top of Section Builder before the project Section-ID library.

## Scope
- Moves Crossbeam total length and Construction/Support Configuration above Project Sections and section-specific geometry.
- Separates the construction-type display widget from the Project-JSON-backed canonical source so Streamlit reruns/restores cannot silently overwrite the selected mode.
- Routes `Precast Segmental` and `Cast-in-Place` immediately to their separately preserved longitudinal layouts.
- Filters the Section Builder library to Solid Section IDs only in Cast-in-Place mode while preserving dormant Hollow definitions for Precast mode.
- Keeps `New Hollow` unavailable in Cast-in-Place mode and automatically changes only the active editor selection to an applicable Solid Section ID when necessary.

## Locked / unchanged
No changes were made to prestress-loss equations, Friction/Wobble, Anchorage Set, Elastic Shortening, `f_cgp`, Primary/Secondary Prestress, PMM/SLS/ULS, or the future Cast-in-Place continuous longitudinal rebar solver.

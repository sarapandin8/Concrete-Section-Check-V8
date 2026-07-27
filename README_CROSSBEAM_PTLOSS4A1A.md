# CROSSBEAM.PTLOSS4A1A — Construction-Route Semantics and Print-Audit Integrity

This milestone polishes the accepted PTLOSS4A1 lightweight Time-Dependent preview without changing any engineering equations or numerical results.

## Changes

- Renames the Precast Segmental route from `REPRESENTATIVE PRELIMINARY TIME-STEP PREVIEW` to `REPRESENTATIVE INTERVAL PREVIEW` so the UI does not imply that a construction-schedule time-step analysis has already been performed.
- Replaces the generic drying-geometry card with an explicit Segment Layout loss-geometry source card, including mixed Solid/Hollow semantics, Section-ID count, and zone count.
- Splits the wide drying contribution audit into a station/section source table and a separate volume/drying-surface contribution table with percentage shares.
- Adds print-heading anchors so AASHTO factors, representative interaction source, and Post-ES source headings remain with their tables in browser print.
- Splits the wide Post-ES audit into tendon stress and tendon steel-property tables so right-side columns remain readable.

## Locked scope

- No creep, shrinkage, relaxation, or `Kdf` equation changed.
- No FEA/contact solver path changed.
- No Project JSON schema or result persistence changed.
- Effective Prestress remains locked.

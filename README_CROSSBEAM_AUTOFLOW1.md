# CROSSBEAM.AUTOFLOW1 — Automatic Prestress-to-FEA Workflow

This milestone removes redundant user confirmations from the Crossbeam prestress-loss and station-force workflow while preserving source validation and audit traceability.

## Accepted interaction model

- A CURRENT/CLOSED Effective Prestress source with complete tendon coverage becomes download-ready automatically.
- The primary workflow is fixed to one safe route: use the system-average total accounted loss (%fpj), convert it to stress loss, subtract it once from the pre-loss FEA tendon-stress basis, and apply the resulting force to each tendon.
- The UI no longer asks for a separate Engineer-adoption checkbox or an FEA route selection.
- The selected upload target declares the response stage automatically: ULS final stage, SLS At Service, or SLS At Transfer.
- Repeated stage and row-coupling confirmation checkboxes are removed.
- FEA program and model revision remain recommended traceability metadata, but blank values do not block calculation.

## Safety retained

- Incomplete or stale Effective Prestress sources remain blocked.
- Incomplete tendon station coverage remains blocked.
- The adopted final loss must remain greater than 0% and less than 60%.
- Units, sign mapping, required columns, station mapping, Section/Zone mapping, and reinforcement mapping remain validated.
- The UI and exports state that the same prestress losses must not be calculated or subtracted again in FEA.
- External FEA remains responsible for structural compatibility and secondary prestress response; returned P/V2/T/M3 rows are used as demand without adding prestress again in Analysis.

## Repo summary

Streamline the Crossbeam prestress-to-FEA workflow with automatic source adoption, one no-double-counting loss route, optional traceability metadata, and stage-aware force imports without repetitive confirmations.

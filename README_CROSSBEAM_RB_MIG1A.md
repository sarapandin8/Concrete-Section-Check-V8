# CROSSBEAM.RB-MIG1A — Current-Schema Stale Built-In Rebar Assignment Repair

This hotfix extends RB-MIG1 to projects already saved in the current Project JSON schema that still carry stale built-in Solid/Hollow rebar template assignments created by an older migration/session-order defect.

## Scope

- Repair current-schema restored projects when a known built-in longitudinal/transverse template is incompatible with the canonical Segment Solid/Hollow role.
- Preserve custom incompatible, missing, or unknown template IDs as `REVIEW REQUIRED`; do not invent engineer intent.
- Preserve the actual restore classification (`PROJECT JSON RESTORED` vs `LEGACY PROJECT MIGRATED`) after page-entry reconciliation.
- Keep current Segment Layout + Section Library as the geometry source of truth.

## Exact reproduced field case

A current-schema project containing `S3 = CB-H01 / Hollow` while Zone `Z-S3` still references `RB-SOLID-COLUMN` and `TR-SOLID-COLUMN` is automatically reconciled to Hollow-compatible built-in templates on project restore/page entry.

## Protected boundaries

No Rebar solver equations, Section/Segment geometry, Friction/Wobble, Anchorage Set, Elastic Shortening equations, `f_cgp`, Primary/Secondary Prestress, `Pe/Pe_eff`, PMM, SLS/ULS, or other member workflows are changed.

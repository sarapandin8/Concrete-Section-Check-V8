# SHEAR.TRACE1 — Beam/Girder Shear Compact Status Source Trace

## Purpose

This milestone fixes the remaining contradiction in the Beam/Girder ULS compact shear table where the table could display:

- `Status = FAIL`, while
- the displayed governing shear row had passing strength and detailing D/C values.

The issue was not the shear equation. It was a data-lineage problem: the compact table combined a status produced from one row in `shear_check_df` with demand/capacity/utilization displayed from another row.

## Root cause

The compact table row for `Check = Shear` used:

- status from `_beam_uls_shear_overall_status(shear_check_df)`, but
- displayed row data from `_beam_uls_governing_shear_row(shear_check_df)`.

If a non-governing row controlled a detailing/coverage failure while the strength-governing row passed, the table could show a passing row but a failing status. This made the UI look wrong and hid the true source of the failure.

## Fix

Added a traceable decision helper:

```text
_beam_uls_shear_decision_summary()
```

This helper now chooses the compact-table source row and status together:

1. Filter boundary/support-only rows using the existing design-row filter.
2. Normalize each row into strength D/C, detailing D/C, demand, and row status gates.
3. If any eligible row fails strength or detailing, return that failing row as the displayed compact row.
4. If all eligible rows pass, return the normal strength-governing row.
5. If a stale text `FAIL` row has no numeric fail evidence, treat it as review metadata and do not let it override current numeric PASS evidence.

## UI behavior after this milestone

The compact table must no longer show a mixed message such as:

```text
Shear | FAIL | x = 9.000 m | D/C 0.541 / det 0.757
```

If shear really fails, the row shown in the compact table is the failing source row. If all eligible rows pass, the compact table shows `Shear = PASS`.

## Scope boundary

No shear equations were changed.
No SLS equations were changed.
No geometry, section-property, prestress, or load-combination equations were changed.
This is a status/source-of-truth routing fix only.

# SHEAR.STATUS4 — Support-Row Status Hardening for Beam/Girder ULS Shear

## Purpose

Fix a remaining compact ULS shear status mismatch seen with Railway U-Girder cases where exact support load rows remained in the calculated shear dataframe and could keep the compact summary at `FAIL` even though the inserted critical shear sections and the shear workspace evidence passed.

## Engineering basis

For Beam/Girder ULS shear, exact support resultants are useful for the demand diagram and peak-demand card, but sectional shear acceptance is normally made at the applicable critical section away from the support. The UI already labels the peak shear demand as `diagram/support demand only` and inserts critical shear sections near supports.

When critical shear section rows exist, exact end support `LOAD STATION` rows are now excluded from the governing shear status and governing-station selection. They remain visible as demand-diagram/source data, but they do not override passing critical-section strength/detailing gates.

## Scope

Changed:

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_uls_girder_compact_workspace.py`

Not changed:

- Shear strength equation
- Detailing equation
- Vn limit equation
- SLS solver
- ULS flexure/torsion equations
- Prestress/debonding logic
- Geometry generator
- Project schema

## Guardrails

This is a status/filtering hotfix, not a capacity increase. If any eligible critical/interior design row has finite D/C > 1.0, the shear check still fails. If no critical-section rows are available, support rows are not automatically ignored.

# SHEAR.STATUS1 — Beam/Girder ULS Shear Status Propagation Hotfix

## Purpose

`SHEAR.GOVERNING1` corrected the displayed governing shear station so the compact table and shear chart no longer chose an arbitrary low-demand row only because a zone-wide detailing D/C failed. A second issue remained: the compact ULS table could still show `Shear = FAIL` while the Shear workspace cards showed `PASS` and the plotted demand was below `φVn` along the member.

The cause was status propagation. `_beam_uls_shear_overall_status()` trusted the row-level `Status` string first. If an older/source row carried `Status = FAIL`, that stale aggregate value could override the explicit gate evidence displayed to the user:

- `Strength status = PASS`
- `Detailing status = PASS`
- `Strength D/C <= 1.0`
- `Detailing D/C <= 1.0`

## Change

The overall Beam/Girder shear status now derives from the explicit strength/detailing/readiness gate columns before falling back to the aggregate row `Status` string.

The check still fails for real failures:

- explicit `Strength status = FAIL`,
- explicit `Detailing status = FAIL`,
- `Strength D/C > 1.0`,
- `Detailing D/C > 1.0`,
- missing stirrup coverage / layout-required rows,
- review/data-required rows.

But a stale `Status = FAIL` no longer overrides clear explicit gate evidence.

## Expected UI result

For a row such as:

```text
Vu = 1,355.74 kN
φVn = 2,506.72 kN
Strength D/C = 0.541
Detailing D/C = 0.757
Strength status = PASS
Detailing status = PASS
```

The compact ULS table must show:

```text
Shear = PASS
```

The overall ULS check may still remain review/fail if a separate gate such as Shear + Torsion, torsion detailing, development length, anchorage, or project review items fail. That is separate from the sectional shear status.

## Scope not changed

No changes were made to:

- shear strength equations,
- torsion or combined V+T equations,
- flexure/PMM equations,
- SLS equations,
- prestress/debonding logic,
- geometry generation,
- section properties,
- load-combination equations,
- project schema,
- Streamlit UI layout.

## Regression tests

Added tests confirm that:

1. compact shear status ignores a stale aggregate `FAIL` when explicit strength/detailing gates pass;
2. Shear + Torsion source gate is clear when the explicit shear gates pass and torsion is below threshold;
3. previous SHEAR.GOVERNING1 behavior still selects the strength-demand governing station rather than a detailing-only low-demand row.

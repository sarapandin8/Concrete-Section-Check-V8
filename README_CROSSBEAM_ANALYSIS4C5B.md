# CROSSBEAM.ANALYSIS4C5B — ULS Governing Evidence and Count Consistency

## Scope

Closes two visual-QA inconsistencies found in the reviewed Crossbeam ULS pages while preserving all accepted solver equations and the deferred physical-joint review scope.

1. The Combined V+T `Why this result` table could show the section-size D/C from the overall longitudinal-governing row instead of the actual section-size-governing row.
2. The Shear source card reported 32 section-capacity checks but described only the 12 retained and 10 support checks, omitting the 10 one-sided physical-joint section-capacity audit rows from the breakdown.

The Combined V+T `Joint review` workspace is intentionally not developed or changed in this milestone.

## Corrections

### Combined V+T evidence ownership

Each overview row now reads its own governing non-joint source:

- Section-size interaction → maximum `Stress D/C value`
- Combined transverse reinforcement → maximum `Transverse D/C value`
- Minimum longitudinal torsion reinforcement → maximum `Al minimum D/C value`
- Direct flexure plus torsional longitudinal tension → maximum `Flexure+torsion D/C value`

This makes the overview table agree with the dedicated component cards and plots. The overall Combined V+T status and controlling check still use the accepted overall governing logic.

### Shear count traceability

The source card is renamed to `ACI section-capacity checks` and its count is assembled explicitly as:

```text
retained section checks
+ generated Column Face / h/2 support checks
+ one-sided physical-joint section-capacity audits
```

Physical-joint force transfer remains `REVIEW REQUIRED`; the one-sided rows provide section-capacity evidence only and do not certify keys, interfaces, anchorage, or joint transfer.

## Files changed

- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis4c4_component_views.py`
- `tests/test_crossbeam_analysis2_uls_shear.py`
- `README_CROSSBEAM_ANALYSIS4C5B.md`
- `README.md`

## Regression boundary

- No Flexure, Shear, Torsion, or Combined V+T engineering equation changed.
- No demand, capacity, station-recovery, interpolation, extrapolation, or governing solver changed.
- No physical-joint transfer calculation was added.
- No Prestress Loss, Loads, Project JSON schema, navigation, or row-deletion behavior changed.
- No result-cache persistence was added.

## QA completed

- Compileall: PASS
- Combined V+T component-view and Shear UI targeted tests: 28 passed
- ANALYSIS4C1–4C5A regression: 33 passed
- Shear ANALYSIS2/2A regression: 26 passed
- Flexure/Torsion/Joint-capacity regression: 30 passed
- Segment layout, Column/support, and Project JSON regression: 28 passed
- A broad combined Analysis test run was attempted but exceeded the 120-second execution limit; no single-run full-suite pass is claimed.

## Repo summary

Align Crossbeam ULS overview evidence with each component's actual governing row and clarify Shear section-capacity counts by including one-sided joint audit rows without changing solver logic or physical-joint review scope.

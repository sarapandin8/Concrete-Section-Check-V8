# CROSSBEAM.SLS1A1 — Transfer Stress-Limit Equation Labels

## Scope

This compact UI refinement keeps the accepted `CROSSBEAM.SLS1A` transfer-stress solver unchanged and adds visible equation/substitution labels directly on the dashed ACI 318-19 stress-limit traces.

For the active local transfer strength `f'ci`, the chart now displays:

```text
Compression limit: -0.60 f'ci = -0.60(f'ci) = limit MPa
Tension limit:     +0.25 sqrt(f'ci) = +0.25 sqrt(f'ci) = limit MPa
```

The chart uses the accepted sign convention:

- compression negative;
- tension positive.

The exact local `f'ci`, equation, substitution, and limit value are also retained in the hover trace at every imported station. If `f'ci` varies along the Crossbeam, the visible right-side label identifies that the local value varies while the hover trace gives the exact station value.

## Regression boundary

No change was made to:

- ACI 318-19 equations or stress limits;
- transfer stress calculations;
- physical segment-joint compression checks;
- Loads or Project JSON persistence;
- ULS, At Service, Result Summary, or Report / QA;
- any non-Crossbeam workflow.

## Files changed

- `concrete_pmm_pro/crossbeam/analysis_charts.py`
- `tests/test_crossbeam_sls1a_transfer_stress.py`
- `README_CROSSBEAM_SLS1A1.md`
- `README.md`

## Repo summary

`Label Crossbeam transfer stress-limit traces with the ACI equations, substituted f'ci values, and exact MPa limits without changing the accepted SLS solver.`

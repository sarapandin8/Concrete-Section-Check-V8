# CROSSBEAM.SUPPORTQA1B — Safe ES Override Defaults and Governing-Source Clarity

## Baseline

Starts from candidate `CROSSBEAM.SUPPORTQA1A — One-Sided Column-Joint ES Audit and Equilibrium Closure` after deployed-page review confirmed the four-column support-footprint, evaluation-coverage, one-sided limit, and joint-equilibrium evidence.

## Purpose

Remove two remaining Elastic Shortening QA ambiguities without changing any structural response or prestress-loss equation:

1. disabled manual `f_cgp` and `Eci` fields must display the current source-derived values rather than stale/default values; and
2. the audit must identify the exact row or tied rows that produce the adopted governing `f_cgp`.

## Changes

### Safe manual-override state

- While the manual `f_cgp` override is disabled, its dormant field is synchronized to the current source-derived `f_cgp`.
- While the manual `Eci` override is disabled, its dormant field is synchronized to the current stressing-stage `Eci`.
- When an engineer enables either override for the first time in the current session, the editable value starts from the current source value.
- A manual value is created only after the engineer subsequently edits that seeded value.
- An already-enabled override restored from Project JSON is preserved on first load; this patch does not silently replace an intentional persisted override.
- Transient previous-toggle state is not added to Project JSON.

This prevents inactive values such as `f_cgp = 0 MPa`, `Eci = 1,000 MPa`, or the historical `31,500 MPa` seed from becoming active merely because a checkbox is selected.

### Governing `f_cgp` source clarity

- The `f_cgp evaluation audit` marks matching source rows as `GOVERNING`.
- A decision-first banner reports:
  - adopted governing `f_cgp`;
  - evaluation role;
  - station;
  - one-sided limit, when applicable;
  - Section ID; and
  - tied-row count, when multiple rows share the governing value.
- Permanently unbonded routes state that the adopted value is a member-length average and therefore has no single governing local row.
- A missing local source match is surfaced as `REVIEW`, not silently accepted.

## Engineering scope

- No Friction/Wobble equation changed.
- No Anchorage Set equation changed.
- No Elastic Shortening equation or stressing-group factor changed.
- No frame/contact stiffness, load, support, or joint-equilibrium formulation changed.
- No additional structural solve was added.
- No Elastic Shortening fingerprint change was required because the numerical source result is unchanged.
- No Project JSON schema changed.
- No Loads or Analysis workflow changed.

## Verification

- SUPPORTQA1B override/governing-source tests: 4 passed.
- SUPPORTQA1/SUPPORTQA1A/SUPPORTQA1B and lightweight ES targeted set: 20 passed.
- Crossbeam regression partitions: 468 passed; 2 known pre-existing obsolete PTLOSS4B2B1 source-string failures remain identical to the starting SUPPORTQA1A baseline.
- Project IO / Loads / dirty-state / navigation / Result Summary / Report QA integration: 121 passed.
- Repository inventory: 2,308 collected tests.
- Modified modules pass `py_compile` and repository `compileall`.

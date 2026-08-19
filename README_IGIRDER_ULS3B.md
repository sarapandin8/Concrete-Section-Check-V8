# IGIRDER.ULS3B — Flexure Runtime-State Synchronization

## Scope

Synchronize the commercial Analysis dashboard `Runtime state` card with the active Precast I-Girder ULS Flexure stage without changing engineering equations, capacities, demands, fingerprints, or stored result versions.

## Behavior

- `Construction — Noncomposite`
  - current PASS + engineer-confirmed Construction ULS factors → `PASS`
  - current FAIL → `FAIL`
  - current result with unconfirmed factor gate → `REVIEW`
  - changed inputs with older stored result → `STALE`
  - ready source/no current result → `READY TO CHECK` / `READY TO REVIEW`
- `Final — Composite`
  - current section FAIL → `FAIL`
  - current section PASS with interface shear pending → `REVIEW`
  - future current section PASS + interface shear PASS → `PASS`
  - changed inputs with older stored result → `STALE`
- Construction and Final calculation buttons rerun once after persisting the current result so the top dashboard cannot lag one interaction behind.

## Engineering impact

None. IGIRDER.ULS3A flexural strength results and cache versions are preserved.

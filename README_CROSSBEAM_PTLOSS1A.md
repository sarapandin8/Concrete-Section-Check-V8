### CROSSBEAM.PTLOSS1A - HDPE External Loss Assumption Polish

PTLOSS1A tightens the Crossbeam `Prestress Loss` assumptions for the current
external tendon system, where the external tendon is HDPE/HDPE-lined through
the deviator contact path.

#### What changed

- Keeps the adopted external HDPE-lined friction coefficient at `mu = 0.25` as
  a conservative design-preview value.
- Documents that AASHTO Table 5.9.3.2.2b-1 lists `mu = 0.23` for polyethylene,
  while `0.25` is used here until supplier data or friction testing is adopted.
- Renames the input label to `External HDPE-lined mu`.
- Displays external tendon `K (/m)` as `N/A` in the station trace because the
  external deviator equation uses `mu(alpha + angle add)` rather than `Kx`.
- Adds `K use` and `mu basis` trace columns so reviewers can see which
  assumption was applied to each row.
- Adds regression coverage proving that external tendon loss ignores the
  internal `Kx` term even if the internal `K` input is changed.
- PTLOSS1B later shortens the `K use`, `mu basis`, and assumptions caption
  wording for better PDF/browser readability without changing this calculation.

#### Scope guard

- This milestone does not add anchorage set, elastic shortening, creep,
  shrinkage, relaxation, SLS, ULS, deviator force, anchorage-zone, D-region,
  report, or solver integration.
- External tendon loss remains a transparent deviator-preview calculation until
  a full deviator table with actual hardware, station, angle, tolerance, and
  stressing sequence data is implemented.

#### Repo summary

Polish Crossbeam Prestress Loss assumptions for HDPE-lined external tendons with conservative mu defaults, N/A external K display, and regression coverage preventing Kx from affecting external deviator loss.

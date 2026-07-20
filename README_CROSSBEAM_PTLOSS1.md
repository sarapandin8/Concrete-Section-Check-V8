### CROSSBEAM.PTLOSS1 - AASHTO Friction/Wobble Loss Foundation

PTLOSS1 adds the first Crossbeam `Prestress Loss` page after `Tendon Profile`.
The page uses Tendon System `Pj` and Tendon Profile station geometry to trace
AASHTO LRFD 5.9.3.2.2b friction/wobble loss at each tendon profile point.

#### What changed

- Adds `concrete_pmm_pro/crossbeam/prestress_loss.py` for AASHTO friction/wobble
  calculations and Project JSON-safe loss settings.
- Adds `Prestress Loss` to the Crossbeam Sections navigation immediately after
  `Tendon Profile`.
- Adds editable assumptions for internal duct `mu`, internal wobble `K (/m)`,
  external deviator `mu`, and external inadvertent angle.
- For the current HDPE-lined external tendon assumption, use `mu = 0.25` as the
  conservative adopted value; AASHTO polyethylene `mu = 0.23` remains a typical
  reference value.
- External tendon station rows treat `K (/m)` as not applicable because the
  AASHTO external deviator expression uses `mu(alpha + angle add)`, not `Kx`.
- Uses the AASHTO internal PT expression
  `Delta fpF = fpj x (1 - exp(-(Kx + mu alpha)))`.
- Converts the AASHTO table default `K = 0.0002 /ft` to about `0.000656 /m`.
- Uses the nearest jacking end for equally tensioned both-end stressing and
  does not double `Pj`.
- Reports station trace rows, per-tendon worst traced station rows, and a loss
  component roadmap.
- Persists PTLOSS1 loss assumptions in a separate
  `crossbeam_prestress_loss_settings` metadata block.

#### Scope guard

- Friction/wobble is calculated; `P after friction` is not final effective
  prestress.
- Anchorage set, elastic shortening, creep, shrinkage, relaxation, SLS, ULS,
  anchorage-zone, deviator-force, D-region, report, and solver integration are
  not implemented in PTLOSS1.
- Existing PTA1 `Pj` force-source arithmetic is unchanged.
- Existing Tendon System and Tendon Profile input schemas remain unchanged.

#### Repo summary

Add a Crossbeam Prestress Loss page with AASHTO LRFD 5.9.3.2.2b friction/wobble station tracing, editable loss assumptions, nearest-end both-jacking handling, and separate Project JSON metadata persistence.

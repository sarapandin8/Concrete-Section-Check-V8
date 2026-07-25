# CROSSBEAM.PTLOSS3B2A — Linear 2D Stressing-Stage Portal-Frame Response Foundation

This milestone starts from the accepted `CROSSBEAM.SECTION-UI1B` baseline and adds an auditable **fixed-base linear 2D Portal-Frame QA kernel** for the Portal Frame Prestressed Crossbeam. It does not release final stressing-stage `f_cgp`, Elastic Shortening, `Pe`, or `Pe_eff`.

## Structural model

- Analysis plane: Crossbeam longitudinal station `s` versus vertical direction.
- Crossbeam: piecewise gross-section Euler-Bernoulli frame elements using the Section/Segment assignment source.
- Columns: physical column stations/heights with gross `EA` and in-plane `EI_perp_s`; bases fixed by the accepted project assumption.
- Mesh stations include:
  - member ends,
  - Section/Segment boundaries,
  - column centerlines,
  - tendon profile points,
  - intermediate stations limited to 0.50 m maximum beam-element length.
- Crossbeam self-weight is derived from assigned gross section area and concrete material density.

## Tendon equivalent-load source

The prestress load case is assembled from:

- accepted tendon profile geometry, and
- accepted `P after Anchorage Set` at each traced station.

For each piecewise tendon segment, endpoint force vectors and eccentric nodal moments are assembled at Crossbeam centroid nodes. The route does **not** restart from `fpj` and does not substitute a generic uniform equivalent load.

## Linear QA load cases

1. `SELF-WEIGHT — PORTAL FRAME ONLY`
2. `PRESTRESS AFTER ANCHORAGE SET`
3. `LINEAR SUPERPOSITION QA`

The UI shows:

- model/source readiness,
- beam/column element counts,
- global force and moment equilibrium residual,
- load-case summary,
- Crossbeam moment diagram,
- axial/shear diagram,
- vertical displacement diagram,
- fixed-base reactions,
- column end actions,
- equivalent tendon-load assembly audit.

## Sign convention

- `u_s`: positive along increasing Crossbeam station `s`.
- `v`: positive upward.
- rotation: positive counterclockwise.
- Crossbeam axial action `N`: compression-positive.
- Crossbeam moment `M`: sagging-positive.
- shear `V = dM/ds` under the adopted beam sign convention.

## Safety boundary

PTLOSS3B2A deliberately excludes:

- continuous full-length compression-only temporary support/contact,
- automatic lift-off iteration,
- final Primary/Secondary Prestress decomposition,
- contact-aware gravity/prestress stressing stage,
- source-derived `f_cgp`,
- final incremental pair-by-pair Elastic Shortening,
- `Pe` / `Pe_eff`,
- Result Summary / Report/QA handoff.

Therefore the new structural response is labeled **linear QA / benchmark only**. It must not be treated as the actual stressing-stage response while falsework contact is active.

## Numerical QA

The new frame kernel is benchmarked against:

- cantilever tip-load closed-form displacement and rotation,
- fixed-fixed beam uniform-load end actions,
- global equilibrium of piecewise tendon equivalent loads,
- complete default Crossbeam self-weight/prestress/superposition cases.

## Production files changed

- `concrete_pmm_pro/crossbeam/stressing_stage_frame.py` — new
- `concrete_pmm_pro/ui/crossbeam_pages.py`

## Tests added

- `tests/test_crossbeam_ptloss3b2a_linear_frame.py`

## Engineering equations not changed

- Friction/Wobble equations unchanged.
- Anchorage Set equations unchanged.
- Existing Elastic Shortening reference equations unchanged.
- No PMM, ULS, SLS, Shear/Torsion, Time-Dependent Loss, Result Summary, or Report/QA equation changed.
- No Project JSON schema or result persistence added.

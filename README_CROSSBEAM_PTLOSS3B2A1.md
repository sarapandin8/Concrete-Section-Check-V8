# CROSSBEAM.PTLOSS3B2A1 — Stage Modulus, Reference-Axis, and Linear QA Hardening

This milestone starts from the accepted `CROSSBEAM.PTLOSS3B2A` baseline and hardens the fixed-base 2D stressing-stage Portal-Frame QA before any compression-only contact or source-derived `f_cgp` release.

## 1. Stressing-stage modulus sources

Crossbeam stiffness no longer uses the 28-day assigned `Ec` while labeling it `Eci`.

For every active Crossbeam Section ID:

- `f'ci = adopted stressing-strength ratio × f'c`
- ACI-auto materials use `Eci = 4700 sqrt(f'ci)` in MPa.
- Manual-`Ec` materials retain the user material basis and use `Eci = Ec(f'c) sqrt(f'ci/f'c)`.
- The default `f'c = 45 MPa`, ratio `0.80` case therefore uses `f'ci = 36 MPa` and `Eci = 28,200 MPa`.

Column stiffness remains a separate source:

- each column `f'c` input is treated as the available stressing-stage column strength;
- `Ec = 4700 sqrt(column f'c)`;
- the UI exposes the column bending axis as `I⊥s = I22`.

Joint/closure concrete strength remains a construction acceptance source only and is not represented as a separate frame stiffness region in this milestone.

## 2. Common reference axis and exact centroidal rigid offsets

Active Solid/Hollow regions may have different centroid depths. PTLOSS3B2A1 now:

- selects a common reference axis at the first active region centroid depth;
- stores each section centroid offset from that reference;
- applies an exact small-displacement rigid-offset transformation at each frame-element end;
- avoids artificial high-stiffness dummy-link elements;
- assembles tendon equivalent loads from the physical tendon elevation relative to the common reference axis.

The UI reports:

- reference Section ID;
- reference centroid depth;
- active centroid spread;
- per-region rigid offset;
- Crossbeam and column `E`, `A`, `I⊥s`, `EA`, and `EI⊥s`.

## 3. Tendon sign and Primary `P·e` audit

The tendon load source still uses accepted `P after Anchorage Set` and never restarts from `fpj`.

PTLOSS3B2A1 adds a separate section-local Primary Prestress reference:

- local eccentricity `e` is positive below the active section centroid;
- Primary moment is shown as `-P·e` with sagging positive;
- a tendon below the centroid therefore produces a negative/hogging Primary moment reference;
- the reference is not substituted for the restrained Portal-Frame solution and does not represent Secondary Prestress.

## 4. Independent analytical benchmarks

The UI and tests include isolated synthetic checks for:

1. straight tendon through centroid: `N = P`, `M = 0`, `v = 0`;
2. straight tendon 200 mm below centroid: `-P·e` sign and cantilever response;
3. symmetric parabolic tendon in a symmetric portal: mirrored `M`, `v`, and base reactions plus global equilibrium.

These benchmark results are diagnostic only and do not feed project results.

## 5. Mesh and station audit

The frame mesh inserts exact nodes at:

- member ends;
- Segment/Section-Zone boundaries;
- column centerlines;
- tendon profile control stations.

An optional diagnostic compares prestress-only linear QA results using target maximum beam-element lengths:

- `0.50 m`
- `0.25 m`
- `0.125 m`

The diagnostic reports changes in maximum `N`, `V`, `M`, and `v`; it is isolated from engineering result state.

## 6. UI and print polish

- Axial force and shear are now separate charts.
- A Primary `-P·e` reference chart is shown for the prestress load case.
- The stage-stiffness/reference-axis audit is grouped in an expander.
- Print CSS avoids splitting alerts, number inputs, dataframes, horizontal input blocks, and expanders at browser page breaks.

## 7. Safety boundary retained

PTLOSS3B2A1 still does **not** release:

- continuous full-length compression-only contact;
- automatic falsework lift-off;
- final gravity + incremental stressing contact state;
- certified Primary/Secondary Prestress decomposition;
- source-derived `f_cgp`;
- final Elastic Shortening loss;
- `P after ES`, `Pe`, or `Pe_eff`;
- Result Summary or Report/QA handoff.

## 8. Production files changed

- `concrete_pmm_pro/crossbeam/stressing_stage_frame.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`

## 9. Tests

- updated `tests/test_crossbeam_ptloss3b2a_linear_frame.py`
- added `tests/test_crossbeam_ptloss3b2a1_hardening.py`

## 10. Unchanged calculation scope

- Friction/Wobble equations unchanged.
- Anchorage Set equations unchanged.
- Published Elastic Shortening reference equations unchanged.
- No PMM, ULS, SLS, Shear/Torsion, time-dependent loss, Result Summary, or Report/QA equation changed.
- No Project JSON schema or result-cache persistence change.

# CROSSBEAM.PTLOSS3B2B2A — Lightweight AASHTO ES Route and On-Demand Advanced QA

## Purpose

Reduce the Crossbeam Elastic Shortening runtime to a practical design workflow. The ordinary route no longer auto-runs the detailed Gravity → G1 → G2 → G3 → G4 construction-stage contact history, synthetic benchmarks, or three-mesh verification whenever Streamlit reruns.

## Ordinary design route

The default Elastic Shortening workflow now runs only when the engineer presses **Run Lightweight ES Analysis**:

1. Build the accepted 2D gross-section Portal Frame model at the normal design mesh.
2. Assemble self-weight and every active Tendon's accepted station-by-station force after Friction and Anchorage Set.
3. Solve one cumulative rigid vertical compression-only contact state.
4. Evaluate concrete stress at the prestressing-steel centroid.
   - **Bonded after grouting:** representative continuous-member sections (span center, column centerlines, and maximum-|M| station between columns); governing compression is used.
   - **Permanently unbonded:** member-length average stress at the prestressing-steel centroid.
5. Apply the AASHTO LRFD 2020 Article 5.9.3.2.3b identical-group sequence factor to the verified simultaneous symmetric stressing groups.
6. Continue the accepted force chain from `P after Anchorage Set` to the Elastic Shortening component and `P after ES` preview; there is no restart from `fpj`.

The lightweight route requires one common explicit final bond system for all active Tendons. Mixed bonded/unbonded systems are blocked for engineer-specific evaluation rather than silently averaged.

## Runtime behavior

- Opening the Elastic Shortening page performs **zero structural solves**.
- Changing display controls or opening result expanders performs **zero structural solves**.
- The normal route performs **one cumulative contact solve** only after the Run button is pressed.
- Results are stored against a solver/input fingerprint and shown as `CURRENT` or `STALE`.
- Clearing the result is explicit.

## Optional Advanced Construction-Stage QA

The accepted detailed solvers remain available under **Advanced Construction-Stage QA — optional and computationally heavy**. They run only after the engineer presses **Run Advanced Construction-Stage QA** and include:

- fixed-base linear load cases;
- linear three-mesh verification;
- gravity-only contact and contact mesh verification;
- cumulative Gravity → G1 → G2 → G3 → G4 contact stages;
- independent final one-shot consistency;
- incremental three-mesh verification.

Synthetic developer benchmarks remain in pytest and are not rerun in the Streamlit user session.

## Default bonded regression reference

With the default eight-tendon example changed explicitly to `Bonded after grouting`:

- structural solve count: `1`;
- final contact: `10 active / 41`, `31 open`;
- cumulative contact complementarity: `PASS`;
- source-derived `f_cgp`: `12.836388669 MPa`;
- average Elastic Shortening loss: `33.285848277 MPa`;
- maximum first-group sequence loss: `66.571696554 MPa`.

These values are new design-route regression evidence. The previously accepted detailed B2B2 G0→G4 solver and its tests are retained unchanged as optional Advanced QA.

## Locked downstream scope

This milestone does not release:

- time-dependent creep, shrinkage, or relaxation losses;
- final `Pe` / `Pe_eff` assembly;
- Result Summary or Report/QA solver credit;
- mixed bond-system automatic routing;
- finite-stiffness falsework, settlement, or interface friction.

## Primary files

- `concrete_pmm_pro/crossbeam/lightweight_elastic_shortening.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`
- `concrete_pmm_pro/crossbeam/construction_stage.py`
- `tests/test_crossbeam_ptloss3b2b2a_lightweight_es.py`

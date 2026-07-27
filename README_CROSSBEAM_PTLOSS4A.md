# CROSSBEAM.PTLOSS4A — Lightweight Time-Dependent Loss Source and On-Demand Preview

## Purpose

Add a source-gated, on-demand AASHTO time-dependent prestress-loss component for Portal Frame Crossbeam without returning to automatic heavy structural analysis.

## Source-to-target audit

The implementation reviewed `Segmental_Box_Girder_Pro_v1.4` and its BG40 Project JSON before changing Concrete Section Pro.

### Reused engineering patterns

- SI-facing inputs with explicit AASHTO ksi/in conversion inside calculation functions.
- Separate creep, shrinkage, and relaxation components.
- Explicit relative humidity, age, drying-perimeter, and steel-class sources.
- Length/area-weighted source trace and guarded downstream handoff.
- On-demand result state with input fingerprinting.

### Intentionally not copied

- BG40 `f_cgp = 36.26 MPa`.
- External/unbonded tendon routing.
- BG40 span-by-span construction ages and `tf = 27,000 days`.
- BG40 box-girder drying perimeter.
- BG40 report-match incremental constants or relaxation interaction cap.
- Any BG40 final Effective Prestress value.

## Crossbeam route

The calculation consumes the stored CURRENT Lightweight Elastic Shortening result and performs zero structural solves.

- `Cast-in-Place`: representative AASHTO LRFD 5.9.3.4.5 nonsegmental post-tensioned route.
- `Precast Segmental`: preliminary representative preview only; final adoption remains subject to construction-schedule time-step analysis under AASHTO LRFD 5.9.3.4.1 and 5.9.3.5.
- `Permanently unbonded` or mixed bond systems: source blocked in PTLOSS4A pending a separately reviewed route.

## Drying geometry

For each active Section / Zone:

- concrete volume = section area × zone length,
- drying surface = (outer perimeter + adopted interior-perimeter fraction × inner perimeter) × zone length,
- member end faces are excluded,
- `V/S = total concrete volume / total exposed longitudinal surface`,
- `h0 = 2V/S` is shown for traceability.

Interior perimeter choices are 0%, 50%, or 100%. The 50% option corresponds to the AASHTO commentary treatment for poorly ventilated enclosed cells.

## Loss components

The component preview uses:

- AASHTO 5.4.2.3.2 creep coefficient `ψ(tf,ti)`, with elapsed time after load application,
- incremental shrinkage strain from the adopted interval start to final time, measured from end of curing,
- bonded-steel interaction coefficient `Kdf` from AASHTO 5.9.3.4.3a-2,
- representative post-ES tendon stress for the AASHTO low-relaxation expression,
- `ΔfpTD = ΔfpCD + ΔfpSD + ΔfpR2`.

The result remains REVIEW when calculated `V/S` exceeds 6.0 in., because that is the maximum ratio identified in the AASHTO commentary development range for the approximate size-factor expressions.

## Runtime and persistence

- Opening the tab: 0 structural solves.
- Changing inputs: no calculation until Run is pressed.
- Run: arithmetic-only use of stored post-ES source data.
- Project JSON schema version: 6.
- Project JSON stores only Time-Dependent inputs, not calculated results or fingerprints.
- Effective Prestress / `Pe` / `Pe_eff` assembly remains locked.

## Default regression evidence

With the accepted default Crossbeam model, bonded-after-grouting Tendons, RH = 75%, `ti = 28 days`, curing end = 7 days, `tf = 18,250 days`, and 50% interior perimeter:

- `V/S = 323.386 mm = 12.732 in.` — REVIEW outside commentary development range,
- `Kdf = 0.8942766`,
- creep loss = `78.3698 MPa`,
- shrinkage loss = `40.8906 MPa`,
- relaxation loss = `7.8887 MPa`,
- Time-Dependent subtotal = `127.1491 MPa`,
- structural solves = `0`.

These are regression values for this model and are not universal defaults.

## Not changed

- Friction/wobble equations and results.
- Anchorage-set equations and results.
- Lightweight Elastic Shortening FEA/contact result.
- Advanced Construction-Stage QA.
- Project geometry, section, tendon, or rebar schemas.
- Result Summary and Report / QA solver credit.
- Effective Prestress assembly.

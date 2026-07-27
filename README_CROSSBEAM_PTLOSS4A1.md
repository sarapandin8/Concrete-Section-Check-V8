# CROSSBEAM.PTLOSS4A1 — Variable-Section V/S Routing and Audit Visibility Hardening

## Purpose

Clarify how the lightweight Crossbeam time-dependent-loss preview treats members containing both Solid and Hollow Section/Zone regions, and make the calculation sources readable in normal UI and browser-print review without changing the accepted PTLOSS4A loss equations or regression values.

## Member-equivalent and local V/S

The AASHTO preview input is the member-equivalent ratio:

`V/S = Σ(Ai Li) / Σ(udry,i Li)`

where each Section/Zone retains its own:

- gross concrete area,
- outer perimeter,
- interior perimeter,
- adopted interior exposure factor,
- exposed drying perimeter,
- local `V/S = Ac / udry`, and
- local specification size factor `ks`.

The UI explicitly states that the member-equivalent V/S is not the arithmetic average of the Solid and Hollow local values.

For the accepted default model with 50% interior-void exposure:

- Hollow local V/S = `8.185 in.`,
- Solid local V/S = `18.773 in.`,
- member-equivalent V/S = `12.732 in.`.

## Commentary-range semantics

`V/S > 6.0 in.` is now treated as an AASHTO Commentary calibration-range advisory, not a hard Specification code failure.

- The Specification lower bound `ks = 1.0` remains applied.
- The UI recommends engineering review or project-specific material data when accurate intermediate-age behavior is important.
- The advisory by itself no longer blocks the Cast-in-Place nonsegmental representative route.
- Precast Segmental remains preliminary and non-adoptable because a construction-schedule time-step route is still required for final adoption.

## Audit presentation

The Time-Dependent calculation trace now shows:

1. local Section-type drying geometry,
2. local Solid/Hollow V/S and `ks`,
3. Section/Zone concrete-volume and drying-surface contributions,
4. high-precision shrinkage strain in decimal and microstrain,
5. a readable representative-section / bonded-interaction table instead of a collapsed JSON object.

## Numerical scope

No accepted numerical result changed for the default Precast Segmental regression model:

- creep loss = `78.369843 MPa`,
- shrinkage loss = `40.890590 MPa`,
- relaxation loss = `7.888682 MPa`,
- Time-Dependent subtotal = `127.149115 MPa`,
- structural solves = `0`.

## Not changed

- AASHTO creep, shrinkage, relaxation, or `Kdf` equations.
- Drying-perimeter exposure choices.
- Friction/Wobble, Anchorage Set, or Elastic Shortening results.
- Project JSON schema or persistence behavior.
- Effective Prestress assembly or downstream handoff.
- Result Summary or Report / QA solver credit.

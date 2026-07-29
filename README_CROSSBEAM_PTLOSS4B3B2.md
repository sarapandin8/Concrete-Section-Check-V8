# CROSSBEAM.PTLOSS4B3B2 — Stressing-Strength Source Guard and No-Event TD Regression

## Purpose

Repair the deployed `f'ci/f'c = 0.10` legacy widget/state fallback before it can feed Elastic Shortening or Time-Dependent loss calculations.

## Changes

- Keeps the established design default `f'ci/f'c = 0.80`.
- Migrates legacy/invalid stored values below `0.50` to `0.80` on session initialization and Project JSON restore.
- Changes the editable widget lower bound from `0.10` to `0.50`.
- Adds core solver/source guards so a direct low-ratio call is blocked instead of producing a very low `Eci` and inflated losses.
- Shows `f'c`, adopted ratio, `f'ci`, and `Eci` cards on Time-Dependent.
- Corrects no-event runtime wording to `tg → tr → tf` and `no permanent-load events`.
- Adds a no-permanent-event regression against the accepted result: creep ≈ 78.37 MPa, shrinkage ≈ 40.89 MPa, relaxation ≈ 7.89 MPa, TD subtotal ≈ 127.15 MPa.

## Engineering boundary

No AASHTO creep, shrinkage, relaxation, friction, anchorage-set, or elastic-shortening equation was changed. This milestone repairs source-state integrity and prevents an invalid stressing-strength input from reaching the accepted equations.

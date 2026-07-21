# CROSSBEAM.PTLOSS2B - Anchorage Set Decision View + Formula & SI Unit Audit

## Scope

Polishes the Crossbeam `Prestress Loss` workspace around the accepted PTLOSS2 anchorage-set preview and adds explicit formula/unit audit evidence for both friction/wobble and anchorage set. The milestone keeps `Pe / Pe_eff`, elastic shortening, time-dependent losses, PMM, SLS/ULS, rebar, reports, and all other member workflows unchanged.

## Engineering decisions

- New-project/default anchorage set is `Δa = 6.00 mm` as a **user-editable design assumption**, not an AASHTO-mandated value.
- The UI explicitly instructs the engineer to verify/replace `Δa` using the approved PT system / anchorage supplier data before final design use.
- A user may set `Δa = 0`; this intentionally disables the anchorage-set preview and returns `INPUT REQUIRED` rather than reporting a false zero loss.
- `Pe / Pe_eff` remains locked. Anchorage-set output remains component-scoped preview/audit data only.

## Friction / wobble formula and unit audit

The accepted PTLOSS1 solver equations are unchanged.

For internal tendons the app exposes:

`P(x) = Pj exp[-(Kx + μ α)]`

`ΔfpF = fpj [1 - exp(-(Kx + μ α))]`

The app now shows the unit conversion that is otherwise easy to hide in code:

- accepted PTLOSS1 reference wobble coefficient: `K = 0.0002 /ft` (project/PT-system value must remain engineer-verifiable);
- `1 m = 3.280839895 ft`;
- converted SI reference: `K = 0.000656167979... /m`;
- therefore `K(/m) × x(m)` is dimensionless;
- `μ` is dimensionless and `α` is in radians, so `μ α` is dimensionless.

A representative governing active station is recomputed independently for the audit panel. The displayed audit checks that recomputed exponent and post-friction stress reproduce the accepted PTLOSS1 row to numerical tolerance.

For the current external-tendon preview the UI also exposes the implemented expression using the accepted deviator angular change plus the adopted inadvertent-angle addition. No `Kx` term is used for the current external preview.

## Anchorage-set formula and SI unit audit

The anchorage-set solver equation is unchanged. PTLOSS2B exposes the actual compatibility formulation used by the code rather than presenting it as a verbatim numbered AASHTO equation.

Using the accepted post-friction stress diagram and the mirrored-diagram preview:

`Δa = (1000 / Ep) ∫[fbefore(x) - fafter(x)] dx`

with

`fafter(x) = 2 fbefore(La) - fbefore(x)` for `0 ≤ x ≤ La`,

which is evaluated as:

`Δa = (2000 / Ep) [∫ fbefore(x) dx - La fbefore(La)]`

when `x` and `La` are integrated in metres and stress / `Ep` are in MPa. The factor `1000 mm/m` converts the final movement to millimetres.

Dimensional audit displayed by the app:

- `(MPa·m / MPa) × 1000 mm/m = mm` for anchorage movement;
- `Aps(mm²) × f(MPa = N/mm²) / 1000 = P(kN)` for tendon force.

For the governing calculated seating end the app displays substituted values for `Δa`, `Ep`, `La`, stress integral, zero-movement stress, one-side stress area, mirrored stress-difference area, calculated movement, and compatibility residual.

## Decision-view polish

The `Anchorage Set / Draw-in` main view now prioritizes engineering decisions:

- `Worst local loss` and `Max influence length` show `— / NOT CALCULATED` if no valid solution exists instead of misleading `0.000` values;
- a compact one-row-per-tendon decision summary shows status, jacking arrangement, seating ends, adopted `Δa`, maximum local loss, maximum influence length, and minimum lock-off force;
- detailed seating-end compatibility data is moved to a collapsed expander;
- detailed station trace is moved to a collapsed expander;
- repeated review/limitation text is summarized by unique issue/note counts, with the per-end table retained in a collapsed expander;
- formula/source/SI-unit audits are collapsed by default to preserve a clean commercial decision view.

## Validation

### Friction/wobble unit conversion

Regression explicitly verifies:

`0.0002 /ft × 3.280839895 ft/m = 0.000656167979... /m`

and round-trips the converted value back to `0.0002 /ft` within floating-point tolerance.

### Friction/wobble substituted equation

A dedicated audit test recomputes the governing station exponent and `P/Pj` from the displayed terms and requires exact agreement with the accepted PTLOSS1 station row to numerical tolerance.

### Anchorage-set closed-form hand check

The accepted linear benchmark remains:

- `f(x) = 1400 - 10x MPa`;
- `Ep = 200,000 MPa`;
- adopted `Δa = 5.0 mm`.

At the closed-form solution `La = 10.0 m`:

- `∫ f(x) dx = 13,500 MPa·m`;
- `La f(La) = 13,000 MPa·m`;
- one-side area = `500 MPa·m`;
- mirrored stress-difference area = `1,000 MPa·m`;
- `Δa = 1000 × 1000 / 200000 = 5.000 mm`.

The solver reproduces these values and closes the compatibility residual to numerical tolerance.

## Changed production files

- `concrete_pmm_pro/crossbeam/prestress_loss.py`
  - changes the new/default anchorage-set assumption to `6.00 mm`;
  - adds formula/unit audit helpers only;
  - accepted friction/wobble solver equations remain unchanged.
- `concrete_pmm_pro/crossbeam/anchorage_set.py`
  - adds audit-only intermediate values needed to expose the existing compatibility calculation;
  - anchorage-set solution equations remain unchanged.
- `concrete_pmm_pro/ui/crossbeam_pages.py`
  - adds formula/source/SI-unit audit expanders and decision-view polish.

## Changed tests

- `tests/test_crossbeam_ptloss1_aashto_friction.py`
- `tests/test_crossbeam_ptloss2_anchorage_set.py`

No changes were made to `app.py`, shared routing, PMM, SLS/ULS, ordinary rebar, other prestress workflows, report logic, or other member-workflow production modules.

## Verification results

- `python -m compileall -q app.py concrete_pmm_pro`: PASS.
- PTLOSS1/PTLOSS2 targeted regression: `22 passed`.
- Complete Crossbeam regression: `210 passed`.
- Selected cross-workflow/project IO/prestress/serviceability/report smoke: `131 passed`.
- A one-process non-Crossbeam suite run timed out at about 40% with no failure encountered before timeout.
- Four known pre-existing non-Crossbeam stale tests were rerun and fail identically on the accepted PTLOSS2A baseline; they remain out of scope and were not modified.
- Live Streamlit render/import smoke was not run because `streamlit` is not installed in the execution runtime.

## Repo summary

Add Crossbeam PTLOSS2B anchorage-set decision-view polish plus transparent friction/wobble and draw-in formula/SI-unit audits while preserving accepted solver equations and other member workflows.

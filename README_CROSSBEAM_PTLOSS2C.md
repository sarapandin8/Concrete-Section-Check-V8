# CROSSBEAM.PTLOSS2C - Full-Length Both-End Anchorage Seating Interaction

## Scope

PTLOSS2C extends the Crossbeam `Anchorage Set / Draw-in` component so a both-end tendon can be evaluated beyond the independent half-length seating limit without changing the accepted PTLOSS1 friction/wobble force result or releasing final effective prestress.

The milestone remains a **component-scoped preview**. It does not assemble `Pe` / `Pe_eff`, elastic-shortening loss, time-dependent loss, SLS/ULS checks, anchorage-zone design, or D-region design.

## Engineering basis and boundary

- Anchorage seating/set remains an instantaneous prestress-loss component.
- The existing local solution first applies the accepted force-diagram compatibility / mirrored-profile method independently from each active stressing end.
- For `Jack = Both`, if the adopted seating movement exceeds the independent half-length capacity, PTLOSS2C may activate a guarded **full-length coupled** final-state compatibility solution.
- The coupled formulation is an engineering implementation extension of the FHWA graphical mirror-image / area-compatibility concept; it is **not** presented as a verbatim numbered AASHTO equation.
- The same adopted `Δa` is currently applied at both ends in the coupled preview.
- Explicit first-end / second-end stressing order, intermediate jack force history, re-jacking, staged seating, and project-specific PT procedures are not simulated and remain design/procedure review items.

## Accepted friction source remains protected

PTLOSS2C adds full left- and right-jacking branch traces to the PTLOSS1 station audit source:

- `Stress from left jack (MPa)`
- `Stress from right jack (MPa)`
- corresponding exponents and forces

These are additive trace fields only. The accepted PTLOSS1 nearest-end `Stress after friction`, `P after friction`, source-end selection, friction equation, and `K / μ / α` logic remain unchanged.

## Coupled both-end formulation

Let:

- `f_i(s)` = accepted pre-seating tendon stress profile,
- `f_L(s)` = left-jacking friction branch,
- `f_R(s)` = right-jacking friction branch,
- `s_n` = zero-displacement neutral / meeting station,
- `f_n` = common final meeting stress after seating.

The final reverse-slip branches are represented as:

```text
Left : f_after,L(s) = f_n + f_L(s_n) - f_L(s),   0 <= s <= s_n
Right: f_after,R(s) = f_n + f_R(s_n) - f_R(s),   s_n <= s <= L
```

The solution closes seating compatibility at both ends:

```text
Δa_L = (1000 / Ep) ∫[0..s_n] (f_i - f_after,L) ds
Δa_R = (1000 / Ep) ∫[s_n..L] (f_i - f_after,R) ds
```

with continuity:

```text
f_after,L(s_n) = f_after,R(s_n) = f_n
```

The `1000` factor converts the integration coordinate from metres to millimetres when stress and `Ep` are in MPa.

## Guardrails

A coupled result is not accepted unless the implementation can satisfy the required QA conditions, including:

- a valid unique neutral-station solution,
- left and right seating compatibility within tolerance,
- force/stress continuity at the meeting station,
- no negative final tendon stress,
- no stress gain above the accepted pre-seating post-friction profile.

If these conditions are not satisfied, the component remains `REVIEW` rather than forcing a numerical loss result.

## Validation benchmarks

### Symmetric hand-solvable overlap case

For a 20 m tendon with symmetric linear left/right jacking branches, `Ep = 200,000 MPa`, and `Δa = 6 mm` at both ends, where each independent 10 m half-branch can accommodate only 5 mm:

- neutral station `s_n = 10.000 m`,
- meeting stress after seating `f_n = 1280 MPa`,
- lock-off stress at each anchorage `= 1180 MPa`,
- left compatibility `= 6.000 mm`,
- right compatibility `= 6.000 mm`,
- continuity residual approximately zero,
- no stress gain and no negative final stress.

The station trace is symmetric: approximately 1180, 1230, 1280, 1230, and 1180 MPa at 0, 5, 10, 15, and 20 m.

### Default Crossbeam case

With the current default 8-tendon Crossbeam, `Jack = Both`, `Δa = 6.00 mm`, and `Ep = 195,000 MPa`, the PTLOSS2C regression benchmark resolves all 16 seating ends with `FULL-LENGTH COUPLED` status and closes the seating compatibility checks within tolerance. This is still a preview result subject to the explicit stressing-sequence limitation above.

## UI / audit changes

The Anchorage Set decision view now distinguishes `ISOLATED LOCAL` from `FULL-LENGTH COUPLED` results and exposes the neutral station, meeting stress, isolated-branch capacity, compatibility residuals, continuity check, stress-gain check, and minimum-final-stress check in the detailed audit/formula sections.

## Changed files

Production:

- `concrete_pmm_pro/crossbeam/anchorage_set.py`
- `concrete_pmm_pro/crossbeam/prestress_loss.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`

QA:

- `tests/test_crossbeam_ptloss1_aashto_friction.py`
- `tests/test_crossbeam_ptloss2_anchorage_set.py`

Documentation:

- `README.md`
- `README_CROSSBEAM_PTLOSS2C.md`

## Verification

- Targeted PTLOSS1/PTLOSS2C regression: passed.
- Complete Crossbeam regression: `216 passed`.
- Non-Crossbeam split regression: `1,834 passed / 4 failed`; the four failures are the same known pre-existing stale QA debts from the accepted baseline and are outside this milestone scope.
- No PMM, SLS/ULS, rebar, report, shared routing, or other member-workflow solver changes were made.
- Live Streamlit rendering was not executed in the development runtime if `streamlit` is unavailable; source/compile/test verification does not replace visual runtime QA.

## Repo summary

Add Crossbeam PTLOSS2C guarded full-length both-end anchorage-seating compatibility using accepted left/right friction branch traces while keeping explicit stressing sequence and Pe/Pe_eff locked.

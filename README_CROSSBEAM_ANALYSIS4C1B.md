# CROSSBEAM.ANALYSIS4C1B — Actionable Torsion Source Guidance

## Purpose

Make the Combined Reinforcement Preview tell the engineer exactly what to do when the outer torsion cage has not yet been defined or verified, instead of showing a generic `SOURCE BLOCKED` message.

## Change

When an outer torsion cage is present but its closure has not been verified:

- the `Outer torsion cage — At` card shows `VERIFY CLOSED LOOP`;
- the card directs the user to `Rebar → Transverse / Shear → Outer torsion cage source`;
- the instruction says to set `Closure = Verified closed loop` and apply the table;
- the `Longitudinal torsion — Aℓ` card shows `Aℓ CREDIT PENDING`;
- the card states that the outer bars have been identified, but Aℓ credit remains pending until the cage is verified;
- a visible warning banner repeats the exact navigation and action.

When no outer torsion cage has been defined:

- the At card shows `DEFINE OUTER CAGE`;
- the Aℓ card shows `Aℓ CREDIT UNAVAILABLE`;
- the warning directs the user to define Bar, Spacing, Relationship, and Closure, then apply the table.

When the cage is verified, the existing green adopted At and Aℓ summaries remain unchanged.

## Engineering behavior

- No reinforcement quantity or cage geometry is changed.
- No Shear, Torsion, Combined V+T, or Direct P–M3 equation is changed.
- No Project JSON schema or persistence behavior is changed.
- The warning remains a source-adoption instruction; it does not certify hook, lap, anchorage, or construction detailing automatically.

## Tests

- Compileall: PASS.
- Targeted source-contract, As/Aℓ summary, transverse template, and Project JSON tests: 25 passed.
- Crossbeam Rebar regression: 115 passed; one pre-existing assertion still expects 7 data editors while the accepted ANALYSIS4C1 line contains 8.

## Repo summary

Replace generic torsion source-blocked messages with direct instructions to define or verify the outer closed cage and automatically unlock Aℓ credit.

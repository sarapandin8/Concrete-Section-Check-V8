# CROSSBEAM.SLS1D.PRINT.CLOSEOUT

## Scope

Close the remaining Crossbeam SLS browser-PDF presentation defects identified in the reviewed Transfer and Final Service exports.

## Changes

- Show the full workflow-compatible design-code edition (`ACI 318-19`) on the Analysis context card.
- Separate coincident `Gov. tension` and `Gov. joint` chart labels without changing governing points or engineering results.
- Render Transfer and Final required-action tables as wrapping, print-safe HTML.
- Split the wide Transfer calculation audit into source, force/property, and stress/criteria tables so right-side values remain present and readable in PDF output.
- Exclude Developer diagnostics from browser printing even when its expander is open.

## Preserved behavior

- No SLS, ULS, prestress-loss, section-property, or joint-interpolation equations changed.
- No Project JSON schema, result-cache, load-source, or stage-routing behavior changed.
- Class C remains gross classification complete with separate cracked transformed-section verification required.

## Repo summary

Close Crossbeam SLS print defects with edition-correct code labeling, collision-free governing markers, wrapping audit tables, and print-excluded developer diagnostics.

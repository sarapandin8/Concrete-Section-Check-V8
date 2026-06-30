# ANCHORAGE.RAIL.UGIRDER1 — Railway U-Girder Anchorage / End-Zone Evidence

## Purpose

Add guarded anchorage/end-zone bursting and spalling evidence for the Railway U-Girder workflow after `PRESTRESS.DEVELOPMENT1`.

This milestone is an engineering-review evidence layer only. It is not final code-certified design and is not an Engineer-of-Record certification.

## Implemented evidence

- Reads the active Railway U-Girder strand/debonding table.
- Separates bonded end strands from debonded/sleeved strands at the left and right ends.
- Computes a visible end-zone prestress transfer force screen.
- Reports debonded sleeve-termination force separately from end-face bonded force.
- Computes a guarded bursting tie demand using `Tb = 0.25P`.
- Computes required end-zone and sleeve-termination tie steel using displayed `φfy`.
- Reports a concrete stress preview using total web area and web `fci`.
- Adds the anchorage/end-zone table to report registry and Word report export.
- Updates the Railway U-Girder ULS check matrix so anchorage/end-zone is no longer hidden as a pure future item.

## Deliberate limitations

- No final anchorage-zone reinforcement design.
- No strut-and-tie model generation.
- No project-specific end-region finite-element analysis.
- No final debonded strand sleeve-termination detailing validation.
- No SLS solver equations changed.
- No ULS flexure/shear/torsion equations changed.
- No prestress/debond station-participation logic changed.
- No force-ramp integration into the solvers.
- No project schema changed.

## Allowed wording

Use:

```text
Engineering-review evidence
Review / reinforcement layout required
Not final code-certified design
```

Do not use:

```text
Final Code-Certified PASS
Engineer-certified anchorage design complete
Final end-zone design complete
```

## Final certification blockers still remaining

- Project-specific anchorage-zone reinforcement detailing.
- End-zone benchmark validation.
- Debonded strand sleeve-termination detailing validation.
- Local bursting/spalling strut-and-tie or equivalent project-specific model.
- Engineer-of-Record review and sign-off.

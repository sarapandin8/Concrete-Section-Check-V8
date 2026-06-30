# ULS.RAIL.UGIRDER1 — Railway U-Girder ULS Strength Check Framework

## Purpose

This milestone starts Phase 2 after the Railway U-Girder SLS closeout package. It adds a guarded Railway U-Girder ULS strength-check framework for engineering review, demand traceability, code-basis boundaries, and final-design readiness planning.

## Status

Railway U-Girder ULS is **framework-ready for engineering review**. It is **not final code-certified design** and is not an engineer certification.

## Implemented scope

- Detect Railway U-Girder context.
- Read active ULS station-resultant rows from Loads / `beam_uls_loads_table`.
- Build ULS demand summary rows for Mux, Vuy, Tu, Muy, Vux, and Nu.
- Build ULS code-basis table using the Bridge Beam/Girder AASHTO LRFD route.
- Build ULS check matrix covering flexure, shear, torsion, combined V+T, prestress development/anchorage, and certification boundary.
- Register ULS framework tables in the report table registry.
- Add a guarded ULS framework section to the draft Word report.
- Add Report / QA preview panel for Railway U-Girder ULS framework tables.

## Explicit non-scope

No SLS solver equations were changed. No ULS solver equations were certified by this milestone. No prestress, debonding, section-property, PMM, shear, torsion, or load-combination equations were modified.

The following remain future work before final certification can be claimed:

- Railway U-Girder section-type-specific flexure validation.
- PSC shear route including prestress effects, dv policy, and end-region checks.
- Railway U-Girder torsion and combined V+T interaction.
- Transfer length force ramp.
- Development length and debonded strand anchorage.
- Anchorage / end-zone bursting and spalling.
- Lifting insert / local hardware check.
- Creep/shrinkage and time-dependent composite redistribution.
- Independent benchmark examples and final design report traceability.

## Wording guard

Allowed wording:

- Framework-ready for engineering review.
- Guarded ULS review.
- Not certified.

Do not claim final code-certified design, final-design pass wording, engineer certification, or software certification from this milestone.

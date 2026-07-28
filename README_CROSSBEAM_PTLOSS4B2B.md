# CROSSBEAM.PTLOSS4B2B — Event-Response Source Verification

This milestone hardens the Precast Segmental event-based Time-Dependent loss route without changing the accepted creep, shrinkage, relaxation, Elastic Shortening, contact, or frame equations.

## Scope

- Verifies that the falsework-removal event uses a newly solved no-contact response rather than reusing the stored post-ES contact response.
- Stores compact SHA-256 response fingerprints for the contact and released states.
- Compares matched element/station response rows for moment, axial force, shear, vertical displacement, and concrete stress at the Tendon CG.
- Exposes the event-specific governing representative source with station, element-side limit, Section ID, N/A, -Myp/I, engineer-entered later-load delta fcd, and fcgp.
- Blocks the event source when active falsework carries compression reaction but the released response is unchanged within tolerance.
- Clarifies that an unchanged governing fcgp can coexist with meaningful response redistribution when the same representative limit row remains governing.
- Updates construction-schedule wording and the Time-Dependent footer to the current PTLOSS4B2B scope.
- Adds print-oriented event audit tables and reduces the event expander's print-bottom spacing.

## Regression model evidence

- Post-ES compression contact: 10 active / 41 candidate nodes.
- Total falsework reaction before release: 2,976.292 kN.
- Maximum stationwise response changes after release:
  - |Delta M| = 2,933.599 kN-m.
  - |Delta N| = 427.643 kN.
  - |Delta V| = 1,506.983 kN.
  - |Delta v| = 2.255574 mm.
  - |Delta fcgp| = 0.608853 MPa.
- The scalar governing fcgp remains 12.836389 MPa within numerical tolerance because the same right-column, right-side limit row remains governing.
- Result status: `RESPONSE EFFECT VERIFIED — GOVERNING f_cgp UNCHANGED`.

## Locked boundaries

- Later permanent-load delta fcd remains engineer-entered until a verified Loads-workspace source is connected.
- Relaxation remains one final AASHTO R2 term and is not time-resolved.
- Fully coupled creep redistribution is not implemented.
- Pe / Pe_eff assembly, Result Summary, and Report / QA handoff remain locked.
- Project JSON schema and result-persistence behavior are unchanged.

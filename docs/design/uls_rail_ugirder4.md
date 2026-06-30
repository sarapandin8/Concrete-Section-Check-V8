# ULS.RAIL.UGIRDER4 — Railway U-Girder Torsion / V+T Guard Evidence

## Scope

This milestone adds guarded Railway U-Girder ULS torsion and combined V+T evidence to the existing Railway U-Girder ULS framework.

The route consumes:

- active ULS station-resultant rows from Loads (`Tu`, `Vuy`),
- active closed-hoop transverse zones from the Rebar/Transverse source table,
- ordinary longitudinal rebar as the single source of truth for torsion `Al`,
- Railway U-Girder geometry for guarded outside-perimeter and closed-hoop path estimates,
- the ULS.RAIL.UGIRDER3 shear evidence table as the V source for combined V+T review.

## Evidence added

The exported table `railway_u_girder_uls_torsion_vt_guard` includes:

- torsion threshold screen `φTcr`,
- guarded closed-hoop `φTn`,
- torsion D/C,
- shear D/C handoff,
- linear V+T review index,
- closed-hoop `At/s` provided and required,
- longitudinal torsion `Al` required and provided,
- closed-hoop spacing/detailing status,
- explicit blocked final-claim wording.

## Guardrails

This is engineering-review evidence only. It is not final code-certified design and is not engineer certification.

The following remain blockers for final certification:

- dedicated Railway U-Girder closed torsion-cell / multi-cell calibration,
- refined PSC torsion effects,
- calibrated code-specific V+T interaction,
- transfer/development length,
- anchorage/end-zone bursting and spalling,
- independent benchmark validation,
- Engineer-of-Record review.

## Non-scope

No SLS solver equations, PMM solver equations, flexure/shear solver equations, prestress/debond participation logic, geometry generator, load-combination equation, project schema, or report certification wording were modified.

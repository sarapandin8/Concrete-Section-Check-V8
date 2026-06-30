# ULS.RAIL.UGIRDER2 — Railway U-Girder Flexure Calculation Evidence

## Purpose

This milestone advances the Railway U-Girder Phase 2 ULS workflow from a pure framework/check-matrix into guarded flexure section-strength calculation evidence.

It is still **not final code-certified design** and is not an engineer certification.

## Implemented

- Adds `railway_u_girder_uls_flexure_evidence_dataframe()`.
- Consumes active ULS station-resultant rows from the Loads table.
- Uses nonzero `Mux` station rows for flexure evidence.
- Builds a section-strength `AnalysisInput` from:
  - Railway U-Girder section geometry,
  - active concrete material or Railway U-Girder web `f'c`,
  - dedicated girder strand-layout participation at the demand station,
  - current PMM / strain-compatibility engine.
- Routes Bridge prestressed flexure through the existing AASHTO LRFD prestressed flexure phi layer.
- Adds a report/Word table named `Railway U-Girder ULS Flexure Calculation Evidence`.
- Keeps wording limited to `Engineering Review PASS` / `Engineering Review FAIL` / `REVIEW`.

## Guardrails

The calculation evidence is intentionally guarded because the current engine still has certification blockers:

- Railway U-Girder-specific benchmark validation is not complete.
- Transfer length and development length are not complete.
- Anchorage / end-zone bursting and spalling checks are not complete.
- Differential web/slab material modeling is represented as a single-material PMM evidence model in this milestone.
- Time-dependent composite redistribution is not complete.
- Shear, torsion, and combined V+T are not certified by this milestone.

## Non-goals

No SLS solver equations were changed.
No ULS solver equations were changed.
No prestress/debond participation logic was changed.
No PMM solver equation was changed.
No shear, torsion, V+T, load-combination, project-schema, or geometry-generator logic was changed.

## Allowed decision wording

Allowed:

```text
Engineering Review PASS
Engineering Review FAIL
REVIEW
```

Not allowed:

```text
Code-Certified PASS
Final Design PASS
Engineer-Certified PASS
```

## Next recommended milestones

- `ULS.RAIL.UGIRDER3` — Railway U-Girder PSC Shear Route
- `ULS.RAIL.UGIRDER4` — Railway U-Girder Torsion / V+T Guard
- `PRESTRESS.DEVELOPMENT1` — Transfer / Development Length
- `ANCHORAGE.RAIL.UGIRDER1` — End-Zone / Bursting Review
- `VALIDATION.RAIL.UGIRDER1` — Independent benchmark examples

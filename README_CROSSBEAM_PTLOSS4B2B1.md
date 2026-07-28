# CROSSBEAM.PTLOSS4B2B1 — Code-Route and Event-Audit Semantic Cleanup

Clarifies the accepted PTLOSS4B2B event-source verification without changing the structural solver or time-dependent-loss results.

## Scope

- Shows a Precast Segmental-specific AASHTO refined-framework trace instead of presenting the nonsegmental Article 5.9.3.4.5 route as the active basis.
- Retains Article 5.9.3.4.5 only for the Cast-in-Place / nonsegmental construction route.
- Labels response audit values as stage maxima versus maximum stationwise changes.
- Renames the stress-change row to show that its before/after values come from the row with maximum stationwise change.
- Exposes raw governing-event axial force N and bending moment M before the derived N/A and -My/I stress components.
- Updates milestone/footer wording to PTLOSS4B2B1.

## Locked behavior

- One falsework-removal structural solve.
- Accepted frame/contact formulations and tendon equivalent loads.
- Creep, shrinkage, relaxation, Kdf, V/S, and schedule equations.
- Project JSON schema version 8.
- Effective Prestress, Result Summary, and Report/QA handoffs remain locked.

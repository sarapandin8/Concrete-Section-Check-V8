# CROSSBEAM.ANALYSIS4C7D20 — Global ULS + SLS Report Aggregation Closeout

## Scope

This milestone hardens Result Summary / Report-QA executive aggregation after Crossbeam SLS Stress & Cracking was integrated.

### Changes

- Crossbeam global executive criticality no longer compares ULS strength D/C numerically against SLS stress/joint utilization.
- Within the same severity class, ULS strength is the executive critical domain before SLS; existing ULS Torsion vs Combined V+T tie semantics are preserved.
- Result Summary and Report / QA expose separate **Critical ULS** and **Critical SLS** cards.
- Crossbeam failing-check summaries list ULS and SLS failures together; SLS failures are described by actual stress versus limit rather than by a cross-domain D/C ranking.
- If a FAIL exists while ULS or SLS result packages are missing/stale, executive and report-readiness detail now states that incompleteness explicitly instead of silently presenting only the active domain.
- Deflection / Camber remains explicitly pending and is not promoted to PASS.

## Engineering impact

No ULS or SLS solver equations, demand/capacity calculations, prestress handling, reinforcement credit, physical-joint criteria, or source routing were changed.

# IGIRDER.ULS6E — Standalone Torsion Coverage / Detailing Semantic Closeout

## Scope

This milestone closes the two remaining standalone Precast I-Girder torsion QA issues found after ULS6D full-capacity visual review:

1. a covered-station transverse strength failure could visually mask missing torsion-reinforcement coverage elsewhere in the member; and
2. the Analysis status wording used one generic `detailing` label even though transverse closed-hoop detailing and longitudinal corner detailing have different ownership.

The AASHTO threshold, `Veff`, General Procedure, `Tn`, `phiTn`, automatic `ph`, support-face station treatment, and transverse reinforcement equations are unchanged from ULS6D.

## 1. Explicit torsion-zone coverage gate

Every physical station with `Threshold status = DESIGN REQUIRED` is now checked independently for a torsion-qualified transverse source.

A station is coverage-ready only when its provided transverse zone has:

- `Use for Torsion` enabled,
- `Closed Loop` confirmed,
- `135 deg Hook` confirmed, and
- a finite automatically derived `ph` from the active section/cover/bar geometry.

The stored torsion package includes a `torsion_coverage_summary` reporting:

- required design-station count,
- covered design-station count,
- uncovered station list, and
- a separate coverage status.

A transverse strength FAIL at one covered station does not erase or hide uncovered design-required stations elsewhere. Analysis reports both conditions when they coexist.

## 2. Detailing semantics split by ownership

Standalone Torsion now reports these concepts separately:

- **Transverse strength** — `Tu / phiTn` and required `At/s`;
- **Hoop detailing** — closed-loop source, hook, spacing/minimum/detailing gates;
- **Torsion-zone coverage** — whether every design-required station is covered by a qualified source;
- **Corner longitudinal detail** — explicit bar/tendon-at-corner confirmation; and
- **Longitudinal strength** — still `COMBINED CHECK REQUIRED`, owned by the future concurrent Shear + Torsion Article 5.7.3.6.3-1 check.

The Transverse Rebar card now reports `NOT CONFIRMED` when torsion zones are selected but the corner longitudinal detail checkbox is not confirmed; it no longer labels that condition generically as `COMBINED CHECK`.

## 3. Analysis / audit / Report-QA behavior

The compact Torsion audit now includes:

- Threshold
- Coverage
- Transverse
- Longitudinal
- Hoop detailing
- Corner detail

The detailed audit retains the full stored engineering trace.

The Torsion status card explicitly states coverage completeness and does not use a generic `detailing PASS` phrase for the entire torsion system.

Report / QA reads the stored coverage summary and reports torsion-zone coverage, hoop detailing, corner-longitudinal detail, and longitudinal-strength status separately without rerunning the solver.

## 4. Result/cache ownership

Current result versions:

- Torsion: `IGIRDER.ULS6E.torsion-coverage-detailing-closeout`
- Shear + Torsion dependency: `IGIRDER.ULS6E.combined-vt-longitudinal-pending`

Standalone Shear remains on the accepted ULS5 family. Flexure and Girder-Deck Interface Shear result ownership is unchanged.

## 5. Remaining certification boundary

Standalone Torsion may certify the AASHTO threshold and transverse torsion component only. If torsion is above threshold and the transverse component passes with complete coverage/detailing, final solid prestressed longitudinal acceptance still remains a concurrent Shear + Torsion Article 5.7.3.6.3-1 requirement.

Therefore Standalone Torsion must not manufacture a final member PASS from `phiTn` alone.

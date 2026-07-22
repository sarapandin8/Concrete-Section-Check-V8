# Crossbeam PTLOSS3 Elastic Shortening — Method Specification

## 1. Published basis

For post-tensioned members other than slab systems, the AASHTO LRFD sequential average elastic-shortening framework is represented by

`Delta fpES,avg = [(N-1)/(2N)] (Ep/Eci) fcgp`

where the published `N` is the number of identical prestressing tendons and `fcgp` is the concrete stress at the center of gravity of the prestressing tendons from the post-jacking prestress state and applicable member self-weight/stage effects.

## 2. Crossbeam stressing procedure

Project construction intent: tendons are stressed as geometrically symmetric left/right pairs. Tendons within one verified pair are stressed simultaneously and do not create sequential elastic-shortening loss against each other.

PTLOSS3 therefore introduces `G`, the number of verified equivalent simultaneous stressing groups/pairs, for the Crossbeam sequence preview:

`Delta fpES,avg = [(G-1)/(2G)] (Ep/Eci) fcgp`

`Delta fpES,g = [(G-g)/G] (Ep/Eci) fcgp`

This is an engineering mapping of the published sequential-stressing principle. It is released only when every active tendon belongs to one geometrically symmetric pair and group jacking forces are equivalent within the adopted tolerance. It is not a blanket redefinition of AASHTO `N` for arbitrary unequal groups.

## 3. Symmetric-pair source

Pairing is derived from adopted tendon geometry, not tendon names. A pair must have:

- mirrored lateral coordinates,
- matching longitudinal stations,
- matching vertical/depth profile,
- matching tendon type,
- effectively equal jacking-force source.

Default 8-tendon geometry resolves to four groups: `T1+T5`, `T2+T6`, `T3+T7`, `T4+T8`.

## 4. Stage modulus Eci

Assigned material effective `Ec` may be used as a preview `Eci` source only with an explicit stressing-age review note. Final design must confirm the modulus applicable at the actual stressing/load-transfer stage. Manual override is advanced QA only.

## 5. Stage concrete stress fcgp

`fcgp` is a hard source gate. It must ultimately come from a validated stressing-stage section response including:

- accepted prestress force state,
- tendon eccentricity/CGPS basis,
- applicable gross section properties,
- self-weight and other stage effects required by the adopted method,
- protected sign convention and representative section/station basis.

PTLOSS3A does not invent a portal-frame self-weight/frame moment and does not silently substitute a prestress-only `fcgp`. A manual override is allowed only for QA preview and blocks final-ready status.

## 6. Force-chain rule

Elastic Shortening is downstream of the accepted immediate-loss chain:

`Pj -> Friction/Wobble -> Anchorage Set -> Elastic Shortening`

The station preview subtracts only the ES component from `P after Anchorage Set`. It never reconstructs `P after ES` as `fpj - Delta fpES`.

## 7. QA and release gates

Before Elastic Shortening can feed `Pe/Pe_eff`:

1. symmetric stressing-pair source must be verified,
2. actual stressing-pair sequence/procedure must be confirmed,
3. `Eci` stressing-stage source must be confirmed,
4. source-derived `fcgp` route must be implemented and benchmarked,
5. formula and SI-unit tests must pass,
6. post-anchor -> post-ES station-force chain must pass regression,
7. Crossbeam and cross-workflow regression gates must pass.

# SHEAR.LABEL1 — Clear Shear Detailing D/C Labels

## Purpose

Replace the compact ULS shear utilization abbreviation `det` with explicit engineering labels.  The previous compact-table wording could show values such as:

```text
0.460 / det 1.893
```

That was technically a strength/detailing utilization pair, but the abbreviation was not self-explanatory.  Users had to open the full shear audit table to understand that the second value could be controlled by minimum shear reinforcement, for example `Av/s provided < Av/s min`.

## New wording

The compact ULS table and top governing-shear card now use explicit labels:

```text
Strength D/C 0.460; Av/s min D/C 1.893
```

If maximum spacing controls instead of minimum Av/s, the label becomes:

```text
Strength D/C 0.460; Spacing D/C 1.200
```

If the source row does not expose the controlling detailing sub-check, the fallback label is:

```text
Strength D/C 0.460; Shear rebar detailing D/C 1.893
```

## Scope

Changed UI display / status text only:

- Compact ULS check table shear utilization display.
- Governing shear check summary card display.
- Backward-compatible parser for old cached `det` utilization strings.

No shear equation, phi Vn calculation, minimum Av/s equation, spacing limit equation, flexure/torsion equation, SLS equation, geometry, load combination, project schema, or report certification wording was changed.

## Engineering meaning

A shear row still fails if either of the following numeric gates fails:

```text
Strength D/C = |Vu| / phiVn > 1.0
Detailing D/C > 1.0
```

The label change only makes the detailing component readable.  It does not relax or tighten the design check.

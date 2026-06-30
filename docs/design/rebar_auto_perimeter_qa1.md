# REBAR.AUTO.PERIMETER.QA1 — Auto Perimeter Rebar Matrix Closeout

## Purpose

Audit the auto perimeter ordinary-rebar generator after `REBAR.AUTO.PERIMETER.OVERLAP1` and lock the behavior across common Concrete Section Pro section families.

## Section families covered

The QA matrix covers rectangular / chamfered / filleted solids, hollow / box / I-girder / plank / voided plank geometries.

## Findings

The previous perimeter-order spacing guard correctly removed duplicate bars at short step/chamfer control points. QA then exposed a second overlap mode for narrow-web girder sections: two generated bars can sit on opposite offset faces and be far apart along the perimeter but spatially close in x/y. This can happen when web width is small relative to the bar-center offset.

## Closeout rule

The generator now applies two anti-overlap guards:

1. closed-perimeter spacing guard for adjacent short step/chamfer control points;
2. true Euclidean spacing guard that merges spatially close generated bar centers, typically onto the narrow-web centerline when opposite offset faces would collide.

Generated bars must remain inside concrete, outside holes, unique after rounding, and separated by at least the minimum center-spacing guard for the QA matrix.

## Limitations

This remains an automatic preview/detailing aid. The engineer must still review bar grouping, cover, clear spacing, constructability, lap/splice zones, congestion with prestress/tendons, stirrups/ties, and local project detailing requirements before issuing drawings.

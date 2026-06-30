# SLS.RAIL.UGIRDER8 — Service Stage Multi-Fiber Stress Plot with Web/Slab Limit Labels

## Scope

This milestone improves the Railway U-Girder Service-stage SLS graph so the gross full U-section service stress field is sampled at four engineering fibers:

- Top web fiber
- Bottom web fiber
- CIP slab top fiber
- CIP slab bottom fiber

The graph also labels separate Web and Slab compression/tension limit lines directly on the plot, so users do not confuse web concrete strength with CIP slab concrete strength.

## Engineering basis

The Service-stage section basis remains the existing full gross Railway U-section elastic preview.  The top/bottom stresses returned by the existing SLS diagram dataframe are not changed.  Slab fiber stresses are sampled from the same linear elastic stress field using physical y-coordinates derived from the Railway U-Girder parameters:

- Top web fiber: `H`
- Bottom web fiber: `0`
- CIP slab top fiber: `h2 + h4`
- CIP slab bottom fiber: `h2`

Concrete material basis:

- Web fibers use `web f'c`
- CIP slab fibers use `slab f'c`

## Out of scope

This milestone does not change:

- gross section properties
- prestress/debond participation
- stage stress equations
- final service accumulation equations
- SLS decision summaries
- ULS checks
- anchorage, transfer length, development length, or end-zone checks
- report logic

The graph remains a guarded engineering-review preview, not a final code-certified staged composite design check.

## Regression checks

Added source and function-level tests verifying:

- the four Railway U-Girder service fibers are present,
- slab fiber stresses are interpolated from the full-U stress field,
- web/slab concrete strengths remain distinct in the graph data,
- limit labels for Web and Slab tension/compression are rendered on the plot.

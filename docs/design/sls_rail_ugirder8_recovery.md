# SLS.RAIL.UGIRDER8.RECOVERY — Multi-Fiber Service Plot Rebased on Correct Latest Baseline

## Purpose

The first SLS.RAIL.UGIRDER8 package was built from an older baseline and could roll back previously accepted fixes.  This recovery milestone reapplies the Railway U-Girder Service stage multi-fiber stress plot onto the correct latest baseline that includes:

- `SLS.MATERIAL.ROUTING4` canonical transfer-stage strength routing.
- `SLS.RAIL.UGIRDER7` dedicated Lifting stage tab.
- `SLS.TENSION.DEFAULT1` verified bonded tension reinforcement default.

## Scope

Only the Railway U-Girder Service stage plot routing is changed.  The existing full gross U-section elastic stress field is sampled at:

1. Top web fiber.
2. Bottom web fiber.
3. CIP slab top fiber.
4. CIP slab bottom fiber.

The plot adds labeled web/slab limit lines so the material basis is explicit.

## Guardrails

This milestone does not change:

- Stress equations.
- Section properties.
- Geometry generator.
- Pe/debond station participation.
- ULS checks.
- Anchorage, transfer length, or development length checks.
- Report logic.

## Regression focus

The targeted tests include the multi-fiber plot plus the previously accepted fixes that must not regress:

- Railway U-Girder Lifting stage tab.
- Transfer stage `f'ci` routing.
- Verified bonded tension reinforcement default.
- Debonding and prestress station handoff.

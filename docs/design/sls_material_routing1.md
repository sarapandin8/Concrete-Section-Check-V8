# SLS.MATERIAL.ROUTING1 — Stage Material Strength Routing Audit and Correction

## Scope

This milestone corrects the material-strength source used by Beam/Girder SLS stress-limit previews.  It is a routing/guardrail milestone only; it does not change stress kernels, PMM, ULS, geometry, section properties, prestress losses, or report generation.

## Engineering issue

The full-length SLS stress diagram previously derived the concrete strength used in preview limit formulas from the primary concrete material.  That is unsafe for staged prestressed members because the correct concrete strength depends on the stage and selected preset:

- Transfer / release checks should use the transfer strength `f'ci`, not final `f'c`.
- Construction / pre-composite checks should use the precast member concrete strength.
- Service checks should use the material basis associated with the checked fiber/component.
- Railway U-Girder has separate precast web and CIP slab concrete strengths.

## Implemented routing

### Railway U-Girder

| SLS stage | Routed strength |
|---|---:|
| Transfer / Release | `web f'ci` |
| Lifting | same transfer-stage routing in the Railway staged preview |
| Deck casting / Pre-composite | `web f'c` |
| Final service / Composite | `web f'c` for current top/bottom extreme-fiber full-U diagram, with CIP slab `f'c` retained in audit notes |

### Generic prestressed girder presets

| SLS stage | Routed strength |
|---|---:|
| Transfer / Release | `f'ci` from prestress/loss settings when available; fallback `0.8 f'c` |
| Deck casting / Pre-composite | primary/precast `f'c` |
| Final service / Composite | active section/service `f'c` |

## UI behavior

- The full-length SLS diagram and Code Limit Summary now use a stage-routed material-strength helper.
- Locked stage checks synchronize the displayed strength value to the stage material source of truth so stale service `f'c` cannot remain in a transfer check.
- Stage-basis cards include an audit note explaining which strength was selected.

## Guardrails

- Railway U-Girder transfer/lifting must not use final web `f'c` when `web f'ci` differs.
- Generic prestressed girder transfer checks must not silently use final `f'c` when `f'ci` is available.
- CIP slab `f'c` remains visible as a separate staged/material-basis item; the current generic top/bottom full-U service diagram does not yet perform separate slab-fiber limit checks.

## Out of scope

- Final certified SLS design
- Transfer-length force ramp
- Development length / anchorage / end-zone bursting
- Creep/shrinkage redistribution
- ULS coupling
- Geometry or section-property changes

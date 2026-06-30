# SLS.RAIL.UGIRDER7 — Dedicated Railway U-Girder Lifting Stage Tab

## Intent
Add a dedicated **Lifting stage** tab to the Beam/Girder SLS stress workspace when the active section is Railway U-Girder.

## Engineering basis
Railway U-Girder lifting is a temporary handling stage, not the same as transfer/release or wet slab construction.

The preview uses:
- one precast web only,
- transfer-stage prestress `Pe_transfer`,
- station-based debonded strand participation,
- two-point lifting moment basis,
- lifting point ratio from Railway U-Girder stage settings, default `a/L = 0.20`,
- lifting impact factor from Railway U-Girder stage settings, default `1.10`,
- transfer-stage concrete strength `web f'ci` for limit guidance.

## UI behavior
For Railway U-Girder only, the SLS result workspace tabs are:

```text
Transfer stage | Lifting stage | Construction stage | Service stage
```

Other Beam/Girder workflows retain the prior tabs:

```text
Transfer stage | Construction stage | Service stage
```

## Scope
This milestone is an Analysis-page preview/UI and stage-routing milestone only.

It does not add or certify:
- lifting insert design,
- local lifting stress around anchors/inserts,
- transfer length ramp,
- development length,
- anchorage or end-zone bursting checks,
- ULS coupling,
- final code-certified handling design.

## Regression coverage
Added tests confirm:
- Railway U-Girder receives the Lifting stage tab while generic I-girder does not.
- Lifting stage limit guidance routes to `web f'ci`, not final `f'c`.
- Lifting full-length rows use the Railway U-Girder one-web lifting preview and two-point lifting moment sign behavior.

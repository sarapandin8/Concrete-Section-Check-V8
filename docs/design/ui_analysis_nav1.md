# UI.ANALYSIS.NAV1 — ULS Strength navigation rename and check selector placement

## Scope
- Rename the visible Analysis subpage from `ULS / PMM` to `ULS Strength`.
- Move the Column/Pier/Wall/Pylon strength-check selector (`Flexural (PMM)`, `Shear`, `Torsion`, `Shear + Torsion`) directly below the `ULS Strength` subpage heading.
- Rename the selector label from `ULS check` to `ULS Strength Check`.

## Rationale
The previous `ULS / PMM` label under-described the implemented Analysis workspace because the same subpage now includes scoped ACI RC shear, torsion, and combined V+T views in addition to flexural PMM. The check selector belongs at the top of the subpage so users choose the strength route before reviewing the decision summary and selected result body.

## Guardrails
- No solver equation changes.
- No demand/capacity equation changes.
- No shear, torsion, or V+T calculation changes.
- No project schema or save/load changes.

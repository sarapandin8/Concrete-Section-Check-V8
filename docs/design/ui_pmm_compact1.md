# UI.PMM.COMPACT1 — Flexural PMM decision-first compact workspace

## Scope
Reduce Flexural (PMM) page length and make the first-screen review closer to commercial engineering software.

## Changes
- Collapse Analysis Mode / Member Type, Analysis Settings, and Readiness into `Analysis setup / readiness`.
- Collapse the Analysis Workspace Overview and input diagnostics into `Analysis input overview / diagnostics`.
- Make runtime controls shorter and more horizontal while keeping the Run / Recalculate action visible.
- Hide the empty prestress message inside a collapsed Prestress diagnostics panel.
- Keep PMM method validation notes available but remove the visible method card strip from the main result flow.
- Move `PMM Visual Review` before the stored calculation snapshot / D/C trace.
- Collapse stored D/C trace under `Stored calculation snapshot / D/C trace`.

## Guardrails
- No PMM solver changes.
- No D/C equation changes.
- No shear/torsion/V+T changes.
- No geometry, section-property, rebar, prestress, loads, or report calculation changes.
- Stored/cached result behavior is unchanged.

## Product intent
The Flexural page should behave like a decision page first and a diagnostics console second.  Detailed solver, cache, and trace data remain available for QA but no longer dominate the first screen.

# CROSSBEAM.ANALYSIS4C7D27 — Stage-isolated Deflection / Camber workspace

## Scope
D27 removes the duplicated/nested Transfer vs Final Service navigation from `Analysis → SLS Deflection / Camber` and makes the active stage own the complete visible workflow.

## UI behavior
- One stage selector only: `At Transfer` / `At Final Service`.
- At Transfer renders only its displacement source, source editor/import, `Run Transfer Camber Review`, Transfer result cards, Transfer graph, and Transfer audit tables.
- At Final Service renders only its displacement source, L/360 support-span and Lo/180 overhang criteria, `Run Final Service Deflection Check`, Final Service result cards, Final Service graph, and Final Service audit tables.
- The inactive stage is not rendered below the active stage and no second stage tab row appears in the result area.

## Result ownership
- Transfer and Final Service now use separate result keys and separate input fingerprints.
- Editing/replacing Final Service displacement or Final Service L/n / Lo/n criteria does not make the stored Transfer result stale.
- Editing/replacing Transfer displacement does not make the stored Final Service result stale.
- The external-FEA source remains one dedicated Analysis-owned source in Project JSON; stage replacement still preserves the other stage.

## Engineering logic unchanged
D27 does not change displacement sign convention, support-chord relative response, overhang reference response, L/360 / Lo/180 defaults, limit equations, governing selection, or Plotly response/limit construction from D26.

## Validation
- `py_compile`: PASS for modified Python modules.
- Focused D22–D27 / persistence / global-summary regression: 31 tests PASS.
- Dedicated D27 isolation tests: PASS.
- Full repository suite: not run.

**Repo summary:** Isolate Crossbeam SLS Deflection/Camber by stage so each Transfer or Final Service view owns its source, run, stored fingerprint, result cards, graph, and audits without leaking the inactive stage into the workspace.

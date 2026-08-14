# CROSSBEAM.ANALYSIS4C7D26 — Full-member deflection + overhang serviceability defaults

Date: 2026-08-13 (Asia/Bangkok)  
Baseline: `CROSSBEAM.ANALYSIS4C7D25 — Deflection/Camber stage-source + chart UX closeout`

## Scope

This milestone extends the Portal Frame Prestressed Crossbeam `Analysis → SLS Deflection / Camber` route so the same Final Service graph/check can include actual end overhangs without misusing the support-to-support span criterion.

### General-practice application defaults

- Support-to-support span criterion default: `L/360`.
- End-overhang criterion default: `Lo/180`, where `Lo` is the actual projection from the adjacent column centre to the member end.
- These are application defaults for general engineering review, not universal ACI mandates; the UI states that project/serviceability requirements must be verified.
- Existing `Review only`, alternative L/n choices, and Custom ratios remain available.

### Geometry-aware overhang behavior

- Left overhang exists only when the first column centre is inside the member start (`s > 0`).
- Right overhang exists only when the last column centre is inside the member end (`s < member length`).
- If no overhang exists, the app hides overhang controls and produces no overhang limits or audit rows.
- If one side exists, only that side is checked; if both exist, both are checked.
- Imported displacement coverage must reach the actual member end for every overhang being evaluated; no free-end displacement is extrapolated.

### Relative member response

The teal serviceability trace is now a full-member `Relative member deflection` response:

- support-to-support spans: imported FEA displacement minus the straight chord joining adjacent column-centre movements;
- left/right overhangs: imported FEA displacement minus the vertical movement of the adjacent column centre.

The overhang definition removes rigid support translation but intentionally retains support rotation in the physical cantilever/free-end response because this route imports vertical displacement only and does not fabricate a rotational DOF.

### Final Service limits and governing result

- Main spans use their own actual `L/n` limits.
- Overhangs use their own actual `Lo/n` limits.
- All applicable red dashed limits are drawn in the same full-member graph.
- Governing Final Service status and D/C can come from either a support span or an overhang.
- Transfer remains response-only; the full relative trace can still include overhang response but no Final Service L/n acceptance is applied to Transfer.

### Project JSON

- Span and overhang criterion settings are persisted with the dedicated Analysis-owned displacement source.
- Analysis-source metadata schema is bumped to v2.
- Deflection preparation/result schemas are bumped to v3 so older cached results are rebuilt before review.

## Engineering behavior preserved

- Verified external-FEA vertical displacement remains the source of truth.
- Positive displacement = upward/camber; negative = downward/deflection.
- No generic Crossbeam M/EI simple-span displacement is fabricated.
- ULS, SLS Stress & Cracking, prestress-loss, reinforcement, and physical-joint stress equations are unchanged.

## Regression

- `py_compile`: PASS for changed Python modules.
- D22–D26 focused Deflection/Camber regression: 20 passed.
- D17–D21 stored-SLS / report aggregation regression: 22 passed.
- Total focused passing tests: 42.
- D13–D16 combined batch was not used for milestone sign-off because that combined command exceeded the local execution timeout; no failure result was produced.

Visual QA in deployed Streamlit is still required for the new default controls, full-member teal trace, overhang red dashed limits, and no-overhang auto-hide behavior.

# CROSSBEAM.ANALYSIS4C7C3 — Flexure Runtime + Segmental φMn Envelope Hotfix

This hotfix closes two deployed Flexure defects without changing the ACI 318-19 resistance equations.

- Initializes the active construction method inside the Crossbeam Flexure workspace before any caption/render use, eliminating the deployed `NameError` after `Calculate Flexure`.
- For Precast Segmental construction, solves both binary ordinary-rebar-credit limits at every eligible ACI development boundary (`ld-` no-credit and `ld+` full-credit) at the same station. This lets the φMn chart draw a complete Segment-owned capacity envelope with truthful vertical credit steps even when station-dependent `fpe(s)` makes capacity vary along the member.
- Physical Segment joints remain true trace breaks with independently solved `s−/s+` capacities. Column/support interiors remain omitted from ordinary beam traces. Full-span PT end stations remain retained.
- No Flexure, Shear, Torsion, Combined V+T, prestress-loss, strength-reduction-factor, or Project JSON equation/schema change is introduced.

Validation performed:

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS
- Crossbeam Analysis test inventory run in bounded batches — 120 passed
- Deployment dependency contract — 1 passed
- New runtime/envelope regression — 2 passed, including a six-Segment station-dependent-prestress benchmark verifying both development-boundary φMn limits are present in each affected Segment trace.

Repo summary: Fix the deployed Crossbeam Flexure construction-mode NameError and complete Precast Segmental φMn envelopes by solving both binary development-boundary capacity limits without changing engineering equations.

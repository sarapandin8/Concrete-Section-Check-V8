# CROSSBEAM.RB-CIP3B — Auto-Layout Quantity Source and Transition Review Clarity

This milestone corrects Cast-in-Place reinforcement completeness semantics after RB-CIP3A visual QA.

## Scope

- Treat a valid assigned Outer-face auto-layout as a complete longitudinal quantity definition.
- For `By exact bar count`, derive total perimeter reinforcement area directly from bar count and nominal diameter.
- For `By target spacing`, recognize the definition as complete while keeping actual generated count/area dependent on the assigned Solid section geometry.
- Keep Top/Bottom/Side adopted As as an optional override / independent QA value rather than a duplicate confirmation.
- Show assigned quantity sources explicitly in the CIP Longitudinal workspace.
- Improve transition-table readability with wider columns and a full-text `Transition review details` expander.

## Protected behavior

- Section/Zone template assignment remains the single CIP adopted-reinforcement source.
- Zone boundaries remain property boundaries, not physical joints.
- Precast Segmental joint semantics and `As crossing joint = 0 mm²` are unchanged.
- No PMM, ULS, SLS, shear/torsion, prestress-loss, Result Summary, or Report/QA solver handoff is enabled.
- No development, splice, termination, anchorage, or exact continuing-bar identity is certified.
- No Project JSON schema change.

## Repo summary

Recognize valid Cast-in-Place auto-layout definitions as complete reinforcement quantity sources, derive exact-count As, keep adopted As optional, and expose full transition-review details without enabling solver credit.

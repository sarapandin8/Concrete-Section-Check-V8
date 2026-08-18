# Concrete Section Pro — IGIRDER.ULS1

## Milestone
Bridge Precast I-Girder Construction-ULS automatic demand foundation and staged Flexure routing.

## Implemented
- Isolates the new route to the Bridge shared `parametric_i_girder` preset; U-/box-/plank workflows are not changed by this milestone.
- Adds a stage-separated Flexure workspace:
  - **Construction — Noncomposite**: automatic simple-span demand on the precast girder only.
  - **Final — Composite**: verified imported FEA strength demand; composite resistance remains guarded until the two-concrete-region strength solver is implemented.
- Automatic Construction-ULS line loads can include:
  - precast girder self-weight,
  - wet CIP deck,
  - formwork / SIP forms,
  - construction live load.
- Project-applicable ULS factors are engineer-entered and require explicit confirmation. Default factor values of 1.0 are neutral placeholders and are **not** asserted to be AASHTO defaults.
- Unshored simple-span construction is implemented. Shored construction is blocked from automatic acceptance because shore reactions/load sharing require a project construction model.
- Construction flexural capacity uses the precast section, station-dependent strand participation/debonding, and the Construction-stage effective prestress force.
- Construction settings are persisted in Project JSON and participate in dirty-state / ULS cache invalidation.
- Final Composite Flexure deliberately reports **REVIEW REQUIRED** instead of reusing the precast-only one-concrete-region capacity model.

## Explicitly not closed in this milestone
- Final composite `φMn` using separate girder and CIP deck concrete regions.
- Girder–deck interface shear/composite-action gate.
- Local bridge deck slab design.
- Automatic code-selected construction load factors.
- Shored construction demand analysis.

## Engineering intent
Construction and Final Composite ULS are different structural stages with different demand and resistance models. Final imported FEA `Mu` is not reused as the Construction-stage demand, and the CIP deck is not credited to Construction-stage strength.

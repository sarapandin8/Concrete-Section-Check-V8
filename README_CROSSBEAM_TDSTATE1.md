# CROSSBEAM.TDSTATE1 — Durable TD Inputs, Explicit Schedule Decision, and Reset

## Scope

Close the Time-Dependent input-state and adoption-control defects observed after navigating from `Sections → Prestress Loss → Time-Dependent` to `Analysis` and back.

## Root cause

Streamlit removes widget-owned keys when the page containing those widgets is not rendered. The TD page previously treated those transient keys as the only live source, so environmental, age, drying, steel, and no-later-event values could disappear or revert after workspace navigation.

## Changes

- Add a durable, input-only TD state owner separate from widget keys and calculated results.
- Restore TD widgets from the durable owner after workspace navigation.
- Preserve the same TD values when Project JSON is saved while another workspace is active.
- Normalize the dirty-state hash so first-time materialization of unchanged defaults does not make Analysis stale.
- Replace the ambiguous no-later-event checkbox with an explicit `Permanent-load schedule adoption decision` card.
- Provide `Confirm no later permanent events` and `Revoke confirmation` actions with visible decision status.
- Add `Reset to defaults` for RH, curing/stressing/grouting/falsework/final ages, drying exposure, steel relaxation class, and the no-later-event decision.
- Clear the current TD result when defaults are reset because its input fingerprint is no longer current.
- Preserve imported FEA response rows and permanent-load event mappings during reset.

## General-practice reset values

- RH: 75%
- End of curing: 7 days
- Tendon stressing: 28 days
- Tendon grouting: 28 days
- Falsework removal: 35 days
- Final age: 18,250 days (50 years)
- Interior void drying exposure: 50% for the generic enclosed-cell starter assumption
- Prestressing steel: low-relaxation seven-wire strand
- No-later-event decision: not confirmed; explicit engineer action remains required when no event is adopted

## Preserved behavior

- No friction/wobble, anchorage-set, elastic-shortening, creep, shrinkage, relaxation, effective-prestress, SLS, or ULS equation changed.
- No construction-stage frame/contact solve or FEA import/mapping logic changed.
- No Project JSON schema version changed; the existing flattened TD metadata contract remains intact.
- Reset does not delete or rewrite imported permanent-load event data.

## Repo summary

Persist Crossbeam TD source inputs across navigation, replace the ambiguous no-event checkbox with an explicit schedule decision, and add a safe reset-to-defaults action.

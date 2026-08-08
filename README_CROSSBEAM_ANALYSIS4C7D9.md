# CROSSBEAM.ANALYSIS4C7D9 — Combined V+T scope cleanup

## Scope
Close the current Precast Segmental Combined V+T sectional workflow without implying that a physical segment-joint V+T transfer solver exists.

## Changes
- Retired the undeveloped `Joint review` tab from the active Combined V+T review selector.
- Preserved physical-joint one-sided s− / s+ rows in a collapsed `Physical-joint one-sided evidence — NOT EVALUATED` audit expander.
- Changed Precast physical-joint transfer semantics from `REVIEW REQUIRED` to `NOT EVALUATED` for this milestone.
- Physical-joint audit rows remain excluded from sectional PASS/FAIL and governing ownership and no joint D/C is created.
- A passing sectional Combined V+T result is no longer downgraded solely because physical segment joints exist; joint transfer remains a separate future/project check.
- Added stale-widget-state migration so projects previously saved with `Joint review` selected reopen on `Section-size interaction` safely.
- Reworded legacy Rebar Template quantity warnings so Combined V+T traceability matches the adopted detailed longitudinal layout for provided Aℓ and the adopted transverse template for transverse capacity.
- Updated source/count and scope wording so support/joint overlaps are described as audit-only evidence rather than an implemented joint-review gate.

## Engineering logic preserved
- No ACI equations changed.
- No Shear, Torsion, Flexure, or Combined V+T capacity equations changed.
- Segmental tendon-only Flexure remains unchanged.
- Local station-dependent effective prestress remains unchanged.
- Joint-side rows remain one-sided and are never averaged into sectional capacities.
- Cast-in-Place physical-joint semantics remain NOT APPLICABLE.

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- D9 scope/traceability + Combined component/semantic tests — 22 passed
- Flexure + Shear + Torsion + Combined targeted regression — 61 passed

## Visual QA requested
Confirm the Combined V+T page now exposes only Section-size interaction, Transverse reinforcement, and Longitudinal reinforcement as active tabs; physical-joint evidence should appear only in the collapsed NOT EVALUATED audit expander, and Calculation limitations should no longer claim that actual provided reinforcement is undefined when the detailed adopted source is being used.

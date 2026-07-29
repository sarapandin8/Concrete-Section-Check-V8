# CROSSBEAM.PTLOSS4B3B — Compact Multi-Event Permanent-Load FEA Schedule

## Scope

PTLOSS4B3B refines the Time-Dependent Prestress Loss workspace by replacing the verbose single-`tp` FEA source declaration with a compact, multi-event permanent-load schedule.

## User workflow

1. Import one Excel/CSV response table containing one or more incremental FEA `Case Name` datasets.
2. Map each adopted Case Name to a permanent-load group and activation age.
3. Run the event-based Time-Dependent preview.

Standard permanent-load groups:

- Beam / Girder permanent load — CIP / PC / Steel
- Slab / Deck permanent load — CIP / PC / Steel deck
- SDL on slab
- Box girder permanent load
- SDL track work / Utility
- Other permanent load

## Engineering behavior

- Each event uses one unfactored incremental FEA response case with row-coupled `P / V2 / M3`.
- Imported rows are selected automatically by `Case Name`; users do not activate every station row manually.
- Each event may have its own activation age.
- Creep/shrinkage intervals are generated automatically from the event ages.
- Events at the same age are applied before the next interval.
- Cumulative `Δfcd` is formed only from matching station/element/side/section keys; independent governing maxima are never added.
- All adopted event cases must use the same FEA response mesh and model revision.
- Obvious ULS/live/wind/seismic/temperature/prestress/creep/shrinkage/relaxation/envelope case names are blocked.
- No later permanent-load event is a valid schedule state.
- Import and mapping perform zero structural solves; Segmental Run retains one internal falsework-removal solve.

## Backward compatibility

- PTLOSS4B3A single-event Project JSON is migrated into one PTLOSS4B3B schedule row.
- Deployed PTLOSS4B3 Loads-owned response rows remain migratable.
- Legacy single-`tp` calculation calls remain supported and regression-tested.

## Files changed

- `concrete_pmm_pro/crossbeam/later_permanent_response.py`
- `concrete_pmm_pro/crossbeam/event_stage_stress.py`
- `concrete_pmm_pro/crossbeam/time_dependent_loss.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`
- `concrete_pmm_pro/ui/loads_page.py`
- `concrete_pmm_pro/io/project_io.py`
- `concrete_pmm_pro/state/dirty_state.py`
- `tests/test_crossbeam_ptloss4b3b_multi_event.py`

## Calculation scope

No Friction/Wobble, Anchorage Set, Elastic Shortening, AASHTO material-factor, shrinkage, or relaxation equations were changed. The new logic partitions the accepted representative-stress Time-Dependent QA route across multiple permanent-load activation events. Station/tendon-dependent `Pe(s)` and `Pe_eff(s)` assembly remains locked.

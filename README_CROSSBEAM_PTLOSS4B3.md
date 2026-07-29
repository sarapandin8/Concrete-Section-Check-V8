# CROSSBEAM.PTLOSS4B3 — Verified Later Permanent Load Event Source

This milestone connects the Portal Frame Crossbeam **Loads** workspace to the
Precast Segmental Time-Dependent Loss schedule without unlocking final effective
prestress.

## Scope

- Adds a workflow-specific Later Permanent Load table for Portal Frame Crossbeam.
- Supports downward point loads in kN and uniform line loads in kN/m.
- Requires load stations and uniform-load boundaries to coincide with the accepted
  0.5 m frame mesh so load effects can be recovered exactly by the existing frame
  response kernel.
- Applies point loads at beam nodes and uniform loads directly to complete beam
  elements.
- Runs zero structural solves when the Loads or Time-Dependent tab is opened.
- Runs one falsework-release solve and, when the later-load source is verified,
  one additional cumulative released-frame later-load solve.
- Derives the event `Δfcd` from structural response rather than the engineer input.
- Keeps the engineer-entered `Δfcd` only as an explicitly labelled QA fallback when
  no active Later Permanent Load rows exist.
- Blocks the result when active load rows are invalid; it does not silently fall
  back to the manual value.
- Adds load-source, frame-load closure, raw N/M, stationwise response delta, and
  fingerprint audit output.
- Saves and restores the Later Permanent Load table through Project JSON.

## Engineering boundary

The verified later-load handoff closes the structural event source, but it does
**not** make the Time-Dependent result adoptable. The current schedule still uses
one representative bonded `f_cgp` route; station-dependent/tendon-dependent creep
integration, time-resolved relaxation interaction, and downstream `P_e(s)` /
`P_{e,eff}(s)` assembly remain locked.

No accepted Friction/Wobble, Anchorage Set, Elastic Shortening, creep, shrinkage,
or relaxation equations were changed.

## Runtime contract

- Open or edit Loads / Time-Dependent: `0 solves`
- Segmental run without active verified later loads: `1 solve` (falsework release)
- Segmental run with active verified later loads: `2 solves` (release + later load)

## Changed production files

- `concrete_pmm_pro/crossbeam/later_permanent_load.py`
- `concrete_pmm_pro/crossbeam/event_stage_stress.py`
- `concrete_pmm_pro/crossbeam/time_dependent_loss.py`
- `concrete_pmm_pro/ui/loads_page.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`
- `concrete_pmm_pro/io/project_io.py`
- `concrete_pmm_pro/state/dirty_state.py`

## Tests

- New PTLOSS4B3 load-source, event-solve, source-blocking, Project JSON, and UI
  routing tests.
- Complete Crossbeam regression executed.
- Complete repository test inventory executed in partitions because a monolithic
  `pytest -q` run exceeded the sandbox timeout.

## Repo summary

Connect Crossbeam later permanent loads to a verified two-event prestress-loss schedule with exact mesh-based frame loading, response-derived Δfcd, Project JSON persistence, and full source/response audit traceability.

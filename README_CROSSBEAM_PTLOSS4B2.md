# CROSSBEAM.PTLOSS4B2 — Event-Based Stage Stress Sources

Adds a lightweight Precast Segmental time-dependent-loss route that solves only structural events rather than every time step.

## Scope

- Reuses the CURRENT Lightweight ES result and post-ES tendon force distribution.
- Runs one fixed-base/no-falsework-contact frame solve at falsework removal.
- Uses the stored post-ES/grouting concrete stress for the first interval.
- Uses the released-stage concrete stress for the second interval.
- Applies an explicit engineer-entered later permanent-load concrete-stress increment, Δfcd at the Tendon CG, for the final interval until a verified Loads-workspace source is connected.
- Keeps creep/shrinkage aging arithmetic between events.
- Keeps relaxation as one final AASHTO R2 total term.
- Keeps Effective Prestress assembly locked.

## Runtime

- Opening the page: 0 structural solves.
- Running the Segmental event-based preview: 1 structural solve.
- No FEA solve per time step.

## Persistence

Prestress-loss Project JSON schema version 8 adds only the input `td_later_load_delta_fcgp_mpa`; no result cache or solver output is persisted.

## Exclusions

- Verified Loads-workspace later permanent-load source.
- Time-resolved relaxation.
- Fully coupled creep redistribution.
- Final Pe / Pe_eff assembly and Result Summary / Report handoff.

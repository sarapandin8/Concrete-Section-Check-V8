# CROSSBEAM.PTLOSS4B1 — Precast Segmental Schedule Time-Step Foundation

## Purpose

Introduce an explicit, lightweight construction-schedule route for Precast Segmental Crossbeam time-dependent prestress losses without reintroducing heavy FEA/contact reruns. The milestone partitions the accepted post-grouting creep and shrinkage response into schedule intervals while preserving the accepted PTLOSS4A1A1 totals for the default immediate-grouting regression case.

## Construction schedule

PTLOSS4B1 stores and validates representative concrete ages for:

- tendon stressing, `ti`,
- tendon grouting, `tg`,
- falsework removal, `tr`,
- later permanent-load application, `tp`, and
- final time, `tf`.

The chronology gate is:

```text
ti ≤ tg ≤ tr ≤ tp < tf
```

The bonded time-dependent route begins at grouting. When `tg > ti`, the pre-grouting interval is disclosed as excluded and final adoption remains blocked.

## Time-step calculation

For Precast Segmental construction, creep and shrinkage are accumulated over:

1. post-grouting to falsework removal,
2. falsework removal to later permanent load, and
3. later permanent load to final time.

Each interval exposes:

- start/end age,
- incremental creep coefficient `Δψ`,
- creep-loss increment,
- incremental shrinkage strain `Δεsh`,
- shrinkage-loss increment,
- relaxation increment, and
- cumulative time-dependent loss.

A closure audit confirms that the interval sums equal the direct post-grouting component totals. For the default regression schedule (`ti = tg = 28 d`, `tr = 35 d`, `tp = 90 d`, `tf = 18,250 d`), the accepted totals remain:

- creep = `78.369843 MPa`,
- shrinkage = `40.890590 MPa`,
- relaxation = `7.888682 MPa`,
- subtotal = `127.149115 MPa`, and
- structural solves = `0`.

## Scope guards

This milestone is a schedule and material-aging QA foundation, not final Effective Prestress adoption.

- Falsework removal and later permanent-load events partition time only; they do not yet update structural stress.
- Later permanent-load concrete stress change `Δfcd` is not yet included.
- Relaxation remains one final AASHTO R2 interval term because a time-development law is not yet sourced.
- Delayed grouting requires a separate pre-grouting loss model.
- No `Pe/Pe_eff`, Result Summary, or Report/QA handoff is unlocked.

## Runtime and persistence

- Opening the page, changing a display, or opening the QA expander performs zero structural solves.
- The three new schedule ages are input-only Project JSON fields under Crossbeam Prestress Loss schema version 7.
- Time-dependent results and runtime cache are not persisted into Project JSON.

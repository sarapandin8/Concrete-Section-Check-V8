# IGIRDER.CASECONTROL5 — Girder / load-case result review

Date: 2026-10-06. Baseline: concrete-section-pro_IGIRDER-ARROWDISPLAY4.zip,
SHA-256 1d4cffd1ef40a32c76807d8e05ffe28c0e01888b4e4a55e64c082eb41bafe38f.

## Requested behavior

After Calculate, select a girder and its load case in Flexure → Final — Composite,
Shear, Torsion and Shear + Torsion. Identify the controlling case independently
for each girder and check, retaining its station, component and source identity.

## User workflow

1. Import the girder/case collection in Loads and complete the model inputs.
2. Open the required Analysis check. For Flexure, select Final — Composite.
3. Press Calculate [check] — all [N] girders (current model).
4. Read the Controlling load cases table, with one current result per girder.
5. In Girder results view, choose All imported girders — separate charts or
   Choose girder / load case — stored results. The latter provides Girder to review.
6. Load case to review offers Automatic — controlling load case (default),
   All load cases, and every actual named case/vector series for that girder.
7. Inspect the selected graphs, trace, station rows and source audit. The
   Load-case ranking / controlling components expander retains all-case context.

Each named-case view filters the original stored rows. It does not envelope
different force components or select demand and capacity from different cases.
Native CSI source endpoint context remains available from the same girder.
Full case identity remains in the table and figure metadata; long figure titles
may shorten the text. CSI case names can include step, bound and source row set.

## Numerical controlling criterion

| Check | Stored ratios considered |
|---|---|
| Final Composite Flexure | Signed-section utilization / D/C |
| Shear | Strength, detailing, minimum Av/s, spacing, Vn upper limit |
| Torsion | Transverse strength, available longitudinal steel ratio, detailing, spacing |
| Shear + Torsion | Concrete stress, combined transverse, combined longitudinal, spacing, available overall D/C |

The largest available nonnegative numeric ratio controls. Infinite ratios are
retained and labelled ∞. Synthetic diagram boundary rows do not control.
Shear uses the accepted critical-section / near-support eligibility rules.
The utilization overview and controlling summary use the same components.

Equal maxima retain every tied case, with the first original case displayed
automatically. The component table retains each component's controlling source.
Numerical control is separate from the accepted status decision: all-member
failure/review counts remain visible when the selected case passes. Missing
capacities, source/development gates and partial sub-checks remain unresolved.

If Torsion has no strength/detailing D/C but a valid investigation threshold,
the fallback |Tu|/(0.25φTcr) is labelled INVESTIGATION ONLY. It is not a φTn
strength acceptance. Ranking groups strength D/C separately from investigation
ratios. With no numeric ratio, the automatic view shows a pending source-review
row and explicitly states NO NUMERIC D/C; it does not infer control from force.

## State and scope

- Changing the review girder/case does not call a solver, activate a Loads member,
  alter the load bank, or replace complete cached results with filtered rows.
- A shortened Flexure station list resets a prior out-of-range station selection.
- Input hashes still control freshness. STALE / NOT CALCULATED / ERROR members
  have no old numerical control in the collection summary and no stale chart.
- Result Summary and Report / QA continue to use the design member selected in
  Loads. A result-review selection does not publish another member to that cache.
- All collection members still use the current shared section/deck/steel,
  prestress and support model. Different member details require separate models.
- Project JSON persists the input collection; result caches remain session-only.
- No engineering equations, resistance calculations, acceptance gates or
  dependency versions changed. No result-cache persistence was introduced.
- The accepted Arrow display adapter remains applied to mixed structured audit
  fields; original list/dict traces and typed result values remain in the cache.

## Verification

- py_compile: app.py, all changed production modules and QA entry points.
- Scoped regression: 688 passed across 55 I-girder / Beam ULS / load-bank /
  Project modules. This is not a claim that every repository test was run.
- New meaningful cases cover smaller signed demand controlling by D/C,
  detailing/minimum control, partial rows, finite/infinite ties, investigation
  fallback, source review, repeated stations, and overview/summary agreement.
- Real Streamlit AppTest: both Exterior Girder and Interior Girder 2, two load
  cases each, across all four checks; automatic/named/all-case and single-member
  views; no review-time solver calls; unchanged input and stored result frames.
- Actual app.py Analysis routing verified for all four checks and both girders.
- Original mixed Deck development trace Arrow failure reproduced with the
  display adapter removed; normal result views remain free of Arrow exceptions.
- Representative 1440 × 560 selected-case charts visually inspected, including
  the combined component chart. PNGs and exact Plotly specs are in QA evidence.
- Runtime: Python 3.14.7, pandas 3.0.6, Streamlit 1.61.0, PyArrow 24.0.0.
- QA uses controlled hypothetical inputs. These checks do not verify a live
  deployment or certify the user's bridge design.

Evidence: qa/evidence/igird_casecontrol5/. Reproduce from the project root with
qa/igird_casecontrol5_ui_verify.py and qa/igird_casecontrol5_app_verify.py.

## Repository summary

Add girder and load-case result selection with traceable controlling-case summaries across all four I-girder ULS checks.

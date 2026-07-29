# CROSSBEAM.PTLOSS4B3 — Imported FEA Later Permanent Load Response

## Baseline

- Accepted starting ZIP: `concrete-section-pro_CROSSBEAM-PTLOSS4B2B1-code-route-event-audit-semantic-cleanup(1).zip`
- Accepted starting SHA-256: `a3d9a8a82190c10ab732a7e59692e0ac543c8114598ee54d83cb89f2a3b76a9c`
- The earlier manual Point-load / Uniform-load PTLOSS4B3 candidate is superseded and is not a baseline.

## Scope

PTLOSS4B3 connects the Crossbeam Time-Dependent Later Permanent Load event to imported incremental FEA internal-force results by reusing the established Loads-workspace Excel/CSV import pattern:

1. Download Excel/CSV template.
2. Upload an FEA result table.
3. Normalize supported source-column aliases.
4. Preview and validate.
5. Replace or append the canonical Crossbeam table.
6. Apply one adopted incremental FEA case/combination to the Time-Dependent schedule.

Canonical imported columns are:

`Active | Station x (m) | Case Name | Step Type | Step Num | FEA Object | FEA Element | End / Side | Section ID | P | V2 | M3 | Note`

Fixed exchange convention:

- Station: m along the physical Crossbeam, `s = 0 ... L`.
- `P`: kN, compression positive.
- `V2`: kN, retained for source and response audit.
- `M3`: kN-m, sagging positive in the Crossbeam `s`-vertical plane.

The imported `P / V2 / M3` tuple remains coupled by source row. The app does not create a fictitious envelope by combining force-component maxima from different rows or cases.

For each accepted row, the concrete-stress increment at the tendon CG is calculated as:

`Delta f_cd = P/A - M3*y_p/I`

The current schedule adopts the governing value on the representative route comprising the left column centerline, span center, right column centerline, and imported maximum-absolute-M3 station within the column lines. This remains a schedule QA source; final station/tendon-dependent `Pe(s)` and `Pe_eff(s)` assembly remains locked.

## Runtime

- Opening or editing Loads: 0 structural solves.
- Import / Preview / Apply: 0 structural solves.
- Time-Dependent Run: 1 internal solve for falsework removal only.
- Later Permanent Load: imported FEA response; no second internal structural solve.

## Safety gates

- Exactly one active adopted FEA case/combination is permitted.
- Station must lie within `0 ... L`.
- `P`, `V2`, and `M3` must be numeric on every active row.
- A discontinuity station must be resolved by `End / Side` and/or `Section ID`.
- Duplicate case/station/element/side keys are blocked.
- An active but invalid import produces `REVIEW REQUIRED`; it does not silently fall back to a hidden manual value.
- The legacy manual `Delta f_cd` value remains loadable for backward compatibility but is ignored by the PTLOSS4B3 UI run route.
- Imported-source fingerprints are included in the Time-Dependent calculation trace.

## Changed production files

- `concrete_pmm_pro/crossbeam/later_permanent_response.py` — new imported-response validation, section/tendon mapping, stress calculation, representative-route source, and fingerprint.
- `concrete_pmm_pro/crossbeam/event_stage_stress.py` — consumes the verified imported FEA source without adding a structural solve.
- `concrete_pmm_pro/crossbeam/time_dependent_loss.py` — routes the Later Permanent Load schedule event from imported response.
- `concrete_pmm_pro/ui/loads_page.py` — Crossbeam-specific reuse of the established template/upload/preview/replace/append import workflow.
- `concrete_pmm_pro/ui/crossbeam_pages.py` — imported-source status and detailed Time-Dependent audit; visible manual Later-load input removed.
- `concrete_pmm_pro/io/project_io.py` — persists the canonical imported Crossbeam response table.
- `concrete_pmm_pro/state/dirty_state.py` — tracks the imported table as a Loads input source.

## Tests

Final focused verification after the last safety edits:

- PTLOSS4B3 + accepted PTLOSS4B2B1/PTLOSS4B2B/PTLOSS4A + Loads + Project IO + dirty-state set: **100 passed**.
- Complete Crossbeam regression: **402 passed**.
- Project IO / dirty state / Loads / analysis-mode / dashboard smoke: **112 passed**.
- `python -m compileall -q concrete_pmm_pro app.py`: **passed**.
- Full repository collection: **2,240 tests collected**.
- Monolithic `pytest -q`: attempted but exceeded the available 120-second execution window near 48%; therefore no full-repository-green claim is made.

Earlier partitioned repository testing identified six failures that were independently reproduced on the accepted PTLOSS4B2B1 baseline and are not caused by PTLOSS4B3. They concern legacy Railway U-Girder rebar/default assertions, one sidebar regression assertion, one Result Summary source-blocked wording assertion, and two widget-key audit assertions.

Live Streamlit visual click-through was not available in the packaging environment. Treat this package as a candidate baseline until the Loads import, Time-Dependent audit, and Project JSON save/reload are manually reviewed in the deployed app.

## Engineering equations unchanged

No accepted equation was changed for:

- Friction / Wobble,
- Anchorage Set,
- Elastic Shortening,
- Creep,
- Shrinkage,
- Relaxation,
- falsework-removal structural response.

This milestone changes only the Later Permanent Load response source and its UI/state/QA handoff.

## Repo summary

`Connect Crossbeam time-dependent losses to row-coupled imported FEA P/V2/M3 responses using the existing Loads import workflow, verified source mapping, Project JSON persistence, and one-solve event audit.`

# CROSSBEAM.ANALYSIS1A — Navigation, Status, and Populated-Source QA

## Scope

This milestone hardens the accepted `CROSSBEAM.ANALYSIS1` three-stage station-check foundation before any ACI 318 strength or service-stress solver is introduced.

## Changes

- Makes the commercial sidebar use the same Crossbeam-specific Analysis subpage list as the main Analysis router, eliminating the previous generic `ULS Strength` highlight while `Station Check Foundation` was displayed.
- Uses the complete member-code edition label (`ACI 318-19`) in the Analysis dashboard card.
- Replaces the misleading Crossbeam runtime state with `INPUT REVIEW ONLY`; no SLS/ULS solver is marked current.
- Hides generic Developer timing diagnostics from the Crossbeam foundation page.
- Adds a shared full-length Crossbeam Analysis chart foundation showing:
  - member extent `s = 0 to L`,
  - Segment/Zone bands and Section IDs,
  - physical Precast Segment joints or CIP analysis-zone boundaries,
  - actual Column footprints along `s`,
  - Column centerlines and IDs,
  - validated ULS Final, SLS At Transfer, and SLS At Service source-station markers,
  - one-sided `s- / s+` marker semantics.
- Adds source-only station-coverage QA for member ends, both sides of each Column centerline, and both sides of every internal Segment/Zone boundary in all three required datasets.
- Adds populated regression fixtures proving different Section IDs on opposite joint faces, row-coupled force preservation, actual rebar source mappings, Column-side coverage, and full-length chart landmarks.

## Engineering limits

- No ACI 318-19 stress, flexure, shear, torsion, or capacity equation is evaluated.
- No result interpolation or production envelope is created between imported stations.
- `STATION COVERAGE REVIEW REQUIRED` is a source-review state and does not silently become a solver PASS/FAIL result.
- The project-specific Precast Segment Joint compression criterion (`>= 0.70 MPa` at top and bottom fibers) remains identified but is not calculated in this milestone.
- D-regions, anchorage zones, beam-column joints, seismic detailing, and construction-stage verification remain separately guarded scopes.

## Files changed

- `app.py`
- `concrete_pmm_pro/crossbeam/analysis_foundation.py`
- `concrete_pmm_pro/crossbeam/analysis_charts.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `concrete_pmm_pro/ui/crossbeam_analysis_page.py`
- `tests/test_crossbeam_analysis1a_navigation_status_chart_qa.py`
- `README_CROSSBEAM_ANALYSIS1A.md`

## Repo summary

`Harden Crossbeam Analysis navigation and review status, add populated three-stage source QA, and establish a shared full-length chart standard with Column footprints and station-coverage gates.`

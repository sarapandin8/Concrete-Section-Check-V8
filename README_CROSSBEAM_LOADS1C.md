# CROSSBEAM.LOADS1C — Simplified External-FEA Import Gate and Project Persistence

## Scope

This milestone simplifies the accepted Crossbeam station-force import workflow before the SLS/ULS solvers are developed. It removes detailed external-FEA adoption blockers that were disproportionate for a section design/checking application, while retaining the row-coupled dataset declaration and canonical input validation.

## Changes

- Replaces the detailed external-FEA contract with one engineer confirmation per required dataset:
  - ULS Final Stage,
  - SLS At Transfer,
  - SLS At Service.
- Makes FEA program, FEA model/revision, prestress Source ID, prestress Contract ID, and uniform final-loss metadata optional traceability inputs rather than import blockers.
- Retains automatic validation of:
  - station limits,
  - numeric `P`, `V2`, `T`, and `M3`,
  - nonblank Case/Combination,
  - duplicate Case/Stage/Station/Check Point rows,
  - fixed Transfer/Service stage routing,
  - source-unit and sign normalization,
  - separate ULS, Transfer, and Service datasets.
- Keeps imported rows stored canonically in kN and kN·m.
- Adds contract schema `crossbeam-station-force-import-contract-v3`.
- Migrates prior LOADS1A/LOADS1B detailed confirmations into the new dataset confirmations when an older Project JSON is loaded.
- Preserves old optional metadata and legacy declaration fields in Project JSON so loading and re-saving an older project does not discard prior inputs.
- Adds round-trip tests proving that current and legacy Project JSON files preserve:
  - ULS rows,
  - SLS At Transfer rows,
  - SLS At Service rows,
  - Check Point labels,
  - optional FEA metadata,
  - source units/signs,
  - dataset confirmations.
- Invalidates the three simplified confirmations when the applied Column/support layout changes, while retaining imported rows as stale evidence.

## Engineering limits

- Dataset confirmation is an engineer declaration, not an independent verification of the external FEA model.
- The app still does not allow synthetic force rows assembled from independent maxima.
- No ACI 318 stress, flexure, shear, torsion, or capacity equation is evaluated in this milestone.
- Analysis remains blocked until all three required datasets contain validated active rows.

## Files changed

- `concrete_pmm_pro/crossbeam/station_force_contract.py`
- `concrete_pmm_pro/ui/loads_page.py`
- `concrete_pmm_pro/ui/crossbeam_pages.py`
- `tests/test_crossbeam_loads1a_compact_station_force_import.py`
- `tests/test_crossbeam_loads1b_separate_sls_transfer_service.py`
- `tests/test_crossbeam_analysis1_three_stage_foundation.py`
- `tests/test_crossbeam_analysis1a_navigation_status_chart_qa.py`
- `tests/test_crossbeam_loads1c_simplified_gate_persistence.py`
- `README_CROSSBEAM_LOADS1C.md`

## Repo summary

`Simplify Crossbeam external-FEA station-force adoption to one confirmation per dataset while preserving canonical validation and complete current/legacy Project JSON inputs.`

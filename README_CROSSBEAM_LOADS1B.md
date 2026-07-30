# CROSSBEAM.LOADS1B — Separate SLS At Transfer and At Service Imports

## Starting baseline

- `CROSSBEAM.LOADS1A — Compact Selected Station-Force ULS/SLS Import`
- Accepted Prestress Loss basis remains `CROSSBEAM.PTLOSS4D2B`.

## Purpose

Keep the compact member-style station-force workflow while separating the two serviceability states that use different prestress conditions:

- **SLS At Transfer** — immediate-loss prestress state only: Friction/Wobble, Anchorage Set, and Elastic Shortening; no final Time-Dependent loss.
- **SLS At Service** — adopted final prestress state using the linked uniform system-average final loss; external FEA includes primary and secondary prestress response once.

ULS remains a factored final-stage FEA response import.

## UI changes

- `SLS Loads` now contains fixed sub-tabs:
  - `At Transfer`
  - `At Service`
- Each sub-tab has its own Excel/CSV template, upload preview, Replace, Append, and editable station-force table.
- `Stage` is assigned by the sub-tab and is not user-editable or required in the template.
- The visible table remains compact:
  - `Active`
  - `Station s (m)`
  - `Check Point`
  - `Case Name`
  - `P`
  - `V2`
  - `T`
  - `M3`
  - `Note`
- One existing backend SLS table is retained for Project JSON compatibility; rows are stored with canonical `Transfer stage` or `Final service stage` metadata.

## FEA source contract v2

The contract now separates declarations for:

### Final stage — ULS and SLS At Service

- Final effective prestress / total loss applied exactly once.
- External portal-frame FEA includes final-stage secondary prestress.
- ULS rows are factored final-stage responses.
- SLS At Service rows are verified final-service responses.

### Transfer stage — SLS At Transfer

- Transfer prestress uses immediate losses only: Friction, Anchorage Set, and Elastic Shortening, applied once.
- Imported rows use the verified transfer-age support/contact and loading state.

### Common

- `P`, `V2`, `T`, and `M3` in each row come from one FEA output state.

LOADS1A contracts migrate their final-stage confirmations, while the new Transfer confirmations intentionally remain pending because the earlier schema did not declare that stage separately.

## Analysis handoff

Analysis readiness now requires all three validated inputs:

1. ULS Final Stage
2. SLS At Transfer
3. SLS At Service

The handoff exposes separate `sls_transfer_rows` and `sls_service_rows`, while retaining combined `sls_rows` for downstream compatibility. No structural solver is run in Loads.

## Preserved behavior

- Selected row-coupled station-force workflow.
- Optional `Check Point` for duplicate Case/Stage/Station locations.
- No mandatory raw Element or I/J-end metadata.
- Canonical storage in kN and kN·m.
- Source-unit and sign normalization only during import.
- Prestress Source ID / Contract ID traceability.
- Existing Project JSON key `crossbeam_sls_loads_table`.
- Prestress Loss calculations and Effective Prestress handoff are unchanged.

## Regression status

- LOADS1A + LOADS1B targeted contract/import tests: 17 passed.
- Project IO + Loads regression set: 93 passed.
- Crossbeam regression was sampled beyond the targeted set; one known pre-existing PTLOSS4B2B1 source-string failure reproduced unchanged. The complete Crossbeam suite exceeded the execution timeout in this environment.

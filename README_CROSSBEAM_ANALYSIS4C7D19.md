# CROSSBEAM.ANALYSIS4C7D19 — SLS audit semantics / Final Service classification closeout

## Scope

Narrow SLS presentation and audit-semantics cleanup on top of D18. No stress equations, demand routing, ACI classification equations, or Segmental physical-joint criteria are changed.

## Changes

- Transfer physical-joint zero-tension failures now show no finite governing utilization at the station/face row; the ordinary ACI transfer-stress utilization is retained separately for audit.
- Final Service charts and tables use explicit ACI classification language:
  - `Class U threshold = 0.62√f'c`
  - `Class C threshold = 1.00√f'c`
  - `Class U/T compression limit = -0.60f'c` only where Class U/T is the active gross-section route.
- Class C rows show the active 0.60f'c compression-limit field as N/A and retain `0.60f'c reference` separately; Class C still requires a cracked transformed-section verification.
- Final Service plot adds both Class U and Class C classification boundaries instead of labeling 0.62√f'c as a generic tension limit.
- SLS Case labels are preserved verbatim from the imported source. Routing remains controlled by the canonical SLS `Stage`; therefore a source Case label such as `ULS-01` is not rewritten by the app.
- Transfer preparation schema bumped to v5 and Final Service preparation schema to v2 so pre-D19 stored SLS results rebuild under the clarified audit fields.

## Engineering contracts preserved

- Concrete fiber stress: compression negative, tension positive.
- Precast Segmental Transfer joints: no tension (`stress <= 0.0 MPa`).
- Precast Segmental Final Service joints: at least 0.70 MPa compression (`stress <= -0.70 MPa`).
- Cast-in-Place: no physical Segment-joint gate.
- Imported Final Service P/M3 are used exactly once; effective/secondary prestress is not added again.
- Class C remains gross classification only until valid cracked transformed-section analysis is available.

## Benchmark source-identity verification

The repository benchmark itself stores Crossbeam SLS rows with `Case Name = ULS-01` while the canonical `Stage` field distinguishes `Transfer stage` from `Final service stage`. D19 therefore does not rewrite the Case label; it makes the stage-routing contract explicit in UI/scope wording and regression coverage.

## Verification

- Python compile: PASS (`app.py`, Crossbeam SLS solver, Analysis UI).
- Focused D13–D19 / Result Summary / Report-QA regression: 65 unique tests, all PASS (executed in batches).
- No full-repository test suite was run.

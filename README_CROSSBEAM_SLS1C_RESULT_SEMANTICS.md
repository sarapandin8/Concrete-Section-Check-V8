# CROSSBEAM.SLS1C.RESULT.SEMANTICS

Clarifies Portal Frame Crossbeam SLS result semantics, preserves the verified external-FEA force boundary, and closes the Project JSON and browser-PDF presentation defects reported after SLS1B.

## Engineering result semantics

- Renames the Analysis dashboard status from `Runtime state` to `SLS check status` for the Crossbeam SLS workspace. A structural `FAIL` no longer implies a solver/runtime failure.
- Shows the governing signed stress and direction. A physical-joint tension is reported as, for example, `+8.958 MPa (tension)` with the required stress `<= -0.700 MPa`; it is not collapsed to `compression 0.000 MPa`.
- Uses Section-level ACI Class U/T/C classification based on the complete gross-section top/bottom stress state.
- Applies ACI 318-19 Table 24.5.4.1 total-load compression limits only to Class U/T members.
- Reports Class C as `Gross classification — COMPLETE` and `Cracked verification — REVIEW REQUIRED` under ACI 318-19 24.5.2.3.
- Does not fabricate a cracked transformed-section result from the same total-response P/M3 bucket. A valid cracked-section model/source remains required before Class C final acceptance.
- Preserves the independent project rule requiring both faces and both fibers of every Precast physical joint to remain at least 0.70 MPa in compression.

## Stage force boundary

- Transfer and Final Service remain separate input buckets and result caches.
- Imported external-FEA P/M3 resultants are used exactly once at each stage.
- If the user intentionally imports identical P/M3 resultants into Transfer and Final Service, the gross-section stresses are intentionally identical.
- Final prestress loss is not applied again inside the stress page because the final effective and secondary prestress response is already included in the verified FEA resultants.

## Presentation fixes

- Adds higher-specificity sidebar colors and WebKit text-fill protection for selected and loaded Project JSON cards.
- Keeps full filenames readable on the pale status backgrounds.
- Hides closed Streamlit expanders in print media so they do not generate an almost-empty trailing browser-PDF page; open audit expanders remain printable.

## Verification

- Targeted Project/SLS/Upload regression: 46 passed.
- Crossbeam regression: 530 passed; 7 baseline failures unchanged (baseline: 527 passed, same 7 failures).
- Full repository regression: 2,362 passed; 13 baseline failures unchanged (baseline: 2,359 passed, same 13 failures).
- No Project JSON schema, ULS solver, Transfer stress equation, Prestress Loss equation, or external-FEA load boundary changed.

## Repo summary

Clarify Crossbeam SLS engineering status, expose signed joint stress, gate Class C on honest cracked-section verification, and harden Project upload and browser-PDF presentation.

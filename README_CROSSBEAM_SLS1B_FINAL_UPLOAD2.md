# CROSSBEAM.SLS1B.FINAL.UPLOAD2

Restores a dedicated Portal Frame Crossbeam `At Final Service` stress workflow beside `At Transfer` and replaces the unreadable post-Apply Project JSON alert with an app-owned, theme-safe loaded-file card.

## Final Service workflow

- Adds deterministic `At Transfer` / `At Final Service` stage navigation inside Analysis -> SLS / Stress & Cracking.
- Reads only active `Final service stage` Crossbeam station-force rows.
- Uses verified external-FEA P/M3 resultants exactly once; effective prestress and secondary prestress are not added again.
- Reuses strict Precast physical-joint coverage and bracket-only linear interpolation for both s- and s+ Section faces.
- Uses ACI 318-19 total-load compression limit `0.60f'c`.
- Classifies gross-section service tension as Class U, Class T, or Class C using Sections 24.5.2.1 through 24.5.2.3.
- Requires cracked transformed-section follow-up for Class C.
- Keeps the project physical-joint minimum compression criterion of 0.70 MPa.
- Shows the separate ACI sustained-load `0.45f'c` requirement as an explicit scope guard because the current Loads workspace has one Final Service total-response bucket.
- Separates Transfer and Final Service result caches and fingerprints.
- Transfer no longer depends on the final-loss contract; Final Service still requires a valid final-loss source.

## Project JSON status UI

- Replaces the native Streamlit success alert shown after Apply with a theme-owned status card.
- Uses dark navy filename text on a pale teal background.
- Forces both CSS `color` and `-webkit-text-fill-color` to prevent global/theme overrides.
- Preserves filename wrapping at narrow sidebar width.
- Does not change Project JSON schema, serialization, canonical restore, or Apply timing.

## Verification

- Targeted Project/SLS/Upload regression: 43 passed.
- Crossbeam regression: 509 passed; 8 baseline failures unchanged.
- Full repository regression: 2,357 passed; 15 baseline failures unchanged.
- Streamlit AppTest: Final Service source ready with 16 imported rows, 5 auto-interpolated joints, 26 station/face checks, and 52 fiber checks; Run completed with no rendering exception.
- No ULS equations, Transfer stress limits, Prestress Loss equations, or other member-workflow solvers changed.

## Repo summary

Restore Crossbeam Final Service concrete-stress review with independent stage routing, ACI service classification, strict joint interpolation, and a readable theme-owned Project JSON loaded status.

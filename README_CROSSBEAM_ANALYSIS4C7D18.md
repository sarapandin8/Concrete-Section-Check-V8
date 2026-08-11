# CROSSBEAM.ANALYSIS4C7D18 — SLS physical-joint stage criteria closeout

## Purpose
Separate the adopted Precast Segmental physical-joint concrete-stress gates by SLS stage while preserving the existing app stress sign convention.

## Locked stress sign convention
- Imported axial force `P`: compression positive.
- Calculated/displayed concrete fiber stress: compression negative, tension positive.

## Adopted Precast Segmental joint rules
### At Transfer
- Physical-joint Top and Bottom fibers are checked independently on both `s-` and `s+` Section faces.
- No concrete tension is permitted at the physical joint.
- Acceptance: signed concrete stress `<= 0.0 MPa`.
- This zero-tension gate is additional to the normal ACI 318-19 Transfer compression/tension stress limits.
- Because the allowable joint tension is zero, no fabricated joint D/C ratio is reported; a controlling zero-tension gate reports utilization as N/A while ACI utilization ratios remain auditable.

### At Final Service
- Existing project rule is preserved unchanged.
- Both Top and Bottom fibers at both `s-` and `s+` faces must remain at least `0.70 MPa` in compression.
- Acceptance with the app stress sign convention: signed stress `<= -0.70 MPa`.

### Cast-in-Place
- No physical Segment-joint stress gates are activated.
- Transfer and Final Service concrete stresses continue to use the applicable ACI criteria through the normal monolithic Zone route.

## Implementation changes
- `concrete_pmm_pro/analysis/crossbeam_sls_transfer.py`
  - added explicit Transfer zero-tension and Final-Service minimum-compression constants;
  - changed the Transfer joint gate from the former service-style `-0.70 MPa` rule to signed stress `<= 0.0 MPa`;
  - preserved the Final Service `-0.70 MPa` rule;
  - added joint no-tension margin/exceedance audit fields;
  - prevents a synthetic D/C from being reported for the zero allowable tension gate;
  - bumped the Transfer preparation/result schema so stored pre-D18 Transfer results become stale and must be recalculated.
- `concrete_pmm_pro/ui/analysis_page.py`
  - Transfer scope, cards, chart joint marker, captions, and PASS wording now describe the zero-tension gate;
  - Final Service chart explicitly retains the `-0.70 MPa` joint marker.
- `app.py`
  - Result Summary / Report-QA capacity labels and Design Basis now distinguish Transfer `<= 0.0 MPa` from Final Service `<= -0.70 MPa`.

## Verification
- Python compile check: PASS.
- Focused SLS / Result Summary / Report-QA regression: `60 passed`.
- Added D18 regression tests proving:
  - `-0.50 MPa` joint compression passes At Transfer but fails the Final Service `0.70 MPa` rule;
  - small positive joint tension fails Transfer even when below the ordinary ACI transfer tension limit;
  - no finite D/C is fabricated for the zero-tension joint gate;
  - Transfer schema bump invalidates pre-D18 cached Transfer results;
  - downstream Result Summary / Report-QA wording preserves the two different stage criteria.

## Engineering equations
No ACI stress equation was changed. D18 changes the adopted project-specific Precast physical-joint acceptance criterion at Transfer and keeps the existing Final Service joint criterion unchanged.

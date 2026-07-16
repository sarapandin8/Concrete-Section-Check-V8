# Concrete Section Pro — CROSSBEAM.RB2G

## Milestone

`CROSSBEAM.RB2G — Combined cross-section reinforcement preview`

## Implemented

- Replaced the old stacked Combined review with one layer-ordered Crossbeam section figure.
- Added concrete, void, transverse cage/tie, longitudinal bars, and centroid in the required visual order.
- Added preview-only 25 mm transverse corner bends.
- Added a Solid closed-tie centerline that follows the section's bottom outer fillets.
- Kept Hollow left/right web cages rectangular and independent from the inner void chamfers.
- Added a conservative geometric containment check using longitudinal and transverse bar radii.
- Added visible `REVIEW REQUIRED` diagnostics by longitudinal face/layer; no engineering input is moved automatically.
- Retained the accepted full-length CROSSBEAM.TR1A transverse elevation below the combined section figure.
- Preserved the separate Longitudinal and Transverse / Shear preview modes.

## Important default-state finding

The default longitudinal and transverse center offsets are both 50 mm. Therefore the default generated longitudinal bars are not geometrically inside the transverse cage/tie. RB2G reports `REVIEW REQUIRED`; it does not silently alter either template. A deeper longitudinal center offset can produce `READY FOR DETAILING REVIEW` when all generated bar circles clear the transverse steel.

## Scope exclusions

This milestone does not provide solver credit or certify ACI minimum transverse reinforcement, `φVn`, torsion, confinement, anchorage/development, D-regions, tendon continuity, or segment-joint shear transfer. Crossbeam rebar Project JSON persistence remains a later milestone.

## Validation

- Changed Python files compiled successfully.
- New RB2G and related focused tests: 30 passed.
- Complete Crossbeam suite: 97 passed.
- Full repository suite: 1,926 passed; 6 unrelated failures were reproduced identically on the accepted CROSSBEAM.TR1A baseline.
- Static Plotly PNG review completed for default Solid and Hollow combined figures.
- Streamlit server startup smoke test completed successfully.
- No live interactive Streamlit browser review was claimed.

## Repo summary

Add a true combined Crossbeam reinforcement section preview with transverse bars outside longitudinal bars, solid ties following outer fillets, rectangular hollow web cages, and 25 mm bend fillets for realistic detailing review.

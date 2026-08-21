# IGIRDER.ULS5A — Shear QA Closeout

This milestone starts from `IGIRDER.ULS5 — AASHTO Prestressed I-Girder Shear General Procedure` and closes the visual/decision QA items identified from `shear(2).pdf`.

## Near-support critical-section semantics

- For the adopted AASHTO LRFD 5.7.3.2 route where the support reaction introduces compression into the end region, the explicit `CRITICAL SHEAR SECTION` at approximately `dv` from each support is the design section for that near-support region.
- Ordinary imported `LOAD STATION` rows between the support and the adopted critical section remain visible for the demand diagram and audit, but they no longer independently govern the sectional shear D/C.
- This prevents arbitrary station spacing such as `x = 1.000 m` from outranking an inserted `x = dv = 1.051 m` design section.
- The AASHTO exception is visible: a concentrated load within `dv`, or a support reaction that does not introduce compression into the end region, requires support-face review. Concrete Section Pro does not silently infer that exception from a generic FEA resultant table.

## Engineering variable help

The Shear workspace now includes a collapsed `Variable definitions / Engineering terms` reference with concise definitions, units, physical meaning, and code basis for key variables including `Vu`, `bv`, `d`, `dv`, `epsilon_s`, `beta`, `theta`, `Vc`, `Vs`, `Vn`, `phiVn`, `Av/s`, `Av/s,min`, `smax`, `Aps`, `fpo`, `Vp`, and `phi`.

## Calculation equations and trace

The Shear workspace now includes a read-only `Calculation trace / Equations — governing shear station` expander. It reads the governing stored/calculated row and does not rerun the solver. The trace shows:

- longitudinal strain `epsilon_s` and the negative-strain adoption branch;
- `beta` and `theta` General Procedure equations;
- `Vc` with the SI-safe equivalent of the AASHTO source coefficient;
- `Vs` for the active vertical-stirrup route;
- nominal resistance `Vn` and its upper limit;
- resistance factor `phi` and `phiVn`;
- final strength D/C;
- actual substitution values for the governing station.

The visible strain card now reports raw and adopted strain in consistent per-mille units while retaining the dimensionless raw strain for audit.

## Report / QA stored equation trace

For the Precast I-Girder workflow, Report / QA now reads the stored current Shear result and presents a fuller equation / intermediate-value audit without rerunning the shear solver. The report-side trace includes the governing station and case, demand, geometry, raw/adopted strain, beta/theta, Vc/Vs/Vn, phi/phiVn, detailing quantities, prestress participation, General Procedure branch, resistance-factor branch, and the same variable-definition reference used by Analysis.

## Check-specific limitations

The final `ULS strength-check limitations` expander is now check-specific on the Shear page. It no longer repeats unrelated Flexure and Torsion limitations while reviewing Shear.

## Result-state behavior

Because the governing-row semantics changed, the I-Girder Shear result version is bumped to `IGIRDER.ULS5A.shear-qa-closeout`. Dependent Combined V+T is also version-bumped/review-guarded. Accepted Construction Flexure, Final Composite Flexure, Girder-Deck Interface Shear, SLS, and prestress-loss states are not globally invalidated.

## Engineering equations

No General Procedure resistance equation was changed from ULS5. This milestone changes governing-row eligibility near supports, adds read-only equation/variable traceability, and tightens check-specific UI semantics.

## Verification

- Production compile: PASS for `app.py` and modified Shear/code-basis modules.
- Focused I-Girder + compact Beam/Girder regression: 133 passed.
- Result Summary / Report-QA regression: 19 passed.
- Crossbeam Shear/Torsion/CIP/summary/report regression: 48 passed.
- Total relevant focused regression in this milestone: **200 passed**.
- Full repository suite was not run to completion for ULS5A; no full-suite PASS is claimed.

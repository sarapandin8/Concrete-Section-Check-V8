# Concrete Section Pro — IGIRDER.VTQA1 calculation review

Reviewed against the supplied **AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5**, particularly printed pages 5-61 through 5-78. This review covers the normal-weight, solid precast I-girder sectional route with straight pretensioned strands. It does not certify a composite deck torsion mechanism or the user's final girder design.

## Findings and corrections

| Item | Finding / released behavior | Source |
|---|---|---|
| Automatic effective shear depth | The former area-weighted reinforcement centroid was not the force-weighted de defined by the specification. Automatic I-girder dv now uses the deliberately conservative **0.72h** value. A larger verified de/resultant-based dv can be entered through the existing Sections → Rebar depth input. Manual dv exceeding the physical section depth blocks calculation; it cannot silently fall back to a centroid estimate. The displayed d remains an audit estimate. | 5.7.2.8 and Eq. 5.7.2.8-2; C5.7.2.8 |
| Nominal shear resistance | Vn=min(Vc+Vs+Vp,0.25fc bv dv+Vp); Vc=0.0316 β√fc bv dv in ksi/in units, converted explicitly; Vs=(Av/s)fy dv cotθ. Vp=0 for this straight-strand model. | 5.7.3.3 |
| General Procedure | β=4.8/(1+750εs), θ=29+3500εs. Negative εs uses the permitted zero branch; maximum adopted εs=0.006. Mu is raised to the required shear/depth minimum in the strain equation. App Nu is compression-positive and converted to AASHTO tension-positive. | 5.7.3.4.2 |
| Longitudinal source and development | Undefined bar materials receive **zero elastic stiffness**, replacing the former implicit Es=200 GPa credit. Undefined fy never becomes a material assumption. Ordinary As stiffness and force participation reduce once with available length/verified ld; unconfirmed continuity/development receives zero credit and withholds final acceptance. Existing verified Flexure development settings are reused until an explicit V/T setting exists. | 5.7.3.4.2, 5.10.8.2.1a |
| Strand development | Existing transfer/development source remains: fpo ramps through transfer length from each group's bond commencement; developed Aps is reduced, including sleeves and physical cut ends. No full-strength strand is invented at x=0 or x=L. | 5.9.4.3.2; 5.7.3.4.2 |
| Design concrete strength | Shear fc is limited to 15 ksi=103.421 MPa; torsion and torsion-required combined checks use at most 10 ksi=68.948 MPa. Nominal flexural material properties are not overwritten by these shear/torsion design limits. | 5.7.2.1 |
| Nominal torsion resistance | Tn=2Ao(At/s)fy cotθ λduct. At is **one leg**, while physical shear Av uses the actual effective leg count. λduct=1 within this model's stated route. Ao follows the solid-section shear-flow path with be=Acp/pc. It is neither gross composite area nor 0.85Aoh. | 5.7.3.6.2; C5.7.3.6.2 |
| Investigation threshold | Torsion design is required when abs(Tu)>0.25φTcr. φTcr is a cracking reference, not φTn. The source coefficient is **0.126**, in ksi/in units. Existing axial/prestress K guards and transferred final effective prestress remain. | 5.7.2.1 |
| Resistance factor / transverse fy | Existing bonded/debonded φ=0.90/0.85 policy and 75 ksi transverse design-fy ceiling, with the existing EPP strain screen, are retained. | 5.5.4.2; 5.7.2.7 |
| Shared hoop | Above threshold, the actual hoop must supply **max(Av/s shear, Av/s minimum)+2At/s torsion**. Torsion allocation is removed before any Vs relief is credited to the longitudinal equation. A standalone shear PASS plus a standalone torsion transverse PASS is insufficient for final coupled acceptance. | 5.7.3.6.1 |
| Longitudinal combined force | Developed Aps·fps+As·fy must satisfy Mu/(φdv)+0.5Nu(AASHTO)/φ+cotθ·hypot(abs(Vu/φ−Vp)−0.5Vs,0.45ph Tu/(2Aoφ)). Existing nominal fps source, prestress dominance, corner/perimeter confirmations and source gates remain. | 5.7.3.6.3-1; 5.7.3.5 |
| Spacing | Retain the solid I-girder route's 5.7.2.6 minimum/maximum-spacing checks. No unsupported ACI-style ph/8 rule was added to this AASHTO route. | 5.7.2.5/.6; 5.10.8.2.6d |
| M2 and V3 | Original Muy/M2 and Vux/V3 values remain reference-only. They no longer alter the I-girder torsion K guard or manufacture a biaxial blocking reason for the primary combined check. | Explicit user workflow requirement |
| Incomplete calculation | Known Veff/spacing/transverse results are retained when longitudinal material/fps data is missing. A genuine known failure remains FAIL, but overall D/C remains unavailable and the row is labelled PARTIAL. Missing data is not represented as zero capacity or a full check. | Source/readiness control |

The combined compression/Veff limit is explicitly labelled a **conservative additional guard**, rather than a separate exact interaction equation supplied by the specification.

## Section and stage basis

Current V/T geometry is the **precast I-girder**: its web width, h, Acp, pc, Ao and actual hoop ph. Deck width Be is used separately by positive Final-Composite flexure and by the existing positive nominal fps preparation for combined longitudinal resistance. Composite deck concrete is not automatically added to Tn: a verified composite torsion/shear-flow path, closed cage participation through the deck, interface force transfer, and appropriate material/stage model would be required first. This release does not implement or certify that route.

The original imported primary forces and signs are retained. P=0 is a user Excel edit, not an app override. M2/V3 remain visible raw references. Native CSI Max/Min envelope components do not prove simultaneous action vectors; completing materials/cage inputs alone cannot certify a final coupled PASS.

## Photographed cage and missing inputs

The latest screenshot already has Use for Torsion, Closed Loop and 135° Hook checked for all five zones, and corner/perimeter confirmations checked. These inputs were respected in reproduction. **Selecting the transverse cage does not define the material of the longitudinal bars.** The available source JSON contains 34 bars named SD40 with no matching rebar material catalog entry; it also leaves ordinary bar continuity/development unconfirmed.

Before this release, 84 of 88 combined check rows stopped at unresolved SD40 and the other four at zero developed longitudinal strain stiffness. The displayed combined graph had no numeric checks. With the new source handling, this same photographed-cage reproduction retains **88 partial Veff/spacing rows and 84 numeric transverse rows**, while overall D/C remains unavailable. Known sub-check failures are reported without masquerading as completed longitudinal checks.

On Analysis, enter the actual verified SD40 fy, confirm continuity only if true, and enter the verified governing ld/end anchorage. The inline fy starts at **0**, and Define is disabled until a value is supplied. This avoids an assumed grade strength. The existing bar geometry and name stay intact. Calculate Shear + Torsion refreshes all three V/T results in one action.

## Verification and numerical examples

The separately labelled **hypothetical in-memory QA** uses the original Left Exterior Girder native workbook, P=0, photographed cage confirmations, SD40 fy=390 MPa, continuous full-span bars, ld=1000 mm and **unanchored physical bar cut ends**. These values demonstrate app operation and are not applied to the user's production input files.

Independent US-customary substitution checks **1,723 scalar values** over 84 finite shear rows, 59 finite torsion-strength rows and 84 completed combined rows. Maximum relative discrepancy is less than 8×10⁻¹³. This verifies the listed equations and unit conversion for these fixtures, not every possible material/model branch. Additional regressions test the 15/10 ksi caps, missing material credit, single development scaling, invalid depth rejection, reference-only M2/V3, stale result invalidation, original case pairing and preserved graph gaps.

| Hypothetical verified-input QA | Governing result |
|---|---|
| Shear strength | D/C **1.5095**, x=18 m, Max/set 2 |
| Torsion transverse component | D/C **1.4310**, x=2 m, Max/set 1 |
| Combined transverse reinforcement | D/C **2.1420**, x=2 m, Max/set 1 |

The remaining FAILs reflect insufficient supplied sectional resistance under those QA assumptions. They are not removed by chart cleanup. Physical ends with zero developed longitudinal stiffness retain source-review gaps for θ/φTn/combined longitudinal calculation; end-region anchorage and bearing require their own design assessment.

Default graphs have **two legend entries**: Max D/C and Limit=1.0, with one governing marker. The maximum comes from each original case/check ratio; demand and resistance envelopes from different cases are never divided. A selected-case view shows the signed imported force and that same case's ±resistance. Connecting lines are visual interpolation only. The combined graph explicitly states partial row count; it shows the largest **available** component and does not certify missing components. Detailed equations, source rows, cracking thresholds and component diagrams remain in collapsed panels.

Evidence: `qa/evidence/igird_vtqa1/independent_equation_substitution.csv`, `equation_verification.json`, `vtqa1_ui_result.json`, and the fresh extraction regression summary. PNGs render the exact production Plotly trace coordinates through Matplotlib. Standalone HTML contains the interactive Plotly figure. They are scientific previews, not browser screenshots.

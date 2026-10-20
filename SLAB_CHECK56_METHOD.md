# SLAB.CHECK56 — calculation basis and verification

This release adds a bounded section-review calculator. It is a statically equilibrated N–M sandwich field using stated AASHTO component limits, with separate conservative shear screens. It does not establish a complete code-compliant deck design, a complete STM, strain compatibility, anchorage or a validated 3D N–M–V resistance domain.

## Source records and geometry

Use the supplied concurrent row components F11/F22/F12/M11/M22/M12/V13/V23. The project basis treats the components within each supplied U1A/U1B/U2A/U2B Max/Min row as concurrent. No component-wise synthetic combination is assembled. Keep every original corner and source identity before taking an element envelope.

Native table joins recover the original Area corners, generated analysis joints, original local axes and corner thicknesses. Bilinear parent mapping interpolates Thick1..4 without substituting the project-wide slab thickness. The physical longitudinal direction follows the straight bridge station progression; transverse is perpendicular within the slab plane. All four actual bar heights are retained. Convex planar quadrilaterals, near-horizontal deck normals and constant-width straight alignment are scope guards. Unsupported geometry/axis definitions stop calculation.

At each corner, rotate membrane and moment tensors by R N Rᵀ and R M Rᵀ; reversal of local 3 also reverses the moment signs. Rotate the transverse shear vector consistently. Original eight source columns remain unchanged. There is no moment transport to another origin.

## Units and CSI signs

Per unit width, kN/m is numerically N/mm. Multiply kN·m/m by 1,000 to obtain N·mm/mm. Measure z from the shell midsurface, positive toward physical top. CSI defines Mij = −∫z σij dz. Positive direct moment therefore gives compression at the positive-3 surface and tension at the opposite surface. Moment-sign and tensor-reversal tests cover this convention.

## Equilibrated N–M field

Two concrete face layers have equal depth a and centroid positions zt = h/2 − a/2 and zb = −h/2 + a/2. Concrete is compression-only; the four provided bar mats are tension-only at their actual z coordinates. A ±45° concrete compression field carries each face's in-plane shear q. Its compression tensor includes |q| in both diagonal terms and −q off-diagonal; additional direct compression Cx and Cy is nonnegative. The maximum principal compression controls concrete utilization.

Let K = −1,000 M. Face shears follow exact equilibrium:

    qt = (Kxy − zb Nxy)/(zt − zb)
    qb = Nxy − qt

For each steel direction, solve the two axial/moment equilibrium equations for tensile steel and additional concrete compression. Four face-activity candidates are evaluated: no extra compression, top extra compression, bottom extra compression, or compression at both faces. Direct concrete compression and parallel tensile steel at the same face are mutually exclusive. Diagonal compression may coexist with orthogonal steel ties, as in a cracked membrane field.

Search 21 face-depth candidates: 13 fixed fractions from 0.025h to 0.45h, four tie-capacity-based depths and four uniaxial demand-based roots. Evaluate all 4 × 4 activity pairs at each depth. Prefer candidates with qualified shear applicability, then the smallest maximum utilization. This finite admissible-field search is not a global optimization or a full strain-compatible constitutive analysis.

Reconstruct Nx/Ny/Nxy/Mx/My/Mxy independently from the selected field. The acceptance residual is the largest component error divided by max(1, |that source component|), after returning moments to kN·m/m. A residual over 1e-7 blocks results.

## Adopted component limits

References below refer to the supplied AASHTO LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5. These component rules are inputs to the scoped field model; adopting them does not establish the validity of every field, node or transfer region for final design.

| Item | Adopted rule | Reference |
|---|---|---|
| Reinforcing tie | φs = 0.90; resistance φs As fy | 5.5.4.2 |
| Concrete field | φc = 0.70, efficiency ν = 0.45; design compression limit φc ν f′c | 5.5.4.2; 5.8.2.5.3a |
| Material range | Normal-weight concrete; f′c ≤ 15 ksi | Scope of adopted component limit |
| One-way shear | φv = 0.90; no Vs or Vp credit | 5.5.4.2; 5.7.3 |
| Shrinkage/temperature | Conservative infinite-width bound from 5.10.6, per face/direction; fy credit capped at 75 ksi; 0.11–0.60 in²/ft | 5.10.6 |
| Bar maximum spacing | min(1.5h, 18 in) | 5.10.3.2 |

Deck f′c, fy, bar size, spacing and physical covers come from the current project's existing inputs. Transverse bars are outside longitudinal bars. Missing values are not replaced by invented steel. Local CSI thickness controls fit; overlapping opposite mats block calculation. The normal rebar modulus used by the conservative shear strain screen is Es = 200,000 MPa.

## Separate shear and additional tie screens

The concrete core available after reserving the face layers limits the shear effective depth:

    dv = min[h − 2a, max(0.9(h − maximum bar-centre cover), 0.72h)]
    Vu = sqrt(Vx² + Vy²)

For h < 16 in without principal membrane tension, use β = 2 under 5.7.3.4.1. Otherwise a conservative strain upper bound is calculated using absolute principal moment, positive principal membrane force, Vu and half the smallest mat stiffness. Only if that bound is ≤0.006 is the no-stirrup general screen used with εs = 0.006. No aggregate-size credit is assumed; ag = 0, sx = h and sxe is bounded to 12–80 in. Shear demand near zero is a qualified zero-demand case. An unqualified nonzero-shear row has NaN shear D/C and remains REVIEW if known checks pass.

The implemented Vc coefficient is evaluated in consistent US units and converted to MPa, with the 0.25 f′c ceiling. The reduced core depth is an additional conservative modelling restriction, not a demonstrated simultaneous 3D stress field.

The longitudinal shear-tie addition is based on 5.7.3.5. In the shear direction the full nominal flange force is conservatively checked at each face, with no Vs/Vp relief. Projecting the tension field onto orthogonal reinforcement also requires |Nxy| in both directions:

    ΔTV,x = (Vx² + |Vx Vy|)/(Vu φv) × cotθ
    ΔTV,y = (Vy² + |Vx Vy|)/(Vu φv) × cotθ

Use θ = 45° for the shallow route and the conservative cotangent at 29° for the general tensile-strain route. The provided steel supply is used once:

    As,req,i = max[(TNM,i/φs + ΔTV,i)/fy,i, As,shrinkage,i]

Multiply mm²/mm by 1,000 for mm²/m. This extra tie screen is reported separately; it is not inserted into the six-component N–M equilibrium reconstruction or claimed to validate full 3D coupling.

## Results and interpretation

The field D/C is the maximum of the steel requirement ratios, concrete compression, shrinkage minimum, bar maximum spacing and qualified one-way shear. Unknown shear is absent from that numeric partial-check score but is preserved as unknown and forces REVIEW. Known failures remain visible even if another check is unresolved.

Wood–Armer values max(0, ±Mx + |Mxy|), max(0, ±My + |Mxy|) are bending-only conservative references in the trace. They are not used to replace membrane demand or independently enveloped with another record's actions.

The plan map takes the governing source corner/case of each actual mesh element without averaging, clipping peaks, zeroing endpoints or filling missing regions. Known exceedances outrank REVIEW; REVIEW outranks a numerically passing subset. Incomplete case/corner coverage is grey unless a known exceedance already controls. Each displayed row retains its original concurrent source vector. Four mat summaries are all-case steel summaries; independent concrete/shear checks still apply.

## Independent benchmarks

For h = 350 mm, f′c = 35 MPa, four mats As = 1,000 mm²/m, fy = 390 MPa, longitudinal centre cover 64 mm and transverse centre cover 48 mm:

- Longitudinal tie design resistance is 351 kN/m. Adopted concrete stress is 11.025 MPa. The force-couple compression depth is 31.836735 mm and the design moment of this field is 94.798653 kN·m/m. Mu = 40 gives D/C = 0.4219469234. Tests cover both directions and both signs, with zero tensile force in the directly compressed face.
- Nx = 100 kN/m gives 50 N/mm tension at each longitudinal mat with no moment.
- Nx = −100 kN/m gives 50 N/mm direct concrete compression at each face and no invented steel compression credit.
- Nxy = ±60 kN/m gives 30 N/mm tension in each orthogonal mat and ±30 N/mm face shear.
- A skew quadrilateral with thicknesses 200/350/300/250 mm has independently interpolated thickness 259 mm at the test point.
- A separate reconstruction checks six components using asymmetric actual mat heights. Five hundred signed random records check equilibrium and the face-activity constraint.

Additional tests cover shear tie force, phi use, minimum steel, bar fit, unsupported code/materials, invalid actions, axis rotation/reversal, stale results, complete/partial coverage, chart peaks, Project JSON reset and Calculate-only UI behavior.

## Remaining design work

No final-design acceptance is implied. Complete STM topology/nodes/anchorage, strain-compatible or otherwise independently validated combined 3D resistance, flexural-minimum reinforcement under 5.6.3.3, cover/exposure, fatigue, local wheel/punching, support regions and SLS remain separate. Large point requirements near supports/load-transfer regions need regional assessment before detailing. Results stay outside the existing girder Summary / Report.

## Primary authored references

- AASHTO, LRFD Bridge Design Specifications, Ninth Edition (2020), Section 5, supplied with the project; clauses listed above.
- [CSI — Shell internal force and stress output conventions](https://docs.csiamerica.com/help-files/csibridge/Output_Conventions/Shell_Element_Internal_Forces_Stresses_Output_Convention.htm).
- CSI Analysis Reference Manual, Shell Element, Internal Force and Stress Output; the CSI-authored definitions include Mij = −∫x3 σij dx3. [CSI-authored manual mirror](https://www.scribd.com/document/137119139/CSI-BRIDGE-Analysis-Reference-Manual).
- [CSI — Area Local Axes](https://docs.csiamerica.com/help-files/csibridge/Advanced_tab/Assign/Area/Area_Local_Axes.htm).
- [P. B. Lourenço — Reinforced Concrete Design, contributed chapter](https://phoogenboom.nl/b14_chapt_16.pdf), discussion of sandwich layers, real lever arms and transverse shear.
- [Autodesk — Wood and Armer moments](https://help.autodesk.com/cloudhelp/ENU/ASBD-InProdUS/files/structure/tech_info/ti_rft_moments/ASBD_InProdUS_structure_tech_info_ti_rft_moments_Wood_and_Armer_Moments_html.html).
# Superseded by SLAB.AUDIT58

The unconditional full shear-tie additions and coupled face/core screening described in this historical method are withdrawn. Use [SLAB_AUDIT58_FINDINGS_TH.md](SLAB_AUDIT58_FINDINGS_TH.md) for the current separate N–M steel / shear component scope and combined-interaction REVIEW gate.


# IGIRDER.COUPLED34 — coupled research resistance

This release implements an explicitly **unvalidated research model**. It does
not deliver production-ready Full composite Tn or V–T acceptance. The numerical
model, its contact discretization, and the physical composite structure have
different validation requirements. No number from this model is sent to the
production resistance owners, Result Summary, Report/QA or saved result data.

## Mechanics actually implemented

The candidate is one central rectangular closed cell, with width equal to the
measured U-leg centre spacing A. Its height extends from the girder bottom
cover/bar centreline to the top of the measured hook centreline B-db/2. It is a
hypothesis, not a reconstruction of the actual I-hoop, splice, or slab cage.
Assigned slab width Be is not its torsional cell width. Its Ao/ph do not replace
the accepted girder Ao/ph in any other engine.

Internal units are N, mm and MPa. For vertical V and torque T:

    qV = |V|/(2 dv)
    qT = T/(2 Ao)
    required force per vertical leg per member length = (qV + |qT|)/cot(theta)
    required slab closing-tie force per length = |qT|/cot(theta)

Both vertical legs are conservatively checked for the additive V/T side. The
girder segment, U segment and slab closing segment form a series path: their
resistances are limited individually. Their Tn values are never added.

The same U-leg tension variables Ti must also satisfy the joint free body:

    sum(Ti) - sum(Cj) = lambda n
    sum(yi Ti) - sum(yj Cj) = lambda mx
    sum(Sxj) = lambda qx; sum(Syj) = lambda qy
    -sum(yj Sxj) = lambda (mz_background + A qT)

Cj is compression-only contact. Directional nonnegative friction rays form an
inscribed polygon within the circular Coulomb cone, not a circumscribed one.
Both local friction <= mu Cj and total friction <= mu sum(Ti) are enforced.
External compression is not automatically credited as additional Pc. The last
equation retains opposing longitudinal interface shears under pure torque:
zero net qx does not mean zero interface traction. Girder Tu is never assigned
to the roll action mx.

M/N are held fixed while lambda scales V/T and the explicit interface
background vector together. The longitudinal force screen follows the
solid-section concurrent force form in AASHTO 2020 5.7.3.6.3-1, with Vc=Vp=0
and Vs equal to the carried nominal-equivalent V. The same developed ordinary
bar force reserve supplies M/N and V/T. The adapter uses the weaker of its two
half-section ordinary-bar reserves; prestress is omitted. Scalar force credit
does not establish the necessary corner/perimeter bar distribution, nodal
force transfer, or strain compatibility.

The current adapter uses theta=45 degrees, zero Vc, zero cohesion, and a
diagonal-flow cap of 0.25 fc teff sin(45) cos(45), where teff is the minimum of
A/2, web/2 and slab thickness/2. **This diagonal cap is an explicit research
assumption. It is not a calibrated cracked-concrete stress–strain law or an
AASHTO certification of the composite section.** Closing-bar fy is provisionally
the lower known dowel/slab reinforcement grade; actual transverse-bar grade
and closure still need drawing verification.

Pure model Tn is evaluated at V=M=N=external interface loads=0 with all model
factors=1. It is not the torsion remaining at the actual M/N/V. The optional
factored model uses steel=.90, contact/diagonal=.70 and interface=.90, explicitly
as model factors. They do not make this a validated LRFD composite method.

## Source and numerical guards

- All original force rows and reference snapshots are retained.
- Actual model V–T requires one declared simultaneous source vector, immutable
  CSI origin, and an exact member/app-case/station interface background state.
- New advanced interface states explicitly include the background traction
  moment mz; they are not inferred from a case name, an envelope, or Girder Tu.
  If starting with total interface traction resultants, an independent free
  body must distinguish the closed-cell circulatory part before this research
  background vector can be used. No automatic recovery is implemented here.
- Each actual vector is transported once to the local composite resistance
  centroid. Nonzero M2/V3 blocks this uniaxial research calculation.
- Missing/ambiguous joint states are not replaced by zero.
- LP equilibrium, capacity bounds, primal/dual optimality and finiteness are
  independently checked with scaled tolerances. A feasible point alone does
  not establish maximum radial model resistance.
- Contact 32/64-strip sensitivity is reported. Model V–T is withheld if the
  nominal refinement change exceeds 2% or either nominal solve is unavailable.

## Structural validation not completed

The present formulation does not solve slip/opening compatibility, sectional
strain compatibility, concrete crack evolution, dowel shear/bending, local
splitting, slab transverse bending, splice bond transfer, nodes, fatigue or
end D-regions. It has not been calibrated or validated against tests of this
girder–slab–U-dowel assembly. Software tests and contact refinement do not fill
those gaps. Production fields are hard withheld; no user checkbox, uploaded
evidence label, drawing reference or numeric model pass can enable them.

The measured 90-degree U hook may function as developed tension anchorage in
the existing joint model. It does not automatically establish a fully closed
torsion path. AASHTO 2020 5.7.2.4 and 5.10.8.2.6d distinguish these details;
the latter specifies full continuity and 135-degree standard torsion hooks,
and gives a 1.3 ld lap condition for paired U units. This release reports that
condition but does not certify execution of the actual cage or use the special
alternative lap exception as an automatic shortcut.

## Evidence needed to develop a production method

1. Document the actual U/I-hoop/slab transverse and longitudinal cage, laps,
   anchorage, cover, node zones and support-region load paths. A connection
   drawing must identify how the complete system closes and transfers force;
   a 90-degree tail length alone cannot define it.
2. Recover simultaneous component/free-body actions with verified axes,
   origins and external loads. Validate signed section equilibrium and joint
   tractions at several stations; use no fitted origin as resistance metadata.
3. Add a compatible nonlinear cracked-concrete / steel / bond-slip / contact
   formulation, or a fully detailed code-compliant 3D strut-and-tie route with
   all nodal and anchorage checks. Demonstrate the intended scope and failure
   modes before selecting resistance factors.
4. Independently compare pure torsion, vertical shear, combined V/T at several
   ratios and signs, and concurrent M/N against representative physical
   composite tests and a separately implemented analysis. Include interface
   slip/opening and failure location, not just peak load. Predeclare acceptance
   criteria and validate separate specimens from any calibration set.

The production gate may be reconsidered only in a separately verified model
version after those items are complete. COUPLED34 remains a review tool.

## References checked

- User-supplied AASHTO LRFD 9th Edition (2020), Section 5: 5.7.2.4,
  5.7.3.6.1–3, 5.7.4 and 5.10.8.2.6d. Printed pages 5-77 and 5-189 were also
  inspected visually in the supplied PDF.
- O. Bayrak, *Combined Shear and Torsion*, ASPIRE Spring 2017:
  https://www.aspirebridge.com/magazine/2017Spring/AASHTO-BridgeDesign-Aspire-SPG2017-Web.pdf
  Describes concurrent actions and the equilibrium/compatibility requirement
  for refined analysis. It is not validation of the present composite model.
- K. N. Rahal and M. P. Collins (2003), *Experimental Evaluation of ACI and
  AASHTO-LRFD Design Provisions for Combined Shear and Torsion*, DOI
  10.14359/12601:
  https://www.concrete.org/publications/internationalconcreteabstractsportal.aspx?ID=12601&m=details
  The published abstract concerns four large nonprestressed specimens, not
  the user's precast/slab/U-dowel assembly; no claim of composite validation is
  made from it.

## Reproduce software checks

Run `tests/test_igird_coupled34.py` with real Streamlit installed. Analytical
limits cover weakest series tie, the concurrent longitudinal reserve, pure
shear, V/T sharing, opening with friction, opposing interface shear couples,
signed equilibrium, an inscribed friction cone, mesh refinement, zero strength,
invalid input and source/reference/persistence guards. Browser verification
uses `qa/igird_coupled34_browser_verify.py`. Its optional synthetic U detail is
for software QA only and must not overwrite a project drawing/input model.

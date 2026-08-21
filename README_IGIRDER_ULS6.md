# IGIRDER.ULS6 — AASHTO Prestressed I-Girder Torsion General Procedure

**Date:** 2026-08-21  
**Baseline:** `concrete-section-pro_IGIRDER-ULS5B-shear-ui-semantic-polish.zip`  
**Scope:** Standalone ULS Torsion for `Bridge Beam / Girder → Precast I-Girder` under AASHTO LRFD 9th Edition. Combined Shear + Torsion longitudinal certification remains the next milestone.

## Engineering route

The I-Girder route no longer uses the legacy fixed `theta = 45 deg` torsion preview. For every active torsion station it uses the AASHTO Section 5 source route below.

1. **Investigation threshold — Article 5.7.2.1**
   - Torsion is investigated where `|Tu| > 0.25 phi Tcr`.
   - Solid section: `Tcr = 0.126 K lambda sqrt(f'c) Acp^2 / pc` in the AASHTO source units; the implementation evaluates the dimensional coefficient through explicit US-customary → SI helpers.
   - `K = sqrt(1 + fpc/(0.126 lambda sqrt(f'c)))`, subject to the AASHTO upper-bound rules.

2. **K source hardening**
   - `fpc` is based on effective prestress after losses and is ramped through the pretension transfer length from the actual bond commencement, including debonded strands.
   - For factored axial force, the K input uses `fpc - Nu/Ag`; AASHTO takes `Nu` positive in tension while Concrete Section Pro Loads uses compression-positive, so the sign conversion is explicit in the audit trace.
   - When gross-section extreme tensile stress from factored load plus effective prestress exceeds `0.19 lambda sqrt(f'c)`, `Kmax = 1.0` as required by Article 5.7.2.1.
   - If gross `Ixy` is non-negligible, or the centroid is detected in a flange while a named web/flange-junction `fpc` source is unavailable, the app conservatively suppresses prestress enhancement with `Kmax = 1.0` rather than inventing a stress location.
   - If the axial adjustment makes the K square-root radicand negative, the row returns REVIEW/NOT READY; capacity is not fabricated.

3. **Torsion-modified General Procedure — Article 5.7.3.4.2**
   - For a solid section requiring torsion:
     `Veff = sqrt[Vu^2 + (0.9 ph Tu / (2 Ao))^2]`.
   - `Veff` replaces `Vu` in the longitudinal-strain equation.
   - The existing ULS5 prestress transfer/development participation is reused in `epsilon_s`.
   - `beta` and `theta` are station-dependent; `theta` is not fixed at 45 degrees.
   - If the active transverse reinforcement is below the Article 5.7.2.5 minimum, the below-minimum General Procedure branch remains source-blocked because `sx/ag → sxe` is not owned by the current project model; no `sxe` is invented.

4. **Solid-section torsional resistance — Article 5.7.3.6.2**
   - `Tn = 2 Ao (At/s) fy cot(theta) lambda_duct`.
   - `At` is one leg of the verified closed transverse torsion reinforcement.
   - For the solid I-Girder, `Ao` is the area enclosed by the centerline of the effective width `be = Acp/pc` per C5.7.3.6.2; the ACI `0.85Aoh` shortcut is not used.
   - `ph` is the actual centerline perimeter of the verified closed torsion hoop and must be user-confirmed in `Sections → Rebar`.

5. **Transverse reinforcement design fy — Article 5.7.2.7**
   - Torsion is outside the flexural-shear-only 100 ksi exception.
   - For nonprestressed transverse reinforcement above 60 ksi, the design strength is the stress at strain 0.0035 and not more than 75 ksi.
   - Under the app's current elastic-perfectly-plastic reinforcing-steel basis, the explicit controlling cap is 75 ksi (`517.1068 MPa`). The entered and adopted design fy are both exposed in the audit trace.

6. **Detailing source gates**
   - A valid torsion design-required row needs a user-confirmed fully continuous closed torsion loop, actual `ph`, active transverse zone coverage, and 135-degree standard-hook anchorage confirmation.
   - Minimum `Av/s` and maximum transverse spacing remain explicit AASHTO gates.
   - No minimum hoop, `ph`, or longitudinal steel is silently invented.

## Standalone Torsion certification boundary

For a **solid prestressed I-Girder above the torsion threshold**, a numerically passing transverse `phi Tn` check does **not** become a final standalone PASS. AASHTO 5.7.3.6.3-1 is a concurrent longitudinal equilibrium equation involving `Mu`, `Nu`, `Vu`, `Vs`, `Vp`, `Tu`, `Ao`, `ph`, prestressing steel and ordinary longitudinal reinforcement. Therefore:

- transverse/detailing failure → `FAIL`;
- missing closed-loop source → `LAYOUT REQUIRED`;
- below `0.25 phi Tcr` → `BELOW THRESHOLD`;
- transverse/detailing pass above threshold → `REVIEW — COMBINED CHECK REQUIRED`.

No solid-I-Girder torsion-only `Al` shortcut is used.

## UI / QA

Analysis → Torsion includes:

- decision cards for threshold, `Veff/theta`, resistance and status;
- full-span signed `Tu`, `±phiTn`, `±phiTcr`, and `±0.25phiTcr` diagram;
- `Calculation trace / Equations — governing torsion station`;
- `Variable definitions / Engineering terms`;
- detailed read-only audit table and Torsion-only limitations.

Report / QA reads the stored current-version Torsion result and displays the same engineering trace without rerunning the solver.

## Result/cache architecture

- Torsion result version: `IGIRDER.ULS6.prestressed-torsion-general-procedure`.
- Combined V+T pending version: `IGIRDER.ULS6.combined-vt-longitudinal-pending`.
- Accepted I-Girder Shear ULS5B result/version and its input hash are unchanged by torsion-only settings.
- Flexure and Girder–Deck Interface Shear caches are not invalidated by this milestone.

## Not certified in ULS6

- Full concurrent transverse sum of Article 5.7.3.6.1.
- Solid-section longitudinal resistance Eq. 5.7.3.6.3-1.
- Compatibility-torsion redistribution.
- Hollow / box-girder torsion route.
- Warping torsion.
- Anchorage, bearing/end-zone, fatigue, and shop-drawing constructability beyond the explicit closed-loop/source gates.

These remain visible limitations rather than silent assumptions.

# IGIRDER.ULS5 — AASHTO Prestressed I-Girder Shear General Procedure

This milestone starts from the accepted `IGIRDER.ULS4A` package and replaces the Precast I-Girder's fixed `β = 2.0`, `θ = 45°` bridge-shear route with the AASHTO LRFD 9th Edition Article 5.7.3.4.2 General Procedure. The implementation is intentionally scoped to standalone I-Girder Shear; Combined Shear + Torsion remains review-gated until its torsion `θ` route is made consistent with the new station-dependent shear route.

## Prestressed shear solver

- Precast I-Girder Shear now evaluates the Article 5.7.3.4.2 longitudinal strain at each design/check station and derives station-dependent `β` and `θ`.
- For sections containing at least the Article 5.7.2.5 minimum transverse reinforcement, the solver uses the General Procedure minimum-reinforcement branch.
- If provided `Av/s` is below the minimum, the alternate General Procedure branch requires traceable `sx` / aggregate-size input to obtain `sxe`. Because the current project model does not own that source, the strength route is reported as `REVIEW` and no assumed `sxe` capacity is fabricated; the overall row remains `FAIL` on the detailing deficiency.
- `Vc`, `Vs`, `Vn`, and `φVn` are evaluated from the station-specific General Procedure parameters while preserving the existing stirrup-zone ownership, minimum `Av/s`, maximum-spacing, nominal-resistance-limit, and zone-coverage gates.
- Existing critical shear sections at approximately `dv` from supports are preserved; support/end rows remain physical diagram boundaries rather than governing design sections.

## Prestress participation and end-region trace

- The General Procedure strain term uses active longitudinal rebar and prestressing steel from existing project sources.
- Pretensioned `fpo` builds linearly from zero at the actual bond commencement to the full adopted `0.70 fpu` value over the Article 5.9.4.3 transfer length basis of `60db`.
- Strand `Aps` participation is reduced proportionally when the station lies inside the conservative development screen.
- The development screen uses `fps = fpu` as an explicit conservative upper-bound because this shear route does not own a station-specific nominal-flexural `fps` solve; a larger `fps` produces a longer development screen. Debonded strands use the conservative `κ = 2.0` branch.
- `Vp = 0` remains explicit for the current straight-strand I-Girder source. A future harped/depressed-strand workflow must provide a source-owned vertical prestress component rather than silently assuming one.

## Resistance-factor safety

- Prestressed shear/torsion `φ` is no longer hard-coded to a single value for this route.
- Monolithic prestressed concrete with bonded strands/tendons uses the bonded branch.
- Presence of unbonded or debonded strands/tendons selects the lower AASHTO branch.
- The selected `φ`, branch, and code basis are carried into the result/audit trace.

## SI-unit safety

- Solver internal units remain `N`, `mm`, and `MPa`.
- AASHTO equations/constants stated in US customary units are handled through explicit conversion helpers rather than interpreted as SI values.
- Transfer/development helpers explicitly convert MPa↔ksi and mm↔in where required.

## Combined Shear + Torsion guard

Standalone I-Girder Shear now uses station-dependent `θ`, while the existing torsion/combined implementation still contains a fixed-`θ` route. IGIRDER.ULS5 therefore does **not** combine those routes into a final PASS. I-Girder Combined V+T is held at `REVIEW / NOT CERTIFIED` until the torsion `θ` provisions are calibrated consistently from the source code basis.

## Analysis / Result Summary architecture

- Check-specific Analysis pages no longer repeat the global Overall ULS cards and global compact ULS check table.
- Shear, Torsion, and Shear + Torsion each own their own decision cards, plot, audit, and limitations.
- Cross-check aggregation is owned by `Result Summary → ULS Summary`.
- Precast I-Girder ULS Summary reads current stored stage-specific results for Construction Flexure, Final Composite Flexure, Girder–Deck Interface Shear, Shear, Torsion, and Shear + Torsion without rerunning solvers.

## Selective result invalidation

- The I-Girder Shear result version is bumped for the General Procedure change.
- Dependent I-Girder Shear + Torsion results are also invalidated/review-gated.
- Accepted Construction Flexure, Final Composite Flexure, Girder–Deck Interface Shear, SLS, and prestress-loss result states are not globally cleared by this milestone.

## Scope / limitations retained

- The existing Bridge Beam/Girder effective-depth / `dv` source and manual-override ownership are retained. This milestone does not globally refactor section effective-depth ownership because that helper is shared by already accepted workflows.
- Strand transfer/development is applied explicitly to the General Procedure longitudinal-strain participation. A future dedicated end-region `dv` refinement may separately calibrate full Article 5.7.2.8 development-aware effective shear depth without disturbing accepted Flexure or Interface Shear routes.
- Exact axial-tension compression-face cracking threshold is not separately source-owned; where tensile axial force is present, the current I-Girder strain route uses the conservative doubled-strain branch and reports it in the trace.
- No Final Composite Flexure or Girder–Deck Interface Shear resistance/demand equations are changed.
- No Project JSON persistence behavior is changed.
- No analysis-result persistence experiment is introduced.

## Verification performed for this package

- `python -m py_compile` passes for `app.py` and all modified production modules.
- Focused engineering + relevant cross-workflow regression: **193 passed** in the final release-candidate run.
- The broad repository suite was attempted but is **not claimed as fully passed** within the available execution window. At least one discovered failure (`test_anchorage_rail_ugirder1_source_markers_and_docs_lock_boundary`) is reproducible unchanged on the clean IGIRDER.ULS4A baseline and is unrelated to this milestone.

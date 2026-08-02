# CROSSBEAM.ANALYSIS2 — ACI 318-19 Prestressed ULS Shear Station Checks

## Baseline

- Starting ZIP: `concrete-section-pro_CROSSBEAM-TDSTATE2-navigation-safe-temp-widget-state.zip`
- Starting SHA-256: `8cda3d37f10a25d89d3b01c48e8259907bbc1d81fc2f94a6fc1f3a0bc3ed37f6`

## Scope

Add an on-demand Crossbeam **Shear** check beside the accepted Crossbeam
Flexure check in `Analysis → ULS Strength`. The ULS selector follows the same
lazy-calculation pattern used by the accepted Bridge/Beam workflow; only the
selected check runs when its Calculate button is pressed.

This milestone intentionally exposes only:

```text
Flexure | Shear
```

Torsion and Shear + Torsion will be added only after their own production
milestones are implemented and reviewed. No empty or misleading tabs are
created.

## Engineering route

- Consume active canonical Crossbeam `ULS Final Stage` station rows.
- Preserve row coupling: `P`, `V2`, `T`, and `M3` always come from the same
  imported FEA output row/state.
- Map `V2 → Vu`; use `|Vu|` for the resistance check while retaining the signed
  V2 source for plots and audit.
- Rebuild the active Section ID, concrete material, longitudinal reinforcement,
  transverse template, tendon positions, and Effective Prestress source at
  every check station.
- Use imported external-FEA resultants once. Prestress force or secondary
  prestress is not added to demand again.

The production sectional route is based on:

- ACI 318-19 22.5.6.2 approximate `Vc` for prestressed flexural members,
  including `Aps fse ≥ 0.4(Aps fpu + As fy)`.
- ACI 318-19 22.5.2.1 for `d`, with `d ≥ 0.8h`; `dp` remains the actual
  prestressing-steel depth for Table 22.5.6.2(a).
- ACI 318-19 22.5.8.5.3 for provided `Vs = Av fyt d / s`.
- ACI 318-19 22.5.1.2 for the section/diagonal-compression limit.
- ACI 318-19 9.6.3.2 and Table 9.6.3.4 for required minimum web reinforcement.
- ACI 318-19 Table 9.7.6.2.2 for maximum leg spacing along the member and
  across the member width.
- ACI 318-19 Table 20.2.2.4(a), limiting shear-design `fyt` to 420 MPa.
- ACI 318-19 Table 21.2.1, using `phi = 0.75` for shear.

For generated Crossbeam polygons, `bw` is the conservative minimum positive
**total material width** sampled through the central 25–75 percent of the
section depth. For a hollow section this represents the sum of the active web
widths rather than the gross overall width.

## Conservative scope gates

- Exact Precast physical segment joints are retained in the result table as
  `REVIEW`; sectional beam shear does not certify interface/joint shear
  transfer, keys, shear friction, local reinforcement, or D-region behavior.
- Stations inside an applied Column/Support footprint are retained as
  `REVIEW`; the sectional route does not certify the support D-region.
- The ACI 22.5.6.2 route is not released as PASS when the prestress-dominance
  applicability ratio is below 0.400. The app reports `REVIEW` instead of
  inventing refined `Vci/Vcw` inputs that are not available from the current
  compact Loads contract.
- Imported axial tension downgrades an otherwise passing row to `REVIEW` under
  ACI 22.5.1.8.
- Engineer-selected FEA stations remain authoritative. ACI 9.4.3 support-face
  and critical-section conditions, fully transferred effective prestress,
  post-tensioning anchorage/end zones, hanger reinforcement, development,
  fatigue, seismic detailing, and local D-regions remain separate checks.
- A row that requires shear reinforcement but has no accepted sectional `Av/s`
  credit is `FAIL`, not a silent REVIEW or assumed minimum layout.

## Commercial UI and state behavior

- Reuse the accepted Bridge/Beam ULS selector, primary-action pattern, status
  cards, compact tables, wide static Plotly chart helper, legend semantics,
  governing marker, captions, warning colors, and QA expanders.
- Add no independent theme, ad-hoc chart layout, or new visual language.
- Show signed V2 demand and eligible sectional `phiVn` capacity; amber markers
  identify physical-joint and support D-region scope guards.
- Cache Shear separately under Crossbeam-namespaced keys and invalidate it with
  a deterministic source fingerprint.
- Do not run Shear on page navigation, tab changes, Result Summary, or
  Report/QA.

## Preserved behavior

- Existing Crossbeam ULS Flexure equations and result cache are unchanged.
- Existing Crossbeam Transfer/Final-Service SLS equations are unchanged.
- Prestress Loss, Effective Prestress, Loads, Project JSON, navigation, and
  external-FEA contracts are unchanged.
- Bridge/Beam, Building Beam/Girder, and Column/Pier/Wall/Pylon solvers are
  unchanged.
- No Torsion, combined V+T, Cracked Class C, sustained-load SLS, Deflection /
  Camber, Result Summary, or Report/QA production route is added here.

## QA completed

- `python -m compileall -q app.py concrete_pmm_pro tests` — passed.
- ANALYSIS2 and adjacent ULS/navigation target set — **102 passed**.
- Shared Analysis/navigation regression — **126 passed**.
- Bridge/Beam and Railway U-Girder ULS regression — **90 passed**.
- Shared ULS chart/cache/dashboard group — **24 passed, 1 baseline-existing failure**; the same failure reproduces on the untouched TDSTATE2 baseline.
- Complete Crossbeam suite — **536 passed, 7 baseline-existing failures**; all seven failures reproduce on the untouched TDSTATE2 baseline and are outside ANALYSIS2 scope.
- Full repository suite was attempted but did not complete within the available 15-minute execution window; it reached approximately 44 percent and showed only the already identified baseline failures before timeout.
- A standalone Plotly figure build completed using the same accepted Beam/Bridge shear chart helper. A live Streamlit browser review was not available in this runtime because Streamlit is not installed in the execution environment.

## Repo summary

Add ACI 318-19 prestressed Crossbeam ULS shear station checks with row-coupled FEA demand, provided transverse-reinforcement gates, physical-joint/support scope guards, deterministic caching, and Bridge/Beam-standard UI.

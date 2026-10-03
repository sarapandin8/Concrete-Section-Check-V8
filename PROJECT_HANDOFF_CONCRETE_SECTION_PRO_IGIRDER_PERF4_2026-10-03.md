# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.PERF4

Date: 2026-10-03 (Asia/Bangkok)

## Baseline and scope

Continue the latest delivered `concrete-section-pro_IGIRDER-DBQA1-PERF3-debond-audit-flexure.zip`, SHA256 `8e095d6b6a3553307ce39a5c4d003b4f91db9d573a85daf8104da4af3bce15f5`. This continues ULS7 and the originally supplied ULS6F project, handoff and source standards. Preserve every baseline file.

User reported Flexure still slow and asked whether Nu can be omitted. Milestone **IGIRDER.PERF4** improves computation with numerically equivalent reuse. It does not revise the engineering result versions: DBQA1, ULS7 combined V+T, ULS6E torsion, ULS5A shear, ULS2P Construction and ULS3A Final Composite remain.

Source fixture: `I_Girder_20m.json`, 44,911 bytes, SHA256 `c27a27278fef69b5347e7216f5b3c9324f723a9a0ca2d5b52a8956c1fe765799`. Original JSON and packaged QA fixture are unchanged. No strand/layout edits or load edits were made.

## Why it was slow

PERF3 correctly reused five physical PMM clouds for the 21 station rows. Its underlying sweep still repeated the concrete/ordinary-rebar calculation for every strand state. A CPU profile of the actual fixture found **1,468,800** scalar compression-block membership checks, each creating a Shapely Point and testing polygon validity, and **63** PMM slice queries that repeatedly grouped/sorted the same clouds. Nominal PMM point copies and engineering-unit DataFrames were also rebuilt at every station.

Nu does not enter the neutral-axis sweep. It selects the demand slice of an already-generated cloud. Setting every Nu to zero still needs the same five physical prestress clouds in this fixture; only demand-state/query reuse improves further. The profile is instrumented and is not used as the headline wall-time benchmark.

## Implementation

| File | Final change |
|---|---|
| `analysis/pmm_section_cache.py` (new) | One bounded, exact-key concrete/rebar base sweep per Calculate; batch inside/on-boundary geometry predicate; publish completed sweeps only. |
| `analysis/pmm_solver.py` | Optional calculation-local base cache; compute resolved bar materials once; preserve force accumulation order, strain equations, steel laws, displacement subtraction, phi, caps and metadata. |
| `analysis/pmm_prepared.py` (new) | Prepare reduced/nominal clouds and their display/slice data once per physical state. |
| `analysis/capacity_check.py` | Optional prepared context guarded by PMM-result identity; original demand/envelope/fallback logic retained. |
| `visualization/pmm_dashboard.py` | Prepare the existing sort/radius tie-break once; same bracketing/interpolation, duplicate handling and fallback; retain only the last queried slice in each prepared object. |
| `ui/analysis_page.py` | Enable caches only for Bridge + parametric I-Girder + full-span Flexure; fresh caches for each Calculate; expose elapsed time and base sweep counts in the existing analysis notes. |
| `tests/test_igird_perf4.py` (new) | Numerical equivalence, invalidation, failure recovery, boundary/hole predicate, independent prestress/phi/Nu states, prepared-demand metadata and exact duplicate slices. |

Base key uses exact polygon WKB, code basis, fc/ecu/alpha1/beta1, resolution, displaced-concrete option, and ordered bar coordinates/areas/resolved fy/Es. Prestress and phi are recomputed separately. Geometry, steel, material fallback, force/development state and Nu remain governed by the accepted physical-cloud/capacity-state keys. No cache is saved in JSON/session results or used by Summary/Report to trigger solves.

The valid-polygon batch predicate uses `intersects_xy`, which includes boundary points like the existing `covers(Point)` test. Invalid/empty polygons retain the conservative result; geometry exceptions retain the scalar fallback. Tests cover boundaries, holes and invalid geometry.

Protected production items remain byte-identical to PERF3: `prestress_stress.py`, `strain_compatibility.py`, `slice_envelope.py`, code-check constants/rules, composite section preparation, combined V+T modules, Debonding QA/UI, JSON import/export/schema, `app.py`, dependencies and existing tests.

## Measured outcome

Same source fixture, same local environment and 72 angles × 120 depths, 21 Final Composite stations:

| Measurement | PERF3 | PERF4 |
|---|---:|---:|
| Full-span calculation wall time | 45.832 s | 5.416 s |
| Physical PMM clouds | 5 | 5 |
| PMM sweep wall time summed | 31.613 s | 1.777 s |
| Concrete/rebar base sweeps | 5 | 1 built + 4 reused |
| Neutral-axis points per physical cloud | 8,640 | 8,640 |
| Station result rows | 21 | 21 |

Speedup **8.46×**; wall-time reduction **88.18%**. These are one cold calculation per version in the same runtime, not medians or a deployed performance guarantee. Production-renderer browser Calculate button: **6.405 s**, with no JavaScript page error or Streamlit exception. Generic startup `app.py` passed.

All columns in the station result table are exactly equal to PERF3, including Mn, phiMn, D/C, status, c, theta, source/basis and warnings. Independent solver comparison loaded the old solver file directly from the extracted baseline ZIP: **86,400 points** (five Final Composite + five Construction states), every field/warning/info exactly equal. Slice differential against PERF3: 80 cases, exact DataFrame and attrs equality; prepared route checked on default-Pu cases. New targeted tests: 54 passed. Selected regression: **506 tests across 47 modules passed**, zero failures/errors/skips. Full repository suite was not run. Exact fresh-extract release validation is recorded in the companion release manifest.

## Nu: when zero is legitimate

Attached AASHTO LRFD 9th Edition Section 5, Articles **5.6.2.1** and **5.6.3.2.5**, require equilibrium and strain compatibility for strength. At nominal equilibrium, concrete compression plus signed ordinary/prestressing-steel forces must balance the applied axial force. When external Nu is zero, the internal forces still have to balance; the prestressing steel is still included through its effective initial strain plus the section strain change.

Use Nu = 0 only after the structural-analysis source establishes zero external axial demand for the relevant station/case. A simply supported arrangement alone does not establish this for every real bridge model: restraint, temperature, bearing/braking loads and system action depend on the model/load combination. Confirm the imported axial sign convention and whether the FEA force output includes prestress effects before deciding how it maps to the current internal-prestress representation. The supplied JSON does not establish that provenance; it contains Nu from **−1.492 to +575.159 kN**, under the app's compression-positive convention.

A diagnostic copy with Nu = 0 (never saved to the project or used in production): **4.191 s**, versus 5.416 s with original Nu. Original and zero-Nu cases both built five PMM clouds. Removing Nu changed nominal Mn by up to **4.091%**:

| Station | Original Nu (kN) | Mn with Nu (kN-m) | Mn at Nu = 0 (kN-m) | Change |
|---|---:|---:|---:|---:|
| 0 m | +575.159 | 6,978.836 | 6,693.336 | −4.091% |
| 10 m | +25.940 | 10,354.173 | 10,342.805 | −0.110% |
| 20 m | −1.492 | 6,692.596 | 6,693.336 | +0.011% |

The sign of the capacity change is not uniform even in this fixture. This diagnostic is not a basis for a general Nu-neglect rule. A future specialized one-axis solver could reduce work further, but would require separate root/bracket and governing-branch validation; it is not introduced here.

Primary references: supplied `SECTION 5 CONCRETE STRUCTURES.pdf` (AASHTO 9th, pp. 5-33–34 and 5-41–42); [FHWA Post-Tensioned Box Girder Design Manual, §7.3.2.1](https://www.fhwa.dot.gov/bridge/concrete/hif15016.pdf) for internal prestress equilibrium and strain decomposition; [FHWA PSC design example, Step 5.5](https://www.fhwa.dot.gov/bridge/lrfd/pscus055.cfm) for strand stress at flexural strength. These references establish mechanics; edition-specific acceptance remains based on the attached AASHTO source.

## Remaining engineering gates

Existing Debonding detailing **FAIL** and development/service review remain. `Be_strength_verified = false` and girder/deck Interface Shear remain independent acceptance gates. Current Final Composite route is positive primary-Mux flexure; it does not certify a biaxial check of the imported Muy. `ENV_ULS` concurrency is not established by this JSON. Performance and section-strength PASS do not close these gates. No scope/certification claim is broadened by this milestone.

## Delivery and run

Full clean ZIP: `concrete-section-pro_IGIRDER-PERF4-equivalent-fast-flexure.zip`. SHA256/size/entries/integrity and exact fresh-extract test evidence are in the companion `RELEASE_MANIFEST_IGIRDER_PERF4_2026-10-03.json`.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Start from a new extracted directory, launch its `app.py`, then load the unchanged JSON. Analysis → ULS → Flexure → Final — Composite → Calculate Final Composite Flexure. The analysis notes identify **IGIRDER.PERF4**. If the running app still shows PERF3, check that its process points to the newly extracted folder and restart it.

Evidence: `qa/evidence/igird_perf4/`; actual input UI: `qa/igird_dbqa_perf_runtime.py`. QA Nu = 0 output is explicitly named diagnostic and is not fed to production Result Summary/Report.

Repo summary: Accelerate I-girder full-span flexure with equivalent concrete/rebar sweep and PMM query reuse while retaining every station's Nu and all neutral-axis points.

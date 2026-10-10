# Concrete Section Pro — IGIRDER.TORSIONAUDIT12

Date: 2026-10-10. Based on the complete original IGIRDER.MAXMIN10 archive.
No push or deployment. The attached AASHTO source is Ninth Edition, 2020.

## Behavior

General Procedure torsion/combined strain now uses actual |Vu−Vp|dv in the
Mu minimum; Veff still replaces the shear term in Eq. 5.7.3.4.2-4. The old
double use of Veff adopted a greater strain, which p. 5-72 permits as a
conservative choice, but gave materially smaller phiTn than direct substitution
for low-Mu/high-Tu cases. This is a direct-method change, not a claim that every
previous conservative result violated the code.

Combined actual-shear compression D/C uses |Vu|/[phi(0.25fc bv dv+Vp)] under
Eq. 5.7.3.3-2. The former Veff compression screen remains a separate REVIEW
item above 1.0, excluded from code-component D/C. It cannot authorize PASS.
True shear/transverse/longitudinal/detailing failures retain FAIL priority.

The new Calculation trace and stored results expose actual Mu floor/adopted Mu
and distinguish the actual shear limit from the additional Veff screen.
Torsion and combined result versions invalidate old session caches.

Composite force lever-arm/strain geometry, girder web properties and girder
torsion cage geometry are retained. There is no deck-area inflation of Ao,
Beam-only source routing, ACI 0.85Aoh factor, or change to shear-only/flexure.
The existing source, concurrent-action, development, interface, support,
negative-composite and detailing gates remain. A lower theta can increase
longitudinal force even while phiTn increases.

## Changed application files

- `concrete_pmm_pro/ui/analysis_page.py`: actual Vu moment floor, trace fields,
  stored torsion columns, torsion result version.
- `concrete_pmm_pro/analysis/igird_combined_vt.py`: actual shear D/C and separate
  additional Veff review ratio; combined result version.
- `concrete_pmm_pro/ui/igird_combined_vt.py`: partial/full results, status gates,
  calculation trace and review warning.

Tests update one version expectation and increase the insufficient-transverse
fixture's Tu to retain a physically insufficient example under direct strain.
New tests/QA evidence accompany the patch. All original non-cache files outside
these three modules and two existing tests are byte-identical before adding
new release documentation and evidence. requirements.txt is unchanged.

## Validation and limits

- 62-module scoped regression: 821 passed; not the entire repository suite.
- 8 hypothetical haunched-I midspan cases: 80 independent scalar comparisons,
  maximum relative error 5.28e-14. Polygon/inset geometry is analytic; capacity
  equations are independently substituted in US units. Developed dv and
  nominal fps are held as source trace inputs.
- Actual app.py AppTest: 8 calculate calls, two girders/two LCs/four checks,
  36 paired Max/Min PNGs at 2880x1120, zero exceptions, review solver calls 0,
  input/cache/design-member snapshots unchanged and stale results hidden.
- Two isolated midspan UI cases distinguish REVIEW from real FAIL. Their full
  member results retain additional critical shear-section failures.
- Runtime used for verification: Python 3.12.14, Streamlit 1.61.0,
  pandas 2.2.3, NumPy 2.3.5, Plotly 5.24.1, Kaleido 0.2.1.

Evidence: `qa/evidence/igird_torsion_audit12/`. Hypothetical QA geometry/actions
are not the user's bridge model or an approval of whole-member/system design.
Existing extra conservatism in tensile-Nu strain, Veff spacing stress, transfer,
development, residual steel allocation and threshold policies remains.

After loading this source tree, calculate Torsion and Shear + Torsion again.
Review all source rows/critical stations, extra review screens and physical
cage/interface evidence; a midspan PASS does not establish whole-member PASS.
For the user's exact comparison, obtain their I-girder Project JSON and the
affected same-source load case/station results.

## Reproduction

Run scoped tests listed in `qa/evidence/igird_torsion_audit12/regression_modules.txt`.
Run `python qa/igird_torsion_audit12.py --label corrected` for current benchmarks.
The `baseline` evidence was generated from unmodified MAXMIN10 before patching;
do not regenerate it with the corrected tree and call that MAXMIN10.
`qa/igird_torsion_audit12_app_verify.py` and
`qa/igird_torsion_audit12_guard_verify.py` reproduce app/export and isolated
station review checks, respectively. Local runtime overlays are not shipped.

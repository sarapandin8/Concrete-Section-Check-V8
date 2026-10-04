# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.CHART2

Date: 2026-10-04. AASHTO LRFD 9th Edition (2020). Continue the project app-style skill. Scope: V/T charts and feedback for completed calculations with incomplete engineering sources.

## Accepted baseline

Continue the full delivered `concrete-section-pro_IGIRDER-CHART1-interface-envelope-legend-cleanup.zip`, SHA-256 `742abd38c546e8d3dc6455c7535a3586974c59f8711776e678165cfb4a9e74b3`. Preserve every one of its 1,104 entries and all accepted ULS6F → ULS7 → DBQA/PERF → FLEXDEP1 → FLEXSIGN1 → CSIIMPORT1/2 → CHART1 changes.

The user will enter P=0 directly in Excel. No automatic P override or axial-demand mode is authorized. Original six imported component values/signs remain intact; the V/T calculations retain their established primary-action and source-coupling rules. No user workbook or project JSON is edited.

## User report and evidence

`image(2).png` shows repeated/overlapping Shear legends. `image(3).png` shows four identically truncated Torsion demand legends, a missing φTn source and **0/63** torsion-qualified stations. `image(4).png` already says **Calculated for current inputs**, followed by **DATA REQUIRED**, no finite D/C and warnings about incomplete sources. The primary button fires; the engineering sources prevent the D/C plot. This release must not make a numeric curve by assuming cage qualifications or steel material properties.

The unchanged 80-row latest native CSI fixture plus accepted deck250 project reproduces the failure in full `app.py`: Shear 88 rows, Torsion 80 rows, Combined 88 rows; Combined has 71 DATA REQUIRED and 17 REVIEW, with no finite overall D/C. All five transverse zones are unselected for torsion. Early-return rows also identify **Longitudinal material SD40 is unresolved**. The uploaded screenshots show 92 Combined review rows, so these QA row counts are not claimed to reproduce every current input of the user's local model.

## Display changes

- Demand legends keep the distinguishing bound and occurrence: **Vuy Max 1/2, Vuy Min 1/2; Tu Max 1/2, Tu Min 1/2**. Max is solid and Min dotted; occurrence 2 uses a diamond marker. Full case names remain on hover and in the audit. Different envelope/member collisions receive distinct compact case identifiers.
- Shear shows **±φVn**, **φVc**, **Critical x** and **Gov. shear** once in the legend. Positive/negative resistance coordinates remain unchanged. The governing demand stays annotated rather than adding a duplicate legend item.
- Only exact, finite copies of a resistance/reference path are drawn once. Different case-dependent capacities, disjoint paths and all missing-source gaps remain. Shear β/θ depend on the original case inputs, so legitimately different capacity paths must not be collapsed into an invented single strength. Full source resistance/threshold case names are included in hover.
- Native Torsion cracking/investigation references no longer repeat coincident paths. The first available φTn source gets a visible legend even if the first case has no torsion capacity. No missing φTn is fabricated.
- Combined V+T shows one compact legend per utilization quantity, while different original case paths and gaps remain. Full case identity is carried in hover. Scalar utilization and original row-based D/C are unchanged.
- Precast I-Girder Shear, Torsion and Combined use the established browser Plotly renderer with hover; no server-side Kaleido rasterization runs in these Analysis routes. Other member workflows retain their existing rendering path. Full physical 0–20 m domains remain visible.

## Calculation feedback and required sources

The primary Calculate control shows progress while running. The Combined workspace explicitly reports completed row count and finite-D/C row count. A read-only **Required inputs / blocking sources** table lists the stored reason, affected rows/positions, input page and action. Each row's `Review reason` is also in the compact table.

For native CSI sources, M2/V3 reference-action advisories are excluded from the list of missing primary inputs. Their original notes and values remain unchanged in the compact/detailed audit.

When no finite D/C exists, the message says the calculation completed and tells the engineer to finish those inputs and recalculate. The absence of a curve no longer looks like an unresponsive button. Existing DATA REQUIRED/REVIEW/FAIL gates are retained.

For this fixture, complete the actual input sources through:

1. **Sections → Rebar → Transverse Rebar**: verify each actual cage zone, then confirm **Use for Torsion**, **Closed Loop** and **135° Hook** where applicable. Check physical zone coverage. Automatic ph remains geometry-derived. Do not tick confirmations merely to remove a warning.
2. **Materials / Sections → Rebar → Longitudinal Rebar**: define the material referenced by the actual bars (SD40 here), or map bars to the correct existing defined material with verified fy.
3. **Longitudinal development — Shear + Torsion** and transverse detailing confirmations: verify continuity, end anchorage/ld, corner reinforcement and longitudinal perimeter distribution. Remaining warnings and actual strength failures still require engineering resolution.

CSI Max/Min bounds are not proven concurrent FEA action vectors. The existing numerical-screening/source-coupling guard remains; no new final PASS is issued merely by completing the cage inputs.

## Verification

`tests/test_igird_vt_chart_display.py` checks native signed coordinate fidelity, distinct short labels/full source identity, both capacity signs, exact copies versus different paths, missing gaps, first available torsion capacity visibility, repeated-source row counts and actionable material/zone mapping without data mutation.

`qa/igird_vt_chart_ui_verify.py` runs full `app.py` and clicks all three actual Calculate controls. It rejects any I-Girder server-side rasterization, checks unique legends and unchanged native force coordinates, validates the incomplete-source message/actions and proves ordinary review does not solve again. With the QA comparison option, **every original numeric, status and note cell equals the pre-change baseline dataframe**, for all 88/80/88 check rows.

A separate QA app instance explicitly supplies hypothetical confirmed cage flags and the missing verified QA SD40 material; **84** rows then have finite overall D/C and the production Combined chart is rendered. Those hypothetical inputs are not applied to the user's model or saved as production project inputs. Native envelope coupled acceptance still cannot PASS. The fixture retains unresolved end/development/source gates; this test is proof of UI operation, not acceptance of the user's girder.

AST comparison confirms only five existing UI/figure definitions in `analysis_page.py`, the stored-result `render_workspace` and presentation helpers change. All engineering producer functions and all 188 other existing production Python files remain identical to CHART1. No equations, numerical gates, force import, Project JSON schema or result-cache persistence changes are made.

Fresh extraction verification passed **608 selected tests across 50 modules** in 55.56 seconds with no failures, errors or skips. Python compilation and full-app startup passed. Full-app native import (480 exact force-component comparisons), prior Flexure/Interface and new V/T Calculate/review controls all passed. The final ZIP's Python fingerprint must equal this tested extraction.

Fresh extraction validation details are recorded under `qa/evidence/igird_chart2/` and in the release manifest. PNGs are Matplotlib previews using exact production Plotly coordinates; embedded-JS HTML provides the actual interactive figure specifications. These are not browser screenshots; native browser/print-layout verification is not claimed.

## Run

```bash
streamlit run app.py
python -m pytest -q tests/test_igird_vt_chart_display.py tests/test_igird_chart_display.py
python qa/igird_vt_chart_ui_verify.py
```

Repo summary: Clarify native CSI shear/torsion chart legends and report actionable missing sources after combined V+T calculations.

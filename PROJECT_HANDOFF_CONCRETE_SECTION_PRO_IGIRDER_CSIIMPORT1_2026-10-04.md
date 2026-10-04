# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.CSIIMPORT1

Date: 2026-10-04. Code: AASHTO LRFD Bridge Design Specifications, 9th Edition (2020).

## Baseline and task

Continue the complete accepted `concrete-section-pro_IGIRDER-FLEXSIGN1-csi-axial-convention.zip`, SHA-256 `2b41d454aead8a92f3f7f2efa8e9bf22dbf5ad0fe63eb7c4ed4250f410fb669f`. Preserve every baseline file and all ULS6F → ULS7 → DBQA/PERF → FLEXDEP1 → FLEXSIGN1 history. This milestone changes the Precast I-Girder Loads import and its source/coverage gates. It does not change AASHTO resistance equations, steel or concrete models, development/anchorage assumptions, strand layout, or the physical cut ends at x=0 and 20 m. Continue the project app-style skill in `docs/CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md`.

The user requested the Excel template to match native CSiBridge forces and include both Max and Min. The user requested the critical girder and suggested Left Exterior. Authoritative input: `Bridge_ULS_Left_Exterior_Max_Min_Template CSiBridge.xlsx`, retained byte-for-byte as `qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx`. The first sheet is a whole-bridge section and must not be imported automatically into an individual I-Girder check.

## Native input and mapping

Header row 1: `Layout Line Distance, Girder Distance, ItemType, P, V2, V3, T, M2, M3`. Row 2 declares m / kN / kN-m. Force and moment signs remain unchanged. Girder Distance supplies x; Layout Line Distance remains source metadata.

| CSiBridge | App field | Canonical import unit |
|---|---|---|
| Girder Distance | Station x (m) | m |
| M3 | Mux | kN-m |
| V2 | Vuy | kN |
| T | Tu | kN-m |
| M2 | Muy | kN-m |
| V3 | Vux | kN |
| P | Nu, raw CSI P | kN |

The workbook contains 19 worksheets: bridge-total, six girder, six beam-only and six slab-only outputs. Each girder contains 80 rows: 40 Max, 40 Min, 21 distinct x coordinates. Interior stations have two occurrences of each bound. These rows are retained in source order and assigned stable source paths such as `ENV_ULS / Left Exterior Girder / Max / set 1`. Set 1/2 means occurrence order at a source station; it is not a load combination, support face or Before/After label. No component envelope vector is assembled from different rows. The supplied workbook has no OutputCase column; the importer asks for the actual FEA combination/envelope name.

## Critical-member selection

Comparison includes both bounds and every source row, restricted to individual Girder worksheets.

| Girder | Max abs M3 (kN-m) | Max abs V2 (kN) | Max abs T (kN-m) |
|---|---:|---:|---:|
| Left Exterior Girder | 7184.6936 | 1409.165 | 223.0256 |
| Right Exterior Girder | 7184.6901 | 1409.165 | 223.0259 |
| Interior Girder 1 | 5929.5237 | 1473.640 | 122.8176 |
| Interior Girder 2 | 6410.5607 | 1153.968 | 359.5989 |
| Interior Girder 3 | 6410.5609 | 1153.968 | 359.5986 |
| Interior Girder 4 | 5929.5224 | 1473.643 | 122.8173 |

Default: **Left Exterior Girder**, largest |M3| at x=10 m; Right Exterior is practically tied. Vertical shear demand is largest for Interior Girder 4; torsion is largest for Interior Girder 2. This is demand ranking, not a member-capacity or coupled-D/C comparison. Do not assert one girder controls all checks. The engineer can select another girder explicitly. Whole-bridge, beam-only and slab-only selections cannot be applied as a girder demand in this UI.

## Source concurrence and analysis coverage

Max/Min labels alone do not demonstrate that P, V2, V3, T, M2 and M3 occur simultaneously. [CSI CSiBridge Bridge Response documentation](https://docs.csiamerica.com/help-files/csibridge/Analysis_tab/Bridge_Panel.htm) explains that Correspondence returns the other actions at the loading condition controlling a selected maximum/minimum response. [CSI enveloping-combination guidance](https://web.wiki.csiamerica.com/wiki/pages/viewpage.action?pageId=1481148) explains why independently enveloped actions can represent different load combinations. The current worksheet supplies no correspondence driver / governing case identity. Concurrence is therefore unverified for this input; this is an inference from the actual supplied fields, not a claim that every CSI Max/Min output lacks correspondence.

Keep the numerical results for review. Imported coupled checks receive explicit `Source coupling = ENVELOPE — REVIEW`; numerical PASS cannot certify Flexure with Nu, General Shear, Torsion or Combined V+T. Numerical FAIL is retained as screening evidence, not proof that the unidentified simultaneous load vector occurs. PASS components feeding the overall strength status also become REVIEW; their original numerical status is stored separately. No checkbox certifies these source rows. Use corresponding FEA action sets for final coupled design acceptance.

The previous Final Composite UI selected only positive/zero Mux, which would omit one negative bound in the new Left Exterior sheet. Native CSI import now screens every finite bound, including that negative row; all 80 rows and four source paths are stored. Negative composite acceptance, deck tension reinforcement/continuity, biaxial M2/Muy resistance, composite action, end/D-region transfer and existing detailing gates remain separate. Legacy imports retain their established positive-composite scope. Dashboard/cache selection uses the same native source-row coverage as Calculate, so the new result is current rather than stale. Summary and trace display stored results only.

## Implementation

- `io/girder_csi_import.py`: table discovery, units normalization, exact row/axis mapping, member ranking, source metadata, append validation and concurrence gates.
- `ui/girder_csi_import.py`: selected worksheet, critical-demand comparison, native template download, source/mapped previews and apply. CSV requires an individual girder distance and member name.
- `ui/loads_page.py`: native import is the default for Precast I-Girder; legacy app-column mode remains reachable. Other presets keep their existing import.
- `ui/analysis_page.py`: source-gated Flexure/Shear/Torsion, all native Final bounds, matching dashboard/hash coverage and visible source warning. Input hash includes the source-contract version.
- `ui/igird_combined_vt.py`: source-gated actual ULS7 results, including supplemental rows matched to their source path.
- `ui/igird_flexure_development.py`: stored source sheet, Excel row, ItemType, row set and concurrence fields in trace.
- `assets/templates/Bridge_Beam_ULS_CSiBridge_Template.xlsx`: native 9-column header, units row, Max/Min example stations and blank force input cells. Created and visually inspected with Artifact Tool; no authoring dependency is added to app runtime.
- `tests/test_igird_csi_import.py`, `qa/igird_csi_import_runtime.py`, `qa/igird_csi_import_ui_verify.py`: fidelity, engineering-consumer and production Streamlit UI checks.

The existing 10-column Loads schema is preserved. Machine-readable source identity is stored in Note with the `CSP_CSI_SOURCE=` prefix and survives project JSON save/load. Do not remove this metadata or rename source paths when reviewing the native import. Applying native CSI declares the existing FLEXSIGN1 tension-positive input convention; import itself never negates Nu. Append rejects existing nonzero axial data with a different/undeclared convention and rejects repeated Case/station paths. Replace remains reversible. Unknown units, nonfinite/missing force values and duplicate headers block apply; missing values are never interpreted as zero. Native imports store kN/kN-m and require matching Loads unit controls.

## Validation and limitations

See `qa/evidence/igird_csiimport1/` for source-row screening results, template render, production UI verification and fresh-extraction regression. The UI check exercises critical worksheet default, whole-bridge rejection, Replace, duplicate Append rejection, legacy mode, actual Final Calculate, stored trace and current-result dashboard. Upload bytes are provided through a controlled fixture to the production Streamlit widgets. Browser visual verification is **not completed**: retained local Chrome binaries were truncated and fail before opening; a fresh download timed out. Do not present earlier FLEXSIGN1 browser screenshots as new CSIIMPORT1 evidence.

The clean extraction passed **501 tests across 45 selected modules**, with zero failures/errors/skips, compileall and complete `app.py` startup. Production UI actions passed with zero Streamlit exceptions, all 80 Final rows calculated, one negative row screened, and a current-result dashboard. Numerical screening counts are 78 REVIEW and 2 FAIL under the unchanged 250 mm-deck fixture. These are envelope-source screening counts, not a certified simultaneous-action design result. Final Python files must match that tested extraction. The release manifest records the exact scope and final checksum. Do not describe this selected regression scope as the entire repository suite. All original baseline files and accepted fixtures remain in the ZIP; caches, environments, node modules and new runtime logs are excluded.

Run:

```bash
streamlit run app.py
python -m pytest -q tests/test_igird_csi_import.py tests/test_loads.py
python qa/igird_csi_import_ui_verify.py
```

Repo summary: Add native CSiBridge girder imports with critical-flexure selection, exact Max/Min row preservation, unit-aware force mapping and explicit source-concurrency review gates.

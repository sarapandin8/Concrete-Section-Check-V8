# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.CSIIMPORT2

Date: 2026-10-04. Continue AASHTO LRFD Bridge Design Specifications, 9th Edition (2020), and the project app-style skill. This handoff supersedes CSIIMPORT1's two-format import instructions.

## Authorized task and accepted baseline

Fix the user's report that the latest Excel cannot be imported without manual edits. Read all six source force components; the user explicitly confirms **V3 and M2 are reference only**. P, V2, T and M3 feed the existing relevant checks. Preserve CSI signs, both Max and Min, repeated source stations, development/sign conventions and the complete accepted application.

Baseline: `concrete-section-pro_IGIRDER-CSIIMPORT1-native-csi-max-min.zip`, SHA-256 `ce21bc1cbb78d06c81bed084eb74981698a0cfbc4da4563022c4b000b5bd5a2b`. Preserve all 1,076 baseline archive entries and the previous ULS6F → ULS7 → DBQA/PERF → FLEXDEP1 → FLEXSIGN1 → CSIIMPORT1 lineage. Do not change strand development, resistance equations, phi, axial sign conversion, physical x=0/20 cut ends, deck geometry or engineering acceptance gates.

## Reproduced incompatibility and correction

The former **App columns (legacy)** branch sends this native workbook to a parser expecting Case Name and Station x (m). The supplied workbook uses ItemType and Girder Distance and contains a units row. That branch produces 81 validation errors, starting with a blank Case Name. Native CSI import worked in prior narrow tests, but that did not establish that both entry paths accepted the user's file. We have reproduced this failure path; we do not know which radio choice or deployment the user had running.

The Precast I-Girder ULS panel now has **one upload control**, `Upload Bridge Beam/Girder ULS station-load import`. It discovers native CSI or existing app-column headers automatically. The format radio is removed, and its old persisted state cannot route a native file to the wrong parser. Existing app tables and aliases remain available through the same uploader. Other section presets retain their existing import UI.

Native input is validated before Replace/Append. Missing or nonfinite values in any component, unsupported units and a wrong member scope prevent applying the import. No missing reference value is silently replaced with zero. Append checks numeric station values across native numbers and legacy text and rejects duplicate case/station paths. Native apply declares CSI tension-positive P; legacy apply preserves its current declared Nu convention.

## Exact latest source and fields

Authoritative latest attachment: `Bridge_ULS_Left_Exterior_Max_Min_Template CSiBridge(1).xlsx`, 15,457 bytes. SHA-256: `ec775724f4c909a0a88dbaf98200dc741b62b9311db1f3aa2499a5621ac5d7ef`. Its bytes are preserved as `qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx`; no corrected replacement workbook is required.

One sheet: **Left Exterior Girder**. Header row: Layout Line Distance, Girder Distance, ItemType, P, V2, V3, T, M2, M3. The second row declares m / kN / kN-m. Retain all 80 data rows: 40 Max and 40 Min, 21 distinct positions from x=0 to 20 m, and both repeated occurrences of each bound at internal stations. Do not infer Before/After labels or combine forces from different rows.

| Source | App field | Unit | Role |
|---|---|---|---|
| Girder Distance | Station x (m) | m | Analysis position |
| P | Nu (raw P) | kN | Existing axial action |
| V2 | Vuy | kN | Existing vertical shear |
| T | Tu | kN-m | Existing torsion |
| M3 | Mux | kN-m | Existing primary-axis flexure |
| M2 | Muy | kN-m | Reference only |
| V3 | Vux | kN | Reference only |

The Analysis input contract retains all six values. Original source forces are also stored with calculated rows as Source Mux, Vuy, Tu, Muy, Vux and Nu with units, plus source Excel row, worksheet, ItemType and occurrence. The Flexure trace labels M2/V3 as reference and displays those stored quantities without another solver run. The developed flexure solver continues its existing primary-axis Mux with Nu route; this milestone does not add biaxial or transverse-axis resistance checks.

A single-sheet workbook cannot establish which unprovided girder controls other demands. For the earlier multi-sheet export, the existing |M3| ranking still defaults to Left Exterior, with separate |V2| and |T| leaders. Entire Bridge Section / beam-only / slab-only force sets remain blocked as individual I-Girder section demands.

## User workflow

1. Run this release's complete app with `streamlit run app.py`.
2. Open Loads → ULS → Final Composite import. Use force kN and moment kN-m, as required by the native import's normalized values.
3. Upload the latest original Excel unchanged. Confirm the detected CSI format and Left Exterior Girder worksheet. Enter the actual FEA envelope name if the export has no OutputCase.
4. Click **Replace current rows**. Both Max and Min and all six components now appear in the Loads table.
5. Open Analysis and Calculate the desired stage/check. M2 and V3 remain reference values.

The previous static CSI Excel template remains unchanged. Its blank force cells must be populated when creating a new dataset. It is not necessary to move the user's values into that template.

## Source and acceptance limits retained

Max/Min alone does not establish simultaneous P/V2/T/M3. Keep the existing source-coupling REVIEW gate, numerical evidence and failures; do not add a checkbox to declare an unverified envelope vector concurrent. The supplied source has no governing case/correspondence identity. Previous CSIIMPORT1 primary CSI documentation and acceptance limits still apply. Final Composite still screens every native row, including the negative M3 bound; negative-composite acceptance, ordinary bar anchorage, end/D-region transfer and composite action retain their existing gates.

With the unchanged 250 mm deck JSON fixture and this Left Exterior source, numerical Final screening remains **78 REVIEW and 2 FAIL**. Import success does not close those engineering gates or make a failing section pass.

## Implementation and verification

Changed production modules: `io/girder_csi_import.py`, `ui/girder_csi_import.py`, `ui/loads_page.py` and `ui/igird_flexure_development.py`. Source-contract version is IGIRDER.CSIIMPORT2.auto-detect-v2, so previous cached results are invalidated. The existing 10-column Loads schema and Note source metadata are preserved.

`tests/test_igird_csi_import_auto.py` verifies exact latest workbook mapping, all six components reaching Analysis, reference/source trace values, incomplete-component rejection, legacy header aliases and duplicate append handling. The earlier source/strength regression tests remain included.

`qa/igird_csi_import_ui_verify.py` now exercises **full app.py** rather than only the narrower QA runtime page. It uses the unchanged workbook bytes, seeds the former legacy-format session selection, checks one uploader and no format radio, applies Replace, compares all **480 force values and 80 station values** with Excel, rejects a missing V3 without modifying current loads, invokes real Final Calculate, checks all 80 calculated source traces and raw-P conversion, reads the current-result dashboard, rejects whole-bridge forces and imports an existing app-column CSV while retaining its Nu convention. AppTest supplies upload bytes to Streamlit controls; it is not a browser drag-and-drop or visual layout check. Browser visual verification is not completed.

The clean candidate extraction passed **514 tests across 46 selected modules**, with zero failures, errors or skips, plus compileall and complete app.py startup. Full-app Streamlit UI verification passed with zero exceptions, all 80 rows calculated, all six components retained in stored traces and a current-result dashboard. Final Calculate took 8.864 seconds in this environment. These are selected regression and AppTest results, not the entire repository test suite or browser visual verification.

Fresh extraction evidence belongs in `qa/evidence/igird_csiimport2/`; the final release manifest records tests, checksum, preserved baseline entries and tested Python fingerprints. No caches, environments, node modules or new runtime logs belong in the deliverable. Historical baseline evidence is preserved separately.

Run:

```bash
streamlit run app.py
python -m pytest -q tests/test_igird_csi_import.py tests/test_igird_csi_import_auto.py
python qa/igird_csi_import_ui_verify.py
```

Repo summary: Fix automatic CSiBridge Excel import, preserve every Max/Min row and all six signed forces, and retain M2/V3 as reference values.

# IGIRDER.MAXMIN10 — separate Max / Min charts

Baseline: IGIRDER.UTILIZATION9, 2026-10-08. Presentation changes only.

## Behavior

Native CSI Max/Min results for one girder and source LC now have two visible
charts, headed Max and Min. This applies to Flexure — Final Composite, Shear,
Torsion and Shear + Torsion, in the collection, detailed design-member workspace
and Report / QA. Girder and base LC appear in each exported chart title.

The LC selector groups the native occurrence series into one source LC option.
Max/set 1, Max/set 2, Min/set 1 and Min/set 2 remain individual force paths and
original check rows. A repeated row is not assigned a Before/After meaning that
the source table has not established. Full names, Excel row and source sheet
remain on demand hover and in the stored audit.

- Flexure, Shear and Torsion default to **Max / Min — demand / capacity**.
- **Max / Min — utilization** reviews original component D/C separately within
  each ItemType. Torsion uses the UTILIZATION9 paired stored strength ratio
  `|Tu| / phiTn`, with the original maximum design/check D/C as open markers.
- Shear + Torsion defaults to separate Max / Min original component utilization
  charts. Its equations, completion gates and detailed audits remain available.
- **Selected source case** retains individual occurrence review in collection
  and Report / QA. **All load cases** retains the existing collection overview.
- Generic/static/app-column cases without native bound metadata retain their
  existing charts and selectors. A case name containing "Max" proves no bound.

For Report / QA, choose a check, girder and LC. **Create report chart PNG** creates
two download buttons: **Download Max report chart PNG** and **Download Min report
chart PNG**. Each image is 2880 x 1120 px. The selected stored-check CSV contains
both ItemTypes and every occurrence of the selected LC. Separate torsion strength
audit CSVs are available when reviewing utilization.

## Engineering and source integrity

Max/Min follow recorded CSI ItemType, not the sign of Mux, Vu or Tu. The Min
demand can be positive and Max demand can be negative. Signed actions remain
unchanged. The lower red `-phiVn` / `-phiTn` branch mirrors resistance magnitude;
it is not a plotted Min demand. Flexure resistance retains its original signed
sectional direction and developed composite-section calculations.

Grouping requires a complete qualified native series. The schema, file, LC,
sheet, distance basis, explicit step number, correspondence control, mode and
recorded coupling/evidence must match. Conflicting/partly untagged series are
excluded as a whole. No bounds are joined across unrelated files or members.
Correspondence declarations retain their original gates; chart grouping does
not declare an envelope to be a concurrent action vector.

Every capacity path uses the cached results for that bound's original source
case. No maximum demand is divided by another case's independently minimized
capacity. Existing qualified physical-endpoint sharing remains limited to
unique actual CSI rows in the same family; no interior force or resistance is
filled, extrapolated, interpolated or replaced by zero. Lines between source
stations are a plotting convention.

Missing Max or Min receives an explicit unavailable message. An imported bound
without stored checks is demand-only, or unavailable in utilization mode.
Cached NaN resistance retains its gap and cross. Showing another bound does not
clear that missing source. The complete original stored check rows remain in
the audit, including source gates and nested development traces.

Each chart footer reports that ItemType's stored control, station, original
FAIL/REVIEW counts and all-LC member control. Controls still use the largest
available original design/component D/C, including longitudinal/detailing
checks, rather than the largest signed force. Original ties and member-wide
gates remain in the ranking and summary. The chart-foot diamond locates that
same original component control; it has no force/capacity ordinate. This avoids
confusing a legacy status-priority capacity marker with the maximum component
D/C station. Detailed combined-check traces and
acceptance messages remain present when the duplicate legacy chart is hidden.

No equations, ULS/SLS acceptance, solver calls during review/export, input/load
activation, result versions, Project JSON, cache persistence or dependencies
changed. Review widgets write only their own selection state. Different member
details still require separate project models; Calculate all uses the existing
shared section/deck/reinforcement model.

## Diagnosis and verification scope

The user's app screenshot was labelled **Tu Max 1**. This identifies a selected
Max occurrence graph; the lower red capacity curve is not Min demand. The
screenshot alone does not prove that the overall calculation/import omitted
Min. The new paired view makes both source bounds directly inspectable.

The user's CSI screenshot records T = +231.1552 / -244.4573 kN-m for U2A and
uses Layout Line distance. Archived QA workbooks instead contain Left Exterior
Tu extrema +207.8554 / -223.0256 kN-m. These are different data snapshots.
QA uses their actual vectors with a hypothetical section/reinforcement model;
the second QA LC is a deliberately scaled fixture to exercise LC switching.
This work does not recalculate the user's complete project or substitute QA
forces for their imported results. Compare station coordinates only after
confirming the same Layout Line / Girder Distance basis.

## Verification evidence

Runtime: Python 3.14.7, Streamlit 1.61.0, pandas 3.0.6, PyArrow 24.0.0,
Plotly 5.24.1 and Kaleido 0.2.1; requirements.txt unchanged.

- Scoped baseline/new-feature regression: 61 modules, 794 passed.
- Final targeted regression after source qualification/missing-cache additions:
  102 passed, including 43 new Max/Min behavior tests.
- Generic collection AppTest: all four checks, both girders, AUTO/named/ALL,
  source audits, read-only results/input snapshots and stale hiding PASS.
- Native app.py AppTest: two girders x two LCs x four checks, both bound charts,
  source-vector review, detailed routes, paired source CSV, Max/Min PNG widgets,
  stored input/cache/design-member snapshots and stale hiding PASS.
  Review solver calls = 0. Evidence:
  `qa/evidence/igird_maxmin10/app/app_integration.json`.
- Tests cover exact original signed force coordinates and all occurrence rows;
  conflicting families/metadata; missing bounds/cache; distinct bound capacity;
  Min longitudinal control and retained member-wide failures/reviews.
- Final export verification: 36 PNGs, exact 2880 x 1120 px and component-control
  station/footer agreement, zero export solver calls and unchanged state.
  Final Max/Min images for all four checks were visually inspected.
- Source audit: 646 historical QA files unchanged; existing analysis calculation
  functions, dependencies, core/engine/IO and result versions unchanged.

AppTest plus exported-image inspection are used; no live Streamlit Cloud
deployment or full-page browser inspection is claimed. Existing Streamlit
table deprecation logs can appear. New check/control tables use the accepted
Arrow display adapter. Historical QA evidence remains unchanged.

Commands, from the repository root:

```bash
python -m pytest -q tests/test_igird_maxmin10.py tests/test_igird_casecontrol5.py tests/test_igird_reportcharts8.py tests/test_igird_chart3_full_span.py
python qa/igird_maxmin10_app_verify.py
python qa/igird_maxmin10_export_verify.py
python qa/igird_casecontrol5_ui_verify.py --output-dir qa/evidence/igird_maxmin10/generic_collection --release IGIRDER.MAXMIN10
```

## Repository summary

Separate native CSI Max/Min charts by girder and load case across flexure,
shear, torsion and combined checks, preserving source-paired resistance,
original controls and report PNG/CSV exports.

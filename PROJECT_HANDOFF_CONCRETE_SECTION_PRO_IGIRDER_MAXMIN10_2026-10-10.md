# Concrete Section Pro — IGIRDER.MAXMIN10

Date: 2026-10-10, Asia/Bangkok. Full source milestone; no push or deployment.

## Accepted baseline

Restored the complete IGIRDER.UTILIZATION9 archive (2026-10-08), not an earlier
ULS6F / CASECONTROL / ARROWFIX tree or the unrelated Segmental Box Girder app.

- Source ZIP: `concrete-section-pro_IGIRDER-UTILIZATION9.zip`
- SHA-256: `8ac24c149fb8f4a73c9ed04213e33cde7947898325fabf49838ae5987245539e`
- Original size: 55,739,090 bytes; 1,662 files; ZIP CRC checked before extraction.
- Historical source, QA fixtures and evidence are retained. All changes to
  existing application files are limited to five UI modules.

## User request and resulting behavior

The user wants separate Max and Min plots for the same girder / LC, including
Flexure — Final Composite and Shear in the same format as Torsion. The prior
screenshot showed **Tu Max 1**, which was one selected source series. That does
not establish that Min was absent from every underlying calculation/import.

The native CSI LC selector now groups every related occurrence into one source
LC option. Each girder's panel shows separate **Max** and **Min** charts, with
girder, base LC, quantity, units and stored control clearly identified. The
same figures are used in the detailed design-member workspace and Report / QA.

Flexure, Shear and Torsion default to separate demand/capacity charts.
**Max / Min — utilization** is available; Torsion retains UTILIZATION9's actual
same-source `|Tu|/phiTn` line and separate original design/check D/C markers.
Shear + Torsion also follows the shared format, using its original component
utilization. Its equations, required-source review and full audit remain present.

**Selected source case** retains individual Max/set or Min/set inspection in
the collection and Report / QA. Generic/static/app-column cases retain their
existing behavior. **All load cases** retains the existing collection overview.

Report / QA: select the check, girder and LC, then **Create report chart PNG**.
There are separate **Download Max report chart PNG** and **Download Min report
chart PNG** buttons, each 2880 x 1120 px. The stored-check CSV includes both
bounds and every original occurrence in the selected LC. Torsion utilization
also has separate bound station-audit CSVs. Filenames include member, LC, bound
and a source-family token while remaining compact.

## Source and engineering constraints preserved

- Max/Min are classified by recorded CSI ItemType, not force sign or a textual
  case-name guess. Every signed source action and repeated row remains intact.
- Source families must match native schema, file, LC, sheet, distance basis,
  step number, correspondence control, mode, coupling and evidence. A mixed or
  partly untagged series is excluded as a whole. Different girders/files/LCs
  never supply each other's missing bounds.
- Both source occurrence paths remain visible, labelled set 1/set 2. They are
  not assumed to be Before/After without source evidence. No occurrence rows
  are discarded or averaged, and each capacity uses its own cached source case.
- Missing bounds receive an explicit unavailable message. Imported bounds
  without stored checks remain demand-only or unavailable in utilization.
  NaN resistance/ratios keep their gaps and status crosses. No missing force is
  filled, extrapolated or converted to zero; no resistance moves between bounds.
- Existing unique native CSI shared physical endpoints are retained with their
  originating Excel identity. No internal station is fabricated.
- Each footer reports that bound's original controlling component D/C, station,
  FAIL/REVIEW counts and all-LC member control. The chart-foot diamond locates
  the same control, without assigning a force/capacity ordinate to a detailing
  ratio. It replaces legacy marker selection in these new paired views because
  a legacy status-priority station could differ from the maximum component D/C.
- The lower red `-phiVn` / `-phiTn` branch is mirrored resistance, not Min demand.
  Flexure resistance retains its original signed sectional direction.
- Original ties, source/concurrency, width, development, interface-shear,
  longitudinal V+T, detailing and overall member gates remain unchanged.
- No engineering equation, ULS/SLS decision, result version, dependency,
  Project JSON or result-persistence behavior changed. Reviewing/exporting
  stored results calls no solver and changes no engineering input, load bank,
  cached result or design member. Review widgets own only their selection state.

## Changed files

New shared presentation module:
`concrete_pmm_pro/ui/igird_maxmin_charts.py` — provenance-qualified LC families,
read-only source filters, per-bound figures, original controls, shared UI and
compact export naming.

Existing UI integration points:

- `igird_member_results.py`: grouped LC selection, paired plots and complete
  selected-family audits; retain individual source and all-case review.
- `igird_uls_report.py`: same paired figures, both-bound CSV and two PNG exports.
- `igird_vt_workspace.py`: detailed Shear/Torsion use the shared native view;
  the legacy generic/source route remains available.
- `analysis_page.py`: detailed Final Composite/combined charts share the view.
- `igird_combined_vt.py`: optional chart visibility hides only the duplicate
  legacy graph; equations, status messages, source checks and audit remain.

New tests/scripts: `tests/test_igird_maxmin10.py`,
`qa/igird_maxmin10_model.py`, `qa/igird_maxmin10_app_verify.py`,
`qa/igird_maxmin10_export_verify.py`. Release notes:
`docs/IGIRDER_MAXMIN10_2026-10-10.md`.

## Verification

Runtime: Python 3.14.7; Streamlit 1.61.0; pandas 3.0.6; PyArrow 24.0.0;
Plotly 5.24.1; Kaleido 0.2.1. requirements.txt is byte-identical to the baseline.

- Scoped regression: 61 modules, **794 passed**. This ran before 11 additional
  source-qualification/missing-cache tests and final control-marker refinement.
- Final targeted regression: 4 modules, **102 passed**, including **43** new
  Max/Min tests with exact force/source coordinates and per-bound control-marker
  agreement. Conflicting families, ambiguous metadata, missing bounds/cache,
  distinct bound resistance, Min longitudinal control and immutable results
  are covered. This is scoped validation, not the entire repository test suite.
- Generic collection AppTest: both girders, all four checks, AUTO/named/ALL,
  full audits, original state preservation and stale hiding **PASS**.
- Actual app.py native AppTest: two girders x two LCs x four checks, both bound
  charts, source-vector review, detailed routes, paired check CSV and separate
  PNG download widgets **PASS**. No Streamlit exceptions; review solver calls
  **0**; input/cache/design-member snapshots unchanged; stale results hidden.
- Final export verification regenerates **36** PNGs from stored production QA
  results, checks 2880 x 1120 px and control-marker/footer agreement, with no
  solver or state writes. Exported figures are visually reviewed.
- Changed/new Python modules and app.py compile successfully.

Evidence: `qa/evidence/igird_maxmin10/` contains regression logs/XML, module list,
actual-app verification, generic collection evidence, source/check CSVs,
Plotly JSON, full-size PNGs, final export verification and archive/source audits.
Historical evidence remains unchanged. Optional local AppTest checkpoints and
runtime environments are outside the distributable archive.

QA uses archived CSI vectors with a hypothetical section/reinforcement model.
U2A fixture actions are preserved; QA_LC2 scales the fixture solely to test LC
switching. These are not a reconstruction or engineering approval of the user's
complete project. The screenshot extrema (+231.1552 / -244.4573 kN-m) differ
from the archived Left Exterior fixture (+207.8554 / -223.0256 kN-m). The CSI
screenshot uses Layout Line distance; the importer prefers Girder Distance.
Confirm a common distance basis before comparing station coordinates.

AppTest and exported-image inspection were used. No live Streamlit Cloud
deployment or full-page browser verification is claimed. Inherited Streamlit
table deprecation and automatic Arrow-fix logs may appear; completed AppTests
have no fatal exception. New result/control tables use the accepted Arrow
display adapter.

## Deployment and use

Use the full `concrete-section-pro_IGIRDER-MAXMIN10.zip` root as the replacement
source tree. Preserve the unchanged dependencies and supported Python runtime.
After deploying or loading a Project JSON, calculate the relevant check again
to populate session-only stored member results. Open a girder, choose the source
LC, then demand/capacity or utilization. Inspect original stored controls/gates
and both charts before exporting. Different member section/deck/reinforcement
details still require separate project models.

Do not overwrite or change earlier archives. No git push, commit, cloud restart
or deployment was performed. Continue future work from this milestone.

## English repository summary

Separate native CSI Max/Min charts by girder and load case across flexure,
shear, torsion and combined checks, preserving source-paired resistance,
original controls and report PNG/CSV exports.

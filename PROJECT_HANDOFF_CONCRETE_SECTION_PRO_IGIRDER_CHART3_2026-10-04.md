# Project handoff — IGIRDER.CHART3

## Accepted baseline and delivered scope

Baseline: `concrete-section-pro_IGIRDER-VTQA1-simplified-charts-code-review.zip`, SHA-256 `b5f6b2b8171c90b9f2c378d346416282f0d0ad5d09258bf62e59986a638f1adf`, 1,166 entries. Preserve all baseline files and previous handoffs. This release is the complete app, not a patch. The source code remains governed by `CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md` and the supplied AASHTO LRFD Ninth Edition (2020) Section 5.

The user wants every case diagram across the full physical 20 m span, including φTn. Native CSI occurrence-set 2 curves lost shared physical endpoints when the selected case was filtered. The torsion threshold early return independently omitted calculable resistance at 17 interior station rows. Both causes are addressed.

## Implementation

- `visualization/igird_uls_chart_display.py`: native source-family endpoint view with exact row provenance; compact hover retains provenance; unavailable capacity is marked at the chart foot, never as numeric zero.
- `ui/analysis_page.py`: shared demand view accepts full source context and explicit physical span; separate stored torsion capacity diagram evaluated during Calculate with an internal `__Capacity diagram` flag. The flag bypasses only threshold/zero-demand early returns. All section/material/hoop/strain/development gates remain. Known original resistance is reused, omitted resistance is evaluated with actual station forces, and unavailable stations remain NaN. Shear keeps internal missing stations in the chart. Isolated known capacities are visible as markers. Combined component charts use full physical axes.
- `ui/igird_vt_workspace.py`: retains all source rows for selected-case demand; uses the stored torsion diagram, with a collapsed station/source/θ audit and missing-source explanation. Source-generated diagram rows are never design rows.
- New regressions: `tests/test_igird_chart3_full_span.py`; actual UI evidence script `qa/igird_chart3_ui_verify.py`. Existing VTQA1 UI verification now permits exact shared endpoints while retaining original force coordinates.

## Cache and engineering invariants

Shear and Torsion cache versions add `.chart3-capacity-diagram` to invalidate pre-diagram payloads. Combined retains the unchanged concurrent V+T equation/result version, which Summary uses to interpret the same engineering decisions; a chart payload must not change that contract. The new `shear_diagram_capacity_df` and `torsion_diagram_capacity_df` must be carried into the corresponding caches when Calculate Shear + Torsion populates its source checks. Previously cached Combined design rows remain numerically valid; press Calculate again to create the new diagram sources.

Shear diagram endpoints also use the actual source forces. The previous set-2 synthetic boundary used zero forces and could show an unrelated larger φVn against the shared actual Vu. The new separate diagram evaluates actual shared endpoints and retains the original critical-section rows for plotting. Shared Max/Min endpoints must give exactly the same β/θ/φVn for both occurrence sets. Zero-Vu capacity can be evaluated without changing the original NO DEMAND decision. Both diagrams are independently checked at all 84 source/view stations (336 additional θ/resistance scalar comparisons).

Do not merge the diagram table into `_beam_uls_torsion_check_dataframe`, decision/governing rows, Report/QA acceptance, or Summary. Do not solve on chart/case changes, summary, or report review. No persistent-cache experiment is introduced. Do not replace raw CSI imports with augmented plot views, change signs, add an axial-force override, assign P=0 automatically, or promote M2/V3 to primary actions. No extra dependency is needed.

Endpoint sharing requires native metadata, a matching sheet/base-case/Max-or-Min/distance/schema/kind family and one finite source endpoint. It does not fill interior holes, unavailable endpoints, conflicting endpoints, or legacy case names without provenance. Shared rows identify their originating Excel row and case on hover. Caption and source audit distinguish source decisions from diagram evaluations.

## Development/source qualifications

The unanchored QA model uses explicitly hypothetical verified fy=390 MPa, continuous bars, ld=1000 mm. It has 76 finite φTn rows out of 84 diagram rows, with 0/L strain-source gaps. The second QA model explicitly selects both full-strength end anchors through real controls; all 84 diagram rows have finite φTn. These settings are not inferred or confirmed for the user. The supplied original JSON/workbook remain byte-identical.

The current station-strain route does not automatically invoke the optional near-support εs-at-dv provision in 5.7.3.4.2. Concentrated-load conditions and anchorage need suitable source ownership before enabling that alternative. Do not copy an interior capacity to disguise an unavailable end strain source. Full x-axis coverage does not imply numeric D/C at excluded support boundaries.

Standalone φTn remains the transverse component under 5.7.3.6.2. Source-qualified concurrent longitudinal and combined checks remain separately required above the investigation threshold; native Max/Min envelopes cannot establish concurrent Mu/Nu/Vu/Tu acceptance. V/T section geometry remains solid precast; composite-deck torsion is not newly certified.

## Evidence and resuming work

Read `IGIRDER_CHART3_GRAPH_REVIEW_2026-10-04.md`, `qa/evidence/igird_chart3/chart3_ui_result.json` and `fresh_validation_summary.json`. The UI script compares six original decision/source DataFrames with VTQA1 exactly, exercises all four native cases with and without end anchorage, and independently checks θ/φTn in 168 scalar substitutions. It also runs actual Construction/Final/Interface/Combined controls and checks that review does not solve.

The complete ZIP is named `concrete-section-pro_IGIRDER-CHART3-full-span-source-capacity-diagrams.zip`. The final release manifest beside it records its exact checksum, entry inventory, baseline preservation, tests, and equality of the final Python fingerprint with the freshly tested extraction. PNG/HTML evidence inside the app is from production Plotly coordinates; it is not a browser screenshot or browser-print verification claim.

User-facing run instructions: unzip the whole app and run the existing Streamlit entrypoint. Press Calculate Torsion or Calculate Shear + Torsion once after opening this release, then select the case diagram. Use the stored diagram audit for below-threshold resistance and end-source explanations. Keep the English Repo summary as the single sentence in `REPO_SUMMARY_IGIRDER_CHART3.md`.

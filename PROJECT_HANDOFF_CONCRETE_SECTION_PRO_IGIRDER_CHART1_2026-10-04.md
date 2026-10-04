# PROJECT HANDOFF — CONCRETE SECTION PRO — IGIRDER.CHART1

Date: 2026-10-04. Continue AASHTO LRFD 9th Edition (2020) and the project app-style skill. This is a chart presentation milestone.

## Baseline and authorized task

Continue the complete delivered `concrete-section-pro_IGIRDER-CSIIMPORT2-auto-detect-all-forces.zip`, SHA-256 `7e632d217913213ca0adcfa537f17052051d2bc86b9159db694410df50c22847`. Preserve all 1,086 baseline entries and the accepted ULS6F → ULS7 → DBQA/PERF → FLEXDEP1 → FLEXSIGN1 → CSIIMPORT1/2 lineage.

The user supplied `Flexure_Final-Composite(2).pdf` and reported overlapping/repeated legends and multiple superimposed deck-interface shear lines. The user separately cancelled the proposed axial-demand-mode change and will enter **P=0 directly in their Excel**. That cancellation remains binding: no axial mode, automatic P override or modified user workbook is added. V3/M2 remain reference-only, and CSI import still retains all original source rows.

## Findings in the supplied PDF and source

The interface figure drew four independent demand paths: Max/set 1, Max/set 2, Min/set 1 and Min/set 2. Their long legends share the same envelope/member prefix. Fixed-width legend slots cannot contain those full labels, so the text overlaps adjacent entries. Automatic Plotly colors also made some demand paths red, although dashed red is the project's resistance convention.

The flexure figure drew a φMn trace for each case and showed every φMn legend entry. For P=0, the developed section resistance at a given position is common to those source sets, so those paths overlap. The old demand-label truncation retained the shared prefix and removed the differentiating Max/Min/occurrence suffix. A failed/missing equilibrium path or genuinely different Nu-dependent resistance must not be collapsed away.

## New display behavior

- Interface main chart: **vui max** is the maximum calculated scalar interface demand at each position, across every original Max/Min and occurrence. It remains blue. **φvni** is the minimum available scalar resistance at that position and remains dashed red. Both station values retain their actual controlling source case for hover. Missing resistance stays a gap. No axial/shear/torsion load vector is assembled from different rows.
- Original row-based interface D/C, minimum reinforcement, governing row and PASS/FAIL/REVIEW remain unchanged. The chart's independently enveloped quantities do not create another D/C. All 80 original rows remain in the audit.
- Flexure legends identify **Mux Max 1, Mux Max 2, Mux Min 1, Mux Min 2**. Full source case names remain on hover and in the audit. Demand is blue; Min uses a dotted line and occurrence 2 uses a diamond marker. Multi-envelope/member collisions receive distinct short case identifiers.
- φMn legend appears once. A redundant capacity trace is removed only when every finite original coordinate exactly coincides with one original covering path. Different resistance values, disjoint station ranges and any missing-equilibrium gap prevent merging. No trace coordinate is changed to create a common curve.
- Final Composite and interface figures permit hover while disabling drag and the mode bar. Other browser figures retain their existing default interaction behavior.
- Existing 0–20 m figure domains and shared global chart fonts, colors and margins remain active. No new formula, section geometry, resistance model, load input, JSON behavior or result-cache persistence is introduced. Review pages read stored calculations.

## Implementation

`concrete_pmm_pro/visualization/igird_uls_chart_display.py` contains read-only display aggregation, concise source labels and exact coincidence checks. The scoped render functions in `ui/analysis_page.py` use these helpers, add full source hover values and update captions. Engineering producers are unchanged; AST comparison against the accepted ZIP records the five modified UI/figure functions.

`tests/test_igird_chart_display.py` covers scalar bounds/occurrences, source identity, input-table immutability, gap preservation, independent envelope values without mixed-case D/C, unchanged governing check, demand-coordinate fidelity, coincident versus different/disjoint capacity paths and unique legends.

## Verified numerical fixture and limits

`qa/igird_chart_ui_verify.py` runs **full app.py** using the existing 250-mm deck project and the latest 80-row Left Exterior force fixture with P=0 as a QA input matching the user's stated decision. The original fixture and user workbook are not modified. Interface anchorage is set to the checked condition shown in the PDF.

It invokes actual Final Composite and Interface Calculate controls, checks all 80 rows in each calculation, verifies the maximum plotted vui against every original station group and its source identity, confirms unique short legends and one exact common φMn curve, and rejects any unexpected solver call during an ordinary review rerun. Stored numerical dataframes remain byte-for-value equivalent before and after that review.

The resulting midspan φMn is **9,975.756314 kN-m**. Governing interface vui is **1.714291 MPa**, with the original D/C **0.560094**. These reproduce the rounded PDF card values. The fixed fixture's all-row flexure screening still contains 76 REVIEW and 4 FAIL at physical-end bounds under unchanged end development/anchorage assumptions. This chart milestone does not close engineering acceptance gates. Do not use a clearer graph as evidence that an unresolved end/check now passes.

Preview PNGs are rendered with Matplotlib from the actual production Plotly trace coordinates, with full span and unique legends. Standalone interactive HTML files embed Plotly JS and require no CDN. These are data/trace previews, not browser screenshots. Full-app Streamlit AppTest verification is completed; native browser visual or browser-print layout verification is not completed. The original PDF shows right-side print clipping as well as crowded legends; this release does not claim a full print-export redesign.

Fresh extraction verification passed **527 selected tests in 48 modules** in 41.48 seconds, with no failures, errors or skips. Python compilation and full-app startup passed. The unchanged native CSI importer passed its full-app regression with 480 exact force-component comparisons, and the chart full-app calculation/review verification passed. AST comparison confirms exactly five existing UI/figure definitions changed; all 189 other existing production Python modules are byte-identical to CSIIMPORT2. The new module contains presentation helpers only.

Fresh extraction evidence is in `qa/evidence/igird_chart1/`. The clean release excludes caches, environments, node modules and new runtime logs; all historical baseline files remain. The release manifest records the checksum, preserved entries, selected regression, actual UI actions and tested Python fingerprints.

Run:

```bash
streamlit run app.py
python -m pytest -q tests/test_igird_chart_display.py tests/test_igird_uls3c_flexure_legend_polish.py
python qa/igird_chart_ui_verify.py
```

Repo summary: Simplify I-Girder interface-shear envelopes and remove duplicate flexure legends while preserving every original check result.

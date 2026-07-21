### CROSSBEAM.PTLOSS2 - Anchorage Set / Draw-in Loss Foundation

Adds an isolated Crossbeam anchorage-set/draw-in compatibility preview that derives zero-movement influence length, lock-off force/stress, and station-level additional seating loss from the accepted post-friction force diagram while keeping `Pe / Pe_eff` and later loss/stage solvers locked. See `README_CROSSBEAM_PTLOSS2.md`.

### CROSSBEAM.PTLOSS1G - Prestress Loss Subtab Architecture

Reorganizes the Crossbeam `Prestress Loss` workspace into `Overview`, `Friction & Wobble`, `Anchorage Set / Draw-in`, `Elastic Shortening`, `Time-Dependent`, and `Audit` subtabs while preserving accepted friction/wobble calculations and keeping future loss components plus `Pe / Pe_eff` assembly explicitly guarded. See `README_CROSSBEAM_PTLOSS1G.md`.

### CROSSBEAM.PTLOSS1F - Regression Baseline Lock

Repairs stale regression assertions for the tendon-profile import schema, current Crossbeam navigation, and Railway U-Girder historical README closeout evidence without changing production code, solver equations, prestress logic, Project JSON, reports, rebar, or member-workflow runtime behavior. See `README_CROSSBEAM_PTLOSS1F.md`.

### CROSSBEAM.PTLOSS1E - Prestress Loss Table Export Layout Polish

Polishes the Crossbeam `Prestress Loss` table layout by moving repeated
blocking issues/review notes out of the wide station trace into a compact
review table, placing `Status` near the left side, and using engineering
display symbols `μ` and `α` while preserving calculation behavior. See
`README_CROSSBEAM_PTLOSS1E.md`.

### CROSSBEAM.PTLOSS1D - External Note Table Compactness Polish

Polishes the Crossbeam `Prestress Loss` external tendon table notes with
compact HDPE review and no-deviator wording so PDF/export tables stay readable,
while preserving the PTLOSS1C calculation behavior and summary metrics. See
`README_CROSSBEAM_PTLOSS1D.md`.

### CROSSBEAM.PTLOSS1C - External Summary And Review Note Fix

Fixes Crossbeam `Prestress Loss` summary cards so calculated external
HDPE-lined review-note rows govern `Worst traced loss` and `Minimum P/Pj`,
separates blocking issues from nonblocking notes, and requires review only when
external tendons lack `Deviator` points. See `README_CROSSBEAM_PTLOSS1C.md`.

### CROSSBEAM.PTLOSS1B - Loss Table Readability Polish

Polishes the Crossbeam `Prestress Loss` station trace by shortening `K use` and
`mu basis` wording plus splitting long assumptions captions, while preserving
the PTLOSS1A AASHTO friction/wobble calculations and HDPE-lined external tendon
defaults. See `README_CROSSBEAM_PTLOSS1B.md`.

### CROSSBEAM.PTLOSS1A - HDPE External Loss Assumption Polish

Polishes the Crossbeam `Prestress Loss` assumptions for HDPE-lined external
tendons by keeping `mu = 0.25` as a conservative adopted value, documenting the
AASHTO polyethylene reference value `mu = 0.23`, displaying external `K (/m)` as
`N/A`, and adding regression coverage that prevents the internal `Kx` term from
affecting external deviator loss. See `README_CROSSBEAM_PTLOSS1A.md`.

### CROSSBEAM.PTLOSS1 - AASHTO Friction/Wobble Loss Foundation

Adds a Crossbeam `Prestress Loss` page after `Tendon Profile` that calculates
AASHTO LRFD 5.9.3.2.2b friction/wobble station traces from Tendon System `Pj`
and Tendon Profile geometry, persists editable loss assumptions in a separate
Project JSON metadata block, and clearly guards that `P after friction` is not
final effective prestress. See `README_CROSSBEAM_PTLOSS1.md`.

### CROSSBEAM.PTA1A - Jacking Force Trace Wording Hotfix

Polishes the Crossbeam PTA1 jacking-force source wording, removes repeated
`Active Pj credit` from station trace rows, and labels station `Pj` as a
per-tendon source value that must not be summed across geometry stations while
leaving force arithmetic, Project JSON shape, reports, rebar workflows, and
solvers unchanged. See `README_CROSSBEAM_PTA1A.md`.

### CROSSBEAM.PTA1 - Prestress Force Source Foundation

Adds a Crossbeam prestress-force source audit that derives each tendon's
`Aps total`, `fpj`, and source `Pj` from the Tendon System, summarizes active
total jacking force, and traces that source to Tendon Profile station rows
without changing Project JSON shape, reports, rebar workflows, or solvers. See
`README_CROSSBEAM_PTA1.md`.

### CROSSBEAM.PTQA8 - Tendon Profile Import Writeback QA

Adds Crossbeam Tendon Profile post-apply writeback QA that confirms imported
rows match active profile state, Project JSON tendon metadata, Calculated Audit
context, and Elevation/Cross Section/3D view coverage while leaving Project
JSON shape, reports, rebar workflows, and solvers unchanged. See
`README_CROSSBEAM_PTQA8.md`.

### CROSSBEAM.PTQA7 - Tendon Profile Import Apply Verification Polish

Adds Crossbeam Tendon Profile import view-coverage verification so active
tendons must cover `s=0..L` with enough points for Elevation, Cross Section,
and 3D review before guarded apply is enabled, while leaving Project JSON
shape, reports, rebar workflows, and solvers unchanged. See
`README_CROSSBEAM_PTQA7.md`.

### CROSSBEAM.PTQA6 - Tendon Profile Import UX Audit Trace

Adds Crossbeam Tendon Profile import audit trace with Excel sheet selection,
active-profile CSV download, row-level diff preview, guarded apply metadata,
and friendlier validation hints while leaving Project JSON shape, reports,
rebar workflows, and solvers unchanged. See `README_CROSSBEAM_PTQA6.md`.

### CROSSBEAM.PTQA5A - Import Apply Streamlit State Hotfix

Fixes the Tendon Profile import apply crash by resetting confirmation through a
separate revision key instead of writing to the Streamlit checkbox widget key
after it has been instantiated. Apply/Undo behavior, row validation, Project
JSON export shape, reports, rebar workflows, and solvers remain unchanged. See
`README_CROSSBEAM_PTQA5A.md`.

### CROSSBEAM.PTQA5 - Tendon Profile Import Apply Guard

Adds a guarded Crossbeam Tendon Profile import apply flow: the import panel is
more compact, valid CSV/XLSX previews show row-change counts, and replacing the
active `s-x-dtop` table now requires explicit confirmation with one-step undo.
The action is limited to Tendon Profile geometry rows and does not change
Tendon System, Segment Layout, Section Builder, Project JSON export shape,
reports, rebar workflows, or solvers. See `README_CROSSBEAM_PTQA5.md`.

### CROSSBEAM.PTQA4 - Tendon Profile Import Foundation

Adds a Crossbeam Tendon Profile import foundation with a live CSV template
download and preview-only CSV/XLSX validation against the current Tendon System,
Segment Layout, and Section Builder context. Uploaded rows are normalized for
review but are not applied to the active profile table, Project JSON, reports,
or solvers in this milestone. See `README_CROSSBEAM_PTQA4.md`.

### CROSSBEAM.PTQA3 - Rebar Joint PT Continuity Status Sync

Syncs the Crossbeam Rebar workspace with the Tendon Profile continuity audit so
the PT continuity card, locked-joint message, rebar elevation annotations,
joint table, and compact station audit no longer say PT is unverified after the
profile audit has passed. Ordinary rebar crossing remains locked to `0 mm²`,
and rebar templates, tendon coordinates, Project JSON shape, reports, and all
solvers remain unchanged. See `README_CROSSBEAM_PTQA3.md`.

### CROSSBEAM.PTQA2 - Tendon Review Figure Layout Polish

Polishes the Crossbeam Tendon Profile review experience by adding a compact
joint-level PT continuity summary above the detailed audit rows and moving the
Elevation/3D Orthographic legends into reserved figure header bands so labels
and models no longer overlap. This is presentation and audit-readability polish
only; tendon coordinates, continuity rules, Project JSON shape, reports, rebar
workflows, and solvers remain unchanged. See `README_CROSSBEAM_PTQA2.md`.

### CROSSBEAM.PTQA1 - Tendon Geometry Continuity Audit

Adds a Crossbeam Tendon Profile `Calculated Audit` check for active tendon
geometry continuity at every internal segment joint, verifying interpolated
profile coverage, positive Aps/fpj source values, and internal tendon
Section-ID polygon fit on both adjacent joint faces. The PT continuity card now
reports live geometry status instead of hard-coded `NOT VERIFIED`; Project JSON
shape, tendon presets, rebar workflows, reports, and solvers remain unchanged.
See `README_CROSSBEAM_PTQA1.md`.

### CROSSBEAM.PT1L - Parabolic Preset Parameter Reactivity

Makes the Crossbeam Tendon Profile `Preset bend offset (mm)` and
`Support width (m)` sliders immediately regenerate the selected tendon profile
rows, so Parabolic Tendon 2 Span low-point depth and middle-support crown width
change visibly when those controls change. `Re-apply` remains available for
target-tendon changes; Project JSON shape, member length ownership, review
routing, rebar workflows, reports, and solvers remain unchanged. See
`README_CROSSBEAM_PT1L.md`.

### CROSSBEAM.PT1K - Interior-Support Parabolic Crown

Refines `Parabolic Tendon / 2 Span` so the middle-support zone uses its own
inverted parabolic crown across `2 x support width`, giving a smoother tangent
through the interior column instead of a sharp high-point kink. The generated
geometry remains ordinary editable `s-x-dtop` rows and does not change Project
JSON shape, member length ownership, review routing, or solvers. See
`README_CROSSBEAM_PT1K.md`.

### CROSSBEAM.PT1J - Support-Width Tendon Profile Sampling

Adds support-width-aware Crossbeam Tendon Profile quick-start generation so
2 Span bent profiles use a three-point high zone across the column width, and
Parabolic Tendon profiles use denser sampled control points for smoother
single-span, midspan, and interior-support geometry. The new support-width
slider only affects generated editable `s-x-dtop` seed rows; Project JSON shape,
member length ownership, review routing, and solvers remain unchanged. See
`README_CROSSBEAM_PT1J.md`.

### CROSSBEAM.PT1I - Curated 2-Span Tendon Profile Gallery

Curates the Crossbeam Tendon Profile quick-start catalog to three unnumbered
patterns - Straight Tendon, Straight Tendon With Bends, and Parabolic Tendon -
and replaces ambiguous Multiple Span behavior with explicit 2 Span profiles that
repeat the simple-span shape across the middle support. Legacy numbered preset
names and Multiple Span state are normalized into the new options; Project JSON,
review figures, member length ownership, and solvers remain unchanged. See
`README_CROSSBEAM_PT1I.md`.

### CROSSBEAM.PT1H — Quick-Start Tendon Profile Gallery

Adds a reference-style Crossbeam Tendon Profile quick-start gallery with
Straight, Bent, and Parabolic tendon families plus Single Span and Multiple
Span schematics. Changing the active quick-start option rewrites the selected
tendons' editable `s-x-dtop` rows, while target/offset changes can be re-applied
explicitly; Project JSON, member length ownership, review figures, and all
solvers remain unchanged. See `README_CROSSBEAM_PT1H.md`.

### CROSSBEAM.PT1G — Editable Tendon Profile Points and Presets

Adds Crossbeam Tendon Profile quick-start presets for straight, bent,
parabolic, and multi-span draped geometry, plus explicit dynamic row add/delete
handling in the editable `s-x-dtop` table. Presets replace only selected
tendons, keep full-inventory web-centered coordinates as the reference, and
leave Project JSON, member length ownership, review figures, and all solvers
unchanged. See `README_CROSSBEAM_PT1G.md`.

### CROSSBEAM.PT1F — Web-Centered Tendon Default Placement

Seeds the Portal Frame Crossbeam default tendon system as eight web-centered
tendons, four per side. T1-T4 start on the left web centerline and T5-T8 on
the right web centerline; their default P1/P2/P3 points keep x and dtop
constant, with vertical levels from 500 mm below the top to 300 mm above the
bottom. Existing edited tendon inputs, Project-JSON schema, solvers, and other
workflows remain unchanged. See `README_CROSSBEAM_PT1F.md`.

### CROSSBEAM.PT1E — 3D Visual Hierarchy and Neutral Concrete Palette

Replaces Plotly's per-trace rainbow Mesh3d colors with role-based neutral
Solid/Hollow concrete colors, stable high-contrast tendon colors, and explicit
section/void boundary loops. Both muted and transparent display modes keep the
orthographic geometry legible without changing section, segment, tendon,
Project-JSON, or solver data. See `README_CROSSBEAM_PT1E.md`.

### CROSSBEAM.PT1D — Tendon Inventory Source of Truth

Removes the independent `Number of tendons` input and derives Stored/Active
counts from the Tendon System rows. Controlled Add and confirmed Remove
actions keep each complete tendon, its three default profile points, visible
Tendon IDs, and Project-JSON restore state synchronized while preserving the
minimum three-tendon guard and leaving all solvers unchanged. See
`README_CROSSBEAM_PT1D.md`.

### CROSSBEAM.PT1C — Crossbeam Member-Length Source of Truth

Moves the sole editable Crossbeam total length `L` to a member-level card in
Section Builder, makes Segment Layout and Tendon Profile read-only consumers,
and requires an explicit Keep-or-Scale decision before any length change is
committed. Proportional scaling updates Segment, Tendon, and existing Rebar
Zone longitudinal stations together without changing section geometry,
reinforcement quantities, materials, or solvers. See
`README_CROSSBEAM_PT1C.md`.

### CROSSBEAM.PT1B — Transparent-3D State Isolation and Visible Sub-tabs

Keeps `Transparent 3D concrete` display-only by separating the durable
Crossbeam length from Streamlit widget lifecycle state, safely recovers the
known stale 0.100 m sentinel from matching stored station endpoints, and
restyles React-Aria sub-tabs to the current blue app theme without changing
geometry coordinates, Project-JSON inputs, solvers, or other workflows. See
`README_CROSSBEAM_PT1B.md`.

### CROSSBEAM.PT1 — Tendon System and Tendon Profile Source of Truth

Promotes the Crossbeam tendon system and top-referenced Plan/Profile/3D
geometry to a versioned Project-JSON source of truth with compact first-edit
tables and station-specific Section ID centroid audit, while keeping PT
continuity required but unverified and leaving all solvers isolated. See
`README_CROSSBEAM_PT1.md`.

### UI.SYNC1 — Placement Clarity and Workflow Display Sync

Separates Crossbeam transverse placement inputs into cross-section cage offset
and longitudinal Zone-end controls, and commits the Setup workflow dropdown
before rerun so the displayed Active Member Workflow and downstream context
change together on the first selection. See `README_UI_SYNC1.md`.

### CROSSBEAM.RB-EDIT1 — Single-Commit Editable Rebar Tables

Commits the first edit across all 14 Crossbeam Rebar data tables by consuming
Streamlit `edited_rows` patches in widget callbacks, while preserving linked
material/fy values, Template/Zone references, Project-JSON persistence, and
solver isolation. See `README_CROSSBEAM_RB_EDIT1.md`.

### CROSSBEAM.RB-PERSIST1 — Crossbeam Reinforcement Project-JSON Persistence

Persists the complete Crossbeam longitudinal/transverse template libraries, Segment/Zone assignments and references, and stable preview selections in a versioned Project-JSON block with older-file migration and post-load reference validation, while keeping all solvers and analysis-result caches isolated. See `README_CROSSBEAM_RB_PERSIST1.md`.

### CROSSBEAM.RB2G2 — Hollow Transverse Bar-Piece Topology

Replaces the schematic Hollow transverse layout with two complete closed web loops, four Outer/Inner Top/Bottom flange U-bars, and four straight chamfer bars. Every bar piece participates in geometric clash/coverage review, while Av/s credit remains web-leg-only and all solvers stay isolated. See `README_CROSSBEAM_RB2G2.md`.

### CROSSBEAM.RB2G1 — Cage-Relative Longitudinal Offset Correction

Derives active-Zone longitudinal preview centers from the transverse cage offset plus both bar radii, fits web/corner bars to the actual cage path, preserves Hollow flange-face bars between independent web cages, and removes the default reinforcement overlap without changing adopted quantities or solver inputs. See `README_CROSSBEAM_RB2G1.md`.

### CROSSBEAM.RB2G — Combined Cross-Section Reinforcement Preview

Replaces the stacked Combined review with one layer-ordered Crossbeam section figure, adds 25 mm transverse bend fillets, makes Solid ties follow the outer bottom fillets, preserves rectangular Hollow web cages, validates transverse-outside-longitudinal containment using true bar radii, and retains the accepted full-length transverse elevation below. Preview-only scope and all solver/joint guards remain unchanged. See `README_CROSSBEAM_RB2G.md`.

### CROSSBEAM.TR1 — Transverse / Shear Rebar Templates and Local-Zone Review

Adds independent Hollow-web and Solid multi-leg transverse reinforcement templates, dual Longitudinal/Transverse Zone assignment, compact no-scroll input tables, Av/s previews, and local cross-section/elevation review while preserving zero ordinary-rebar joint crossing, no automatic joint-shear credit, and unchanged solvers.

See `README_CROSSBEAM_TR1.md`.

### CROSSBEAM.RB2E — Linked Rebar Grade Dropdown Hotfix

Synchronizes the Crossbeam Rebar Template `Material` and `fy` dropdowns visibly after one selection by refreshing the compact editor from the corrected canonical pair.

See `README_CROSSBEAM_RB2E.md`.

### CROSSBEAM.RB2D — Editable Template IDs and Linked Rebar Grade Dropdowns

Makes Crossbeam Rebar Template IDs engineer-editable with atomic Segment/Zone reference updates, and replaces free-form rebar grade inputs with linked SD40/SD50 and 390/490 MPa dropdowns while preserving all solver and joint-continuity guards.

See `README_CROSSBEAM_RB2D.md`.

### CROSSBEAM.RB2C — Direct-Edit Rebar Template Tables

Replaces the selected-template form with compact direct-edit tables for default and project Rebar Templates, including inline dropdown/number inputs, per-row copy/delete selection, guarded deletion, and six-column no-scroll table limits while preserving stable Template IDs, zero ordinary-rebar joint crossing, and unchanged solvers.

See `README_CROSSBEAM_RB2C.md`.

### CROSSBEAM.RB2B — Rebar Template Management and Count/Spacing Layout

Adds Crossbeam-only Rebar Template create/duplicate/guarded-delete actions plus outer/inner layouts by target spacing or exact bar count, while retaining compact no-scroll summaries, zero ordinary-rebar joint crossing, and unchanged solvers.

See `README_CROSSBEAM_RB2B.md`.

### CROSSBEAM.RB2A — Rebar Review Hardening and PT-Continuity Guard

Hardens the Crossbeam rebar review workspace with compact no-scroll tables, selected-template editing, separate generated/adopted reinforcement, enhanced bar markers, and an explicit PT-continuity-required/not-verified guard while leaving all existing solvers unchanged.

See `README_CROSSBEAM_RB2A.md`.

### CROSSBEAM.RB2 — Segment Section Rebar Preview and Subnavigation Polish

Adds Crossbeam-only segment/zone section rebar figures with Solid outer-perimeter and Hollow outer/inner-face layouts, clearer template controls, and separated button navigation while keeping ordinary-rebar joint crossing locked at zero and all existing solvers unchanged.

See `README_CROSSBEAM_RB2.md`.

### CROSSBEAM.SECLIB1E — One-Click Project-Section Selection

Fixes the Crossbeam Project Section Summary so the selected row/checkbox activates the section on the first click by staging the Section ID in a pre-rerun callback before geometry and preview widgets render.

See `README_CROSSBEAM_SECLIB1E.md`.

### CROSSBEAM.SECLIB1D — Section Naming and Active-Row Polish

Adds optional role-based section-name suggestions, duplicate-name protection, a clear active-project-section line, and highlighted table selection while keeping Section IDs stable and existing workflows/solvers unchanged.

See `README_CROSSBEAM_SECLIB1D.md`.

### CROSSBEAM.SECLIB1B — Visible Section Summary and Low-Effort Management

Adds a visible project-section inventory plus direct name editing and guarded deletion while preserving stable Section IDs, Segment Layout references, Streamlit state safety, and all existing workflow/solver behavior.

See `README_CROSSBEAM_SECLIB1B.md`.

### CROSSBEAM.SECLIB1A — Streamlit State Hotfix and Low-Effort Section Workflow

Fixes the Crossbeam Section Definition Library selectbox session-state mutation error and simplifies section creation to Select → Duplicate/New → Edit geometry → Assign in Segment Layout, while keeping advanced management collapsed and all existing workflows unchanged.

See `README_CROSSBEAM_SECLIB1A.md`.

### CROSSBEAM.SECLIB1 — Multi-Section Definition Library and Segment Assignment

Adds project Section IDs above the two Crossbeam geometry preset families, supports several Solid/Hollow instances with independent dimensions and gross properties, assigns Section IDs in Segment Layout, and persists the workflow-scoped library in backward-compatible Project JSON metadata without connecting it to existing solvers.

See `README_CROSSBEAM_SECLIB1.md`.

### CROSSBEAM.RB1 — Segment-Based Rebar Templates and Joint Participation

Adds a Crossbeam-only Rebar workspace with segment/zone templates, a locked zero-ordinary-rebar rule at every segment joint, tendon-only global joint continuity, schematic rebar elevation, and station/joint audit tables. Existing workflows, solvers, Project JSON, and result persistence are unchanged.

See `README_CROSSBEAM_RB1.md`.

### CROSSBEAM.UI1 — Segment Layout and Tendon Plan/Profile/3D workspaces

Separates the Portal Frame Prestressed Crossbeam geometry foundation into workflow-scoped `Tendon System`, `Segment Layout`, and `Tendon Profile` subpages while leaving existing workflows on `Section Builder | Rebar | Prestress`.

#### What changed
- Removes the combined crossbeam longitudinal-layout/tendon table from Section Builder.
- Adds a segment elevation with solid/hollow role assignment, station boundaries, Section IDs, segment lengths, and left/right anchorage markers.
- Adds one tendon-system row per tendon for Internal/External type, strand count, Aps/strand, fpu, fpj/fpu, and Left/Right/Both jacking.
- Adds one tendon geometry source for Plan (`s-x`), Profile (`s-dtop`), interactive 3D (`s-x-y`), and a calculated eccentricity audit.
- Keeps cross-section axes `x-y`, adds longitudinal station `s`, and preserves top-referenced `dtop` and centroid-based `e(s)`.
- Uses crossbeam-namespaced Streamlit state with in-session migration from accepted WF1/WF1A seed keys.

#### Not changed
- No prestress-loss, SLS, ULS, shear/torsion, anchorage-zone, deviator-force, D-region, Project JSON schema, solver, or result-persistence changes.
- Railway U-Girder, Bridge/Building Beam-Girder, and Column/Pier Sections navigation remains unchanged.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/crossbeam_pages.py concrete_pmm_pro/ui/section_builder.py
pytest -q tests/test_crossbeam_ui1_workspaces.py tests/test_crossbeam_wf1a_routing_safety.py tests/test_crossbeam_wf1_workflow.py tests/test_reinforcement_system_flags.py tests/test_workflow_status_alignment.py tests/test_preset_routing1_workflow_presets.py tests/test_workflow_type3_shared_section_presets.py tests/test_navigation_workspace.py tests/test_ui_active_tabs1_navigation.py tests/test_app_commercial_tabs.py tests/test_project_io.py tests/test_project_dashboard.py tests/test_section_builder_layout.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_prestress_tendon_products.py tests/test_qa_railway_u_girder_workflow_regression_audit.py tests/test_building_beam_girder_sls_load_workflow.py tests/test_girder_service_workflow.py tests/test_design_code_source_of_truth.py tests/test_design_code_sync3_setup_widget.py
```

Crossbeam UI1 and cross-workflow regression gate: **200 passed**.

### SLS.STAGE.STRESS.QA3A — Streamlit widget-state hotfix

Hotfixes the QA3 staged SLS profile synchronization so read-only summary/detail synchronization never writes back to Streamlit widget-bound keys after the visible guide widgets are instantiated.

#### What changed
- Stops `_girder_sls_normalized_guide_method_from_state()` from assigning to the `Tension reinforcement condition` selectbox session-state key during downstream graph/status rendering.
- Keeps bonded-confirmation checkbox keys read-only inside the summary/detail sync helper; only non-widget traceability source keys may be updated.
- Preserves QA3 behavior: summary tables, detail cards, graphs, Result Summary, and Report / QA continue to use the selected per-stage tensile limit profile.

#### Not changed
- No stress equations, Pe(x), debonding, load routing, geometry, material routing, ULS/SLS calculation kernel, Project JSON behavior, or result-cache persistence changed.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py concrete_pmm_pro/serviceability/girder_code_limits.py concrete_pmm_pro/reporting/traceability.py concrete_pmm_pro/reporting/readiness.py concrete_pmm_pro/reporting/word_export.py
pytest -q tests/test_sls_stage_stress_qa3_profile_sync.py tests/test_sls_stage_stress_qa2_practical_auxiliary_basis.py
pytest -q tests/test_girder_sls_full_length_diagram.py tests/test_railway_u_girder_sls_stage_preview.py tests/test_railway_u_girder_sls_stage_limits.py tests/test_result_summary2_sls_code_integration.py tests/test_report_qa2_unified_readiness.py
```

Targeted SLS staged stress profile-sync, full-length diagram, Railway U-Girder staged SLS, Result Summary, and Report/QA tests passed.

### SLS.RAIL.UGIRDER9 — Lifting a/L and Debonding Audit Table

Adds a read-only audit panel to **Analysis → SLS / Stress & Cracking → Lifting stage** for Railway U-Girder staged stress previews.

#### What changed
- Adds a Railway U-Girder lifting `a/L` + debonding audit table below the lifting stress diagram.
- The audit table reports span-derived lifting point `a`, opposite lifting point `L-a`, support spacing, impact factor, one-web self-weight × impact load, lifting support reaction, two-point lifting moment, effective strand count, Pe_transfer, yps, active strand groups, and audit notes at lifting/debond/station-grid points.
- Uses the same two-point lifting moment model with end overhangs and the same station-based debonded-strand step availability as the stress graph.
- Updates Prestress strand dashboard wording from ambiguous `Bonded strands` / `Debonded strands` to `Fully bonded throughout` / `Debonded near ends`.

#### Not changed
- No SLS stress equations, Pe(x) calculation, load routing, section-basis logic, code-limit formulas, ULS checks, project schema, or report certification wording.
- The debonding handoff remains a step-function preview; transfer/development length, anchorage, and end-zone detailing remain separate engineering review items.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py concrete_pmm_pro/ui/prestress_page.py concrete_pmm_pro/serviceability/railway_u_girder_stages.py
pytest -q tests/test_railway_u_girder_lifting_audit.py tests/test_railway_u_girder_sls_stage_preview.py tests/test_railway_u_girder_sls_stage_limits.py
pytest -q tests/test_result_summary* tests/test_report* tests/test_railway_u_girder_lifting_audit.py
```

Targeted lifting audit, Railway U-Girder staged SLS, Result Summary, and Report/QA tests passed.

### RESULT.SUMMARY3B — Critical Check Ranking and Failure-Action Polish

Polishes the **Result Summary Dashboard** so the Overview and ULS Summary rank and explain failures using the same decision evidence shown in Analysis.

#### What changed
- Critical Check ranking now parses all utilization values in compact strings, so detailing ratios such as `Av/s min D/C 1.893` can govern over a lower SLS stress utilization.
- The Overview Critical Check card now reports the check-level label such as `ULS Shear` instead of only the broad module label.
- Overall FAIL wording now lists the leading failing checks so ULS shear detailing, source-blocked V+T, and SLS preview failures are visible together.
- Source-blocked Beam/Girder Shear + Torsion rows now display `Interaction D/C ...; source gate BLOCKED` so the interaction ratio is not mistaken for an accepted final pass.
- Shear failure actions now name the minimum stirrup/detailing gate and recommend increasing shear reinforcement or reducing stirrup spacing when Av/s minimum controls.

#### Not changed
- No PMM, shear, torsion, SLS stress, prestress, or V+T engineering equations.
- No solver execution from Result Summary; the workspace remains read-only and uses stored Analysis outputs.
- No project schema, load routing, report export, or widget-key contract changes.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_result_summary*.py tests/test_results_ws*.py tests/test_state_persist1_reinforcement_and_results.py
pytest -q tests/test_result_summary1_dashboard.py tests/test_result_summary2_sls_code_integration.py tests/test_result_summary3_decision_polish.py tests/test_result_summary3b_critical_ranking.py tests/test_results_ws2_beam_uls_dashboard.py tests/test_results_ws4_summary_dashboard.py tests/test_aashto_col_vt1.py tests/test_column_pier_vt_report1.py tests/test_valid_column_pier_vt.py
```

Targeted Result Summary and VT/report tests passed.

### UI.COMMERCIAL4.7 — ULS Summary Spacing and Decision Table Polish

Polishes the newly upgraded **Analysis → ULS Strength → Summary** dashboard for better readability and commercial presentation.

#### What changed
- Widens the overall Column/Pier ULS decision card so `REVIEW / incomplete` and similar decisions do not feel cramped.
- Improves the ULS decision table with fixed column proportions, more readable row spacing, and cleaner typography.
- Highlights the `Required Action` column as an action note so the engineer can see the next required step faster.
- Keeps `Route / Scope` as a quieter technical note so it no longer competes visually with the required action.
- Maintains the commercial blue-accent and light-card visual system introduced in UI.COMMERCIAL4.6.

#### Not changed
- No PMM solver equations.
- No shear, torsion, or combined V+T engineering equations.
- No load routing, project schema, save/load contract, report logic, or widget keys.

#### Validation run
```bash
python -m py_compile concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_analysis_modes.py tests/test_app_commercial_tabs.py
```

All targeted tests passed.


## UI.COMMERCIAL4.5 — Soft Metric Cards and Load Workspace Hierarchy Polish

Softened the dashboard summary metric cards so they no longer appear as heavy primary actions. Streamlit `st.metric` cards now use a light blue-tinted card surface with blue accent border/value typography instead of solid blue fills, keeping the Loads workspace and other metric summaries closer to the new commercial dashboard visual system.

This is presentation-only UI polish. It does not change solver equations, SLS/ULS/PMM/prestress/rebar logic, report logic, widget keys, project schema, save/load behavior, or navigation state.

See `docs/design/ui_commercial4_5.md`.

### UI.PLOT5 — Global Plot Readability Polish

### UI.PLOT6 — ULS Torsion Full-Length Capacity Plot Hotfix

- ULS Beam/Girder torsion capacity/threshold traces now extend over the active member station domain when explicit boundary rows are missing or stale.
- This is a display-only plot continuity fix; torsion equations, governing station logic, and combined V+T checks are unchanged.


Added a global Plotly readability layer for all charts rendered through `st.plotly_chart`.  The app now strengthens plot text color, tick labels, axis titles, legend text, hover labels, annotation labels, grid contrast, and 3D scene axis labels across Analysis, Sections, Rebar, Prestress, Reports, and future pages without changing trace data or engineering calculations.

No solver equations, result dataframe values, trace coordinates, data-editor commit logic, widget keys, navigation/page routing, project schema, geometry generator, load routing, prestress/debonding logic, or report certification wording were changed.

See `docs/design/ui_plot5.md`.

### UI.PLOT4 — ULS Shear Diagram and Failure Diagnosis Polish

Added a display-only ULS shear diagnosis layer so the Shear workspace explains why a calculated shear result passes or fails without requiring the engineer to open the raw audit table. The shear cards now include a diagnosis strip with the controlling reason, evidence, and recommended action, such as minimum Av/s failure, maximum spacing failure, strength failure, Vn-limit failure, or layout coverage requirement. The ULS shear plot also uses a more report-style layout with taller plot height, bottom legend spacing, axis labels, and a governing decision marker that reflects the actual decision row.

No shear equation, φVc/φVs/φVn calculation, Av/s minimum equation, spacing limit equation, SLS/ULS solver, data-editor commit logic, widget key, load-combination equation, project schema, geometry generator, prestress/debonding logic, or report certification wording was changed.

See `docs/design/ui_plot4.md`.

### UI.PLOT1 — Engineering Stress Diagram Plot Style

Added a display-only engineering stress diagram style layer for full-length SLS stress plots. The updated plots use report-style title/subtitle typography, stronger top/bottom stress curves, explicit compression/tension limit colors, a visible 0 MPa reference line, bottom legend box, framed axes, and clearer governing tension/compression markers. This milestone applies first to Beam/Girder SLS full-length stress diagrams and Railway U-Girder service multi-fiber stress diagrams.

No stress solver, Pe(x), load, section-basis, code-limit formula, data editor, widget key, project schema, geometry, prestress/debonding, or ULS logic was changed.

See `docs/design/ui_plot1.md`.

### UI.THEME1 — Commercial Engineering Theme Foundation

Added a visual-only commercial engineering theme foundation inspired by the user's preferred dark-navy engineering tool UI. The theme improves the app background, dark navy section/expander bars, sidebar foundation, metric cards, table/editor chrome, plot panels, existing custom cards, alerts, and input borders while preserving the current workspace/page structure.

No solver equations, data-editor commit logic, widget keys, navigation/page routing, project schema, section geometry, prestress/debonding logic, load-combination logic, or report certification wording were changed.

See `docs/design/ui_theme1.md`.

### UI.DATAEDITOR.COMMIT1 — One-Pass Commit for Rebar and Load Input Tables

Fixed first-edit persistence for Streamlit `st.data_editor` inputs that previously could require entering the same value twice before the project/source table retained it.  The fix adds patch-payload reconstruction and `on_change` commit callbacks for Beam/Girder transverse rebar, Column/Pier transverse rebar, Column/Pier ULS/SLS load tables, Beam/Girder ULS load tables, Building Beam/Girder ULS load tables, and Beam/Girder staged SLS load tables.  No solver equations, load-combination equations, shear equations, section properties, or project schema were changed.

### SHEAR.LABEL1 — Clear Shear Detailing D/C Labels

This UI/diagnostic polish replaces opaque compact shear utilization wording such as `0.460 / det 1.893` with explicit labels such as `Strength D/C 0.460; Av/s min D/C 1.893` or `Strength D/C 0.460; Spacing D/C 1.200`.  The parser remains backward compatible with old cached `det` strings, but the compact ULS check table and top governing-shear card no longer expose `det` as the user-facing label.

Changed areas: `concrete_pmm_pro/ui/analysis_page.py`, docs, and regression tests. No shear equation, φVn calculation, minimum Av/s equation, spacing limit equation, flexure/torsion equation, SLS equation, geometry generator, load-combination equation, project schema, or certification wording was changed.

See `docs/design/shear_label1.md`.

### SHEAR.STATUS1 — Beam/Girder ULS Shear Status Propagation Hotfix

This hotfix corrects the Beam/Girder ULS shear compact-table and source-gate status propagation. The earlier SHEAR.GOVERNING1 fix correctly moved the displayed governing shear station to the strength-demand row, but the compact table could still report `Shear = FAIL` when a stale/source row-level `Status` string said `FAIL` even though the explicit displayed gates were clear:

```text
Strength D/C <= 1.0
Detailing D/C <= 1.0
Strength status = PASS
Detailing status = PASS
```

The overall shear status now derives from the explicit strength/detailing/readiness gates instead of trusting the aggregate `Status` string alone. This keeps the compact ULS table, top summary cards, source gate for Shear + Torsion, and the Shear workspace cards consistent. No shear equation, torsion equation, flexure equation, SLS equation, prestress/debonding logic, geometry generator, section properties, load-combination equation, project schema, or UI layout is changed.

See `docs/design/shear_status1.md`.

### SHEAR.GOVERNING1 — Beam/Girder ULS Shear Governing-Station Selection Hotfix

This hotfix corrects the Beam/Girder/Railway U-Girder ULS shear governing-row selection used by the compact ULS table, summary cards, shear chart marker, and shear audit table. The displayed governing shear station now ranks non-boundary rows by strength D/C and absolute Vu, instead of letting a zone-wide detailing D/C failure select an arbitrary low-demand row. Overall shear status still fails when any non-boundary strength/detailing gate fails.

No shear equation, torsion equation, flexure equation, SLS equation, prestress/debonding logic, geometry generator, section properties, load-combination equation, project schema, or UI layout is changed.

See `docs/design/shear_governing1.md`.

### CLOSEOUT.RAIL.UGIRDER1 — Railway U-Girder SLS Engineering Review Closeout

This milestone closes the current Railway U-Girder development slice as a guarded SLS engineering-review package. It adds an explicit closeout status table to the Railway U-Girder report package and Word report section while preserving the non-certification boundary:

```text
Railway U-Girder SLS Engineering Review Package - Closeout Ready
```

Closeout-ready means the accepted Railway U-Girder SLS preview workflow is report-ready with regression evidence, not that the workflow is a final design certification. Transfer/development length, anchorage/end-zone bursting, lifting hardware, creep/shrinkage redistribution, ULS Railway U-Girder coupling, and final certification checks remain future work.

See `docs/design/closeout_rail_ugirder1.md`.

### REBAR.RAIL.UGIRDER1 — Railway U-Girder Ordinary Rebar Enable Routing Hotfix

This hotfix resolves a Railway U-Girder ordinary-rebar workflow issue where `Include ordinary rebar / longitudinal Al` could be enabled in Section Builder but the Rebar workspace could still remain in the disabled stored-preview state. Section Builder now synchronizes the steel-system checkbox state to project metadata on change, and the Longitudinal Rebar tab includes an in-page recovery action to enable ordinary rebar / longitudinal Al and open the editable input table on rerun.

No solver equations, SLS/ULS calculations, prestress/debonding logic, geometry generation, project schema, or certification wording are changed.

See `docs/design/rebar_rail_ugirder1.md`.


### QA.RAIL.UGIRDER1 — Railway U-Girder Workflow Regression Audit

This milestone stabilizes the accepted `SLS.RAIL.UGIRDER8.RECOVERY` baseline before new feature work. It adds regression coverage for Railway U-Girder save/load preservation, symmetric debond station participation, stage material-strength routing, and guarded engineering-review wording. No solver equations, section properties, Pe/debond participation logic, ULS, anchorage, transfer-length, development-length, or report logic are changed.

See `docs/design/qa_rail_ugirder1.md`.

### SLS.RAIL.UGIRDER8.RECOVERY — Multi-Fiber Service Plot Rebased on Correct Latest Baseline

This recovery package fixes the earlier SLS.RAIL.UGIRDER8 packaging mistake by rebasing the Railway U-Girder service multi-fiber stress plot onto the latest accepted baseline that already includes:

- SLS.MATERIAL.ROUTING4 canonical transfer-stage strength routing.
- SLS.RAIL.UGIRDER7 dedicated Lifting stage tab.
- SLS.TENSION.DEFAULT1 verified bonded tension reinforcement default.

The Railway U-Girder Service stage SLS plot now samples the existing full gross U-section elastic stress field at:

- Top web fiber.
- Bottom web fiber.
- CIP slab top fiber.
- CIP slab bottom fiber.

The graph labels the web and slab stress limits directly on the limit lines so the web f'c and CIP slab f'c bases are not confused. This milestone is UI/plot routing only and does not change stress equations, section properties, Pe/debond logic, ULS, anchorage, transfer length, development length, or report logic.

Validation performed from packaged working tree:

```bash
python -m compileall -q app.py concrete_pmm_pro tests
pytest -q \
  tests/test_railway_u_girder_service_multifiber_plot.py \
  tests/test_girder_sls_full_length_diagram.py \
  tests/test_sls_material_routing1_stage_strength.py \
  tests/test_railway_u_girder_sls_lifting_stage_tab.py \
  tests/test_railway_u_girder_sls_decision_summary.py \
  tests/test_railway_u_girder_sls_final_accumulation.py \
  tests/test_railway_u_girder_sls_service_load_handoff.py \
  tests/test_railway_u_girder_sls_locked_in.py \
  tests/test_railway_u_girder_sls_stage_limits.py \
  tests/test_railway_u_girder_sls_stage_preview.py \
  tests/test_girder_prestress_station.py \
  tests/test_girder_strand_debonding_ui.py \
  tests/test_railway_u_girder_prestress_layout.py \
  tests/test_railway_u_girder_stage_model.py \
  tests/test_girder_code_limit_analysis_preview.py \
  tests/test_project_io.py \
  tests/test_analysis_modes.py \
  tests/test_app_commercial_tabs.py \
  tests/test_ui_keys1_widget_keys.py \
  tests/test_file_uploader_clear_button_css.py \
  tests/test_rebar_compact_workspace.py \
  tests/test_rebar_inclusion_visual_regression.py \
  tests/test_reinforcement_system_flags.py \
  tests/test_prestress_preview_policy.py
```

Result: `244 passed in 11.35s`.

### SHEAR.TRACE1

- Added traceable Beam/Girder ULS shear compact-table source selection.
- The compact shear status and displayed shear row now come from the same decision source.
- Prevents a misleading table row such as `Shear = FAIL` while displaying a passing D/C row.
- No shear equations, SLS equations, geometry, prestress, or project schema were changed.

## Latest milestone

### SLS.RAIL.UGIRDER7 — Dedicated Railway U-Girder lifting stage tab
- Adds a Railway-only `Lifting stage` tab to the Beam/Girder SLS stress workspace.
- The lifting preview uses one precast web, Pe_transfer, station-based debond participation, two-point lifting moment, a/L from stage settings, and the lifting impact factor.
- Lifting limit guidance routes to web f'ci, not final web f'c.
- Other Beam/Girder workflows keep the existing Transfer / Construction / Service tabs.
- No ULS, anchorage, transfer/development length, lifting-insert, geometry, or report logic changes.


### SLS.MATERIAL.ROUTING4 — Canonical Transfer Stage Strength Hotfix

- Fixed the actual remaining visible Transfer-stage tensile-guide bug: canonical code-limit labels such as `Transfer / Release` now route directly to the stage material source instead of being remapped to `User-defined` and falling through to service `f'c`.
- Railway U-Girder visible Transfer guide now uses `web f'ci = 36 MPa` when staged settings define `web_fc_MPa = 45`, `web_fci_MPa = 36`, and `slab_fc_MPa = 35`.
- Added regression coverage for the visible-guide path that passes the canonical `Transfer / Release` label.
- No solver, geometry, PMM, ULS, prestress-loss, report, or project-schema calculation changes.


### SLS.MATERIAL.ROUTING3 — Visible Transfer Guide Stage-Strength Hotfix

- Fixed the remaining visible SLS tensile guide route that could still show final concrete `f'c` as transfer `f'ci` for Railway U-Girder after Analysis reruns or stale selector paths.
- Broadened Railway U-Girder detection from section parameters and geometry metadata parameters.
- Made the visible tensile guide consume the same stage-routed material-strength helper as the diagram controls.
- Added regression tests for stale generic selector + stale generic transfer `fci = f'c` conditions.
- No solver, geometry, ULS, prestress-loss, report, or project-schema calculation changes.


### SLS.RAIL.UGIRDER3 — Locked-In Staged Stress Accumulation Handoff

- Adds a guarded Railway U-Girder locked-in staged stress accumulation handoff under Prestress → Rail U-Girder stages.
- Transfer locked-in stress uses one precast web with web self-weight plus `Pe_transfer`.
- Wet slab casting locked-in stress adds the wet slab/formwork increment plus `(Pe_construction - Pe_transfer)` on the one-web basis.
- Final service Pe is reported as a full-U section handoff increment `(Pe_final - Pe_construction)` and is not algebraically summed with web-locked fibers.
- Service loads, transfer-length ramping, development length, anchorage/end-zone bursting, creep/shrinkage redistribution, ULS coupling, and final code-certified checks remain guarded future scope.


### SLS.RAIL.UGIRDER2 — Stage Stress-Limit Preview

- Adds guarded stage-aware stress-limit checks to the Railway U-Girder staged SLS preview.
- Transfer and lifting limit checks use one precast web and `f'ci(web)`.
- Wet slab casting limit checks use one precast web and `f'c(web)`.
- The full-U service row remains a Pe-only reference and uses `min(f'c web, f'c slab)` as a conservative preview strength until locked-in service-load superposition is finalized.
- No solver-equation, geometry, PMM, shear/torsion, load-import, rebar, prestress-loss, report, or project-schema calculation changes.

- PRESTRESS.DEBOND.ANALYSIS1: adds an explicit station-based debonded-strand participation handoff for girder strand layouts. The new row-level station table derives effective strand count, Aps, transfer/construction/final Pe, and yps from Left/Right debond length plus Debonded strand nos, and is surfaced under Prestress → Effective prestress preview. This is a guarded step-function participation model only; no transfer-length ramp, development/anchorage check, final code-certified debonding check, or SLS/ULS stress-equation change is included.
- PRESTRESS.DEBOND.VIEW3: cleans up Railway U-Girder debonding UI by auto-mirroring L-row debond metadata to matching R rows in symmetric left/right mode and by simplifying the Debonding along span left-side row labels into single-line, non-overlapping text. The editable source remains Left/Right debond length plus Debonded strand nos; no solver, Pe/loss, station-effective prestress, SLS/ULS, geometry, section-property, report, or project-schema equation changes.
- PRESTRESS.DEBOND.VIEW1: replaces the Debonding along span line chart with an elevation-style debonding schematic and row summary. Railway U-Girder shows one representative web by default for symmetric left/right layouts, labels debonded strand counts per row, and uses the approved default debond length rule `max(0, L/5 - 0.5 m × (row - 1))` when debonded strand numbers are selected with zero entered length. This remains detailing/preview metadata only; no solver, Pe/loss, effective prestress, PMM, SLS, geometry, report, or project-schema equation changes.
- SECTION.BUILDER.FOCUS1: declutters the Section Builder definition panel by removing the collapsed `Project / workflow / axis details` and `Browse by geometry family` helpers, and by showing `Concrete Material Assignment` plus `Section / Member Assembly` as visible section-specific decision panels. No solver, geometry generator, section-property, rebar, prestress, load, SLS/ULS, report, or project-schema calculation logic changes.
- SECTION.ASSEMBLY1: moves Beam/Girder system inputs out of Setup and into Section Builder as workflow-specific section assembly controls. Bridge workflow now shows `Bridge Section Assembly`; Building workflow shows `Building Member Assembly`. The settings still persist under the existing beam/girder metadata key for save/load and downstream Loads/Prestress/SLS consumers, but Setup is limited to project, workflow, and design-code decisions. No solver, geometry generator, prestress loss, rebar force, PMM, SLS, load calculation, report, or project-schema equation changes.
- PRESET.LABEL1: hotfixes workflow-specific Section Builder preset selector labels so aliases that already include their category, such as `Precast I-Girder: Bridge · Precast Composite Girder`, are not displayed with a duplicated trailing `· Precast Composite Girder`. No preset routing metadata, geometry generator, solver, PMM, SLS, prestress, rebar, report, or project calculation logic changes.
- PRESET.ROUTING1: adds explicit `allowed_workflows` metadata to section presets so Building Beam/Girder hides bridge/railway/highway-only presets such as Slab Bridge and Railway U-Girder, while Bridge Beam/Girder keeps infrastructure presets visible. The shared Precast I-Girder keeps its stable `parametric_i_girder` key/geometry generator but now displays workflow-specific labels: `Precast I-Girder: Building · Precast Composite Girder` or `Precast I-Girder: Bridge · Precast Composite Girder`. No solver, geometry-generator, PMM, SLS, prestress, rebar, load, report, or project calculation logic changes.
- MATERIAL.ROUTING1: makes Setup → Materials library-only for concrete/rebar/prestress definitions, moves section concrete assignment responsibility to Section Builder, adds Railway U-Girder web/slab/f'ci material assignment sync into staged metadata, enforces standard DB rebar material/fy by Bar Size (DB10–DB28 = SD40, DB32 = SD50), and keeps prestress Product as the source of truth for Area/fpy/fpu/Ep. No PMM, SLS, Pe/loss, shear/torsion, geometry, report, or force-equation changes.
- STAGE.RAIL.UGIRDER1: adds a Railway U-Girder staged-construction model/UI for the prestressed through U-girder workflow. The new Rail U-Girder stages tab captures web f'c/f'ci, slab f'c, ACI auto Ec display, concrete unit weight, Case B wet-slab load carried 50/50 by the precast webs, 2.5 kN/m² formwork load, 10.0 m default span, two-point lifting at 0.20L, and 1.10 lifting impact factor. It also summarizes Transfer, Lifting, Wet slab casting, Composite construction, and Service section bases without changing stress solvers, Pe/loss logic, PMM, SLS, report, or project schema beyond settings persistence.
- PRESTRESS.RAIL.UGIRDER2: corrects the Railway U-Girder default top strand row pattern so Row 5 uses drawing grid columns 3, 4, 6, and 7 on both left and right side blocks. The total 72-strand layout, strand product metadata, debond symbol metadata, force/loss logic, solver behavior, geometry, report, and project schema are unchanged.
- PRESTRESS.RAIL.UGIRDER1: adds Railway U-Girder default strand layout and drawing debond symbol metadata. The preset now seeds 72 strands (36 per side) using 12.7 mm ASTM A416 Grade 270 low-relaxation strands with five rows at 95/150/205/260/315 mm from the bottom. Debond pattern symbols (0/1000/2000/3000/4000/5000 mm) are preview metadata only and do not change station-based analysis yet. No solver, SLS, PMM, shear/torsion, geometry, rebar, report, or project schema changes.
- SECTION.RAIL.UGIRDER3: polishes the Railway U-Girder input wording and dimension labels by renaming h1 to `Step from bottom`, h2 to `Bottom recess`, and separating hx/hy annotations onto opposite haunches to avoid label overlap. No concrete polygon, solver, rebar, prestress, SLS, shear/torsion, report, or schema changes.
- SECTION.RAIL.UGIRDER2: refines the Railway U-Girder preset with editable Haunch X/Y and h1-h4 drawing controls (h1 step height, h2 bottom opening, h3 side floor thickness, h4 center floor thickness) while keeping the 50 mm exterior notch derived and six 25 mm chamfers fixed drawing details. No solver, rebar, prestress, SLS, shear/torsion, report, or schema changes.
- SECTION.RAIL.UGIRDER1: adds a Bridge Beam/Girder Railway U-Girder non-composite through-trough preset from the provided railway section drawing defaults (B=5500 mm, H=1600 mm, top wall 600 mm, bottom side block 650 mm, inner haunch 300 x 300 mm, floor thickness 395/450 mm) with derived 50 mm exterior notches and six fixed 25 mm chamfers. No solver, rebar, prestress, SLS, shear/torsion, report, or schema changes.
- UPLOAD.FILEUPLOADER.CLEAR1: narrows Streamlit file-uploader action CSS to the dropzone Browse button only so uploaded-file pill remove (x) controls keep native click behavior. No load parser, session-state, solver, geometry, SLS, shear/torsion, report, or schema changes.
- SECTION.SLAB.BRIDGE1: adds a Bridge Beam/Girder Slab Bridge preset from the provided drawing defaults (B=5100 mm, B/2=2550 mm, edge depth 400 mm, centerline depth 450 mm) as a solid crowned non-composite slab polygon with dimension guides and geometry regression tests. No solver, rebar, prestress, SLS, shear/torsion, report, or schema changes.
- UI.REBAR.COMPACT1: polishes the Rebar workspace into a compact commercial decision layout with panel titles, active/excluded participation cards, collapsed detail tables, and lower preview heights. No solver, geometry, SLS, shear/torsion, report, or schema changes.
- UI.REBAR.INCLUSION4: adds a focused regression gate for Column/Pier, Bridge Beam/Girder, and Building Beam/Girder ordinary-rebar inclusion visual/state behavior; stored excluded rows stay preserved but publish zero active analysis rebars unless explicitly enabled. No solver, geometry, SLS, shear/torsion, report, or schema changes.
- UI.REBAR.INCLUSION2: Rebar page now reads section-level ordinary-rebar inclusion from top-level session state or project metadata, preserves stored rows while publishing zero active analysis rebars when disabled, and labels stored/excluded bars clearly for Beam/Girder workflows.
- UI.PMM.NAV2: Flexural PMM result-view tabs (`Summary`, `PMM Check`, `3D Interaction`, `SLS`, `Diagnostics / QA`) are now rendered immediately under the Flexural (PMM) workspace after run/cache controls, before lower method QA and stored snapshot expanders; no solver or demand/capacity logic changed.
- UI.ANALYSIS.NAV1: Analysis subpage label now reads `ULS Strength`, and the Column/Pier ULS Strength Check selector is shown directly under that subpage before the decision/result panels; no solver or demand/capacity logic changed.
- UI.PMM.COMPACT1: Flexural PMM decision-first compact workspace; advanced setup, input overview, method notes, stored snapshot, and diagnostics are collapsed so the PMM visual decision review appears earlier without changing solver equations.
- UI.ACTION.BUTTONS2: highlighted action buttons now respect enabled/disabled state; Flexural PMM runtime controls use compact status cards without changing solver logic.
- UI.ACTIVE.TABS3: navigation density polish; deterministic tab clusters are tighter, working-screen vertical spacing is reduced, and active-tab highlight is lighter while preserving existing tab positions and options.
- UI.ACTIVE.TABS2: compact commercial active tab bar; deterministic app-owned navigation now stays left-aligned and detail `st.tabs` use dark-blue active styling.
# Concrete Section Pro

- UI.PMM.NAV3: Move PMM result-view tabs immediately under Flexural (PMM); run/cache and diagnostics remain below.

## Current Baseline Note — UI.COMMERCIAL.TABS4

This repository has advanced beyond the older README milestone history below. `APP.BRAND1` renames the visible application/report brand to **Concrete Section Pro** and relaxes compact-header CSS so the product title no longer clips at the top of the working screen. The current uploaded baseline is `Concrete-Section-Check-V6`, stabilized by `QA.BASELINE1`, `WORKFLOW.STATUS1`, `STATUS.COLPIER1`, `STATUS.COLPIER2`, `STATE.SECTION1`, `STATE.RESULT1`, `STATE.RESULT2`, `STATE.RESULT3`, and `STATE.RESULT4`; subsequent section geometry milestones and `QA.CODE.AUDIT1` add filleted/chamfered hollow section benchmarks plus a Streamlit duplicate download-key hotfix. `UI.KEYS1` hardens all app/UI `st.button()` and `st.download_button()` call sites with explicit unique keys to reduce duplicate-element regressions. `UI.COMMERCIAL.TABS4` adds a clear dark-blue active-tab highlight for the existing navigation controls. `UI.COMMERCIAL.SECTION1` added a commercial-style Section Builder header, panel titles, and preview-canvas polish without changing solver, geometry, or project schema behavior. The current architecture includes Column/Pier/Wall/Pylon flexural PMM production-preview readiness evidence, ACI RC nonprestressed Column/Pier shear/torsion/V+T scoped PASS/FAIL gates, guarded Beam/Girder ULS flexure/shear/torsion preview routing, staged Beam/Girder SLS stress workflows, SLS deflection/camber preview, validation packs, and Word report QA. `UI.COMMERCIAL.TABS1` removes the extra nested Section Builder workflow bar and applies visual-only commercial styling to existing app tabs without navigation changes. `UI.COMMERCIAL.TABS2` strengthens existing tab, button, and user-input label typography with bold dark-blue text and slightly larger tab/button sizing without adding or moving controls. `UI.COMMERCIAL.TABS3` broadens the selector coverage to the current Streamlit `stButtonGroup` DOM used by the visible segmented navigation, so the Workspace and subpage tabs actually receive the commercial typography. `UI.ACTIVE.TABS1` replaces fragile selected-state CSS with deterministic app-owned active-tab rendering, `UI.ACTIVE.TABS2` makes the tab cluster compact and left-aligned, and `UI.ACTIVE.TABS3` further tightens the navigation density and working-screen vertical spacing. `UI.PMM.COMPACT1` makes the Flexural (PMM) workspace decision-first by collapsing setup/readiness/input overview/method notes/stored snapshots behind expanders and moving PMM Visual Review ahead of detailed cache/trace outputs.

`QA.BASELINE1` does not change solver equations, PMM demand/capacity logic, prestress `Pe_eff` behavior, shear/torsion formulas, service-stress formulas, deflection formulas, or report calculation logic. It only aligns stale tests/docs and adds a pytest-only Streamlit fallback for environments without the UI runtime installed.

Column/Pier ACI RC nonprestressed shear, torsion, and V+T detail tabs now align with the ULS Decision Summary and can issue scoped `PASS`/`FAIL` when the implemented gates are complete. `STATUS.COLPIER2` fixes the Streamlit render-order issue where the visually top decision summary could read stale PMM demand/capacity state and show `NOT READY` on the same rerun that successfully calculated Flexural (PMM). AASHTO LRFD, active prestress in V/T, seismic special detailing, anchorage/hooks, lap splices, shop-drawing detailing, and final code-certified project claims remain explicitly guarded. `STATE.SECTION1` fixes Section Builder widget-state restoration after inactive workspaces are skipped: user-edited geometry and composite metadata now restore from durable `section_parameters` instead of resetting to preset defaults when returning from Setup/Loads/Analysis. `STATE.RESULT1` persists valid Flexural (PMM) result cache and D/C summary metadata in saved project JSON, restores them only when their engineering input hash still matches the loaded project, and clarifies that normal Streamlit page rerenders are not solver reruns. `STATE.RESULT2` added PMM display-artifact caching and an explicit detailed-dashboard render gate. `STATE.RESULT3` restores the main PMM Visual Review, PMM Check, and 3D Interaction tabs so the PMM/3D graphics remain discoverable after a successful run; only legacy raw point-cloud plots and raw PMM tables remain behind an advanced rendering toggle. `STATE.RESULT4` hotfixes the duplicate Streamlit download-button element ID caused when the stored result snapshot and dashboard Summary tab both render the ULS D/C trace CSV export in one rerun. `SECTION.PROPERTY.BENCHMARK1` adds executable section-property benchmarks for the filleted/chamfered hollow presets, including closed-form rectangular hollow zero-feature checks, analytical area checks, and centroid-direction sanity checks.

### WORKFLOW.STATUS1 — Workflow Capability Wording Alignment

The clean repo baseline now aligns Setup, Analysis, Project Design Code capability guards, and draft report wording with the current implemented Beam/Girder guarded preview capabilities. Bridge/Building Beam-Girder flexure, SHEAR.CODE2, TORSION.CODE2, combined V+T, staged SLS stress, deflection/camber, prestress, and debonding tools are described as preview / engineering-review workflows only. Column/Pier AASHTO PMM remains planned / REVIEW, and final code-certified girder design remains outside current scope.

See `docs/design/qa_baseline1.md`, `docs/design/workflow_status1.md`, `docs/design/status_colpier1.md`, `docs/design/status_colpier2.md`, `docs/design/state_section1.md`, `docs/design/state_result1.md`, `docs/design/state_result2.md`, `docs/design/state_result3.md`, `docs/design/state_result4.md`, and `docs/design/section_property_benchmark1.md`, and `docs/design/ui_keys1.md`, `docs/design/ui_commercial_section1.md` for milestone scope and QA gate notes.


## Milestone QA.PO1 Scope

- Adds an executable prestress-aware axial cap validation pack.
- Checks RC-only, PS-only, and RC + bonded prestress nominal `Po` against independent formulas.
- Confirms `Po` subtracts `Ast` and `Aps` once from concrete compression and adds `fy*Ast` plus `fpy*Aps` or `0.90fpu*Aps`.
- Confirms `Pe_eff` and product breaking-load metadata are not used in nominal axial strength.
- Confirms prestress `count` multiplies element area once and unbonded prestress is excluded upstream before the axial-cap helper is called.
- Confirms tied-column `phiPn,max` cap uses `0.80 * phi * Po`.
- Existing PMM solver, D/C extraction, prestress stress model, warning display, load import, and report export behavior are unchanged.

# Concrete PMM Pro

Professional Streamlit engineering application foundation for reinforced concrete and prestressed concrete PMM analysis.

This repository is at Milestone PS.DB1.2 plus P.1.1, V.PS1.1 visualization cleanup, and R.FIG.1.1 figure-export deployment hotfix. The PMM solver and ULS demand/capacity workflow are still prototypes. The app navigation is grouped into engineering workspaces, and the Analysis workspace has real subtabs for ULS Strength, SLS / Stress & Cracking, and Report / QA. Analysis now includes runtime controls, stable engineering-input hashes, cache status indicators, and lightweight timing diagnostics around expensive UI-triggered operations. Existing Project, Materials, Section Builder, Rebar, Prestress, Loads, PMM, SLS, cracking, report export, and report QA tools remain reachable without changing calculation logic. Bonded prestress contribution is included in the PMM prototype with refined prestressing steel stress-strain models, ordinary rebar displaced-concrete refinement, independent hand-calculation spot checks, engineering verification safeguards, benchmark-style solver checks, refined PMM slice interpolation, slice envelope robustness checks, clearer warning/reporting text, numerical cleanup, elastic SLS stress checks using either gross or uncracked transformed section properties, optional effective bonded prestress contribution, no-tension/decompression serviceability judgement, SLS stress sign benchmark checks, cracking/tension-zone classification from existing SLS stress results, custom SLS stress check points with geometry validation, SLS stress visualization on the section, context-aware engineering limitation filtering, report manifest JSON, draft Word report export, and Word report QA; unbonded prestress, full cracked-section stress redistribution, crack-width checks, Beam/Girder flexure/shear/torsion checks, PDF export, and production-grade design certification are intentionally not implemented yet.



## Current Validation Direction

Latest validation milestones add a traceable path from prototype PMM results toward commercial-grade engineering QA:

- `QA.VALIDATION1` establishes the validation matrix and report runner.
- `VALID.RC1` adds rectangular RC axial/bending/symmetry benchmark checks.
- `VALID.RC2` adds ACI-style phi transition and tension-control benchmark checks.
- `VALID.PS1` adds bonded-prestress PS-only and RC+PS benchmark checks for `eps_t`, `Pe_eff/fpe`, `Po + Aps`, stress-warning metadata, and RC+PS numeric schema.
- `VALID.PS2` adds prestress stress-state governing-region checks so fpu-cap and compression-reversal warnings can be classified as governing-related or background PMM-surface events.
- `SOLVER.PS.PASSIVE1` separates Pe_eff=0/fpe=0 passive PT bars/strands from active prestress, so passive high-strength steel contributes to PMM strength without active-prestress fpu-cap or compression-reversal warnings.
- `SOLVER.PS.STRESS1` treats active-prestress fpu-cap events as PMM stress-state metadata rather than standalone global warnings, with escalation reserved for governing-region impact.

These validation packs do not hide solver warnings.  They provide the evidence needed to later downgrade prototype wording into documented method notes or keep true governing-impact warnings visible.


## Milestone SOLVER.PS.STRESS1 Scope

- Keeps active-prestress fpu-cap events in PMM point metadata for QA and governing-region checks.
- Stops promoting background fpu-cap events from ultimate PMM surface generation into standalone engineering warnings.
- Keeps active-prestress compression-reversal and fallback warnings as engineering-review items.
- Updates warning guidance so fpu-cap events are usually QA/numerical notes unless governing-impact classification escalates them.
- Does not change PMM force equilibrium, material stress calculation, D/C equations, load import, report export, or prestress input behavior.

## Milestone SOLVER.PS.PASSIVE1 Scope

- Separates passive prestressing-steel rows from active prestress rows.
- Treats rows with Pe_eff/fpe/initial strain equal to zero as bonded high-strength passive steel.
- Keeps passive PS bars/strands in strain compatibility and phi eps_t tracking.
- Prevents passive rows from emitting active-prestress compression-reversal or fpu-cap warnings.
- Adds passive-PS benchmark checks and regression tests.
- Does not remove active-prestress warnings for rows with nonzero Pe_eff/fpe/initial strain.

## Milestone VALID.PS2 Scope

- Adds prestress stress-state governing-region benchmark pack.
- Adds per-PMM-point compression-reversal metadata alongside existing fpu-cap metadata.
- Checks that fpu-cap events can be separated into global PMM-surface events and events near the governing Pu region.
- Checks that compression-reversal events are traceable by PMM region for later warning-policy refinement.
- Does not change PMM solver equations, D/C equations, load import, report export, or prestress input behavior.

## Milestone VALID.RC2 Scope

- Adds RC phi transition / tension-control benchmark pack.
- Directly checks tied-column ACI-style phi behavior for compression-controlled, transition, tension-controlled, and no-tensile-strain cases.
- Verifies the rectangular RC PMM sweep samples all phi regions.
- Verifies every RC PMM point phi value and strain-condition label matches the independent phi helper.
- Does not change solver equations, PMM D/C logic, prestress behavior, load import, report export, or UI warning display.

## Milestone QA.VALIDATION1 Scope

- Added a formal PMM solver validation framework instead of relying on UI warning cleanup.
- Added `concrete_pmm_pro/verification/validation_framework.py` with a validation matrix covering RC-only PMM, prestress PMM, demand/capacity interpolation, numerical robustness, and warning policy.
- Added validation tests that confirm solver warning families are tied to root-cause validation items rather than being hidden from the user.
- Added `docs/validation/pmm_solver_validation.md` to document the path from prototype warnings toward benchmark-supported commercial-grade behavior.
- Existing PMM solver equations, D/C logic, prestress stress model, load import, report export, and UI result values are unchanged.

## Internal Units

- Length: mm
- Stress: MPa
- Force: N
- Moment: N-mm

## Milestone PS.DB1 Scope

- Added an explicit 15.2 mm strand tendon product database for standard products including `6-1`, `6-7`, `6-12`, `6-19`, and `6-55`.
- Tendon product records include strand count, strand diameter, strand steel area, tendon steel area, nominal breaking load, fpu, duct type, duct ID reference, and typical use where available.
- Added custom tendon generation by strand count, such as `6-25`, using default 15.2 mm strands, 140 mm2 per strand, 1860 MPa fpu, and 260 kN breaking load per strand.
- The Prestress tab can append standard or custom tendon products to the manual table while preserving existing manual/custom prestress entry behavior.
- Product selection sets `Area_mm2` to total tendon steel area, leaves `Diameter_mm` blank for tendon groups, and keeps effective prestress `Pe_eff_kN` / `fpe_MPa` user-controlled.
- Breaking load and duct information are shown as reference metadata only and are not treated as effective prestress or steel diameter.
- Section preview remains V.PS1.1 true-scale circular steel area based on tendon steel area, not duct diameter.
- Section Builder geometry parameters remain inside Sections -> Section Builder, not in `st.sidebar`.
- Existing PMM/SLS solver formulas, prestress sign convention, D/C algorithm, runtime cache logic, report export, report QA, and engineering limitations are unchanged.

## Milestone PS.DB1.1 Scope

- Simplified tendon product creation to two modes: Standard tendon product and Custom tendon.
- Manual prestress editing remains available in the Advanced Prestress Table instead of as a separate product creation mode.
- Product dropdown options include standard tendon products, prestress database products, and custom labels already present in the current table.
- Project save/load preserves or safely reconstructs tendon product metadata such as strand count, breaking-load reference, duct type, and duct ID.
- Product breaking load remains reference-only, `Count` remains the number of identical tendon elements, and `Strand Count` remains product metadata.

## Milestone PS.DB1.2 Scope

- Standard and custom 15.2 mm tendon products now populate `fpy_MPa = 1580`, `fpu_MPa = 1860`, and `Ep_MPa = 195000`.
- Tendon group `Diameter_mm` is normalized to blank/null because tendon groups are governed by total steel area, not a single steel diameter.
- Added display-only `Eq Steel Dia_mm` based on `sqrt(4A/pi)` for tendon group preview/readability; it is not stored as engineering diameter.
- Project save/load reconstructs missing tendon material defaults for clear 15.2 mm tendon group rows without inventing duct data.
- Duct ID remains reference-only and is not used as steel diameter or true-scale display diameter.

## Milestone V.PS1.1 Scope

- Section preview prestress, PT bar, and tendon group steel areas are drawn as Plotly circle shapes in section coordinate units.
- True-scale circle bounds use `x0/x1/y0/y1` from element coordinates and radius = display steel diameter / 2.
- Display steel diameter uses nominal steel diameter for single strand/PT bar when available, or equivalent steel-area diameter from `sqrt(4A/pi)`.
- Tendon group display diameter uses total steel area equivalent diameter and does not use duct or pipe diameter.
- Small circular scatter markers remain only for hover text and legend entries.
- Existing PMM/SLS solver formulas, prestress sign convention, D/C algorithm, material models, load interpretation, report export, report QA, and engineering limitations are unchanged.

## Milestone V.PS1 Scope

- Section preview prestress markers now use circular markers for strand, tendon, wire, PT bar, and custom prestress steel.
- Rebar remains circular and keeps its existing visual style.
- Prestressing strand/tendon and PT bars are distinguished by color and legend group instead of marker shape.
- Prestress marker sizing is based on nominal steel diameter when available for single steel elements, or equivalent steel-area diameter when diameter is unavailable.
- Tendon group preview diameter is based on total steel area equivalent diameter, not a duct or pipe diameter.
- Hover text shows true nominal diameter, display steel diameter, display basis, per-element steel area, total steel area, Pe_eff, and bonded status.
- Existing PMM/SLS solver formulas, prestress sign convention, D/C algorithm, material models, load interpretation, report export, report QA, and engineering limitations are unchanged.

## Milestone P.1.1 Scope

- Demand/capacity summary caching now uses a dedicated D/C input hash instead of reusing only the PMM result hash.
- The D/C hash combines the PMM result/input hash with active ULS demand case data used by the prototype D/C check.
- D/C cache reuse is invalidated when active ULS `Pu`, `Mux`, `Muy`, load activity, or the PMM result hash changes.
- UI-only load-case notes remain excluded from the D/C cache hash.
- Existing session-state cache keys are preserved where possible while also storing the dedicated D/C input hash.
- Existing PMM/SLS solver formulas, prestress sign convention, D/C algorithm, material models, load interpretation, report export, report QA, and engineering limitations are unchanged.

## Milestone R.FIG.1.1 Scope

- Plotly is constrained to `plotly>=5.22,<6` and Kaleido is pinned to `kaleido==0.2.1` for deployment-friendly Plotly PNG export compatibility with Plotly 5.x environments.
- Draft Word reports continue to embed export-ready Plotly figures as PNG images when local static image export succeeds.
- If PNG export fails, the Word report still generates with the existing figure placeholder and Kaleido/detail warning.
- HTML export fallback remains available.
- Report export still uses stored results and does not rerun solvers.
- Existing PMM/SLS solver formulas, sign conventions, D/C logic, report QA, warning propagation, and engineering limitations are unchanged.

## Milestone R.FIG.1 Scope

- Plotly static PNG export for Word report figures now depends on `kaleido>=1.1`.
- Draft Word reports embed export-ready Plotly figures as PNG images when the local Kaleido/Chrome backend can render them.
- PMM interaction surface figure export uses an existing stored dashboard figure and does not rerun the PMM solver.
- If PNG export fails, the Word report still generates with the existing figure placeholder and Kaleido/detail warning.
- Existing PMM/SLS solver formulas, sign conventions, D/C logic, report QA, warning propagation, and engineering limitations are unchanged.

## Milestone P.1 Scope

- ULS Strength includes an `Analysis Runtime Control` panel with Fast, Standard, and High Accuracy presets.
- Fast, Standard, and High Accuracy wire to existing neutral-axis angle/depth resolution controls; Standard matches the previous default resolution.
- PMM analysis uses a stable engineering-input hash and reuses cached PMM results when the hash is unchanged.
- Hash inputs include section geometry, holes, materials, rebar, prestress/PT bar data, bonded/unbonded flags, effective prestress values, load cases, relevant analysis settings, and the selected accuracy preset.
- Hash inputs intentionally exclude UI-only notes, labels, generated prestress ids, section metadata, selected tabs, report preview options, and plot display state.
- D/C summaries are cached against the PMM result hash to avoid silent recomputation on UI reruns.
- SLS stress checks store a serviceability input hash and can reuse cached SLS results when serviceability inputs are unchanged.
- Runtime diagnostics record elapsed time for PMM interaction generation, D/C evaluation, SLS stress calculation, PMM/SLS figure generation, and Word/report export.
- Stale PMM/SLS results are warned when engineering inputs change after the last run.
- Existing PMM/SLS formulas, prestress sign convention, D/C algorithm, report export/QA logic, engineering limitations, warning propagation, materials, loads, and result values for the same settings are unchanged.

## Milestone UI.1 Scope

- Analysis now has real subtabs: ULS Strength, SLS / Stress & Cracking, and Report / QA.
- ULS Strength contains the existing analysis mode controls, analysis settings, readiness panel, PMM run workflow, PMM plots, D/C output, PMM warnings, and PMM verification/hand checks.
- SLS / Stress & Cracking contains the existing serviceability settings, transformed/gross SLS stress check, custom stress points, no-tension/decompression checks, cracking classification, SLS visualization, and SLS benchmark checks.
- Report / QA contains the existing pre-report traceability, readiness, engineering warnings, limitations, report manifest, figure export registry, draft Word export, and Word report QA tools.
- Results remains a future workspace placeholder only.
- Existing PMM/SLS calculations, prestress sign convention, D/C algorithm, report export/QA logic, engineering limitations, warning propagation, materials, loads, and session state data are unchanged.

## Milestone UI.A0 Scope

- Top-level navigation is grouped into Setup, Sections, Loads, Analysis, and Results.
- Setup contains Project and Materials.
- Sections contains Section Builder, Rebar, and Prestress.
- Loads contains the existing Loads workspace.
- Analysis contains subtabs for ULS Strength, SLS / Stress & Cracking, and Report / QA.
- The existing mixed Analysis workspace is preserved intact under ULS Strength for this UI-only milestone.
- SLS / Stress & Cracking and Report / QA subtabs currently show placeholder routing notes; existing SLS, cracking, report export, and report QA outputs remain available under ULS Strength.
- Results remains a future workspace placeholder only.
- Existing PMM/SLS calculations, prestress sign convention, D/C algorithm, report QA/export logic, limitations, warnings, materials, loads, and session state data are unchanged.

## Milestone 5.5 Scope

- Word report QA validates generated draft `.docx` content before future PDF/final template work.
- Required report section checks verify headings for executive summary, traceability, readiness, warnings, limitations, units, terminology, tables, figures, and generation notes.
- Draft disclaimer validation checks that the report says it is a draft engineering report, generated from current/stored results, and not final design certification.
- Engineering limitation validation checks that HIGH/CRITICAL limitations in the `ReportManifest` are disclosed.
- Engineering warning validation checks that warnings are present when recorded, or explicitly absent when none are recorded.
- Unit convention and terminology checks cover Force/kN, Moment/kN-m, Stress/MPa, Length/mm, Area/mm2, `Pu`, `Mux`, `Muy`, `Pe_eff`, No-Tension, and Decompression.
- Traceability/readiness QA checks readiness status, generated status, analysis mode, ULS/SLS availability, warning count, and limitation count.
- Table/figure QA checks report table and figure sections, figure placeholders, and duplicate SLS bar-chart caption risk.
- Misleading certification language checks flag overstatements such as fully validated, guaranteed safe, or certified design language without draft/prototype context.
- Word Report QA results can be downloaded as `word_report_qa.csv` from the Analysis tab.
- Existing PMM/SLS calculations are unchanged, and PDF export remains future work.

## Milestone 5.4 Scope

- Word report styling and content polish improves cover page, executive summary, headings, compact tables, and footer note.
- `ReportExportOptions` controls appendices, figures, max table rows, terminology, and registries.
- High/Critical engineering limitations are emphasized and sorted ahead of lower-risk limitations.
- Engineering warnings are shown clearly, including the no-warning case.
- Long tables are truncated with a clear note that full CSV export remains available.
- Draft figures include captions, selected context, source, limitations, and PNG-unavailable placeholders.
- Report generation notes state that export uses stored results, does not rerun solvers, does not change calculations, and PDF export remains future work.
- Existing PMM/SLS calculations are unchanged.

## Milestone 5.3 Scope

- Draft Word report export creates `.docx` bytes from the existing `ReportManifest`.
- The draft report includes cover metadata, executive summary, analysis scope, result traceability, readiness, engineering warnings, engineering limitations, unit conventions, terminology, table registry, figure registry, figures where available, and appendices.
- High/Critical limitations remain prominent in the report.
- Figure embedding uses PNG export when available; missing `kaleido` produces a report warning/placeholder instead of failing.
- Report generation reads current stored results and does not rerun analyses.
- Draft Word report download is available from the Analysis tab.
- PDF export remains future work.
- Existing PMM/SLS calculations are unchanged.

## Milestone 5.2 Scope

- Fixed duplicated SLS bar chart export readiness: `sls_stress_bar_diagram` is the single SLS bar chart export key.
- `sls_stress_visualization` is retained only as a compatibility/summary registry key and no longer exports the same bar chart.
- PMM figure export readiness is more context-aware.
- PMM Mux-Muy slice figures can be exported when stored selected slice dataframe data exists.
- PMM slice envelope figures can be exported when stored selected envelope dataframe data exists.
- PMM demand/capacity overlay returns a clear warning when demand point data is missing.
- PMM 3D surface export is not recreated during report export unless an existing dashboard figure state is available.
- PMM figure export uses existing stored result data and does not rerun the PMM solver.
- PMM figure export items carry limitations and warnings, including directional D/C prototype and convex hull fallback overestimation risk where detectable.
- Existing PMM/SLS calculations are unchanged.
- Final Word/PDF report export remains future work.

## Milestone 5.1 Scope

- Report figure export preparation adds `ReportFigureContext` and `ReportFigureExportItem`.
- Figure export registry captures availability, export readiness, selected combo/context, suggested PNG/HTML filenames, warnings, and limitations.
- Safe filename helper normalizes report figure filenames for future exports.
- Plotly HTML export helper returns downloadable HTML bytes.
- Optional Plotly PNG export helper returns PNG bytes when `kaleido` is available and a clear warning when it is not.
- Exportable SLS stress bar and SLS section stress point figures can be rebuilt from existing SLS summary/session data without rerunning solvers.
- Report manifest now includes figure context and figure export items while remaining JSON serializable.
- Analysis tab shows figure export context and registry, plus figure registry CSV export.
- Existing PMM/SLS calculations are unchanged.
- Final Word/PDF report export remains future work.

## Milestone 5.0 Scope

- Report Export Foundation creates `ReportManifest`, `ReportMetadata`, `ReportSection`, `ReportTableInfo`, and report figure registry foundations.
- Report manifest collection reads existing session results only and does not rerun PMM, SLS, cracking, verification, or hand-check solvers.
- Report section plan covers executive summary, metadata, analysis scope, geometry/materials, reinforcement/prestress, ULS PMM, ULS D/C, SLS stress, cracking classification, SLS visualization, verification, warnings/limitations, unit conventions, terminology, and appendices.
- Report table registry lists traceability, readiness, warnings, limitations, unit conventions, terminology, ULS/PMM, SLS, cracking, custom stress point, verification, and visualization tables.
- Report figure registry lists section layout, PMM surface/slices/envelope, SLS stress point/bar figures, cracking overlay, transformed preview, and custom stress point layout for future image export.
- Draft report outline helper produces text only; final Word/PDF generation remains future work.
- Manifest JSON, report section CSV, report table CSV, report figure CSV, and draft outline TXT downloads are available from the Pre-Report QA section.
- Engineering warnings and all engineering limitations are included in the report manifest, including high/critical limitation visibility.
- Existing PMM/SLS calculations are unchanged.
- Word/PDF report export remains future work.
- Beam/Girder flexure/shear/torsion calculations remain future work.
- Cracked-section solver, crack-width checks, and unbonded prestress model remain future work.

## Milestone A.3.2.2 Scope

- Limitations filtering hotfix ensures `collect_limitations_for_report(include_all=False)` always retains every HIGH and CRITICAL engineering limitation.
- Added branch coverage for Beam/Girder limitations filtering.
- Added coverage for alternate PMM/D-C context keys: `dc_summary`, `demand_capacity_summary`, and `rc_demand_capacity_result`.
- Added coverage for cracking context through `crack_classification_summary`.
- Context detection now fails closed when an object's `__bool__` raises `TypeError` or `ValueError`.
- Filtered MEDIUM limitations are context-aware rather than included wholesale.
- `neutral_axis_sweep_resolution` is included when PMM or D/C context exists.
- `prestress_compression_reversal` is included when prestress context exists.
- `crack_width_check` is included when SLS or cracking context exists.
- `beam_girder_shear_torsion` is included when Beam/Girder mode is selected.
- Filtered limitations now retain critical convex hull fallback risk plus high-risk `Ixy` coupling, directional D/C method, prestress axial cap, cracked section, and unbonded prestress limitations.
- Duplicate limitation keys are removed while preserving order.
- Added tests for the `include_all=False` limitations path.
- Shapely defensive exception handling was narrowed where practical around compression block membership, self-crossing checks, convex hull fallback, and stress check point validation.
- Invalid/sparse geometry inputs remain safe and do not crash the app.
- Existing PMM/SLS calculations are unchanged.
- Report export remains future work.
- Pre-report engineering limitations registry lists implemented/prototype/simplified/ignored/future-work items.
- Significant `Ixy` in transformed serviceability properties is now reported as an engineering warning because current SLS stress checks use an uncoupled `Ix`/`Iy` formula.
- D/C directional slice/envelope interpolation limitation is listed as high risk.
- Convex hull PMM slice fallback overestimation risk is listed as critical and shown more prominently in the PMM dashboard.
- Neutral-axis sweep resolution limitation is listed for engineering review.
- Cracked section SLS remains future work.
- Prestress axial cap is now validated by QA.PO1 at helper level: ACI axial cap uses a prestress-aware `Po` including bonded Aps; code-specific final-design review remains required.
- Prestress compression reversal remains a simplification; negative tensile strain is clamped to zero, but SOLVER.PS.COMP1 retains reversal events as PMM metadata and escalates them only when detected near the governing region.
- Unbonded prestress is still ignored with warning.
- Lightweight concrete Ec warning is available when the normal-weight ACI Ec estimate is used with low density.
- Ultimate concrete strain `ecu` default/code-basis note is listed for non-ACI/AASHTO workflow review.
- UI/lint cleanup before report export includes clearer readiness text, unbonded prestress count visibility, and obvious unused import/parameter cleanup.
- Existing PMM/SLS calculations are unchanged.
- Word/PDF report export remains future work.
- Pre-report QA and result traceability foundation is available in the Analysis tab.
- `ResultTraceabilitySnapshot` summarizes project metadata, analysis mode, section/material availability, ULS PMM/D-C status, SLS status, crack classification, verification status, warning count, and custom stress point counts.
- Report readiness checks classify report preparation as READY, PARTIAL, or NOT_READY.
- Engineering warnings are consolidated and de-duplicated without rerunning solvers.
- Standard terminology is available for demand, capacity, SLS, prestress, and analysis mode naming.
- Unit conventions are available for force, moment, stress, length, area, inertia, strain, angle, reinforcement area, and prestress force.
- Available report figures are listed for future export, including PMM dashboard, PMM slice/envelope, SLS stress visualization, cracking classification, transformed properties, and custom stress points.
- CSV exports are available for result traceability snapshot, report readiness, engineering warnings, unit conventions, terminology, and available report figures.
- Word/PDF report export remains future work.
- Existing PMM solver logic, SLS stress formulas, prestress eccentric sign logic, transformed section logic, and cracked-section assumptions are unchanged.
- Project JSON persists `analysis_mode_settings`, including member type and workflow metadata.
- Project JSON persists `custom_stress_check_points`, including name, coordinates, point type, active flag, governing flag, source, and note.
- Project JSON persists `include_default_stress_check_points`.
- Loaded custom SLS stress check points restore into the Custom Stress Check Points UI table.
- Inactive custom stress points are preserved in the project file but excluded from SLS stress analysis.
- Non-governing custom stress points remain visible in SLS results but do not govern summaries.
- Existing PMM solver logic, SLS stress formulas, prestress eccentric sign logic, and `LoadCase` `Pu` / `Mux` / `Muy` fields are unchanged.
- Analysis Mode / Member Type framework adds Column / Pier / Wall / Pylon PMM Mode, Beam / Girder Future Mode, and General Section Mode.
- Column / Pier / Wall / Pylon PMM Mode is the current primary workflow and continues to use `Pu`, `Mux`, and `Muy` with PMM interaction, ULS D/C review, and SLS stress tools.
- Beam / Girder Mode is a placeholder for future flexure, shear, torsion, transfer-stage, service-stage, and tendon-profile workflows. Beam/Girder calculations are not implemented yet.
- General Section Mode keeps the existing PMM and SLS tools available for section review when the member type is not yet classified.
- Existing PMM solver behavior, existing SLS stress formulas, and existing LoadCase `Pu` / `Mux` / `Muy` fields are unchanged.
- Prestress should not be double-counted by entering effective prestress `Pe` as `Pu` demand when prestress elements are already defined.
- PMM interaction is not the primary design method for typical Beam/Girder flexural design; dedicated Beam/Girder checks are future work.
- Metadata-driven Section Builder with category filtering and generated parameter controls.
- Geometry generators that convert every preset into `SectionGeometry`.
- Shapely-backed section validation for outer polygons, holes, area, rebar locations, and prestress element locations.
- Safer generator-side validation for hollow, box, girder, and voided sections.
- Plotly section preview with equal aspect ratio, centroid marker, holes, and dimension labels.
- Dimension labels support symbol + value, symbol only, and value only display modes.
- `PrestressElement` remains the primary model for prestressing steel, including wire, strand, prestressing bar, tendon group, and custom steel.
- Unified prestressing steel database in `data/prestress_steel_database.csv`.
- Loads tab foundation with editable `Pu`, `Mux`, and `Muy` demand values.
- `Pu`, `Mux`, and `Muy` are intended primarily for future ULS PMM strength checks.
- SLS load cases can be stored now, and active SLS load cases can be checked using either gross-section or uncracked transformed-section elastic concrete stress with optional effective bonded prestress contribution, cracking/tension-zone classification, custom stress check points, and selected-combo stress visualization.
- User-facing load units for force (`kN`, `N`, `tonf`) and moment (`kN-m`, `N-mm`, `tonf-m`).
- Internal load storage in `LoadCase` uses `Pu_N`, `Mux_Nmm`, and `Muy_Nmm`.
- Backward compatibility is maintained for older `Mx_Nmm` / `My_Nmm` and `mx_nmm` / `my_nmm` project data.
- Sign convention panel for axial load, biaxial moment, and x-y coordinates.
- Serviceability settings are stored in `ServiceabilitySettings`, including section-basis selection, SLS load type, compression limit ratio, tension limit mode, no-tension check, decompression check, critical point filter, and effective-prestress-force inclusion flag.
- Active SLS load cases are filtered and displayed in engineering units using `Pu`, `Mux`, and `Muy`.
- Gross section properties are calculated from `SectionGeometry` using net concrete area for hollow sections: area, centroid, `Ix`, `Iy`, `Ixy`, bounds, and section moduli.
- Default serviceability stress check points are generated at the top fiber, bottom fiber, left fiber, right fiber, and centroid.
- Elastic SLS stress checks calculate concrete stress at default stress check points for active SLS load cases using the selected section basis.
- SLS stress display uses compression negative and tension positive, intentionally separate from the ULS PMM compression-positive force convention.
- Concrete compression and tension limit checks support compression limit ratio, user-defined tension limit, `sqrt(f'c)` ratio mode, no-tension checks, and decompression checks.
- Milestone 4.5 decompression check is implemented as a no-tension stress check at selected concrete stress points; member-level tendon-zone decompression and cracked-section analysis are future work.
- SLS stress result tables report stress type, limit, utilization, PASS/FAIL status, message, and section basis.
- SLS summaries identify overall status, governing combo, governing point, maximum compression/tension stress, maximum utilization, no-tension violations, decompression violations, compression failures, and tension failures.
- Critical point filtering supports checking all default points or extreme fibers only.
- SLS Verification / Stress Sign Benchmarks run deterministic checks for axial compression sign, Mux/Muy bending signs, eccentric prestress signs, transformed-section stress behavior, no-tension/decompression judgement, and governing SLS result selection.
- SLS verification results can be exported as `sls_verification_results.csv`.
- Cracking / tension-zone classification uses existing elastic SLS stress results to identify compression, zero stress, tension within limit, tension limit exceedance, no-tension violation, and decompression violation.
- Crack classification summaries report overall classification, governing combo, governing point, maximum tension stress, and tension point count.
- Critical point filtering is respected by the crack classification workflow; `extreme_fibers_only` excludes centroid/reference points from governing classification.
- Cracking classification results can be exported as `sls_cracking_classification.csv`.
- Milestone 4.7 does not perform cracked-section stress redistribution, cracked transformed neutral-axis iteration, or crack-width checks.
- Users can define additional SLS stress check points beyond the default top, bottom, left, right, and centroid/reference points.
- Custom stress point types include tendon zone, web-flange junction, reentrant corner, construction joint, segmental joint, and custom.
- Custom stress check points are validated against the concrete section geometry; points outside concrete or inside voids are rejected for analysis until fixed.
- Custom points can be included or excluded from governing serviceability summaries while still appearing in stress result tables.
- Custom stress check point metadata is included in SLS stress results and cracking/tension classification tables.
- Stress check point lists can be exported as `sls_stress_check_points.csv`.
- SLS stress visualization plots the concrete section outline, holes/voids, default stress check points, and custom stress check points for a selected SLS combo.
- Stress plot markers are colored by PASS/FAIL status, compression/tension state, and cracking/tension classification overlay.
- Stress point hover text reports total, external, and prestress stress, status, utilization, point type/source, governing flag, and classification message.
- A selected-combo SLS stress bar diagram shows compression as negative and tension as positive with a zero-stress reference line.
- Selected combo visualization data can be exported as `sls_stress_visualization_selected_combo.csv`.
- SLS stress visualization is based on selected stress check points, not a full stress contour.
- Effective bonded prestress can be included in elastic SLS stress using existing `Pe_eff`, initial stress, or initial strain values from `PrestressElement`.
- Elastic SLS stress output reports section basis, external stress, prestress stress, and total stress separately; status and utilization use total stress.
- Prestress effective force is treated as compression on the concrete/member, with eccentricity moments from tendon location relative to the selected section-basis centroid.
- SLS prestress eccentric moment signs follow `Mpe_x = -sum(Pe * (y_ps - cy))` and `Mpe_y = -sum(Pe * (x_ps - cx))`, so a tendon located near a fiber increases compression at that same fiber.
- Unbonded prestress is ignored in SLS stress checks with a clear warning.
- Prestress losses, secondary effects, tendon profile variation along the member length, cracking, and crack widths are not calculated in the SLS check.
- Prestress service contribution summary and CSV export report bonded count, ignored unbonded count, total `Pe_eff`, prestress centroid, and `Mpe_x` / `Mpe_y`.
- Elastic SLS stress results can be exported as `sls_elastic_stress_results.csv`.
- Concrete elastic modulus can be estimated with `Ec = 4700 * sqrt(f'c)` for normal-weight concrete or overridden with a user-defined Ec.
- Modular ratio helpers compute `n_s = Es/Ec` for ordinary rebar and `n_p = Ep/Ec` for prestressing steel.
- Uncracked transformed section properties are available for concrete + ordinary rebar + bonded prestress using the `net_steel` transformed area convention.
- Ordinary rebar transformed contribution uses `(n_s - 1) * As`; bonded prestress contribution uses `(n_p - 1) * Aps`.
- Transformed section output includes transformed area, centroid, `Ix`, `Iy`, `Ixy`, rebar contribution, prestress contribution, counts, warnings, and CSV export.
- User can choose gross section basis or uncracked transformed section basis for elastic SLS stress checks.
- Transformed SLS stress uses transformed area, centroid, `Ix`, and `Iy`; full unsymmetric `Ixy` stress coupling is still a future refinement.
- Cracked section analysis, crack-width checks, and unbonded prestress serviceability modeling are future work.
- Rebar tab foundation with manual coordinate input.
- Rebar database in `data/rebar_database.csv`.
- Rebar validation against the current `SectionGeometry`, including outside-concrete and inside-void checks.
- Rebar summary with active bar count and total `As`.
- Rebar hotfix behavior: database Bar Size takes precedence over manual diameter, while `Custom` uses manual `Diameter_mm`.
- `st.session_state["rebars_valid_for_analysis"]` indicates whether parsed rebars are free of parse and geometry errors.
- Prestress tab foundation with manual input for wire, strand, prestressing bar/PT bar, tendon group, and custom prestress steel.
- Prestress input modes: Passive, Effective Force Pe, Effective Stress fpe, and Jacking Stress + Losses.
- `Pe_eff_kN` is the user-facing prestress force input for Effective Force Pe mode.
- Internal prestress force remains stored as `pe_eff_n` in N.
- Effective Force Pe is checked against `fpu_MPa`; values that create initial stress greater than `fpu_MPa` are rejected.
- Prestress elements store `pe_eff_n`, initial stress, and initial strain for future PMM analysis.
- Bonded defaults to `True`; select `False` only for unbonded prestressing steel.
- Bonded prestress can be included in the PMM prototype; unbonded prestress is still ignored with a clear warning.
- Project tab foundation for project-level information, JSON save, JSON load, and project summary.
- `ProjectModel` stores section preset data, generated section geometry, materials when available, load cases, rebars, and prestress elements.
- Project JSON loading restores core model objects into `st.session_state` for review in the existing tabs.
- Materials tab foundation for concrete, rebar, and prestressing steel material input.
- Concrete material input includes `f'c`, `ecu`, density, and beta1 with ACI auto/manual modes.
- Rebar material input supports project material lists such as SD40 and SD50.
- Prestressing steel material input supports wire, strand, prestressing bar/PT Bar, tendon group, and custom steel.
- PT Bar / Prestressing Bar material properties include `fpu`, optional `fpy`, `Ep`, area, diameter, grade, source, and catalog verification metadata.
- `aci_beta1(fc_MPa)` helper is available for future ACI 318 workflows.
- Analysis settings are captured for the future PMM workflow, including code, strength load type, inclusion flags, phi-factor flag, and neutral-axis step counts.
- Analysis readiness / preflight checks validate that section geometry, concrete material, ULS load cases, rebars, prestress elements, and material lists are ready enough for future analysis.
- `AnalysisInput` is the intended future PMM solver input container. Future solver code should consume `AnalysisInput`, not direct Streamlit session data.
- PMM Solver Prototype generates a nominal and phi-reduced PMM point cloud from concrete, ordinary reinforcing bars, and optional bonded prestress.
- The solver consumes `AnalysisInput`; it does not read Streamlit `session_state`.
- Concrete compression uses a Whitney stress block with Shapely polygon clipping for arbitrary section geometry.
- Ordinary rebar uses linear strain compatibility with elastic-perfectly-plastic stress capped at `fy`.
- Ordinary rebar inside the Whitney compression block can use net replacement force `As(fs - 0.85f'c)` to avoid double counting concrete compression already included in the stress block.
- Ordinary rebar outside the compression block remains `As*fs`.
- Analysis Settings includes a toggle, `Subtract displaced concrete at rebar locations`, which is enabled by default and preserved in Project JSON.
- PMM results include rebar displaced-concrete subtraction and inside-compression-block counts for engineering review.
- Prestressing steel / PT Bar displaced concrete subtraction is not included yet; this refinement applies to ordinary rebar only.
- Bonded prestress contribution prototype supports wire, strand, prestressing bar/PT Bar, tendon group, and custom `PrestressElement` through the same common interface.
- Bonded prestress uses stored `initial_strain`, or converts `initial_stress_mpa` / `pe_eff_n` to initial strain when needed.
- Prototype prestress stress uses `eps_ps,total = eps_pe - eps_section`, where positive section compression reduces tendon tensile strain and section tension increases tendon tensile strain.
- Prestress stress models are selectable in Analysis settings: `bilinear` and `linear_cap`.
- `linear_cap` uses elastic `Ep * eps` stress capped between zero and `fpu`.
- `bilinear` uses `fpy` / proof stress when available, then a prototype post-yield slope before capping at `fpu`.
- If `fpy` / proof stress is missing for the bilinear model, the solver falls back to the linear capped prestress model with a clear warning.
- PT Bar / `prestressing_bar` inputs warn when `fpy_MPa` / proof stress is missing, close to `fpu_MPa`, or lower than initial prestress stress.
- Compression reversal of prestressing steel is still not fully modeled; negative total tensile strain is clamped to zero with a warning.
- PMM result data includes prestress stress model, stress warning count, maximum prestress stress, and fpu-cap count where applicable.
- Prestress sign convention checks verify that section compression strain reduces tendon tensile strain and section tension strain increases tendon tensile strain.
- Prestress PMM verification tools check bonded/unbonded status, material strengths, initial stress/strain, `Pe_eff`, and PT Bar proof stress availability before analysis review.
- Prestress Analysis Check Table is available in the Analysis tab with OK, WARNING, ERROR, and IGNORED statuses.
- PT Bar / `prestressing_bar` analysis checks warn when proof/yield stress (`fpy_MPa`) is missing.
- RC-only versus RC + bonded prestress comparison is generated when bonded prestress is included.
- Prestress contribution summary reports included bonded count, ignored unbonded count, total bonded `Aps`, total `Pe_eff`, max absolute prestress force, and mean absolute prestress force.
- Compression reversal of prestressing steel, bonded prestress production validation, and unbonded prestress models are future work.
- ACI axial cap now uses the QA.PO1-validated prestress-aware `Po` helper including ordinary rebar and bonded prestress steel; unbonded prestress is excluded upstream by policy.
- Report export and advanced serviceability checks remain future milestones.
- Analysis settings include tied or spiral transverse reinforcement for prototype phi-factor and axial-cap behavior.
- RC PMM axial strength cap refinement adds ACI-style tied and spiral cap factors.
- Tied columns use maximum axial cap factor 0.80 with compression-controlled phi of 0.65; QA.PO1 covers helper-level area and strength bookkeeping.
- Spiral columns use maximum axial cap factor 0.85 with compression-controlled phi of 0.75; code-specific project review remains required.
- PMM results include capped `phiPn` values for axial compression display and axial-only checks.
- RC PMM visualization displays engineering-unit summaries in kN and kN-m.
- Analysis results include P-Mnx, P-Mny, Mnx-Mny, and 3D point-cloud Plotly charts.
- Active ULS demand points are displayed and overlaid for visual reference only.
- RC PMM result CSV export is available with both internal-unit and display-unit columns.
- Lightweight solver verification helpers summarize point count, phi range, NaN/Inf status, and envelope extremes.
- RC ULS demand/capacity prototype checks active ULS load cases using `Pu`, `Mux`, and `Muy`.
- The prototype estimates directional moment capacity from the PMM point cloud at the demand axial load.
- D/C ratio is reported as demand moment magnitude divided by estimated phi-reduced directional moment capacity.
- Results include PASS, FAIL, OUT_OF_RANGE, or NOT_CHECKED status plus governing combo and maximum D/C ratio.
- Axial-only ULS D/C checks use capped maximum axial capacity when available.
- Directional moment D/C now uses a cleaned selected-Pu slice envelope with ray-intersection capacity extraction as the preferred path; point-cloud interpolation remains only as a fallback when slice/envelope data are unavailable.
- PMM Slice Dashboard adds an active ULS load case selector for reviewing a Mux-Muy capacity slice at the selected Pu.
- The dashboard shows the selected demand point, demand vector, and load case D/C status on the Mux-Muy slice.
- A 3D PMM interaction dashboard displays the PMM point cloud, active ULS load points, selected load point, and current Pu slice.
- PMM Summary Card reports selected combo, Pu, Mux, Muy, resultant Mu, available phiMn at Pu, status, D/C ratio, analysis mode, and prestress inclusion state.
- Load case D/C ranking sorts governing demand cases for engineering review.
- PMM slice visualization is based on the current prototype PMM point-cloud interpolation; final production interpolation and validation remain future work.
- PMM verification / benchmark suite builds rectangular RC benchmark cases directly as `AnalysisInput` objects.
- Benchmark cases include base RC, higher `f'c`, higher `As`, RC + bonded PT Bar, and matching RC-only cases.
- Verification checks confirm finite PMM results, positive axial capacity, higher `f'c` capacity increase, higher `As` non-reduction, and symmetric positive/negative bending balance.
- Verification checks include rebar displaced-concrete behavior, including net force reduction inside the compression block, unchanged force outside the block, and PMM comparison with the toggle enabled/disabled.
- Independent PMM hand-calculation spot checks are available for engineering review.
- Hand checks include RC axial compression `Po` and `phiPn,max`, rebar displaced-concrete spot checks, prestress strain convention checks, prestress stress model checks, a simplified uniaxial RC strain compatibility point, and symmetry sanity checks.
- Hand check results can be displayed and exported to CSV from the Analysis tab verification expander.
- Hand checks are simplified spot checks and do not replace full independent validation or code-certified design software.
- RC-only versus RC + bonded PT Bar benchmark comparison confirms bonded prestress changes the PMM result and produces nonzero prestress force.
- Unbonded prestress ignore behavior is checked to preserve current solver scope.
- Analysis tab includes a compact `PMM Verification / Benchmark Checks` expander with PASS / WARNING / FAIL results.
- Verification suite results support engineering review but do not replace independent validation or final design certification.
- Refined PMM slice interpolation builds selected-Pu Mux-Muy slices by interpolating along each neutral-axis `theta_rad` / `c_mm` PMM point family.
- The previous tolerance-based `pmm_slice_at_pu_tolerance()` method remains available as a fallback when interpolation data is missing or too sparse.
- Preferred `pmm_slice_at_pu()` now attempts `pmm_slice_at_pu_interpolated()` first and records slice method, skipped theta count, interpolated theta count, and warnings in dataframe attrs.
- Directional ULS D/C now first builds an interpolated PMM slice at demand `Pu`; directional capacity is then read from the cleaned slice envelope with ray-intersection before fallback methods are considered.
- PMM dashboard slice plots display whether the selected Pu slice is interpolated or a tolerance fallback.
- PMM Summary Card includes slice method and D/C method so users can see how the prototype value was obtained.
- Verification suite checks that interpolated slices are available for benchmark results and that directional capacity from the slice is finite.
- PMM slice envelope processing cleans duplicate/noisy Mux-Muy slice points before plotting and directional D/C checks.
- `SliceEnvelopeResult` reports input/output point counts, envelope method, validity, warnings, self-crossing detection, and convex-hull fallback state.
- Envelope cleanup computes polar angle/radius, removes near-duplicate angles while keeping the largest radius, and checks angular coverage, radius jumps, and self-crossing risk.
- Convex hull fallback is available for visualization safety and always warns that it may overestimate non-convex interaction shapes.
- Directional ULS D/C now prefers the cleaned PMM slice envelope with ray-intersection capacity extraction, then falls back to polar slice interpolation and point-cloud directional methods only when needed.
- PMM dashboard plots raw slice points lightly and the cleaned envelope boundary as the main curve.
- PMM Summary Card now reports envelope method, envelope validity, convex hull fallback state, and boundary warning count.
- Verification suite includes envelope availability, finite radius, directional envelope capacity, envelope D/C, and convex hull fallback checks.
- Numerical cleanup removes pandas downcasting `FutureWarning` risk in PMM result display conversion by using explicit numeric handling.
- Neutral-axis depth sweep now uses a relative lower bound, `c_min = max(1 mm, 0.001 * projected depth)`, for improved numerical robustness.
- PMM result numerical summaries use vectorized NaN/Inf checks instead of flattening all numeric values into Python lists.
- Slice envelope angular coverage warnings are tuned: limited coverage and moderate coverage are warnings for review, not automatic invalidation by themselves.
- Code-quality cleanup keeps slice duplicate checks readable and avoids repeated lazy imports inside active load-case loops.
- Standardized prototype warning constants centralize PMM prototype, D/C prototype, bonded prestress, unbonded prestress, serviceability, report export, convex hull fallback, and RC axial cap limitation wording.
- D/C result rows include method metadata: capacity method, slice method, envelope method, fallback state, and warning count.
- ULS D/C result CSV export is available for engineering-unit review.
- Selected PMM slice and selected slice envelope CSV exports are available from the PMM Slice Dashboard.
- Analysis tab groups engineering warnings from PMM results, prestress checks, D/C checks, and selected slice/envelope review while preserving warning order and removing duplicates.
- Lightweight PMM dataframe numerical checks report row count, NaN/Inf columns, envelope magnitude summaries, and warnings without changing solver output.
- Active SLS load cases can be checked with gross-section or uncracked transformed-section elastic concrete stress, including no-tension/decompression judgement, SLS sign benchmark verification, and cracking/tension-zone classification from selected check points; cracked-section redistribution remains future work.
- Final production PMM interpolation and design certification are future work.

## Prestressing Steel Database

`data/prestress_steel_database.csv` is the single prestressing steel database. It includes strand rows and generated high-strength prestressing bar rows with metadata columns:

- `source`
- `area_source`
- `is_catalog_verified`

Prestressing bar areas are initially generated from `pi*d^2/4`. Manufacturer catalog values should override generated areas when available.

## Run

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Test

```powershell
python -m pytest -q
```

## Architecture Notes

The Section Builder does not hard-code parameter inputs per section type. It reads category, preset, and parameter definitions from `data/section_presets.json` and generates controls dynamically.

All section presets are converted to `SectionGeometry` before future analysis. Future PMM solver code should consume `SectionGeometry` or `SectionModel` only, not preset names or UI metadata.

Load cases are stored in internal units before analysis. `Pu_N`, `Mux_Nmm`, and `Muy_Nmm` are the primary names for new data. Older project JSON using `Mx_Nmm` / `My_Nmm` is migrated on load.

Rebars are stored as `Rebar` objects in `st.session_state["rebars"]`. They are previewed on the current section geometry and used by the PMM prototype when included in analysis settings.

Prestress elements are stored as `PrestressElement` objects in `st.session_state["prestress_elements"]`. `Pe_eff_kN` from the UI is converted to internal `pe_eff_n`, and initial strain is stored for PMM analysis. Bonded prestress is included by the current PMM prototype when `include_prestress = True`; unbonded prestress is ignored with warning because its separate model is future work.

Project files are serialized through `ProjectModel` as JSON. Save/load is intended to preserve the current data foundation for later analysis milestones, including `analysis_settings` and `serviceability_settings`; it does not automatically trigger capacity or serviceability stress calculation.

Analysis mode settings are stored as `AnalysisModeSettings` and persisted in Project JSON. The Analysis tab can identify the current workflow as Column / Pier / Wall / Pylon PMM Mode, Beam / Girder Future Mode, or General Section Mode. Column/Pier mode keeps the existing PMM interaction workflow as the primary path. Beam/Girder mode is only a placeholder and warns that future flexure, shear, torsion, transfer-stage, service-stage, and tendon-profile checks are not implemented yet. General Section mode keeps PMM and SLS tools available for careful section-level review. The helper module `concrete_pmm_pro/core/analysis_modes.py` centralizes labels, descriptions, workflow flags, and warnings, including the reminder not to double-count prestress as `Pu`.

Pre-report QA helpers live in `concrete_pmm_pro/reporting/`. Milestone A.3 adds result traceability snapshots, report readiness checks, engineering warning consolidation, standard terminology, unit convention tables, and an available figure registry foundation. Milestone A.3.1 adds `reporting/limitations.py`, an engineering limitations registry covering `Ixy` coupling, directional D/C interpolation, convex hull fallback, neutral-axis sweep resolution, cracked-section future work, prestress axial cap method note, prestress compression reversal, unbonded prestress, crack width future work, beam/girder future checks, lightweight concrete Ec, and ultimate concrete strain code-basis review. Milestone A.3.2 fixes filtered limitations so HIGH and CRITICAL items remain visible when `include_all=False`, and narrows defensive Shapely exception handling without changing geometry behavior. Milestone A.3.2.1 adds branch coverage for Beam/Girder filtering and clarifies filtered MEDIUM limitation rules. Milestone A.3.2.2 adds coverage for alternate D/C context keys, cracking context through `crack_classification_summary`, and defensive truthiness handling that does not infer context when `bool(value)` raises. Milestone 5.0 adds report foundation files for metadata, section planning, table registry, figure registry, manifest JSON, and draft outline generation. Milestone 5.1 adds report figure export preparation through `ReportFigureContext`, `ReportFigureExportItem`, safe filenames, Plotly HTML export, optional `kaleido` PNG export, and export-ready SLS figure reconstruction from existing session results. Milestone 5.2 removes the duplicate SLS bar-chart export path, improves PMM figure context/readiness, and enables PMM Mux-Muy slice and slice-envelope export when stored dashboard dataframes already exist. Milestone 5.3 adds draft Word report export using `ReportManifest`, with metadata, traceability, readiness, warnings, limitations, units, terminology, tables, and export-ready figures when PNG export is available. Milestone 5.4 polishes the Word report with improved cover/executive summary styling, high/critical limitation emphasis, warning presentation, table truncation policy, figure captions/placeholders, report generation notes, and `ReportExportOptions`. Milestone 5.5 adds `reporting/report_qa.py` for Word report QA, including heading, disclaimer, limitation, warning, unit, terminology, traceability, figure/table, and misleading-certification wording checks. The Analysis tab can export CSV files for `result_traceability_snapshot.csv`, `report_readiness.csv`, `engineering_warnings.csv`, `engineering_limitations.csv`, `unit_conventions.csv`, `standard_terminology.csv`, `available_report_figures.csv`, `report_section_plan.csv`, `report_tables.csv`, `report_figures.csv`, `report_figure_export_registry.csv`, and `word_report_qa.csv`, plus `report_manifest.json`, `draft_report_outline.txt`, and `concrete_pmm_pro_draft_report.docx`. These helpers summarize existing session results only; they do not recalculate PMM/SLS results and do not generate PDF reports yet.

Materials are stored as `ConcreteMaterial`, `RebarMaterial`, and `PrestressSteelMaterial` objects. Project JSON preserves the active concrete material, rebar material list, prestressing steel material list, and active material names. PT Bar / Prestressing Bar elements are supported through `PrestressElement`; effective prestress force is defined in the Prestress tab.

Analysis settings are stored as `AnalysisSettings`, including tied/spiral transverse reinforcement and the `include_prestress` flag. Preflight builds an `AnalysisInput` object only when readiness errors are resolved. The Analysis tab can run the RC-only prototype or the RC + bonded prestress prototype, show point-cloud plots, export CSV results, run a prototype ULS demand/capacity check, review selected ULS cases in the PMM Slice Dashboard, and run benchmark-style verification checks.

Serviceability settings are stored as `ServiceabilitySettings`. The Analysis tab includes a `Serviceability / SLS Foundation` expander that prepares active SLS load tables, gross section properties, transformed section properties, default/custom stress check points, and elastic SLS stress checks. Milestone A.2 persists custom SLS stress check points through Project JSON, including inactive rows and non-governing flags, and restores them into the editable table after project load. The SLS display convention is compression negative and tension positive. Users can select gross section basis or uncracked transformed section basis; transformed stress uses the selected basis area, centroid, `Ix`, and `Iy`. Effective prestress is treated as compressive action on concrete. When enabled, effective bonded prestress contributes elastic SLS stress using the same selected section-basis centroid and inertia plus existing `Pe_eff`, initial stress, or initial strain from the Prestress tab; losses are not recalculated in the SLS check. Eccentric prestress induces equivalent service moments `Mpe_x = -sum(Pe * (y_ps - cy_basis))` and `Mpe_y = -sum(Pe * (x_ps - cx_basis))`, which means a tendon located near a fiber increases compression at that same fiber. No-tension and decompression checks fail when tensile stress is greater than the selected zero-stress tolerance. Decompression in Milestone 4.5 is a no-tension point-stress check, not a full tendon-zone or cracked-section decompression analysis. Milestone 4.6 adds `concrete_pmm_pro/verification/sls_benchmarks.py` for SLS sign and benchmark checks covering axial compression, biaxial bending sign, eccentric prestress sign, transformed section behavior, no-tension/decompression judgement, and governing SLS result selection; results can be exported as `sls_verification_results.csv`. Milestone 4.7 adds `concrete_pmm_pro/serviceability/cracking.py` for tension/cracking risk classification from existing SLS stress results, including tension-limit exceedance, no-tension violation, decompression violation, critical point filtering, and `sls_cracking_classification.csv` export. Milestone 4.8 adds `concrete_pmm_pro/serviceability/points.py` for custom SLS stress check point parsing, section/void validation, default/custom point merging, governing inclusion metadata, and `sls_stress_check_points.csv` export. Milestone 4.9 adds `concrete_pmm_pro/visualization/sls_stress.py` for selected-combo SLS section stress plots, stress point hover data, cracking/tension overlay fields, stress bar diagrams, and `sls_stress_visualization_selected_combo.csv` export. The current serviceability workflow does not perform full cracked-section stress redistribution, crack-width checks, unbonded prestress serviceability modeling, full unsymmetric `Ixy` stress coupling, full stress contours, or report export yet.

The PMM prototype uses this sign convention: compression force is positive, steel/prestress tension force is negative, x is positive to the right, y is positive upward, `Mnx = sum(F * (y - y_ref))`, and `Mny = sum(F * (x - x_ref))`. Section strain is positive in compression and negative in tension. Prestress initial strain is positive in tendon tension. Bonded prestress total tensile strain is modeled as `eps_ps,total = eps_pe - eps_section`, so compression strain at the tendon reduces tendon tensile strain and tension strain increases it. Prestressing steel stress is modeled as a tensile magnitude, then converted to tension-negative section force. Compression reversal of prestressing steel is future work. Demand naming remains separate: `Mux` and `Muy` are demand inputs, while `Mnx` and `Mny` are nominal resistance outputs.

PMM result display helpers convert internal `N` and `N-mm` values to `kN` and `kN-m` for review. The display dataframe includes `phiPn_capped_N`, `phiPn_capped_kN`, `prestress_force_N`, `prestress_force_kN`, prestress included/ignored counts, `rebar_displaced_concrete_subtracted_N`, `rebar_displaced_concrete_subtracted_kN`, and `rebar_inside_compression_count`. Ordinary rebar inside the Whitney compression block uses `As(fs - 0.85f'c)` when the Analysis Settings toggle is enabled, while prestressing steel still uses its separate prototype stress-strain path without displaced-concrete subtraction. The ULS D/C workflow now prefers a cleaned selected-Pu slice envelope built from interpolated theta-family PMM slice points, then estimates directional capacity by intersecting the demand moment ray with the actual Mx-My envelope boundary. If ray-intersection envelope capacity cannot be used, the workflow falls back to polar slice interpolation and point-cloud methods with warnings. Axial-only D/C uses capped maximum phiPn. D/C display tables and CSV export identify capacity method, slice method, envelope method, fallback state, and warning count. The PMM Slice Dashboard reuses the same prototype point cloud to show raw slice points, cleaned envelope boundary, demand vector, 3D PMM interaction view, PMM summary card, D/C ranking table, selected slice CSV export, and selected envelope CSV export. The PMM verification suite in `concrete_pmm_pro/verification/pmm_benchmarks.py` runs benchmark-style sanity checks on rectangular RC and RC + bonded PT Bar cases, including interpolated slice availability, envelope robustness, directional capacity checks, and displaced-concrete toggle comparisons. The independent hand-check suite in `concrete_pmm_pro/verification/hand_checks.py` compares selected solver behavior against simplified hand calculations for axial compression, rebar displaced concrete, prestress strain/stress conventions, uniaxial RC strain compatibility, and symmetry sanity; results can be exported as `pmm_hand_check_results.csv` from the Analysis tab. The SLS benchmark suite in `concrete_pmm_pro/verification/sls_benchmarks.py` verifies compression-negative/tension-positive stress signs, gross/transformed stress behavior, eccentric prestress sign, no-tension/decompression judgement, governing SLS selection, crack classification checks, and custom SLS stress point behavior; results can be exported as `sls_verification_results.csv`. Cracking classification uses existing SLS stress results only, supports `all` or `extreme_fibers_only` critical point filtering, and exports `sls_cracking_classification.csv`. Custom SLS stress check points can represent tendon zones, web-flange junctions, segmental joints, construction joints, reentrant corners, or general custom review points; invalid geometry is reported before analysis and governing inclusion can be disabled per point. SLS stress visualization plots selected-combo stress check points on the section outline with holes/voids, custom point metadata, status/classification marker colors, hover details, and an optional stress bar diagram; visualization data exports as `sls_stress_visualization_selected_combo.csv`. Directional moment D/C, warning summaries, numerical checks, benchmark checks, hand checks, SLS verification checks, cracking classification, custom SLS point checks, SLS stress visualization, and elastic SLS stress/no-tension/decompression checks remain prototype engineering review tools only; final production validation, unbonded prestress, report export, cracked-section stress redistribution, crack-width checks, full transformed/cracked serviceability refinements, and prestress loss/profile effects are future work.


## Solver validation direction

Concrete PMM Pro now includes a PMM solver validation framework and the first executable RC-only benchmark pack:

- `QA.VALIDATION1` — validation matrix / report structure
- `VALID.RC1` — rectangular RC PMM benchmark pack with axial-cap, uniaxial bending, symmetry, and numeric-schema checks

These validation assets are not a final certification. They are the project control system for reducing prototype warnings only when benchmark evidence supports the change.

### UI.VALIDATION.STATUS1 — Validation status panel

The Analysis workspace now includes a commercial-facing validation status panel.  It summarizes which PMM method areas have implemented benchmark coverage, which are still validation-in-progress, and which are planned future checks.  This replaces broad `Prototype Result` heading wording while retaining Diagnostics / QA notes for final engineering review.

### UI.VALIDATION.STATUS1.1 — Validation Evidence Detail Polish

The Analysis validation panel now separates the first-screen validation overview from the detailed evidence table.  The compact overview shows method area, validation status, design-use guidance, and case ID.  A nested detailed evidence expander keeps benchmark evidence and remaining engineering limitations available for QA without crowding the main Analysis result page.  This milestone does not change solver equations; it improves how validation evidence is communicated to users.

### UI.ANALYSIS3.9 — Result Hierarchy and Solver Info Cleanup

The Analysis diagnostics now use a cleaner commercial-style hierarchy. First-screen solver diagnostics show only compact QA essentials, while detailed PMM envelope metadata, reinforcement/prestress solver metadata, prestress stress-state diagnostics, and RC-only vs RC+PS capacity comparisons are retained in collapsed QA expanders. This is a UI hierarchy and traceability refinement only; it does not change solver equations or D/C results.

### UI.ANALYSIS4 — Governing PMM Slice Visualization

The PMM Check tab now emphasizes the governing Mux-Muy slice at the selected Pu.  The figure shows the cleaned PMM slice envelope, the demand vector, the capacity ray, and the ray/envelope intersection used to compute available phiMn and D/C.  Selected-case cards also show capacity margin and reserve ratio.  This milestone does not change PMM equations or D/C extraction; it makes the existing SOLVER.PMM.DC1 ray-intersection result traceable to the user visually.


- UI.ANALYSIS4.1: Clean PMM slice plot interaction with selected-only default, optional chart annotations, and controlled all-ULS demand point overlay.

### UI.ANALYSIS4.2 — Governing Slice Plot Minimal Mode

The PMM Check slice plot now uses a governing-case-only display by default and resets the annotation control key so old session-state callouts do not persist after upgrade.  Annotation callouts remain available for presentation screenshots, but they are off by default because text boxes can hide demand and capacity markers.  The plot can still show selected cases, selected + governing, or all active ULS points when the user explicitly chooses those modes.

### UI.ANALYSIS4.3 — Result Confidence / Design Decision Banner

Adds a first-screen design decision banner to the Analysis workspace. The banner separates the governing ULS PMM strength decision from QA diagnostics so users can distinguish direct governing-result warnings from background method notes. It summarizes PASS/FAIL, confidence, final review scope, D/C, fallback count, D/C warnings, governing QA count, and capacity margin without changing PMM solver equations or D/C extraction.

### UI.ANALYSIS4.4 — Final Analysis Workspace Polish

The Analysis workspace decision area now avoids duplicate status storytelling between the top workspace header and the Design Decision banner.  The header acts as a compact workspace status strip, while the decision banner carries the engineering conclusion.  The banner also separates Decision, Confidence, and Scope / Exclusions into dedicated blocks so ULS PMM strength status, validation confidence, prestress inclusion, and SLS exclusion are easier to read.  This milestone is UI communication polish only and does not change solver equations, PMM surface generation, demand/capacity extraction, prestress behavior, load import, report export, or cache behavior.

### SECTION.PRESET1A — Parametric I-Girder Geometry

Adds a bridge-oriented parametric I-Girder preset under the Girder category. The preset uses mm units and the following user-facing variables: B1, B2, D1, D2, D3, D5, D6, T1, T2, and C1. The generated geometry is a symmetric analysis-ready concrete polygon with validation checks for web/flange/haunch dimensions before downstream PMM or future girder analysis.

### UI.SECTION.PRESET1.1 — Simplified section preset selection

The Section Builder now uses a direct **Section Type / Preset** selector so parametric girder presets such as **Parametric I-Girder** are visible without first selecting a category. Geometry family/category is still shown as metadata and is available in an optional browse expander.

### SECTION.PRESET1A.1 — I-Girder Geometry Visual Polish & Dimension QA

Parametric I-Girder now includes an engineering-oriented dimension QA panel in Section Builder. The preset reports the depth stack, web clear zone, top/bottom web transition checks, optional C1 chamfer note, and analysis-compatibility status. Geometry metadata now records I-girder zone depths and ULS PMM / future SLS / future Beam-Girder compatibility tags.

### SECTION.PROP1 — Parametric Section Properties Calculation

- Added gross section property calculation for generated section polygons, including net area, centroid, centroidal Ix/Iy, extreme-fiber distances, and top/bottom section modulus.
- Parametric I-Girder section properties now display analysis-ready Ix/Iy instead of placeholder values.
- These properties provide the basis for future prestressed bridge girder SLS stress checks and station-based Beam/Girder workflows.


### SECTION.PRESET1B — Parametric Plank Girder Geometry

Adds bridge-oriented parametric plank girder presets for **Interior** and **Exterior** girders.  The generated concrete polygon is the precast plank only, using B, b1, b2, b3, H, h1, and h2 in mm.  Composite bridge-girder metadata is retained for future AASHTO workflows: Tslab, manual Be, Ebeam, Edeck, auto n = Edeck/Ebeam, auto Btransformed = n × Be, girder length, and exterior overhang where applicable.  Auto AASHTO effective flange width calculation is intentionally marked as planned; current Be is project/manual input with transformed-width values calculated automatically.

### SECTION.PRESET1B.2 — Plank Girder Stepped-Profile Geometry Hotfix

Corrects the parametric plank-girder concrete outline to follow the user-confirmed reference geometry.  Interior plank width is now generated as B at y = 0 and y = h1, b3 at y = h2, and B - 2*b1 at y = H with symmetric side recesses.  Exterior plank keeps the right exterior edge vertical for full depth; the left interior edge is at x = 0 for y = 0 to h1, x = b2 at y = h2, and x = b1 at y = H.  This is a geometry-shape hotfix only; composite metadata, section-property summary, PMM solver, analysis workspace, and report behavior are unchanged.


### UI.ACTIVE.TABS1
- Added deterministic app-owned active tab highlighting for Workspace, Setup/Sections subpages, Analysis subpages, and Column/Pier ULS checks.
- Active tab state is rendered from `st.session_state` instead of relying on Streamlit's version-dependent selected-state DOM.
- No solver, geometry, load, report, rebar, prestress, or project schema changes.


## UI.ACTION.BUTTONS1

- Highlight primary action buttons with a soft amber fill and bold dark-blue text.
- Apply the same action language to upload browse buttons.
- Mark PMM Run, Save Project, Load Project JSON, and project info update as primary actions.
- No solver, geometry, loads, rebar, prestress, report, or project schema changes.


## UI.SECTION.COMPACT1 — Section Builder compact working layout

- Reflowed Section Builder into a compact working layout: geometry inputs and gross properties now stack in the left column while live preview remains in the right column.
- Reduced preview canvas height and converted preview status into compact cards to remove the large unused left-side whitespace.
- Kept geometry generation, section-property calculations, PMM solver, reinforcement/prestress data, and project schema unchanged.


### UI.PRESTRESS.PREVIEW1 — Prestress preview visible by default
- Shows the Prestress page section preview directly when Prestress is enabled from Section Builder, including passive/reference prestress rows.
- Keeps ordinary rebar hidden from the default Prestress preview; combined rebar + prestress remains a collapsed coordination preview.
- Shows a geometry-only preview when Prestress is enabled but no active prestress rows are available yet.
- No prestress calculation, PMM, SLS, shear/torsion, report, or schema changes.

### UI.PMM.NAV4 — PMM Result View Tabs First + Remove SLS View Tab
- Move PMM result-view tabs immediately under the Flexural (PMM) result-view heading.
- Render decision/summary cards inside the Summary tab rather than above the tabs.
- Remove the local SLS tab from Flexural PMM result views; serviceability belongs in the main Analysis SLS subpage workflow.
- No solver, D/C, load, report, or project-schema changes.

- UI.ANALYSIS.NAV2: promotes Summary to the first ULS Strength Check tab and moves project/code/decision overview into that Summary tab without changing solver logic.

### UI.REBAR.COMPACT1 — Rebar Workspace Commercial Layout Polish
- Reflows the Longitudinal Rebar workspace into compact input/status/preview panels with professional titles and captions.
- Adds explicit active `Analysis Participation: Included` cards and a two-column stored/excluded layout when ordinary rebar is disabled.
- Keeps detailed stored/active rebar tables collapsed by default while preserving the clean section preview without dimension guides.
- No solver, geometry, section-property, SLS, shear/torsion, report, or project-schema changes.

### UI.REBAR.INCLUSION1 — Rebar inclusion state and clean Rebar preview
- Rebar page now labels stored ordinary rebar as excluded when disabled in Section Builder.
- Longitudinal/combined Rebar previews hide section dimension guides; Section Builder remains the dimension source.
- No geometry, solver, rebar parser, or project schema changes.


### UI.REBAR.INCLUSION4 — Rebar Inclusion Visual Regression Check
- Adds tests for Column/Pier, Bridge Beam/Girder, Building Beam/Girder shared prestressed girder, and Building basic RC beam inclusion defaults.
- Confirms explicit include/exclude checkbox state remains the source of truth over workflow defaults.
- Confirms the Rebar disabled-state UI preserves stored rows, labels them excluded, and publishes zero active analysis rebars.
- No solver, geometry, SLS, shear/torsion, report, or project-schema changes.

### UI.REBAR.INCLUSION3
- Align Building Beam/Girder shared prestressed girder ordinary-rebar inclusion defaults with Section Builder.
- Stored ordinary rebar remains preserved but is excluded from analysis when the ordinary-rebar system is disabled or workflow-default excluded.
- No solver, section property, or project schema changes.

### UI.PRESTRESS.PREVIEW2 — Hide Dimension Guides on Prestress Preview
- Prestress page previews now hide Section Builder dimension guides so the canvas focuses on prestressing steel layout.
- Geometry-only and combined reinforcement coordination previews on the Prestress page also suppress dimension guides for readability.
- Section Builder remains the owner of dimension review; no prestress force, parser, geometry, solver, SLS, report, or project-schema logic was changed.

### UI.PRESTRESS.CROSSLAYOUT1 — Cross-section Layout Scale and Padding Polish
- Enlarges the Prestress girder cross-section layout plot and adds explicit x/y inspection padding while preserving equal aspect ratio.
- Moves row labels into the right paper margin and consolidates symmetric left/right row labels so dense 72-strand Railway U-Girder layouts read clearly.
- Keeps strand coordinates, debond metadata, prestress force/loss logic, geometry, solver, report, and project schema unchanged.


### PRESTRESS.DEBOND.VIEW2 — Debonding Schematic Label Cleanup

- Removes `Debond pattern (mm)` from the primary editable strand-layout table; left/right debond length and debonded strand numbers are the source of truth.
- Keeps legacy `Debond pattern mm` backend metadata load/save compatible while deriving the visible row summary from the active inputs.
- Replaces ambiguous schedule wording with a computed `Debond summary` and explicit `... from left/right end` dimension labels.
- Removes repeated per-row sleeve-length labels from the schematic and increases bottom spacing to prevent left-end annotation overlap.
- No solver, effective prestress, prestress loss, SLS/ULS, geometry, section-property, report, or project-schema calculation changes.

### SECTION.ASSEMBLY2 — Railway U-Girder Assembly Panel Alignment

- Replaces the Railway U-Girder assembly editor with rail-specific controls in Section Builder.
- Uses default span `L = 10.0 m`, Case B wet slab support, 50/50 wet slab distribution to webs, editable formwork load, lifting a/L, and lifting impact factor.
- Hides generic repeated-girder fields such as overall system width and tributary load-take-down width for Railway U-Girder.
- Keeps legacy `beam_girder_system_settings` synchronized for downstream span/unit-weight consumers without changing solver equations.

### PRESTRESS.DEBOND.ANALYSIS1 — Station-Based Debonded Strand Participation

- Adds `girder_station_participation_dataframe()` as the explicit solver-adjacent handoff from debonding metadata to station-based analysis previews.
- Uses the current source of truth: `Left debond (m)`, `Right debond (m)`, `Debonded strand nos`, row strand count/area/y, and stage Pe force columns.
- Inside active sleeve zones, only selected debonded strands are removed from effective Aps/Pe; blank selections keep legacy whole-row debonding semantics.
- Surfaces a row-level station participation audit table in Prestress → Effective prestress preview.
- Does not change SLS/ULS equations, transfer-length ramping, development length, anchorage, or final code-certified debonding checks.


### SLS.RAIL.UGIRDER1 — Railway U-Girder Staged Stress Preview

- Adds a guarded Railway U-Girder staged SLS stress preview in Prestress → Rail U-Girder stages.
- Transfer, lifting, and wet slab casting use a one-precast-web section basis; the service row is a full-U Pe reference.
- Consumes the station-based debonded-strand participation handoff so active strands, Aps, Pe, and yps vary by station inside sleeve zones.
- Adds a two-point lifting UDL moment model with lifting point `a/L` and lifting impact factor from the stage settings.
- Does not perform locked-in staged stress superposition, transfer-length force ramping, development length, end-zone checks, final code certification, or ULS solver changes.

### SLS.RAIL.UGIRDER4 — Service Load Handoff Preview
- Added Railway U-Girder service-load handoff rows in `Prestress → Rail U-Girder stages`.
- Active SLS load cases from the Loads tab are evaluated on the full Railway U-Girder gross basis with station-based `Pe_final(x)` from debonding participation.
- Added guarded service-load stress-limit preview using `min(f'c web, f'c slab)`.
- Web-stage locked-in stresses are intentionally not transformed/summed into the full-U service rows; this remains a review-level handoff, not final certified SLS design.


### SLS.RAIL.UGIRDER5 — Final Staged Service Accumulation Preview

- Adds guarded final staged service-stress accumulation for Railway U-Girder.
- Combines locked-in web stresses from transfer/wet casting with final Pe loss increment and active SLS service-load increments.
- Keeps load attribution guarded: Loads tab rows are treated as additional post-composite service increments to avoid double-counting automatic self-weight.
- Adds governing rows, service-limit preview, documentation, and regression tests.
- No ULS, geometry, prestress-loss, anchorage, transfer-length, development-length, report, or project-schema calculation changes.

### SLS.RAIL.UGIRDER6 — Decision Summary + Status Polish

- Added a guarded Railway U-Girder SLS decision summary for Transfer, Lifting, Wet slab casting, and Final service.
- Decision wording is limited to `Preview PASS` / `REVIEW` and remains engineering-review level, not code-certified design.
- No solver equations, geometry, ULS, shear/torsion, prestress-loss, report, or project-schema calculation logic changed.


### SLS.MATERIAL.ROUTING2 — Robust Stage Material Routing for SLS Diagram Guide

- Fixes a missed Analysis-page route where the full-length SLS tensile-limit guide could still show final concrete `f'c` as transfer `f'ci` when `section_preset_key` was stale/missing.
- Railway U-Girder detection now prioritizes generated section geometry metadata, then falls back to section display names and session-state keys.
- Protects Transfer/Lifting routing to precast web `f'ci = 36 MPa` for Railway U-Girder while retaining Construction as web `f'c` and Service extreme-fiber preview as web `f'c` with CIP slab `f'c` audit notes.
- No solver equation, geometry, section-property, prestress-loss, ULS, shear/torsion, report, or project-schema calculation logic changed.

### SLS.MATERIAL.ROUTING1 — Stage Material Strength Routing Audit and Correction

- Corrects Beam/Girder SLS stress-limit preview material routing so Transfer/Release checks use `f'ci` instead of final `f'c` where applicable.
- Railway U-Girder full-length SLS diagram now routes Transfer/Lifting to web `f'ci`, pre-composite construction to web `f'c`, and current top/bottom service preview to web `f'c` with CIP slab `f'c` retained in audit notes.
- Generic prestressed girder transfer checks now use prestress/loss `f'ci` when available, falling back to `0.8 f'c` only when no transfer strength is available.
- Adds regression tests so a transfer-stage preview cannot silently reuse a stale service concrete strength.
- No solver equations, geometry, section-property, prestress-loss, ULS, shear/torsion, report, or project-schema calculation logic changed.


### SLS.TENSION.DEFAULT1 — Bonded Tension Reinforcement Default

- Earlier milestone defaulted the SLS tensile-limit guide to a bonded-reinforcement assumption; QA2 now labels the practical route as `Engineer-confirmed bonded auxiliary reinforcement`.
- Promote legacy Auto defaults once while preserving explicit conservative/no-tension user selections.
- Keep `Model-detected active ordinary rebar at tensile face` available as a manual screening option.
- No solver, material-strength routing, geometry, prestress/debonding, ULS, or report logic changes.

### REPORT.RAIL.UGIRDER1 — Railway U-Girder SLS Engineering Review Report Section

- Adds a report-ready Railway U-Girder staged SLS engineering-review package to Report / QA and Draft Word Report export.
- Exposes guarded tables for geometry, material/stage settings, stage quantities, prestress/debonding, governing staged SLS rows, final service rows, decision summary, and service multi-fiber web/slab stress summary.
- Keeps decision wording limited to `Preview PASS` / `REVIEW` and explicitly states the output is not final code-certified design.
- Adds a Railway U-Girder report-scope limitation so exported reports disclose excluded checks such as transfer/development length, anchorage/end-zone, lifting hardware, creep/shrinkage redistribution, ULS coupling, and final certified design checks.
- No solver equation, prestress force, debond participation, geometry, section-property, ULS, or project-schema calculation logic changed.

### ULS.RAIL.UGIRDER1 — Railway U-Girder ULS Strength Check Framework

Adds a guarded Railway U-Girder ULS strength-check framework after the SLS closeout baseline. The milestone provides Railway U-Girder ULS context detection, active ULS demand summary, Bridge Beam/Girder AASHTO route guardrails, ULS check-readiness matrix, report table registry entries, Word report section, and Report / QA preview panel. This is framework-ready engineering-review evidence only; it is not final code-certified design and is not engineer certification.

Changed areas: `concrete_pmm_pro/analysis/railway_u_girder_uls.py`, report registry/Word export, Report / QA preview, docs, and regression tests. No SLS/ULS solver equations, prestress/debonding logic, section properties, PMM, shear, torsion, or load-combination equations were modified.


### ULS.RAIL.UGIRDER2 — Railway U-Girder Flexure Calculation Evidence

Adds guarded Railway U-Girder ULS flexure calculation evidence after the ULS framework milestone. The evidence consumes active ULS `Mux` station rows, maps station-based dedicated strand participation into the existing strain-compatibility PMM engine, and applies the Bridge/AASHTO LRFD prestressed flexure phi-routing layer. Report registry and Word export now include `Railway U-Girder ULS Flexure Calculation Evidence`.

Decision wording is limited to `Engineering Review PASS` / `Engineering Review FAIL` / `REVIEW`. This milestone remains engineering-review evidence only; it is not final code-certified design and is not engineer certification. No SLS solver equations, ULS solver equations, prestress/debond participation logic, PMM solver equations, shear/torsion/V+T equations, load-combination equations, project schema, or geometry-generator logic were modified.

### ULS.RAIL.UGIRDER3 — Railway U-Girder PSC Shear Route Evidence

Added guarded Railway U-Girder PSC shear route evidence to the ULS framework. The route reads active ULS Vuy station-resultant rows and active provided-stirrup zones, estimates Railway U-Girder bv/d/dv basis, computes an AASHTO LRFD-compatible sectional shear evidence row with φVc, φVs, φVn, D/C, Av/s/spacing detailing guard, and exports the evidence to report registry and Word report.

Changed areas: `concrete_pmm_pro/analysis/railway_u_girder_uls.py`, report registry/Word export, docs, and regression tests. No SLS solver equations, PMM solver equations, prestress/debond participation logic, geometry generator, torsion equation, V+T equation, load-combination equation, or project schema were modified.

Status wording remains guarded: Engineering Review PASS / FAIL for shear evidence only; not final code-certified design. Final certification still requires refined PSC Vci/Vcw/Vp, critical-section/end-region validation, development length, anchorage/end-zone checks, independent benchmarks, and Engineer-of-Record review.


### REBAR.RAIL.UGIRDER2 — Auto Perimeter Apply Commit Hotfix

Fixes a Streamlit rerun/widget-state bug where pressing `Apply generated perimeter layout to Rebar table` after generating Railway U-Girder ordinary perimeter bars could return to the normal Longitudinal Rebar page without the generated rows being committed to the editable Rebar table. The apply action now commits the generated table through a dedicated state helper, bumps the Rebar data-editor revision, clears stale `rebar_data_editor_*` widget states, returns the UI to `Manual table`, and shows an apply-success message so the generated rows are immediately visible and editable.

Changed areas: `concrete_pmm_pro/ui/rebar_page.py`, docs, and regression tests. No SLS/ULS solver equations, prestress/debonding logic, geometry generator, section properties, report certification wording, or project schema were modified.

### REBAR.RAIL.UGIRDER3 — Railway U-Girder Section Builder to Rebar Immediate UI Sync

- Added non-widget steel-system mirrors from Section Builder so `Include ordinary rebar / longitudinal Al` opens the Rebar workspace immediately.
- Rebar page now reconciles the active ordinary-rebar flag from the Section Builder mirror / project metadata before entering the disabled stored-row branch.
- The manual `Enable ordinary rebar / longitudinal Al` button remains only as a stale-state recovery path and should not be required after enabling in Section Builder.
- No solver, geometry, prestress, debond, ULS/SLS, project schema, or report certification logic changed.

### ULS.RAIL.UGIRDER4 — Railway U-Girder Torsion / V+T Guard Evidence

Added guarded Railway U-Girder ULS torsion and combined V+T guard evidence to the ULS framework. The route reads active ULS Tu/Vuy station-resultant rows, active closed-hoop transverse zones, ordinary longitudinal rebar as the Al source of truth, and produces an AASHTO LRFD-compatible engineering-review table with φTcr threshold screen, φTn, torsion D/C, shear D/C handoff, linear V+T review index, At/s, Al, spacing/detailing status, and blocked final-certification notes.

Changed areas: `concrete_pmm_pro/analysis/railway_u_girder_uls.py`, report registry/Word export, docs, and regression tests. No SLS solver equations, PMM solver equations, flexure/shear solver equations, prestress/debond participation logic, geometry generator, load-combination equation, project schema, or report certification wording were modified.

Status wording remains guarded: Engineering Review PASS / FAIL for torsion/V+T guard evidence only; not final code-certified design. Final certification still requires dedicated Railway U-Girder closed torsion-cell calibration, refined PSC torsion effects, calibrated V+T code interaction, development length, anchorage/end-zone checks, independent benchmarks, and Engineer-of-Record review.

### PRESTRESS.DEVELOPMENT1 — Railway U-Girder Transfer / Development Length Evidence

Added guarded Railway U-Girder prestress transfer/development evidence after the ULS torsion/V+T milestone. The route reads the active strand/debonding table and produces a report/Word-ready table with strand row data, fpe/fps basis, transfer length, development length, sleeve termination stations, bonded length to midspan, and left/right development D/C screens.

Changed areas: `concrete_pmm_pro/analysis/railway_u_girder_uls.py`, report registry/Word export, docs, and regression tests. No SLS solver equations, ULS flexure/shear/torsion equations, prestress/debond participation logic, geometry generator, section properties, load-combination equation, project schema, or report certification wording were modified.

Status wording remains guarded: Engineering Review PASS / FAIL for transfer/development evidence only; not final code-certified design. Final certification still requires development benchmark validation, debonded anchorage detailing, anchorage/end-zone bursting/spalling checks, independent benchmarks, and Engineer-of-Record review.

### ANCHORAGE.RAIL.UGIRDER1 — Railway U-Girder Anchorage / End-Zone Evidence

Added guarded Railway U-Girder anchorage/end-zone bursting and spalling evidence after the transfer/development milestone. The route reads the active strand/debonding table, separates bonded end strands from debonded/sleeved strands, reports end-zone Pe transfer force, sleeve-termination force, bursting tie demand, required end-zone/sleeve As, concrete stress preview versus web f'ci, and guarded detailing notes.

Changed areas: `concrete_pmm_pro/analysis/railway_u_girder_uls.py`, report registry/Word export, docs, and regression tests. No SLS solver equations, ULS flexure/shear/torsion equations, prestress/debond station-participation logic, geometry generator, section properties, load-combination equation, project schema, or report certification wording were modified.

Status wording remains guarded: anchorage/end-zone evidence is engineering-review only; not final code-certified design. Final certification still requires project-specific anchorage-zone reinforcement detailing, debonded strand sleeve-termination validation, end-region benchmarks, and Engineer-of-Record review.

### RELEASE.RAIL.UGIRDER1 — Railway U-Girder Engineering-Review Release Closeout

Closed the current Railway U-Girder work as an engineering-review release baseline without adding UI and without changing solver equations. The release adds report/Word closeout tables for release manifest, release readiness, and final-claim guardrails. Accepted release wording is `Railway U-Girder Engineering Review Release Baseline - Closeout Ready`.

This milestone keeps the product boundary explicit: the Railway U-Girder package is closeout-ready for engineering review only; it is not final code-certified design and is not engineer certification. Final certification still requires project-specific detailing, independent benchmark validation, authority-specific criteria, and Engineer-of-Record review.

Changed areas: report release helper, report table registry, Word report export, docs, and regression tests. No UI panels, SLS solver equations, ULS flexure/shear/torsion equations, prestress/debond station-participation logic, geometry generator, section properties, load-combination equations, project schema, or report certification wording were promoted to certified status.


### FINAL.RAIL.UGIRDER1 — Railway U-Girder Final Design-Check Evidence Closeout

This milestone consolidates the Railway U-Girder SLS report evidence, ULS flexure/shear/torsion-V+T evidence, prestress development evidence, anchorage/end-zone evidence, release traceability, Word-report tables, and QA guardrails into a final software design-check evidence package.

Status wording:

```text
Railway U-Girder Final Design-Check Evidence Package - Complete
```

Boundary:

```text
This is not legal Engineer-of-Record certification and must not be represented as Final Code-Certified Design Complete without signed project certification, independent validation, and authority/client acceptance.
```

No SLS solver equations, ULS equations, prestress/debond logic, geometry generation, load combinations, project schema, or Streamlit UI panels were changed by this milestone.
### SHEAR.STATUS2 — Shear Numeric Gate Status Hotfix

- Prioritizes finite shear strength/detailing D/C evidence over stale text status fields in the Beam/Girder compact ULS shear summary.
- Prevents `Shear = FAIL` when the visible shear card and diagram show Strength PASS, Detailing PASS, and D/C values below 1.0.
- No shear equations or solver equations were changed.



## UI.PLOT2 — SLS Decision Plot and Failure Diagnosis Layout

This milestone adds a decision-first SLS stress diagram panel with PASS/FAIL/REVIEW status, controlling stress demand, actual-versus-limit value, utilization, and direct failure/review diagnosis. It also collapses the tensile-limit guide by default and increases plot readability. This is display and diagnostic polish only; it does not change stress equations, Pe(x), material routing, load routing, project schema, or ULS/SLS solver logic.


## UI.PLOT3 — Railway U-Girder Service Multi-Fiber Plot Label Cleanup

Polished the Railway U-Girder service-stage multi-fiber SLS plot so the legend no longer crowds the x-axis label and right-side web/slab limit labels sit outside the plot area. Actual-vs-limit decision cards now use clear comparison symbols where possible. This is display-only UI polish; SLS stress equations, limits, load routing, prestress/debonding logic, and ULS checks are unchanged.

## UI.PLOT7 — Dashed-Line Legend Visibility Polish

Polished the global Plotly rendering layer so dashed engineering limit/capacity traces remain visibly dashed in legend swatches. The global readability wrapper now uses wider legend samples/entries and applies a minimum line width to non-solid dashed traces. This affects SLS stress diagrams, ULS shear/torsion plots, PMM/interaction plots, section/rebar/prestress previews, and report/QA Plotly figures rendered through `st.plotly_chart`.

This is presentation-only polish. It does not change trace coordinates, result dataframes, solver equations, shear/torsion/flexure calculations, SLS stress limits, load routing, widget keys, or project schema.

## UI.COMMERCIAL4.4 — Light-Blue Accordion System

Replaced the previous solid dark-navy Streamlit expander bars with a lighter blue accordion style so secondary audit/detail sections no longer dominate the commercial dashboard visual hierarchy. Collapsed and expanded expander headers now use light-blue surfaces, blue borders, and dark readable text; navy is retained for structural/brand emphasis rather than default accordion fills.

This is presentation-only UI polish. It does not change solver equations, SLS/ULS/PMM/prestress/rebar logic, project schema, widget keys, save/load behavior, or navigation state.

## SLS.STAGE.STRESS.QA2 — Practical Auxiliary Reinforcement Basis

This milestone keeps the SLS staged stress limit source-of-truth from QA1, but changes the temporary tensile-limit guide to match practical precast-girder use. The higher bonded-auxiliary tensile limit can now be traced to either engineer confirmation from design/detailing drawings or model-detected active ordinary rebar at the tensile face. The app no longer presents a disabled ordinary rebar model as a contradiction when the engineer-confirmed drawing basis is intentionally used.

Key UI/QA changes:

- Renamed the user-facing temporary reinforcement route from `Verified bonded tension reinforcement` to `Engineer-confirmed bonded auxiliary reinforcement`.
- Added a separate `Model-detected active ordinary rebar at tensile face` route for projects where ordinary rebar is enabled and modeled.
- Added report/summary traceability for bonded-auxiliary source: engineer-confirmed from drawings versus model-detected active rebar.
- Keeps conservative not-verified limits active when engineer confirmation is selected but not checked, or when model detection is selected but no active tensile-face rebar is detected.
- Rewords the guide card from `Detected tensile fiber` to `Reinforcement basis source` so the UI does not imply model verification when the proof source is external drawings.

No stress equations, Pe(x), debonding, load routing, geometry, material routing, ULS/SLS calculation kernel, Project JSON schema, or result-cache persistence were changed. This is UI/QA traceability and source-basis wording only; development length, anchorage, end-zone, continuity, area adequacy, crack-control, and project certification remain separate engineering reviews.

## CROSSBEAM.WF1 — Portal frame PC crossbeam workflow

Adds the first layout/data-foundation milestone for the Portal Frame Crossbeam — Prestressed Concrete workflow. Scope is intentionally limited to workflow routing, ACI design-code gating, two crossbeam section presets, station-based solid/hollow layout, and top-referenced tendon profile source data. It does not calculate prestress losses, SLS stresses, ULS capacity, anchorage zones, or D-region checks.

## CROSSBEAM.UI1A — Section-Builder-linked segment assignment

Reorders the Portal Frame Crossbeam Sections subpages so Segment Layout follows Section Builder, changes the clean/default crossbeam length to 20.000 m, and replaces free-text Section role / Section ID assignment with a dropdown sourced from the same two Portal Frame Crossbeam presets used by Section Builder. Legacy UI1 solid/hollow rows are migrated to the corresponding preset keys, while existing workflows retain their original Section Builder / Rebar / Prestress navigation and calculation routes.

No prestress-loss, SLS, ULS, shear/torsion, Project JSON schema, result-cache, or report solver logic was changed.

## CROSSBEAM.UI1B — Full-length dashed hollow-void elevation

Updates only the Portal Frame Crossbeam Segment Layout elevation so hidden hollow void boundaries extend across the complete assigned hollow segment and are shown with dashed lines instead of an inset solid cut-out. Hollow segment fill remains lighter for rapid Solid/Hollow recognition. No geometry properties, assignment data, tendon data, solver paths, Project JSON behavior, or non-Crossbeam workflow is changed.

## CROSSBEAM.SECLIB1C — Table-driven active section synchronization

The Crossbeam Project Section Summary now supports single-row selection. Selecting a row safely stages that Section ID as active, then synchronizes the Section Builder geometry editor, gross properties, live preview, and section-management controls on rerun without mutating widget-owned Session State after instantiation. See `README_CROSSBEAM_SECLIB1C.md`.

## CROSSBEAM.SECLIB1F — One-click section open and save-action polish

Replaces the Project Section Summary checkbox selector with a dedicated one-click Edit button column and moves Section-name saving to the app-standard blue primary action button. This is Crossbeam-only UI/state polish; geometry, assignments, Project JSON, solvers, reports, and existing workflows are unchanged. See `README_CROSSBEAM_SECLIB1F.md`.

# SLAB.IMPORT67 — native static shell exports without StepType

The same four CSI export sets now accept **Element Forces - Area Shells with the StepType header absent**, as in a static equivalent-train-load analysis. An omitted step is stored as blank; exported Max/Min and StepNum identities are retained. Force values, case names, units, native record order and duplicate-record safeguards are preserved. No spreadsheet editing or extra confirmation is required.

Malformed known tables now identify the actual missing required headers. The download checklist and import guide explain the optional StepType field. The accepted DESIGN66 calculation, proposal, graph, Summary and Report routes remain the analysis baseline.

Verified against the supplied static workbook: **127,680 native records**, including **109,824 Top Slab records** from S1A, S1C, U1A, U1B, U2A and U2B. Every one of the eight force/moment components and all native record keys matches the workbook exactly. Import readiness and successful chart calculation are software checks; the existing sectional design scope and review requirements still apply. Imported case names are preserved without automatic ULS/SLS classification.

See [SLAB_IMPORT67_NOTES_TH.md](SLAB_IMPORT67_NOTES_TH.md), [SLAB_IMPORT67_VERIFICATION.json](SLAB_IMPORT67_VERIFICATION.json), [REPO_SUMMARY_SLAB_IMPORT67.md](REPO_SUMMARY_SLAB_IMPORT67.md), and [qa/slab_import67_real_inputs.py](qa/slab_import67_real_inputs.py).

## Historical milestone — DESIGN66

# SLAB.DESIGN66 — checked reinforcement spacing proposals

Continue with the same four CSI exports and the existing reinforcement inputs. **Calculate Top slab** now also prepares a bounded bar-spacing proposal with the existing bar diameters and mat levels. Open **Suggested bar spacing · not applied** to review its four-mat checks and the one-way shear still requiring attention. No additional input table or calculation button is added.

Every changed candidate is rechecked with the accepted AASHTO LRFD 2020 sectional equations against all retained native records and available matching support-face vectors. Trial spacings use a 10 mm grid, the cast-in-place clear-spacing trial bound and at most four iterations. This is a checked proposal, not a minimum-steel optimizer or full-deck approval. Unknown aggregate, source coverage, local support regions, shell coupling and anchorage retain their review states.

Current inputs and their charts / Summary remain unchanged. The compact report separates **Current/** from **Proposal/**; changing ballast or nominal UDL metadata reuses a mechanically identical proposal. Revise the existing reinforcement inputs and Calculate again to assess an adopted layout. Full shell interaction, fatigue and SLS remain separate.

The original JSON32 / four-export example produces DB16 spacings of **90 / 80 / 150 / 110 mm** for top longitudinal / bottom longitudinal / top transverse / bottom transverse. Its known shear-tie maxima reduce to **0.935 longitudinal / 0.946 transverse**, while one-way shear still reaches **3.002 longitudinal / 1.264 transverse**. The proposal is **REVIEW**; it is not automatically applied or certified. The example is not the user's future equivalent-UDL reanalysis.

See [SLAB_DESIGN66_NOTES_TH.md](SLAB_DESIGN66_NOTES_TH.md), [SLAB_DESIGN66_VERIFICATION.json](SLAB_DESIGN66_VERIFICATION.json), [REPO_SUMMARY_SLAB_DESIGN66.md](REPO_SUMMARY_SLAB_DESIGN66.md), and [qa/slab_design66_real_inputs.py](qa/slab_design66_real_inputs.py).

## Historical milestone — TOP65

# SLAB.TOP65 — compact Top slab ULS review

Use **Loads → Slab Shell Results** to import the same four complete CSI export sets, then **Analysis → Slab Reinforcement → Calculate Top slab**. New static-equivalent-train case names and blank static StepType are accepted. The existing four top/bottom longitudinal/transverse reinforcement mats are reused.

One calculation prepares signed four-mat N–M envelopes, tension-side shear ties, directional one-way shear, minimum reinforcement and spacing checks. Choose **Plan map** or **Station D/C** for one graph at a time. Station curves show actual maxima with gaps and scope markers, without smoothing. Result Summary and Report / QA read current stored Top slab results; a compact report can be prepared without rerunning a solver.

**CSI load basis / Ballast** records the load model, ballast below the sleeper (default 300 mm), track strip width and nominal pressure. The 2 m / 75 kN/m² defaults are editable assumptions for the previously discussed project, not a universal AASHTO U20 equivalent. These entries do not change imported forces, concrete depth or resistance. Impact/load factors and ballast redistribution are not applied again. Reanalyse CSI and re-export all four sets when its loading changes. A static full-span UDL is not automatically qualified as an envelope of moving-load longitudinal shear or local wheel effects.

**AASHTO LRFD Ninth Edition (2020), sectional ULS scope.** Existing native forces, axes, equations and agreed connection/bearing/one-pass peak exclusions are preserved. A new cast-in-place clear-spacing check uses 5.10.3.1.1 and the existing aggregate input; an unconfirmed aggregate branch remains REVIEW. Direct N–M uses both physical mats, with top/bottom rows identifying bending sign. Nxy/Mxy interaction, simultaneous biaxial shear, local support paths, actual anchorage, fatigue and SLS remain separate. No full-deck certificate is issued. Punching retains the accepted isolated loaded-area route; continuous train UDL does not invent wheel footprints. Interface results remain a read-only link to current Final Composite Flexure checks.

See [SLAB_TOP65_NOTES_TH.md](SLAB_TOP65_NOTES_TH.md), [SLAB_TOP65_VERIFICATION.json](SLAB_TOP65_VERIFICATION.json), [REPO_SUMMARY_SLAB_TOP65.md](REPO_SUMMARY_SLAB_TOP65.md), and [qa/slab_top65_real_inputs.py](qa/slab_top65_real_inputs.py). The example folder contains results from the **original** JSON32 / four exports, not the user's future UDL reanalysis.

## Historical milestone — SHEAR64

# SLAB.SHEAR64 — loaded-area punching and linked interface results

**Analysis → Slab Reinforcement** now groups results into **One-way shear / Punching shear / Reinforcement**, with one primary Calculate button and one plan plot. The accepted AASHTO63 equations, native actions and agreed exclusions are preserved. Punching uses **AASHTO LRFD Ninth Edition (2020) 5.12.8.6** for isolated rectangular normal-force load/reaction areas, with no assumed footprint or added mesh/U punching Vs.

Enter only physical load-area X/Y/L/B; existing materials, thickness and four mat levels are reused. Blank Vu uses an explicitly conservative absolute shell-corner demand bound: a passing bound is sufficient for the force component; an exceeded bound remains REVIEW. Optional independently established factored perimeter Vu receives a direct component check. Missing/excluded source, special perimeters and local support paths are guarded. **Full deck acceptance remains REVIEW REQUIRED.**

The slab page reads each member's current **Flexure → Final — Composite → Interface shear** result using existing hashes and both strength/minimum reinforcement checks. It neither reruns Flexure nor extends a member result to all bridge girder lines. Geometry-only punching edits reuse valid one-way results. Project JSON saves area inputs in metadata, never solver caches.

The unchanged supplied project still has known transverse/longitudinal shear **1.490 / 3.002**. Its actual punching footprints are absent (**NOT CALCULATED**) and interface checks need a current Flexure run after input-only JSON load. Demonstration footprints in the QA results are explicitly examples, never project defaults.

See [SLAB_SHEAR64_NOTES_TH.md](SLAB_SHEAR64_NOTES_TH.md), [SLAB_SHEAR64_VERIFICATION.json](SLAB_SHEAR64_VERIFICATION.json), [REPO_SUMMARY_SLAB_SHEAR64.md](REPO_SUMMARY_SLAB_SHEAR64.md), and [qa/slab_shear64_real_inputs.py](qa/slab_shear64_real_inputs.py).

## Historical milestone — AASHTO63

# SLAB.AASHTO63 — four-mat code checks and support-face sections

The default **Analysis → Slab Reinforcement** workspace uses AASHTO LRFD Ninth Edition (2020) with the existing top/bottom longitudinal/transverse mats. It adds fixed-Nu moment resistance and sufficient flexural-minimum proofs, per-mat temperature/spacing and conservative required straight-bar development lengths. Flexural shear ties use the appropriate strain-based flexural phi.

Girder contact faces use the existing flange width; finite diaphragm faces use native thickness overwrites. Same-element/case eight-component interpolation does not reuse previously excluded corners. Local support footprints remain REVIEW rather than being declared passing. All native source forces, row identities and agreed REVIEW61 masks remain intact.

The supplied example has **known transverse / longitudinal shear D/C 1.490 / 3.002** and shear-tie D/C **1.235 / 2.077**. Direct directional N–M, sufficient minimum proofs and four-mat temperature/spacing pass their scopes. **Full deck acceptance remains REVIEW REQUIRED**: shell coupling, local support paths, punching, interface transfer and actual anchorage are unresolved. These are code-based component checks, not a complete shell or bridge approval.

Use the same JSON and four complete native CSI workbooks. Calculate once; ten graph views and case filters reuse stored results. Heavy source/cut CSVs are prepared only on an explicit request. Legacy research is opt-in and does not feed production results.

See [SLAB_AASHTO63_NOTES_TH.md](SLAB_AASHTO63_NOTES_TH.md), [SLAB_AASHTO63_VERIFICATION.json](SLAB_AASHTO63_VERIFICATION.json), [REPO_SUMMARY_SLAB_AASHTO63.md](REPO_SUMMARY_SLAB_AASHTO63.md) and [qa/slab_aashto63_real_inputs.py](qa/slab_aashto63_real_inputs.py).

## Historical milestone — AASHTO62

# SLAB.AASHTO62 — directional AASHTO slab section checks

The default **Analysis → Slab Reinforcement** workspace now checks AASHTO LRFD Ninth Edition (2020) directional shear, direct N–M strain-compatible strips and tension-side flexural shear ties using the existing four reinforcement mats. One Calculate button prepares all component views; chart/case filters do not rerun the solver. Legacy field and zone-average models are explicitly opt-in under **Case studies / Legacy shell model**.

The unchanged project JSON and four native CSI exports remain the inputs. Agreed girder/diaphragm lines, bearing end zones and the fixed REVIEW61 one-pass peak rule are applied before checking. For the supplied model, 146,432 source rows become **113,232 checked rows**, with **26,240 geometric/end exclusions + 6,960 isolated-peak exclusions**. All original actions and omitted source identities remain auditable.

The supplied model still has component failures: transverse shear **5.845**, longitudinal shear **3.002**, transverse shear tie **1.663**, longitudinal shear tie **2.077**. Direct N–M ratios exclude Nxy/Mxy transfer and are not a replacement for the earlier full N–M field. **Full deck acceptance remains REVIEW REQUIRED**: biaxial shell coupling, critical support sections, anchorage, complete flexural minimum, punching/local railway effects, fatigue and SLS are separate.

See [SLAB_AASHTO62_NOTES_TH.md](SLAB_AASHTO62_NOTES_TH.md), [SLAB_AASHTO62_VERIFICATION.json](SLAB_AASHTO62_VERIFICATION.json) and [qa/slab_aashto62_real_inputs.py](qa/slab_aashto62_real_inputs.py). Existing girder equations and Project JSON input-only behaviour are preserved.

## Historical milestone — legacy workspace

# SLAB.AUDIT58 — correct inflated slab steel demands

The supplied JSON32 and CSI exports reproduce REVIEW57's bottom-longitudinal D/C of **19.734376** exactly. The previous model added an unqualified full shear-chord force to **both** slab faces and let it distort N–M field selection. AUDIT58 withdraws that addition. Steel requirements now belong to the **N–M field only**; an independent one-way shear section screen is shown separately. Nonzero shear keeps **combined N–M–V at REVIEW**, even when independent components pass.

For the supplied project, the four mat maxima change from 19.714 / 19.734 / 10.352 / 11.457 to **4.906 / 5.189 / 1.699 / 2.243** in the N–M-only scope. The separate shear screen still reaches **16.351** at a support corner. These results do not establish design acceptance. Inspect the support/load-transfer region before converting corner demands into reinforcement schedules.

Use the unchanged JSON and four Excel exports, then Calculate once in **Analysis → Slab Reinforcement**. The default **N–M field** map, separate top cards, trace and CSV identify the scope of each ratio. **Overall section** means the maximum known component ratio, not a full interaction ratio.

Verification: **75 focused tests passed**; full-input AppTest checked 146,432 rows through all 10 map views and a case filter with a single solver invocation. See [SLAB_AUDIT58_FINDINGS_TH.md](SLAB_AUDIT58_FINDINGS_TH.md), [SLAB_AUDIT58_VERIFICATION.json](SLAB_AUDIT58_VERIFICATION.json) and the reproducible [real-input QA script](qa/slab_audit58_real_inputs.py).

## Previous milestone — superseded shear-addition method

The REVIEW57/CHECK56 descriptions below record the earlier release. Their unconditional shear-tie addition is withdrawn by AUDIT58.

# SLAB.REVIEW57 — code bending references and governing-check explanations

Continue from CHECK56 in **Analysis → Slab Reinforcement**. Calculate once, then review the existing plan map or the new **Code flexure reference / Minimum sufficient screen** views. **What controls / All-case check breakdown** identifies each mechanism's actual source record and counts unique exceeded/review elements. The trace separates N–M tie demand from conservative shear-tie additions, and CSV exports retain those source identities.

The new conventional 1 m RC strip reference uses actual mat cover, AASHTO α1/β1 and a verified tension-controlled strain before using φ=0.90. It is an independent **N=0 bending reference**. Any nonzero membrane component keeps its result unavailable; the coupled N–M field remains the main result. Passing the stronger **1.33Mu** branch is a sufficient minimum-reinforcement screen. Exceeding it remains **REVIEW**, because the lesser Mcr branch has not been evaluated. No unknown steel ultimate strength is requested or invented.

Existing coupled field resistance, As requirements and preview states are retained. This milestone does **not** establish full 3D N–M–V resistance or complete deck code acceptance. See [SLAB_REVIEW57_HANDOFF_TH.md](SLAB_REVIEW57_HANDOFF_TH.md), [SLAB_REVIEW57_METHOD.md](SLAB_REVIEW57_METHOD.md) and [SLAB_REVIEW57_VERIFICATION.json](SLAB_REVIEW57_VERIFICATION.json).

## Previous milestone

# SLAB.CHECK56 — slab reinforcement calculation and plan map

Import the existing complete CSI Excel exports in **Loads → Slab Shell Results**, then open **Analysis → Slab Reinforcement** and press **Calculate Slab Reinforcement**. The calculator checks every imported Top Slab source record with the existing four reinforcement mats. One plan map shows the governing source corner for each element; view/case changes reuse the stored calculation.

The new sandwich **N–M section preview** preserves simultaneous membrane/bending components, actual bar heights, local 200–350 mm corner thicknesses and CSI signs. It adds conservative shear screens, required/provided reinforcement, explicit REVIEW states, folded equations and source-preserving CSV export. AASHTO component limits are adopted; this is **not complete bridge-deck code acceptance or a validated full 3D N–M–V resistance model**. Anchorage, flexural minimum, local wheel/punching effects, fatigue and SLS remain separate.

Verification: **99 selected tests passed**. Real-file browser QA checked **146,432 slab records** in **6.00 s of solver time** (10.02 s for the measured Calculate-to-render UI flow), one solver call through subsequent filters, full mesh rendering and a 4,576-element CSV. See [SLAB_CHECK56_HANDOFF_TH.md](SLAB_CHECK56_HANDOFF_TH.md), [SLAB_CHECK56_METHOD.md](SLAB_CHECK56_METHOD.md) and [SLAB_CHECK56_VERIFICATION.json](SLAB_CHECK56_VERIFICATION.json).

## Previous milestone

# SLAB.IMPORT55 — deck slab navigation and native CSI import

Bridge workflow: import complete Excel exports in **Loads → Slab Shell Results** and review the shell package and existing four reinforcement groups in **Analysis → Slab Reinforcement**. Keep every worksheet; tables are detected automatically, even when the files are renamed or combined. The page lists the four supplied export sets, exact required tables and any missing data.

This milestone validates input correspondence only. Slab resistance, required reinforcement, D/C and design PASS/FAIL are not calculated. Existing girder ULS/SLS equations and Project JSON schema are unchanged. See [SLAB_IMPORT55_HANDOFF_TH.md](SLAB_IMPORT55_HANDOFF_TH.md) and the downloadable in-app export checklist.

## Previous milestone

# IGIRDER.SLS54 — visible SLS page header

Fix clipped compact SLS navigation by clearing Streamlit's top toolbar on screen. Preserve scroll position, calculation results, other workspace spacing and A4 printing. See [IGIRDER_SLS54_HANDOFF_TH.md](IGIRDER_SLS54_HANDOFF_TH.md).

## Previous milestone

# IGIRDER.SLS53 — compact SLS stress diagrams

Analysis → **SLS / Stress & Cracking** now uses one **Calculate SLS Stress** action for every stage and load case of the selected I-girder. Review one graph at a time by stage, case and concrete component. Settings, equations and source tables are folded. All-case status stays independent of graph filters; Service uses the existing Beam/Slab material checks consistently. Stored results are input-bound and Summary / Report remain read-only.

Full 0–L axes, readable legends, unclipped end markers, source context in chart exports, local horizontal scrolling on phones and A4 vector printing. Existing CODE52 ULS workspaces and stress equations are retained. See [IGIRDER_SLS53_HANDOFF_TH.md](IGIRDER_SLS53_HANDOFF_TH.md) for use, scope and verification.

## Previous milestone

# IGIRDER.CODE52 — compact code-based Shear / Torsion / V–T

One primary Calculate action, two review selectors and one visible Max/Min chart. Calculate **Shear + Torsion** once to populate all three code views. Code checks are the main results; equations/source audit/settings are collapsed. The U-leg/slab LP is retained under **Case study — Composite model (LP)** and runs only on explicit request for the selected girder. It remains separate from production Summary / Report.

Existing code values, FAIL / REVIEW gates and original CSI Tu are retained. No full-composite design qualification is inferred. See [IGIRDER_CODE52_HANDOFF_TH.md](IGIRDER_CODE52_HANDOFF_TH.md) for use, scope and verification.

## Previous milestone

# IGIRDER.COMPOSITE51

U/slab anchorage-plane geometry, exact Calculate-only reuse, and removal of duplicate shear-model rendering. Same nominal Vn/Tn/V–T as COMPOSITE50; full-composite design validation remains incomplete.

See [IGIRDER_COMPOSITE51_HANDOFF_TH.md](IGIRDER_COMPOSITE51_HANDOFF_TH.md) for measured geometry, verification and use.

# IGIRDER.COMPOSITE50 — whole-girder interface shear

แก้ longitudinal shear ที่รอยต่อให้ตรวจจากแรงเฉือนรวมของ girder แยก d interface จาก dv web ตรวจแรงขา U ร่วมกัน และเพิ่ม AASHTO shear/interface reference แบบต่ออนุกรม พร้อมแก้กราฟและตารางหน้า Shear ถูกตัดเมื่อพิมพ์ A4

ผล JSON เดิม: 608/608 interior source vectors; nominal V-only governors 0.790 / 0.813 และ V–T governors 1.554 / 0.938 สำหรับ Interior 2 / Left Exterior ตามลำดับ ยังเป็น model review และยังไม่ใช่ full-composite production-design acceptance

อ่าน [IGIRDER_COMPOSITE50_HANDOFF_TH.md](IGIRDER_COMPOSITE50_HANDOFF_TH.md) สำหรับสูตร ขอบเขต ผลทดสอบ วิธีใช้ และ Repo summary

---

# IGIRDER.VN49 — Shear workspace, strand-layer regression and calculation reuse

Continue from the accepted COMPOSITE48 ZIP. The Shear page now shows its own V-only governor, Vu, nominal Vn with actual M3/N held, paired station chart, and I-hoop/U allocation. Torsion and combined results stay in their own views. A capacity-cap ratio below 1 no longer masks the demand utilization in source-case ranking; genuine cap violations remain visible.

The pooled model does not use strand x coordinates. Missing/invalid transverse positions therefore remain **unknown** instead of blocking every pooled result or being inferred as x=0. Spatial 3D truss analysis retains its strict position requirement. Strand area, y level, sleeves and development remain in the calculation.

Calculation reuse is bounded and session-only: exact geometry/steel responses and a hash-bound shared composite model are reused without rounding loads or interpolating capacities. In the supplied 640-row project, all 608 interior rows calculate even with strand x removed from the regression fixture. All five capacity/utilization measures match COMPOSITE48. A controlled 32-row Shear calculation improves from 8.39/7.29 to 3.42/3.35 seconds; the full nominal-model scan measures 48.96 seconds versus the previously recorded 369.62 seconds. These timings have different scopes.

Verification: 294 selected tests pass; 148 accepted geometry/steel responses are reproduced. Actual app.py Calculate flows pass with missing-x input; Torsion/V–T reuse the model after Shear, and redraw adds no solver calls. Both new full-span charts were rasterized and visually checked. A full browser screenshot review was unavailable because browser download failed.

**The resistance method remains a research nominal model**, using fixed theta, zero Vc and a shared concrete-flow ceiling. This release fixes the calculation blockage, runtime and presentation; it does not establish full-composite LRFD design acceptance. See `IGIRDER_VN49_HANDOFF_TH.md`.

## Previous milestone

# IGIRDER.COMPOSITE48 — Concurrent V/T source scan and hoop-source correction

Continuing development baseline: accepted MODELTN47 ZIP. The joint nominal model includes the I-girder closed hoops, both independent U legs, and developed slab longitudinal steel. Shear, Torsion and Shear + Torsion reuse this model in Analysis. It now calculates every eligible **interior concurrent source vector** and selects the maximum nominal V–T D/C per girder. Individual V-only/T-only governors hold the actual M3/N; the displayed pure Model Vn/Tn intercepts retain M=N=0.

Actual hoop geometry and steel are read independently of the code torsion threshold screen. Below-threshold Tu no longer erases an existing qualified hoop. Original CSI Tu is retained at its reporting point. Blocked rows and physical end exclusions remain visible. No new input fields or Calculate buttons were added.

**This release does not establish full-composite resistance for production design.** The shared concrete-flow ceiling, U-to-slab stress field/nodal transfer and six-resultant resistance about the CSI origin remain unvalidated; no design phi or PASS is inferred. A complete justified code stress field/STM is an alternative to nonlinear strain/slip analysis, but the current LP is not such a verified field. See `IGIRDER_COMPOSITE48_HANDOFF_TH.md` for the exact method gaps and research references.

Verification: 212 selected tests pass, including 22 new test cases; all 608 interior rows of the supplied 640-row JSON calculate, including 122 recovered below-threshold rows. All 486 previously numeric rows retain the same results. The 32 physical end rows require a separate end-region method. AppTest verifies the three actual Calculate flows and stored-only redraw; browser screenshot QA was unavailable. Project JSON continues to save inputs; model results remain separate from production Summary / Report / QA.

## Previous milestone

# IGIRDER.MODELTN47 — U + slab Model Tn in Analysis

Composite I-girder Torsion and V–T now show the stored **Model Tn with both U legs and slab longitudinal steel** as the primary Analysis result. The same nominal model supplies Vn and concurrent V–T D/C. The I-hoop code route and its full-span charts remain under Reference checks. Existing inputs and Calculate buttons are reused.

Model values remain nominal **MODEL REVIEW**, with no inferred phi or design PASS. The model selects one maximum-|reported CSI Tu| source row per girder, not a full-span governing V–T search. Result Summary / Report / QA retain the separate code-check results. No resistance equation, raw CSI force, or Project JSON persistence policy changed. See `IGIRDER_MODELTN47_HANDOFF_TH.md`.

## Previous milestone

# IGIRDER.EDIT33 — Continuous dowel input editing

Committing a second cell no longer loses that value or collapses **Dowel detail**. The dimension, independent layout and optional joint-force editors keep a stable input seed while editing; the changing missing-dimension count retains the same expander. Leaving and reopening the input view reuses accepted values, and loading another Project JSON clears old editor deltas. Copy zoning deliberately replaces the editor seed.

Use your latest saved Project JSON. This update changes UI session state only; engineering equations, raw CSiBridge loads and the Project JSON schema are unchanged. See `IGIRDER_EDIT33_HANDOFF_TH.md`.

## Previous milestone

# IGIRDER.DOWEL32 — U-dowel dimension guide

The existing **Dowel detail** form now includes a transverse U-dowel drawing and an enlarged 90° hook. A–F on the drawing match the input rows, and current values appear next to each reference. Open **How to measure A–F** for measurement endpoints. Unknown lengths stay blank; the drawing is schematic and does not infer or verify actual bar geometry.

Use your existing Project JSON, including `I_Girder_20m_FLEXURE31_REVIEW.json`. In Analysis → ULS Strength → Flexure → Final — Composite, enable **Edit composite / dowel inputs** and expand **Dowel detail**. This is a presentation-only update; equations, raw CSI forces, input schema, and result persistence are unchanged. See `IGIRDER_DOWEL32_HANDOFF_TH.md` for validation and release details.

## Previous milestone

# IGIRDER.FLEXURE31 — One Final Flexure workspace

Final Composite now has one **Calculate Flexure** command. It calculates sectional flexure and girder–deck interface shear for all imported girders or the design member. Optional U-dowel screening uses the same command and remains separate from production resistance acceptance. One girder and one Max/Min chart are displayed by default; Both is explicit. Chart, case, origin and zoom controls only read stored results.

Load `I_Girder_20m_FLEXURE31_REVIEW.json`, then Analysis → ULS Strength → Flexure → Final — Composite. The supplied JSON records the requested separate cut-end review at exact physical 0/L only. Span D/C does not certify end-region/anchorage acceptance: original end results and overall REVIEW remain visible in Analysis, Result Summary and Report / QA.

`CSI source M3` shows original imported moments. `Demand / capacity` uses transported Mux at the resistance centroid. Missing φMn has a labelled grey gap; no endpoint force is zeroed and no resistance is interpolated. The end-reference audit explains P × eccentricity and retains raw values. Project JSON saves inputs and the scope choice; the new Final Flexure and interface result tables stay in the session.

See `IGIRDER_FLEXURE31_HANDOFF_TH.md`. Resistance equations and raw CSI loads are unchanged. Full composite Tn/V–T resistance remains outside this UI milestone.

## Previous milestone

# IGIRDER.INPUT30 — Simple composite inputs

Named Girder worksheets now use the normal ULS import path. Beam/Slab worksheets from the same file are retained as source inputs in Project JSON and never imported as extra girders. Dowel details and optional manual joint forces are collapsed; existing section, reinforcement and Loads inputs are reused.

Run `streamlit run app.py` and open `I_Girder_20m_INPUT30_DRAFT.json`. See `IGIRDER_INPUT30_HANDOFF_TH.md`. The draft adds DL/U2A component reference inputs only; active Loads and measured dowel unknowns are preserved.

Selected tests: 271 passed (20 new INPUT30 cases); actual-file import and full-app Streamlit AppTest passed. Browser screenshot QA was unavailable. Resistance equations are unchanged: automatic interface-reaction recovery and full composite Tn/V–T resistance remain unimplemented.

# Concrete Section Pro — IGIRDER.JOINT29

Analysis now checks U-dowel tension-hook / straight development and actual bonded-leg cover through the local girder polygon. A separate cracked-joint equilibrium model screens simultaneous interface shear, opening and roll using one shared developed-steel supply, compression-only contact and zero-cohesion friction. Joint mx is entered from a free-body/interface source; Girder Tu is never substituted.

Run `streamlit run app.py`, open `I_Girder_20m_JOINT29_DRAFT.json`, then Analysis → Final Composite → U-dowel torque transfer. Complete independent dowel ranges, measured anchorage, leg spacing, coating/region and actual joint actions before Calculate U-dowel Joint. Unknowns remain unknown. All mechanism results retain REVIEW for composite design and stay outside production ULS / Summary / Report-QA. Full composite V–T and biaxial resistance remain incomplete. See `IGIRDER_JOINT29_HANDOFF_TH.md`. 251 selected tests passed, including 40 new cases; full-app Streamlit AppTest passed. SciPy is now a runtime dependency.

## Previous milestone

# Concrete Section Pro — IGIRDER.DOWEL28

Girder–deck interface checks now select the actual crossing reinforcement: extended girder stirrups, explicitly linked dowels, or an independent dowel layout. Independent dowels supply their own diameter, crossing-leg count, spacing, fy and longitudinal extents; missing ranges retain REVIEW without a stirrup fallback. Editing I-hoops cannot increase independent dowel Avf.

Run `streamlit run app.py` and open `I_Girder_20m_DOWEL28_DRAFT.json`. In Analysis → Final Composite → Interface Shear → Dowel layout, enter actual start/end stations for C/D/E before calculating. The supplied DB12 @70/@150/@200 draft intentionally leaves those ranges unknown. Existing Loads and slab longitudinal inputs are preserved. See `IGIRDER_DOWEL28_HANDOFF_TH.md`. Selected tests: 211 passed, including 20 DOWEL28 test cases. Full composite shear–torsion and biaxial resistance remain incomplete; dowels do not enlarge the torsion cage automatically.

## Previous milestone

# Concrete Section Pro — IGIRDER.EQUILIBRIUM27

The existing ULS uploader now provides an optional read-only Girder/Beam/Slab equilibrium audit. Declared static exports are matched by physical source identity, component offsets are identified from P/M2/M3, and torque is independently reconstructed and checked at held-out stations. Component envelopes are not treated as simultaneous vectors. Loads and strength/acceptance logic are unchanged.

Use the CSIREF26 Project JSON and `streamlit run app.py`. See `IGIRDER_EQUILIBRIUM27_HANDOFF_TH.md`. Selected tests: 178 passed, including 15 new tests. The supplied DL file reconciles all six girders at 276 cuts. Full composite shear–torsion resistance remains incomplete.

## Previous milestone

# Concrete Section Pro — IGIRDER.CSIREF26

CSI reporting origins are now saved with each native Loads source. Analysis transports moments to its station-specific resistance origin while retaining all raw Loads values and recording the mapping in Calculation trace. Use the supplied `I_Girder_20m_CSIREF26.json`, or configure the source reporting point in Loads → `CSI force output reference`, then recalculate Analysis.

This is the force-reference integration milestone. Full composite shear–torsion and biaxial resistance remain incomplete; Girder resultants checked against the partial I-hoop mechanism retain REVIEW qualification. See `README_IGIRDER_CSIREF26.md` and `IGIRDER_CSIREF26_HANDOFF_TH.md` for setup, tests and scope.

## Previous milestone

# Concrete Section Pro — IGIRDER.ENDSECTION18

Based on the complete accepted AUTOLOAD17 ZIP. Section Builder → Solid End Sections defines independent left/right solid lengths, linear side tapers, end width/chamfer and physical cut-end coordinates on the existing Loads axis. The station preview displays the actual polygon and longitudinal zoning.

ULS Flexure, Shear, Torsion, Shear + Torsion and interface checks use local geometry. Final-composite flexural/depth calculations retain the existing deck; web/torsion remain precast. Polygon/context caches are isolated within Calculate, and JSON persists inputs only. Vn/Tn capacity diagrams sample geometry changes using labeled same-case interpolated forces; these samples never become design PASS rows. Original CSI forces and girder assignment are preserved.

Run `streamlit run app.py`. See `IGIRDER_ENDSECTION18_HANDOFF_TH.md` and `qa/evidence/igird_endsection18/`. Different girder details still require separate models. SLS stresses/deflection and FE stiffness/self-weight retain the existing uniform-section model. Bearing/D-region, end reinforcement and CSI moment-reference confirmations remain separate.

## Previous milestone

# Concrete Section Pro — IGIRDER.SHEARCOMP1

Final-Composite V/T now uses developed flexural C/T resultants and force-weighted de for dv, with precast web properties retained. Stirrup spacing stress includes phi. Bearing centerlines/internal faces are distinct from physical strand cut ends; unknown bearing lengths do not create fictitious support faces or near-support exemptions.

Run `streamlit run app.py`. See the new handoff and `docs/CONCRETE_SECTION_PRO_IGIRDER_SHEARCOMP1_REVIEW_2026-10-05.md`. The `examples/` model records bearing CL x=0.4/19.6 m and the unchanged latest Excel forces, including original P; import your own P=0 Excel if that is the intended source. No material/anchorage/interface confirmation is inferred. Recalculate Interface/Shear/Torsion/Combined for the current inputs. Full-span diagrams retain genuine missing-source markers.

## Previous milestone

# Concrete Section Pro — IGIRDER.VTQA1

Shear, Torsion and Combined V+T show one maximum original D/C curve and limit=1.0 by default. Choose a single case for the signed force/resistance diagram. Three main cards and collapsed traces reduce workspace clutter; detailed source checks remain available.

Analysis exposes missing longitudinal material and development inputs. Define actual verified fy/Es, confirm real continuity/anchorage/ld, then Calculate Shear + Torsion once to refresh all three V/T results. Independently known partial checks stay visible when another source is missing; missing overall acceptance stays unresolved.

Automatic I-girder dv now uses conservative 0.72h instead of treating an area centroid as the code's force-weighted de. Verified manual dv remains available. Unknown bar materials receive zero stiffness, developed As is credited once, fc design limits are 15 ksi for shear and 10 ksi for torsion/required combined checks, and M2/V3 remain raw references. V/T geometry is precast; composite deck torsion is not certified. The user supplies P=0 in Excel. Native Max/Min source coupling gates remain.

Run `streamlit run app.py`. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_VTQA1_2026-10-04.md`, `IGIRDER_VTQA1_CALCULATION_REVIEW_2026-10-04.md` and `qa/evidence/igird_vtqa1/` for source provisions, assumptions and verification. Hypothetical QA materials/development are not production inputs.

## Historical milestones

# Concrete Section Pro — IGIRDER.CHART2

Shear and Torsion legends identify native Max/Min occurrences and show resistance/reference quantities once. Exact finite copies are drawn once, while genuinely different case-dependent paths and gaps remain. Precast I-Girder V/T Analysis uses the established browser Plotly renderer with full source hover.

Combined V+T now reports completed check rows and finite-D/C rows, with a visible required-input/source-action table. Missing torsion-qualified cage inputs or unresolved longitudinal materials retain their engineering gates; no capacity is assumed to make a graph. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CHART2_2026-10-04.md` for verification and input guidance.

# Concrete Section Pro — IGIRDER.CHART1

Final Composite charts now use short, distinct Max/Min/occurrence labels and show φMn once in the legend. Exact coincident resistance paths are drawn once; genuinely different capacity paths and missing-equilibrium gaps remain. Interface shear shows one blue maximum scalar demand envelope and one dashed-red minimum available resistance curve, with original source cases on hover. All original row-based calculations and D/C remain in the audit.

Run `streamlit run app.py`, open Analysis → ULS → Flexure → Final Composite and calculate the required checks. Hover shows full source identity. The user's P=0 decision is entered in their Excel; no automatic axial override is added. Import, signs, material/development rules and all engineering equations are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CHART1_2026-10-04.md`, `tests/test_igird_chart_display.py` and `qa/evidence/igird_chart1/`. `python qa/igird_chart_ui_verify.py` exercises full app.py and exports exact trace previews. PNGs use Matplotlib; standalone Plotly HTML is interactive. These are not browser screenshots, and browser print-layout verification is not completed.

## Previous milestone

# Concrete Section Pro — IGIRDER.CSIIMPORT2

The Precast I-Girder ULS panel now accepts the user's unchanged latest single-sheet CSiBridge Excel through one uploader with automatic format detection. All 80 rows, both Max/Min, repeated stations and all six signed force components are retained. Existing app-column CSV/XLSX tables use the same uploader. The previous format radio is removed.

Run `streamlit run app.py`. On Loads → ULS → Final Composite import, use kN / kN-m, upload the original Excel, confirm Left Exterior Girder and the actual FEA envelope name, then **Replace current rows**. No header changes, units-row deletion or manual force edits are required. Existing native multi-sheet imports still select the largest |M3| girder demand by default.

**M2→Muy and V3→Vux are reference only**, as confirmed by the user. P→Nu, V2→Vuy, T→Tu and M3→Mux feed the existing relevant checks. All six source quantities are retained in Analysis inputs and in the stored result trace. CSI signs and the existing internal Nu = −P conversion remain intact. Engineering equations and source-coupling REVIEW/FAIL gates are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CSIIMPORT2_2026-10-04.md`, `tests/test_igird_csi_import_auto.py` and `qa/evidence/igird_csiimport2/`. `python qa/igird_csi_import_ui_verify.py` exercises the full app.py using original workbook upload bytes, including a persisted old legacy-format selection, all 480 force values, actual Final Calculate, reference trace and legacy compatibility. This is Streamlit AppTest verification; browser visual verification is not completed.

## Previous milestone instructions (historical)

The CSIIMPORT1 format-radio steps below are superseded by automatic detection above.

# Concrete Section Pro — IGIRDER.CSIIMPORT1

The Precast I-Girder Loads importer now reads native multi-sheet CSiBridge member forces with a units row and both Max/Min bounds. Select **Left Exterior Girder**, the largest |M3| in the supplied workbook. All 80 original rows remain, including repeated stations; no force component or sign is mixed across rows. The default critical-member comparison ranks |M3| demand, with separate |V2| and |T| leaders. It does not establish the critical member by capacity ratio for every check.

Run `streamlit run app.py`. On Loads → ULS → Final Composite import, keep **CSiBridge girder forces**, upload the native workbook, check the selected worksheet and FEA envelope name, then **Replace current rows**. Download the new Excel template from the same panel. The existing **App columns (legacy)** import remains available. Native imports normalize declared units to kN/kN-m and preserve raw CSI signs; the FLEXSIGN1 Nu conversion remains inside the solver.

Final Composite screens all 80 imported rows, including the negative Mux bound. Negative composite acceptance and concurrent Mu/Nu/Vu/Tu are not established by this worksheet. Numerical screening and failures remain visible; coupled PASS is REVIEW. Use CSiBridge Correspondence / governing load-case actions for final coupled acceptance. M2/Muy is preserved but the developed flexure route remains primary-axis Mux only. The current AASHTO development, φ, prestress, geometry and detailing rules are unchanged.

See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_CSIIMPORT1_2026-10-04.md`, `tests/test_igird_csi_import.py` and `qa/evidence/igird_csiimport1/`. The shipped Excel asset is static; the app needs no spreadsheet-authoring dependency. `python qa/igird_csi_import_ui_verify.py` runs the production Streamlit import and Calculate controls using fixture upload bytes. This is an AppTest check, not a browser visual verification.

## Previous accepted milestone

# Concrete Section Pro — IGIRDER.FLEXSIGN1

Precast I-Girder ULS now accepts unchanged CSiBridge frame P signs through an explicit Loads / Analysis convention selector. Raw P is positive in tension; solver Nu is positive in compression and equals −P. Flexure, Shear, Torsion and concurrent Shear + Torsion share this conversion. All imported table values are preserved. See `PROJECT_HANDOFF_CONCRETE_SECTION_PRO_IGIRDER_FLEXSIGN1_2026-10-04.md` and `docs/CONCRETE_SECTION_PRO_FLEXSIGN1_REVIEW_2026-10-04.md`.

Run the complete application with `streamlit run app.py`. For the user's unchanged CSiBridge table select **CSiBridge / CSI frame P — positive tension, negative compression**, then Analysis → ULS → Flexure → Construction / Final Composite → Calculate. The supplied corrected JSON already declares this convention and uses a 250 mm deck matching the latest PDF. Legacy JSON files retain the old compression-positive interpretation until explicitly selected; review the selector before Calculate.

The FLEXDEP1 AASHTO LRFD 9th Edition (2020) transfer/development and strain-based φ solver remains active. Physical beam / strand cut ends are confirmed at x=0 and 20 m, with zero extensions. Under the current unverified bar anchorage, the corrected Final result still fails at both ends: no equilibrium at x=0; φMn=1.049 < Mu=4.472 kN-m at x=20. The new handoff supersedes earlier compression/tension interpretations for this CSiBridge source. Numeric section PASS does not close material, detailing or composite-action acceptance gates.

## Earlier Crossbeam milestone

Eliminates the deployed Crossbeam ULS trace-owner `NameError` by removing the runtime helper lookup and resolving `Zone-owned` versus `Segment-owned` directly at every render site. All ANALYSIS4C7C engineering and chart behavior remains unchanged. See `README_CROSSBEAM_ANALYSIS4C7C2.md`.

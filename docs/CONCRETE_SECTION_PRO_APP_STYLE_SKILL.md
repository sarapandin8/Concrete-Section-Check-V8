# CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md

**Skill name:** Concrete Section Pro App Style Skill  
**Purpose:** Reusable engineering-app UI/UX, dashboard, chart, report, and development standard.  
**Primary reference app:** Concrete Section Pro  
**Stable reference baseline:** `concrete-section-pro_ULS-CHART-UI2-legend-status-polish.zip`  
**Baseline lineage:** started from stable `SLS-RAIL-UGIRDER9-lifting-debond-audit`, then added `ULS-CHART-UI1` and `ULS-CHART-UI2` chart/UI polish.  
**Important exclusion:** Do **not** reintroduce the later `STATE-RESULT-PERSIST1/2/3x` analysis-cache persistence experiments unless explicitly requested and separately scoped.

---

## 0. How to use this skill

When a new ChatGPT chat, agent, or developer is asked to build any engineering app using the Concrete Section Pro style, it must read and follow this file before writing or modifying code.

Use this skill for:

- structural engineering apps
- bridge engineering apps
- geotechnical/foundation apps
- load combination tools
- section capacity tools
- stress/check dashboards
- calculation/report-preview apps
- any Streamlit engineering app that should look and behave like Concrete Section Pro

This skill defines **style, interaction model, engineering dashboard behavior, graph language, status wording, and development discipline**. It does not replace the engineering code formulas for a new domain.

---

## 1. Core philosophy

Concrete Section Pro is not a raw calculator. It is a **professional engineering decision-review workspace**.

Every app using this style must help the user answer these questions quickly:

1. What is the active model/workflow?
2. What design code is being used?
3. What checks have been run?
4. What is passing, failing, incomplete, blocked, or requiring review?
5. What controls the design?
6. Which case/station/stage controls?
7. What should the engineer do next?
8. Is the result ready for report/QA?
9. What limitations or scope guards remain?

The app must feel like commercial engineering software: clear, conservative, traceable, and decision-first.

---

## 2. Non-negotiable rules

### 2.1 Do not over-certify

Never imply that a check is fully code-certified if it is only a preview, scoped route, preliminary review, or partial gate.

Use clear labels such as:

- `Preview PASS`
- `Preview FAIL`
- `REVIEW REQUIRED`
- `Scope guard`
- `Not certified by this gate`
- `Detailed review remains separate`

### 2.2 Do not hide engineering limitations

If a check excludes seismic detailing, anchorage, development length, staged construction, second-order effects, fatigue, buckling, creep/shrinkage, or code-specific detailing, state it visibly.

Example wording:

```text
Seismic confinement/detailing review remains separate; this gate does not certify plastic-hinge confinement, hoop anchorage, lap-splice confinement, or seismic detailing.
```

### 2.3 Do not create ad-hoc graph styling

All graphs must follow the shared engineering chart standard in this file. Do not create one-off Plotly styles, random colors, random legend names, or inconsistent markers.

### 2.4 Do not let diagnostic output become production output

Diagnostic/debug results must never overwrite production results, feed Result Summary, feed Report/QA, or be saved as engineering results.

### 2.5 Do not rerun solvers in summary/report pages

Pages such as `Result Summary` and `Report / QA` are read-only review pages. They must use stored results only and must not trigger solver reruns.

### 2.6 Prioritize core calculation reliability over convenience features

If a convenience feature such as result persistence, export, or diagnostics causes core analysis to slow down or become unreliable, remove or defer the convenience feature.

### 2.7 Always preserve accepted baselines

For code work, always start from the latest accepted ZIP baseline supplied or confirmed by the user. Do not rebuild from memory. Do not reapply rejected experimental changes.

---

## 3. Default workspace structure

A Concrete Section Pro style app should generally use this workspace structure:

```text
Setup
Model / Sections
Loads
Analysis
Result Summary
Report / QA
```

For non-section apps, adapt the names while preserving the roles:

| Concrete Section Pro page | Generic engineering-app role |
|---|---|
| Setup | project, code, units, workflow, assumptions |
| Sections / Model | geometry, materials, reinforcement, model definition |
| Loads | demands, cases, combinations, staged loads |
| Analysis | solver/check workspace |
| Result Summary | decision dashboard from stored results |
| Report / QA | read-only report readiness, traceability, QA/export |

Do not combine all functions into one long page. Keep workflow stages distinct.

---

## 4. Global app shell

Use a clean, professional app shell:

- top header card with app name and short subtitle
- workspace tabs or sidebar navigation
- active context strip showing workflow, model/section type, design code, and units
- soft card backgrounds
- rounded cards
- clear section headers
- consistent badges
- generous spacing
- no dense wall of controls without grouping

### 4.1 Header pattern

Each main workspace should have a page header card:

```text
[icon badge] Workspace / Page title
Professional one-line description.
[right badge: WORKSPACE NAME]
```

Example:

```text
RS  Result Summary Dashboard
Professional decision dashboard for stored analysis results. Opening Result Summary does not rerun PMM, ULS, or SLS.
```

### 4.2 Active context strip

Every workspace should show key context at the top:

```text
WORKSPACE
ACTIVE WORKFLOW
MODEL / SECTION TYPE / PRESET
DESIGN CODE
UNITS
```

Example:

```text
Workspace: Result Summary
Active Workflow: Bridge Beam / Girder — RC / Prestressed Member
Section Type / Preset: Railway U-Girder
Design Code: AASHTO LRFD 9th Edition
Units: mm, MPa, N, N-mm
```

This prevents users from reviewing results under the wrong workflow/code/unit context.

---

## 5. Status language

Use a consistent status taxonomy.

### 5.1 Primary result statuses

| Status | Meaning | Visual intent |
|---|---|---|
| `PASS` | check is complete and utilization/gate passes | positive/success |
| `FAIL` | check is complete and fails | critical/red |
| `Preview PASS` | preliminary/scoped check passes | positive but scoped |
| `Preview FAIL` | preliminary/scoped check exceeds limit | critical but with preview wording |
| `REVIEW` | engineering review needed; not automatically pass/fail | amber/warning |
| `REVIEW REQUIRED` | strong review requirement | amber/warning |
| `NOT CALCULATED` | check has not run | neutral/amber |
| `LAYOUT READY` | input layout exists but calculation not run | neutral/info |
| `LAYOUT REQUIRED` | required input layout missing | amber |
| `BELOW THRESHOLD` | demand below threshold; detailed check not governing | green/info |
| `SOURCE BLOCKED` | combined check cannot be accepted because source gate failed | red/critical |
| `NOT REQUIRED` | code route says item not required | neutral/info |
| `INCOMPLETE` | required analysis set is not complete | amber |
| `STALE` | result exists but inputs changed | amber/red depending severity |

### 5.2 Avoid misleading PASS

If a sub-check passes numerically but a source gate fails, the overall combined check must not show `PASS`.

Example:

```text
Interaction D/C = 0.947; source gate BLOCKED
```

Display status:

```text
SOURCE BLOCKED
```

not:

```text
PASS
```

### 5.3 Partial vs full status wording

Use partial wording only when not all required checks are available.

Bad:

```text
ULS PARTIAL CHECK — PASS
```

when all ULS checks have been run.

Good:

```text
ULS STRENGTH CHECK — PASS
```

When checks are missing:

```text
ULS PARTIAL CHECK — REVIEW
```

---

## 6. Dashboard card pattern

### 6.1 Metric/status cards

Metric cards should contain:

- uppercase small label
- large status/value
- concise engineering explanation
- optional source/case/station line

Example:

```text
OVERALL STATUS
FAIL
Failing checks: SLS Stress (Preview FAIL; 3.077). Review source Analysis before report issue.
```

### 6.2 Result Summary top cards

Result Summary should usually include:

```text
Overall Status
Design Code
Critical Check
ULS/SLS Completeness or module completeness
Report Handoff
```

Example:

```text
Overall Status: FAIL
Design Code: AASHTO LRFD 9th Edition
Critical Check: SLS Stress — Preview FAIL · 3.077 · AUTO-LIFT
Completeness: ULS 4 · SLS complete, but failing check exists
Report Handoff: Review required
```

### 6.3 Required Actions table

A dashboard must not only say FAIL. It must tell the engineer what to review next.

Required Actions columns:

```text
Priority | Module | Issue | Required Action
```

Example action:

```text
Review Lifting stage (AUTO-LIFT) tension at x = 2.000 m / Top fiber; utilization = 3.077. Adjust lifting/support-stage assumptions, release strength, prestress losses, temporary reinforcement, or section/stage geometry before Report / QA.
```

Keep table action concise; move long explanation to expander or note if needed.

---

## 7. Result Summary page standard

The `Result Summary` page is a decision dashboard. It is not a solver page and not a full report.

### 7.1 Required subpages

Use:

```text
Overview
ULS Summary
SLS Summary
Traceability
```

Adapt names for non-structural apps, but keep the same logic:

- Overview = executive decision dashboard
- Strength/ULS/Safety Summary = ultimate/strength checks
- Service/SLS/Performance Summary = serviceability/performance checks
- Traceability = stored result sources, hashes, cache status, code basis

### 7.2 Overview responsibilities

Overview must show:

- overall status
- design code
- critical check
- completeness
- report handoff readiness
- executive result state
- governing result table
- required actions

### 7.3 Critical check ranking

Critical check ranking must consider all meaningful utilization values, not just the first D/C column.

For example, if a row has:

```text
Strength D/C 0.422; Av/s min D/C 1.893
```

then `1.893` can govern over an SLS utilization of `1.830`.

Ranking must include:

- strength D/C
- detailing D/C
- stress utilization
- source-blocked conditions
- SLS utilization
- blocked/failure priority

### 7.4 Report handoff states

Use:

```text
Not ready
Review required
Ready
```

Do not display `Ready` if there are FAIL, BLOCKED, Preview FAIL, or incomplete required checks.

---

## 8. Report / QA page standard

The Report / QA page is a read-only, stored-result review page.

### 8.1 Required behavior

Report / QA must:

- not rerun solvers
- show stored results only
- align with Result Summary status
- show design code edition clearly
- show report readiness
- show critical check if failing
- include traceability / diagnostics expanders

### 8.2 Top cards

Recommended cards:

```text
Overall status
Critical check
Report readiness
Design code
Runtime mode
```

Example:

```text
Runtime mode
Read-only
Report / QA does not rerun PMM, ULS, SLS, or verification solvers.
```

### 8.3 Do not mislead with readiness wording

If stored results exist but a check fails, do not say:

```text
Ready to review
```

without context.

Use:

```text
Review required
Stored results are available, but failed checks must be resolved or documented before report issue.
```

---

## 9. Analysis page standard

Analysis is the only workspace where solvers/checks should run.

### 9.1 Analysis page structure

For each analysis module:

1. selected command card
2. primary action button
3. status/metric cards
4. compact check table
5. check-specific workspace
6. graph/diagram
7. audit/details expanders
8. limitations/scope notes

### 9.2 Compact check table

The compact table must summarize calculated and pending checks.

Typical columns:

```text
Check | Status | Governing x/station | Case | Demand | Capacity | Utilization | Required Action
```

For stage-based checks:

```text
Module | Check | Status | Code basis | Governing case/stage | Station/point | Demand | Capacity/Limit | D/C/Util. | Source
```

### 9.3 Action buttons

Primary action buttons must clearly state what will be calculated:

```text
Calculate Flexure
Calculate Shear
Calculate Torsion
Calculate Shear + Torsion
Run SLS Stress
```

Do not run hidden expensive solvers from tabs intended only for review.

### 9.4 Not calculated state

When a check has not been run, show a clear message:

```text
Flexure has not been calculated for the current inputs. Press Calculate before reviewing capacity, utilization, audit tables, or diagrams.
```

---

## 10. Chart and figure standard

Charts are first-class engineering figures, not decorative plots.

### 10.1 Shared chart requirements

All charts must use a shared standard for:

- figure size
- margins
- fonts
- legend placement
- line widths
- marker styles
- axis title format
- grid style
- governing markers
- limit lines
- captions
- footer notes

Do not create chart styling inline from scratch for each graph.

### 10.2 ULS Beam/Girder chart standard

Use wide, readable full-span charts.

Concrete Section Pro accepted standard:

```text
Static ULS chart export target: approximately 1440 × 560 px
Display: scaled to content width
Purpose: full-span readability
```

Every Beam/Girder ULS chart should follow the same width/layout standard:

- Flexure
- Shear
- Torsion
- Shear + Torsion

### 10.3 Legend rules

Legend names should be short. Put detailed meaning in the caption.

Good legend labels:

```text
Demand Mux
φMn
Gov. flexure
Stress D/C
Transverse D/C
Limit = 1.0
Gov. V+T
```

Avoid long legend labels such as:

```text
Stress D/C (V+T stress) — Strength I
Transverse D/C ((Av+2At)/s)
```

The caption can explain:

```text
Stress D/C is the combined concrete stress interaction; Transverse D/C is the provided transverse reinforcement utilization.
```

### 10.4 Hide non-applicable traces

Do not show irrelevant graph traces or legends.

Example:

If `Longitudinal Al = NOT REQUIRED`, then hide:

```text
Long. Al D/C trace
Long. Al D/C legend item
```

### 10.5 Governing marker

Governing points must be marked visibly but not aggressively. Use a distinct marker and label:

```text
Gov. D/C 0.426
Gov. V+T
Governing demand
```

### 10.6 Limit lines

Use a clear `Limit = 1.0` line for demand/capacity charts.

Limit lines must be visually consistent across charts.

### 10.7 Captions

Every engineering chart should have a short caption below it. Captions should explain:

- what is plotted
- what the limit means
- what assumptions or exclusions remain

Example:

```text
Combined V+T is plotted as utilization ratio versus station because Vu and Tu have different units. Stress D/C is the combined concrete stress interaction; Transverse D/C is the provided transverse reinforcement utilization. The red dashed line is the D/C = 1.0 check limit.
```

---

## 11. Engineering figure cards and diagrams

Geometry and reinforcement figures should behave like engineering drawings, not raw plots.

### 11.1 Figure requirements

- clear axes and units
- dimension labels not overlapping
- section outline visible
- centroid/CL markers where useful
- reinforcement symbols clear
- zoom/detail cards for congested areas
- captions and notes
- consistent style across section types

### 11.2 Strand/rebar visualization

For prestress and strands:

- use distinct symbols for bonded/debonded
- show strand row summaries
- show detail zoom for strand blocks
- avoid confusing wording

Use:

```text
Fully bonded throughout
Debonded near ends
```

instead of ambiguous:

```text
Bonded strands
Debonded strands
```

when counting global strand categories.

### 11.3 Debonding/elevation schematic

Debonding views should show:

- one web or side basis clearly
- mirrored behavior if applicable
- debond distances at both ends
- row-level summary
- station axis
- clear bonded/debonded legend

---

## 12. Input panel style

Input panels should be grouped into cards with short explanations.

Recommended elements:

- section status cards
- workflow cards
- material cards
- geometry parameter cards
- live preview cards
- compact tables for repeated items
- clear unit labels
- default notes

Avoid huge ungrouped forms.

Use small helper text to explain critical fields.

---

## 13. Code basis visibility

Design code must be visible on key pages:

- active context strip
- Result Summary cards
- ULS/SLS summary tables
- Report / QA top cards
- chart subtitles if relevant

Use edition labels when available:

```text
AASHTO LRFD 9th Edition
ACI 318-19
EN 1992-1-1
```

Avoid vague labels such as only:

```text
AASHTO LRFD
```

when the edition is known.

---

## 14. Traceability standard

Traceability page or expander should show:

```text
Workflow
Design code
Project input hash, if available
Stored result counts
ULS stored checks
SLS stored state
Runtime mode
Last run timestamp, if available
Cache status: Current / Stale / Missing / Not saved
```

Do not show misleading runtime status such as `Not run` when stored results exist. Use:

```text
Read-only summary; stored analysis results available
```

or:

```text
No solver rerun from this page
```

---

## 15. Persistence and save/load rule

Project JSON should be treated carefully.

### 15.1 Safe default

The safest stable behavior is:

```text
Project JSON saves input model primarily.
Analysis results may need to be rerun after loading unless explicit result persistence is implemented and tested.
```

### 15.2 Do not add result-cache persistence casually

Analysis-result persistence is risky in Streamlit apps because of:

- session state order
- widget key restrictions
- stale hashes
- load/apply timing
- expensive serialization
- hidden cache invalidation
- solver rerun side effects

Only implement result persistence as a separate milestone with tests. Never mix it with calculation changes.

### 15.3 Avoid known rejected line

For Concrete Section Pro specifically, do not reintroduce the `STATE-RESULT-PERSIST1/2/3x` line into a clean repo unless explicitly requested and redesigned safely. That line caused runtime/state regressions and should not be used as a style reference.

---

## 16. Development workflow rules

### 16.1 Milestone discipline

Every change should be a named milestone.

Examples:

```text
ULS.CHART.UI1 — Wide ULS chart standard
ULS.CHART.UI2 — Legend/status polish
REPORT.QA1 — Readiness alignment
SLS.RAIL.UGIRDER9 — Lifting/debond audit
```

### 16.2 One scope per milestone

Do not mix unrelated changes such as:

- UI chart polish
- solver performance
- Project JSON persistence
- report export
- code formula changes

in the same milestone.

### 16.3 Always state what did not change

For engineering apps, after each milestone state:

```text
No engineering equations changed.
No ULS/SLS calculation logic changed.
No Project JSON behavior changed.
No result-cache persistence added.
```

as applicable.

### 16.4 Testing standard

At minimum:

- `python -m py_compile app.py` and modified modules
- targeted tests for modified behavior
- regression tests for prior accepted behavior
- manual UI screenshot review for visual work

Do not claim full test pass if only targeted tests were run.

### 16.5 Repo summary

After each milestone, provide a copyable commit summary.

Example:

```text
Polish Beam/Girder ULS chart legends, hide non-applicable Longitudinal Al traces, and show full ULS strength status when all checks are complete.
```

---

## 17. Forbidden practices

Do not do the following:

1. Do not show `PASS` when a source gate is failed or blocked.
2. Do not show diagnostic one-station results as production envelopes.
3. Do not write diagnostic results to production cache.
4. Do not send diagnostic results to Result Summary or Report / QA.
5. Do not rerun solvers from Result Summary or Report / QA.
6. Do not create ad-hoc chart styles.
7. Do not use vague design-code labels when edition is known.
8. Do not hide limitations in collapsed developer-only expanders.
9. Do not claim final code certification for preview/scoped checks.
10. Do not let save/export logic slow or break core calculation flow.
11. Do not pack release ZIPs with `__pycache__`, `.pyc`, `.pytest_cache`, or temporary work folders.
12. Do not rebuild from memory when a baseline ZIP exists.

---

## 18. Packaging standard

Release ZIPs must be clean.

Exclude:

```text
__pycache__/
*.pyc
.pytest_cache/
.git/
.venv/
venv/
temp work folders
large logs
local debug outputs
```

Before delivering a ZIP, report:

```text
File name
SHA-256
Size
Zip entries
Cache files present? yes/no
Tests run
```

---

## 19. Concrete Section Pro reference baseline

For style reference, use the accepted clean baseline:

```text
concrete-section-pro_ULS-CHART-UI2-legend-status-polish.zip
```

Known characteristics:

- clean package size about 1.39 MB
- around 503 zip entries
- no `__pycache__`, `.pyc`, or `.pytest_cache`
- has stable Beam/Girder Flexure runtime restored
- includes ULS chart width standard
- includes ULS Shear + Torsion legend/status polish
- includes Railway U-Girder lifting a/L and debonding audit from the stable line
- does not include the problematic analysis-cache persistence experiments

---

## 20. Quick implementation checklist

Before calling an app “Concrete Section Pro style,” verify:

```text
[ ] Has a professional app shell and active context strip
[ ] Has clear workspace separation
[ ] Uses card-based decision UI
[ ] Shows design code and units visibly
[ ] Uses consistent PASS/FAIL/REVIEW/INCOMPLETE wording
[ ] Has Result Summary dashboard
[ ] Has Report / QA read-only page
[ ] Does not rerun solvers outside Analysis
[ ] Has full-width engineering charts
[ ] Has clear legends and captions
[ ] Hides non-applicable graph traces
[ ] Shows governing case/station/stage
[ ] Shows required engineering actions for failures
[ ] Shows scope guards and limitations
[ ] Avoids over-certification
[ ] Has targeted tests
[ ] Provides repo summary after each milestone
[ ] Release ZIP is clean
```

---

## 21. Starter prompt for a new chat

Use this prompt when starting a new ChatGPT chat inside the Engineering App Development Standard Project:

```text
โปรดอ่าน CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md ก่อนเริ่มงาน แอปใหม่นี้ต้องใช้ UI/UX, dashboard, graph, status wording, Result Summary, and Report/QA style ตาม Concrete Section Pro โดยไม่สร้าง style ใหม่เอง ห้ามใช้ ad-hoc Plotly styling ห้าม over-certify engineering checks และต้องแยก milestone ทุกครั้งที่แก้โค้ด
```

English version:

```text
Please read CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md before starting. The new app must follow the Concrete Section Pro UI/UX, dashboard, graph, status wording, Result Summary, and Report/QA style. Do not invent a new style, do not use ad-hoc Plotly styling, do not over-certify engineering checks, and separate each code change into a clear milestone.
```

---

## 22. Final rule

The Concrete Section Pro style is a **decision-first engineering software standard**.

If a proposed change makes the app prettier but less traceable, reject it.  
If a proposed change makes the app more automated but less reliable, reject it.  
If a proposed change hides engineering uncertainty, reject it.  
If a proposed change improves clarity, traceability, and safe engineering review, accept it.


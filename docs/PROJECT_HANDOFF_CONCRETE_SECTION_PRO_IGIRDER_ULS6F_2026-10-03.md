# PROJECT HANDOFF — CONCRETE SECTION PRO
## Precast I-Girder ULS Through IGIRDER.ULS6F

**Handoff date:** 2026-10-03  
**Project:** Concrete Section Pro  
**Active workflow:** Bridge Beam / Girder — RC / Prestressed Member  
**Section preset:** Precast I-Girder: Bridge · Precast Composite Girder  
**Design code:** AASHTO LRFD 9th Edition  
**Internal units:** mm, MPa, N, N-mm  

---

## 1. Purpose of this handoff

This handoff captures the current accepted engineering/UI state of the Precast I-Girder ULS workflow and the exact point at which development should resume.

The current packaged baseline is **IGIRDER.ULS6F — Torsion Full-Span Capacity Trace Closeout**. The major standalone Torsion solver path is implemented, the transverse-rebar/Torsion input linkage has been rebuilt, automatic `ph` is implemented, support-face torsion stations are eligible, coverage/detailing semantics are separated, and the latest package contains a chart-assembly fix intended to remove false gaps in the `±φTn` trace.

**Important:** ULS6F has been packaged and regression-tested, but the final running-app visual QA of the ULS6F `±φTn` full-span trace is still pending. Do not call Standalone Torsion “Fully Accepted” until that visual check is completed.

---

## 2. First message for the next development chat

Use this block to resume development without losing state:

```text
Continue Concrete Section Pro from the latest packaged baseline:

concrete-section-pro_IGIRDER-ULS6F-torsion-full-span-chart-closeout.zip

SHA-256:
eaba7ac697037cc7dc82fdc6f1b17392aedcbd5a578ebefd25603f868eed4f3a

Active workflow:
Bridge Beam / Girder — RC / Prestressed Member
Precast I-Girder: Bridge · Precast Composite Girder
AASHTO LRFD 9th Edition
Internal units: mm, MPa, N, N-mm

Current status:
- Construction Flexure: accepted.
- Final Composite Flexure: accepted.
- Girder–Deck Interface Shear: accepted.
- Prestressed I-Girder Shear General Procedure: accepted and visually closed.
- Standalone Torsion engineering solver: implemented through ULS6E.
- ULS6F fixes the remaining ±φTn full-span chart gap at the presentation layer.
- Final visual QA of the ULS6F Torsion chart is still required before declaring Standalone Torsion fully accepted.
- Shear + Torsion concurrent longitudinal certification is NOT yet complete and is the next engineering milestone after Torsion visual closeout.

Immediate next action:
1. Open ULS6F in Streamlit.
2. Use the same QA case with all five transverse zones qualified for torsion.
3. Recalculate Torsion.
4. Confirm red dashed ±φTn is continuous over the full 0–20 m physical member domain, including zone boundaries x=3, 6, 14, 17 m and the physical support faces.
5. Confirm graph values match the stored Torsion audit values and that real source gaps still remain visible if a zone is deliberately made not-ready.
6. If visual QA passes, close Standalone Torsion as FULLY ACCEPTED.
7. Then develop Shear + Torsion as the full concurrent V+T / longitudinal AASHTO check, including Article 5.7.3.6.3-1.

Do not change accepted Flexure, Interface Shear, or standalone Shear equations while doing the Torsion closeout or Combined V+T work.
```

---

## 3. Latest packaged baseline — IGIRDER.ULS6F

### Package

```text
/mnt/data/concrete-section-pro_IGIRDER-ULS6F-torsion-full-span-chart-closeout.zip
```

### Package metadata

```text
SHA-256: eaba7ac697037cc7dc82fdc6f1b17392aedcbd5a578ebefd25603f868eed4f3a
Size: 2,794,401 bytes
ZIP entries: 945
Cache artifacts: 0
ZIP integrity: PASS
```

### ULS6F purpose

ULS6F is a **display/QA closeout only**. It does not alter the accepted ULS6E Torsion engineering equations or stored result version.

The chart defect was caused by duplicate plot rows at the same `(Case, x)` where a physical engineering station had a finite `φTn` while a synthetic `DIAGRAM BOUNDARY` row could carry `NaN`. Plotly could treat the `NaN` as a line break.

ULS6F therefore coalesces plot rows before drawing capacity/reference traces, with priority:

1. physical engineering station with a finite result;
2. synthetic diagram/reference row only if no physical finite result exists.

A real capacity gap caused by genuinely missing/non-ready reinforcement must **not** be bridged or interpolated.

### Result/cache ownership

Stored result versions intentionally remain at the ULS6E family:

```text
Torsion:
IGIRDER.ULS6E.torsion-coverage-detailing-closeout

Shear + Torsion dependency:
IGIRDER.ULS6E.combined-vt-longitudinal-pending
```

ULS6F must not stale valid stored Torsion results merely because the chart assembly changed.

### Verification notes recorded at release

```text
Production compile: PASS
Relevant I-Girder regression: 155 passed
Relevant Crossbeam Shear/Torsion regression: 48 passed
Result Summary / Report-QA batches before packaging: 11 passed
Fresh-extract verification from the ZIP: 111 passed
Full repository suite: not run in full; no full-suite PASS is claimed
```

---

## 4. Source documents and project references

Primary engineering/reference files currently available in the project environment include:

```text
SECTION 5 CONCRETE STRUCTURES.pdf
ACI318-19.pdf
มยผ. 1301-61 มาตรฐานการออกแบบอาคารต้านทานแรงสั่นสะเทือนแผ่นดินไหว.pdf
มยผ.1311-50_มาตรฐานการคํานวณแรงลมและการตอบสนอ.pdf
CONCRETE_SECTION_PRO_APP_STYLE_SKILL.md
CSP_STYLE_SCREENSHOTS_REFERENCE.pdf
BG40_Cal Final_29-06-2026.pdf
```

For the current I-Girder ULS Shear/Torsion work, the main code source is **SECTION 5 CONCRETE STRUCTURES.pdf**. Exact AASHTO equations, branches, limits, units, and source notes must be read from that source before changing engineering logic.

Do not silently substitute remembered equations or ACI torsion shortcuts into the AASHTO I-Girder route.

---

## 5. Current ULS page status

| ULS check | Current state | Notes |
|---|---|---|
| Construction Flexure | **Accepted** | Noncomposite construction-stage resistance. |
| Final Composite Flexure | **Accepted** | Positive composite flexure scope accepted; negative-moment certification remains out of current route. |
| Girder–Deck Interface Shear | **Accepted** | AASHTO 5.7.4, full-span source ownership and audit clarity closed at ULS4A. |
| Shear | **Accepted / Visual QA closed** | AASHTO prestressed General Procedure implemented; Shear UI/semantics closed through ULS5B. |
| Torsion | **Engineering implementation complete; final visual closeout pending** | Solver/input architecture complete through ULS6E; ULS6F fixes false chart gaps. Need one final visual check. |
| Shear + Torsion | **Not yet certified** | Current stored dependency explicitly says longitudinal certification pending. This is the next engineering milestone after Torsion closeout. |
| Result Summary → ULS Summary | **Stage-specific architecture exists** | Must continue reading current-version stored results only; no solver rerun from summary. |
| Report / QA | **Stored-result architecture exists** | Equations/audit read stored current results; no hidden rerun. |

---

## 6. Locked engineering decisions that must be preserved

### 6.1 Construction Flexure

- Construction-stage flexure is **noncomposite**.
- Resistance is the precast I-Girder section only.
- Construction demand can include girder self-weight, wet deck, formwork/SIP, and user-defined temporary construction loads.
- Do not invent load factors not explicitly implemented/project-approved.
- Demand and resistance remain station-dependent and full-span.

### 6.2 Final Composite Flexure

- Final ULS demand comes from verified imported Final ULS FEA resultants.
- Resistance is Precast I-Girder + effective CIP deck.
- Current certified scope is **positive longitudinal composite flexure only**.
- Deck longitudinal reinforcement is excluded from positive `Mn` by default unless explicitly elected and valid.
- Transverse deck reinforcement must never be credited as longitudinal girder flexural steel.
- Composite flexure acceptance does not replace Girder–Deck Interface Shear.

### 6.3 Girder–Deck Interface Shear

Accepted ULS4A policy:

- Code basis = AASHTO LRFD 5.7.4.
- Demand source = Final ULS `Vuy`, independently from positive-`Mux` flexure filtering.
- `bvi` default = I-Girder top-flange width B1; manual override allowed.
- Interface surface condition must be explicit.
- Crossing reinforcement must actually cross and develop across the interface before receiving `Avf` credit.
- Conservative default `Pc = 0`.
- Weaker-side concrete strength is used where required.
- Solver internal units stay N, mm, MPa.
- US-customary AASHTO constants must be converted explicitly and audited.

### 6.4 I-Girder Flexure and ordinary longitudinal rebar

For the active Precast I-Girder workflow, Flexure `Mn / φMn` uses:

- concrete;
- active ordinary longitudinal reinforcement at its actual coordinates; and
- active prestressing strands.

Do **not** classify ordinary longitudinal bars as separate “Flexure-only” and “Torsion-only” bars.

The Longitudinal Rebar table remains the single ordinary-rebar source. If bars are physically added because of torsion, they also participate in Flexure according to their actual location/strain.

This is different from the separate Segmental Crossbeam project-specific rule where ordinary rebar may be intentionally excluded from `Mn`.

---

## 7. Accepted Precast I-Girder Shear route — ULS5 / ULS5A / ULS5B

### 7.1 General Procedure

The old prestressed I-Girder bridge route using fixed `β = 2.0`, `θ = 45°` was replaced for the active I-Girder workflow by AASHTO LRFD 5.7.3.4.2 General Procedure.

Implemented route includes station-dependent:

```text
εs → β → θ → Vc → Vs → Vn → φVn → D/C
```

Key locked behaviors:

- `β = 4.8 / (1 + 750 εs)` when at least minimum transverse reinforcement is present.
- `θ = 29 + 3500 εs` degrees.
- Negative raw `εs` may adopt zero using the allowed branch; raw and adopted values are shown separately.
- Below-minimum transverse reinforcement branch is not allowed to fabricate `sxe` when required source inputs are unavailable.
- Prestress transfer/development participation is station-aware.
- Prestressed shear `φ` branch distinguishes bonded from debonded/unbonded cases as implemented.
- Existing provided stirrup zones, minimum `Av/s`, maximum spacing, `Vn` limit, and zone coverage gates are preserved.

### 7.2 Near-support Shear semantics

- For the adopted compression-end support case, the explicit critical shear section near `dv` from the support is the design section.
- Ordinary imported load stations between support face and `dv` remain visible for diagram/audit but do not independently govern.
- Such rows display `NON-GOVERNING` semantics.
- Exceptions such as concentrated load within `dv` or a support reaction not introducing compression require explicit review; the app does not silently infer them from generic FEA resultants.

### 7.3 Shear UI/QA architecture

Shear includes:

- `Calculation trace / Equations — governing shear station`;
- `Variable definitions / Engineering terms`;
- raw/adopted `εs` in consistent units;
- check-specific limitations;
- no global Overall ULS aggregation inside the Shear page.

Cross-check aggregation belongs in Result Summary → ULS Summary.

---

## 8. Standalone Precast I-Girder Torsion route — ULS6 through ULS6E

### 8.1 Engineering scope

Standalone Torsion currently certifies the **transverse torsion component and associated detailing/coverage gates**. It does **not** issue final member PASS above the investigation threshold from `φTn` alone.

Final longitudinal solid-section acceptance remains owned by the future concurrent **Shear + Torsion** check.

### 8.2 Torsion threshold

Torsion is investigated where:

```text
|Tu| > 0.25 φTcr
```

The implemented `Tcr` route follows AASHTO LRFD 5.7.2.1, including prestress factor `K` and its guards.

The audit explicitly handles:

- effective prestress after losses;
- transfer/debonding effects;
- `fpc - Nu/Ag` axial adjustment using explicit sign conversion because app Loads are compression-positive while AASHTO `Nu` convention is tension-positive in the relevant equation;
- the `K ≤ 1.0` extreme-tension-fiber guard where required;
- refusal to fabricate `K` when its required source/branch is not valid.

### 8.3 Torsion-modified General Procedure

For a solid I-Girder requiring torsion:

```text
Veff = sqrt[ Vu² + (0.9 ph Tu / (2 Ao))² ]
```

`Veff` replaces `Vu` in the AASHTO 5.7.3.4.2 longitudinal-strain evaluation.

Then:

```text
Veff → εs → β → θ
```

Therefore `θ` is station-dependent and must not be fixed at 45°.

### 8.4 Transverse torsional resistance

The implemented transverse resistance is:

```text
Tn = 2 Ao (At/s) fy cotθ λduct
φTn = φ Tn
```

Important ownership:

- `At` is the area of **one closed-loop leg** per spacing for torsion.
- Shear continues to use `Av/s = effective legs × bar area / spacing`.
- A single physical stirrup-zone table is reused, but Shear and Torsion interpret the reinforcement area differently.

### 8.5 `Ao`, `Acp`, `Pcp`, `be`, `ph`

Current solid-section policy:

- `Acp` = area enclosed by the outside perimeter of the concrete section.
- `Pcp` = outside perimeter of the concrete section.
- `be = Acp / Pcp` for the adopted solid-section shear-flow path.
- `Ao` is derived from the AASHTO solid-section shear-flow path.
- The app does **not** use the ACI-style shortcut `Ao = 0.85 Aoh` for this route.
- `ph` = perimeter measured along the centerline of the actual closed transverse torsion reinforcement.

---

## 9. Transverse Rebar → Torsion linkage — current accepted architecture

### 9.1 Single physical transverse-reinforcement source

The existing **Sections → Rebar → Transverse Rebar** zone table remains the source of truth for the physical transverse reinforcement.

Do not duplicate bar size, spacing, `fy`, legs, or zone limits in a separate Torsion table.

Each provided zone may be qualified for Torsion by confirming:

```text
Use for Torsion
Closed Loop
135° Hook
```

### 9.2 Automatic `ph`

`ph` is no longer entered manually per zone.

For Precast I-Girder, the app derives the closed-hoop centerline from the active section geometry using the shared geometry basis:

```text
centerline offset = clear cover + db/2
```

The hoop topology is common along the member.

Consequences:

- changing spacing changes `At/s` but does not change the hoop topology;
- if bar diameter changes, the centerline offset and derived `ph` may change slightly;
- `ph` is shown read-only;
- the UI includes a section preview showing concrete outline and the red closed-hoop centerline used for `ph`;
- an advanced audited centerline-offset override may be used for a project-approved cage geometry, but `ph` itself remains derived rather than directly typed.

The app must refuse invalid/collapsed/split inset geometry rather than inventing a closed hoop.

### 9.3 Latest QA case values

From the most recent reviewed Transverse Rebar QA before ULS6F:

```text
Closed-hoop clear cover = 44.0 mm
DB12 → db/2 = 6.0 mm
Centerline offset = 50.0 mm
Auto ph = 4,195.1 mm
Torsion-qualified zones = 5
Capacity-ready zones = 5
Corner longitudinal detail = CONFIRMED
```

Five zones span the full 20 m member:

```text
0–3 m       DB12 @ 100 mm
3–6 m       DB12 @ 150 mm
6–14 m      DB12 @ 250 mm
14–17 m     DB12 @ 150 mm
17–20 m     DB12 @ 100 mm
```

---

## 10. Longitudinal rebar and Torsion — locked architecture

Do **not** create a separate “torsion longitudinal rebar” table and do **not** add a per-bar Flexure/Torsion identity checkbox.

The Longitudinal Rebar table remains the single ordinary longitudinal-rebar source.

For the future concurrent Shear + Torsion check:

- determine the active flexural tension side from the concurrent actions;
- use the relevant developed ordinary longitudinal `As` from the same bar coordinates/source;
- use developed prestressing `Aps` / prestress participation at the station;
- combine these with concurrent `Mu`, `Nu`, `Vu`, and `Tu` in the AASHTO longitudinal requirement.

The UI may audit corner longitudinal bar/tendon presence, but this is a detailing gate, not a separate longitudinal steel ownership model.

---

## 11. Corner longitudinal-detail semantics

Current UI behavior must remain separated by ownership:

- **Transverse strength** — `Tu / φTn`, required `At/s`.
- **Hoop detailing** — closed loop, 135° hook, spacing/minimum/detailing checks.
- **Torsion-zone coverage** — every design-required station must be covered by a capacity-ready torsion zone.
- **Corner longitudinal detail** — explicit confirmation that longitudinal bar/tendon detail exists at each closed-hoop corner as required by the adopted detailing policy.
- **Longitudinal strength** — remains `COMBINED CHECK REQUIRED` until Shear + Torsion is implemented.

Do not use one generic `detailing PASS` label to imply that both transverse and longitudinal requirements have been certified.

---

## 12. Physical support-face Torsion semantics

This was corrected in ULS6D and must not regress.

- A physical FEA/load station at `x = 0` or `x = L` is eligible for Torsion threshold/capacity checks and may govern.
- The Shear `dv` near-support exclusion does **not** apply to Torsion.
- Synthetic `DIAGRAM BOUNDARY` rows exist only for plot continuity/reference and must never replace or invalidate a physical support-face engineering station.
- If a physical support station lacks a source required for the full General Procedure capacity, the app may still perform the section-level `Tcr / 0.25φTcr` threshold screening; it must not fabricate missing capacity.

Latest reviewed Torsion audit demonstrated `x=0` being checked with a real finite `φTn` and D/C, confirming support-face eligibility.

---

## 13. Torsion coverage gate — ULS6E

Every physical station with:

```text
Threshold status = DESIGN REQUIRED
```

must independently have a torsion-qualified, capacity-ready transverse source.

A station is coverage-ready only when the provided zone has:

- Use for Torsion enabled;
- Closed Loop confirmed;
- 135° Hook confirmed;
- finite automatically derived `ph`.

Stored Torsion results include a coverage summary with:

- required design-station count;
- covered design-station count;
- uncovered station list;
- separate coverage status.

A transverse strength failure at one covered station must not hide a missing-coverage deficiency elsewhere.

---

## 14. Last reviewed full-capacity Torsion QA before ULS6F

The latest reviewed full-capacity QA showed the Torsion solver itself producing a complete station-dependent path.

Representative governing result:

```text
Tu = 500.00 kN-m
0.25φTcr = 31.98 kN-m
Threshold = DESIGN REQUIRED
Veff = 3,315.76 kN
β = 1.413
θ = 40.18°
φ = 0.900
Tn ≈ 119.16 kN-m
φTn ≈ 107.25 kN-m
D/C = 4.662
Status = FAIL
```

This is a **real transverse torsion strength failure** for the test reinforcement, not a software error.

The reviewed chart already showed the intended hierarchy:

- blue = `Tu demand`;
- red dashed = `±φTn`;
- orange dashed = `±φTcr`;
- purple dotted = `±0.25φTcr`.

The remaining chart issue was that `±φTn` was not visually continuous over the full member even when all five torsion zones were capacity-ready. ULS6F is the presentation fix for that issue.

---

## 15. Immediate visual QA required for ULS6F

Before declaring Standalone Torsion fully accepted, perform this exact check:

1. Use all five torsion-qualified/capacity-ready zones over 0–20 m.
2. Keep the same QA load case where `Tu = 500 kN-m` is above `0.25φTcr` over the member.
3. Recalculate Torsion in ULS6F.
4. Confirm `+φTn` and `-φTn` have a finite plotted value at every physical analysis station where coverage is ready.
5. Confirm no artificial gaps at:
   - `x = 0`;
   - `x = 3 m`;
   - `x = 6 m`;
   - `x = 14 m`;
   - `x = 17 m`;
   - `x = 20 m`.
6. Confirm the `φTn` graph values match the compact/detailed Torsion audit values.
7. Confirm zone changes may create real kinks/steps in capacity, but no unexplained blank segment.
8. Deliberately make one required zone not-ready and confirm:
   - coverage status becomes deficient;
   - `φTn` remains `NaN` for the real missing source;
   - the chart shows a real gap rather than silently interpolating/bridging it.

If all items pass, mark:

```text
PRECAST I-GIRDER STANDALONE TORSION — FULLY ACCEPTED
```

---

## 16. Next engineering milestone after Torsion — Shear + Torsion

Suggested milestone name:

```text
IGIRDER.ULS7 — Concurrent Shear + Torsion / Longitudinal Certification
```

### 16.1 Main objective

Close the AASHTO concurrent `V + T` check for solid prestressed I-Girders, including the longitudinal requirement owned by Article 5.7.3.6.3-1.

Standalone Torsion must not be used as a substitute for this check.

### 16.2 Required source/actions

At each station/case, use the concurrent resultants from the same active ULS row/case:

```text
Mu
Nu
Vu
Tu
```

Do not combine envelopes from unrelated rows unless the code route explicitly supports that envelope combination.

### 16.3 General Procedure consistency

The Combined route must use the same torsion-modified General Procedure basis as accepted Standalone Torsion:

```text
Veff → εs → β → θ
```

Do not mix:

- Shear station-dependent `θ`; and
- a legacy Torsion fixed `θ = 45°`.

That legacy inconsistency is already closed by ULS6 and must not return.

### 16.4 Transverse combined reinforcement

Implement the AASHTO concurrent transverse requirement using the accepted physical transverse-zone source.

Preserve:

- provided zone ownership;
- minimum transverse reinforcement;
- spacing limits;
- active-zone coverage;
- torsion closed-loop qualification;
- `At/s` one-leg semantics;
- shear `Av/s` effective-leg semantics;
- design `fy` policy/cap;
- duct factor as applicable.

The Combined page should distinguish:

```text
Shear transverse demand/resistance
Torsion transverse demand/resistance
Combined transverse requirement
Provided transverse reinforcement
Coverage/detailing gates
```

### 16.5 Longitudinal concurrent requirement

The future Combined solver must use the exact AASHTO Article 5.7.3.6.3-1 source equation and its definitions/limits.

The intended source architecture is:

```text
ordinary longitudinal rebar from the existing Longitudinal Rebar table
+
developed prestressing steel / effective prestress at the station
+
concurrent Mu, Nu, Vu, Tu
→
longitudinal demand versus resistance
```

Do not create a torsion-only `Al` shortcut merely to manufacture a PASS.

Development/transfer behavior near supports must be respected for both ordinary longitudinal reinforcement and prestressing as required by the source route.

### 16.6 Final Combined status

The Combined page may finally issue member-level:

```text
PASS / FAIL / REVIEW
```

only after all required components are resolved:

- concurrent transverse V+T strength;
- transverse detailing;
- torsion coverage;
- concurrent longitudinal requirement;
- development/participation gates;
- required corner/detailing checks.

Standalone Torsion remains a component check and should not become the final V+T acceptance authority.

---

## 17. Analysis UI architecture — do not regress

Each check-specific Analysis mode owns only its own:

- decision/status cards;
- graph;
- governing/check trace;
- audit tables;
- variable definitions;
- calculation equations/substitution;
- check-specific limitations.

Do **not** put global Overall ULS aggregation back into individual Shear, Torsion, or Combined pages.

Global ULS aggregation belongs in:

```text
Result Summary → ULS Summary
```

---

## 18. Equation/variable explanation standard

The user explicitly requested that the app help engineers remember variable meaning and calculation logic.

For major engineering pages, preserve the current pattern:

### Analysis page

- concise decision cards;
- important formula route;
- `Variable definitions / Engineering terms` expander;
- `Calculation trace / Equations` expander for the governing/check station;
- actual substitutions and units;
- branch/condition used by the solver;
- code article/equation basis where appropriate.

### Report / QA

- fuller derivation/audit trail;
- stored-result evidence only;
- no hidden solver rerun;
- enough information to reconstruct how the result was obtained.

---

## 19. Result Summary / Report-QA contract

### Result Summary

- Must use stage/check-specific stored results.
- Must recognize current accepted result versions rather than old legacy caches.
- Must not rerun engineering solvers.
- Overall status may be PASS only when all required current check results are present and acceptable.
- Missing required result → INCOMPLETE, not PASS.
- REVIEW / not-certified component must propagate appropriately.

### Report / QA

- Read current stored result packages.
- Show the same engineering values/branches as Analysis.
- Do not rerun the solver simply by opening Report / QA.

---

## 20. Cache and invalidation policy

Keep invalidation narrow and dependency-aware.

Examples already accepted:

- Shear engineering changes stale Shear and dependent Shear + Torsion only.
- Torsion engineering-source changes stale Torsion and dependent Shear + Torsion only.
- Presentation-only chart fixes such as ULS6F should not stale engineering results.
- Do not unnecessarily stale accepted Final Composite Flexure or Girder–Deck Interface Shear.

Project JSON compatibility must be preserved unless a schema change is explicitly required and migrated/tested.

---

## 21. Packaging / delivery contract

Every milestone or completed fix must deliver a **full latest project ZIP**.

The ZIP must be clean and contain no:

```text
__pycache__
*.pyc
.pytest_cache
other temporary/cache build artifacts
```

Before delivery:

1. compile modified production modules;
2. run focused engineering tests;
3. run relevant cross-workflow regression;
4. verify Result Summary / Report-QA if affected;
5. package full project;
6. verify ZIP integrity;
7. extract the actual ZIP to a fresh directory;
8. rerun relevant tests/compile from the fresh extracted artifact;
9. report SHA-256, size, entry count, cache count, and test results;
10. include a **one-sentence Repo summary** in the delivery message.

Do not claim full-suite PASS unless the entire repository suite actually completes.

---

## 22. Relevant milestone history

```text
IGIRDER.ULS4A
Interface Shear Full-Span & Audit Clarity Closeout

IGIRDER.ULS5
Prestressed I-Girder Shear General Procedure

IGIRDER.ULS5A
Shear QA Closeout

IGIRDER.ULS5B
Shear UI Semantic Polish

IGIRDER.ULS6
AASHTO Prestressed I-Girder Torsion General Procedure

IGIRDER.ULS6A
Torsion chart threshold clarity

IGIRDER.ULS6B
Torsion visual-QA / audit compacting closeout

IGIRDER.ULS6C
Torsion rebar-source closeout

IGIRDER.ULS6C1
Transverse Rebar runtime hotfix

IGIRDER.ULS6D
Automatic ph + support-face + Rebar UI closeout

IGIRDER.ULS6E
Torsion coverage / detailing semantic closeout

IGIRDER.ULS6F
Torsion full-span capacity trace closeout
```

---

## 23. Known limitations / deliberately deferred items

Do not silently expand certification beyond current scope.

Known/deferred items include:

- Final Composite negative-moment/continuity-region flexure not certified.
- Dedicated I-Girder flexural end-zone `φMn` taper from transfer/development length remains deferred unless the user explicitly returns to it.
- Standalone Torsion does not certify the final concurrent longitudinal V+T requirement.
- Anchorage, bearing/end-zone D-regions, final hook/lap execution, fatigue, and shop-drawing constructability remain separate project checks unless explicitly developed.
- A complete full-repository test-suite PASS is not currently claimed for the latest milestone.

---

## 24. Current priority / stop condition

### Priority 1 — ULS6F visual confirmation

Do not start a broad Combined V+T refactor before verifying the ULS6F chart behavior in the running app.

Required outcome:

```text
±φTn continuous across all capacity-ready physical stations over 0–L,
with no artificial zone/boundary gaps,
and real source gaps still visible when deliberately created.
```

### Priority 2 — close Standalone Torsion

If ULS6F visual QA passes:

```text
PRECAST I-GIRDER STANDALONE TORSION — FULLY ACCEPTED
```

Record the accepted PDF/screenshot as the visual-QA source.

### Priority 3 — develop Shear + Torsion

Proceed to the full concurrent transverse + longitudinal AASHTO route without changing accepted standalone Shear/Torsion equations unless a source-backed defect is found.

---

## 25. Repo summary

`Advance Concrete Section Pro through Precast I-Girder ULS6F with accepted prestressed Shear General Procedure, full standalone AASHTO Torsion engineering/source architecture, automatic closed-hoop ph and coverage/detailing gates, and a final presentation-layer fix for full-span ±φTn trace continuity; visual confirmation of ULS6F remains the last step before concurrent Shear + Torsion development.`

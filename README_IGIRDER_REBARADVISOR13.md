# IGIRDER.REBARADVISOR13 — Reinforcement advisor

Extend the full accepted IGIRDER.TORSIONAUDIT12 app with an Analysis advisor
that identifies which existing stirrup zones need strengthening, sizes a trial
layout from all current girder/case/station results, and verifies that layout
using the accepted Shear + Torsion solver after an explicit button press.

## Use

1. Run `streamlit run app.py` and load the original Project JSON.
2. Open Analysis → ULS Strength → Shear + Torsion and press
   **Calculate Shear + Torsion — all … girders (current model)**.
3. Review **Reinforcement advisor — ตำแหน่งและวิธีแก้ไข**. The shared zone
   table includes current/proposed hoops, governing girder/station, before D/C,
   and an audit of governing cases and sampled failure locations.
4. Press **Calculate trial — ตรวจชุดปลอกที่แนะนำทุกคาน**. This calculates
   all original force vectors independently for every girder with the proposed
   hoops and shows exact torsion, transverse, spacing and longitudinal ratios.
5. Review **Trial remaining actions** and use **Action details** to read the
   full action and its source case. Download the trial layout, verification and
   remaining-actions CSVs from **Trial audit / downloads**.
6. If the layout is adopted after checking actual cage/bending/placement
   details, edit Sections → Rebar → Beam/Girder Shear Reinforcement Layout
   and calculate the production checks again.

## Scope and ownership

- Suggestions use every current stored case and repeated source occurrence,
  not the case selected for a chart. The section/stirrup model is shared across
  the imported girder collection. Recommendations therefore cover both girders.
- Each recommendation covers the complete existing zone. Failed sampled x
  values identify checked points, not interpolated continuous failure bounds.
- The sizing estimate uses reported physical required Av/s, one-leg At/s and
  code maximum spacing. Combined physical hoop steel is counted once.
  Torsion is sized as one leg even for a hoop with more shear-effective legs.
- Try the existing diameter with closer spacing first, then DB16/20/25/32.
  Original spacing is never relaxed. Legs, fy, zone boundaries and closed-hoop
  qualification inputs remain the user's values.
- The default minimum trial spacing of 50 mm and 10 mm increment are user
  constructibility screens, **not code minimum spacing requirements**. They
  can be changed in Trial options. Actual placement/cover/hooks require review.
- A new diameter can change ph, strain/theta and other station calculations;
  the estimate is never presented as a verified result. The explicit trial uses
  the full existing solver, including the longitudinal force and all gates.
- Source-envelope/concurrency, development, nominal-fps/pretensioned dominance,
  negative composite scope, effective-depth and interface checks stay visible.
  A numerical transverse result below 1.0 does not imply overall PASS.
- Missing/nonfinite transverse data, uncovered stations and duplicate or
  overlapping zones block a complete proposal. Diagram boundary placeholders
  are excluded from sizing.
- Trial results are stored only under `_igird_rebaradvisor_trial_runtime`.
  Changed model/forces/options/layout hide stale trials. Trials do not overwrite
  inputs, production cache, Result Summary or Report / QA.
- Review, Result Summary and Report / QA do not run advisor/production solvers.
  No trial-result persistence was added to Project JSON.

## Original user-project verification

Input: `I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck350.json`.

SHA-256: `12b43739fa137984c5f8ddc1f618e414a67893187d7bb57b29b3ab1de8bfb88d`.
Fresh accepted-solver results were generated independently for **2 girders ×
320 source rows**. Old cached results in the input JSON were not used to size
the trial. Case/station/source-row/Mu/Nu/Vu/Tu columns match before and after.

| Existing zone | x from left end (m) | Current | Verified transverse trial | Before maximum V+T transverse D/C | Trial maximum V+T transverse D/C |
|---|---:|---|---|---:|---:|
| Left support | 0–1.5 | DB12 @70 | DB12 @50 | 1.337 | 0.955 |
| Left transition | 1.5–4.5 | DB12 @100 | DB12 @80 | 1.154 | 0.923 |
| Midspan | 4.5–15.5 | DB12 @200 | DB12 @80 | 2.448 | 0.979 |
| Right transition | 15.5–18.5 | DB12 @100 | DB12 @50 | 1.966 | 0.983 |
| Right support | 18.5–20 | DB12 @70 | DB16 @70 | 1.579 | 0.887 |

All ten girder/zone combinations meet the calculated φTn, transverse V+T,
shear strength/minimum and spacing ratios for this trial. Overall V+T remains
FAIL in eight girder/zone combinations and REVIEW in two. For example,
Interior Girder 2 retains longitudinal force D/C 1.058 at x=15 m, 1.140 at
x=18 m and 1.144 at x=19 m. Its governing force deficit at x=18 m is 484.5 kN.
The pretensioned dominance condition additionally fails near physical ends,
independently of the numerical longitudinal force ratio. Every imported force
source is marked ENVELOPE — REVIEW; deck development/interface/depth-source
and negative composite checks remain separate acceptance items.

Do not treat this transverse trial as a final approved reinforcement design.
The app provides the remaining specific engineering actions and full source
rows so the longitudinal layout, development and load-source issues can be
resolved and all production checks recalculated.

## Validation

- Compile `app.py`, both modified existing modules, both new advisor modules
  and the four QA scripts.
- 75 scoped tests passed: advisor, TORSIONAUDIT12 and MAXMIN10.
- 116 additional regression tests passed: concurrent V+T, automatic physical
  ph, multiple girders, case controls, report charts and Project IO.
- Advisor-only rerun after final UI edits: 16 tests passed.
- Actual `app.py` AppTest with the original project: explicit trial calls for
  both 320-row girders; all-case sizing independent of displayed LC; production
  inputs/cache unchanged; one advisor in detailed review; changed trial options
  and input staleness hidden; Summary/Report guarded against solver calls and
  trial publication.
- Actual local Chromium UI verification at 1680 px and 1280 px, including an
  explicit trial-button calculation. Screenshots were reviewed visually.
- These are scoped checks; this milestone does not claim the entire repository
  test suite was rerun.

QA evidence is in `qa/evidence/igird_rebaradvisor13/`. The original 47 MB input
and temporary pickle checkpoints are external and are not packed in the release.
The QA scripts accept external file paths so the checks can be reproduced.

No engineering equations or production ULS/SLS logic changed. No Ao/deck-strip
research model was introduced. No Project JSON behavior or result persistence
changed. The full accepted baseline and its historical evidence remain included.

Commit summary:

```text
Add all-case I-girder stirrup recommendations and explicit isolated trial verification with remaining longitudinal/source actions.
```

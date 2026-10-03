# Project handoff — Concrete Section Pro — IGIRDER.ULS7

Date: 2026-10-03. Workflow: Bridge Beam / Girder, Precast I-Girder, AASHTO LRFD
9th Edition (2020). Internal units: mm, MPa, N, N-mm.

## Baseline and completed milestone

Continue from `concrete-section-pro_IGIRDER-ULS7-concurrent-vt-longitudinal.zip`.
Its authoritative archive metadata/fresh-extract verification is in the companion
release manifest. Start with `README_IGIRDER_ULS7.md`.

Original ULS6F baseline SHA-256:
`eaba7ac697037cc7dc82fdc6f1b17392aedcbd5a578ebefd25603f868eed4f3a`.
The original uploaded baseline was preserved. No baseline project file was removed.

ULS6F visual closeout is complete. The production Torsion renderer was run in
Streamlit in a local browser with five DB12 zones @100/150/250/150/100, span20m,
Tu500kN-m, boundaries3/6/14/17, physical stations0–20. Positive/negative phiTn
traces are continuous when all sources are ready, and every chart value equals
the stored audit value. Z3 not-ready creates a real gap. See screenshots and
`qa/uls6f_runtime_audit.json`. The model is a reconstructed QA fixture, not an
undocumented original project. The high-Tu section fails strength as expected.
Standalone Torsion is an accepted transverse component implementation; final
longitudinal acceptance belongs to the concurrent check.

ULS7 implements the concurrent solid-section transverse sum and longitudinal
AASHTO5.7.3.6.3-1 using one action row and developed physical steel. Analysis,
Summary and Report share stored decision rows. No Summary/Report solver rerun.

## Engineering basis and preserved decisions

Primary supplied source: `SECTION 5 CONCRETE STRUCTURES.pdf`, printed pp.5-75–5-78,
Articles5.7.3.4.2,5.7.3.5,5.7.3.6.1–.3. Source development references are
5.9.4.3.2 and5.10.8.2.1a. Do not substitute remembered ACI torsion shortcuts.
See the original handoff/style instructions copied under `docs/`.

- Construction Flexure remains noncomposite and station dependent; do not invent
  construction load factors.
- Final Composite Flexure remains the accepted positive composite route. Effective
  deck width, concrete and optional longitudinal deck bars keep their existing
  source ownership. Negative composite certification is not added here.
- Interface Shear remains AASHTO5.7.4 with its own crossing/anchorage gate.
- Standalone Shear General Procedure and Torsion ULS6E equations are unchanged.
- Av/s=effective shear legs×area/spacing; At/s=one closed-hoop leg/spacing.
  The physical hoop is counted once against max(shear requirement,minimum)+2At/s.
- Mu/Nu/Vu/Tu must be concurrent. Real support faces are eligible. Synthetic
  DIAGRAM BOUNDARY rows never become governing engineering checks. Supplemental
  critical-dv rows use the existing concurrent interpolation; ambiguous duplicate
  vectors at one case/x are all retained and interpolation is withheld/REVIEW.
- App Nu compression-positive is negated for AASHTO tension-positive Nu.
- R=developed Aps×nominal fps + sum(developed As×actual fy). Nominal fps is solved
  with the existing AASHTO block/bonded-strand model, minimum tension-group stress,
  developed ordinary bars, and no optional deck-bar force credit in this new source.
- Strand development/debonding and fpo transfer ramp reuse the accepted helper.
  fps=fpu is used only as a conservative development-length screen.
- Ordinary development is explicit: continuity plus governing verified ld/end
  anchorage confirmations. Missing data receive zero ordinary strength/stiffness
  credit and withhold PASS. A common full-span model does not cover cut-off bars.
- The pretensioned Aps*fps>As*fy condition, closed hoop/hook/spacing, corner and
  perimeter confirmations remain separate gates. Numerical D/C alone is insufficient. The perimeter checkbox is now available
  in the actual Transverse Rebar UI and its project-load widget mirror is reset.
- Straight strands use Vp=0/lambda_duct=1. Normal-weight concrete only. The Veff
  compression cap is an additional conservative guard, not an ACI stress equation.
- Zero Mu above threshold checks both halves conservatively. Negative composite,
  biaxial actions, lightweight, fatigue and bearing/D-regions remain separate scope.

## Versions and persistence

| Check | Stored version |
|---|---|
| Construction Flexure | IGIRDER.ULS2P.flexure-performance-optimization |
| Final Composite Flexure | IGIRDER.ULS3A.composite-flexure-audit-closeout |
| Interface Shear | IGIRDER.ULS4A.full-span-audit-clarity |
| Shear | IGIRDER.ULS5A.shear-qa-closeout |
| Torsion | IGIRDER.ULS6E.torsion-coverage-detailing-closeout |
| Shear + Torsion | IGIRDER.ULS7.concurrent-vt-longitudinal |

`igird_longitudinal_development_settings` is persisted in existing project metadata
and restored on project load. Older projects clear prior development confirmations
and widget mirrors. Torsion settings/zone sources are also saved and restored
from the current project metadata, clearing previous-project direct/widget
mirrors so confirmation flags cannot leak. Development invalidates Combined only. Older pending combined versions
are ignored; accepted versions for other checks remain unchanged. Current combined
hash is checked in read-only Summary/Report, so changed sources withhold stale PASS.

Standalone Torsion keeps its own longitudinal-pending stored semantics. Summary
may resolve it to PASS—COMPONENT only with all transverse/coverage/corner gates
and a current complete Combined PASS; it does not rewrite the Torsion package.
Overall ULS needs all stage-specific checks. SLS/report completeness is separate.

## Verification evidence

- Compile production modules: PASS.
- Related I-Girder/ULS chart/Crossbeam/Summary/Report/cache regressions:248 passed.
- Modified Summary/legend-focused regression:51 passed.
- Perimeter UI/source/cache-focused closeout:83 passed.
- Actual perimeter-confirmation widget/event lifecycle:PASS; unconfirmed→REVIEW, confirmed→PASS with complete sources. The final fresh-extract batch includes this regression.
- New ULS7 engineering module:39 cases, including independent force/nominal-fps
  benchmarks, axial sign, physical hoop allocation, development/debonding,
  nominal-fps sources, physical ends, unknown sources, duplicate vectors, cache
  ownership, JSON round trip, read-only Report, component Summary and real gaps.
- Real production app.py startup, Rebar page integration, four Combined scenarios,
  stored Summary/Report and development controls:PASS, zero app exceptions.
- Local browser inspection:ULS6F continuous/gap and ULS7 PASS/FAIL/REVIEW/gap plus
  stored Report. Evidence under `qa/evidence/`.
- 70 accepted engineering/source helper bodies byte-identical to baseline.
- Fresh-extract test count and final ZIP metadata:companion release manifest.
- Full repository suite was not run; do not claim otherwise.

Independent longitudinal force benchmark:Mu1000kN-m, Nu(app)=-200kN, Vu500kN,
Tu150kN-m, phi0.9, dv1200mm, Ao300000mm², ph4000mm, cot(theta)1.25.
With the specified residual hoop allocation and Vs cap, required force is
1752.011352kN, resistance2300kN and F/R0.761744066. See JSON/test for all inputs.

Two old pending-certification test assertions were updated to the ULS7 missing-
composite-source guard. One pre-existing source-text assertion was absent even
in ULS6F; it now verifies the existing dynamic current-result/completeness wording.
No production behavior was changed to satisfy that stale literal assertion.

## Next development

Do not broaden acceptance silently. Next work should obtain an independent
complete girder benchmark with actual geometry, imported concurrent cases,
ordinary bar cut-offs/anchorage drawings and strand development/overhang details.
Review the conservative zero-Mu dual-half policy against the project's support
model; do not discard physical Tu at supports. Expand ordinary development to
station-specific cut-off/mixed details only with a verified source model. Negative
composite, biaxial, bearing/D-region and fatigue routes require their own explicit
milestones and source equations. Keep Analysis check-specific and Summary/Report
read-only. Continue full clean ZIP, compile/focused/cross-workflow QA, fresh-extract
verification and a one-sentence Repo summary at each milestone.

Repo summary: Implement concurrent AASHTO I-Girder V+T longitudinal checks with
physical hoop allocation, developed steel, preserved ULS6E torsion and stored
Summary/Report traceability.

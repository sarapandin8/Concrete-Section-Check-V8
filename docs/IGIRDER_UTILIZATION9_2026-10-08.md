# IGIRDER.UTILIZATION9 — Torsion utilization continuity

Baseline: IGIRDER.REPORTCHARTS8 (2026-10-07).

## Problem and resulting behavior

The Overview — utilization plot used the maximum original design/check D/C.
The torsion threshold screen intentionally omits those design ratios at BELOW
THRESHOLD and zero-demand stations. GAPAUDIT7 made the stored Tu / phiTn
capacity diagram continuous through qualified stations; it did not change the
utilization overview. Consequently, an available capacity diagram did not
prevent gaps in the original D/C plot.

The Torsion overview now shows two explicitly distinct quantities:

- Blue line: actual same-case/station |Tu| / stored phiTn (transverse strength).
  Qualified below-threshold and actual zero-Tu stations have numeric values.
- Open markers: maximum original design/check D/C at the station, including
  strength, longitudinal, detailing and spacing components where available.
  Originally omitted design ratios remain omitted. The governing diamond,
  controlling case/component/station, FAIL and REVIEW come from original rows.

The threshold is never used as phiTn. No NaN is filled, no missing force is
accepted as zero, and no engineering value is interpolated. Connecting lines
between evaluated stations remain a plotting convention.

For All load cases, the blue envelope maximizes actual paired case ratios.
It does not divide maximum Tu by independently minimized resistance. Every
unavailable case/station remains in the audit even if another case supplies a
numeric point at the station. The title identifies the all-case paired envelope.

## Source qualification and audit

The read-only view validates the original station action against cached Tu,
requires finite positive stored phiTn, rejects ambiguous case/station rows and
checks recorded diagram source identities. Three-decimal Governing x matching
follows the existing production formatter; ambiguous precision collisions retain
all original rows as unavailable. Existing verified native CSI physical-endpoint
sharing is reused with original source case/sheet/row identities.

Missing/invalid resistance or source mismatches produce NaN and a chart-foot
cross. Another case supplying a plotted value does not resolve the missing row.
Original infinite design D/C remains labelled infinity at the drawing ceiling;
it is not converted to a finite design ratio.

The collapsible Torsion utilization — stored station ratios / original decisions
panel includes the strength ratio, actual/cached Tu, phiTn, original maximum
check D/C/component/status, threshold, availability, curve-gap flag and source
identity. The CSV retains stored float precision and full identities. Original
stored check-row CSV export remains unchanged.

## Analysis and Report / QA

In each girder panel, choose Overview — utilization. The existing selected-case
demand/capacity view remains the default for Torsion.

Report / QA -> I-girder ULS report charts — stored results -> Torsion:
select the girder and Automatic or a named load case, then select Overview —
utilization under Torsion report chart view. Create report chart PNG and Download
report chart PNG export the selected view at 2880 x 1120 px. The same distinction
and original selected/all-case gates appear in the image footer. The station
audit CSV is available in the utilization audit panel.

Review/select/export never calls a solver or modifies inputs, load banks,
stored result frames, cache entries or the design member. Current input/result
version validation and stale-result hiding remain in force.

## Preserved engineering scope

No engineering equations, threshold decisions, coupled-source acceptance,
ULS/SLS logic, result versions, dependencies, Project JSON or persistence changed.
Strength utilization is a plotting quantity, not overall acceptance. Existing
composite-width, development, interface-shear, longitudinal V+T, bearing and CSI
concurrency gates retain their decisions. The project model remains shared among
calculated members; different member details still need separate project models.

## Verification

- Python 3.14.7; Streamlit 1.61.0; pandas 3.0.6; PyArrow 24.0.0;
  Plotly 5.24.1; Kaleido 0.2.1.
- Scoped regression: 60 modules, 762 passed in 58.10 s before final
  title/marker presentation polish.
- Final targeted regression after that polish: 3 modules, 63 passed in 12.68 s;
  21 new behavior tests.
- Final collection AppTest: both girders, AUTO/named/ALL cases, all four checks,
  original tables/results/input integrity, collapsed panels and stale hiding PASS.
- Final actual app.py AppTest: all four Analysis/detail routes and Report / QA;
  both girders x two cases; Torsion utilization, PNG and audit CSV widgets PASS.
  Report review solver calls=0; input/cache/design-member snapshots unchanged.
- Actual hypothetical station-pattern QA: two girders x two cases x 21 stations;
  Exterior x=12/13/14/20 and Interior x=5 below-threshold patterns have qualified
  stored strength ratios; deliberate missing phiTn at x=9 retains a gap and cross.
- Source-case mismatches, missing/nonfinite/zero/negative phiTn, missing Tu,
  duplicate/precision-colliding sources, original infinity, paired case maxima
  and verified native CSI endpoint provenance covered by behavior tests.
- py_compile PASS for changed/new Python modules and app.py.
- Exported Plotly images visually inspected; shared 1440 x 560 layout and
  2880 x 1120 station-pattern exports verified.

QA inputs are hypothetical, not a recalculation of the user's PDF project.
This is scoped regression, not the entire repository test suite. AppTest and
exported-image review were used; no live Streamlit Cloud deployment or full-page
browser verification was performed. Inherited Streamlit table deprecation and
Arrow automatic-fix logs can occur; completed AppTests have no fatal exception.
New audit tables use the existing Arrow display adapter.

Commands (run from repository root):

```bash
python -m pytest tests/test_igird_utilization9.py tests/test_igird_gapaudit7.py tests/test_igird_reportcharts8.py -q
python qa/igird_casecontrol5_ui_verify.py --output-dir qa/evidence/igird_utilization9/collection --release IGIRDER.UTILIZATION9
python qa/igird_reportcharts8_app_verify.py --output-dir qa/evidence/igird_utilization9/app --release IGIRDER.UTILIZATION9
python qa/igird_utilization9_verify.py
```

The scoped module list and all current evidence are in qa/evidence/igird_utilization9.
Historical evidence from all prior milestones is retained.

## Repository summary

Fix torsion utilization gaps using paired stored station forces and resistance while preserving original design checks, governing cases, and report export.

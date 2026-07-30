# CROSSBEAM.PTLOSS4D2A — Engineer-Adopted FEA Handoff Contract and Workbook QA

## Purpose

Harden the PTLOSS4D2 external-FEA export so a reviewed Effective Prestress source cannot be downloaded as an adopted design handoff without an explicit engineer decision on the representative Time-Dependent loss approximation and a declared FEA application route.

## Engineer adoption contract

The Effective Prestress page now requires the engineer to:

1. select exactly one FEA application route:
   - `DIRECT_EFFECTIVE_FORCE`, or
   - `JACKING_FORCE_WITH_FEA_LOSSES`;
2. confirm adoption of the current representative creep + shrinkage + relaxation scalar for this preliminary external-FEA handoff.

The adoption confirmation is tied to the current source fingerprint and selected route. It resets automatically when either changes. Download buttons remain disabled until the source is closed and the engineer adoption checkbox is confirmed.

## Status semantics

- `PRELIMINARY SOURCE READY — ENGINEER ADOPTION REQUIRED` means the source chain is numerically closed but export is not enabled.
- `ENGINEER-ADOPTED PRELIMINARY HANDOFF — EXTERNAL FEA ONLY` means the current representative TD approximation and selected application route are recorded in the export contract.
- `SOURCE BLOCKED` means the upstream Effective Prestress source or projected-station coverage/closure is incomplete.

The handoff remains preliminary. External FEA must calculate portal-frame secondary prestress, and verified SLS `P/V2/M3` resultants must return through the main Loads workspace.

## Compact export package

The workbook now contains:

1. `Handoff Summary`
2. `Tendon Handoff`
3. `Three-Point Profile`
4. `System Station`
5. `QA Checks`
6. `Instructions`

Changes include:

- full SHA-256 source fingerprint retained once in `Handoff Summary`;
- short 12-character Source ID used in data sheets and CSV files;
- Contract ID records the source, selected route, and engineer TD-adoption state;
- compact Tendon summary columns without repeated instructions/fingerprint text;
- explicit Left / Mid / Right profile naming instead of claiming a full station profile;
- three-decimal stress/force/percentage display formats while preserving full stored precision;
- frozen headers/identifier columns, filters, bounded column widths, and print-width settings.

## Formula-driven QA sheet

`QA Checks` contains live Excel formulas for:

- system-average stress closure;
- system-average force closure;
- each Tendon-average stress/force closure;
- each Left/Mid/Right profile-row stress/force closure.

The workbook requests full recalculation on open. A closure row reports `PASS` only when both stress and force residuals are within the adopted tolerance.

## Human-readable traceability

When sources are available, `Handoff Summary` records:

- project and member identity;
- construction type;
- member-design and prestress-loss code bases;
- stressing/jacking mode;
- `ti`, `tg`, `tr`, and `tf`;
- permanent-load event schedule;
- RH, concrete `f'c`, stressing `f'ci`, and member-equivalent V/S;
- TD subtotal and limitation;
- FEA application route, adoption status, Source ID/fingerprint, and Contract ID.

## Safety and regression boundary

- No Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, Relaxation, Effective Prestress, or closure equation is changed.
- Export/adoption controls perform zero structural solves.
- The adoption checkbox is a handoff decision, not a Project JSON engineering result.
- Main Loads remains dedicated to verified ULS/SLS response import.
- Secondary prestress is not subtracted from `Pe` and remains an external-FEA responsibility.

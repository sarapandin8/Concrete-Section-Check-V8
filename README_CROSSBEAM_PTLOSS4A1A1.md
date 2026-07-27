# CROSSBEAM.PTLOSS4A1A1 — Static Print-Audit Table Hotfix

## Purpose

Complete the PTLOSS4A1A browser-print audit by replacing the remaining scrollable Time-Dependent QA dataframes with compact static HTML evidence tables. The hotfix keeps all right-side values in the print DOM and combines the four loss equations into one compact block without changing any engineering calculation.

## Changes

- Adds a workflow-scoped static audit-table renderer with fixed column widths, wrapped headings, compact print typography, and `break-inside: avoid-page` behavior.
- Splits local Section/Zone drying evidence into print-safe tables for:
  - Section geometry,
  - interior exposure and adopted drying perimeter,
  - local Section-type V/S and `ks`, and
  - Section-type volume/drying-surface shares.
- Uses short print headers for the station/section map while retaining Segment, station limits, length, Section ID, and Section role.
- Keeps all per-zone concrete-volume, drying-surface, volume-share, and drying-surface-share values visible.
- Keeps Post-ES average tendon stress, station count, `fpu`, and adopted `fpy = 0.90fpu` visible for T1–T8.
- Converts the AASHTO factor and representative-interaction audits to the same static evidence format.
- Combines `Kdf`, creep, shrinkage, and relaxation equations into one aligned LaTeX block to avoid a nearly empty trailing print page.

## Numerical scope

No accepted result changes for the default Precast Segmental regression model:

- creep loss = `78.369843 MPa`,
- shrinkage loss = `40.890590 MPa`,
- relaxation loss = `7.888682 MPa`,
- Time-Dependent subtotal = `127.149115 MPa`,
- structural solves = `0`.

## Locked scope

- No AASHTO creep, shrinkage, relaxation, or `Kdf` equation changed.
- No member-equivalent or local Solid/Hollow V/S calculation changed.
- No Friction/Wobble, Anchorage Set, Elastic Shortening, FEA, or contact result changed.
- No Project JSON schema, result persistence, Effective Prestress handoff, Result Summary, or Report / QA solver credit changed.

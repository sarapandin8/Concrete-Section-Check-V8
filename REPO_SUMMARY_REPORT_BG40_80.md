# Report BG40 80 repository summary

Add an I-girder calculation report following BG40 R10 chapter order with
numbered calculation details, native Word math, source references and full
source-evidence exports.

- Starts from the accepted SLAB-PUNCHLOCAL79 release.
- Adds a report data collector, A4 Word renderer and Report / QA workspace.
- Preserves the original R10 Word styles, theme, page settings and cell formatting from a stripped template; the source document is untouched.
- Adds chapter-specific input/action diagrams, dimensioned sections, governing stress blocks/hoops, SLS depth profiles and slab plan/profile views.
- Registers and exports every embedded figure with the full source evidence.
- Reports current stored ULS packages for every loaded design member.
- Retains same-row actions and the original code, development and source gates.
- Uses current SLS53, DEFLECT70 and SLAB.REVIEW68 result accessors.
- Marks unbound historical loss audits for review.
- Preserves Local Punching index versus physical-perimeter acceptance.
- Hides old exports after calculation inputs, output cells or report metadata change.
- Keeps existing report functions and the Crossbeam workflow compatible.

No engineering equations or ULS/SLS analysis algorithms changed.
No Project JSON behavior or result persistence was added.
104 targeted/regression tests passed; see qa/evidence/report_bg40_80/targeted.xml.


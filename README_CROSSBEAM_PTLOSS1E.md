### CROSSBEAM.PTLOSS1E - Prestress Loss Table Export Layout Polish

PTLOSS1E fixes the Crossbeam `Prestress Loss` printed/exported table layout
after the PTLOSS1D compact issue text still left the far-right station column
cropped in the app/PDF view.

#### What changed

- Removes the repeated `Issue` column from the wide station trace table and
  moves blocking issues/review notes into a separate compact
  `Station review / notes` table.
- Moves `Status` near the left side of station and per-tendon tables so review
  state stays visible even when a user scrolls or exports a wide table.
- Shortens station trace numeric headings such as `xj`, `P(x)`, `Loss`, `Exp`,
  and `P/Pj` to reduce horizontal width without changing values.
- Uses engineering display symbols `μ` and `α` in the UI labels, captions, and
  displayed table headings. Internal Python/JSON keys still use ASCII `mu` and
  `alpha` for compatibility.

#### Scope guard

- No AASHTO friction/wobble equation, `Pj`, status rule, summary metric,
  Project JSON, navigation, solver, SLS, ULS, anchorage set, elastic shortening,
  creep, shrinkage, relaxation, report, anchorage-zone, deviator-force, or
  D-region logic is changed.

#### Repo summary

Polish Crossbeam Prestress Loss table export layout by separating review notes from the wide station trace and using μ/α display notation while preserving calculation behavior.

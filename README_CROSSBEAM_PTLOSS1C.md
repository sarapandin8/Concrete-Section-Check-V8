### CROSSBEAM.PTLOSS1C - External Summary And Review Note Fix

PTLOSS1C fixes the Crossbeam `Prestress Loss` summary behavior observed when
valid external HDPE-lined tendons are calculated as review-note rows.

#### What changed

- Summary cards now use all active calculated station rows, including external
  rows marked `LOSS READY + NOTE`, so `Worst traced loss` and `Minimum P/Pj`
  reflect the governing calculated external tendon point.
- External HDPE-lined rows with explicit `Deviator` points now show
  `LOSS READY + NOTE` instead of `REVIEW REQUIRED`.
- External tendons with no `Deviator` point remain `REVIEW REQUIRED` because
  the AASHTO `0.04 rad/deviator` term is not applied.
- Review text is split into blocking issues and nonblocking review notes; the
  UI shows blocking issues as warnings and review notes as info messages.
- The summary card now reports required review rows and nonblocking note rows
  separately.
- Scope wording now says deviator-force/hardware checks remain future work,
  while the current page is the friction/wobble preview.

#### Scope guard

- No AASHTO friction/wobble equation, `Pj`, Project JSON, navigation, solver,
  SLS, ULS, anchorage set, elastic shortening, creep, shrinkage, relaxation,
  report, anchorage-zone, or D-region logic is changed.
- External tendon loss remains a transparent deviator-preview calculation until
  detailed deviator hardware/stressing-sequence inputs are added.

#### Repo summary

Fix Crossbeam Prestress Loss external tendon summaries by including review-note calculated rows in governing metrics, separating blocking issues from notes, and warning only when external tendons lack Deviator points.

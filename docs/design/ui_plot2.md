# UI.PLOT2 — SLS Decision Plot and Failure Diagnosis Layout

Purpose: improve the SLS stress diagram page so the user sees the stage decision,
controlling stress demand, actual-versus-limit value, utilization, and failure
reason before reading audit tables.

Scope:
- UI/diagnostic layer only.
- Adds a decision-first SLS summary panel above the stress plot.
- Collapses the tensile-limit guide by default to reduce visual clutter while
  preserving the same control and session-state behavior.
- Increases SLS plot height and improves legend/font readability.
- Keeps governing compression/tension markers and report-style stress plot lines.

No solver or engineering formula changes:
- no SLS stress equation changes,
- no Pe(x) or debonding participation changes,
- no material routing or stage limit formula changes,
- no load routing or project schema changes.

# CROSSBEAM.PTLOSS3B2B2A2 — Lightweight response-audit display hotfix

This hotfix repairs the display-only cumulative structural-response expander in the lightweight Elastic Shortening route. The stored lightweight result was already calculated correctly; the error occurred only when the UI called the shared Plotly response helper with obsolete `case_label` / `response` arguments and passed the print caption positionally after the helper contracts had become keyword-only.

Changes:
- call `_ptloss3b2a_response_figure` with its current `title`, `field`, `y_title`, and `trace_name` contract for moment and axial-force traces;
- call `_render_ptloss3b2a_print_figure` with the required keyword-only `caption` argument;
- add focused regression coverage that executes the shared response-figure helper and rejects stale helper keywords in the display-only block;
- preserve the one-solve lightweight ES result, `f_cgp`, ES losses, contact state, optional Advanced QA boundary, and all engineering equations unchanged.

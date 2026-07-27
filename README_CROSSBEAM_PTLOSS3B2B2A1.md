# CROSSBEAM.PTLOSS3B2B2A1 — Runtime Status and Advanced-QA Guard Polish

This milestone keeps the accepted lightweight AASHTO Elastic Shortening equations and one-solve cumulative contact route unchanged while aligning operational status wording with the released on-demand workflow.

Changes:

- the Construction Source card now reports `SOURCE READY — RUN ON DEMAND` when its inputs are complete;
- the pre-run sequence-loss card reports `NOT RUN` semantics instead of implying that the feature is unreleased;
- the Component Status card identifies the actual blocker (`Final tendon bond system`), then transitions through `READY TO RUN`, `RERUN REQUIRED`, and `ES ESTIMATE CURRENT` states;
- optional Advanced Construction-Stage QA now requires an explicit acknowledgement that it is computationally heavy and may trigger cloud throttling;
- a current Advanced-QA bundle cannot be rerun accidentally until it is cleared.

No frame stiffness, tendon equivalent loads, contact active-set logic, `f_cgp` routing, Elastic Shortening equation, Project JSON schema, or downstream result handoff is changed.

# CROSSBEAM.SUPPORTQA1C — TD Schedule Defaults and Adoption Gate

This milestone closes the multi-column prestress-loss QA line by hardening the Time-Dependent Loss schedule source without changing any prestress-loss equation or structural solver.

## Changes

- Sets general-practice new-project defaults to RH 75%, curing end 7 d, stressing 28 d, grouting 28 d, falsework removal 35 d, and final age 18,250 d (50 years).
- Migrates only the known invalid legacy pattern RH=1% with zero-age schedule to those defaults and displays a visible restoration notice.
- Preserves valid project-specific schedules and manual values.
- Adds an explicit confirmation when no later permanent-load event applies before final service.
- Blocks Time-Dependent Run unless `0 < curing <= ti <= tg <= tr < tf`, RH is at least 20%, and either later events are adopted or the no-later-event declaration is confirmed.
- Persists the no-later-event declaration in Project JSON schema version 9.
- Adds field guidance clarifying that defaults are editable starter assumptions, not code-mandated construction ages.

## Unchanged

- No Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, Relaxation, or Effective Prestress equation changed.
- No frame/contact solver or event solve changed.
- No Loads or Analysis workflow changed.
- Existing valid Project JSON schedule values are not overwritten.

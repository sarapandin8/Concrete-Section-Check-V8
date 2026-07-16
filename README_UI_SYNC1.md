# Concrete Section Pro — UI.SYNC1

## Milestone

`UI.SYNC1 — Placement clarity and workflow display synchronization`

## Crossbeam transverse placement

The former `Placement within each zone` table mixed two independent coordinate
directions. It is now presented as two explicit editors:

- `Cross-section cage placement` controls the transverse cage/tie centerline
  offset measured inward, normal to the concrete face.
- `Longitudinal placement within each zone` controls the first transverse set
  from the Zone start and the minimum clearance to the Zone end.

The longitudinal caption states that the Zone-end value is a minimum clearance.
The actual last-set clearance can be larger because sets advance from the Zone
start using the template spacing. Existing Project-JSON field names and values
are unchanged.

Splitting the editor increases the current Crossbeam Rebar editable-table count
from 14 to 15. Both new editors retain the RB-EDIT1 first-change callback.

## Setup workflow synchronization

The `Active Member Workflow` card previously rendered from canonical state
before the dropdown selection was committed. The dropdown then updated the
canonical state later in the same run, leaving the card one rerun behind.

UI.SYNC1 adds a pre-rerun callback that commits `analysis_mode_settings` and its
widget synchronization marker before the page renders. The workflow card,
configuration summary, design-code routing, and downstream context therefore
receive the same selected workflow on the first change.

## Scope guards

- No transverse geometry formula, spacing algorithm, Av/s calculation, Zone
  station generation, or Project-JSON schema is changed.
- No PMM, Beam/Girder, SLS, shear, torsion, tendon, Result Summary, Report/QA,
  segment-joint, or analysis-cache ownership is changed.

## Validation

- Split placement first-edit tests cover cage centerline offset plus Zone-start
  and Zone-end inputs.
- Workflow callback and selectbox-registration tests cover pre-rerun commit.
- Complete Crossbeam suite: 111 passed.
- Crossbeam/Project/Workflow regression gate: 190 passed.
- Full repository suite: 1,943 passed; the same 6 unrelated baseline failures
  remain.
- Streamlit AppTest confirmed the workflow card changes on the first dropdown
  selection and rendered both new placement editors without exceptions.
- Streamlit health endpoint returned HTTP 200 with `ok`.

## Repo summary

Separate Crossbeam transverse placement inputs by coordinate direction and
commit the Setup workflow selection before rerun so the displayed workflow and
downstream context update together on the first change.

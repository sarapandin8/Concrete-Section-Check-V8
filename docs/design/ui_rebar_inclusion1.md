# UI.REBAR.INCLUSION1 — Rebar inclusion state and clean Rebar preview

## Scope
- Align the Rebar workspace with the Section Builder ordinary-rebar inclusion flag.
- Remove section dimension guides from Rebar previews because section dimensions are owned by Section Builder.

## Changes
- When ordinary rebar is disabled in Section Builder, the Rebar page now presents stored rows as `Excluded` rather than analysis-active.
- Stored ordinary rebar rows are preserved for later use and can be reviewed without implying analysis participation.
- The disabled-state preview is labeled as excluded from analysis.
- Longitudinal and combined Rebar previews pass an empty dimension guide list to `create_section_preview()`.
- Captions now direct users to Section Builder for section dimensions.

## Out of scope
- No geometry changes.
- No PMM/shear/torsion/SLS solver changes.
- No rebar parser or rebar area calculation changes.
- No project schema changes.

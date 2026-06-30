# UI.COMMERCIAL4.4 — Light-Blue Accordion System

This milestone replaces the old solid dark-navy Streamlit expander bars with a lighter blue accordion visual system to match the newer commercial dashboard shell.

## Purpose

The previous navy expander bars were too visually heavy after the app moved toward a clean commercial blue-accent UI. They made secondary audit/detail sections compete with primary controls, status cards, and result summaries.

## Scope

- Change global Streamlit expander summary styling from solid navy to light-blue surfaces.
- Use blue borders and accent chevrons for interactive state.
- Keep readable dark-slate/navy text on light backgrounds.
- Use a slightly stronger light-blue surface for expanded accordion headers.
- Preserve navy as a structural/brand emphasis color only, not as the default expander bar fill.

## Non-goals

- No solver equations were changed.
- No SLS, ULS, PMM, prestress, rebar, or section-property equations were changed.
- No project schema, save/load logic, widget keys, or navigation state was changed.
- No expander labels or engineering content were moved or renamed.

## Expected visual behavior

Collapsed expanders use a clean blue-tinted surface and border. Expanded headers use a slightly stronger blue tint, while the body remains a white panel. This makes audit/detail sections visible but stops them from overpowering primary engineering inputs and result cards.

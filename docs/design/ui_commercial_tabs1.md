# UI.COMMERCIAL.TABS1 — Existing app tab polish without navigation changes

## Scope
- Remove the nested Definition / Analysis / Report workflow bar that UI.COMMERCIAL.SECTION1 added inside Section Builder.
- Apply visual-only CSS polish to the existing Streamlit segmented/radio tab controls used by the app.

## Design constraint
This milestone must not add new tabs, move existing tabs, or change navigation behavior. The goal is AdSec-like visual treatment for the current app tab controls, not a workflow redesign.

## Included
- Section Builder keeps its commercial hero/card styling but no longer shows local Analysis or Report tabs.
- App-wide segmented/radio navigation controls receive a compact commercial tab treatment.
- Tests guard against reintroducing the nested Section Builder workflow tabs.

## Out of scope
- No solver changes.
- No geometry, section property, rebar, prestress, loads, analysis, or report calculation changes.
- No project schema changes.

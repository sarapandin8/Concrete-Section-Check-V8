# AASHTO.COL.SEISMIC3 — Seismic advisor card typography

## Purpose

The AASHTO LRFD seismic bridge-column transverse advisor uses dense status cards for spacing, confinement length, Ash/rho, and overall detailing status. Streamlit's default metric value typography was visually too large for this workflow and made the card deck feel heavier than the engineering content required.

## UI decision

This milestone keeps the blue engineering emphasis but reduces the metric value size on the Rebar page so the advisor reads like compact design information rather than dashboard KPIs.

## Implementation

- Add Rebar-page CSS targeting Streamlit metric labels and values.
- Reduce metric value font size to a compact `1.04rem`.
- Allow long values to wrap using `overflow-wrap: anywhere` and `white-space: normal`.
- Keep labels small, uppercase, and consistent with the commercial engineering card style.

## Engineering scope

No AASHTO calculation logic was changed. This is a presentation-only update for the seismic detailing advisor cards.

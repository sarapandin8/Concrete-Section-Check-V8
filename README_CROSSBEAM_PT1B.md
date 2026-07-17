# Concrete Section Pro — CROSSBEAM.PT1B

## Milestone

`CROSSBEAM.PT1B — Transparent-3D state isolation and visible sub-tabs`

## Delivered

- `Transparent 3D concrete` is explicitly display-only. ON renders the 3D
  concrete mesh at 13% opacity so tendons and segment boundaries remain
  visible; OFF uses 42% opacity. Neither state edits geometry or analysis.
- The durable Project-JSON Crossbeam length is separated from the transient
  Streamlit number-input key. Toggle reruns and widget cleanup can no longer
  delete or reset `L`.
- A one-time guarded recovery handles the known stale 0.100 m widget sentinel
  only when the stored segment range is continuous and every stored tendon
  profile agrees on the same endpoint. It restores `L` from those endpoints
  without moving any segment or tendon coordinate.
- Sub-tabs now match both legacy button tabs and the current Streamlit
  React-Aria `div[data-testid="stTab"]` DOM. Inactive tabs use white cards on a
  light-blue rail; the active tab uses the app's blue border, fill, and dark
  bold text.

## Scope guards

- No segment/profile coordinate is scaled, clamped, or moved automatically.
- Project-JSON engineering inputs, tendon validation rules, PT continuity,
  reinforcement workflows, and every solver remain unchanged.
- No other member workflow or navigation structure is modified.

## Validation

- Crossbeam, Project-IO, and shared theme regression: 177 passed.
- Full repository regression: 1,958 passed; the same 6 unrelated baseline
  failures remain in Railway U-Girder and legacy source-audit tests.
- Live-browser ON/OFF interaction kept `L = 20.000 m` in all three states and
  produced 0 geometry errors and 0 browser errors.
- Runtime CSS inspection confirmed the current React-Aria active tab renders
  as dark-blue 800-weight text on a blue-bordered light-blue card.

## Repo summary

Make Crossbeam 3D transparency presentation-only by isolating durable length
state from Streamlit widgets, and restore clearly visible theme-aligned
React-Aria sub-tabs without changing engineering inputs or solvers.

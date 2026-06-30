# STATE.RESULT3 — Restore PMM Visual Review Visibility

## Purpose

STATE.RESULT2 correctly reduced unnecessary PMM solver/display rebuild work after
navigation, but it over-gated the Flexural (PMM) workspace by hiding the main PMM
Check and 3D Interaction dashboard behind an optional render checkbox. That made
available PMM visuals appear to disappear even though the stored PMM result was
still present.

## Scope

This milestone restores the commercial review expectation:

- The PMM Visual Review area is visible whenever a stored PMM result and D/C
  summary are available.
- The PMM Check tab and 3D Interaction tab render from stored/cached PMM result
  data and do not rerun the PMM solver.
- The 3D PMM Interaction tab remains internally guarded by its own display toggle
  because surface rendering can be expensive.
- Only the legacy raw point-cloud plots and raw PMM result table/export are gated
  behind an advanced rendering control.

## Engineering boundary

This is a UI/state/performance milestone only. It does not change PMM solver
equations, section capacity calculations, demand/capacity logic, prestress logic,
shear/torsion checks, SLS checks, or report calculation logic.

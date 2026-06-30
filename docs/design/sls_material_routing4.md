# SLS.MATERIAL.ROUTING4 — Canonical Transfer Stage Strength Hotfix

## Scope

Fix the remaining Railway U-Girder SLS visible tensile-limit guide path that still displayed and used final web concrete strength `f'c = 45 MPa` as the transfer/release strength even when the Railway U-Girder staged material settings defined `web f'ci = 36 MPa`.

## Root cause

The prior routing fixes allowed callers to pass simplified tab labels such as `Transfer stage`.  The visible tensile guide, however, passes the canonical code-limit stage label `Transfer / Release`.

The stage-strength helper incorrectly tried to map every input through the simplified tab-label mapper first.  For the canonical label `Transfer / Release`, that mapper returned `User-defined`, which is a recognized stage label but not a physical stage.  Railway U-Girder routing then fell through to the service/full-U strength branch and displayed `web f'c = 45 MPa` in the transfer guide.

## Correction

The stage-strength helper now normalizes direct canonical stage labels first:

- `Transfer / Release` routes to Railway U-Girder `web f'ci`.
- `Deck casting / Pre-composite` routes to Railway U-Girder `web f'c`.
- `Final service / Composite` routes to Railway U-Girder service/full-U preview strength.
- Simplified UI labels such as `Transfer stage` still map through the existing tab-label mapper.
- `User-defined` no longer falls through to transfer; it safely defaults to service preview behavior.

## Guardrail

A regression test now reproduces the visible-guide path by passing the canonical stage label `Transfer / Release` directly and asserts that Railway U-Girder transfer strength is `36 MPa`, not `45 MPa`.

## Out of scope

No geometry generator, PMM, ULS, prestress-loss, effective-prestress, shear/torsion, report, project-schema, or final code-certified SLS design logic changed.

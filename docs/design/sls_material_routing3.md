# SLS.MATERIAL.ROUTING3 — Visible Transfer Guide Stage-Strength Hotfix

## Purpose

Fix the remaining Beam/Girder SLS full-length diagram guide route where the visible tensile stress guide could still display final concrete strength as transfer `f'ci`, especially after Analysis reruns or project-load paths with stale preset selectors.

## Scope

- Broaden Railway U-Girder detection for SLS material-strength routing.
- Detect Railway U-Girder from durable `section_parameters` and geometry metadata parameters, not only preset labels.
- Use guarded Railway stage settings fallback only when the Railway-specific material triplet and construction method are present.
- Make the visible tensile stress guide use the same stage-routed strength helper as the diagram controls.
- Add regression tests for stale generic selector + stale generic `fci = f'c` conditions.

## Engineering rule enforced

For Railway U-Girder:

- Transfer / Release: use `web f'ci`.
- Lifting: use `web f'ci` in Railway staged preview.
- Construction / wet casting: use `web f'c`.
- Service extreme-fiber preview: use `web f'c` for top/bottom full-U diagram, with CIP slab `f'c` retained as audit note for future slab-fiber checks.

The visible tensile guide must not display `f'ci = web f'c` when `web f'ci` is available.

## Out of scope

- No solver equation changes.
- No geometry or section-property changes.
- No ULS coupling.
- No transfer-length, development-length, or anchorage/end-zone checks.
- No separate CIP slab-fiber service stress check in this milestone.

# SECTION.BUILDER.FOCUS1 — Expose Material and Assembly Controls

## Scope

This milestone declutters the Section Builder definition panel after `SECTION.ASSEMBLY1` moved beam/girder system controls out of Setup.

## Changes

- Removed the collapsed `Project / workflow / axis details` expander from the Section Builder definition panel.
- Removed the collapsed `Browse by geometry family` helper expander from the default Section Builder view.
- Made `Concrete Material Assignment` visible by default in a bordered panel instead of hiding it in an expander.
- Made `Section / Member Assembly` visible by default instead of hiding it in an expander.
- Updated Section Workspace Status and geometry workspace copy so material/assembly controls are described as visible section-specific controls.

## Engineering intent

Setup should remain limited to project/workflow/design-code decisions. Section-specific material assignment and assembly behavior belong in Section Builder because they vary by preset and workflow, including Bridge I-Girder, Building I-Girder, Plank Girder, Box Beam, and Railway U-Girder.

## Out of scope

No solver equations, geometry generators, section-property integration, rebar force logic, prestress loss logic, load equations, report logic, or project-schema calculation behavior were changed.

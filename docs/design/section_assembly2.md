# SECTION.ASSEMBLY2 — Railway U-Girder Assembly Panel Alignment

## Purpose

Align the Railway U-Girder assembly controls with the staged construction model:
two precast prestressed webs connected by a cast-in-place slab.

## Scope

- Railway U-Girder receives a rail-specific `Bridge Section Assembly` panel.
- Default span is `L = 10.0 m`.
- Case B wet slab casting is shown explicitly: wet slab/formwork load is carried by web-only sections and distributed 50/50 to left/right web.
- Editable controls remain limited to stage/assembly metadata: concrete unit weight, formwork load, lifting a/L, and lifting impact factor.
- Generic repeated-girder controls such as overall U-girder system width and tributary load take-down width are hidden for Railway U-Girder.
- Legacy `beam_girder_system_settings` remains synchronized for downstream span and unit-weight consumers.

## Out of scope

No solver equations, section geometry, PMM, SLS stress, Pe/loss logic, rebar/prestress layout, load equations, or report logic were changed.

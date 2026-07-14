# CROSSBEAM.UI1A — Section-Builder-linked segment assignment

Scope:

- Portal Frame Crossbeam tab order: Section Builder, Segment Layout, Rebar, Tendon System, Tendon Profile.
- Default crossbeam length: 20.000 m.
- Segment assignment uses a `Section type / preset` dropdown sourced from the Portal Frame Crossbeam presets in Section Builder.
- Free-text Section role and Section ID are removed from the user editor; preset key and Solid/Hollow role are derived internally.
- Accepted UI1 rows migrate to the matching solid/hollow Section Builder preset.
- Untouched UI1 30 m seed state migrates once to the new 20 m seed; edited layouts are preserved.
- Existing non-Crossbeam navigation and solver behavior remain unchanged.

Engineering boundary:

This remains a geometry/layout workspace only. It does not calculate prestress losses, SLS stresses, ULS resistance, anchorage zones, column-joint regions, or solid-to-hollow D-regions.

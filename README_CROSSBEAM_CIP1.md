# CROSSBEAM.CIP1 — Cast-in-Place Solid-Only Workflow Guard

This milestone makes the Portal Frame Crossbeam longitudinal layout construction-type-aware without changing any accepted prestress-loss or structural solver equations.

## Precast Segmental
- Preserves the accepted Solid/Hollow physical segment layout.
- Keeps physical segment-joint semantics and the existing Segmental Rebar workflow.

## Cast-in-Place
- Enforces Solid Section IDs only in the active Section/Zone Layout.
- Seeds one full-length `Z1` Solid zone for a new Cast-in-Place layout.
- Treats internal boundaries as section/property zones, not physical joints.
- Uses a monolithic Solid elevation with no Hollow/hidden-void legend or joint semantics.
- Disables creation of new Hollow sections while Cast-in-Place is active.
- Guards the existing Segmental Rebar editor because its segment-local bars and `As = 0` joint rule are not applicable; continuous CIP longitudinal rebar remains a later named milestone.

## State safety
- Precast and Cast-in-Place layouts are stored separately and restored when switching construction type.
- Both layouts persist through Project JSON.
- Both dormant and active layouts scale with an approved member-length scale operation.

## Locked scope
- No continuous Cast-in-Place rebar editor yet.
- No ACI development/splice solver.
- No change to Friction, Anchorage Set, Elastic Shortening, `fcgp`, Primary/Secondary Prestress, PMM, SLS, or ULS solvers.

# CROSSBEAM.CIP1B — CIP Semantic Cleanup & Safer Column Defaults

- Treats `L` as the physical end-to-end Crossbeam length in Section Builder wording.
- New-project column defaults are C1 = 1.500 m and C2 = L - 1.500 m; very short members use ordered quarter-point seeds.
- Cast-in-Place Section Library hides `New Hollow` and uses Zone/Section semantics in user-facing assignment text.
- Cast-in-Place property heading is generic (`Gross Concrete Section Properties`) and the workflow filter states Solid-only applicability.
- If a Cast-in-Place project still uses a material name containing `Precast`, the app raises a review warning but does not change material properties automatically.
- No Rebar topology, prestress-loss equation, PMM/SLS/ULS, or stage-solver logic is changed.

# CROSSBEAM.ANALYSIS.UI1 — Compact Beam/Girder-Aligned Analysis Workspace

This milestone replaces the standalone Crossbeam Station Check Foundation as a primary Analysis page with compact Crossbeam-specific `ULS Strength` and `SLS / Stress & Joint Compression` workspaces.

## Scope

- aligns Crossbeam Analysis hierarchy with the accepted Beam/Girder decision-first pattern;
- limits main-page cards and tables to decision-critical information;
- keeps ULS checks as `Flexure`, `Shear`, `Torsion`, and `Shear + Torsion`;
- keeps SLS stages as `At Transfer` and `At Service`;
- retains the Precast Segmental physical-joint compression gate of at least `0.70 MPa` at top and bottom fibers;
- moves the source-coverage chart, full mapping tables, fingerprints, and source diagnostics into a collapsed audit expander;
- prevents the UI shell from being mistaken for a completed solver by keeping calculation buttons disabled and results `NOT CALCULATED`;
- routes Crossbeam pages only to Crossbeam-owned UI functions and does not call generic Beam/Girder solvers.

## Not changed

- no ACI 318 strength equation;
- no SLS stress equation;
- no ULS/SLS result persistence;
- no Loads contract or Project JSON change;
- no Result Summary or Report / QA connection;
- no behavior change for other member workflows.

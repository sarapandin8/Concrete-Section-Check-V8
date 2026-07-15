# CROSSBEAM.TR1 — Transverse / Shear Rebar Templates and Local-Zone Review

## Scope

Adds a workflow-scoped transverse/shear reinforcement foundation for `Portal Frame Crossbeam — Prestressed Concrete` while preserving the accepted segment-joint rules and leaving every existing ULS/SLS solver unchanged.

### Rebar workspace structure

The Crossbeam Rebar subnavigation is now:

```text
Longitudinal | Transverse / Shear | Segment / Zone | Preview | Joint & Station Audit
```

Existing Active Member Workflows continue to use their accepted Rebar navigation and data models.

### Independent transverse template library

Adds editable project templates for:

- factory-precast Hollow segment web reinforcement;
- denser Hollow segment end-zone reinforcement;
- Solid CIP column-region multi-leg ties; and
- Solid anchorage/end-block local transverse reinforcement.

Each Transverse Template supports:

- editable Template ID and name;
- guarded copy/delete actions;
- `SD40 ↔ 390 MPa` and `SD50 ↔ 490 MPa` linked dropdowns;
- bar-size and spacing input;
- independent left/right effective web legs for Hollow sections;
- effective multi-leg tie input for Solid sections;
- closed-cage/tie flag;
- cage center offset from the concrete face; and
- first/last transverse-set offsets within the assigned Zone.

All editable tables are intentionally limited to five or six visible columns to avoid hidden right-side columns and horizontal-scroll discovery problems.

### Independent Longitudinal / Transverse assignment

Each Segment/Zone now references two independent templates:

```text
Zone
→ Longitudinal Template ID
→ Transverse Template ID
```

Zone geometry and reinforcement assignment are displayed in separate compact tables. Role compatibility is checked against the Section ID assigned by Segment Layout:

```text
Hollow Section → Hollow / Any templates
Solid Section  → Solid / Any templates
```

Existing RB1/RB2 session state is migrated in place by preserving every custom Zone and adding only a missing compatible Transverse Template reference.

### Av/s input preview

The app calculates a read-only input preview from the provided bar, spacing, and effective legs:

```text
Hollow: Av,left/s, Av,right/s, Av,total/s
Solid:  Av,total/s from effective multi-leg ties
```

This is an input traceability preview only. No ACI shear strength, minimum reinforcement, maximum spacing, torsion, confinement, or D-region equation is evaluated in TR1.

### Transverse preview

The Preview page now supports:

```text
Longitudinal
Transverse / Shear
Combined review
```

The transverse view includes:

- Solid closed-tie / multi-leg cross-section schematic;
- Hollow left-web and right-web cage schematic;
- transverse-set elevation generated from spacing and first/last offsets;
- number of sets in the selected Zone; and
- local `Av,total/s` summary.

All transverse graphics terminate within the assigned Segment/Zone.

## Locked engineering guards

```text
Longitudinal ordinary rebar crossing every segment joint = 0 mm²
Transverse reinforcement = local to each Segment/Zone
Automatic segment-joint shear-transfer credit = NONE
PT continuity = REQUIRED — NOT VERIFIED
```

Joint shear keys, interface compression/friction, tendon clamping force, joint opening/decompression, anchorage zones, solid–hollow transitions, column D-regions, shear capacity, and torsion remain separate future checks.

## Not changed

- No ULS flexure, shear, torsion, combined V+T, or SLS equation.
- No generic Beam/Girder stirrup table or solver routing.
- No Result Summary or Report / QA logic.
- No Project JSON schema or result-cache persistence.
- No Railway U-Girder, Bridge/Building Beam-Girder, or Column/Pier Rebar workflow.

## Validation

```text
Python compilation: PASS
Crossbeam lineage and TR1 tests: 91 passed
Crossbeam/navigation/Project JSON/Rebar regression gate: 251 passed
Analysis/Result Summary/Report QA gate: 252 passed + 1 unchanged baseline static-source failure
```

The single static-source failure reproduces unchanged in the accepted RB2E baseline and is unrelated to TR1.

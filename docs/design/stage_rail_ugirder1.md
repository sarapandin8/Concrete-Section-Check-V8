# STAGE.RAIL.UGIRDER1 — Railway U-Girder Stage Model and UI

## Purpose

Define the staged-construction basis for the Railway U-Girder preset before any staged stress solver is added.  This milestone records the engineering assumptions, material defaults, lifting defaults, and Case B wet-slab attribution needed for a later guarded stress preview.

## Engineering basis

The Railway U-Girder is not treated as a full U-section at every stage.  The construction model is:

1. Precast side webs are cast separately.
2. Prestress is released at web concrete strength `f'ci`.
3. The webs are lifted, transported, erected, and positioned.
4. The cast-in-place slab is placed between the two webs.
5. For this project, wet slab load is **Case B**: carried by the two precast webs before composite action.
6. After the slab hardens, the section behaves as the full Railway U-Girder.

## Default inputs

- Span length `L = 10.0 m` for Railway U-Girder when no previous project/session value exists.
- Support condition: simply supported.
- Concrete unit weight: `24 kN/m³`.
- Precast web `f'c = 45 MPa`.
- Precast web transfer strength `f'ci = 36 MPa`.
- Cast-in-place slab `f'c = 35 MPa`.
- Concrete modulus display: ACI normal-weight `Ec = 4700 sqrt(f'c)` MPa.
- Wet slab load distribution: 50% to left web and 50% to right web.
- Formwork/construction load: `2.5 kN/m²`, editable.
- Two-point lifting default: `a/L = 0.20`, editable.
- Lifting impact factor: `1.10`, editable.

## Stage map

| Stage | Section basis | Automatic load attribution |
|---|---|---|
| Transfer | One precast web only | web self-weight + Pe_transfer |
| Lifting | One precast web only | web self-weight × lifting impact + Pe_lifting |
| Wet slab casting | One precast web only | web self-weight + 50% wet slab + 50% formwork/construction + Pe_construction |
| Composite construction | Full Railway U-Girder | locked-in prior loads; no service loads yet |
| Service | Full Railway U-Girder | service loads from Loads tab + Pe_eff_final |

## UI changes

A `Rail U-Girder stages` tab is shown inside the girder prestress workflow only when the active preset is `Railway U-Girder`.  It shows:

- Material inputs and ACI auto `Ec` captions.
- Support/load method defaults.
- Span and lifting point preview.
- Stage basis summary table.
- Auto-load attribution preview table.
- Guardrails warning that the full U-section must not be used for Transfer, Lifting, or Wet slab casting.

## Persistence

The editable staged-construction settings are saved/restored under project metadata key:

```text
railway_u_girder_stage_settings
```

## Out of scope

- No stress solver changes.
- No Pe/loss calculation changes.
- No debonding force effectiveness changes.
- No PMM/SLS/shear/torsion/report changes.
- No change to strand coordinates or section geometry.

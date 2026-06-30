# QA.RELEASE2 Regression Checklist

Milestone focus: regression audit after the generic precast lifting-stage workflow.

## Scope

- Section Builder assembly metadata
- Rebar and prestress state preservation
- SLS Transfer / Lifting / Construction / Service tabs
- Railway U-Girder special lifting route
- Generic precast girder lifting route
- Plot legend / dashed limit visibility
- Save / load persistence for lifting metadata

## Generic Precast Lifting Acceptance

Applicable presets:

- Bridge Precast I-Girder
- Bridge Precast Box Beam, interior and exterior
- Bridge Precast Plank Girder, interior and exterior
- Bridge Precast Voided Plank Girder, interior and exterior
- Building Precast I-Girder

Required behavior:

- Lifting stage tab is visible for eligible precast girder presets.
- Lifting basis is individual precast unit only.
- Composite slab, topping, wearing surface, barriers, and building service loads are excluded from lifting self-weight.
- Two-point lifting moment responds to lifting a/L.
- Lifting line load responds to lifting impact factor.
- Transfer/release stress limits are used unless the user changes the visible guide.
- Railway U-Girder continues to use its existing one-web lifting route.
- CIP / cast-in-place presets should not expose generic lifting by default.

## User-Confirmed UI Evidence

- Building Precast I-Girder: lifting tab visible; stress changes with a/L and impact factor.
- Box Beam: AUTO-LIFT visible; governing station follows lifting point; stress changes with a/L.
- Voided Plank Girder: AUTO-LIFT visible; governing station follows lifting point; stress changes with a/L.

## Regression Guard Tests Added

- Generic lifting load uses individual precast unit self-weight only.
- Building lifting excludes building SDL/LL service loads.
- Lifting station grid includes lifting points and ends.
- Two-point lifting moment changes with lifting ratio.
- Streamlit end-zone guidance keys are stage-qualified and editable widgets are rendered only in the Transfer tab.
- Section Builder contains lifting a/L and lifting impact factor inputs.

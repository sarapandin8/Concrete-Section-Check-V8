# IGIRDER.ULS3 — AASHTO Final Composite Flexure Capacity

## Scope

Adds the first calculated `Final — Composite` ULS Flexure route for:

`Precast I-Girder: Bridge · Precast Composite Girder`

Construction-stage ULS2P behavior is intentionally unchanged.

## Engineering basis

- Final demand remains the verified/imported Final ULS FEA `Mux` source from Loads.
- Final positive flexural resistance uses an **analysis-only** composite section made from the project precast I-Girder polygon plus the effective CIP deck rectangle (`Be × Tslab`). The stored project polygon remains precast-only.
- The strength solver uses the existing explicit AASHTO Section 5 strain-compatibility PMM engine.
- For different girder/deck concrete strengths, the analysis-only composite compression section uses the **lower** of the two f'c values. This is the conservative uniform-strength option supported by AASHTO LRFD 9th C5.6.2.2 / 5.6.3.2.6 rather than fabricating a two-material strength result.
- AASHTO prestressed flexure resistance factor routing remains `φ = 1.00` on nominal Mn.
- Final effective prestress and station-dependent strand participation/debonding are used.

## Deck longitudinal reinforcement

Section Builder now provides `Composite Deck Longitudinal Reinforcement` inputs. Positive composite Mn excludes deck longitudinal reinforcement by default. The engineer may explicitly enable credit and define top/bottom longitudinal layers by diameter, spacing, cover, fy, and Es. Transverse deck reinforcement is not credited to longitudinal girder flexure.

## Effective width gate

The existing `AASHTO.BE1` calculated effective-width helper remains preliminary. If helper mode is selected, numerical Final Composite flexure may be calculated but the section status remains `REVIEW`. For a current numerical section PASS, use `Manual` Be with the project-verified effective width.

## Acceptance semantics

- Numerical positive section flexure may be `PASS` or `FAIL`.
- If section flexure fails, Final Composite status is `FAIL`.
- If section flexure passes, Final Composite status remains `REVIEW` until the separate girder–deck interface shear check is implemented and verified.
- Negative Mux / continuity-region composite flexure is not certified by this milestone. It requires deck longitudinal tension reinforcement / continuity-region design.

## Performance

Final Composite uses the ULS2P single-PMM-sweep nominal-Mn reuse and browser-rendered Plotly chart path. Capacity-state caching continues to reuse equal geometry/material/strand states across stations.

## Result cache

Final Composite result version:

`IGIRDER.ULS3.aashto-composite-flexure-capacity`

This prevents older guarded/demand-only Final Composite states from being presented as current calculated results.

# IGIRDER.ULS4 — AASHTO Girder–Deck Interface Shear

This milestone closes the separate composite-action gate for **Precast I-Girder: Bridge · Precast Composite Girder** Final Composite positive flexure.

## Engineering scope

- Implements AASHTO LRFD 9th Edition Article 5.7.4 girder/slab interface shear as a separate check from section Mn.
- Demand follows Article 5.7.4.5 using verified Final ULS `Vuy` and station-specific interface effective depth `dv` from the centroid of tension steel to the CIP slab mid-thickness.
- Resistance follows Article 5.7.4.3:
  - `Vni = c Acv + mu (Avf fy + Pc)`
  - capped by `K1 f'c Acv` and `K2 Acv`
  - `Vri = phi Vni`
- Uses the weaker concrete strength across the interface.
- Uses `Pc = 0` by conservative default.
- Limits interface-reinforcement `fy` to the AASHTO 60 ksi design cap.
- Checks Article 5.7.4.2 minimum interface reinforcement, including the 1.33-demand upper bound on required minimum reinforcement.
- The special low-stress roughened girder/slab minimum-reinforcement waiver is reported as **potentially eligible** only; it is not silently applied.

## SI-unit safety

All internal equilibrium is N-mm-MPa. AASHTO US-customary source constants are explicitly converted at the analysis-module boundary:

- `1 ksi = 6.894757293168361 MPa`
- roughened girder/slab `c = 0.28 ksi = 1.930532 MPa`
- normal-weight roughened girder/slab `K2 = 1.8 ksi = 12.410563 MPa`
- interface `fy <= 60 ksi = 413.685438 MPa`
- Article 5.7.4.2 coefficient `0.05 ksi = 0.344738 MPa`
- roughened-interface waiver stress `0.210 ksi = 1.447899 MPa`

A dedicated regression evaluates the same AASHTO demand and resistance example independently in US customary units and SI units and requires numerical equivalence after conversion.

## Reused project sources

- `bvi` defaults to I-Girder top-flange `B1`; manual override is available.
- Final ULS active station `Vuy` is reused as the interface-demand source.
- Existing station-specific strand/debonding participation is reused to determine the tension-steel centroid.
- Existing Beam/Girder shear-reinforcement zones provide bar size, legs, spacing, and `fy` for `Avf`.
- No `Avf` strength credit is taken until the user confirms the girder stirrups cross the interface and are fully developed/anchored in the CIP deck.

## UI / status behavior

Final Composite Flexure now contains a dedicated **Girder–Deck Interface Shear — AASHTO 5.7.4** panel with:

- surface-condition selection,
- AUTO / manual `bvi`,
- interface stirrup anchorage confirmation,
- current/stale stored-result ownership,
- demand/resistance chart,
- governing cards,
- unit-conversion trace,
- station audit table.

Final Composite overall status is:

- `FAIL` if section flexure fails or interface shear fails,
- `PASS` only when current section flexure and current interface shear both pass,
- otherwise `REVIEW` / `STALE` as applicable.

Changing interface-only detailing does not invalidate the Final Composite Mn calculation; the interface gate owns a separate fingerprint and stored result.

## Explicitly unchanged

- Construction-stage auto demand and noncomposite flexure.
- Final Composite Mu, Mn, phiMn and neutral-axis solver.
- Final effective prestress calculation.
- Effective-width and deck-longitudinal-rebar credit policies.
- Current positive-flexure-only Final Composite scope; negative composite flexure remains a separate future check.

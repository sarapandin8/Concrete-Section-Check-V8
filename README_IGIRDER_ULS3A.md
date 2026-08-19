# IGIRDER.ULS3A — Composite Flexure Audit Closeout

This milestone is a focused semantic/audit closeout on top of IGIRDER.ULS3 for **Precast I-Girder: Bridge · Precast Composite Girder**.

## Changes

- Synchronizes the Construction and Final Composite selected-command card with the result calculated in the same Streamlit interaction. The command card no longer remains `NOT CALCULATED` while current result cards/plots are already displayed.
- Adds governing-section neutral-axis evidence to Final Composite positive flexure (`c` from the interpolated +Mx PMM slice at Pu, plus compression-face angle).
- Adds an explicit AASHTO LRFD 5.6.3.2.6 applicability card:
  - `SATISFIED` when the neutral axis is below the CIP deck and inside the prestressed girder,
  - `NOT REQUIRED` when the neutral axis remains within the deck,
  - `REVIEW` if the neutral-axis audit falls outside the composite section depth.
- Adds visible deck longitudinal-rebar credit status on Final Composite flexure:
  - `EXCLUDED` for the conservative default,
  - `INCLUDED` with effective longitudinal As when valid credit is enabled,
  - `REVIEW` if credit is requested without a valid active deck-rebar layer.
- Adds neutral-axis columns to the flexure audit table.
- Bumps the Final Composite stored-result version so older ULS3 results are recalculated with the new audit evidence.

## Explicitly deferred

Per project decision, this milestone **does not** add automatic pretension transfer/development-length reduction to the full-span phiMn curve. Existing section-strength/debonding behavior is preserved. End-zone transfer/development effects remain a later dedicated milestone.

## Engineering calculations unchanged

- Construction auto-demand equations are unchanged.
- Construction midspan/noncomposite section solver is unchanged.
- Final Composite section geometry, lower-f'c conservative basis, Final effective prestress, station strand/debonding participation, phi policy, and imported Final ULS demand are unchanged.
- Girder-deck interface shear remains a separate pending composite-action gate.

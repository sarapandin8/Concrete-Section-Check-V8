# CROSSBEAM.ANALYSIS4C7D21 — Final Service compression-reference continuity

## Scope

Close the Final Service chart readability issue where the red `0.60f'c` compression trace visually disappeared through Class C regions.

## Changes

- Plot `0.60f'c` as a continuous full-member **compression reference** trace.
- Keep the engineering acceptance contract unchanged:
  - Class U/T: `0.60f'c` remains the active gross-section total-load compression limit.
  - Class C: the active gross-section compression-limit field remains `N/A`; cracked transformed-section verification is still required.
- Update chart subtitle/caption so the continuous line cannot be mistaken for an active Class C acceptance criterion.
- Preserve the existing Class U and Class C tension-classification thresholds and the Segmental `0.70 MPa` physical-joint Final Service gate.

## Engineering equations

No stress equation, ACI classification equation, prestress/demand routing, physical-joint criterion, or stored-result ownership logic was changed.

## Repo summary

Show the Final Service `0.60f'c` compression line continuously as a reference across the member while keeping it active only for Class U/T and retaining Class C cracked-analysis semantics.

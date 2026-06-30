# PRESTRESS.DEBOND.ANALYSIS1 — Station-Based Debonded Strand Participation

## Purpose

This milestone makes debonded-strand input usable as a station-based analysis handoff instead of remaining only drawing/preview metadata.

It adds an explicit row-level station participation dataframe that converts the current girder strand layout table into effective strand count, effective Aps, stage Pe, and yps metadata at each station. The model is still guarded and step-function based.

## Source of truth

The editable strand layout table remains the source of truth:

- `Left debond (m)`
- `Right debond (m)`
- `Debonded strand nos`
- strand row count, area, y-from-bottom, and Pe force-state columns

`Debond pattern (mm)` remains legacy/drawing metadata only and is not the primary analysis input.

## Station participation model

For each active row and station `x`:

- if `x < left_debond`, selected debonded strands in that row are excluded;
- if `x > L - right_debond`, selected debonded strands in that row are excluded;
- otherwise all row strands are effective;
- blank `Debonded strand nos` with nonzero left/right debond preserves legacy row-based behavior where the whole row is excluded inside the sleeve.

The row-level handoff now reports:

- total strands;
- debonded strands;
- effective strands;
- ineffective strands;
- left/right sleeve-active flags;
- effective Aps;
- effective transfer/construction/final Pe;
- yps for each effective row.

## Analysis scope

This milestone does **not** perform final code-certified debonding checks.

Still outside scope:

- transfer-length force ramp after debond sleeve termination;
- development length / anchorage checks;
- end-zone bursting/splitting checks;
- final AASHTO/ACI debonding certification;
- changes to SLS/ULS stress equations.

## UI change

The Prestress → Effective prestress preview tab now includes an expander named:

`Row-level station participation / analysis handoff`

This gives users and future solver code a direct audit table showing which strands are effective at each critical station.

## Regression protection

Added/updated tests verify that a row with 9 strands and `Debonded strand nos = 1,9` has:

- 7 effective strands inside the left/right sleeve;
- 9 effective strands at midspan;
- stage Pe and Aps reduced consistently inside the sleeve.

# PRESTRESS.RAIL.UGIRDER2 — Correct Railway U-Girder Row 5 Strand Columns

## Scope

This milestone corrects the drawing-based default strand pattern for the Railway U-Girder preset.

The previous Railway U-Girder starter layout used a continuous four-strand block on Row 5. The user-provided drawing review clarified that Row 5 (top strand row) on both the left and right side blocks shall use 9-column grid positions:

```text
Column 3, Column 4, Column 6, Column 7
```

The corrected Row 5 pattern therefore skips the middle grid column and uses:

```text
zero-based grid indices: 2, 3, 5, 6
```

## Engineering interpretation

The strand grid remains unchanged:

```text
outside edge distance = 130 mm
spacing               = 55 mm
inside edge distance  = 80 mm
bottom side width     = 650 mm
```

For the left side, Row 5 now resolves to:

```text
x = -2510, -2455, -2345, -2290 mm
```

For the right side, Row 5 now resolves to:

```text
x = 2510, 2455, 2345, 2290 mm
```

The row count remains unchanged:

```text
Row 1 = 9 strands per side
Row 2 = 9 strands per side
Row 3 = 7 strands per side
Row 4 = 7 strands per side
Row 5 = 4 strands per side
Total = 36 strands per side = 72 strands total
```

## Out of scope

No changes were made to:

- prestress force calculations
- effective prestress preview equations
- debond symbol metadata rules
- station-based debonding logic
- concrete geometry
- PMM / SLS / shear / torsion solvers
- report generation
- project schema

This is a strand-layout correction only.

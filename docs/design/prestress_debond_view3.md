# PRESTRESS.DEBOND.VIEW3 — Symmetric Auto-Mirror and Label Cleanup

## Scope

This milestone refines the `Debonding along span` view for prestressed girder workflows, with special handling for the Railway U-Girder symmetric layout.

## Changes

- Keeps `Left debond (m)`, `Right debond (m)`, and `Debonded strand nos` as the editable source of truth.
- For Railway U-Girder with `Symmetric left/right` debonding, the L-side row data is mirrored automatically to the matching R-side row:
  - left/right debond lengths,
  - debonded strand number selection,
  - legacy debond pattern metadata.
- If legacy project data contains only R-side debond data, it is copied back to the matching L row to avoid data loss.
- Simplifies the left-side schematic labels into single-line row labels to avoid overlapping text.
- Increases the debonding elevation schematic height and left margin so row labels remain readable in compressed Streamlit layouts.
- Keeps dimension labels as bottom dimension lines rather than placing repeated sleeve-length labels on each row.

## Engineering guard

This milestone is UI/detailing metadata only. It does not change prestress effective force, loss calculation, station-based effective prestress preview, SLS stress, PMM, shear/torsion, geometry, section properties, report, or project schema equations.

## Source-of-truth policy

For symmetric Railway U-Girder detailing, engineers should edit the L rows. Matching R rows are auto-filled during normalization so the table remains symmetric and the debonding schematic stays consistent.

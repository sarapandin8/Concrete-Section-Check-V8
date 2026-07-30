# CROSSBEAM.LOADS1A — Compact Selected Station-Force ULS/SLS Import

## Purpose

Prepare the Portal Frame Crossbeam Loads workspace for the Analysis phase while preserving the established Concrete Section Pro member workflow: the engineer selects the design-force rows required at each station in the external FEA program and imports row-coupled `P / V2 / T / M3` resultants. The app does not require or reconstruct raw frame-element I/J-end output.

## Accepted engineering workflow

1. Concrete Section Pro calculates the adopted final prestress loss.
2. The engineer applies the uniform system-average final loss to the Tendons in the external portal-frame FEA model exactly once.
3. External FEA calculates primary and secondary prestress response and final-stage load combinations.
4. The engineer selects the ULS and SLS force rows needed at each design station.
5. Loads imports the selected rows; Analysis will use them directly without adding effective prestress or secondary prestress again.

## Compact table schemas

ULS:

`Active | Station s (m) | Check Point | Case Name | P | V2 | T | M3 | Note`

SLS:

`Active | Station s (m) | Check Point | Case Name | Stage | P | V2 | T | M3 | Note`

`Check Point` is optional for a single row at one Case/Stage/Station. It becomes required only when the engineer intentionally keeps more than one selected row at the same station, for example `C1-Left` and `C1-Right`.

## Source contract and canonical storage

A collapsed FEA source panel records:

- FEA program and model/revision;
- source force and moment units;
- source `P / V2 / T / M3` sign conventions;
- adopted uniform system-average total prestress loss;
- Prestress Source ID and Contract ID;
- confirmation that prestress is applied once;
- confirmation that external FEA includes secondary prestress;
- confirmation that ULS/SLS rows are final-stage responses;
- confirmation that all four forces in each row come from the same FEA output state.

New imports are converted once to canonical Crossbeam storage:

- force: `kN`;
- moment/torsion: `kN·m`;
- `P`: compression positive;
- `V2`: upward positive;
- `T`: right-hand positive about increasing station `s`;
- `M3`: sagging positive.

Changing source-unit or sign selectors later does not reinterpret applied rows.

## Validation and Analysis handoff

The Loads workspace validates:

- complete FEA source declarations;
- adopted prestress loss between 0% and 60%;
- stations within `0 ≤ s ≤ L`;
- finite `P / V2 / T / M3` values;
- unique `Case + Stage + Station + Check Point` rows;
- explicit Check Point labels when multiple rows share one Case/Stage/Station;
- at least one active ULS row and one active SLS row.

When both tables pass, the app creates a fingerprinted canonical station-force handoff for the future Analysis workflow. LOADS1A does not run section strength or service-stress calculations.

## Persistence and compatibility

- ULS/SLS rows, FEA source contract, and Prestress handoff link persist in Project JSON.
- Older Crossbeam load tables without `Check Point` remain compatible and receive a blank optional column.
- Construction-stage FEA response used by Time-Dependent prestress loss remains owned by `Sections → Prestress Loss → Time-Dependent`.
- No Prestress Loss equation, section solver, or non-Crossbeam load workflow is changed.

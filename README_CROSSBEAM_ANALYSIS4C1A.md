# CROSSBEAM.ANALYSIS4C1A — As / Aℓ Role Summary

## Purpose

Clarify the relationship between ordinary longitudinal reinforcement used by the direct flexure solver (`As`) and the outer-cage-associated subset credited as longitudinal torsion reinforcement (`Aℓ`) in the Crossbeam Combined Reinforcement Preview.

## Change

The reinforcement source-audit row above the combined cross-section figure now contains four cards in this order:

1. `Shear reinforcement — Av`
2. `Outer torsion cage — At`
3. `Longitudinal flexure — As`
4. `Longitudinal torsion — Aℓ`

The new `As` card reports:

- total physical ordinary longitudinal bar count;
- total ordinary longitudinal steel area;
- Outer and Inner contributions for Hollow sections;
- that the section/template bars are included in the flexure source, while station-specific development and physical-joint credit remains controlled in Analysis.

The `Aℓ` card now states explicitly that:

- Outer-cage-associated bars are an `Aℓ` subset of the physical `As` bars;
- Inner-face bars remain in `As` but are excluded from outer-cage `Aℓ` credit;
- `Aℓ` is not additional duplicate steel.

## Engineering behavior

- No reinforcing bar is added, deleted, or duplicated.
- No direct P–M3 equation or solver input is changed.
- No Shear, Torsion, or Combined V+T equation is changed.
- No Project JSON schema or persistence behavior is changed.
- No Flexure, Shear, or Torsion result is changed.

## Repo summary

Show physical longitudinal `As` beside torsion-credit `Aℓ` in the Crossbeam reinforcement preview and make clear that `Aℓ` is a cage-associated subset, not duplicate steel.

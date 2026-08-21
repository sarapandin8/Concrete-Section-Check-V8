# IGIRDER.ULS6A — Torsion Chart Threshold Visual Clarity

**Date:** 2026-08-21  
**Baseline:** `concrete-section-pro_IGIRDER-ULS6-prestressed-torsion-general-procedure.zip`  
**Scope:** UI/chart-only closeout for the Precast I-Girder standalone ULS Torsion workspace. Engineering equations, result versions, input hashes, and solver outputs are unchanged.

## Visual QA issue closed

The ULS6 Torsion chart previously rendered `+/-phiTcr` and `+/-0.25phiTcr` with the same orange dashed style and separate positive/negative legend entries. Static PDF output therefore made the cracking reference and the investigation threshold difficult to distinguish.

ULS6A applies the shared Concrete Section Pro chart language:

- `±phiTn` — red dashed check/capacity line; one compact legend item for the signed pair.
- `±phiTcr` — orange dashed cracking-reference line; one compact legend item for the signed pair.
- `±0.25phiTcr` — purple dotted investigation-threshold line; one compact legend item for the signed pair.
- Positive and negative traces remain individually hoverable even though each pair has one legend entry.
- Duplicate capacity/reference legends across multiple load cases are suppressed.

## Title and caption semantics

The subtitle now reflects what is actually available:

- `demand vs phiTn / torsion thresholds` when transverse torsion capacity is ready;
- `demand vs torsion thresholds — phiTn not ready` when only cracking/threshold references are available;
- `demand only — phiTn not ready` when no torsion capacity/reference source is available.

For the Precast I-Girder route, the chart caption now explicitly identifies the red `±phiTn`, orange `±phiTcr`, and purple `±0.25phiTcr` meanings. When the closed-loop torsion layout is not ready, the caption states that `±phiTn` is intentionally hidden rather than implying that it is plotted.

## Engineering scope unchanged

ULS6A does **not** change:

- AASHTO 5.7.2.1 torsion investigation threshold;
- `Tcr`, `K`, prestress or axial-force treatment;
- torsion-modified `Veff`;
- station-dependent General Procedure `epsilon_s`, `beta`, or `theta`;
- `Tn` / `phiTn` equations;
- transverse reinforcement design-fy policy;
- closed-loop/detailing gates;
- standalone Torsion certification boundary;
- Shear, Flexure, Interface Shear, or Combined V+T solver behavior;
- stored result/cache versions or project JSON schema.

This milestone is visual semantics only.

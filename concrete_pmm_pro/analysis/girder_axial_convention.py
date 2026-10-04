"""ULS girder axial input convention; source rows are never rewritten.

CSI frame P is tension-positive. Section equilibrium uses compression-positive
N; AASHTO shear/torsion formulas may then explicitly use tension-positive N.
Only readers of raw Loads rows call this adapter. Canonical LoadCase values
must not be passed through it again.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

SETTINGS_KEY = "beam_girder_uls_axial_convention"
VERSION = "IGIRDER.FLEXSIGN1.axial-input-v1"
COMPRESSION_POSITIVE = "COMPRESSION_POSITIVE"
CSI_TENSION_POSITIVE = "CSI_TENSION_POSITIVE"
LABELS = {
    CSI_TENSION_POSITIVE: "CSiBridge / CSI frame P — positive tension, negative compression",
    COMPRESSION_POSITIVE: "Already converted Nu — positive compression, negative tension",
}


def axial_convention(state: Mapping) -> dict:
    if str(state.get("section_preset_key") or "parametric_i_girder") != "parametric_i_girder":
        return {"input_sign": COMPRESSION_POSITIVE, "declared": False}
    raw = state.get(SETTINGS_KEY)
    if raw is None:
        metadata = state.get("project_metadata") or {}
        raw = metadata.get(SETTINGS_KEY) if isinstance(metadata, Mapping) else None
    # Legacy projects retain their numerical behavior until the source is
    # explicitly selected. Never infer it from unrelated Crossbeam metadata.
    if raw is None:
        return {"input_sign": COMPRESSION_POSITIVE, "declared": False}
    if not isinstance(raw, Mapping) or raw.get("input_sign") not in LABELS:
        raise ValueError("Select a valid girder ULS Nu input convention in Loads or Analysis.")
    return {"input_sign": raw["input_sign"], "declared": True}


def axial_trace(row: Mapping, state: Mapping) -> dict:
    cfg = axial_convention(state)
    try:
        raw = float(row.get("Nu", 0.0))
    except (ValueError, TypeError):
        raw = float("nan")
    multiplier = -1.0 if cfg["input_sign"] == CSI_TENSION_POSITIVE else 1.0
    canonical = raw * multiplier
    return {
        "Nu input kN": raw,
        "Nu input convention": cfg["input_sign"],
        "Nu conversion factor": multiplier,
        "Nu kN": canonical,
        "Nu action": ("COMPRESSION" if canonical > 0 else "TENSION" if canonical < 0 else "ZERO") if math.isfinite(canonical) else "INVALID",
        "Nu AASHTO tension-positive kN": -canonical,
    }


def axial_demand_compression_positive_kN(row: Mapping, state: Mapping) -> float:
    return axial_trace(row, state)["Nu kN"]

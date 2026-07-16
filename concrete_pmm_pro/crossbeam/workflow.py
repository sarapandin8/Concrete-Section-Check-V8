"""Data-foundation helpers for the portal-frame prestressed crossbeam workflow.

CROSSBEAM.WF1 intentionally stops before stress/loss/capacity solvers.  These
helpers define the durable engineering defaults and the first station-based
layout/tendon source of truth used by future PT loss and SLS/ULS milestones.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CROSSBEAM_LENGTH_M = 20.0
DEFAULT_STRAND_FPU_MPA = 1860.0
DEFAULT_STRAND_APS_MM2 = 140.0
DEFAULT_FPJ_RATIO = 0.75
DEFAULT_TENDON_COUNT = 4
DEFAULT_STRANDS_PER_TENDON = 19
DEFAULT_JACKING_END = "Both"
DEFAULT_TENDON_TYPE = "Internal"

CROSSBEAM_SOLID_PRESET_KEY = "crossbeam_rectangular_solid_bottom_fillets"
CROSSBEAM_SOLID_PRESET_NAME = "PC Crossbeam — Rectangular Solid with Bottom Fillets"
CROSSBEAM_HOLLOW_PRESET_KEY = "crossbeam_rectangular_hollow_bottom_fillets_inner_chamfers"
CROSSBEAM_HOLLOW_PRESET_NAME = "PC Crossbeam — Rectangular Hollow with Bottom Fillets and Inner Chamfers"
CROSSBEAM_SECTION_PRESETS = (
    (CROSSBEAM_SOLID_PRESET_KEY, CROSSBEAM_SOLID_PRESET_NAME, "Solid"),
    (CROSSBEAM_HOLLOW_PRESET_KEY, CROSSBEAM_HOLLOW_PRESET_NAME, "Hollow"),
)

TENDON_TYPE_OPTIONS = ("Internal", "External")
JACKING_END_OPTIONS = ("Left", "Right", "Both")


def calculated_fpj_mpa(fpu_mpa: float = DEFAULT_STRAND_FPU_MPA, fpj_ratio: float = DEFAULT_FPJ_RATIO) -> float:
    """Return default jacking stress fpj in MPa."""

    return float(fpu_mpa) * float(fpj_ratio)


def centroid_from_top_mm(total_depth_mm: float, centroid_y_from_bottom_mm: float) -> float:
    """Return centroid depth measured downward from the top fiber."""

    return float(total_depth_mm) - float(centroid_y_from_bottom_mm)


def tendon_eccentricity_from_top_mm(
    tendon_depth_from_top_mm: float,
    *,
    total_depth_mm: float,
    centroid_y_from_bottom_mm: float,
) -> float:
    """Return tendon eccentricity relative to section centroid.

    User-facing tendon profiles are always entered as depth measured downward
    from the top surface.  Internally, positive eccentricity means the tendon is
    below the centroid; negative means it is above the centroid.
    """

    return float(tendon_depth_from_top_mm) - centroid_from_top_mm(total_depth_mm, centroid_y_from_bottom_mm)


def normalize_tendon_type(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text == "external":
        return "External"
    return "Internal"


def normalize_jacking_end(value: Any) -> str:
    text = str(value or "").strip().casefold()
    normalized = {option.casefold(): option for option in JACKING_END_OPTIONS}
    if text in normalized:
        return normalized[text]
    return DEFAULT_JACKING_END


def default_crossbeam_segment_rows(length_m: float = DEFAULT_CROSSBEAM_LENGTH_M) -> list[dict[str, Any]]:
    """Return first-release station layout rows for a solid/hollow crossbeam.

    The rows are intentionally editable UI seed data.  WF1 does not run station
    checks; it establishes the segmented-section source of truth.
    """

    L = max(float(length_m), 1.0)
    boundaries = [0.0, 0.15 * L, 0.35 * L, 0.50 * L, 0.65 * L, 0.85 * L, L]
    presets = [
        CROSSBEAM_SECTION_PRESETS[0],
        CROSSBEAM_SECTION_PRESETS[1],
        CROSSBEAM_SECTION_PRESETS[0],
        CROSSBEAM_SECTION_PRESETS[1],
        CROSSBEAM_SECTION_PRESETS[0],
        CROSSBEAM_SECTION_PRESETS[1],
    ]
    return [
        {
            "Segment": f"S{i + 1}",
            "x_start_m": round(boundaries[i], 3),
            "x_end_m": round(boundaries[i + 1], 3),
            "Section type / preset": presets[i][1],
            "Section preset key": presets[i][0],
            "Section role": presets[i][2],
            # Compatibility alias retained for accepted WF1/UI1 state readers.
            "Section ID": presets[i][0],
        }
        for i in range(len(presets))
    ]


def default_crossbeam_tendon_rows(
    length_m: float = DEFAULT_CROSSBEAM_LENGTH_M,
    *,
    tendon_count: int = DEFAULT_TENDON_COUNT,
    section_depth_mm: float = 1500.0,
) -> list[dict[str, Any]]:
    """Return seed tendon rows using top-surface profile coordinates."""

    count = max(int(tendon_count), 3)
    L = max(float(length_m), 1.0)
    top_zone = max(120.0, 0.18 * float(section_depth_mm))
    low_zone = max(top_zone + 100.0, 0.72 * float(section_depth_mm))
    rows: list[dict[str, Any]] = []
    for index in range(count):
        tendon_id = f"T{index + 1}"
        rows.append(
            {
                "Tendon ID": tendon_id,
                "Type": DEFAULT_TENDON_TYPE,
                "Strands": DEFAULT_STRANDS_PER_TENDON,
                "Aps/strand mm²": DEFAULT_STRAND_APS_MM2,
                "fpu MPa": DEFAULT_STRAND_FPU_MPA,
                "fpj/fpu": DEFAULT_FPJ_RATIO,
                "Jacking end": DEFAULT_JACKING_END,
                "x/L": 0.0,
                "x_m": 0.0,
                "Depth from top mm": round(top_zone, 1),
            }
        )
        rows.append(
            {
                "Tendon ID": tendon_id,
                "Type": DEFAULT_TENDON_TYPE,
                "Strands": DEFAULT_STRANDS_PER_TENDON,
                "Aps/strand mm²": DEFAULT_STRAND_APS_MM2,
                "fpu MPa": DEFAULT_STRAND_FPU_MPA,
                "fpj/fpu": DEFAULT_FPJ_RATIO,
                "Jacking end": DEFAULT_JACKING_END,
                "x/L": 0.5,
                "x_m": round(0.5 * L, 3),
                "Depth from top mm": round(low_zone, 1),
            }
        )
        rows.append(
            {
                "Tendon ID": tendon_id,
                "Type": DEFAULT_TENDON_TYPE,
                "Strands": DEFAULT_STRANDS_PER_TENDON,
                "Aps/strand mm²": DEFAULT_STRAND_APS_MM2,
                "fpu MPa": DEFAULT_STRAND_FPU_MPA,
                "fpj/fpu": DEFAULT_FPJ_RATIO,
                "Jacking end": DEFAULT_JACKING_END,
                "x/L": 1.0,
                "x_m": round(L, 3),
                "Depth from top mm": round(top_zone, 1),
            }
        )
    return rows

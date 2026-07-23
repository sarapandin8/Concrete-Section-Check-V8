"""Crossbeam PTLOSS3B1A construction/stressing-stage source model.

This module defines only the auditable *source model* needed before a future
Portal-Frame stressing-stage solver can calculate primary/secondary prestress,
contact reactions, and source-derived ``f_cgp``.  It deliberately does not
perform frame analysis.

The workflow assumptions accepted for PTLOSS3B1A are:
- Crossbeam construction method is either Precast Segmental or Cast-in-Place.
- Column bases are fixed by the current Crossbeam project assumption.
- Column plan dimensions are defined relative to the Crossbeam axis: Btrans is transverse/normal to s, and Blong is parallel/along s.
- Temporary erection support/falsework is continuous over the full Crossbeam
  length, initially in contact, vertical compression-only, and allowed to lift
  off automatically in the future stage solver.
- Tendons are stressed as user-confirmed symmetric pairs/groups.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite, pi, sqrt
from typing import Any

from concrete_pmm_pro.core.concrete_materials import aci_concrete_ec_mpa

CONSTRUCTION_METHOD_PRECAST = "Precast Segmental"
CONSTRUCTION_METHOD_CIP = "Cast-in-Place"
CONSTRUCTION_METHOD_OPTIONS = (
    CONSTRUCTION_METHOD_PRECAST,
    CONSTRUCTION_METHOD_CIP,
)

COLUMN_SHAPE_RECT_CHAMFER = "Rectangular — Equal Chamfer 4 Corners"
COLUMN_SHAPE_RECT_FILLET = "Rectangular — Equal Fillet 4 Corners"
COLUMN_SHAPE_CIRCULAR = "Circular"
COLUMN_SHAPE_OPTIONS = (
    COLUMN_SHAPE_RECT_CHAMFER,
    COLUMN_SHAPE_RECT_FILLET,
    COLUMN_SHAPE_CIRCULAR,
)

COLUMN_BASE_ASSUMPTION = "FIXED"
TEMP_SUPPORT_EXTENT = "Continuous full Crossbeam length"
TEMP_SUPPORT_INITIAL_STATE = "IN CONTACT"
TEMP_SUPPORT_BEHAVIOR = "COMPRESSION-ONLY"
TEMP_SUPPORT_LIFTOFF = "AUTOMATIC"
TEMP_SUPPORT_VERTICAL_MODEL = "RIGID VERTICAL CONTACT"

DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO = 0.80
DEFAULT_COLUMN_FC_MPA = 35.0
DEFAULT_COLUMN_HEIGHT_M = 10.0
DEFAULT_COLUMN_BTRANS_MM = 2000.0
DEFAULT_COLUMN_BLONG_MM = 2000.0
DEFAULT_COLUMN_CORNER_MM = 200.0
DEFAULT_COLUMN_DIAMETER_MM = 2000.0
DEFAULT_PRECAST_CLOSURE_STRENGTH_MPA = 50.0


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def _records(values: Any) -> list[dict[str, Any]]:
    if hasattr(values, "to_dict"):
        try:
            return [
                dict(row)
                for row in values.to_dict(orient="records")
                if isinstance(row, Mapping)
            ]
        except (TypeError, ValueError):
            return []
    if isinstance(values, (list, tuple)):
        return [dict(row) for row in values if isinstance(row, Mapping)]
    return []


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(message.strip() for message in messages if message.strip()))


def normalize_construction_method(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in CONSTRUCTION_METHOD_OPTIONS else CONSTRUCTION_METHOD_PRECAST


def normalize_column_shape(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in COLUMN_SHAPE_OPTIONS else COLUMN_SHAPE_RECT_CHAMFER


def default_column_stage_rows(length_m: float) -> list[dict[str, Any]]:
    """Return the practical two-column seed used by new Crossbeam projects.

    C1 is centered at ``s=0`` and C2 at ``s=L``.  The plan-section defaults
    follow the accepted Crossbeam source convention and remain fully editable.
    Dormant shape values are retained so switching between rectangular and
    circular preview shapes does not destroy the user's last dimensions.
    """

    length = max(_float(length_m), 0.0)
    return [
        {
            "Column ID": "C1",
            "Station s (m)": 0.0,
            "Height (m)": DEFAULT_COLUMN_HEIGHT_M,
            "Shape": COLUMN_SHAPE_RECT_CHAMFER,
            "Btrans (mm)": DEFAULT_COLUMN_BTRANS_MM,
            "Blong (mm)": DEFAULT_COLUMN_BLONG_MM,
            "Corner (mm)": DEFAULT_COLUMN_CORNER_MM,
            "Diameter (mm)": DEFAULT_COLUMN_DIAMETER_MM,
            "f'c (MPa)": DEFAULT_COLUMN_FC_MPA,
        },
        {
            "Column ID": "C2",
            "Station s (m)": length,
            "Height (m)": DEFAULT_COLUMN_HEIGHT_M,
            "Shape": COLUMN_SHAPE_RECT_CHAMFER,
            "Btrans (mm)": DEFAULT_COLUMN_BTRANS_MM,
            "Blong (mm)": DEFAULT_COLUMN_BLONG_MM,
            "Corner (mm)": DEFAULT_COLUMN_CORNER_MM,
            "Diameter (mm)": DEFAULT_COLUMN_DIAMETER_MM,
            "f'c (MPa)": DEFAULT_COLUMN_FC_MPA,
        },
    ]


def canonical_column_stage_rows(values: Any, *, length_m: float) -> list[dict[str, Any]]:
    rows = _records(values)
    if not rows:
        rows = default_column_stage_rows(length_m)
    length = max(_float(length_m), 0.0)
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        output.append(
            {
                "Column ID": str(row.get("Column ID") or f"C{index}").strip() or f"C{index}",
                "Station s (m)": min(max(_float(row.get("Station s (m)")), 0.0), length),
                "Height (m)": max(_float(row.get("Height (m)")), 0.0),
                "Shape": normalize_column_shape(row.get("Shape")),
                "Btrans (mm)": max(_float(row.get("Btrans (mm)", row.get("B local-2 (mm)"))), 0.0),
                "Blong (mm)": max(_float(row.get("Blong (mm)", row.get("H local-3 (mm)"))), 0.0),
                "Corner (mm)": max(_float(row.get("Corner (mm)")), 0.0),
                "Diameter (mm)": max(_float(row.get("Diameter (mm)")), 0.0),
                "f'c (MPa)": max(_float(row.get("f'c (MPa)"), DEFAULT_COLUMN_FC_MPA), 0.0),
            }
        )
    output.sort(key=lambda row: (row["Station s (m)"], row["Column ID"]))
    return output


def column_section_properties(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return exact gross A/I properties for the three accepted column shapes.

    ``Btrans`` is normal/transverse to the Crossbeam longitudinal ``s`` axis.
    ``Blong`` is parallel to/along the Crossbeam ``s`` axis.  For the future
    in-plane portal-frame solver, ``I22`` is the inertia about the transverse
    axis (therefore it uses the longitudinal dimension cubed), while ``I33``
    is the inertia about the longitudinal axis.
    """

    shape = normalize_column_shape(row.get("Shape"))
    b = max(_float(row.get("Btrans (mm)", row.get("B local-2 (mm)"))), 0.0)
    h = max(_float(row.get("Blong (mm)", row.get("H local-3 (mm)"))), 0.0)
    corner = max(_float(row.get("Corner (mm)")), 0.0)
    diameter = max(_float(row.get("Diameter (mm)")), 0.0)
    issues: list[str] = []

    if shape == COLUMN_SHAPE_CIRCULAR:
        if diameter <= 0.0:
            issues.append("Circular column diameter must be positive.")
            area = i22 = i33 = 0.0
        else:
            area = pi * diameter**2 / 4.0
            i22 = i33 = pi * diameter**4 / 64.0
    elif shape == COLUMN_SHAPE_RECT_CHAMFER:
        if b <= 0.0 or h <= 0.0:
            issues.append("Rectangular column Btrans and Blong must be positive.")
            area = i22 = i33 = 0.0
        elif corner < 0.0 or corner >= 0.5 * min(b, h):
            issues.append("Equal chamfer must be smaller than half the minimum rectangular dimension.")
            area = i22 = i33 = 0.0
        else:
            c = corner
            area = b * h - 2.0 * c**2
            tri_area = 0.5 * c**2
            tri_i_centroid = c**4 / 36.0
            y = h / 2.0 - c / 3.0
            x = b / 2.0 - c / 3.0
            i22 = b * h**3 / 12.0 - 4.0 * (tri_i_centroid + tri_area * y**2)
            i33 = h * b**3 / 12.0 - 4.0 * (tri_i_centroid + tri_area * x**2)
    else:  # equal fillet
        if b <= 0.0 or h <= 0.0:
            issues.append("Rectangular column Btrans and Blong must be positive.")
            area = i22 = i33 = 0.0
        elif corner < 0.0 or corner >= 0.5 * min(b, h):
            issues.append("Equal fillet radius must be smaller than half the minimum rectangular dimension.")
            area = i22 = i33 = 0.0
        else:
            r = corner
            area = b * h - (4.0 - pi) * r**2
            square_area = r**2
            square_i_centroid = r**4 / 12.0
            quarter_area = pi * r**2 / 4.0
            quarter_centroid_offset = 4.0 * r / (3.0 * pi) if r > 0.0 else 0.0
            quarter_i_centroid = r**4 * (pi / 16.0 - 4.0 / (9.0 * pi))

            square_y = h / 2.0 - r / 2.0
            square_x = b / 2.0 - r / 2.0
            quarter_y = h / 2.0 - r + quarter_centroid_offset
            quarter_x = b / 2.0 - r + quarter_centroid_offset

            i22 = (
                b * h**3 / 12.0
                - 4.0 * (square_i_centroid + square_area * square_y**2)
                + 4.0 * (quarter_i_centroid + quarter_area * quarter_y**2)
            )
            i33 = (
                h * b**3 / 12.0
                - 4.0 * (square_i_centroid + square_area * square_x**2)
                + 4.0 * (quarter_i_centroid + quarter_area * quarter_x**2)
            )

    fc = max(_float(row.get("f'c (MPa)"), DEFAULT_COLUMN_FC_MPA), 0.0)
    ec = aci_concrete_ec_mpa(fc) if fc > 0.0 else 0.0
    return {
        "Shape": shape,
        "Area (mm²)": area,
        "I22 (mm⁴)": i22,
        "I33 (mm⁴)": i33,
        "Ec (MPa)": ec,
        "EA (N)": ec * area,
        "EI22 (N-mm²)": ec * i22,
        "EI33 (N-mm²)": ec * i33,
        "issues": _dedupe(issues),
        "ready": not issues and area > 0.0 and i22 > 0.0 and i33 > 0.0 and ec > 0.0,
    }


def column_stage_property_rows(values: Any, *, length_m: float) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in canonical_column_stage_rows(values, length_m=length_m):
        props = column_section_properties(row)
        issues = list(props.get("issues") or [])
        if row["Height (m)"] <= 0.0:
            issues.append("Column height must be positive.")
        output.append(
            {
                **row,
                "Base": COLUMN_BASE_ASSUMPTION,
                "Area (m²)": props["Area (mm²)"] / 1.0e6,
                "I22 (m⁴)": props["I22 (mm⁴)"] / 1.0e12,
                "I33 (m⁴)": props["I33 (mm⁴)"] / 1.0e12,
                "Ec (MPa)": props["Ec (MPa)"],
                "Status": "READY" if props["ready"] and row["Height (m)"] > 0.0 else "INPUT REQUIRED",
                "Issue": "OK" if not issues else "; ".join(_dedupe(issues)),
            }
        )
    return output


def column_stage_summary(values: Any, *, length_m: float) -> dict[str, Any]:
    rows = column_stage_property_rows(values, length_m=length_m)
    issues: list[str] = []
    if len(rows) < 2:
        issues.append("At least two columns/support lines are required for the Portal Frame stage model.")
    ids = [str(row.get("Column ID") or "") for row in rows]
    if len(set(ids)) != len(ids):
        issues.append("Column IDs must be unique.")
    stations = [round(_float(row.get("Station s (m)")), 9) for row in rows]
    if len(set(stations)) != len(stations):
        issues.append("Column stations must be unique.")
    for row in rows:
        if row.get("Status") != "READY":
            issues.append(f"{row.get('Column ID')}: {row.get('Issue')}")
    issues = _dedupe(issues)
    return {
        "status": "COLUMN SOURCE READY" if rows and not issues else "INPUT REQUIRED",
        "ready": bool(rows) and not issues,
        "column_count": len(rows),
        "rows": rows,
        "issues": issues,
        "base_assumption": COLUMN_BASE_ASSUMPTION,
    }


def temporary_support_source(length_m: float) -> dict[str, Any]:
    return {
        "status": "SOURCE DEFINED",
        "start_s_m": 0.0,
        "end_s_m": max(_float(length_m), 0.0),
        "extent": TEMP_SUPPORT_EXTENT,
        "initial_state": TEMP_SUPPORT_INITIAL_STATE,
        "behavior": TEMP_SUPPORT_BEHAVIOR,
        "lift_off": TEMP_SUPPORT_LIFTOFF,
        "vertical_model": TEMP_SUPPORT_VERTICAL_MODEL,
        "note": (
            "Future stage solver must discretize the full supported range as compression-only vertical contact. "
            "Any contact point requiring tensile reaction must lift off and be re-analysed."
        ),
    }


def default_pair_sequence(group_rows: Any) -> list[str]:
    rows = [row for row in _records(group_rows) if str(row.get("Status") or "") == "PAIR READY"]
    return [str(row.get("Group ID") or "") for row in rows if str(row.get("Group ID") or "")]


def normalize_pair_sequence(value: Any, group_rows: Any) -> list[str]:
    available = default_pair_sequence(group_rows)
    if isinstance(value, str):
        requested = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple)):
        requested = [str(item).strip() for item in value if str(item).strip()]
    else:
        requested = []
    if len(requested) == len(available) and set(requested) == set(available):
        return requested
    return available


def stressing_pair_sequence_rows(group_rows: Any, sequence: Any) -> list[dict[str, Any]]:
    rows = _records(group_rows)
    by_id = {str(row.get("Group ID") or ""): row for row in rows}
    normalized = normalize_pair_sequence(sequence, rows)
    output: list[dict[str, Any]] = []
    for index, group_id in enumerate(normalized, start=1):
        row = by_id.get(group_id, {})
        output.append(
            {
                "Sequence": index,
                "Group ID": group_id,
                "Tendons stressed together": str(row.get("Tendons") or ""),
                "Group Pj (kN)": _float(row.get("Group Pj (kN)")),
                "Status": str(row.get("Status") or "REVIEW REQUIRED"),
            }
        )
    return output


def stressing_pair_sequence_summary(group_rows: Any, sequence: Any) -> dict[str, Any]:
    available = default_pair_sequence(group_rows)
    normalized = normalize_pair_sequence(sequence, group_rows)
    valid = bool(available) and len(normalized) == len(available) and set(normalized) == set(available)
    return {
        "status": "SEQUENCE READY — VERIFY CONSTRUCTION PROCEDURE" if valid else "REVIEW REQUIRED",
        "ready": valid,
        "group_count": len(available),
        "sequence": normalized,
        "rows": stressing_pair_sequence_rows(group_rows, normalized),
        "issues": [] if valid else ["Every verified stressing pair must appear exactly once in the stressing sequence."],
    }


def construction_stage_readiness(
    *,
    construction_method: Any,
    crossbeam_fc_mpa: float | None,
    stressing_strength_ratio: float,
    closure_required_mpa: float,
    column_rows: Any,
    length_m: float,
    group_rows: Any,
    pair_sequence: Any,
) -> dict[str, Any]:
    method = normalize_construction_method(construction_method)
    fc = max(_float(crossbeam_fc_mpa), 0.0)
    ratio = min(max(_float(stressing_strength_ratio, DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO), 0.1), 1.5)
    target = fc * ratio if fc > 0.0 else None
    closure_required = max(_float(closure_required_mpa), 0.0)
    columns = column_stage_summary(column_rows, length_m=length_m)
    sequence = stressing_pair_sequence_summary(group_rows, pair_sequence)
    temp_support = temporary_support_source(length_m)

    issues: list[str] = []
    strength_status = "REVIEW REQUIRED"
    if target is None:
        issues.append("Crossbeam f'c source is not available for the stressing-strength criterion.")
    else:
        strength_status = "DESIGN CRITERION DEFINED"

    closure_status = "NOT APPLICABLE"
    if method == CONSTRUCTION_METHOD_PRECAST:
        closure_status = "REVIEW REQUIRED"
        if closure_required <= 0.0:
            issues.append("Required joint/closure concrete strength at stressing must be defined for Precast Segmental construction.")
        else:
            closure_status = "DESIGN CRITERION DEFINED"

    if not columns["ready"]:
        issues.extend(columns["issues"])
    if not sequence["ready"]:
        issues.extend(sequence["issues"])

    issues = _dedupe(issues)
    ready = not issues
    return {
        "status": "DESIGN SOURCE READY — SOLVER NOT YET RELEASED" if ready else "DESIGN INPUT REQUIRED",
        "ready": ready,
        "construction_method": method,
        "crossbeam_fc_mpa": fc if fc > 0.0 else None,
        "stressing_strength_ratio": ratio,
        "target_stressing_strength_mpa": target,
        "strength_status": strength_status,
        "closure_required_mpa": closure_required if closure_required > 0.0 else None,
        "closure_status": closure_status,
        "columns": columns,
        "pair_sequence": sequence,
        "temporary_support": temp_support,
        "issues": issues,
        "solver_status": "LOCKED — PTLOSS3B1A SOURCE MODEL ONLY",
    }

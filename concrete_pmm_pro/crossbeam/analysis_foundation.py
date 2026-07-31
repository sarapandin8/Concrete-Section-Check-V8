"""Three-stage station-check input assembly for Portal Frame Crossbeam Analysis.

``CROSSBEAM.ANALYSIS1`` is deliberately solver-neutral.  It consumes the
validated Loads handoff, resolves the project Section ID and reinforcement
sources at every active design row, and preserves the original row-coupled
``P, V2, T, M3`` state.  No ACI strength or service-stress equation is evaluated
in this module.

The module also distinguishes physical Precast Segmental joints from
Cast-in-Place section/analysis-zone boundaries.  At an internal boundary a
source row can resolve to the left face (``s-``), right face (``s+``), or both
faces when the imported Check Point does not state a side.  Expanding one
row to two section contexts does not create a force envelope: both contexts
retain the same source-row identity and the same row-coupled resultants.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.crossbeam.rebar import (
    canonical_rebar_templates,
    canonical_rebar_zones,
    template_map,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.section_library import (
    canonical_section_definitions,
    section_property_records,
    validate_section_definitions,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CROSSBEAM_STATION_FORCE_HANDOFF_SCHEMA,
    canonical_sls_stage,
)
from concrete_pmm_pro.crossbeam.transverse import (
    canonical_transverse_templates,
    transverse_template_map,
)


CROSSBEAM_ANALYSIS_FOUNDATION_SCHEMA = "crossbeam-three-stage-station-foundation-v1"
CROSSBEAM_ANALYSIS_FOUNDATION_KEY = "crossbeam_analysis1_station_foundation"

DATASET_ULS_FINAL = "ULS Final Stage"
DATASET_SLS_TRANSFER = "SLS At Transfer"
DATASET_SLS_SERVICE = "SLS At Service"
DATASET_ORDER = (DATASET_ULS_FINAL, DATASET_SLS_TRANSFER, DATASET_SLS_SERVICE)

CONSTRUCTION_PRECAST_SEGMENTAL = "Precast Segmental"
CONSTRUCTION_CAST_IN_PLACE = "Cast-in-Place"

FACE_INTERIOR = "INTERIOR"
FACE_LEFT = "s-"
FACE_RIGHT = "s+"
FACE_END = "END"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if text in {"1", "true", "yes", "y", "on", "active", "ready"}:
        return True
    if text in {"0", "false", "no", "n", "off", "inactive", "blocked"}:
        return False
    return bool(default)


def canonical_construction_method(value: Any) -> str:
    text = _text(value).casefold().replace("_", " ").replace("-", " ")
    if "cast" in text and "place" in text:
        return CONSTRUCTION_CAST_IN_PLACE
    return CONSTRUCTION_PRECAST_SEGMENTAL


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def canonical_segment_rows(rows: Any) -> list[dict[str, Any]]:
    """Return ordered Segment/Zone rows used by station routing."""

    result: list[dict[str, Any]] = []
    for index, source in enumerate(_records(rows)):
        start = _float(source.get("x_start_m", source.get("s_start_m")), float("nan"))
        end = _float(source.get("x_end_m", source.get("s_end_m")), float("nan"))
        role = _text(source.get("Section role") or source.get("Role")).title()
        if role not in {"Solid", "Hollow"}:
            preset_text = _text(
                source.get("Section type / preset")
                or source.get("Section preset key")
                or source.get("Section ID")
            ).casefold()
            role = "Hollow" if "hollow" in preset_text else "Solid"
        result.append(
            {
                "Segment": _text(source.get("Segment") or source.get("Zone") or f"S{index + 1}"),
                "x_start_m": start,
                "x_end_m": end,
                "Section ID": _text(source.get("Section ID") or source.get("Section preset key")),
                "Section role": role,
            }
        )
    return sorted(result, key=lambda row: (row["x_start_m"], row["x_end_m"], row["Segment"]))


def validate_segment_rows(
    rows: Any,
    *,
    member_length_m: float,
    construction_method: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    segments = canonical_segment_rows(rows)
    errors: list[str] = []
    warnings: list[str] = []
    length = float(member_length_m)
    if not segments:
        errors.append("Crossbeam Segment / Zone Layout is required for Analysis station mapping.")
        return segments, errors, warnings
    tolerance = max(1.0e-7, abs(length) * 1.0e-8)
    seen_ids: set[str] = set()
    for index, row in enumerate(segments, start=1):
        label = row["Segment"] or f"row {index}"
        if not row["Segment"]:
            errors.append(f"Segment / Zone row {index} requires an ID.")
        elif row["Segment"] in seen_ids:
            errors.append(f"Duplicate Segment / Zone ID: {row['Segment']}.")
        seen_ids.add(row["Segment"])
        start = row["x_start_m"]
        end = row["x_end_m"]
        if not (math.isfinite(start) and math.isfinite(end)):
            errors.append(f"{label}: start and end stations must be finite numbers.")
            continue
        if end <= start:
            errors.append(f"{label}: end station must be greater than start station.")
        if start < -tolerance or end > length + tolerance:
            errors.append(f"{label}: station range must remain inside 0 <= s <= {length:.6f} m.")
        if not row["Section ID"]:
            errors.append(f"{label}: Section ID is required.")
        if construction_method == CONSTRUCTION_CAST_IN_PLACE and row["Section role"] != "Solid":
            errors.append(f"{label}: Cast-in-Place Analysis permits Solid Section IDs only.")
    if math.isfinite(segments[0]["x_start_m"]) and abs(segments[0]["x_start_m"]) > tolerance:
        errors.append("Segment / Zone Layout must start at s = 0.")
    if math.isfinite(segments[-1]["x_end_m"]) and abs(segments[-1]["x_end_m"] - length) > tolerance:
        errors.append(f"Segment / Zone Layout must end at s = {length:.6f} m.")
    for left, right in zip(segments, segments[1:]):
        delta = right["x_start_m"] - left["x_end_m"]
        if abs(delta) > tolerance:
            errors.append(
                f"Segment / Zone Layout {'gap' if delta > 0.0 else 'overlap'} between "
                f"{left['Segment']} and {right['Segment']}."
            )
    return segments, errors, warnings


def _side_hint(check_point: Any) -> str:
    text = _text(check_point).casefold()
    compact = text.replace(" ", "").replace("_", "").replace("−", "-")
    left_tokens = ("left", "s-", "minus", "i-end", "iend")
    right_tokens = ("right", "s+", "plus", "j-end", "jend")
    if any(token in compact for token in left_tokens):
        return "LEFT"
    if any(token in compact for token in right_tokens):
        return "RIGHT"
    return ""


def _segment_candidates(
    segments: Sequence[Mapping[str, Any]],
    station_m: float,
    *,
    member_length_m: float,
) -> list[dict[str, Any]]:
    tolerance = max(1.0e-7, abs(float(member_length_m)) * 1.0e-8)
    return [
        dict(row)
        for row in segments
        if float(row["x_start_m"]) - tolerance <= station_m <= float(row["x_end_m"]) + tolerance
    ]


def _boundary_contexts(
    candidates: Sequence[Mapping[str, Any]],
    *,
    station_m: float,
    member_length_m: float,
    check_point: str,
    construction_method: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve one or two one-sided section contexts at a station."""

    tolerance = max(1.0e-7, abs(float(member_length_m)) * 1.0e-8)
    ordered = sorted((dict(row) for row in candidates), key=lambda row: (row["x_start_m"], row["x_end_m"]))
    warnings: list[str] = []
    if not ordered:
        return [], warnings
    if len(ordered) == 1:
        row = ordered[0]
        at_end = abs(station_m) <= tolerance or abs(station_m - float(member_length_m)) <= tolerance
        return [
            {
                **row,
                "Station face": FACE_END if at_end else FACE_INTERIOR,
                "Boundary type": "Member end" if at_end else "Within Segment / Zone",
                "Physical segment joint": False,
            }
        ], warnings

    left = max(ordered, key=lambda row: row["x_start_m"] if row["x_start_m"] <= station_m + tolerance else -math.inf)
    right = min(ordered, key=lambda row: row["x_end_m"] if row["x_end_m"] >= station_m - tolerance else math.inf)
    # At a well-formed internal boundary, explicitly choose the row ending at s
    # and the row starting at s.  The fallback above protects legacy layouts.
    left_match = [row for row in ordered if abs(float(row["x_end_m"]) - station_m) <= tolerance]
    right_match = [row for row in ordered if abs(float(row["x_start_m"]) - station_m) <= tolerance]
    if left_match:
        left = left_match[-1]
    if right_match:
        right = right_match[0]

    is_physical_joint = construction_method == CONSTRUCTION_PRECAST_SEGMENTAL
    boundary_type = "Physical segment joint" if is_physical_joint else "Section / analysis zone boundary"
    left_context = {
        **left,
        "Station face": FACE_LEFT,
        "Boundary type": boundary_type,
        "Physical segment joint": is_physical_joint,
    }
    right_context = {
        **right,
        "Station face": FACE_RIGHT,
        "Boundary type": boundary_type,
        "Physical segment joint": is_physical_joint,
    }
    hint = _side_hint(check_point)
    if hint == "LEFT":
        return [left_context], warnings
    if hint == "RIGHT":
        return [right_context], warnings

    # If both sides are materially identical, one interior context is sufficient
    # for a CIP zone boundary.  Physical segment joints stay explicitly two-sided
    # even when the Section ID happens to be the same.
    if (
        not is_physical_joint
        and left_context["Section ID"] == right_context["Section ID"]
        and left_context["Segment"] == right_context["Segment"]
    ):
        left_context["Station face"] = FACE_INTERIOR
        return [left_context], warnings

    warnings.append(
        f"Station s = {station_m:.6f} m is an internal {boundary_type.lower()} without a Left/Right Check Point; "
        "the source row is mapped to both s- and s+ faces without changing its row-coupled forces."
    )
    return [left_context, right_context], warnings


def _zone_for_context(
    zones: Sequence[Mapping[str, Any]],
    *,
    segment_id: str,
    station_m: float,
    face: str,
    member_length_m: float,
) -> dict[str, Any] | None:
    tolerance = max(1.0e-7, abs(float(member_length_m)) * 1.0e-8)
    candidates = [
        dict(zone)
        for zone in zones
        if _text(zone.get("Segment")) == segment_id
        and float(zone.get("s_start_m", 0.0)) - tolerance <= station_m <= float(zone.get("s_end_m", 0.0)) + tolerance
    ]
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda row: (float(row["s_start_m"]), float(row["s_end_m"])))
    if face == FACE_LEFT:
        exact = [row for row in ordered if abs(float(row["s_end_m"]) - station_m) <= tolerance]
        return exact[-1] if exact else ordered[-1]
    if face == FACE_RIGHT:
        exact = [row for row in ordered if abs(float(row["s_start_m"]) - station_m) <= tolerance]
        return exact[0] if exact else ordered[0]
    interior = [
        row
        for row in ordered
        if float(row["s_start_m"]) - tolerance <= station_m <= float(row["s_end_m"]) + tolerance
    ]
    return interior[0] if interior else ordered[0]


def _dataset_specs(handoff: Mapping[str, Any]) -> list[tuple[str, str, list[dict[str, Any]], dict[str, Any]]]:
    return [
        (
            DATASET_ULS_FINAL,
            "Final stage",
            _records(handoff.get("uls_rows")),
            dict(handoff.get("uls_validation") or {}),
        ),
        (
            DATASET_SLS_TRANSFER,
            "Transfer stage",
            _records(handoff.get("sls_transfer_rows")),
            dict(handoff.get("sls_transfer_validation") or {}),
        ),
        (
            DATASET_SLS_SERVICE,
            "Final service stage",
            _records(handoff.get("sls_service_rows")),
            dict(handoff.get("sls_service_validation") or {}),
        ),
    ]


def _active_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if _bool(row.get("Active"), True)]


def _foundation_fingerprint(payload: Mapping[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_crossbeam_analysis_foundation(
    *,
    handoff: Mapping[str, Any] | None,
    member_length_m: float,
    construction_method: str,
    segment_rows: Any,
    section_definitions: Any,
    rebar_zone_rows: Any,
    rebar_template_rows: Any,
    transverse_template_rows: Any,
) -> dict[str, Any]:
    """Assemble source-traceable station contexts without running a solver."""

    method = canonical_construction_method(construction_method)
    source_handoff = dict(handoff or {})
    errors: list[str] = []
    warnings: list[str] = []

    if source_handoff.get("schema") != CROSSBEAM_STATION_FORCE_HANDOFF_SCHEMA:
        errors.append("Validated Crossbeam Loads handoff is missing or has an unsupported schema.")
    if not _bool(source_handoff.get("ready_for_analysis"), False):
        errors.append("Crossbeam Loads handoff is not READY for all three required datasets.")

    segments, segment_errors, segment_warnings = validate_segment_rows(
        segment_rows,
        member_length_m=member_length_m,
        construction_method=method,
    )
    errors.extend(segment_errors)
    warnings.extend(segment_warnings)

    definitions, definition_errors, definition_warnings = validate_section_definitions(
        _records(section_definitions)
    )
    errors.extend(definition_errors)
    warnings.extend(definition_warnings)
    definition_by_id = {row["Section ID"]: row for row in definitions}
    properties_by_id = {row["Section ID"]: row for row in section_property_records(definitions)}

    longitudinal_templates = canonical_rebar_templates(_records(rebar_template_rows))
    transverse_templates = canonical_transverse_templates(_records(transverse_template_rows))
    zones, zone_errors, zone_warnings = validate_rebar_zones(
        _records(rebar_zone_rows),
        segments,
        longitudinal_templates,
        transverse_templates,
    )
    errors.extend(zone_errors)
    warnings.extend(zone_warnings)
    longitudinal_by_id = template_map(longitudinal_templates)
    transverse_by_id = transverse_template_map(transverse_templates)

    mapped_rows: list[dict[str, Any]] = []
    dataset_summaries: list[dict[str, Any]] = []
    mapping_warnings: list[str] = []
    mapping_errors: list[str] = []

    for dataset, stage, dataset_rows, validation in _dataset_specs(source_handoff):
        active = _active_rows(dataset_rows)
        dataset_contexts = 0
        dataset_errors_before = len(mapping_errors)
        dataset_warnings_before = len(mapping_warnings)
        source_fingerprint = _text(validation.get("fingerprint"))
        for source_index, row in enumerate(active, start=1):
            station = _float(row.get("Station s (m)"), float("nan"))
            case_name = _text(row.get("Case Name"))
            check_point = _text(row.get("Check Point"))
            source_row_id = f"{dataset}:{source_index}"
            if not math.isfinite(station):
                mapping_errors.append(f"{source_row_id}: station is not finite.")
                continue
            candidates = _segment_candidates(segments, station, member_length_m=member_length_m)
            contexts, row_warnings = _boundary_contexts(
                candidates,
                station_m=station,
                member_length_m=member_length_m,
                check_point=check_point,
                construction_method=method,
            )
            mapping_warnings.extend(f"{source_row_id}: {message}" for message in row_warnings)
            if not contexts:
                mapping_errors.append(
                    f"{source_row_id}: no Segment / Zone and Section ID resolve at s = {station:.6f} m."
                )
                continue
            for context_index, context in enumerate(contexts, start=1):
                section_id = _text(context.get("Section ID"))
                section_definition = definition_by_id.get(section_id)
                section_property = properties_by_id.get(section_id)
                context_errors: list[str] = []
                context_warnings: list[str] = []
                if section_definition is None:
                    context_errors.append(f"Section ID {section_id or '(blank)'} is not defined.")
                if section_property is None or section_property.get("Status") == "NOT READY":
                    context_errors.append(f"Section ID {section_id or '(blank)'} has no analysis-ready gross properties.")
                elif section_property.get("Status") == "REVIEW":
                    context_warnings.append(f"Section ID {section_id} has geometry/property warnings requiring review.")

                zone = _zone_for_context(
                    zones,
                    segment_id=_text(context.get("Segment")),
                    station_m=station,
                    face=_text(context.get("Station face")),
                    member_length_m=member_length_m,
                )
                longitudinal_id = _text((zone or {}).get("Longitudinal template") or (zone or {}).get("Rebar template"))
                transverse_id = _text((zone or {}).get("Transverse template"))
                longitudinal = longitudinal_by_id.get(longitudinal_id)
                transverse = transverse_by_id.get(transverse_id)
                if zone is None:
                    context_errors.append("No Rebar Zone resolves for this station face.")
                if not longitudinal_id or longitudinal is None:
                    context_errors.append("Longitudinal Rebar Template source is missing.")
                if not transverse_id or transverse is None:
                    context_errors.append("Transverse / Shear Template source is missing.")

                physical_joint = bool(context.get("Physical segment joint"))
                context_status = "READY" if not context_errors else "BLOCKED"
                mapped = {
                    "Dataset": dataset,
                    "Stage": stage if dataset == DATASET_ULS_FINAL else canonical_sls_stage(row.get("Stage") or stage),
                    "Source row": source_row_id,
                    "Source dataset fingerprint": source_fingerprint,
                    "Case / Combination": case_name,
                    "Station s (m)": station,
                    "Check Point": check_point,
                    "Station face": _text(context.get("Station face")),
                    "Boundary type": _text(context.get("Boundary type")),
                    "Physical segment joint": physical_joint,
                    "Segment / Zone": _text(context.get("Segment")),
                    "Section ID": section_id,
                    "Section role": _text(context.get("Section role")),
                    "Section property status": _text((section_property or {}).get("Status")),
                    "Area mm2": (section_property or {}).get("Area mm²"),
                    "Z top mm3": (section_property or {}).get("Z top mm3"),
                    "Z bottom mm3": (section_property or {}).get("Z bottom mm3"),
                    "Rebar Zone": _text((zone or {}).get("Zone ID")),
                    "Longitudinal template": longitudinal_id,
                    "Transverse template": transverse_id,
                    "Ordinary rebar across physical joint": "0 mm2 (LOCKED)" if physical_joint else "Not a physical joint",
                    "Joint compression gate": "REQUIRED >= 0.70 MPa" if physical_joint and dataset != DATASET_ULS_FINAL else "N/A",
                    "P (kN; compression +)": _float(row.get("P"), 0.0),
                    "V2 (kN; upward +)": _float(row.get("V2"), 0.0),
                    "T (kN-m; RH +s)": _float(row.get("T"), 0.0),
                    "M3 (kN-m; sagging +)": _float(row.get("M3"), 0.0),
                    "Source Note": _text(row.get("Note")),
                    "Context status": context_status,
                    "Context issues": context_errors,
                    "Context warnings": context_warnings,
                    "Context ID": f"{source_row_id}:{context_index}:{_text(context.get('Station face'))}",
                }
                mapped_rows.append(mapped)
                dataset_contexts += 1
                mapping_errors.extend(f"{mapped['Context ID']}: {message}" for message in context_errors)
                mapping_warnings.extend(f"{mapped['Context ID']}: {message}" for message in context_warnings)

        dataset_summaries.append(
            {
                "Dataset": dataset,
                "Stage": stage,
                "Source ready": _bool(validation.get("ready"), False),
                "Active source rows": len(active),
                "Mapped check contexts": dataset_contexts,
                "Cases": int(validation.get("cases") or 0),
                "Stations": int(validation.get("stations") or 0),
                "Source fingerprint": source_fingerprint,
                "Mapping errors": len(mapping_errors) - dataset_errors_before,
                "Mapping warnings": len(mapping_warnings) - dataset_warnings_before,
            }
        )

    errors.extend(mapping_errors)
    warnings.extend(mapping_warnings)
    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))

    payload_for_fingerprint = {
        "schema": CROSSBEAM_ANALYSIS_FOUNDATION_SCHEMA,
        "loads_handoff_fingerprint": _text(source_handoff.get("fingerprint")),
        "construction_method": method,
        "member_length_m": float(member_length_m),
        "segments": segments,
        "definitions": definitions,
        "zones": zones,
        "longitudinal_templates": longitudinal_templates,
        "transverse_templates": transverse_templates,
        "mapped_rows": mapped_rows,
    }
    fingerprint = _foundation_fingerprint(payload_for_fingerprint)
    ready = bool(
        _bool(source_handoff.get("ready_for_analysis"), False)
        and not errors
        and all(summary["Source ready"] for summary in dataset_summaries)
        and all(summary["Mapped check contexts"] > 0 for summary in dataset_summaries)
    )
    return {
        "schema": CROSSBEAM_ANALYSIS_FOUNDATION_SCHEMA,
        "ready": ready,
        "status": "READY" if ready else "SOURCE BLOCKED",
        "solver_run": False,
        "member_design_code": "ACI 318-19",
        "prestress_loss_basis": "AASHTO LRFD 2020 Section 5.9.3",
        "construction_method": method,
        "member_length_m": float(member_length_m),
        "loads_handoff_fingerprint": _text(source_handoff.get("fingerprint")),
        "fingerprint": fingerprint,
        "dataset_summaries": dataset_summaries,
        "mapped_rows": mapped_rows,
        "errors": errors,
        "warnings": warnings,
        "limitations": [
            "Input assembly only; no ACI 318 strength or service-stress equation is evaluated.",
            "P, V2, T, and M3 remain row-coupled to one imported FEA output state.",
            "Precast physical-joint SLS compression >= 0.70 MPa is identified but not calculated in ANALYSIS1.",
            "D-regions, anchorage zones, beam-column joints, and seismic detailing remain separate guarded scopes.",
        ],
    }

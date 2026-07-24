"""Cast-in-Place Crossbeam continuous longitudinal rebar topology foundation.

``CROSSBEAM.RB-CIP1`` introduces a solver-neutral, station-based longitudinal
bar-run model for monolithic Cast-in-Place Portal Frame Crossbeams.  The model
is intentionally separate from the accepted Precast Segmental template/zone
model: CIP Section/Zone boundaries are geometry/property boundaries and do not
terminate ordinary longitudinal reinforcement.

This module owns only canonical input data and validation.  It does not create
reinforcement, perform development/splice checks, or hand any bar run to ULS,
SLS, PMM, shear, torsion, prestress-loss, or report solvers.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any


CIP_REBAR_TOPOLOGY_SCHEMA_VERSION = 1

CIP_RUN_LAYER_OPTIONS = (
    "Top",
    "Bottom",
    "Side / Web",
    "Perimeter / Other",
)
CIP_RUN_DEFINITION_BASIS_OPTIONS = (
    "By exact bar count",
    "By target spacing",
)
CIP_RUN_BAR_SIZE_OPTIONS = (
    "DB10",
    "DB12",
    "DB16",
    "DB20",
    "DB25",
    "DB28",
    "DB32",
)
CIP_RUN_MATERIAL_OPTIONS = ("SD40", "SD50")
CIP_RUN_FY_BY_MATERIAL = {"SD40": 390.0, "SD50": 490.0}
CIP_RUN_STANDARD_MATERIAL_BY_SIZE = {
    "DB10": "SD40",
    "DB12": "SD40",
    "DB16": "SD40",
    "DB20": "SD40",
    "DB25": "SD40",
    "DB28": "SD40",
    "DB32": "SD50",
}
CIP_RUN_DIAMETER_BY_SIZE = {
    "DB10": 10.0,
    "DB12": 12.0,
    "DB16": 16.0,
    "DB20": 20.0,
    "DB25": 25.0,
    "DB28": 28.0,
    "DB32": 32.0,
}

# These fields record engineering intent only.  RB-CIP3 will perform the future
# development/splice/termination compliance checks; RB-CIP1 must not certify it.
CIP_RUN_TERMINATION_INTENT_OPTIONS = (
    "Member end / anchorage region",
    "Continue beyond modeled run",
    "Intentional developed termination",
    "Lap / mechanical splice",
    "Not yet defined",
)


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _positive_int(value: Any, default: int = 0) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)
    return number


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(value)


def default_cip_longitudinal_bar_runs() -> list[dict[str, Any]]:
    """Return the safe default: no invented Cast-in-Place reinforcement.

    RB-CIP1 establishes data ownership only.  A new project therefore starts
    with an empty topology rather than silently assuming full-length bars or
    reinforcement quantities that the engineer has not specified.
    """

    return []


def canonical_cip_longitudinal_bar_runs(values: Any) -> list[dict[str, Any]]:
    """Return canonical station-based bar runs without clamping engineering data.

    Unknown/unsupported labels are preserved verbatim so validation can report
    them as ``REVIEW REQUIRED`` rather than silently substituting a supported
    bar, material, layer, or termination intent.
    """

    if hasattr(values, "to_dict"):
        try:
            source_rows = values.to_dict(orient="records")
        except (TypeError, ValueError):
            source_rows = []
    elif isinstance(values, (list, tuple)):
        source_rows = list(values)
    else:
        source_rows = []

    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(source_rows, start=1):
        if not isinstance(source, Mapping):
            continue
        row = dict(source)
        bar_size = str(row.get("Bar size") or "").strip().upper()
        material = str(row.get("Material") or row.get("Rebar material") or "").strip().upper()
        diameter_default = CIP_RUN_DIAMETER_BY_SIZE.get(bar_size, 0.0)
        fy_default = CIP_RUN_FY_BY_MATERIAL.get(material, 0.0)
        canonical.append(
            {
                "Active": _bool(row.get("Active"), True),
                "Run ID": str(row.get("Run ID") or "").strip(),
                "s_start_m": _finite_float(row.get("s_start_m", row.get("s_start (m)")), 0.0),
                "s_end_m": _finite_float(row.get("s_end_m", row.get("s_end (m)")), 0.0),
                "Bar group": str(row.get("Bar group") or "").strip(),
                "Layer / face": str(row.get("Layer / face") or row.get("Layer") or "").strip(),
                "Bar size": bar_size,
                "Bar diameter mm": _finite_float(row.get("Bar diameter mm"), diameter_default),
                "Material": material,
                "fy MPa": _finite_float(row.get("fy MPa"), fy_default),
                "Definition basis": str(row.get("Definition basis") or "").strip(),
                "Bar count": _positive_int(row.get("Bar count"), 0),
                "Target spacing mm": _finite_float(row.get("Target spacing mm", row.get("Spacing mm")), 0.0),
                "Start intent": str(row.get("Start intent") or "Not yet defined").strip(),
                "End intent": str(row.get("End intent") or "Not yet defined").strip(),
                "Notes": str(row.get("Notes") or "").strip(),
            }
        )
    return canonical


def validate_cip_longitudinal_bar_runs(
    values: Any,
    *,
    length_m: float,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate CIP station-based longitudinal topology without solver credit.

    The validation deliberately does *not* require run boundaries to coincide
    with Section/Zone boundaries.  A valid bar run may cross any number of CIP
    zones because the Crossbeam is monolithic.  Development, splice, curtailment,
    anchorage, congestion, and code-minimum checks remain future RB-CIP milestones.
    """

    rows = canonical_cip_longitudinal_bar_runs(values)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        member_length = float(length_m)
    except (TypeError, ValueError):
        member_length = 0.0
    if not isfinite(member_length) or member_length <= 0.0:
        errors.append("Crossbeam physical length L must be positive before CIP bar-run topology can be accepted.")
        member_length = 0.0

    active_ids: list[str] = []
    for row in rows:
        run_id = str(row.get("Run ID") or "").strip()
        if bool(row.get("Active")):
            active_ids.append(run_id)
        label = run_id or "(unnamed run)"

        if not bool(row.get("Active")):
            continue
        if not run_id:
            errors.append("Every active CIP longitudinal bar run requires a Run ID.")

        start = _finite_float(row.get("s_start_m"), 0.0)
        end = _finite_float(row.get("s_end_m"), 0.0)
        if end <= start:
            errors.append(f"{label}: s_end must be greater than s_start.")
        if start < 0.0 or (member_length > 0.0 and end > member_length):
            errors.append(
                f"{label}: station range {start:.3f}–{end:.3f} m must remain within physical Crossbeam extent 0–{member_length:.3f} m."
            )

        if not str(row.get("Bar group") or "").strip():
            errors.append(f"{label}: Bar group is required.")
        layer = str(row.get("Layer / face") or "").strip()
        if layer not in CIP_RUN_LAYER_OPTIONS:
            errors.append(f"{label}: Layer / face '{layer or '(blank)'}' is not supported by the CIP topology contract.")

        bar_size = str(row.get("Bar size") or "").strip().upper()
        if bar_size not in CIP_RUN_BAR_SIZE_OPTIONS:
            errors.append(f"{label}: Bar size '{bar_size or '(blank)'}' is not supported.")
        expected_diameter = CIP_RUN_DIAMETER_BY_SIZE.get(bar_size)
        diameter = _finite_float(row.get("Bar diameter mm"), 0.0)
        if diameter <= 0.0:
            errors.append(f"{label}: Bar diameter must be positive.")
        elif expected_diameter is not None and abs(diameter - expected_diameter) > 1e-9:
            errors.append(
                f"{label}: Bar diameter {diameter:g} mm does not match {bar_size} ({expected_diameter:g} mm)."
            )

        material = str(row.get("Material") or "").strip().upper()
        if material not in CIP_RUN_MATERIAL_OPTIONS:
            errors.append(f"{label}: Material '{material or '(blank)'}' is not supported.")
        expected_material = CIP_RUN_STANDARD_MATERIAL_BY_SIZE.get(bar_size)
        if expected_material is not None and material in CIP_RUN_MATERIAL_OPTIONS and material != expected_material:
            errors.append(
                f"{label}: {bar_size} must use {expected_material} under the app standard bar-grade rule; current Material is {material}."
            )
        expected_fy = CIP_RUN_FY_BY_MATERIAL.get(material)
        fy = _finite_float(row.get("fy MPa"), 0.0)
        if fy <= 0.0:
            errors.append(f"{label}: fy must be positive.")
        elif expected_fy is not None and abs(fy - expected_fy) > 1e-9:
            errors.append(f"{label}: fy {fy:g} MPa does not match {material} ({expected_fy:g} MPa).")

        basis = str(row.get("Definition basis") or "").strip()
        if basis not in CIP_RUN_DEFINITION_BASIS_OPTIONS:
            errors.append(f"{label}: Definition basis '{basis or '(blank)'}' is not supported.")
        elif basis == "By exact bar count" and _positive_int(row.get("Bar count"), 0) <= 0:
            errors.append(f"{label}: Bar count must be positive for 'By exact bar count'.")
        elif basis == "By target spacing" and _finite_float(row.get("Target spacing mm"), 0.0) <= 0.0:
            errors.append(f"{label}: Target spacing must be positive for 'By target spacing'.")

        start_intent = str(row.get("Start intent") or "").strip()
        end_intent = str(row.get("End intent") or "").strip()
        if start_intent not in CIP_RUN_TERMINATION_INTENT_OPTIONS:
            errors.append(f"{label}: Start intent '{start_intent or '(blank)'}' is not supported.")
        if end_intent not in CIP_RUN_TERMINATION_INTENT_OPTIONS:
            errors.append(f"{label}: End intent '{end_intent or '(blank)'}' is not supported.")
        if start_intent == "Not yet defined" or end_intent == "Not yet defined":
            warnings.append(
                f"{label}: start/end termination intent is not fully defined; RB-CIP3 development/splice/termination QA remains pending."
            )

    duplicates = sorted({item for item in active_ids if item and active_ids.count(item) > 1})
    for run_id in duplicates:
        errors.append(f"Duplicate active CIP longitudinal Run ID: {run_id}.")

    if not rows:
        warnings.append(
            "No Cast-in-Place longitudinal bar runs are defined. The workflow does not invent reinforcement; define runs explicitly in the continuous bar-run editor."
        )

    return rows, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def cip_rebar_topology_status(values: Any, *, length_m: float) -> dict[str, Any]:
    """Return a decision-first, solver-neutral topology status summary."""

    rows, errors, warnings = validate_cip_longitudinal_bar_runs(values, length_m=length_m)
    active_count = sum(bool(row.get("Active")) for row in rows)
    if errors:
        status = "REVIEW REQUIRED"
    elif active_count == 0:
        status = "LAYOUT REQUIRED"
    else:
        status = "FOUNDATION READY"
    return {
        "schema_version": CIP_REBAR_TOPOLOGY_SCHEMA_VERSION,
        "status": status,
        "run_count": len(rows),
        "active_run_count": active_count,
        "errors": errors,
        "warnings": warnings,
        "solver_handoff": "LOCKED",
        "development_splice_qa": "NOT RELEASED",
    }

def new_cip_longitudinal_bar_run(values: Any, *, length_m: float) -> dict[str, Any]:
    """Return one explicit draft row after the user asks to add a bar run.

    The draft intentionally carries no bar size, material, layer, quantity, or
    termination certification.  Its station seed spans the physical member only
    as an editing convenience and remains ``REVIEW REQUIRED`` until the engineer
    supplies the required reinforcement definition.  No solver consumes the row.
    """

    existing = canonical_cip_longitudinal_bar_runs(values)
    used = {str(row.get("Run ID") or "").strip() for row in existing}
    index = 1
    while f"CIP-R{index}" in used:
        index += 1
    length = max(_finite_float(length_m, 0.0), 0.0)
    return canonical_cip_longitudinal_bar_runs(
        [
            {
                "Active": True,
                "Run ID": f"CIP-R{index}",
                "s_start_m": 0.0,
                "s_end_m": length,
                "Bar group": "",
                "Layer / face": "",
                "Bar size": "",
                "Material": "",
                "Definition basis": "",
                "Bar count": 0,
                "Target spacing mm": 0.0,
                "Start intent": "Not yet defined",
                "End intent": "Not yet defined",
                "Notes": "",
            }
        ]
    )[0]


def cip_bar_run_zone_intersections(
    run: Mapping[str, Any],
    zone_rows: Any,
    *,
    tolerance: float = 1.0e-9,
) -> list[str]:
    """Return Section/Zone IDs with positive-length overlap with one CIP run.

    Merely touching a zone boundary does not count as occupying the adjacent zone.
    This makes the audit explicit that a continuous bar may cross one or many zone
    boundaries without those boundaries becoming reinforcement terminations.
    """

    start = _finite_float(run.get("s_start_m", run.get("s_start (m)")), 0.0)
    end = _finite_float(run.get("s_end_m", run.get("s_end (m)")), 0.0)
    output: list[str] = []
    if end <= start:
        return output
    if hasattr(zone_rows, "to_dict"):
        try:
            zones = zone_rows.to_dict(orient="records")
        except (TypeError, ValueError):
            zones = []
    elif isinstance(zone_rows, (list, tuple)):
        zones = list(zone_rows)
    else:
        zones = []
    for index, source in enumerate(zones, start=1):
        if not isinstance(source, Mapping):
            continue
        zone_start = _finite_float(source.get("x_start_m", source.get("s_start_m")), 0.0)
        zone_end = _finite_float(source.get("x_end_m", source.get("s_end_m")), 0.0)
        overlap = min(end, zone_end) - max(start, zone_start)
        if overlap > abs(float(tolerance)):
            zone_id = str(source.get("Segment") or source.get("Zone") or f"Z{index}").strip()
            output.append(zone_id or f"Z{index}")
    return output


def cip_longitudinal_runs_at_station(
    values: Any,
    *,
    station_m: float,
    tolerance: float = 1.0e-9,
) -> list[dict[str, Any]]:
    """Return active CIP longitudinal runs present at a review station."""

    station = _finite_float(station_m, 0.0)
    tol = abs(float(tolerance))
    return [
        row
        for row in canonical_cip_longitudinal_bar_runs(values)
        if bool(row.get("Active"))
        and _finite_float(row.get("s_start_m"), 0.0) - tol <= station
        <= _finite_float(row.get("s_end_m"), 0.0) + tol
    ]


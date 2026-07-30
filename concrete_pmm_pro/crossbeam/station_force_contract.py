"""Compact station-force import contract for Portal Frame Crossbeam Loads.

CROSSBEAM.LOADS1B preserves the established member-workflow pattern: the
engineer selects row-coupled design forces at each design station in the
external FEA program, then imports those selected ULS/SLS resultants.  This
module intentionally does not model raw frame-element I/J-end output.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


CROSSBEAM_STATION_FORCE_CONTRACT_SCHEMA = "crossbeam-station-force-import-contract-v2"
CROSSBEAM_STATION_FORCE_HANDOFF_SCHEMA = "crossbeam-station-force-analysis-handoff-v2"

CB_STATION_FORCE_CONTRACT_KEY = "crossbeam_loads_station_force_contract"
CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY = "crossbeam_loads_effective_prestress_link"
CB_STATION_FORCE_VALIDATION_KEY = "crossbeam_loads_station_force_validation"

PRESTRESS_BASIS_UNIFORM_AVERAGE_LOSS = "UNIFORM_SYSTEM_AVERAGE_LOSS"
CANONICAL_FORCE_UNIT = "kN"
CANONICAL_MOMENT_UNIT = "kN-m"
FORCE_UNITS = ("kN", "N", "tonf")
MOMENT_UNITS = ("kN-m", "N-mm", "tonf-m")
P_SIGNS = ("COMPRESSION_POSITIVE", "TENSION_POSITIVE")
V2_SIGNS = ("UPWARD_POSITIVE", "DOWNWARD_POSITIVE")
T_SIGNS = ("RIGHT_HAND_ABOUT_INCREASING_S", "OPPOSITE_RIGHT_HAND_ABOUT_INCREASING_S")
M3_SIGNS = ("SAGGING_POSITIVE", "HOGGING_POSITIVE")

CROSSBEAM_ULS_STATION_FORCE_COLUMNS = [
    "Active",
    "Station s (m)",
    "Check Point",
    "Case Name",
    "P",
    "V2",
    "T",
    "M3",
    "Note",
]
CROSSBEAM_SLS_STATION_FORCE_COLUMNS = [
    "Active",
    "Station s (m)",
    "Check Point",
    "Case Name",
    "Stage",
    "P",
    "V2",
    "T",
    "M3",
    "Note",
]
CROSSBEAM_SLS_STAGE_OPTIONS = (
    "Transfer stage",
    "Final service stage",
)


@dataclass(frozen=True)
class StationForceValidation:
    ready: bool
    active_rows: int
    total_rows: int
    cases: int
    stations: int
    check_points: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "active_rows": self.active_rows,
            "total_rows": self.total_rows,
            "cases": self.cases,
            "stations": self.stations,
            "check_points": self.check_points,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "fingerprint": self.fingerprint,
        }


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
    if value is None or _text(value) == "":
        return float(default)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return float(default)


def _numeric_value(value: Any, blank_default: float = 0.0) -> float:
    try:
        if isinstance(value, float) and math.isnan(value):
            return float("nan")
    except Exception:
        pass
    if value is None or _text(value) == "":
        return float(blank_default)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return float("nan")


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).casefold()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on", "active", "use", "ใช้", "ใช่"}:
        return True
    if text in {"0", "false", "no", "n", "off", "inactive", "ไม่ใช้", "ไม่"}:
        return False
    return default


def _choice(value: Any, options: Sequence[str], default: str) -> str:
    text = _text(value).upper().replace(" ", "_")
    lookup = {option.upper(): option for option in options}
    return lookup.get(text, default)


def canonical_effective_prestress_link(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    loss = max(0.0, min(_float(source.get("average_total_loss_percent"), 0.0), 100.0))
    ratio = max(
        0.0,
        min(_float(source.get("effective_prestress_ratio_percent"), 100.0 - loss), 100.0),
    )
    return {
        "schema": "crossbeam-effective-prestress-loads-link-v1",
        "ready": _bool(source.get("ready"), False),
        "source_id": _text(source.get("source_id")),
        "contract_id": _text(source.get("contract_id")),
        "source_fingerprint": _text(source.get("source_fingerprint")),
        "application_route": _text(source.get("application_route")),
        "engineer_adopted_td": _bool(source.get("engineer_adopted_td"), False),
        "average_total_loss_percent": loss,
        "effective_prestress_ratio_percent": ratio,
        "average_effective_stress_mpa": _float(source.get("average_effective_stress_mpa"), 0.0),
        "average_effective_force_kn": _float(source.get("average_effective_force_kn"), 0.0),
    }


def default_station_force_contract(
    *, effective_prestress_link: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    link = canonical_effective_prestress_link(effective_prestress_link)
    loss = float(link.get("average_total_loss_percent") or 0.0)
    return {
        "schema": CROSSBEAM_STATION_FORCE_CONTRACT_SCHEMA,
        "fea_program": "CSiBridge",
        "model_revision": "",
        "source_force_unit": CANONICAL_FORCE_UNIT,
        "source_moment_unit": CANONICAL_MOMENT_UNIT,
        "p_sign": "COMPRESSION_POSITIVE",
        "v2_sign": "UPWARD_POSITIVE",
        "t_sign": "RIGHT_HAND_ABOUT_INCREASING_S",
        "m3_sign": "SAGGING_POSITIVE",
        "prestress_application_basis": PRESTRESS_BASIS_UNIFORM_AVERAGE_LOSS,
        "adopted_total_loss_percent": loss,
        "effective_prestress_ratio_percent": 100.0 - loss,
        "prestress_source_id": _text(link.get("source_id")),
        "prestress_contract_id": _text(link.get("contract_id")),
        # Final-stage basis used by ULS and SLS At Service.
        "confirmed_final_prestress_applied_once": False,
        "confirmed_external_fea_secondary": False,
        "confirmed_uls_final_stage_response_basis": False,
        "confirmed_sls_service_response_basis": False,
        # Transfer-stage basis intentionally excludes long-term TD loss.
        "confirmed_transfer_immediate_loss_basis": False,
        "confirmed_transfer_stage_response_basis": False,
        # Common row-coupling declaration.
        "confirmed_row_coupled_forces": False,
    }


def canonical_station_force_contract(
    value: Mapping[str, Any] | None,
    *,
    effective_prestress_link: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = default_station_force_contract(effective_prestress_link=effective_prestress_link)
    source = dict(value or {})
    result = dict(defaults)
    result.update({key: source.get(key, default) for key, default in defaults.items()})
    result["schema"] = CROSSBEAM_STATION_FORCE_CONTRACT_SCHEMA
    result["fea_program"] = _text(result.get("fea_program"))
    result["model_revision"] = _text(result.get("model_revision"))
    result["source_force_unit"] = _choice(
        result.get("source_force_unit"), FORCE_UNITS, CANONICAL_FORCE_UNIT
    )
    result["source_moment_unit"] = _choice(
        result.get("source_moment_unit"), MOMENT_UNITS, CANONICAL_MOMENT_UNIT
    )
    result["p_sign"] = _choice(result.get("p_sign"), P_SIGNS, "COMPRESSION_POSITIVE")
    result["v2_sign"] = _choice(result.get("v2_sign"), V2_SIGNS, "UPWARD_POSITIVE")
    result["t_sign"] = _choice(
        result.get("t_sign"), T_SIGNS, "RIGHT_HAND_ABOUT_INCREASING_S"
    )
    result["m3_sign"] = _choice(result.get("m3_sign"), M3_SIGNS, "SAGGING_POSITIVE")
    result["prestress_application_basis"] = PRESTRESS_BASIS_UNIFORM_AVERAGE_LOSS
    loss = max(0.0, min(_float(result.get("adopted_total_loss_percent"), 0.0), 100.0))
    result["adopted_total_loss_percent"] = loss
    result["effective_prestress_ratio_percent"] = 100.0 - loss
    result["prestress_source_id"] = _text(result.get("prestress_source_id"))
    result["prestress_contract_id"] = _text(result.get("prestress_contract_id"))

    # Backward-compatible migration from LOADS1A project metadata.  Final-stage
    # declarations can be inherited; the two new Transfer confirmations remain
    # explicit because old projects never declared that stage separately.
    old_once = _bool(source.get("confirmed_prestress_applied_once"), False)
    old_final = _bool(source.get("confirmed_final_stage_response_basis"), False)
    result["confirmed_final_prestress_applied_once"] = _bool(
        source.get("confirmed_final_prestress_applied_once"), old_once
    )
    result["confirmed_external_fea_secondary"] = _bool(
        source.get("confirmed_external_fea_secondary"), False
    )
    result["confirmed_uls_final_stage_response_basis"] = _bool(
        source.get("confirmed_uls_final_stage_response_basis"), old_final
    )
    result["confirmed_sls_service_response_basis"] = _bool(
        source.get("confirmed_sls_service_response_basis"), old_final
    )
    result["confirmed_transfer_immediate_loss_basis"] = _bool(
        source.get("confirmed_transfer_immediate_loss_basis"), False
    )
    result["confirmed_transfer_stage_response_basis"] = _bool(
        source.get("confirmed_transfer_stage_response_basis"), False
    )
    result["confirmed_row_coupled_forces"] = _bool(
        source.get("confirmed_row_coupled_forces"), False
    )
    return result


def canonical_storage_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    item = canonical_station_force_contract(contract)
    item["source_force_unit"] = CANONICAL_FORCE_UNIT
    item["source_moment_unit"] = CANONICAL_MOMENT_UNIT
    item["p_sign"] = "COMPRESSION_POSITIVE"
    item["v2_sign"] = "UPWARD_POSITIVE"
    item["t_sign"] = "RIGHT_HAND_ABOUT_INCREASING_S"
    item["m3_sign"] = "SAGGING_POSITIVE"
    return item


def validate_station_force_contract(
    contract: Mapping[str, Any],
    *,
    response_type: str | None = None,
    sls_stage: str | None = None,
) -> tuple[list[str], list[str]]:
    """Validate common and stage-specific FEA source declarations.

    ``response_type=None`` checks the complete ULS + Transfer + Service contract.
    Import previews pass a response/stage context so one stage can be reviewed
    without requiring unrelated stage confirmations first.
    """

    item = canonical_station_force_contract(contract)
    errors: list[str] = []
    warnings: list[str] = []
    if not item["fea_program"]:
        errors.append("FEA Program is required.")
    if not item["model_revision"]:
        errors.append("FEA model / revision is required.")
    loss = float(item["adopted_total_loss_percent"])
    if not (0.0 < loss < 60.0):
        errors.append(
            "Adopted uniform system-average final prestress loss must be greater than 0% and less than 60%."
        )
    if not item["prestress_source_id"]:
        warnings.append("Prestress Source ID is blank; traceability to Prestress Loss is incomplete.")
    if not item["prestress_contract_id"]:
        warnings.append("Prestress Contract ID is blank; record the FEA handoff contract used by the model.")
    if not item["confirmed_row_coupled_forces"]:
        errors.append("Confirm that P, V2, T, and M3 in each row come from the same FEA output state.")

    response = _text(response_type).upper()
    stage = canonical_sls_stage(sls_stage) if sls_stage else ""
    check_all = not response
    check_final = check_all or response == "ULS" or (response == "SLS" and stage == "Final service stage")
    check_transfer = check_all or (response == "SLS" and stage == "Transfer stage")

    if check_final:
        if not item["confirmed_final_prestress_applied_once"]:
            errors.append("Confirm that final effective prestress / total loss was applied exactly once in FEA.")
        if not item["confirmed_external_fea_secondary"]:
            errors.append("Confirm that the external portal-frame model calculated final-stage secondary prestress response.")
        if (check_all or response == "ULS") and not item["confirmed_uls_final_stage_response_basis"]:
            errors.append("Confirm that imported ULS rows are factored final-stage FEA responses.")
        if (check_all or (response == "SLS" and stage == "Final service stage")) and not item["confirmed_sls_service_response_basis"]:
            errors.append("Confirm that imported SLS At Service rows are verified final-service FEA responses.")

    if check_transfer:
        if not item["confirmed_transfer_immediate_loss_basis"]:
            errors.append(
                "Confirm that Transfer-stage prestress uses immediate losses only (Friction, Anchorage Set, and Elastic Shortening), applied once in FEA."
            )
        if not item["confirmed_transfer_stage_response_basis"]:
            errors.append(
                "Confirm that imported SLS At Transfer rows use the verified transfer-age support/contact and loading state."
            )
    return errors, warnings


def canonical_sls_stage(value: Any) -> str:
    text = _text(value).casefold()
    aliases = {
        "service": "Final service stage",
        "service stage": "Final service stage",
        "at service": "Final service stage",
        "final stage": "Final service stage",
        "final service": "Final service stage",
        "final service stage": "Final service stage",
        "transfer": "Transfer stage",
        "at transfer": "Transfer stage",
        "transfer stage": "Transfer stage",
        "construction": "Construction stage",
        "construction stage": "Construction stage",
        "user": "User-defined",
        "user defined": "User-defined",
        "user-defined": "User-defined",
    }
    return aliases.get(text, _text(value) or "Final service stage")


def _force_to_kn(value: float, unit: str) -> float:
    if unit == "kN":
        return float(value)
    if unit == "N":
        return float(value) / 1000.0
    if unit == "tonf":
        return float(value) * 9.80665
    raise ValueError(f"Unsupported source force unit: {unit}")


def _moment_to_knm(value: float, unit: str) -> float:
    if unit == "kN-m":
        return float(value)
    if unit == "N-mm":
        return float(value) / 1_000_000.0
    if unit == "tonf-m":
        return float(value) * 9.80665
    raise ValueError(f"Unsupported source moment unit: {unit}")


def _sign_multiplier(contract: Mapping[str, Any], response: str) -> float:
    item = canonical_station_force_contract(contract)
    if response == "P":
        return 1.0 if item["p_sign"] == "COMPRESSION_POSITIVE" else -1.0
    if response == "V2":
        return 1.0 if item["v2_sign"] == "UPWARD_POSITIVE" else -1.0
    if response == "T":
        return 1.0 if item["t_sign"] == "RIGHT_HAND_ABOUT_INCREASING_S" else -1.0
    if response == "M3":
        return 1.0 if item["m3_sign"] == "SAGGING_POSITIVE" else -1.0
    return 1.0


def normalize_station_force_rows(
    rows: Iterable[Mapping[str, Any]] | None,
    *,
    contract: Mapping[str, Any],
    response_type: str,
    rows_are_canonical: bool = False,
) -> list[dict[str, Any]]:
    """Return row-coupled station forces in canonical kN / kN-m signs."""

    source_contract = (
        canonical_storage_contract(contract)
        if rows_are_canonical
        else canonical_station_force_contract(contract)
    )
    is_sls = str(response_type).upper() == "SLS"
    columns = (
        CROSSBEAM_SLS_STATION_FORCE_COLUMNS
        if is_sls
        else CROSSBEAM_ULS_STATION_FORCE_COLUMNS
    )
    normalized: list[dict[str, Any]] = []
    for raw in rows or []:
        source = dict(raw)
        if not any(_text(value) for key, value in source.items() if key != "Active"):
            continue
        row: dict[str, Any] = {
            "Active": _bool(source.get("Active"), True),
            "Station s (m)": _numeric_value(source.get("Station s (m)"), float("nan")),
            "Check Point": _text(source.get("Check Point")),
            "Case Name": _text(source.get("Case Name")),
            "P": _force_to_kn(_numeric_value(source.get("P")), source_contract["source_force_unit"])
            * _sign_multiplier(source_contract, "P"),
            "V2": _force_to_kn(_numeric_value(source.get("V2")), source_contract["source_force_unit"])
            * _sign_multiplier(source_contract, "V2"),
            "T": _moment_to_knm(_numeric_value(source.get("T")), source_contract["source_moment_unit"])
            * _sign_multiplier(source_contract, "T"),
            "M3": _moment_to_knm(_numeric_value(source.get("M3")), source_contract["source_moment_unit"])
            * _sign_multiplier(source_contract, "M3"),
            "Note": _text(source.get("Note")),
        }
        if is_sls:
            row["Stage"] = canonical_sls_stage(source.get("Stage"))
        normalized.append({column: row.get(column, "") for column in columns})
    return normalized


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _row_key(row: Mapping[str, Any], response_type: str) -> tuple[str, ...]:
    values = [
        _text(row.get("Case Name")).casefold(),
        f"{_float(row.get('Station s (m)'), 0.0):.9f}",
        _text(row.get("Check Point")).casefold(),
    ]
    if str(response_type).upper() == "SLS":
        values.insert(1, canonical_sls_stage(row.get("Stage")).casefold())
    return tuple(values)


def _base_station_key(row: Mapping[str, Any], response_type: str) -> tuple[str, ...]:
    values = [
        _text(row.get("Case Name")).casefold(),
        f"{_float(row.get('Station s (m)'), 0.0):.9f}",
    ]
    if str(response_type).upper() == "SLS":
        values.insert(1, canonical_sls_stage(row.get("Stage")).casefold())
    return tuple(values)


def _fingerprint_payload(
    contract: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], response_type: str
) -> str:
    payload = {
        "schema": CROSSBEAM_STATION_FORCE_HANDOFF_SCHEMA,
        "response_type": str(response_type).upper(),
        "contract": canonical_station_force_contract(contract),
        "rows": [dict(row) for row in rows],
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_station_force_rows(
    rows: Iterable[Mapping[str, Any]] | None,
    *,
    contract: Mapping[str, Any],
    member_length_m: float,
    response_type: str,
    rows_are_canonical: bool = False,
    expected_sls_stage: str | None = None,
) -> StationForceValidation:
    canonical_rows = normalize_station_force_rows(
        rows,
        contract=contract,
        response_type=response_type,
        rows_are_canonical=rows_are_canonical,
    )
    expected_stage = canonical_sls_stage(expected_sls_stage) if expected_sls_stage else None
    errors, warnings = validate_station_force_contract(
        contract,
        response_type=response_type,
        sls_stage=expected_stage,
    )
    seen: set[tuple[str, ...]] = set()
    base_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    active_rows = 0
    cases: set[str] = set()
    stations: set[float] = set()
    check_points: set[str] = set()
    is_sls = str(response_type).upper() == "SLS"
    for index, row in enumerate(canonical_rows, start=1):
        prefix = f"{str(response_type).upper()} row {index}"
        is_active = _bool(row.get("Active"), True)
        case_name = _text(row.get("Case Name"))
        if not case_name:
            errors.append(f"{prefix}: Case Name is required.")
        elif is_active:
            cases.add(case_name)
        station = _float(row.get("Station s (m)"), float("nan"))
        if not math.isfinite(station):
            errors.append(f"{prefix}: Station s must be numeric.")
        elif station < -1.0e-9 or station > float(member_length_m) + 1.0e-9:
            errors.append(
                f"{prefix}: Station s = {station:.6f} m is outside 0 ≤ s ≤ {float(member_length_m):.6f} m."
            )
        elif is_active:
            stations.add(round(station, 9))
        point = _text(row.get("Check Point"))
        if point and is_active:
            check_points.add(point)
        for field in ("P", "V2", "T", "M3"):
            if not _finite(row.get(field)):
                errors.append(f"{prefix}: {field} must be a finite numeric value.")
        if is_sls:
            stage = canonical_sls_stage(row.get("Stage"))
            if stage not in CROSSBEAM_SLS_STAGE_OPTIONS:
                errors.append(
                    f"{prefix}: Stage must be one of {', '.join(CROSSBEAM_SLS_STAGE_OPTIONS)}."
                )
            elif expected_stage and stage != expected_stage:
                errors.append(
                    f"{prefix}: Stage must be {expected_stage} in this SLS sub-tab."
                )
        key = _row_key(row, response_type)
        if key in seen:
            errors.append(
                f"{prefix}: duplicate station-force row. Keep Case/Stage/Station/Check Point unique."
            )
        else:
            seen.add(key)
        base_groups.setdefault(_base_station_key(row, response_type), []).append(row)
        if is_active:
            active_rows += 1
    for group_rows in base_groups.values():
        if len(group_rows) > 1 and any(not _text(row.get("Check Point")) for row in group_rows):
            errors.append(
                "Multiple rows share the same Case/Stage/Station; enter Check Point labels to distinguish them."
            )
    if canonical_rows and active_rows == 0:
        warnings.append(f"{str(response_type).upper()}: no active station-force rows are selected.")
    fingerprint = _fingerprint_payload(contract, canonical_rows, response_type)
    return StationForceValidation(
        ready=not errors and active_rows > 0,
        active_rows=active_rows,
        total_rows=len(canonical_rows),
        cases=len(cases),
        stations=len(stations),
        check_points=len(check_points),
        errors=tuple(errors),
        warnings=tuple(warnings),
        fingerprint=fingerprint,
    )


def build_station_force_analysis_handoff(
    *,
    uls_rows: Iterable[Mapping[str, Any]] | None,
    contract: Mapping[str, Any],
    member_length_m: float,
    sls_transfer_rows: Iterable[Mapping[str, Any]] | None = None,
    sls_service_rows: Iterable[Mapping[str, Any]] | None = None,
    sls_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the Analysis handoff with explicit ULS, Transfer, and Service gates.

    ``sls_rows`` is accepted for LOADS1A compatibility and is split by its
    stored Stage value.  New callers should provide the two explicit SLS sets.
    """

    canonical_contract = canonical_station_force_contract(contract)
    canonical_uls = normalize_station_force_rows(
        uls_rows,
        contract=canonical_contract,
        response_type="ULS",
        rows_are_canonical=True,
    )

    if sls_rows is not None and sls_transfer_rows is None and sls_service_rows is None:
        combined_sls = normalize_station_force_rows(
            sls_rows,
            contract=canonical_contract,
            response_type="SLS",
            rows_are_canonical=True,
        )
        canonical_transfer = [
            row for row in combined_sls if canonical_sls_stage(row.get("Stage")) == "Transfer stage"
        ]
        canonical_service = [
            row for row in combined_sls if canonical_sls_stage(row.get("Stage")) == "Final service stage"
        ]
    else:
        canonical_transfer = normalize_station_force_rows(
            sls_transfer_rows,
            contract=canonical_contract,
            response_type="SLS",
            rows_are_canonical=True,
        )
        canonical_service = normalize_station_force_rows(
            sls_service_rows,
            contract=canonical_contract,
            response_type="SLS",
            rows_are_canonical=True,
        )

    # The stage is assigned by the SLS sub-tab, not by a user-editable field.
    for row in canonical_transfer:
        row["Stage"] = "Transfer stage"
    for row in canonical_service:
        row["Stage"] = "Final service stage"

    uls_validation = validate_station_force_rows(
        canonical_uls,
        contract=canonical_contract,
        member_length_m=member_length_m,
        response_type="ULS",
        rows_are_canonical=True,
    )
    transfer_validation = validate_station_force_rows(
        canonical_transfer,
        contract=canonical_contract,
        member_length_m=member_length_m,
        response_type="SLS",
        rows_are_canonical=True,
        expected_sls_stage="Transfer stage",
    )
    service_validation = validate_station_force_rows(
        canonical_service,
        contract=canonical_contract,
        member_length_m=member_length_m,
        response_type="SLS",
        rows_are_canonical=True,
        expected_sls_stage="Final service stage",
    )
    combined_sls = canonical_transfer + canonical_service
    payload = {
        "schema": CROSSBEAM_STATION_FORCE_HANDOFF_SCHEMA,
        "contract": canonical_contract,
        "uls_rows": canonical_uls,
        "sls_transfer_rows": canonical_transfer,
        "sls_service_rows": canonical_service,
        # Retained for downstream compatibility while Analysis migrates to the
        # explicit stage collections.
        "sls_rows": combined_sls,
        "uls_validation": uls_validation.as_dict(),
        "sls_transfer_validation": transfer_validation.as_dict(),
        "sls_service_validation": service_validation.as_dict(),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    payload["fingerprint"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload["ready_for_analysis"] = bool(
        uls_validation.ready and transfer_validation.ready and service_validation.ready
    )
    return payload

"""Construction-mode-aware ULS reinforcement source contract for Crossbeams.

``CROSSBEAM.ANALYSIS4C6A`` makes reinforcement ownership explicit before any
Crossbeam ULS solver receives ordinary-rebar, shear-tie, or torsion-cage credit.
The contract is rebuilt from the active construction mode on demand; it is not a
second persisted engineering input and it does not reinterpret dormant mode data.

Cast-in-Place uses the Solid-only template/Section-Zone assignment as the adopted
local reinforcement source.  Precast Segmental uses the accepted Segment-local
Rebar/Transverse template and Zone source while preserving the locked rule that
ordinary longitudinal reinforcement receives no credit across a physical joint.

This module validates source ownership only.  It does not change ACI strength
equations, station generation, development/joint credit, or Project JSON schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.core.reinforcement_system import ordinary_rebar_enabled
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
    cip_adopted_zone_reinforcement_rows,
    cip_assigned_longitudinal_quantity_rows,
    validate_cip_template_model,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.rebar import (
    canonical_rebar_templates,
    canonical_rebar_zones,
    template_map,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import (
    canonical_transverse_templates,
    transverse_template_map,
    validate_transverse_templates,
)


CROSSBEAM_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"


@dataclass(frozen=True)
class CrossbeamUlsRebarSourceContract:
    """Validated active-mode reinforcement handoff consumed by ULS solvers."""

    ready: bool
    status: str
    construction_method: str
    longitudinal_templates: tuple[dict[str, Any], ...]
    zone_assignments: tuple[dict[str, Any], ...]
    transverse_templates: tuple[dict[str, Any], ...]
    adopted_rows: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str


def _get(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get"):
        return state.get(key, default)
    return getattr(state, key, default)


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _hashable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return round(value, 9) if math.isfinite(value) else str(value)
    if isinstance(value, Mapping):
        return {str(key): _hashable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_hashable(item) for item in value]
    return repr(value)


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        _hashable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()




def _apply_transverse_validation(
    validation_errors: list[str],
    validation_warnings: list[str],
    *,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Keep cage/detailing gates inside Torsion/Combined rather than source-blocking ULS.

    A missing or mismatched outer torsion cage is a valid engineering result
    state (LAYOUT/REVIEW REQUIRED), not proof that the assigned shear-tie source
    is absent. Basic template identity/spacing errors still block handoff.
    """

    for message in validation_errors:
        lowered = str(message).casefold()
        if "torsion cage" in lowered or "outer cage" in lowered:
            warnings.append(str(message))
        else:
            errors.append(str(message))
    warnings.extend(str(message) for message in validation_warnings)

def _assigned_source_payload(
    *,
    zones: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return only active assigned source rows for stale-state fingerprinting."""

    longitudinal_by_id = template_map(longitudinal_templates)
    transverse_by_id = transverse_template_map(transverse_templates)
    longitudinal_ids = sorted(
        {
            str(row.get("Longitudinal template") or row.get("Rebar template") or "").strip()
            for row in zones
            if str(row.get("Longitudinal template") or row.get("Rebar template") or "").strip()
        }
    )
    transverse_ids = sorted(
        {
            str(row.get("Transverse template") or "").strip()
            for row in zones
            if str(row.get("Transverse template") or "").strip()
        }
    )
    return {
        "zones": zones,
        "longitudinal": [longitudinal_by_id[item] for item in longitudinal_ids if item in longitudinal_by_id],
        "transverse": [transverse_by_id[item] for item in transverse_ids if item in transverse_by_id],
    }


def _precast_adopted_rows(
    *,
    zones: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    longitudinal_by_id = template_map(longitudinal_templates)
    transverse_by_id = transverse_template_map(transverse_templates)
    output: list[dict[str, Any]] = []
    for zone in zones:
        longitudinal_id = str(zone.get("Longitudinal template") or zone.get("Rebar template") or "").strip()
        transverse_id = str(zone.get("Transverse template") or "").strip()
        issues: list[str] = []
        if longitudinal_id not in longitudinal_by_id:
            issues.append("Longitudinal template does not resolve to an active source")
        if transverse_id not in transverse_by_id:
            issues.append("Transverse template does not resolve to an active source")
        output.append(
            {
                "Zone ID": str(zone.get("Zone ID") or ""),
                "Segment": str(zone.get("Segment") or ""),
                "s_start_m": float(zone.get("s_start_m") or 0.0),
                "s_end_m": float(zone.get("s_end_m") or 0.0),
                "Longitudinal template": longitudinal_id,
                "Transverse template": transverse_id,
                "Adoption basis": "Precast Segment / Rebar Zone assignment",
                "Status": "ADOPTED SOURCE" if not issues else "REVIEW REQUIRED",
                "Issues": issues,
            }
        )
    return output


def build_crossbeam_uls_rebar_source_contract(state: Any) -> CrossbeamUlsRebarSourceContract:
    """Build the active construction-mode ULS reinforcement source contract.

    Dormant Cast-in-Place data is ignored in Precast mode, and dormant Precast
    data is ignored in Cast-in-Place mode.  Only assigned active-mode templates
    participate in the fingerprint, so editing an unassigned library row does
    not stale valid ULS results.
    """

    construction_method = normalize_construction_method(
        _get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
    )
    layout_rows = _records(_get(state, CROSSBEAM_SEGMENT_ROWS_KEY, []))
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if not layout_rows:
        errors.append("Crossbeam Segment / Zone Layout is missing for ULS reinforcement handoff.")
    if not ordinary_rebar_enabled(state, default=True):
        errors.append("Ordinary reinforcement is disabled in Section Builder; ULS reinforcement credit is not authorized.")

    if construction_method == CONSTRUCTION_METHOD_CIP:
        longitudinal = canonical_rebar_templates(
            _records(_get(state, CIP_RB_TEMPLATE_ROWS_KEY, []))
        )
        zones = canonical_rebar_zones(
            _records(_get(state, CIP_RB_ZONE_ROWS_KEY, []))
        )
        transverse = canonical_transverse_templates(
            _records(_get(state, CIP_TR_TEMPLATE_ROWS_KEY, []))
        )
        assigned_source = _assigned_source_payload(
            zones=zones,
            longitudinal_templates=longitudinal,
            transverse_templates=transverse,
        )
        assigned_longitudinal = [dict(row) for row in assigned_source["longitudinal"]]
        assigned_transverse = [dict(row) for row in assigned_source["transverse"]]
        model_errors, model_warnings = validate_cip_template_model(
            layout_rows=layout_rows,
            longitudinal_templates=assigned_longitudinal,
            transverse_templates=assigned_transverse,
            zone_assignments=zones,
        )
        errors.extend(model_errors)
        warnings.extend(model_warnings)
        _, transverse_errors, transverse_warnings = validate_transverse_templates(assigned_transverse)
        _apply_transverse_validation(
            transverse_errors, transverse_warnings, errors=errors, warnings=warnings
        )

        quantity_rows = cip_assigned_longitudinal_quantity_rows(
            layout_rows=layout_rows,
            longitudinal_templates=assigned_longitudinal,
            zone_assignments=zones,
        )
        for row in quantity_rows:
            if not bool(row.get("Complete")):
                errors.append(
                    f"{row.get('Template ID')}: ULS longitudinal quantity source is incomplete — "
                    f"{row.get('Issue') or 'define a valid bar-size/count-or-spacing source.'}"
                )
        adopted_rows = cip_adopted_zone_reinforcement_rows(
            layout_rows=layout_rows,
            longitudinal_templates=assigned_longitudinal,
            transverse_templates=assigned_transverse,
            zone_assignments=zones,
        )
        for row in adopted_rows:
            if str(row.get("Status") or "") != "ADOPTED SOURCE":
                issues = "; ".join(str(item) for item in row.get("Issues") or [])
                errors.append(
                    f"{row.get('Zone ID') or 'CIP Zone'}: ULS reinforcement source is not adopted — {issues or 'review assignment.'}"
                )
        info.append(
            "Cast-in-Place ULS credit uses the active Solid Section/Zone longitudinal and transverse template assignments."
        )
        info.append(
            "CIP Zone boundaries remain monolithic property boundaries; no physical-joint rebar exclusion is introduced."
        )
    else:
        longitudinal = canonical_rebar_templates(
            _records(_get(state, CB_RB_TEMPLATE_ROWS_KEY, []))
        )
        raw_zones = _records(_get(state, CB_RB_ZONE_ROWS_KEY, []))
        transverse = canonical_transverse_templates(
            _records(_get(state, CB_TR_TEMPLATE_ROWS_KEY, []))
        )
        canonical_zones = canonical_rebar_zones(raw_zones)
        assigned_source = _assigned_source_payload(
            zones=canonical_zones,
            longitudinal_templates=longitudinal,
            transverse_templates=transverse,
        )
        assigned_longitudinal = [dict(row) for row in assigned_source["longitudinal"]]
        assigned_transverse = [dict(row) for row in assigned_source["transverse"]]
        zones, zone_errors, zone_warnings = validate_rebar_zones(
            raw_zones,
            layout_rows,
            assigned_longitudinal,
            assigned_transverse,
        )
        errors.extend(zone_errors)
        warnings.extend(zone_warnings)
        _, transverse_errors, transverse_warnings = validate_transverse_templates(assigned_transverse)
        _apply_transverse_validation(
            transverse_errors, transverse_warnings, errors=errors, warnings=warnings
        )
        adopted_rows = _precast_adopted_rows(
            zones=zones,
            longitudinal_templates=assigned_longitudinal,
            transverse_templates=assigned_transverse,
        )
        for row in adopted_rows:
            if str(row.get("Status") or "") != "ADOPTED SOURCE":
                issues = "; ".join(str(item) for item in row.get("Issues") or [])
                errors.append(
                    f"{row.get('Zone ID') or row.get('Segment') or 'Precast Zone'}: "
                    f"ULS reinforcement source is not adopted — {issues or 'review assignment.'}"
                )
        info.append(
            "Precast Segmental ULS credit uses the active Segment-local Rebar/Transverse template and Zone assignments."
        )
        info.append(
            "Physical-joint and development-zone ordinary longitudinal credit remains governed by the existing tendon-only exclusion route."
        )

    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    info = _dedupe(info)
    source_payload = _assigned_source_payload(
        zones=zones,
        longitudinal_templates=assigned_longitudinal,
        transverse_templates=assigned_transverse,
    )
    fingerprint = _fingerprint(
        {
            "schema": "crossbeam-analysis4c6a-uls-rebar-source-v1",
            "construction_method": construction_method,
            "layout": layout_rows,
            "assigned_source": source_payload,
            "errors": errors,
        }
    )
    ready = bool(layout_rows and adopted_rows) and not errors
    return CrossbeamUlsRebarSourceContract(
        ready=ready,
        status="READY" if ready else "SOURCE BLOCKED",
        construction_method=construction_method,
        longitudinal_templates=tuple(dict(row) for row in assigned_longitudinal),
        zone_assignments=tuple(dict(row) for row in zones),
        transverse_templates=tuple(dict(row) for row in assigned_transverse),
        adopted_rows=tuple(dict(row) for row in adopted_rows),
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(info),
        fingerprint=fingerprint,
    )

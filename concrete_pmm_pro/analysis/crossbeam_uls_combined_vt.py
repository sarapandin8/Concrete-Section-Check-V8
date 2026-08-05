"""Combined ACI 318-19 shear + torsion checks for Portal Frame Crossbeams.

This workflow-scoped module implements the Crossbeam ULS V+T solver-adoption route without
changing the generic PMM, Beam/Girder, or Column/Pier solvers.  It combines the
accepted Crossbeam Shear and standalone Torsion station contracts and performs:

* ACI 9.5.4.3 additive transverse reinforcement, ``Av/s + 2At/s``;
* ACI 9.5.4.4 prestressed flexure plus concentric torsional tension using the
  direct exact-axis Crossbeam P-M3 strain-compatibility solver;
* ACI 22.7.7 solid/hollow combined shear-torsion section-size stress gate;
* the existing shear, torsion-strength, minimum-reinforcement, and detailing
  source gates without silently overriding a component failure.

Physical Precast Segment joints remain one-sided REVIEW locations.  This module
checks adjacent section capacities; it does not design interface shear/torsion
transfer, shear keys, anchorage zones, or D-regions.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass
import math
from typing import Any

from concrete_pmm_pro.analysis.crossbeam_flexure_uniaxial import solve_crossbeam_uniaxial_flexure
from concrete_pmm_pro.analysis.crossbeam_uls import (
    CROSSBEAM_ULS_LOAD_TABLE_KEY,
    CrossbeamUlsPreparation,
    PreparedCrossbeamUlsRow,
    _fingerprint,
    build_crossbeam_uls_flexure_preparation,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    CrossbeamShearPreparation,
    PreparedCrossbeamShearRow,
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    CrossbeamTorsionPreparation,
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY


CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY = "crossbeam_analysis4c2_uls_combined_vt_result"
CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY = "crossbeam_analysis4c2_uls_combined_vt_input_hash"


@dataclass(frozen=True)
class CrossbeamCombinedVtPreparation:
    ready: bool
    shear: CrossbeamShearPreparation
    torsion: CrossbeamTorsionPreparation
    flexure: CrossbeamUlsPreparation
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str
    support_footprints: tuple[dict[str, Any], ...]
    member_length_m: float
    construction_method: str
    excluded_end_zone_rows: tuple[dict[str, Any], ...] = ()
    pt_end_zone_settings: Mapping[str, Any] | None = None


def _dedupe(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _finite(value: Any, default: float = float("nan")) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _station_key(case: Any, station: Any, check_point: Any) -> tuple[str, float, str]:
    return str(case or "ULS"), round(_finite(station, 0.0), 9), str(check_point or "")


def _shear_row_key(row: PreparedCrossbeamShearRow) -> tuple[str, float, str]:
    return _station_key(row.case_name, row.station_m, row.check_point)


def _result_row_key(row: Mapping[str, Any]) -> tuple[str, float, str]:
    return _station_key(row.get("Case"), row.get("Station s (m)"), row.get("Check Point"))


def _flexure_row_key(row: PreparedCrossbeamUlsRow) -> tuple[str, float, str]:
    return _station_key(row.case_name, row.station_m, row.check_point)


def _sectional_source_rows(preparation: CrossbeamShearPreparation) -> list[PreparedCrossbeamShearRow]:
    return [
        row
        for row in preparation.rows
        if row.location_type != "PHYSICAL SEGMENT JOINT" and not row.generated_joint_side_check
    ]


def _combined_demand_rows(preparation: CrossbeamShearPreparation) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _sectional_source_rows(preparation):
        rows.append(
            {
                "Active": True,
                "Station s (m)": row.station_m,
                "Check Point": row.check_point,
                "Case Name": row.case_name,
                "P": row.source_p_kn,
                "V2": row.source_v2_kn,
                "T": row.source_t_knm,
                "M3": row.source_m3_knm,
                "Note": "Combined V+T generated from the accepted row-coupled Shear/Torsion station contract.",
                "__Derived support check": bool(row.generated_support_check),
                "__Location type": row.location_type,
                "__Context station s (m)": row.station_m,
                "__Demand source": row.demand_source,
                "__Source station 1 (m)": row.source_station_1_m,
                "__Source station 2 (m)": row.source_station_2_m,
                "__Source ratio": row.source_ratio,
                "__Extrapolation ratio": row.extrapolation_ratio,
            }
        )
    return rows


def build_crossbeam_uls_combined_vt_preparation(state: Any) -> CrossbeamCombinedVtPreparation:
    shear = build_crossbeam_uls_shear_preparation(state)
    torsion = build_crossbeam_uls_torsion_preparation(state)
    errors = [*shear.errors, *torsion.errors]
    warnings = [*shear.warnings, *torsion.warnings]
    info = [*shear.info, *torsion.info]

    # Build exact-axis flexural section inputs at the same imported/support
    # stations used by V+T.  The canonical Crossbeam Flexure builder owns the
    # Precast development-credit gate, Section/Rebar/Tendon assembly, and ACI
    # direct-solver input semantics.  Physical joints are intentionally omitted.
    try:
        temporary_state = dict(state)
    except Exception:
        temporary_state = copy(state)
    temporary_state[CROSSBEAM_ULS_LOAD_TABLE_KEY] = _combined_demand_rows(shear)
    flexure = build_crossbeam_uls_flexure_preparation(
        temporary_state,
        station_rows_are_pre_routed=True,
    )
    errors.extend(flexure.errors)
    warnings.extend(flexure.warnings)
    info.extend(flexure.info)

    expected_keys = {_shear_row_key(row) for row in _sectional_source_rows(shear)}
    flexure_by_key: dict[tuple[str, float, str], list[PreparedCrossbeamUlsRow]] = {}
    for row in flexure.rows:
        key = _flexure_row_key(row)
        if key in expected_keys:
            flexure_by_key.setdefault(key, []).append(row)
    for key in sorted(expected_keys):
        matches = flexure_by_key.get(key, [])
        if len(matches) != 1:
            errors.append(
                f"Combined V+T direct-flexure source {key[0]} at s={key[1]:.6f} m / {key[2] or 'interior'} "
                f"resolved to {len(matches)} section inputs; exactly one is required."
            )

    construction_method = normalize_construction_method(
        state.get(CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
        if hasattr(state, "get")
        else CONSTRUCTION_METHOD_PRECAST
    )
    payload = {
        "schema": "crossbeam-analysis4c2-combined-vt-v2",
        "shear": shear.fingerprint,
        "torsion": torsion.fingerprint,
        "flexure": flexure.fingerprint,
        "construction_method": construction_method,
        "section_keys": sorted(expected_keys),
    }
    return CrossbeamCombinedVtPreparation(
        ready=bool(shear.ready and torsion.ready and flexure.ready and not errors),
        shear=shear,
        torsion=torsion,
        flexure=flexure,
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
        info=_dedupe(info),
        fingerprint=_fingerprint(payload),
        support_footprints=tuple(shear.support_footprints),
        member_length_m=float(shear.member_length_m),
        construction_method=construction_method,
        excluded_end_zone_rows=tuple(shear.excluded_end_zone_rows),
        pt_end_zone_settings=dict(shear.pt_end_zone_settings or {}),
    )


def _longitudinal_fy_mpa(torsion_row: Mapping[str, Any]) -> float:
    direct = _finite(torsion_row.get("Longitudinal fy MPa"))
    if math.isfinite(direct) and direct > 0.0:
        return direct
    tu = abs(_finite(torsion_row.get("T kN-m"), 0.0)) * 1.0e6
    ph = _finite(torsion_row.get("ph mm"))
    phi = _finite(torsion_row.get("phi"), 0.75)
    ao = _finite(torsion_row.get("Ao mm2"))
    tan_theta = math.tan(math.radians(_finite(torsion_row.get("theta deg"), 45.0)))
    al_strength = _finite(torsion_row.get("Al strength required mm2"))
    denominator = phi * 2.0 * ao * tan_theta * al_strength
    if all(math.isfinite(value) and value > 0.0 for value in (tu, ph, denominator)):
        return tu * ph / denominator
    return float("nan")


def _moment_sign_for_row(target: PreparedCrossbeamUlsRow, candidates: list[PreparedCrossbeamUlsRow]) -> float:
    if abs(float(target.source_m3_knm)) > 1.0e-9:
        return -1.0 if target.source_m3_knm < 0.0 else 1.0
    same_case = [
        row for row in candidates
        if row.case_name == target.case_name and abs(float(row.source_m3_knm)) > 1.0e-9
    ]
    if not same_case:
        return 1.0
    nearest = min(same_case, key=lambda row: (abs(row.station_m - target.station_m), row.station_m))
    return -1.0 if nearest.source_m3_knm < 0.0 else 1.0


def _joint_review_row(
    source: PreparedCrossbeamShearRow,
    shear_row: Mapping[str, Any] | None,
    torsion_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "Check": "Shear + Torsion",
        "Status": "REVIEW",
        "Station type": "PHYSICAL JOINT SIDE",
        "Station s (m)": source.station_m,
        "Check Point": source.check_point,
        "Case": source.case_name,
        "Location type": source.location_type,
        "Section face": source.section_face,
        "Segment": source.segment_id,
        "Section ID": source.section_id,
        "Joint side": source.joint_side,
        "Joint station s (m)": source.joint_station_m,
        "P kN": source.source_p_kn,
        "V2 kN": source.source_v2_kn,
        "T kN-m": source.source_t_knm,
        "M3 kN-m": source.source_m3_knm,
        "Demand source": source.demand_source,
        "Stress status": "NOT CHECKED",
        "Transverse status": "NOT CHECKED",
        "Longitudinal status": "NOT CHECKED",
        "Stress D/C value": float("nan"),
        "Transverse D/C value": float("nan"),
        "Longitudinal D/C value": float("nan"),
        "Overall D/C value": float("nan"),
        "phiVn kN": float("nan") if shear_row is None else _finite(shear_row.get("φVn kN")),
        "phiTn kN-m": float("nan") if torsion_row is None else _finite(torsion_row.get("phiTn kN-m")),
        "Notes": (
            "One-sided adjacent section values are retained for audit. Physical-joint V+T transfer, shear keys/interface friction, "
            "compression, local reinforcement, and D-region behavior require a separate project design and cannot receive PASS here."
        ),
    }


def _section_combined_row(
    source: PreparedCrossbeamShearRow,
    shear_row: Mapping[str, Any],
    torsion_row: Mapping[str, Any],
    flexure_row: PreparedCrossbeamUlsRow,
    flexure_candidates: list[PreparedCrossbeamUlsRow],
    *,
    construction_method: str,
) -> dict[str, Any]:
    torsion_required = str(torsion_row.get("Threshold status") or "") == "DESIGN REQUIRED"
    torsion_layout_required = torsion_required and str(torsion_row.get("Status") or "") == "LAYOUT REQUIRED"

    # ACI 9.5.4.3 adds the required allocations for concurrent shear and
    # torsion.  The provided side is the unique physical vertical-leg pool:
    # all shear-effective legs plus two side legs from an *additional* verified
    # torsion cage.  A cage shared with the shear loop is already inside Av and
    # is never counted a second time.
    shear_strength_req = max(_finite(shear_row.get("Av/s strength required mm2/mm"), 0.0), 0.0)
    shear_min_req = max(_finite(shear_row.get("Av/s minimum required mm2/mm"), 0.0), 0.0)
    shear_adopted_req = max(
        _finite(shear_row.get("Av/s adopted required mm2/mm"), 0.0),
        shear_strength_req,
        shear_min_req,
    )
    shear_provided = _finite(shear_row.get("Av/s mm2/mm"))
    if torsion_required:
        at_req = max(_finite(torsion_row.get("At/s required mm2/mm"), 0.0), 0.0)
        combined_strength_req = shear_adopted_req + 2.0 * at_req
        combined_min_req = max(_finite(torsion_row.get("(Av+2At)/s min mm2/mm"), 0.0), 0.0)
        combined_required = max(combined_strength_req, combined_min_req)
        combined_provided = _finite(
            torsion_row.get(
                "Unique transverse provided/s mm2/mm",
                shear_row.get("Unique combined provided/s mm2/mm", shear_provided),
            )
        )
        transverse_dc = combined_required / combined_provided if combined_provided > 0.0 else float("inf")
        stress_dc = _finite(torsion_row.get("Section limit D/C value"))
    else:
        at_req = 0.0
        combined_strength_req = shear_adopted_req
        combined_min_req = 0.0
        combined_required = shear_adopted_req
        combined_provided = shear_provided
        transverse_dc = combined_required / combined_provided if combined_provided > 0.0 else float("inf")
        stress_dc = _finite(shear_row.get("Section limit D/C"))

    # ACI 9.5.4.4 permits the bonded prestressing steel and ordinary
    # longitudinal bars to resist Mu plus the additional concentric tensile
    # force generated by torsion.  Al,strength*fy becomes an additional axial
    # tension demand; the minimum distributed Al and perimeter detailing remain
    # separate ordinary-reinforcement gates.
    al_strength = _finite(torsion_row.get("Al strength required mm2"), 0.0) if torsion_required else 0.0
    al_minimum = _finite(torsion_row.get("Al minimum mm2"), 0.0) if torsion_required else 0.0
    al_provided = _finite(torsion_row.get("Al provided mm2"), 0.0) if torsion_required else 0.0
    fy_long = _longitudinal_fy_mpa(torsion_row) if torsion_required else float("nan")
    al_minimum_dc = (
        al_minimum / al_provided
        if torsion_required and al_provided > 0.0
        else (float("inf") if torsion_required and al_minimum > 0.0 else float("nan"))
    )
    torsion_tension_n = al_strength * fy_long if torsion_required and math.isfinite(fy_long) else 0.0
    combined_pu_n = source.source_p_kn * 1000.0 - torsion_tension_n

    interaction_status = "NOT REQUIRED"
    interaction_dc = float("nan")
    interaction_moment_dc = float("nan")
    interaction_axial_dc = float("nan")
    interaction_capacity_knm = float("nan")
    solver_status = "NOT REQUIRED"
    force_residual_n = float("nan")
    if torsion_required:
        sign = _moment_sign_for_row(flexure_row, flexure_candidates)
        solver = solve_crossbeam_uniaxial_flexure(
            flexure_row.analysis_input,
            Pu_N=combined_pu_n,
            moment_sign=sign,
        )
        solver_status = solver.status
        force_residual_n = _finite(solver.force_residual_N)
        interaction_axial_dc = _finite(solver.axial_dcr)
        if solver.state is None or solver.capacity_phiMn_Nmm is None or solver.capacity_phiMn_Nmm <= 0.0:
            interaction_status = "REVIEW"
        else:
            interaction_capacity_knm = solver.capacity_phiMn_Nmm / 1.0e6
            interaction_moment_dc = abs(source.source_m3_knm) / interaction_capacity_knm if interaction_capacity_knm > 0.0 else float("inf")
            interaction_candidates = [
                value for value in (interaction_moment_dc, interaction_axial_dc) if math.isfinite(value)
            ]
            interaction_dc = max(interaction_candidates) if interaction_candidates else interaction_moment_dc
            if solver.status != "PASS":
                interaction_status = "REVIEW"
            elif interaction_dc > 1.0 + 1.0e-9:
                interaction_status = "FAIL"
            else:
                interaction_status = "PASS"

    bt_mm = _finite(torsion_row.get("bt mm"), 0.0) if torsion_required else 0.0
    d_mm = _finite(torsion_row.get("d mm"), 0.0) if torsion_required else 0.0
    extension_length_m = (bt_mm + d_mm) / 1000.0 if bt_mm > 0.0 and d_mm > 0.0 else float("nan")
    location_text = f"{source.location_type} {source.requested_location_type} {source.check_point}".upper()
    at_support_face = torsion_required and "COLUMN FACE" in location_text
    available_extension_m = _finite(flexure_row.distance_to_nearest_segment_end_m, float("nan"))
    extension_dc = (
        extension_length_m / available_extension_m
        if torsion_required
        and construction_method == CONSTRUCTION_METHOD_PRECAST
        and math.isfinite(extension_length_m)
        and extension_length_m > 0.0
        and math.isfinite(available_extension_m)
        and available_extension_m > 0.0
        else float("nan")
    )
    if not torsion_required:
        station_development_status = "NOT REQUIRED"
        support_anchorage_status = "NOT REQUIRED"
    elif construction_method == CONSTRUCTION_METHOD_PRECAST:
        # ACI 9.7.5.3 and 9.7.6.3.2 require longitudinal and transverse
        # torsion reinforcement to continue at least bt+d beyond the point
        # where it is required.  The template is known to cover the assigned
        # physical Segment, so the nearest Segment end is the maximum
        # automatically verifiable continuation distance.  Crossing the
        # physical joint is never assumed.
        if (
            not math.isfinite(extension_length_m)
            or extension_length_m <= 0.0
            or not math.isfinite(available_extension_m)
            or available_extension_m + 1.0e-9 < extension_length_m
        ):
            station_development_status = "REVIEW"
        else:
            station_development_status = "PASS"
        support_anchorage_status = "REVIEW" if at_support_face else "NOT APPLICABLE"
    else:
        # CIP zone boundaries are not physical joints in the Crossbeam model.
        # The active reinforcement source is treated as monolithic, while
        # actual bar cut-off and support anchorage remain drawing/detail checks.
        station_development_status = "PASS"
        support_anchorage_status = "REVIEW" if at_support_face else "NOT APPLICABLE"

    longitudinal_detailing_values = [
        _finite(torsion_row.get("Outer bar spacing D/C")),
        _finite(torsion_row.get("Outer bar diameter D/C")),
        _finite(torsion_row.get("Corner coverage D/C")),
    ] if torsion_required else []
    longitudinal_detailing_values = [value for value in longitudinal_detailing_values if math.isfinite(value)]
    longitudinal_detailing_dc = max(longitudinal_detailing_values) if longitudinal_detailing_values else float("nan")
    long_dc_values = [
        value for value in (al_minimum_dc, interaction_dc, longitudinal_detailing_dc) if math.isfinite(value)
    ]
    longitudinal_dc = max(long_dc_values) if long_dc_values else (float("inf") if torsion_required else float("nan"))

    if torsion_layout_required:
        transverse_status = "REVIEW"
    else:
        transverse_status = "PASS" if transverse_dc <= 1.0 + 1.0e-9 else "FAIL"
    stress_status = "PASS" if math.isfinite(stress_dc) and stress_dc <= 1.0 + 1.0e-9 else ("FAIL" if math.isfinite(stress_dc) else "REVIEW")
    if not torsion_required:
        longitudinal_status = "NOT REQUIRED"
    elif any(
        math.isfinite(value) and value > 1.0 + 1.0e-9
        for value in (al_minimum_dc, interaction_dc, longitudinal_detailing_dc)
    ) or interaction_status == "FAIL":
        longitudinal_status = "FAIL"
    elif (
        torsion_layout_required
        or interaction_status == "REVIEW"
        or station_development_status == "REVIEW"
        or support_anchorage_status == "REVIEW"
        or (flexure_row.rebar_credit_status == "NO CREDIT" and al_minimum > 0.0)
    ):
        longitudinal_status = "REVIEW"
    else:
        longitudinal_status = "PASS"

    shear_component_statuses = {
        str(shear_row.get("Strength status") or "REVIEW"),
        str(shear_row.get("Detailing status") or "REVIEW"),
        str(shear_row.get("Section limit status") or "REVIEW"),
    }
    torsion_detailing_status = str(torsion_row.get("Detailing status") or "REVIEW") if torsion_required else "NOT REQUIRED"
    torsion_section_status = str(torsion_row.get("Section limit status") or "REVIEW") if torsion_required else "NOT REQUIRED"
    source_fail = (
        "FAIL" in shear_component_statuses
        or torsion_detailing_status == "FAIL"
        or torsion_section_status == "FAIL"
    )
    source_review = (
        "REVIEW" in shear_component_statuses
        or torsion_layout_required
        or torsion_detailing_status == "REVIEW"
        or torsion_section_status == "REVIEW"
        or bool(torsion_row.get("Hollow cage continuity review"))
        or source.source_p_kn < -1.0e-9
    )
    if source_fail or "FAIL" in {stress_status, transverse_status, longitudinal_status}:
        status = "FAIL"
    elif source_review or "REVIEW" in {stress_status, transverse_status, longitudinal_status}:
        status = "REVIEW"
    else:
        status = "PASS"

    finite_dcs = [
        value
        for value in (
            stress_dc,
            transverse_dc,
            longitudinal_dc,
            _finite(shear_row.get("Strength D/C value")),
            _finite(shear_row.get("Detailing D/C value")),
            _finite(torsion_row.get("Detailing D/C value")) if torsion_required else float("nan"),
        )
        if math.isfinite(value)
    ]
    overall_dc = max(finite_dcs) if finite_dcs else float("nan")
    notes = [
        "ACI 9.5.4.3 compares required Av/s + 2At/s with the unique physical vertical-leg pool; additional cage side legs are included once and shared cage legs are not duplicated.",
        "ACI 9.5.4.4 is checked by solving the exact-axis Crossbeam section at Pu minus the concentric torsional tensile force Al,strength·fy while retaining concurrent row-coupled Mu.",
        "Al,min and longitudinal perimeter detailing remain ordinary-reinforcement gates independent of bonded tendon overstrength.",
        "The assigned torsion template covers the full Segment; the reported bt+d extension length is audited, while physical-joint transfer remains a separate REVIEW.",
    ]
    if torsion_required and flexure_row.rebar_credit_status == "NO CREDIT":
        notes.append(
            f"Ordinary longitudinal flexure credit is NO CREDIT ({flexure_row.development_region}); the direct interaction therefore does not reuse undeveloped As. Torsion bt+d continuation is audited separately."
        )
    if torsion_required and station_development_status == "REVIEW":
        notes.append(
            f"ACI torsion continuation review: available distance to the nearest physical Segment end = {available_extension_m:.3f} m versus required bt+d = {extension_length_m:.3f} m. Reinforcement continuity across a Precast joint is not assumed."
        )
    if bool(torsion_row.get("Hollow cage continuity review")):
        notes.append("Hollow closed-cage continuity, lap, and anchorage remain REVIEW.")
    if at_support_face:
        notes.append("ACI support-face development/anchorage is REVIEW because hooks, embedment, and support anchorage details are not modeled in the template source.")

    return {
        "Check": "Shear + Torsion",
        "Status": status,
        "Station type": source.location_type,
        "Station s (m)": source.station_m,
        "Check Point": source.check_point,
        "Case": source.case_name,
        "Location type": source.location_type,
        "Section face": source.section_face,
        "Segment": source.segment_id,
        "Section ID": source.section_id,
        "Rebar Zone": source.rebar_zone_id,
        "Transverse Template": source.transverse_template_id,
        "P kN": source.source_p_kn,
        "V2 kN": source.source_v2_kn,
        "T kN-m": source.source_t_knm,
        "M3 kN-m": source.source_m3_knm,
        "Demand source": source.demand_source,
        "Generated support check": source.generated_support_check,
        "Requested location type": source.requested_location_type,
        "Torsion required": torsion_required,
        "Stress status": stress_status,
        "Transverse status": transverse_status,
        "Longitudinal status": longitudinal_status,
        "Stress D/C value": stress_dc,
        "Transverse D/C value": transverse_dc,
        "Longitudinal D/C value": longitudinal_dc,
        "Overall D/C value": overall_dc,
        "Shear strength D/C value": _finite(shear_row.get("Strength D/C value")),
        "Shear detailing D/C value": _finite(shear_row.get("Detailing D/C value")),
        "Torsion detailing D/C value": _finite(torsion_row.get("Detailing D/C value")) if torsion_required else float("nan"),
        "Av/s strength required mm2/mm": shear_strength_req,
        "Av/s minimum required mm2/mm": shear_min_req,
        "Av/s adopted required mm2/mm": shear_adopted_req,
        "Av/s provided all shear legs mm2/mm": shear_provided,
        "At/s required mm2/mm": at_req,
        "(Av+2At)/s strength required mm2/mm": combined_strength_req,
        "(Av+2At)/s minimum required mm2/mm": combined_min_req,
        "(Av+2At)/s adopted required mm2/mm": combined_required,
        "Unique transverse provided/s mm2/mm": combined_provided,
        "Outer side legs/s provided mm2/mm": _finite(torsion_row.get("Outer side legs/s provided mm2/mm")),
        "(Av+2At)/s provided mm2/mm": combined_provided,
        "Torsion cage relationship": str(torsion_row.get("Torsion cage relationship") or ""),
        "Torsion cage source status": str(torsion_row.get("Torsion cage source status") or ""),
        "Al strength equivalent mm2": al_strength,
        "Al strength required mm2": al_strength,
        "Al minimum required mm2": al_minimum,
        "Al minimum/adopted required mm2": al_minimum,
        "Al provided mm2": al_provided,
        "Al minimum D/C value": al_minimum_dc,
        "Al area D/C value": al_minimum_dc,
        "Longitudinal detailing D/C value": longitudinal_detailing_dc,
        "Longitudinal fy MPa": fy_long,
        "Torsional tensile force kN": torsion_tension_n / 1000.0,
        "Combined Pu for 9.5.4.4 kN": combined_pu_n / 1000.0,
        "Flexure+torsion phiMn kN-m": interaction_capacity_knm,
        "Flexure+torsion moment D/C value": interaction_moment_dc,
        "Flexure+torsion axial D/C value": interaction_axial_dc,
        "Flexure+torsion D/C value": interaction_dc,
        "Flexure+torsion status": interaction_status,
        "Direct solver status": solver_status,
        "Direct solver force residual N": force_residual_n,
        "Ordinary rebar credit": flexure_row.rebar_credit_status,
        "Development region": flexure_row.development_region,
        "Development length m": flexure_row.development_length_m,
        "Torsion bt mm": bt_mm,
        "Torsion bt+d extension m": extension_length_m,
        "Available extension to nearest Segment end m": available_extension_m,
        "Torsion extension D/C value": extension_dc,
        "Torsion station development status": station_development_status,
        "Torsion support anchorage status": support_anchorage_status,
        "phiVn kN": _finite(shear_row.get("φVn kN")),
        "phiTn kN-m": _finite(torsion_row.get("phiTn kN-m")),
        "Section limit lhs MPa": _finite(torsion_row.get("Section limit lhs MPa")),
        "Section limit rhs MPa": _finite(torsion_row.get("Section limit rhs MPa")),
        "Notes": " | ".join(_dedupe(notes)),
    }

def _rank(row: Mapping[str, Any]) -> tuple[int, float, float]:
    priority = {"FAIL": 4, "REVIEW": 3, "PASS": 2}.get(str(row.get("Status") or "REVIEW"), 3)
    dc = _finite(row.get("Overall D/C value"), -1.0)
    return priority, dc if math.isfinite(dc) else -1.0, abs(_finite(row.get("V2 kN"), 0.0)) + abs(_finite(row.get("T kN-m"), 0.0))


def run_crossbeam_uls_combined_vt(preparation: CrossbeamCombinedVtPreparation) -> dict[str, Any]:
    if not preparation.ready:
        raise ValueError("Crossbeam ULS Shear + Torsion preparation is not ready.")

    shear_result = run_crossbeam_uls_shear(preparation.shear)
    torsion_result = run_crossbeam_uls_torsion(preparation.torsion)
    shear_by_key = {_result_row_key(row): row for row in shear_result.get("rows") or []}
    torsion_by_key = {_result_row_key(row): row for row in torsion_result.get("rows") or []}
    expected_keys = {_shear_row_key(row) for row in _sectional_source_rows(preparation.shear)}
    flexure_by_key = {
        _flexure_row_key(row): row
        for row in preparation.flexure.rows
        if _flexure_row_key(row) in expected_keys
    }
    flexure_candidates = list(flexure_by_key.values())

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for source in preparation.shear.rows:
        key = _shear_row_key(source)
        shear_row = shear_by_key.get(key)
        torsion_row = torsion_by_key.get(key)
        if source.location_type == "PHYSICAL SEGMENT JOINT":
            continue
        if source.generated_joint_side_check:
            rows.append(_joint_review_row(source, shear_row, torsion_row))
            continue
        flexure_row = flexure_by_key.get(key)
        if shear_row is None or torsion_row is None or flexure_row is None:
            errors.append(f"Missing combined source at {key[0]} s={key[1]:.6f} m / {key[2] or 'interior'}.")
            continue
        try:
            rows.append(
                _section_combined_row(
                    source,
                    shear_row,
                    torsion_row,
                    flexure_row,
                    flexure_candidates,
                    construction_method=preparation.construction_method,
                )
            )
        except Exception as exc:
            errors.append(f"{source.case_name} at s={source.station_m:.6f} m: {exc}")

    sectional = [row for row in rows if row.get("Station type") != "PHYSICAL JOINT SIDE"]
    joint_sides = [row for row in rows if row.get("Station type") == "PHYSICAL JOINT SIDE"]
    joint_locations = sorted({round(_finite(row.get("Joint station s (m)"), row.get("Station s (m)")), 9) for row in joint_sides})
    governing = max(sectional, key=_rank) if sectional else None
    if errors:
        sectional_status = "REVIEW"
    elif any(row.get("Status") == "FAIL" for row in sectional):
        sectional_status = "FAIL"
    elif any(row.get("Status") == "REVIEW" for row in sectional):
        sectional_status = "REVIEW"
    else:
        sectional_status = "PASS"
    if sectional_status == "FAIL":
        overall_status = "FAIL"
    elif sectional_status == "REVIEW" or joint_locations or errors:
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"

    return {
        "status": overall_status,
        "sectional_status": sectional_status,
        "rows": rows,
        "governing_row": governing,
        "total_checks": len(rows),
        "sectional_checks": len(sectional),
        "joint_side_checks": len(joint_sides),
        "joint_review_count": len(joint_locations),
        "joint_review_stations_m": joint_locations,
        "generated_support_checks": sum(bool(row.get("Generated support check")) for row in sectional),
        "errors": list(_dedupe(errors)),
        "warnings": list(preparation.warnings),
        "fingerprint": preparation.fingerprint,
        "construction_method": preparation.construction_method,
        "support_footprints": [dict(item) for item in preparation.support_footprints],
        "member_length_m": float(preparation.member_length_m),
        "excluded_pt_end_zone_rows": [],
        "pt_end_zone_settings": dict(preparation.pt_end_zone_settings or {}),
        "scope": (
            "ACI 318-19 Crossbeam combined V+T: 9.5.4.3 additive required Av/s + 2At/s checked against the unique physical transverse-leg pool without double counting, 9.5.4.4 prestressed flexure plus concurrent torsional longitudinal tension, "
            "and 22.7.7 solid/hollow section-size stress limits. Physical-joint transfer, compatibility-torsion redistribution, hollow cage lap/anchorage, "
            "PT anchorage/end zones, D-regions, fatigue, and seismic detailing remain separate project checks."
        ),
    }

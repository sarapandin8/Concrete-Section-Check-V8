"""Lightweight AASHTO time-dependent prestress-loss preview for Crossbeam PT.

PTLOSS4A reuses only the unit-safe creep/shrinkage material-factor concepts from
Segmental Box Girder Pro.  Crossbeam geometry, construction method, tendon force
state, and bond-system routing remain independent sources.

The ordinary route is intentionally arithmetic-only: it consumes a CURRENT
Lightweight Elastic Shortening result and performs no structural solve.  For
Cast-in-Place nonsegmental post-tensioned Crossbeams, the calculation is a
representative AASHTO LRFD 5.9.3.4.5 design estimate.  For Precast Segmental
Crossbeams, PTLOSS4B1 partitions the accepted post-grouting material response
through explicit construction-schedule intervals.  It remains a source-partial
QA route until stage stress redistribution, later-load Δfcd, and a time-resolved
relaxation source are implemented.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    canonical_section_definitions,
    definition_map,
    section_property_record,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    canonical_tendon_system_rows,
)
from concrete_pmm_pro.geometry.summary import to_shapely_polygon

AASHTO_TIME_DEPENDENT_BASIS = (
    "AASHTO LRFD 2020 5.4.2.3 and 5.9.3.4; post-tensioned nonsegmental route 5.9.3.4.5"
)
LIGHTWEIGHT_TD_METHOD = (
    "ONE POST-ES REPRESENTATIVE INTERVAL — CREEP + SHRINKAGE + RELAXATION; 0 STRUCTURAL SOLVES"
)
SEGMENTAL_SCHEDULE_TD_METHOD = (
    "PRECAST SEGMENTAL CONSTRUCTION-SCHEDULE TIME-STEP QA — INCREMENTAL MATERIAL AGING; 0 STRUCTURAL SOLVES"
)
LOW_RELAXATION_STEEL = "Low-relaxation seven-wire strand"
OTHER_PRESTRESSING_STEEL = "Other prestressing steel"
RELAXATION_STEEL_OPTIONS = (LOW_RELAXATION_STEEL, OTHER_PRESTRESSING_STEEL)
MPA_PER_KSI = 6.894757293168361
IN_PER_MM = 1.0 / 25.4


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


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
    return list(dict.fromkeys(str(item).strip() for item in messages if str(item).strip()))


def aashto_ktd(time_days: float, fci_mpa: float) -> float:
    """Return AASHTO 5.4.2.3.2-5 time-development factor.

    The published equation uses f'ci in ksi and elapsed/maturity time in days.
    """

    t = max(_float(time_days), 0.0)
    fci_ksi = max(_float(fci_mpa) / MPA_PER_KSI, 1.0e-9)
    denominator = 12.0 * ((100.0 - 4.0 * fci_ksi) / (fci_ksi + 20.0)) + t
    if denominator <= 0.0:
        return 0.0
    return max(min(t / denominator, 1.0), 0.0)


def aashto_material_factors(
    *, rh_percent: float, v_over_s_mm: float, fci_mpa: float
) -> dict[str, float]:
    """Return AASHTO humidity, size, and strength factors."""

    rh = min(max(_float(rh_percent), 0.0), 100.0)
    v_over_s_in = max(_float(v_over_s_mm), 0.0) * IN_PER_MM
    fci_ksi = max(_float(fci_mpa) / MPA_PER_KSI, 1.0e-9)
    return {
        "rh_percent": rh,
        "v_over_s_in": v_over_s_in,
        "ks": max(1.45 - 0.13 * v_over_s_in, 1.0),
        "khc": 1.56 - 0.008 * rh,
        "khs": 2.00 - 0.014 * rh,
        "kf": 5.0 / (1.0 + fci_ksi),
        "fci_ksi": fci_ksi,
    }


def aashto_creep_coefficient(
    *,
    rh_percent: float,
    v_over_s_mm: float,
    fci_mpa: float,
    load_age_days: float,
    final_age_days: float,
) -> dict[str, float]:
    """Return ψ(tf, ti) using elapsed time after load application.

    AASHTO defines ``t`` in Eq. 5.4.2.3.2-5 as the concrete maturity between
    load application and the time considered; ``ti`` is the age at loading.
    """

    ti = max(_float(load_age_days), 0.01)
    tf = max(_float(final_age_days), ti)
    elapsed = max(tf - ti, 0.0)
    factors = aashto_material_factors(
        rh_percent=rh_percent, v_over_s_mm=v_over_s_mm, fci_mpa=fci_mpa
    )
    ktd = aashto_ktd(elapsed, fci_mpa)
    psi = (
        1.9
        * factors["ks"]
        * factors["khc"]
        * factors["kf"]
        * ktd
        * ti ** (-0.118)
    )
    return {
        **factors,
        "load_age_days": ti,
        "final_age_days": tf,
        "elapsed_days": elapsed,
        "ktd_creep": ktd,
        "psi": max(psi, 0.0),
    }


def aashto_incremental_shrinkage_strain(
    *,
    rh_percent: float,
    v_over_s_mm: float,
    fci_mpa: float,
    curing_end_age_days: float,
    interval_start_age_days: float,
    final_age_days: float,
) -> dict[str, float]:
    """Return shrinkage strain increment over the adopted post-ES interval.

    AASHTO shrinkage maturity is measured from end of curing.  The incremental
    strain is therefore based on the difference in ktd between the final and
    interval-start maturities, not a copied project-specific lump sum.
    """

    curing_end = max(_float(curing_end_age_days), 0.0)
    start = max(_float(interval_start_age_days), curing_end)
    final = max(_float(final_age_days), start)
    start_maturity = max(start - curing_end, 0.0)
    final_maturity = max(final - curing_end, start_maturity)
    factors = aashto_material_factors(
        rh_percent=rh_percent, v_over_s_mm=v_over_s_mm, fci_mpa=fci_mpa
    )
    ktd_start = aashto_ktd(start_maturity, fci_mpa)
    ktd_final = aashto_ktd(final_maturity, fci_mpa)
    delta_ktd = max(ktd_final - ktd_start, 0.0)
    strain = factors["ks"] * factors["khs"] * factors["kf"] * delta_ktd * 0.48e-3
    return {
        **factors,
        "curing_end_age_days": curing_end,
        "interval_start_age_days": start,
        "final_age_days": final,
        "start_maturity_days": start_maturity,
        "final_maturity_days": final_maturity,
        "ktd_shrinkage_start": ktd_start,
        "ktd_shrinkage_final": ktd_final,
        "delta_ktd_shrinkage": delta_ktd,
        "shrinkage_strain": max(strain, 0.0),
    }


def _segmental_schedule_source(
    *,
    stressing_age_days: float,
    grout_age_days: float,
    falsework_removal_age_days: float,
    permanent_load_age_days: float,
    final_age_days: float,
) -> dict[str, Any]:
    """Return a validated member-level construction schedule.

    Ages are concrete ages in days.  Equal-age events are permitted because
    stressing, grouting, and falsework operations may be specified on the same
    day in a design schedule.  The current bonded route begins at grouting.
    """

    ti = _float(stressing_age_days)
    tg = _float(grout_age_days)
    tr = _float(falsework_removal_age_days)
    tp = _float(permanent_load_age_days)
    tf = _float(final_age_days)
    issues: list[str] = []
    if ti <= 0.0:
        issues.append("Tendon stressing age ti must be positive.")
    if tg < ti:
        issues.append("Tendon grouting age tg must not precede stressing age ti.")
    if tr < tg:
        issues.append("Falsework removal age tr must not precede tendon grouting age tg.")
    if tp < tr:
        issues.append("Later permanent-load age tp must not precede falsework removal age tr.")
    if tf <= tp:
        issues.append("Final age tf must be greater than later permanent-load age tp.")
    events = [
        {
            "Event": "Tendon stressing",
            "Symbol": "ti",
            "Age (days)": ti,
            "Calculation role": "Post-ES force and fcgp source",
        },
        {
            "Event": "Tendon grouting",
            "Symbol": "tg",
            "Age (days)": tg,
            "Calculation role": "Start of bonded time-dependent route",
        },
        {
            "Event": "Falsework removal",
            "Symbol": "tr",
            "Age (days)": tr,
            "Calculation role": "Schedule partition; stress redistribution not yet solved",
        },
        {
            "Event": "Later permanent load",
            "Symbol": "tp",
            "Age (days)": tp,
            "Calculation role": "Schedule partition; Δfcd source not yet implemented",
        },
        {
            "Event": "Final time",
            "Symbol": "tf",
            "Age (days)": tf,
            "Calculation role": "End of adopted loss interval",
        },
    ]
    return {
        "ready": not issues,
        "issues": _dedupe(issues),
        "events": events,
        "stressing_age_days": ti,
        "grout_age_days": tg,
        "falsework_removal_age_days": tr,
        "permanent_load_age_days": tp,
        "final_age_days": tf,
        "immediate_grout": abs(tg - ti) <= 1.0e-9,
    }


def _segmental_time_step_rows(
    *,
    schedule: Mapping[str, Any],
    rh_percent: float,
    v_over_s_mm: float,
    fci_mpa: float,
    curing_end_age_days: float,
    ep_mpa: float,
    eci_mpa: float,
    fcgp_mpa: float,
    kdf: float,
    relaxation_loss_mpa: float,
) -> dict[str, Any]:
    """Partition post-grouting creep/shrinkage into schedule intervals.

    The same accepted Kdf is used for every increment so the interval sum
    closes exactly to the corresponding post-grouting component total.  This
    is a material-aging time-step audit, not a stage structural analysis.
    """

    if not schedule.get("ready"):
        return {"ready": False, "issues": list(schedule.get("issues") or [])}
    ti = _float(schedule.get("stressing_age_days"))
    tg = _float(schedule.get("grout_age_days"))
    tr = _float(schedule.get("falsework_removal_age_days"))
    tp = _float(schedule.get("permanent_load_age_days"))
    tf = _float(schedule.get("final_age_days"))
    boundaries = [
        ("Post-grouting → falsework removal", tg, tr),
        ("Falsework removal → later permanent load", tr, tp),
        ("Later permanent load → final time", tp, tf),
    ]

    def _psi_at(age: float) -> float:
        return _float(
            aashto_creep_coefficient(
                rh_percent=rh_percent,
                v_over_s_mm=v_over_s_mm,
                fci_mpa=fci_mpa,
                load_age_days=ti,
                final_age_days=max(age, ti),
            ).get("psi")
        )

    def _shrinkage_between(start: float, end: float) -> float:
        return _float(
            aashto_incremental_shrinkage_strain(
                rh_percent=rh_percent,
                v_over_s_mm=v_over_s_mm,
                fci_mpa=fci_mpa,
                curing_end_age_days=curing_end_age_days,
                interval_start_age_days=start,
                final_age_days=end,
            ).get("shrinkage_strain")
        )

    rows: list[dict[str, Any]] = []
    cumulative_creep = 0.0
    cumulative_shrinkage = 0.0
    cumulative_relaxation = 0.0
    for index, (label, start, end) in enumerate(boundaries, start=1):
        psi_start = _psi_at(start)
        psi_end = _psi_at(end)
        delta_psi = max(psi_end - psi_start, 0.0)
        shrinkage_strain = _shrinkage_between(start, end)
        creep_increment = (
            (_float(ep_mpa) / _float(eci_mpa))
            * max(_float(fcgp_mpa), 0.0)
            * delta_psi
            * max(_float(kdf), 0.0)
            if _float(eci_mpa) > 0.0
            else 0.0
        )
        shrinkage_increment = (
            shrinkage_strain * max(_float(ep_mpa), 0.0) * max(_float(kdf), 0.0)
        )
        relaxation_increment = (
            max(_float(relaxation_loss_mpa), 0.0) if index == len(boundaries) else 0.0
        )
        cumulative_creep += creep_increment
        cumulative_shrinkage += shrinkage_increment
        cumulative_relaxation += relaxation_increment
        subtotal = creep_increment + shrinkage_increment + relaxation_increment
        rows.append(
            {
                "Step": index,
                "Interval": label,
                "t start (days)": start,
                "t end (days)": end,
                "Duration (days)": max(end - start, 0.0),
                "Δψ": delta_psi,
                "Creep increment (MPa)": creep_increment,
                "Δεsh": shrinkage_strain,
                "Shrinkage increment (MPa)": shrinkage_increment,
                "Relaxation increment (MPa)": relaxation_increment,
                "TD increment (MPa)": subtotal,
                "Cumulative TD (MPa)": cumulative_creep
                + cumulative_shrinkage
                + cumulative_relaxation,
            }
        )
    return {
        "ready": True,
        "issues": [],
        "rows": rows,
        "interval_count": len(rows),
        "creep_loss_mpa": cumulative_creep,
        "shrinkage_loss_mpa": cumulative_shrinkage,
        "relaxation_loss_mpa": cumulative_relaxation,
        "time_dependent_loss_mpa": cumulative_creep
        + cumulative_shrinkage
        + cumulative_relaxation,
        "pre_grouting_interval_days": max(tg - ti, 0.0),
        "basis": (
            "Creep and shrinkage are accumulated incrementally between explicit schedule events. "
            "Falsework removal and later permanent-load events currently partition material aging only; "
            "they do not change the structural stress source. Relaxation is retained as one final AASHTO R2 term."
        ),
    }


def crossbeam_drying_geometry(
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    inner_perimeter_factor: float,
) -> dict[str, Any]:
    """Return length-weighted Crossbeam V/S using exposed longitudinal faces.

    Member end faces are intentionally excluded from this prismatic-member
    idealization.  Interior void perimeter is multiplied by the explicit user
    factor (0, 0.5, or 1.0 are the normal choices).
    """

    definitions = canonical_section_definitions(section_definitions)
    by_id = definition_map(definitions)
    factor = min(max(_float(inner_perimeter_factor), 0.0), 1.0)
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    total_volume_m3 = 0.0
    total_surface_m2 = 0.0
    covered_length_m = 0.0
    for index, source in enumerate(_records(segment_rows)):
        start = _float(source.get("x_start_m", source.get("s_start (m)")))
        end = _float(source.get("x_end_m", source.get("s_end (m)")))
        seg_length = max(end - start, 0.0)
        section_id = str(source.get("Section ID") or "").strip()
        definition = by_id.get(section_id)
        if seg_length <= 0.0:
            issues.append(f"Segment {source.get('Segment') or index + 1}: length must be positive.")
            continue
        if definition is None:
            issues.append(
                f"Segment {source.get('Segment') or index + 1}: unknown Section ID {section_id or '(blank)'}."
            )
            continue
        try:
            polygon = to_shapely_polygon(build_geometry_for_definition(definition))
            area_mm2 = float(polygon.area)
            outer_mm = float(polygon.exterior.length)
            inner_mm = sum(float(ring.length) for ring in polygon.interiors)
        except Exception as exc:
            issues.append(f"Section {section_id}: drying geometry could not be resolved: {exc}")
            continue
        exposed_mm = outer_mm + factor * inner_mm
        local_v_over_s_mm = area_mm2 / exposed_mm if exposed_mm > 0.0 else None
        local_v_over_s_in = (
            local_v_over_s_mm * IN_PER_MM if local_v_over_s_mm is not None else None
        )
        local_ks = (
            max(1.45 - 0.13 * local_v_over_s_in, 1.0)
            if local_v_over_s_in is not None
            else None
        )
        volume_m3 = area_mm2 * 1.0e-6 * seg_length
        surface_m2 = exposed_mm * 1.0e-3 * seg_length
        total_volume_m3 += volume_m3
        total_surface_m2 += surface_m2
        covered_length_m += seg_length
        rows.append(
            {
                "Segment": str(source.get("Segment") or f"S{index + 1}"),
                "s start (m)": start,
                "s end (m)": end,
                "Length (m)": seg_length,
                "Section ID": section_id,
                "Section role": str(definition.get("Section role") or ""),
                "Area (m²)": area_mm2 * 1.0e-6,
                "Outer perimeter (m)": outer_mm * 1.0e-3,
                "Inner perimeter (m)": inner_mm * 1.0e-3,
                "Interior exposure factor": factor,
                "Adopted exposed perimeter (m)": exposed_mm * 1.0e-3,
                "Local V/S (mm)": local_v_over_s_mm,
                "Local V/S (in.)": local_v_over_s_in,
                "Local ks": local_ks,
                "Concrete volume (m³)": volume_m3,
                "Drying surface (m²)": surface_m2,
            }
        )
    target_length = max(_float(length_m), 0.0)
    if target_length > 0.0 and abs(covered_length_m - target_length) > 1.0e-6:
        issues.append(
            f"Segment coverage is {covered_length_m:.6g} m but Crossbeam length is {target_length:.6g} m."
        )
    v_over_s_m = total_volume_m3 / total_surface_m2 if total_surface_m2 > 0.0 else None
    section_groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("Section ID") or ""), str(row.get("Section role") or ""))
        grouped = section_groups.setdefault(
            key,
            {
                "Section ID": key[0],
                "Section role": key[1],
                "Total length (m)": 0.0,
                "Concrete volume (m³)": 0.0,
                "Drying surface (m²)": 0.0,
                "Area (m²)": row.get("Area (m²)"),
                "Outer perimeter (m)": row.get("Outer perimeter (m)"),
                "Inner perimeter (m)": row.get("Inner perimeter (m)"),
                "Interior exposure factor": factor,
                "Adopted exposed perimeter (m)": row.get("Adopted exposed perimeter (m)"),
            },
        )
        grouped["Total length (m)"] += _float(row.get("Length (m)"))
        grouped["Concrete volume (m³)"] += _float(row.get("Concrete volume (m³)"))
        grouped["Drying surface (m²)"] += _float(row.get("Drying surface (m²)"))
    section_summary_rows: list[dict[str, Any]] = []
    for grouped in section_groups.values():
        local_m = (
            _float(grouped.get("Concrete volume (m³)"))
            / _float(grouped.get("Drying surface (m²)"))
            if _float(grouped.get("Drying surface (m²)")) > 0.0
            else None
        )
        local_in = local_m * 1000.0 * IN_PER_MM if local_m is not None else None
        grouped["Local V/S (mm)"] = local_m * 1000.0 if local_m is not None else None
        grouped["Local V/S (in.)"] = local_in
        grouped["Local ks"] = max(1.45 - 0.13 * local_in, 1.0) if local_in is not None else None
        grouped["Volume share (%)"] = (
            100.0 * _float(grouped.get("Concrete volume (m³)")) / total_volume_m3
            if total_volume_m3 > 0.0
            else None
        )
        grouped["Drying-surface share (%)"] = (
            100.0 * _float(grouped.get("Drying surface (m²)")) / total_surface_m2
            if total_surface_m2 > 0.0
            else None
        )
        section_summary_rows.append(grouped)
    section_summary_rows.sort(key=lambda row: (str(row.get("Section role")), str(row.get("Section ID"))))
    local_values_in = [
        _float(row.get("Local V/S (in.)"))
        for row in section_summary_rows
        if row.get("Local V/S (in.)") is not None
    ]
    return {
        "ready": bool(rows) and not issues and v_over_s_m is not None,
        "issues": _dedupe(issues),
        "rows": rows,
        "section_summary_rows": section_summary_rows,
        "inner_perimeter_factor": factor,
        "covered_length_m": covered_length_m,
        "total_volume_m3": total_volume_m3,
        "total_drying_surface_m2": total_surface_m2,
        "v_over_s_m": v_over_s_m,
        "v_over_s_mm": None if v_over_s_m is None else v_over_s_m * 1000.0,
        "v_over_s_in": None if v_over_s_m is None else v_over_s_m * 1000.0 * IN_PER_MM,
        "local_v_over_s_min_in": min(local_values_in) if local_values_in else None,
        "local_v_over_s_max_in": max(local_values_in) if local_values_in else None,
        "h0_m": None if v_over_s_m is None else 2.0 * v_over_s_m,
        "basis": (
            "Member-equivalent V/S = Σ(AiLi) / Σ(udry,iLi) using exposed longitudinal faces; "
            "member end faces excluded. Local Section/Zone V/S values remain visible for audit."
        ),
        "formula": "Σ(AiLi) / Σ(udry,iLi)",
    }


def _average_after_es_stress(after_es_station_rows: Any, system_rows: Any) -> dict[str, Any]:
    active = [
        row for row in canonical_tendon_system_rows(system_rows) if bool(row.get("Active", True))
    ]
    system_by_id = {str(row.get("Tendon ID") or ""): row for row in active}
    station_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in _records(after_es_station_rows):
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id:
            station_by_id.setdefault(tendon_id, []).append(row)
    tendon_rows: list[dict[str, Any]] = []
    issues: list[str] = []
    area_sum = 0.0
    weighted_stress = 0.0
    weighted_fpu = 0.0
    for tendon_id, system_row in system_by_id.items():
        aps = max(
            _float(system_row.get("Strands")) * _float(system_row.get("Aps/strand mm²")),
            0.0,
        )
        fpu = max(_float(system_row.get("fpu MPa")), 0.0)
        points = sorted(
            station_by_id.get(tendon_id, []), key=lambda row: _float(row.get("s (m)"))
        )
        valid = [
            (_float(row.get("s (m)")), _float(row.get("Stress after ES (MPa)")))
            for row in points
            if row.get("Stress after ES (MPa)") is not None
        ]
        if aps <= 0.0 or fpu <= 0.0 or not valid:
            issues.append(f"{tendon_id}: complete post-ES stress, Aps, and fpu sources are required.")
            continue
        if len(valid) == 1:
            average = valid[0][1]
        else:
            span = valid[-1][0] - valid[0][0]
            integral = sum(
                0.5 * (f0 + f1) * (s1 - s0)
                for (s0, f0), (s1, f1) in zip(valid, valid[1:])
            )
            average = integral / span if span > 0.0 else sum(value for _s, value in valid) / len(valid)
        area_sum += aps
        weighted_stress += aps * average
        weighted_fpu += aps * fpu
        tendon_rows.append(
            {
                "Tendon": tendon_id,
                "Aps (mm²)": aps,
                "Length-average stress after ES (MPa)": average,
                "fpu (MPa)": fpu,
                "fpy adopted = 0.90 fpu (MPa)": 0.90 * fpu,
                "Stations": len(valid),
            }
        )
    return {
        "ready": bool(tendon_rows) and not issues and area_sum > 0.0,
        "issues": _dedupe(issues),
        "rows": tendon_rows,
        "aps_total_mm2": area_sum,
        "fpt_mpa": weighted_stress / area_sum if area_sum > 0.0 else None,
        "fpu_mpa": weighted_fpu / area_sum if area_sum > 0.0 else None,
        "fpy_mpa": 0.90 * weighted_fpu / area_sum if area_sum > 0.0 else None,
    }


def _representative_section_source(
    *, lightweight_es_result: Mapping[str, Any], section_definitions: Any
) -> dict[str, Any]:
    fcgp_route = dict(lightweight_es_result.get("fcgp_route") or {})
    governing = fcgp_route.get("governing_row")
    if not isinstance(governing, Mapping):
        return {
            "ready": False,
            "issues": [
                "A representative governing section is required; this PTLOSS4A route currently supports bonded-after-grouting Tendons only."
            ],
        }
    section_id = str(governing.get("Section ID") or "").strip()
    definition = definition_map(section_definitions).get(section_id)
    if definition is None:
        return {"ready": False, "issues": [f"Governing Section ID {section_id or '(blank)'} is unavailable."]}
    properties = section_property_record(definition)
    area = _float(properties.get("Area mm²"))
    inertia = _float(properties.get("Ix mm4"))
    eccentricity = abs(_float(governing.get("y_p below section centroid (mm)")))
    issues: list[str] = []
    if area <= 0.0:
        issues.append(f"Section {section_id}: gross concrete area is unavailable.")
    if inertia <= 0.0:
        issues.append(f"Section {section_id}: gross Ix is unavailable.")
    return {
        "ready": not issues,
        "issues": issues,
        "section_id": section_id,
        "evaluation_role": str(governing.get("Evaluation role") or ""),
        "station_m": _float(governing.get("s (m)")),
        "area_mm2": area,
        "inertia_mm4": inertia,
        "eccentricity_mm": eccentricity,
        "governing_row": dict(governing),
    }


def run_crossbeam_lightweight_time_dependent_loss(
    *,
    lightweight_es_result: Mapping[str, Any] | None,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    system_rows: Any,
    construction_method: str,
    rh_percent: float,
    load_age_days: float,
    curing_end_age_days: float,
    final_age_days: float,
    grout_age_days: float | None = None,
    falsework_removal_age_days: float | None = None,
    permanent_load_age_days: float | None = None,
    inner_perimeter_factor: float,
    relaxation_steel_class: str,
    ep_mpa: float,
    eci_mpa: float,
    fci_mpa: float,
) -> dict[str, Any]:
    """Calculate a source-gated, arithmetic-only time-dependent loss preview."""

    es_result = dict(lightweight_es_result or {})
    issues: list[str] = []
    if not es_result.get("ready"):
        issues.append("A CURRENT, source-derived Lightweight Elastic Shortening result is required.")
    if str(es_result.get("bond_state") or "") != TENDON_BOND_STATE_BONDED:
        issues.append(
            "PTLOSS4A currently supports Internal Tendons that are bonded after grouting; permanently unbonded/mixed systems require a separate route."
        )
    ti = _float(load_age_days)
    curing_end = _float(curing_end_age_days)
    tf = _float(final_age_days)
    tg = _float(grout_age_days, ti)
    tr = _float(falsework_removal_age_days, max(tg, ti))
    tp = _float(permanent_load_age_days, max(tr, tg, ti))
    if ti <= 0.0:
        issues.append("Time-dependent load/prestress application age ti must be positive.")
    if curing_end < 0.0 or curing_end > ti:
        issues.append("End-of-curing age must be nonnegative and not exceed ti.")
    if tf <= ti:
        issues.append("Final age tf must be greater than ti.")
    if not (0.0 < _float(rh_percent) <= 100.0):
        issues.append("Relative humidity must be greater than 0 and not exceed 100 percent.")
    if _float(ep_mpa) <= 0.0 or _float(eci_mpa) <= 0.0 or _float(fci_mpa) <= 0.0:
        issues.append("Positive Ep, Eci, and f'ci sources are required.")

    drying = crossbeam_drying_geometry(
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
        inner_perimeter_factor=inner_perimeter_factor,
    )
    if not drying.get("ready"):
        issues.extend(drying.get("issues") or ["Crossbeam drying geometry is not ready."])
    steel = _average_after_es_stress(es_result.get("after_es_station_rows"), system_rows)
    if not steel.get("ready"):
        issues.extend(steel.get("issues") or ["Post-ES tendon stress source is not ready."])
    section = _representative_section_source(
        lightweight_es_result=es_result, section_definitions=section_definitions
    )
    if not section.get("ready"):
        issues.extend(section.get("issues") or ["Representative section source is not ready."])

    if issues:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "adoptable": False,
            "method": LIGHTWEIGHT_TD_METHOD,
            "basis": AASHTO_TIME_DEPENDENT_BASIS,
            "solve_count": 0,
            "issues": _dedupe(issues),
            "drying_geometry": drying,
            "steel_source": steel,
            "section_source": section,
        }

    method = normalize_construction_method(construction_method)
    segmental = method == CONSTRUCTION_METHOD_PRECAST
    schedule = _segmental_schedule_source(
        stressing_age_days=ti,
        grout_age_days=tg,
        falsework_removal_age_days=tr,
        permanent_load_age_days=tp,
        final_age_days=tf,
    )
    if segmental and not schedule.get("ready"):
        issues.extend(schedule.get("issues") or ["Precast Segmental construction schedule is not ready."])
    if issues:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "adoptable": False,
            "method": SEGMENTAL_SCHEDULE_TD_METHOD if segmental else LIGHTWEIGHT_TD_METHOD,
            "basis": AASHTO_TIME_DEPENDENT_BASIS,
            "solve_count": 0,
            "issues": _dedupe(issues),
            "drying_geometry": drying,
            "steel_source": steel,
            "section_source": section,
            "schedule_source": schedule,
        }

    v_over_s_mm = _float(drying.get("v_over_s_mm"))
    creep_interval_start = tg if segmental else ti
    creep_full = aashto_creep_coefficient(
        rh_percent=rh_percent,
        v_over_s_mm=v_over_s_mm,
        fci_mpa=fci_mpa,
        load_age_days=ti,
        final_age_days=tf,
    )
    creep_at_start = aashto_creep_coefficient(
        rh_percent=rh_percent,
        v_over_s_mm=v_over_s_mm,
        fci_mpa=fci_mpa,
        load_age_days=ti,
        final_age_days=creep_interval_start,
    )
    creep = {
        **dict(creep_full),
        "interval_start_age_days": creep_interval_start,
        "psi_full_from_stressing": _float(creep_full.get("psi")),
        "psi_at_interval_start": _float(creep_at_start.get("psi")),
        "psi": max(
            _float(creep_full.get("psi")) - _float(creep_at_start.get("psi")),
            0.0,
        ),
    }
    shrinkage = aashto_incremental_shrinkage_strain(
        rh_percent=rh_percent,
        v_over_s_mm=v_over_s_mm,
        fci_mpa=fci_mpa,
        curing_end_age_days=curing_end,
        interval_start_age_days=creep_interval_start,
        final_age_days=tf,
    )
    aps = _float(steel.get("aps_total_mm2"))
    area = _float(section.get("area_mm2"))
    inertia = _float(section.get("inertia_mm4"))
    eccentricity = _float(section.get("eccentricity_mm"))
    interaction_term = 1.0 + area * eccentricity * eccentricity / inertia
    denominator = (
        1.0
        + (_float(ep_mpa) * aps / (_float(eci_mpa) * area))
        * interaction_term
        * (1.0 + 0.7 * _float(creep.get("psi")))
    )
    kdf = 1.0 / denominator if denominator > 0.0 else 0.0
    fcgp = max(_float(es_result.get("fcgp_mpa")), 0.0)
    creep_loss = (_float(ep_mpa) / _float(eci_mpa)) * fcgp * _float(creep.get("psi")) * kdf
    shrinkage_loss = _float(shrinkage.get("shrinkage_strain")) * _float(ep_mpa) * kdf

    steel_class = (
        relaxation_steel_class
        if relaxation_steel_class in RELAXATION_STEEL_OPTIONS
        else LOW_RELAXATION_STEEL
    )
    kl = 30.0 if steel_class == LOW_RELAXATION_STEEL else 7.0
    fpt = max(_float(steel.get("fpt_mpa")), 0.0)
    fpy = max(_float(steel.get("fpy_mpa")), 0.0)
    fpt_for_equation = max(fpt, 0.55 * fpy)
    relaxation_loss = (
        fpt_for_equation / kl * max(fpt_for_equation / fpy - 0.55, 0.0)
        if fpy > 0.0
        else 0.0
    )
    total = max(creep_loss, 0.0) + max(shrinkage_loss, 0.0) + max(relaxation_loss, 0.0)
    direct_component_totals = {
        "creep_loss_mpa": max(creep_loss, 0.0),
        "shrinkage_loss_mpa": max(shrinkage_loss, 0.0),
        "relaxation_loss_mpa": max(relaxation_loss, 0.0),
        "time_dependent_loss_mpa": total,
    }
    schedule_time_step = None
    if segmental:
        schedule_time_step = _segmental_time_step_rows(
            schedule=schedule,
            rh_percent=rh_percent,
            v_over_s_mm=v_over_s_mm,
            fci_mpa=fci_mpa,
            curing_end_age_days=curing_end,
            ep_mpa=ep_mpa,
            eci_mpa=eci_mpa,
            fcgp_mpa=fcgp,
            kdf=kdf,
            relaxation_loss_mpa=relaxation_loss,
        )
        creep_loss = _float(schedule_time_step.get("creep_loss_mpa"), creep_loss)
        shrinkage_loss = _float(
            schedule_time_step.get("shrinkage_loss_mpa"), shrinkage_loss
        )
        relaxation_loss = _float(
            schedule_time_step.get("relaxation_loss_mpa"), relaxation_loss
        )
        total = _float(schedule_time_step.get("time_dependent_loss_mpa"), total)
        schedule_time_step["closure"] = {
            "creep_residual_mpa": creep_loss
            - direct_component_totals["creep_loss_mpa"],
            "shrinkage_residual_mpa": shrinkage_loss
            - direct_component_totals["shrinkage_loss_mpa"],
            "relaxation_residual_mpa": relaxation_loss
            - direct_component_totals["relaxation_loss_mpa"],
            "total_residual_mpa": total
            - direct_component_totals["time_dependent_loss_mpa"],
        }
    review_notes: list[str] = []
    calibration_advisories: list[str] = []
    blocking_review_notes: list[str] = []
    v_over_s_outside_development = _float(drying.get("v_over_s_in")) > 6.0
    if v_over_s_outside_development:
        calibration_advisories.append(
            "Member-equivalent V/S exceeds the 6.0-in. range considered in developing the AASHTO Commentary size-effect relationships. "
            "The Specification lower bound ks = 1.0 is applied; engineering review or project-specific material data is recommended "
            "when accurate intermediate-age behavior is important."
        )
    if segmental:
        if not schedule.get("immediate_grout"):
            blocking_review_notes.append(
                "The current bonded schedule route excludes the pre-grouting interval; set tg = ti for immediate grouting or provide a separate pre-grouting loss model."
            )
        blocking_review_notes.extend(
            [
                "Construction schedule intervals are now explicit, but falsework removal and later permanent-load events only partition material aging; stage stress redistribution and Δfcd are not yet included.",
                "Relaxation is retained as one final AASHTO R2 interval term because the current source does not provide a time-development law for distributing relaxation among construction steps.",
            ]
        )
    review_notes.extend(calibration_advisories)
    review_notes.extend(blocking_review_notes)
    adoptable = not segmental
    status = (
        "DESIGN ESTIMATE READY"
        if adoptable
        else "SCHEDULE TIME-STEP QA READY — FINAL ADOPTION BLOCKED"
    )
    return {
        "status": status,
        "ready": True,
        "adoptable": adoptable,
        "review_notes": review_notes,
        "calibration_advisories": calibration_advisories,
        "blocking_review_notes": blocking_review_notes,
        "v_over_s_commentary_advisory": v_over_s_outside_development,
        "method": SEGMENTAL_SCHEDULE_TD_METHOD if segmental else LIGHTWEIGHT_TD_METHOD,
        "basis": AASHTO_TIME_DEPENDENT_BASIS,
        "solve_count": 0,
        "issues": [],
        "construction_method": method,
        "route": (
            "PRECAST SEGMENTAL — CONSTRUCTION-SCHEDULE TIME-STEP QA"
            if segmental
            else "CAST-IN-PLACE NONSEGMENTAL — AASHTO 5.9.3.4.5 REPRESENTATIVE DESIGN ESTIMATE"
        ),
        "route_note": (
            "The explicit schedule is evaluated incrementally with zero structural solves. Final adoption remains blocked until construction-stage stress redistribution, later-load Δfcd, and time-resolved relaxation are sourced."
            if segmental
            else "For post-tensioned members after grouting, the pre-grouting/initial interval term is taken as zero in accordance with AASHTO 5.9.3.4.5."
        ),
        "inputs": {
            "rh_percent": _float(rh_percent),
            "load_age_days": ti,
            "curing_end_age_days": curing_end,
            "final_age_days": tf,
            "grout_age_days": tg,
            "falsework_removal_age_days": tr,
            "permanent_load_age_days": tp,
            "inner_perimeter_factor": _float(inner_perimeter_factor),
            "relaxation_steel_class": steel_class,
            "ep_mpa": _float(ep_mpa),
            "eci_mpa": _float(eci_mpa),
            "fci_mpa": _float(fci_mpa),
        },
        "drying_geometry": drying,
        "steel_source": steel,
        "section_source": section,
        "schedule_source": schedule,
        "schedule_time_step": schedule_time_step,
        "creep_source": creep,
        "shrinkage_source": shrinkage,
        "interaction": {
            "Aps_total_mm2": aps,
            "Ac_mm2": area,
            "Ic_mm4": inertia,
            "epc_mm": eccentricity,
            "section_term": interaction_term,
            "Kdf": kdf,
        },
        "relaxation_source": {
            "steel_class": steel_class,
            "KL": kl,
            "fpt_mpa": fpt,
            "fpy_mpa": fpy,
            "fpt_for_equation_mpa": fpt_for_equation,
            "equation": "ΔfpR2 = ΔfpR1 = fpt/KL × (fpt/fpy − 0.55)",
        },
        "creep_loss_mpa": max(creep_loss, 0.0),
        "shrinkage_loss_mpa": max(shrinkage_loss, 0.0),
        "relaxation_loss_mpa": max(relaxation_loss, 0.0),
        "time_dependent_loss_mpa": total,
        "handoff_status": (
            "SCHEDULE QA ONLY — EFFECTIVE PRESTRESS ASSEMBLY LOCKED"
            if segmental
            else "COMPONENT READY — EFFECTIVE PRESTRESS ASSEMBLY LOCKED"
        ),
        "scope_guard": (
            "PTLOSS4B1 evaluates explicit construction-schedule material-aging increments with zero structural solves. It excludes construction-stage stress redistribution, later permanent-load Δfcd, time-resolved relaxation, measured material models, and Pe/Pe_eff assembly."
        ),
    }

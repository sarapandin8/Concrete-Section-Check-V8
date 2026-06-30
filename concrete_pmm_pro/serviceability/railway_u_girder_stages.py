"""Railway U-Girder staged SLS stress preview helpers.

SLS.RAIL.UGIRDER1 provides a guarded, station-based preview for the user-defined
Railway U-Girder construction sequence:
- Transfer / Lifting / Wet slab casting use one precast web only.
- Service reference uses the full Railway U-Girder basis.

The helper consumes the row-based strand debonding table through the existing
station participation handoff.  It intentionally does not perform transfer-
length force ramping, development length, AASHTO/ACI code certification,
or final end-zone checks.  Later milestones add guarded locked-in and
service-load handoff previews without representing final certified design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd
from shapely.geometry import Polygon

from concrete_pmm_pro.core.models import Point2D, SectionGeometry
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.serviceability.girder_prestress import run_girder_prestress_stress_effect
from concrete_pmm_pro.serviceability.girder_code_limits import (
    STAGE_DECK_CASTING,
    STAGE_FINAL_SERVICE,
    STAGE_TRANSFER,
    StressLimitInputRow,
    default_girder_sls_limit_profile,
    run_girder_service_stress_limit_check,
)
from concrete_pmm_pro.serviceability.girder_prestress_station import (
    evaluate_girder_prestress_station,
    station_candidates_from_debonding,
)
from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    default_sls_station_grid,
    simple_span_udl_moment_kNm,
)
from concrete_pmm_pro.serviceability.girder_stress import (
    GirderSectionBasis,
    make_girder_basis_from_gross_summary,
    run_basic_girder_service_stress,
)

DEFAULT_RAILWAY_UGIRDER_STAGE_STATIONS = (0.0, 0.2, 0.5, 0.8, 1.0)
RAILWAY_UGIRDER_SLS_PREVIEW_COLUMNS = [
    "Stage",
    "Station x (m)",
    "Section basis",
    "Auto load w (kN/m)",
    "Auto Mx (kN-m)",
    "Pe stage (kN)",
    "yps eff (mm from bottom)",
    "Top total (MPa)",
    "Bottom total (MPa)",
    "Max compression (MPa)",
    "Max tension (MPa)",
    "Effective strands",
    "Active group IDs",
    "Preview note",
]

RAILWAY_UGIRDER_LIFTING_AUDIT_COLUMNS = [
    "Station x (m)",
    "Station type",
    "a/L basis",
    "Lifting point a (m)",
    "Lifting point L-a (m)",
    "Support spacing (m)",
    "Impact factor",
    "Auto load w (kN/m)",
    "Reaction each (kN)",
    "Lifting moment Mx (kN-m)",
    "Effective strands",
    "Pe_transfer (kN)",
    "yps eff (mm from bottom)",
    "Active group IDs",
    "Audit note",
]


RAILWAY_UGIRDER_LOCKED_IN_COLUMNS = [
    "Accumulation step",
    "Station x (m)",
    "Section basis",
    "Load increment w (kN/m)",
    "Moment increment (kN-m)",
    "Pe increment (kN)",
    "Effective strands",
    "Top increment (MPa)",
    "Bottom increment (MPa)",
    "Cumulative top (MPa)",
    "Cumulative bottom (MPa)",
    "Carry-over basis",
    "Preview note",
]

RAILWAY_UGIRDER_SLS_LIMIT_COLUMNS = [
    "Stage",
    "Station x (m)",
    "Section basis",
    "Concrete strength used (MPa)",
    "Limit stage profile",
    "Top total (MPa)",
    "Bottom total (MPa)",
    "Top status",
    "Bottom status",
    "Overall status",
    "Max utilization",
    "Limit note",
]


RAILWAY_UGIRDER_SERVICE_LOAD_COLUMNS = [
    "Load Case",
    "Station x (m)",
    "Section basis",
    "Pu (kN)",
    "Mux (kN-m)",
    "Pe_final (kN)",
    "yps eff (mm from bottom)",
    "Effective strands",
    "Load top (MPa)",
    "Load bottom (MPa)",
    "Pe top (MPa)",
    "Pe bottom (MPa)",
    "Top total (MPa)",
    "Bottom total (MPa)",
    "Max compression (MPa)",
    "Max tension (MPa)",
    "Active group IDs",
    "Preview note",
]

RAILWAY_UGIRDER_SERVICE_LOAD_LIMIT_COLUMNS = [
    "Load Case",
    "Station x (m)",
    "Section basis",
    "Concrete strength used (MPa)",
    "Limit stage profile",
    "Top total (MPa)",
    "Bottom total (MPa)",
    "Top status",
    "Bottom status",
    "Overall status",
    "Max utilization",
    "Limit note",
]

RAILWAY_UGIRDER_FINAL_SERVICE_COLUMNS = [
    "Load Case",
    "Station x (m)",
    "Section basis",
    "Pu (kN)",
    "Mux (kN-m)",
    "Locked top (MPa)",
    "Locked bottom (MPa)",
    "Service load top (MPa)",
    "Service load bottom (MPa)",
    "Final Pe increment top (MPa)",
    "Final Pe increment bottom (MPa)",
    "Final top (MPa)",
    "Final bottom (MPa)",
    "Max compression (MPa)",
    "Max tension (MPa)",
    "Pe_final increment (kN)",
    "Effective strands",
    "Active group IDs",
    "Preview note",
]

RAILWAY_UGIRDER_SLS_DECISION_SUMMARY_COLUMNS = [
    "Check stage",
    "Decision",
    "Governing source",
    "Governing x / case",
    "Max utilization",
    "Compression (MPa)",
    "Tension (MPa)",
    "Section basis",
    "Review action",
]

RAILWAY_UGIRDER_FINAL_SERVICE_LIMIT_COLUMNS = [
    "Load Case",
    "Station x (m)",
    "Section basis",
    "Concrete strength used (MPa)",
    "Limit stage profile",
    "Final top (MPa)",
    "Final bottom (MPa)",
    "Top status",
    "Bottom status",
    "Overall status",
    "Max utilization",
    "Limit note",
]


@dataclass(frozen=True)
class RailwayUGirderStageQuantities:
    web_area_mm2: float
    slab_area_mm2: float
    full_area_mm2: float
    web_self_weight_kN_m: float
    wet_slab_to_each_web_kN_m: float
    formwork_to_each_web_kN_m: float
    full_u_self_weight_kN_m: float
    projected_slab_width_m: float


@dataclass(frozen=True)
class RailwayUGirderStageBasisSet:
    web_basis: GirderSectionBasis
    full_u_basis: GirderSectionBasis
    quantities: RailwayUGirderStageQuantities


def _float_value(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    return numeric if pd.notna(numeric) else float(default)


def _positive(value: Any, default: float) -> float:
    numeric = _float_value(value, default)
    return numeric if numeric > 0.0 else float(default)


def _point(x: float, y: float) -> Point2D:
    return Point2D(x=float(x), y=float(y))


def railway_u_girder_default_parameter_snapshot() -> dict[str, float]:
    return {
        "width_mm": 5500.0,
        "depth_mm": 1600.0,
        "top_wall_width_mm": 600.0,
        "bottom_side_width_mm": 650.0,
        "h1_step_height_mm": 670.0,
        "h2_bottom_opening_mm": 305.0,
        "h3_floor_side_thickness_mm": 395.0,
        "h4_floor_center_thickness_mm": 450.0,
        "haunch_x_mm": 300.0,
        "haunch_y_mm": 300.0,
        "inner_half_width_mm": 2100.0,
    }


def railway_u_girder_parameter_snapshot_from_geometry(geometry: SectionGeometry | None) -> dict[str, float]:
    """Return Railway U-Girder parameters from geometry metadata with safe defaults."""

    defaults = railway_u_girder_default_parameter_snapshot()
    metadata = getattr(geometry, "metadata", {}) or {}
    params = dict(metadata.get("parameters", {}) or {})
    derived = dict(metadata.get("derived_details", {}) or {})
    if geometry is not None:
        try:
            summary = summarize_geometry(geometry)
            if summary.width_mm:
                defaults["width_mm"] = float(summary.width_mm)
            if summary.depth_mm:
                defaults["depth_mm"] = float(summary.depth_mm)
        except Exception:
            pass
    result = dict(defaults)
    key_map = {
        "width_mm": "width_mm",
        "depth_mm": "depth_mm",
        "top_wall_width_mm": "top_wall_width_mm",
        "bottom_side_width_mm": "bottom_side_width_mm",
        "h1_step_height_mm": "h1_step_height_mm",
        "h2_bottom_opening_mm": "h2_bottom_opening_mm",
        "h3_floor_side_thickness_mm": "h3_floor_side_thickness_mm",
        "h4_floor_center_thickness_mm": "h4_floor_center_thickness_mm",
        "haunch_x_mm": "haunch_x_mm",
        "haunch_y_mm": "haunch_y_mm",
    }
    for out_key, in_key in key_map.items():
        result[out_key] = _positive(params.get(in_key), result[out_key])
    result["inner_half_width_mm"] = _positive(
        derived.get("inner_half_width_mm"),
        max(result["width_mm"] / 2.0 - result["bottom_side_width_mm"], 0.0),
    )
    return result


def _railway_web_right_points_down(params: Mapping[str, float]) -> list[tuple[float, float]]:
    """Return one precast right web polygon in drawing coordinates (y down from top)."""

    depth = float(params["depth_mm"])
    half_width = float(params["width_mm"]) / 2.0
    bottom_side = float(params["bottom_side_width_mm"])
    top_wall = float(params["top_wall_width_mm"])
    h1 = float(params["h1_step_height_mm"])
    inner_half = float(params["inner_half_width_mm"])
    notch = max(bottom_side - top_wall, 0.0)
    upper_outer_half = half_width - notch
    chamfer = 25.0
    return [
        (inner_half + chamfer, 0.0),
        (upper_outer_half - chamfer, 0.0),
        (upper_outer_half, chamfer),
        (upper_outer_half, depth - h1),
        (half_width, depth - h1),
        (half_width, depth - chamfer),
        (half_width - chamfer, depth),
        (inner_half, depth),
        (inner_half, chamfer),
    ]


def railway_u_girder_web_geometry(geometry: SectionGeometry | None = None) -> SectionGeometry:
    """Build the one-web precast section used at transfer/lifting/wet casting.

    The drawing coordinates are converted to the app's section-coordinate
    convention with y measured upward from the bottom fiber.  Only one web is
    returned because transfer, lifting, and wet slab casting are checked per
    precast web.
    """

    params = railway_u_girder_parameter_snapshot_from_geometry(geometry)
    depth = float(params["depth_mm"])
    points = [_point(x, depth - y_down) for x, y_down in _railway_web_right_points_down(params)]
    return SectionGeometry(
        name="Railway U-Girder precast web only",
        outer_polygon=points,
        holes=[],
        metadata={"source": "railway_u_girder_stage_web", "parameters": params},
    )


def railway_u_girder_slab_area_mm2(geometry: SectionGeometry | None = None) -> float:
    params = railway_u_girder_parameter_snapshot_from_geometry(geometry)
    inner_half = params["inner_half_width_mm"]
    floor_underside_y = params["depth_mm"] - params["h2_bottom_opening_mm"]
    floor_side_top_y = floor_underside_y - params["h3_floor_side_thickness_mm"]
    floor_center_top_y = floor_underside_y - params["h4_floor_center_thickness_mm"]
    haunch_start_y = floor_side_top_y - params["haunch_y_mm"]
    slab_points = [
        (-inner_half, haunch_start_y),
        (-(inner_half - params["haunch_x_mm"]), floor_side_top_y),
        (0.0, floor_center_top_y),
        (inner_half - params["haunch_x_mm"], floor_side_top_y),
        (inner_half, haunch_start_y),
        (inner_half, floor_underside_y),
        (-inner_half, floor_underside_y),
    ]
    try:
        return max(float(Polygon(slab_points).area), 0.0)
    except Exception:
        return 0.0


def railway_u_girder_stage_basis_set(
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
) -> RailwayUGirderStageBasisSet:
    settings = dict(settings or {})
    gamma = _positive(settings.get("concrete_unit_weight_kN_m3"), 24.0)
    distribution = min(max(_float_value(settings.get("wet_slab_distribution_each_web"), 0.5), 0.0), 1.0)
    formwork_q = max(_float_value(settings.get("formwork_construction_load_kN_m2"), 2.5), 0.0)
    params = railway_u_girder_parameter_snapshot_from_geometry(geometry)
    web_geometry = railway_u_girder_web_geometry(geometry)
    web_summary = summarize_geometry(web_geometry)
    web_basis = make_girder_basis_from_gross_summary(web_summary)

    if geometry is None:
        full_u_basis = web_basis
        full_area_mm2 = 2.0 * web_summary.area_mm2
    else:
        full_summary = summarize_geometry(geometry)
        full_area_mm2 = float(full_summary.area_mm2)
        full_u_basis = GirderSectionBasis(
            basis_name="composite_transformed",
            area_mm2=float(full_summary.area_mm2),
            centroid_y_from_bottom_mm=float(full_summary.centroid_y_mm - (full_summary.y_min_mm or 0.0)),
            ix_mm4=float(full_summary.ix_nmm4 or web_basis.ix_mm4),
            top_fiber_y_from_bottom_mm=float((full_summary.y_max_mm or 0.0) - (full_summary.y_min_mm or 0.0)),
            bottom_fiber_y_from_bottom_mm=0.0,
            warnings=("Full Railway U-Girder gross basis used as staged-service preview; transformed locked-in behavior is future scope.",),
        )

    slab_area = railway_u_girder_slab_area_mm2(geometry)
    if slab_area <= 0.0 and full_area_mm2 > 2.0 * web_summary.area_mm2:
        slab_area = max(full_area_mm2 - 2.0 * web_summary.area_mm2, 0.0)
    projected_slab_width_m = max(2.0 * float(params["inner_half_width_mm"]) / 1000.0, 0.0)
    quantities = RailwayUGirderStageQuantities(
        web_area_mm2=float(web_summary.area_mm2),
        slab_area_mm2=float(slab_area),
        full_area_mm2=float(full_area_mm2),
        web_self_weight_kN_m=float(web_summary.area_mm2) / 1_000_000.0 * gamma,
        wet_slab_to_each_web_kN_m=float(slab_area) / 1_000_000.0 * gamma * distribution,
        formwork_to_each_web_kN_m=projected_slab_width_m * formwork_q * distribution,
        full_u_self_weight_kN_m=float(full_area_mm2) / 1_000_000.0 * gamma,
        projected_slab_width_m=projected_slab_width_m,
    )
    return RailwayUGirderStageBasisSet(web_basis=web_basis, full_u_basis=full_u_basis, quantities=quantities)


def lifting_udl_moment_kNm(w_kN_m: float, x_m: float, span_length_m: float, lifting_point_ratio: float = 0.20) -> float:
    """Return preview bending moment for a two-point-lift beam under full-length UDL.

    Sagging is positive. Overhang regions are negative. Supports are at a and
    L-a where a = lifting_point_ratio * L.
    """

    L = max(float(span_length_m), 0.001)
    x = min(max(float(x_m), 0.0), L)
    a = min(max(float(lifting_point_ratio), 0.0), 0.49) * L
    w = max(float(w_kN_m), 0.0)
    reaction = w * L / 2.0
    m = -w * x * x / 2.0
    if x >= a:
        m += reaction * (x - a)
    if x >= L - a:
        m += reaction * (x - (L - a))
    return float(m)


def railway_u_girder_stage_station_grid(
    span_length_m: float,
    strand_table: pd.DataFrame | None = None,
    lifting_point_ratio: float = 0.20,
) -> list[float]:
    L = max(float(span_length_m), 0.001)
    a = min(max(float(lifting_point_ratio), 0.0), 0.49) * L
    extra = {0.0, a, L / 2.0, L - a, L}
    try:
        extra.update(station_candidates_from_debonding(strand_table, L))
    except Exception:
        pass
    return default_sls_station_grid(L, extra_stations_m=extra, divisions=20)


def _one_web_strand_table(strand_table: pd.DataFrame | None) -> pd.DataFrame | None:
    if strand_table is None:
        return None
    df = pd.DataFrame(strand_table).copy()
    if df.empty or "Group ID" not in df.columns:
        return df
    mask = df["Group ID"].astype(str).str.strip().str.upper().str.startswith("L ")
    if mask.any():
        return df.loc[mask].reset_index(drop=True)
    return df


def _station_label_for_lifting_audit(*, x: float, span: float, a: float, debond_stations: set[float]) -> str:
    labels: list[str] = []
    tol = max(span, 1.0) * 1.0e-7
    if abs(x) <= tol:
        labels.append("Left end")
    if abs(x - span) <= tol:
        labels.append("Right end")
    if abs(x - a) <= tol:
        labels.append("Lifting point a")
    if abs(x - (span - a)) <= tol:
        labels.append("Lifting point L-a")
    if abs(x - span / 2.0) <= tol:
        labels.append("Midspan")
    if any(abs(x - station) <= tol for station in debond_stations):
        labels.append("Debond transition")
    return " / ".join(labels) if labels else "Station grid"


def railway_u_girder_lifting_stage_audit_dataframe(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    stations_m: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Return the Railway U-Girder lifting a/L and debonding audit table.

    SLS.RAIL.UGIRDER9 is an audit/traceability handoff for the lifting-stage
    stress preview.  It uses the same two-point lifting model, one-web load
    basis, and station-based debonded-strand step availability as the stress
    diagram.  It does not add transfer-length ramping, development-length
    verification, anchorage checks, or any new solver.
    """

    settings = dict(settings or {})
    span = max(float(span_length_m), 0.001)
    lifting_ratio = min(max(_float_value(settings.get("lifting_point_ratio"), 0.20), 0.05), 0.45)
    lifting_factor = max(_float_value(settings.get("lifting_impact_factor"), 1.10), 1.0)
    a = lifting_ratio * span
    support_spacing = max(span - 2.0 * a, 0.0)
    basis_set = railway_u_girder_stage_basis_set(geometry, settings)
    w = basis_set.quantities.web_self_weight_kN_m * lifting_factor
    reaction = w * span / 2.0
    web_strands = _one_web_strand_table(strand_table)
    debond_stations = {
        round(float(x), 6)
        for x in station_candidates_from_debonding(web_strands, span)
        if 0.0 <= float(x) <= span
    }
    station_values = set(debond_stations)
    station_values.update({0.0, round(a, 6), round(span / 2.0, 6), round(span - a, 6), round(span, 6)})
    for x in stations_m or []:
        try:
            station_values.add(round(min(max(float(x), 0.0), span), 6))
        except (TypeError, ValueError):
            continue
    rows: list[dict[str, Any]] = []
    for x in sorted(station_values):
        pe, yps, effective_strands, active_groups = _station_pe(
            web_strands,
            x_m=float(x),
            span_length_m=span,
            pe_source="transfer",
        )
        station_type = _station_label_for_lifting_audit(x=float(x), span=span, a=a, debond_stations=debond_stations)
        if "Debond transition" in station_type:
            note = "Station coincides with a debond termination; effective strands change by step-function preview."
        elif "Lifting point" in station_type:
            note = "Two-point lifting support station from Section Builder a/L input."
        elif "Midspan" in station_type:
            note = "Midspan station included for positive lifting moment reference."
        else:
            note = "Generated station included for lifting stress traceability."
        rows.append(
            {
                "Station x (m)": round(float(x), 6),
                "Station type": station_type,
                "a/L basis": f"a/L={lifting_ratio:.3f}",
                "Lifting point a (m)": a,
                "Lifting point L-a (m)": span - a,
                "Support spacing (m)": support_spacing,
                "Impact factor": lifting_factor,
                "Auto load w (kN/m)": w,
                "Reaction each (kN)": reaction,
                "Lifting moment Mx (kN-m)": lifting_udl_moment_kNm(w, float(x), span, lifting_ratio),
                "Effective strands": effective_strands,
                "Pe_transfer (kN)": pe,
                "yps eff (mm from bottom)": yps,
                "Active group IDs": active_groups,
                "Audit note": note,
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_LIFTING_AUDIT_COLUMNS)


def _station_pe(
    strand_table: pd.DataFrame | None,
    *,
    x_m: float,
    span_length_m: float,
    pe_source: str,
) -> tuple[float, float | None, int, str]:
    if strand_table is None or pd.DataFrame(strand_table).empty:
        return 0.0, None, 0, "No strand layout table"
    station = evaluate_girder_prestress_station(strand_table, x_m=float(x_m), span_length_m=float(span_length_m))
    if pe_source == "transfer":
        pe = float(getattr(station, "pe_transfer_eff_kN", 0.0) or 0.0)
    elif pe_source == "construction":
        pe = float(getattr(station, "pe_construction_eff_kN", 0.0) or 0.0)
    else:
        pe = float(getattr(station, "pe_eff_final_eff_kN", 0.0) or 0.0)
    yps = getattr(station, "yps_eff_mm_from_bottom", None)
    effective_strands = int(getattr(station, "effective_strands", 0) or 0)
    active_groups = str(getattr(station, "active_group_ids", "") or "")
    return pe, (None if yps is None else float(yps)), effective_strands, active_groups


def railway_u_girder_staged_stress_preview_dataframe(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    stations_m: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Return guarded station-based stress preview rows for Railway U-Girder.

    The preview is intentionally stage-local: it reports the elastic stress for
    each stage load and stage Pe on the correct section basis.  It does not
    superimpose locked-in stresses between non-composite and composite bases.
    """

    settings = dict(settings or {})
    span = max(float(span_length_m), 0.001)
    lifting_ratio = min(max(_float_value(settings.get("lifting_point_ratio"), 0.20), 0.05), 0.45)
    lifting_factor = max(_float_value(settings.get("lifting_impact_factor"), 1.10), 1.0)
    basis_set = railway_u_girder_stage_basis_set(geometry, settings)
    q = basis_set.quantities
    station_grid = list(stations_m or railway_u_girder_stage_station_grid(span, strand_table, lifting_ratio))
    web_strands = _one_web_strand_table(strand_table)
    stage_specs = [
        {
            "Stage": "Transfer",
            "Section basis": "One precast web only",
            "basis": basis_set.web_basis,
            "w": q.web_self_weight_kN_m,
            "pe_source": "transfer",
            "strand_table": web_strands,
            "moment": "simple",
            "note": "web self-weight + Pe_transfer; web-only stage",
        },
        {
            "Stage": "Lifting",
            "Section basis": "One precast web only",
            "basis": basis_set.web_basis,
            "w": q.web_self_weight_kN_m * lifting_factor,
            "pe_source": "transfer",
            "strand_table": web_strands,
            "moment": "lifting",
            "note": f"two-point lifting at a/L={lifting_ratio:.3f}; impact factor {lifting_factor:.2f}",
        },
        {
            "Stage": "Wet slab casting",
            "Section basis": "One precast web only",
            "basis": basis_set.web_basis,
            "w": q.web_self_weight_kN_m + q.wet_slab_to_each_web_kN_m + q.formwork_to_each_web_kN_m,
            "pe_source": "construction",
            "strand_table": web_strands,
            "moment": "simple",
            "note": "Case B: web self-weight + 50% wet slab + 50% formwork + Pe_construction",
        },
        {
            "Stage": "Service Pe reference",
            "Section basis": "Full Railway U-Girder gross reference",
            "basis": basis_set.full_u_basis,
            "w": 0.0,
            "pe_source": "final",
            "strand_table": strand_table,
            "moment": "simple",
            "note": "Pe_final on full U-section only; service loads remain in Loads/Analysis workflow",
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in stage_specs:
        basis = spec["basis"]
        w = float(spec["w"])
        for x in station_grid:
            if spec["moment"] == "lifting":
                auto_m = lifting_udl_moment_kNm(w, x, span, lifting_ratio)
            else:
                auto_m = simple_span_udl_moment_kNm(w, x, span)
            service = run_basic_girder_service_stress(basis, N_kN=0.0, M_kNm=auto_m)
            pe, yps, effective_strands, active_groups = _station_pe(
                spec["strand_table"],
                x_m=x,
                span_length_m=span,
                pe_source=str(spec["pe_source"]),
            )
            ps_top = 0.0
            ps_bottom = 0.0
            if pe > 0.0 and yps is not None:
                prestress = run_girder_prestress_stress_effect(basis, Pe_eff_kN=pe, tendon_y_from_bottom_mm=yps)
                ps_top = prestress.top.total_stress_MPa
                ps_bottom = prestress.bottom.total_stress_MPa
            top_total = service.top.total_stress_MPa + ps_top
            bottom_total = service.bottom.total_stress_MPa + ps_bottom
            rows.append(
                {
                    "Stage": spec["Stage"],
                    "Station x (m)": round(float(x), 6),
                    "Section basis": spec["Section basis"],
                    "Auto load w (kN/m)": w,
                    "Auto Mx (kN-m)": auto_m,
                    "Pe stage (kN)": pe,
                    "yps eff (mm from bottom)": yps,
                    "Top service+Pe (MPa)": top_total,
                    "Bottom service+Pe (MPa)": bottom_total,
                    "Top total (MPa)": top_total,
                    "Bottom total (MPa)": bottom_total,
                    "Max compression (MPa)": min(top_total, bottom_total),
                    "Max tension (MPa)": max(top_total, bottom_total),
                    "Effective strands": effective_strands,
                    "Active group IDs": active_groups,
                    "Preview note": spec["note"],
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=RAILWAY_UGIRDER_SLS_PREVIEW_COLUMNS)
    return df


def railway_u_girder_stage_governing_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return one governing compression/tension row per stage for quick review."""

    if df.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for stage, group in df.groupby("Stage", sort=False):
        comp_idx = group["Max compression (MPa)"].idxmin()
        tens_idx = group["Max tension (MPa)"].idxmax()
        comp = df.loc[comp_idx]
        tens = df.loc[tens_idx]
        rows.append(
            {
                "Stage": stage,
                "Governing compression x (m)": comp["Station x (m)"],
                "Max compression (MPa)": comp["Max compression (MPa)"],
                "Governing tension x (m)": tens["Station x (m)"],
                "Max tension (MPa)": tens["Max tension (MPa)"],
                "Section basis": str(comp.get("Section basis") or ""),
                "Preview note": str(comp.get("Preview note") or ""),
            }
        )
    return pd.DataFrame(rows)


def _railway_u_girder_limit_stage_for_preview(stage: str, settings: Mapping[str, Any] | None) -> tuple[str, float, str]:
    """Return (code-limit stage, concrete strength, note) for a staged preview row.

    This helper deliberately keeps Railway U-Girder limits as a preview layer.
    The stress values are generated elsewhere; this function only assigns the
    editable code-profile context and concrete strength used for the limit table.
    """

    settings = dict(settings or {})
    web_fc = _positive(settings.get("web_fc_MPa"), 45.0)
    web_fci = _positive(settings.get("web_fci_MPa"), 36.0)
    slab_fc = _positive(settings.get("slab_fc_MPa"), 35.0)
    name = str(stage or "").strip().lower()
    if name == "transfer":
        return STAGE_TRANSFER, web_fci, "Transfer/release preview uses one precast web and f'ci(web)."
    if name == "lifting":
        return STAGE_TRANSFER, web_fci, "Temporary lifting preview uses transfer-stage web strength f'ci(web)."
    if name == "wet slab casting":
        return STAGE_DECK_CASTING, web_fc, "Wet slab casting preview uses one precast web and f'c(web)."
    if name == "service pe reference":
        return (
            STAGE_FINAL_SERVICE,
            min(web_fc, slab_fc),
            "Full-U Pe-only reference uses min(f'c web, f'c slab) for a conservative preview; service loads remain outside this table.",
        )
    return STAGE_FINAL_SERVICE, web_fc, "User-defined Railway U-Girder preview stage."


def railway_u_girder_staged_stress_limit_check_dataframe(
    stress_df: pd.DataFrame,
    *,
    settings: Mapping[str, Any] | None,
    code: str = "AASHTO LRFD Bridge",
) -> pd.DataFrame:
    """Check staged Railway U-Girder stress-preview rows against editable limits.

    SLS.RAIL.UGIRDER2 adds a stage-aware limit-check handoff without changing
    the stress solver.  It is intentionally conservative/guarded:
    - Transfer and lifting use f'ci(web).
    - Wet slab casting uses f'c(web).
    - The full-U service row remains Pe-reference only and uses min(web/slab f'c)
      unless a later transformed locked-in service workflow supersedes it.
    """

    if stress_df is None or pd.DataFrame(stress_df).empty:
        return pd.DataFrame(columns=RAILWAY_UGIRDER_SLS_LIMIT_COLUMNS)
    df = pd.DataFrame(stress_df).copy()
    rows: list[dict[str, Any]] = []
    for _, source in df.iterrows():
        stage = str(source.get("Stage") or "")
        limit_stage, fc, note = _railway_u_girder_limit_stage_for_preview(stage, settings)
        profile = default_girder_sls_limit_profile(code=code, stage=limit_stage)
        top = _float_value(source.get("Top total (MPa)", source.get("Top service+Pe (MPa)")), 0.0)
        bottom = _float_value(source.get("Bottom total (MPa)", source.get("Bottom service+Pe (MPa)")), 0.0)
        result = run_girder_service_stress_limit_check(
            stresses=(
                StressLimitInputRow("Top", top),
                StressLimitInputRow("Bottom", bottom),
            ),
            fc_MPa=fc,
            profile=profile,
        )
        point_by_fiber = {point.fiber.lower(): point for point in result.points}
        top_point = point_by_fiber.get("top")
        bottom_point = point_by_fiber.get("bottom")
        rows.append(
            {
                "Stage": stage,
                "Station x (m)": source.get("Station x (m)"),
                "Section basis": source.get("Section basis"),
                "Concrete strength used (MPa)": fc,
                "Limit stage profile": profile.stage,
                "Top total (MPa)": top,
                "Bottom total (MPa)": bottom,
                "Top status": getattr(top_point, "status", "NOT_CHECKED"),
                "Bottom status": getattr(bottom_point, "status", "NOT_CHECKED"),
                "Overall status": result.overall_status,
                "Max utilization": result.max_utilization,
                "Limit note": note,
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_SLS_LIMIT_COLUMNS)


def railway_u_girder_stage_limit_governing_rows(limit_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact governing SLS-limit status rows per stage."""

    if limit_df is None or pd.DataFrame(limit_df).empty:
        return pd.DataFrame()
    df = pd.DataFrame(limit_df).copy()
    rows: list[dict[str, Any]] = []
    for stage, group in df.groupby("Stage", sort=False):
        # Prefer the highest utilization. If all are unchecked/None, fall back to
        # the most tensile absolute station for deterministic UI behavior.
        util = pd.to_numeric(group.get("Max utilization"), errors="coerce")
        if util.notna().any():
            idx = util.idxmax()
        else:
            idx = group.index[0]
        row = df.loc[idx]
        rows.append(
            {
                "Stage": stage,
                "Governing x (m)": row.get("Station x (m)"),
                "Overall status": row.get("Overall status"),
                "Max utilization": row.get("Max utilization"),
                "Concrete strength used (MPa)": row.get("Concrete strength used (MPa)"),
                "Limit stage profile": row.get("Limit stage profile"),
                "Section basis": row.get("Section basis"),
                "Limit note": row.get("Limit note"),
            }
        )
    return pd.DataFrame(rows)



def _signed_prestress_top_bottom_MPa(
    basis: GirderSectionBasis,
    *,
    Pe_increment_kN: float,
    tendon_y_from_bottom_mm: float | None,
) -> tuple[float, float]:
    """Return signed prestress stress increment at top/bottom fibers.

    Unlike ``run_girder_prestress_stress_effect``, this helper intentionally
    accepts negative Pe increments so construction/service loss increments can
    be accumulated as a reduction in compression.  It is a local Railway
    U-Girder staged-preview helper, not a new prestress-loss solver.
    """

    pe = _float_value(Pe_increment_kN, 0.0)
    if abs(pe) <= 1.0e-12 or tendon_y_from_bottom_mm is None:
        return 0.0, 0.0
    try:
        yps = float(tendon_y_from_bottom_mm)
    except (TypeError, ValueError):
        return 0.0, 0.0
    if basis.area_mm2 <= 0.0 or basis.ix_mm4 <= 0.0:
        return 0.0, 0.0
    pe_n = pe * 1000.0
    eccentricity_mm = yps - basis.centroid_y_from_bottom_mm
    equivalent_moment_kNm = pe * eccentricity_mm / 1000.0

    def _stress_at(y_from_bottom_mm: float) -> float:
        axial = -pe_n / basis.area_mm2
        bending = equivalent_moment_kNm * 1_000_000.0 * (
            basis.centroid_y_from_bottom_mm - float(y_from_bottom_mm)
        ) / basis.ix_mm4
        return float(axial + bending)

    return _stress_at(basis.top_fiber_y_from_bottom_mm), _stress_at(basis.bottom_fiber_y_from_bottom_mm)


def _load_top_bottom_increment_MPa(
    basis: GirderSectionBasis,
    *,
    w_kN_m: float,
    x_m: float,
    span_length_m: float,
    lifting_point_ratio: float | None = None,
) -> tuple[float, float, float]:
    """Return (Mx, top, bottom) stress increment from a simple UDL action."""

    if lifting_point_ratio is None:
        mx = simple_span_udl_moment_kNm(w_kN_m, x_m, span_length_m)
    else:
        mx = lifting_udl_moment_kNm(w_kN_m, x_m, span_length_m, lifting_point_ratio)
    result = run_basic_girder_service_stress(basis, N_kN=0.0, M_kNm=mx)
    return float(mx), float(result.top.total_stress_MPa), float(result.bottom.total_stress_MPa)



def _load_case_get(load_case: Any, key: str, default: Any = None) -> Any:
    if isinstance(load_case, Mapping):
        return load_case.get(key, default)
    return getattr(load_case, key, default)


def _is_active_sls_load_case(load_case: Any) -> bool:
    active = _load_case_get(load_case, "active", True)
    load_type = str(_load_case_get(load_case, "load_type", "") or "").strip().upper()
    return bool(active) and load_type == "SLS"


def _service_load_case_name(load_case: Any, index: int) -> str:
    name = _load_case_get(load_case, "name", None)
    if name is None and isinstance(load_case, Mapping):
        name = load_case.get("Case Name") or load_case.get("Name")
    text = str(name or "").strip()
    return text or f"SLS-{index + 1}"


def railway_u_girder_service_load_handoff_dataframe(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    load_cases: Iterable[Any] | None,
    station_m: float | None = None,
) -> pd.DataFrame:
    """Return full-U service-load stress rows from active SLS load cases.

    SLS.RAIL.UGIRDER4 consumes service resultants from the Loads tab as a
    guarded full-U handoff.  The load cases are assumed to be service-level
    resultants at the review section; the selected station is used only for the
    station-based Pe_final/debond participation.  Web-stage locked-in stresses
    from transfer/casting are intentionally not algebraically transformed and
    summed in this helper.
    """

    span = max(float(span_length_m), 0.001)
    x = span / 2.0 if station_m is None else min(max(float(station_m), 0.0), span)
    basis_set = railway_u_girder_stage_basis_set(geometry, settings)
    basis = basis_set.full_u_basis
    pe_final, yps_final, effective_final, active_final = _station_pe(
        strand_table,
        x_m=x,
        span_length_m=span,
        pe_source="final",
    )
    pe_top, pe_bottom = _signed_prestress_top_bottom_MPa(
        basis,
        Pe_increment_kN=pe_final,
        tendon_y_from_bottom_mm=yps_final,
    )
    rows: list[dict[str, Any]] = []
    for idx, load_case in enumerate(load_cases or []):
        if not _is_active_sls_load_case(load_case):
            continue
        pu_kN = _float_value(_load_case_get(load_case, "Pu_N", 0.0), 0.0) / 1000.0
        mux_kNm = _float_value(_load_case_get(load_case, "Mux_Nmm", 0.0), 0.0) / 1_000_000.0
        muy_kNm = _float_value(_load_case_get(load_case, "Muy_Nmm", 0.0), 0.0) / 1_000_000.0
        service = run_basic_girder_service_stress(basis, N_kN=pu_kN, M_kNm=mux_kNm)
        top_total = service.top.total_stress_MPa + pe_top
        bottom_total = service.bottom.total_stress_MPa + pe_bottom
        note = "Active SLS load from Loads tab + Pe_final at station; full-U gross preview only."
        if abs(muy_kNm) > 1.0e-9:
            note += " Muy is stored but not included in this 1D U-Girder top/bottom preview."
        rows.append(
            {
                "Load Case": _service_load_case_name(load_case, idx),
                "Station x (m)": round(float(x), 6),
                "Section basis": "Full Railway U-Girder gross reference",
                "Pu (kN)": pu_kN,
                "Mux (kN-m)": mux_kNm,
                "Pe_final (kN)": pe_final,
                "yps eff (mm from bottom)": yps_final,
                "Effective strands": effective_final,
                "Load top (MPa)": service.top.total_stress_MPa,
                "Load bottom (MPa)": service.bottom.total_stress_MPa,
                "Pe top (MPa)": pe_top,
                "Pe bottom (MPa)": pe_bottom,
                "Top total (MPa)": top_total,
                "Bottom total (MPa)": bottom_total,
                "Max compression (MPa)": min(top_total, bottom_total),
                "Max tension (MPa)": max(top_total, bottom_total),
                "Active group IDs": active_final,
                "Preview note": note,
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_SERVICE_LOAD_COLUMNS)


def railway_u_girder_service_load_limit_check_dataframe(
    service_df: pd.DataFrame,
    *,
    settings: Mapping[str, Any] | None,
    code: str = "AASHTO LRFD Bridge",
) -> pd.DataFrame:
    """Check Railway U-Girder service load handoff rows against service limits."""

    if service_df is None or pd.DataFrame(service_df).empty:
        return pd.DataFrame(columns=RAILWAY_UGIRDER_SERVICE_LOAD_LIMIT_COLUMNS)
    settings = dict(settings or {})
    web_fc = _positive(settings.get("web_fc_MPa"), 45.0)
    slab_fc = _positive(settings.get("slab_fc_MPa"), 35.0)
    fc = min(web_fc, slab_fc)
    profile = default_girder_sls_limit_profile(code=code, stage=STAGE_FINAL_SERVICE)
    rows: list[dict[str, Any]] = []
    for _, source in pd.DataFrame(service_df).iterrows():
        top = _float_value(source.get("Top total (MPa)"), 0.0)
        bottom = _float_value(source.get("Bottom total (MPa)"), 0.0)
        result = run_girder_service_stress_limit_check(
            stresses=(
                StressLimitInputRow("Top", top),
                StressLimitInputRow("Bottom", bottom),
            ),
            fc_MPa=fc,
            profile=profile,
        )
        point_by_fiber = {point.fiber.lower(): point for point in result.points}
        top_point = point_by_fiber.get("top")
        bottom_point = point_by_fiber.get("bottom")
        rows.append(
            {
                "Load Case": source.get("Load Case"),
                "Station x (m)": source.get("Station x (m)"),
                "Section basis": source.get("Section basis"),
                "Concrete strength used (MPa)": fc,
                "Limit stage profile": profile.stage,
                "Top total (MPa)": top,
                "Bottom total (MPa)": bottom,
                "Top status": getattr(top_point, "status", "NOT_CHECKED"),
                "Bottom status": getattr(bottom_point, "status", "NOT_CHECKED"),
                "Overall status": result.overall_status,
                "Max utilization": result.max_utilization,
                "Limit note": "Service load handoff uses min(f'c web, f'c slab) and full-U gross preview; not final certified staged SLS.",
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_SERVICE_LOAD_LIMIT_COLUMNS)


def railway_u_girder_service_load_governing_rows(service_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact governing service load rows for quick review."""

    if service_df is None or pd.DataFrame(service_df).empty:
        return pd.DataFrame()
    df = pd.DataFrame(service_df).copy()
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "Load Case": row.get("Load Case"),
                "Station x (m)": row.get("Station x (m)"),
                "Pu (kN)": row.get("Pu (kN)"),
                "Mux (kN-m)": row.get("Mux (kN-m)"),
                "Pe_final (kN)": row.get("Pe_final (kN)"),
                "Top total (MPa)": row.get("Top total (MPa)"),
                "Bottom total (MPa)": row.get("Bottom total (MPa)"),
                "Max compression (MPa)": row.get("Max compression (MPa)"),
                "Max tension (MPa)": row.get("Max tension (MPa)"),
                "Preview note": row.get("Preview note"),
            }
        )
    return pd.DataFrame(rows)


def railway_u_girder_locked_in_stress_accumulation_dataframe(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    stations_m: Iterable[float] | None = None,
) -> pd.DataFrame:
    """Return guarded locked-in stress accumulation rows for Railway U-Girder.

    SLS.RAIL.UGIRDER3 keeps the stage mechanics explicit:
    - Transfer is a locked web-only stress increment.
    - Wet slab casting adds the wet slab/formwork load increment plus the
      construction-stage prestress change on the web-only basis.
    - Final Pe is reported as a full-U section handoff increment only; locked
      web stresses are not algebraically transformed into full-U top/bottom
      fibers in this preview.

    The function deliberately does not model transfer-length force ramping,
    development length, end-zone bursting, creep/shrinkage redistribution, or
    final code-certified locked-in service stress.
    """

    settings = dict(settings or {})
    span = max(float(span_length_m), 0.001)
    lifting_ratio = min(max(_float_value(settings.get("lifting_point_ratio"), 0.20), 0.05), 0.45)
    basis_set = railway_u_girder_stage_basis_set(geometry, settings)
    q = basis_set.quantities
    station_grid = list(stations_m or railway_u_girder_stage_station_grid(span, strand_table, lifting_ratio))
    web_strands = _one_web_strand_table(strand_table)
    rows: list[dict[str, Any]] = []

    for x in station_grid:
        transfer_m, transfer_load_top, transfer_load_bottom = _load_top_bottom_increment_MPa(
            basis_set.web_basis,
            w_kN_m=q.web_self_weight_kN_m,
            x_m=x,
            span_length_m=span,
        )
        pe_transfer, yps_transfer, effective_transfer, active_transfer = _station_pe(
            web_strands,
            x_m=x,
            span_length_m=span,
            pe_source="transfer",
        )
        ps_top, ps_bottom = _signed_prestress_top_bottom_MPa(
            basis_set.web_basis,
            Pe_increment_kN=pe_transfer,
            tendon_y_from_bottom_mm=yps_transfer,
        )
        transfer_top = transfer_load_top + ps_top
        transfer_bottom = transfer_load_bottom + ps_bottom
        rows.append(
            {
                "Accumulation step": "1 Transfer locked-in web stress",
                "Station x (m)": round(float(x), 6),
                "Section basis": "One precast web only",
                "Load increment w (kN/m)": q.web_self_weight_kN_m,
                "Moment increment (kN-m)": transfer_m,
                "Pe increment (kN)": pe_transfer,
                "Effective strands": effective_transfer,
                "Top increment (MPa)": transfer_top,
                "Bottom increment (MPa)": transfer_bottom,
                "Cumulative top (MPa)": transfer_top,
                "Cumulative bottom (MPa)": transfer_bottom,
                "Carry-over basis": "Locked into precast web",
                "Preview note": f"web self-weight + Pe_transfer; active rows: {active_transfer}",
            }
        )

        casting_w = q.wet_slab_to_each_web_kN_m + q.formwork_to_each_web_kN_m
        casting_m, casting_load_top, casting_load_bottom = _load_top_bottom_increment_MPa(
            basis_set.web_basis,
            w_kN_m=casting_w,
            x_m=x,
            span_length_m=span,
        )
        pe_construction, yps_construction, effective_construction, active_construction = _station_pe(
            web_strands,
            x_m=x,
            span_length_m=span,
            pe_source="construction",
        )
        delta_pe_construction = pe_construction - pe_transfer
        delta_yps = yps_construction if yps_construction is not None else yps_transfer
        dps_top, dps_bottom = _signed_prestress_top_bottom_MPa(
            basis_set.web_basis,
            Pe_increment_kN=delta_pe_construction,
            tendon_y_from_bottom_mm=delta_yps,
        )
        casting_top = casting_load_top + dps_top
        casting_bottom = casting_load_bottom + dps_bottom
        cumulative_top = transfer_top + casting_top
        cumulative_bottom = transfer_bottom + casting_bottom
        rows.append(
            {
                "Accumulation step": "2 Wet slab casting locked-in web stress",
                "Station x (m)": round(float(x), 6),
                "Section basis": "One precast web only",
                "Load increment w (kN/m)": casting_w,
                "Moment increment (kN-m)": casting_m,
                "Pe increment (kN)": delta_pe_construction,
                "Effective strands": effective_construction,
                "Top increment (MPa)": casting_top,
                "Bottom increment (MPa)": casting_bottom,
                "Cumulative top (MPa)": cumulative_top,
                "Cumulative bottom (MPa)": cumulative_bottom,
                "Carry-over basis": "Locked into precast web before composite action",
                "Preview note": f"wet slab + formwork + (Pe_construction - Pe_transfer); active rows: {active_construction}",
            }
        )

        pe_final, yps_final, effective_final, active_final = _station_pe(
            strand_table,
            x_m=x,
            span_length_m=span,
            pe_source="final",
        )
        # Use the full strand table for construction Pe at the same station so
        # the final-service prestress loss handoff is on a full-U basis.
        pe_construction_full, yps_construction_full, _eff_c_full, _active_c_full = _station_pe(
            strand_table,
            x_m=x,
            span_length_m=span,
            pe_source="construction",
        )
        delta_pe_final = pe_final - pe_construction_full
        delta_yps_final = yps_final if yps_final is not None else yps_construction_full
        final_top, final_bottom = _signed_prestress_top_bottom_MPa(
            basis_set.full_u_basis,
            Pe_increment_kN=delta_pe_final,
            tendon_y_from_bottom_mm=delta_yps_final,
        )
        rows.append(
            {
                "Accumulation step": "3 Final Pe handoff on full U-section",
                "Station x (m)": round(float(x), 6),
                "Section basis": "Full Railway U-Girder gross reference",
                "Load increment w (kN/m)": 0.0,
                "Moment increment (kN-m)": 0.0,
                "Pe increment (kN)": delta_pe_final,
                "Effective strands": effective_final,
                "Top increment (MPa)": final_top,
                "Bottom increment (MPa)": final_bottom,
                "Cumulative top (MPa)": pd.NA,
                "Cumulative bottom (MPa)": pd.NA,
                "Carry-over basis": "Full-U service increment only; not summed with web-locked fibers",
                "Preview note": f"Pe_final - Pe_construction on full-U basis; service loads remain in Loads/Analysis; active rows: {active_final}",
            }
        )

    if not rows:
        return pd.DataFrame(columns=RAILWAY_UGIRDER_LOCKED_IN_COLUMNS)
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_LOCKED_IN_COLUMNS)


def railway_u_girder_locked_in_governing_rows(locked_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact governing rows for locked-in staged stress handoff."""

    if locked_df is None or pd.DataFrame(locked_df).empty:
        return pd.DataFrame()
    df = pd.DataFrame(locked_df).copy()
    rows: list[dict[str, Any]] = []
    for step, group in df.groupby("Accumulation step", sort=False):
        comp = pd.to_numeric(group.get("Cumulative top (MPa)"), errors="coerce")
        comp_bottom = pd.to_numeric(group.get("Cumulative bottom (MPa)"), errors="coerce")
        inc_top = pd.to_numeric(group.get("Top increment (MPa)"), errors="coerce")
        inc_bottom = pd.to_numeric(group.get("Bottom increment (MPa)"), errors="coerce")
        # Governing by cumulative stress where available; otherwise use increment
        # rows such as full-U Pe handoff.
        combined = pd.concat([comp, comp_bottom], axis=1).min(axis=1, skipna=True)
        tension = pd.concat([comp, comp_bottom], axis=1).max(axis=1, skipna=True)
        if combined.notna().any():
            comp_idx = combined.idxmin()
            tens_idx = tension.idxmax()
            comp_val = combined.loc[comp_idx]
            tens_val = tension.loc[tens_idx]
        else:
            inc_comp = pd.concat([inc_top, inc_bottom], axis=1).min(axis=1, skipna=True)
            inc_tens = pd.concat([inc_top, inc_bottom], axis=1).max(axis=1, skipna=True)
            comp_idx = inc_comp.idxmin()
            tens_idx = inc_tens.idxmax()
            comp_val = inc_comp.loc[comp_idx]
            tens_val = inc_tens.loc[tens_idx]
        row = df.loc[comp_idx]
        tens_row = df.loc[tens_idx]
        rows.append(
            {
                "Accumulation step": step,
                "Governing compression x (m)": row.get("Station x (m)"),
                "Governing compression (MPa)": comp_val,
                "Governing tension x (m)": tens_row.get("Station x (m)"),
                "Governing tension (MPa)": tens_val,
                "Section basis": row.get("Section basis"),
                "Carry-over basis": row.get("Carry-over basis"),
            }
        )
    return pd.DataFrame(rows)


def _locked_web_cumulative_at_station(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    station_m: float,
) -> tuple[float, float, str]:
    """Return locked-in web top/bottom stresses at a station for final preview.

    The returned values are physical web extreme-fiber stresses accumulated
    before full composite action.  They may be added to later full-U incremental
    service actions at the same top/bottom physical fibers for a guarded Railway
    U-Girder review preview, but this is not a creep/shrinkage redistribution or
    code-certified staged composite solver.
    """

    locked = railway_u_girder_locked_in_stress_accumulation_dataframe(
        geometry=geometry,
        settings=settings,
        strand_table=strand_table,
        span_length_m=span_length_m,
        stations_m=[station_m],
    )
    if locked.empty:
        return 0.0, 0.0, "No locked-in web rows available"
    stage2 = locked[locked["Accumulation step"].astype(str).str.startswith("2 Wet slab casting")]
    source = stage2.iloc[0] if not stage2.empty else locked.iloc[-1]
    return (
        _float_value(source.get("Cumulative top (MPa)"), 0.0),
        _float_value(source.get("Cumulative bottom (MPa)"), 0.0),
        str(source.get("Carry-over basis") or "Locked into precast web"),
    )


def railway_u_girder_final_service_accumulation_dataframe(
    *,
    geometry: SectionGeometry | None,
    settings: Mapping[str, Any] | None,
    strand_table: pd.DataFrame | None,
    span_length_m: float,
    load_cases: Iterable[Any] | None,
    station_m: float | None = None,
) -> pd.DataFrame:
    """Return guarded final staged service-stress accumulation rows.

    SLS.RAIL.UGIRDER5 combines:
    - locked-in web stresses from transfer + wet slab casting on the one-web
      basis at the same physical top/bottom web fibers,
    - final prestress loss increment ``Pe_final - Pe_construction`` on the full
      U-section basis, and
    - active SLS resultants from the Loads tab as *additional service increments*
      on the full-U basis.

    This is still an engineering-review preview.  It does not model time-
    dependent redistribution, transfer-length force ramping, development length,
    anchorage/end-zone bursting, or final code certification.
    """

    span = max(float(span_length_m), 0.001)
    x = span / 2.0 if station_m is None else min(max(float(station_m), 0.0), span)
    basis_set = railway_u_girder_stage_basis_set(geometry, settings)
    basis = basis_set.full_u_basis
    locked_top, locked_bottom, locked_note = _locked_web_cumulative_at_station(
        geometry=geometry,
        settings=settings,
        strand_table=strand_table,
        span_length_m=span,
        station_m=x,
    )
    pe_final, yps_final, effective_final, active_final = _station_pe(
        strand_table,
        x_m=x,
        span_length_m=span,
        pe_source="final",
    )
    pe_construction_full, yps_construction_full, _eff_c_full, _active_c_full = _station_pe(
        strand_table,
        x_m=x,
        span_length_m=span,
        pe_source="construction",
    )
    delta_pe_final = pe_final - pe_construction_full
    delta_yps = yps_final if yps_final is not None else yps_construction_full
    pe_top, pe_bottom = _signed_prestress_top_bottom_MPa(
        basis,
        Pe_increment_kN=delta_pe_final,
        tendon_y_from_bottom_mm=delta_yps,
    )
    rows: list[dict[str, Any]] = []
    for idx, load_case in enumerate(load_cases or []):
        if not _is_active_sls_load_case(load_case):
            continue
        pu_kN = _float_value(_load_case_get(load_case, "Pu_N", 0.0), 0.0) / 1000.0
        mux_kNm = _float_value(_load_case_get(load_case, "Mux_Nmm", 0.0), 0.0) / 1_000_000.0
        muy_kNm = _float_value(_load_case_get(load_case, "Muy_Nmm", 0.0), 0.0) / 1_000_000.0
        service = run_basic_girder_service_stress(basis, N_kN=pu_kN, M_kNm=mux_kNm)
        top_total = locked_top + service.top.total_stress_MPa + pe_top
        bottom_total = locked_bottom + service.bottom.total_stress_MPa + pe_bottom
        note = (
            "Locked web stresses + final Pe loss increment + active SLS load increment. "
            "Loads tab values are treated as additional service actions after composite action; "
            "do not include auto web/wet-slab self-weight again unless intentionally checking a total-resultant case. "
            f"Locked basis: {locked_note}."
        )
        if abs(muy_kNm) > 1.0e-9:
            note += " Muy is stored but not included in this 1D top/bottom preview."
        rows.append(
            {
                "Load Case": _service_load_case_name(load_case, idx),
                "Station x (m)": round(float(x), 6),
                "Section basis": "Locked web fibers + full Railway U-Girder incremental service",
                "Pu (kN)": pu_kN,
                "Mux (kN-m)": mux_kNm,
                "Locked top (MPa)": locked_top,
                "Locked bottom (MPa)": locked_bottom,
                "Service load top (MPa)": service.top.total_stress_MPa,
                "Service load bottom (MPa)": service.bottom.total_stress_MPa,
                "Final Pe increment top (MPa)": pe_top,
                "Final Pe increment bottom (MPa)": pe_bottom,
                "Final top (MPa)": top_total,
                "Final bottom (MPa)": bottom_total,
                "Max compression (MPa)": min(top_total, bottom_total),
                "Max tension (MPa)": max(top_total, bottom_total),
                "Pe_final increment (kN)": delta_pe_final,
                "Effective strands": effective_final,
                "Active group IDs": active_final,
                "Preview note": note,
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_FINAL_SERVICE_COLUMNS)


def railway_u_girder_final_service_limit_check_dataframe(
    final_df: pd.DataFrame,
    *,
    settings: Mapping[str, Any] | None,
    code: str = "AASHTO LRFD Bridge",
) -> pd.DataFrame:
    """Check final staged service accumulation rows against service limits."""

    if final_df is None or pd.DataFrame(final_df).empty:
        return pd.DataFrame(columns=RAILWAY_UGIRDER_FINAL_SERVICE_LIMIT_COLUMNS)
    settings = dict(settings or {})
    web_fc = _positive(settings.get("web_fc_MPa"), 45.0)
    slab_fc = _positive(settings.get("slab_fc_MPa"), 35.0)
    fc = min(web_fc, slab_fc)
    profile = default_girder_sls_limit_profile(code=code, stage=STAGE_FINAL_SERVICE)
    rows: list[dict[str, Any]] = []
    for _, source in pd.DataFrame(final_df).iterrows():
        top = _float_value(source.get("Final top (MPa)"), 0.0)
        bottom = _float_value(source.get("Final bottom (MPa)"), 0.0)
        result = run_girder_service_stress_limit_check(
            stresses=(
                StressLimitInputRow("Top", top),
                StressLimitInputRow("Bottom", bottom),
            ),
            fc_MPa=fc,
            profile=profile,
        )
        point_by_fiber = {point.fiber.lower(): point for point in result.points}
        top_point = point_by_fiber.get("top")
        bottom_point = point_by_fiber.get("bottom")
        rows.append(
            {
                "Load Case": source.get("Load Case"),
                "Station x (m)": source.get("Station x (m)"),
                "Section basis": source.get("Section basis"),
                "Concrete strength used (MPa)": fc,
                "Limit stage profile": profile.stage,
                "Final top (MPa)": top,
                "Final bottom (MPa)": bottom,
                "Top status": getattr(top_point, "status", "NOT_CHECKED"),
                "Bottom status": getattr(bottom_point, "status", "NOT_CHECKED"),
                "Overall status": result.overall_status,
                "Max utilization": result.max_utilization,
                "Limit note": "Final staged service accumulation uses min(f'c web, f'c slab) as a conservative preview; review load attribution to avoid double-counted self-weight.",
            }
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_FINAL_SERVICE_LIMIT_COLUMNS)


def railway_u_girder_final_service_governing_rows(final_df: pd.DataFrame) -> pd.DataFrame:
    """Return compact governing rows for final staged service accumulation."""

    if final_df is None or pd.DataFrame(final_df).empty:
        return pd.DataFrame()
    df = pd.DataFrame(final_df).copy()
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "Load Case": row.get("Load Case"),
                "Station x (m)": row.get("Station x (m)"),
                "Locked top (MPa)": row.get("Locked top (MPa)"),
                "Locked bottom (MPa)": row.get("Locked bottom (MPa)"),
                "Service load top (MPa)": row.get("Service load top (MPa)"),
                "Service load bottom (MPa)": row.get("Service load bottom (MPa)"),
                "Final top (MPa)": row.get("Final top (MPa)"),
                "Final bottom (MPa)": row.get("Final bottom (MPa)"),
                "Max compression (MPa)": row.get("Max compression (MPa)"),
                "Max tension (MPa)": row.get("Max tension (MPa)"),
                "Preview note": row.get("Preview note"),
            }
        )
    return pd.DataFrame(rows)


def _railway_preview_decision_from_statuses(statuses: Iterable[Any]) -> tuple[str, str]:
    """Return guarded user-facing decision and review action from limit statuses."""

    clean = [str(status or "").strip().upper() for status in statuses if str(status or "").strip()]
    if not clean:
        return "REVIEW", "No stress-limit result available for this stage."
    if any(status == "FAIL" for status in clean):
        return "REVIEW", "At least one fiber exceeds the preview stress limit."
    if all(status == "PASS" for status in clean):
        return "Preview PASS", "Available for engineering review; not code-certified."
    return "REVIEW", "One or more fibers are not checked by the selected preview profile."


def _railway_max_utilization(group: pd.DataFrame) -> float | None:
    util = pd.to_numeric(group.get("Max utilization"), errors="coerce")
    if util.notna().any():
        return float(util.max())
    return None


def _railway_stage_limit_decision_row(
    *,
    check_stage: str,
    source_df: pd.DataFrame,
    stage_filter: str | None,
    top_column: str,
    bottom_column: str,
    x_column: str,
    source_label: str,
    section_basis_fallback: str,
) -> dict[str, Any]:
    if source_df is None or pd.DataFrame(source_df).empty:
        return {
            "Check stage": check_stage,
            "Decision": "REVIEW",
            "Governing source": source_label,
            "Governing x / case": "No rows",
            "Max utilization": pd.NA,
            "Compression (MPa)": pd.NA,
            "Tension (MPa)": pd.NA,
            "Section basis": section_basis_fallback,
            "Review action": "No stress-limit rows are available for this stage.",
        }
    df = pd.DataFrame(source_df).copy()
    if stage_filter is not None and "Stage" in df.columns:
        df = df[df["Stage"].astype(str).str.strip() == stage_filter]
    if df.empty:
        return {
            "Check stage": check_stage,
            "Decision": "REVIEW",
            "Governing source": source_label,
            "Governing x / case": "No matching rows",
            "Max utilization": pd.NA,
            "Compression (MPa)": pd.NA,
            "Tension (MPa)": pd.NA,
            "Section basis": section_basis_fallback,
            "Review action": f"No rows found for {check_stage}.",
        }
    decision, action = _railway_preview_decision_from_statuses(df.get("Overall status", []))
    util = pd.to_numeric(df.get("Max utilization"), errors="coerce")
    if util.notna().any():
        idx = util.idxmax()
    else:
        # Deterministic fallback: row with largest absolute reported stress.
        top_abs = pd.to_numeric(df.get(top_column), errors="coerce").abs()
        bottom_abs = pd.to_numeric(df.get(bottom_column), errors="coerce").abs()
        combined = pd.concat([top_abs, bottom_abs], axis=1).max(axis=1, skipna=True)
        idx = combined.idxmax() if combined.notna().any() else df.index[0]
    row = df.loc[idx]
    top = _float_value(row.get(top_column), 0.0)
    bottom = _float_value(row.get(bottom_column), 0.0)
    return {
        "Check stage": check_stage,
        "Decision": decision,
        "Governing source": source_label,
        "Governing x / case": row.get(x_column),
        "Max utilization": _railway_max_utilization(df),
        "Compression (MPa)": min(top, bottom),
        "Tension (MPa)": max(top, bottom),
        "Section basis": row.get("Section basis", section_basis_fallback),
        "Review action": action,
    }


def railway_u_girder_sls_decision_summary_dataframe(
    *,
    stage_limit_df: pd.DataFrame | None,
    final_service_limit_df: pd.DataFrame | None,
    active_sls_count: int = 0,
) -> pd.DataFrame:
    """Return compact Railway U-Girder staged SLS decision-summary rows.

    SLS.RAIL.UGIRDER6 intentionally presents guarded review decisions, not a
    code-certified design result.  Transfer/lifting/wet casting are derived from
    the staged local limit table.  Final service is derived from the final
    accumulated service limit table and requires at least one active SLS load
    case from Loads.
    """

    stage_df = pd.DataFrame(stage_limit_df).copy() if stage_limit_df is not None else pd.DataFrame()
    final_df = pd.DataFrame(final_service_limit_df).copy() if final_service_limit_df is not None else pd.DataFrame()
    rows = [
        _railway_stage_limit_decision_row(
            check_stage="Transfer",
            source_df=stage_df,
            stage_filter="Transfer",
            top_column="Top total (MPa)",
            bottom_column="Bottom total (MPa)",
            x_column="Station x (m)",
            source_label="Stage stress-limit preview",
            section_basis_fallback="One precast web only",
        ),
        _railway_stage_limit_decision_row(
            check_stage="Lifting",
            source_df=stage_df,
            stage_filter="Lifting",
            top_column="Top total (MPa)",
            bottom_column="Bottom total (MPa)",
            x_column="Station x (m)",
            source_label="Stage stress-limit preview",
            section_basis_fallback="One precast web only",
        ),
        _railway_stage_limit_decision_row(
            check_stage="Wet slab casting",
            source_df=stage_df,
            stage_filter="Wet slab casting",
            top_column="Top total (MPa)",
            bottom_column="Bottom total (MPa)",
            x_column="Station x (m)",
            source_label="Stage stress-limit preview",
            section_basis_fallback="One precast web only",
        ),
    ]
    if int(active_sls_count or 0) <= 0:
        rows.append(
            {
                "Check stage": "Final service",
                "Decision": "REVIEW",
                "Governing source": "Final staged service accumulation",
                "Governing x / case": "No active SLS load case",
                "Max utilization": pd.NA,
                "Compression (MPa)": pd.NA,
                "Tension (MPa)": pd.NA,
                "Section basis": "Locked web fibers + full Railway U-Girder incremental service",
                "Review action": "Add/activate SLS load cases in Loads before final service review.",
            }
        )
    else:
        rows.append(
            _railway_stage_limit_decision_row(
                check_stage="Final service",
                source_df=final_df,
                stage_filter=None,
                top_column="Final top (MPa)",
                bottom_column="Final bottom (MPa)",
                x_column="Load Case",
                source_label="Final staged service accumulation",
                section_basis_fallback="Locked web fibers + full Railway U-Girder incremental service",
            )
        )
    return pd.DataFrame(rows, columns=RAILWAY_UGIRDER_SLS_DECISION_SUMMARY_COLUMNS)

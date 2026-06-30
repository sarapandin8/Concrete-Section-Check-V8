"""Generic precast lifting-stage report helpers.

GIRDER.LIFT.REPORT1 turns the existing non-Railway precast lifting preview into
report/export tables.  It does not add a new lifting solver.  The report
package reuses the established individual-precast-unit load basis, two-point
lifting moment/shear helpers, precast-gross stress basis, and transfer Pe
station participation used by the Analysis SLS workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd

from concrete_pmm_pro.core.analysis_modes import is_building_beam_girder_workflow
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.serviceability.girder_prestress import run_girder_prestress_stress_effect
from concrete_pmm_pro.serviceability.girder_prestress_station import evaluate_girder_prestress_station, station_candidates_from_debonding
from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY,
    BEAM_GIRDER_SYSTEM_SETTINGS_KEY,
    BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY,
    auto_load_breakdown_for_stage,
    auto_load_settings_from_mapping,
    building_auto_load_breakdown_for_stage,
    building_service_load_settings_from_mapping,
    default_sls_station_grid,
    system_settings_from_mapping,
    two_point_lifting_moment_kNm,
    two_point_lifting_shear_kN,
)
from concrete_pmm_pro.serviceability.girder_stress import run_basic_girder_service_stress
from concrete_pmm_pro.serviceability.girder_workflow import build_girder_service_stress_basis_options

GENERIC_PRECAST_LIFTING_REPORT_STATUS = "Generic precast lifting-stage engineering-review report-ready; not final code-certified"
GENERIC_PRECAST_LIFTING_REPORT_CAPABILITY = (
    "Generic precast lifting-stage report/export package for non-Railway precast girder members. "
    "It summarizes the individual precast unit load basis, lifting a/L, lifting impact factor, two-point lifting actions, "
    "station-based transfer Pe participation, and top/bottom stress preview rows."
)
GENERIC_PRECAST_LIFTING_REPORT_EXCLUSIONS = [
    "lifting insert/local hardware design",
    "rigging/spreader beam design",
    "local anchorage and concrete breakout around lifting inserts",
    "transfer length force ramp and development length certification",
    "end-zone bursting/splitting reinforcement design",
    "torsion during skewed or unsymmetrical lifting",
    "time-dependent redistribution and camber certification",
    "final code-certified design approval",
]

GENERIC_PRECAST_LIFTING_TABLE_KEYS = [
    "generic_precast_lifting_scope",
    "generic_precast_lifting_settings",
    "generic_precast_lifting_load_basis",
    "generic_precast_lifting_station_stress_rows",
    "generic_precast_lifting_governing_rows",
    "generic_precast_lifting_closeout_guard",
]

_ELIGIBLE_PRECAST_LIFTING_PRESET_KEYS = {
    "parametric_i_girder",
    "box_section_fillet",
    "precast_box_beam_exterior",
    "parametric_plank_girder_interior",
    "parametric_plank_girder_exterior",
    "parametric_plank_girder_voided_interior",
    "parametric_plank_girder_voided_exterior",
}


@dataclass(frozen=True)
class GenericPrecastLiftingReportPackage:
    available: bool
    status: str
    warnings: list[str] = field(default_factory=list)
    scope: pd.DataFrame = field(default_factory=pd.DataFrame)
    settings: pd.DataFrame = field(default_factory=pd.DataFrame)
    load_basis: pd.DataFrame = field(default_factory=pd.DataFrame)
    station_stress_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    governing_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    closeout_guard: pd.DataFrame = field(default_factory=pd.DataFrame)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "generic_precast_lifting_scope": self.scope,
            "generic_precast_lifting_settings": self.settings,
            "generic_precast_lifting_load_basis": self.load_basis,
            "generic_precast_lifting_station_stress_rows": self.station_stress_rows,
            "generic_precast_lifting_governing_rows": self.governing_rows,
            "generic_precast_lifting_closeout_guard": self.closeout_guard,
        }


def _get(mapping: Any, key: str, default: Any = None) -> Any:
    if mapping is None:
        return default
    if hasattr(mapping, "get"):
        try:
            return mapping.get(key, default)
        except (AttributeError, TypeError, ValueError):
            return default
    return getattr(mapping, key, default)


def _section_metadata(geometry: Any) -> Mapping[str, Any]:
    metadata = getattr(geometry, "metadata", {}) or {}
    return metadata if isinstance(metadata, Mapping) else {}


def _session_mode(session_state: Any) -> Any:
    return _get(session_state, "analysis_mode_settings")


def _as_dataframe(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value.copy()
    try:
        return pd.DataFrame(value).copy()
    except Exception:
        return pd.DataFrame()


def _active_preset_labels(session_state: Any) -> list[str]:
    geometry = _get(session_state, "section_geometry")
    metadata = _section_metadata(geometry)
    labels: list[str] = []
    for key in ("preset", "generator", "preset_key", "section_preset_key", "display_name", "name", "girder_type"):
        value = str(metadata.get(key) or "").strip()
        if value:
            labels.append(value.casefold())
    params = metadata.get("parameters")
    if isinstance(params, Mapping):
        for key in ("preset", "section_preset_key", "girder_type"):
            value = str(params.get(key) or "").strip()
            if value:
                labels.append(value.casefold())
    geometry_name = str(getattr(geometry, "name", "") or "").strip()
    if geometry_name:
        labels.append(geometry_name.casefold())
    for state_key in ("section_preset_key", "section_preset_name", "active_section_preset_name"):
        value = str(_get(session_state, state_key, "") or "").strip()
        if value:
            labels.append(value.casefold())
    return labels


def is_generic_precast_lifting_report_context(session_state: Any) -> bool:
    """Return True for non-Railway precast girder lifting report contexts."""

    labels = _active_preset_labels(session_state)
    joined = " | ".join(labels)
    if "railway_u_girder" in labels or ("railway" in joined and "u-girder" in joined):
        return False
    if any(key in labels or key in joined for key in _ELIGIBLE_PRECAST_LIFTING_PRESET_KEYS):
        return True
    if "precast" not in joined:
        return False
    return any(term in joined for term in ("i-girder", "i girder", "box beam", "plank girder", "voided plank"))


def _section_parameters(session_state: Any) -> Mapping[str, Any]:
    params = _get(session_state, "section_parameters", {})
    if not isinstance(params, Mapping):
        params = _get(session_state, "active_section_parameters", {})
    return params if isinstance(params, Mapping) else {}


def _topping_thickness_mm(session_state: Any) -> float:
    params = _section_parameters(session_state)
    for key in ("Tslab_mm", "topping_thickness_mm", "deck_topping_thickness_mm", "slab_thickness_mm"):
        try:
            value = float(params.get(key))
        except (TypeError, ValueError, AttributeError):
            continue
        if value > 0.0:
            return value
    return 0.0


def _span_length_m(session_state: Any) -> float:
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    return float(system.span_length_m)


def _load_breakdown(session_state: Any, *, precast_area_mm2: float):
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    mode = _session_mode(session_state)
    if mode is not None and is_building_beam_girder_workflow(mode):
        return building_auto_load_breakdown_for_stage(
            stage_label="Lifting stage",
            system=system,
            service_settings=building_service_load_settings_from_mapping(_get(session_state, BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY)),
            precast_area_mm2=precast_area_mm2,
            topping_thickness_mm=_topping_thickness_mm(session_state),
        )
    return auto_load_breakdown_for_stage(
        stage_label="Lifting stage",
        system=system,
        settings=auto_load_settings_from_mapping(_get(session_state, BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY)),
        precast_area_mm2=precast_area_mm2,
        topping_thickness_mm=_topping_thickness_mm(session_state),
    )


def generic_precast_lifting_scope_dataframe() -> pd.DataFrame:
    rows = [
        {"Item": "Report status", "Value": GENERIC_PRECAST_LIFTING_REPORT_STATUS},
        {"Item": "Capability statement", "Value": GENERIC_PRECAST_LIFTING_REPORT_CAPABILITY},
        {"Item": "Load basis", "Value": "Individual precast unit self-weight × lifting impact factor only"},
        {"Item": "Stress basis", "Value": "Precast gross section; transfer Pe force state where strand layout is available"},
        {"Item": "Railway U-Girder routing", "Value": "Excluded from this generic package; Railway U-Girder uses its dedicated report route"},
    ]
    rows.extend({"Item": "Excluded from current report", "Value": item} for item in GENERIC_PRECAST_LIFTING_REPORT_EXCLUSIONS)
    return pd.DataFrame(rows, columns=["Item", "Value"])


def generic_precast_lifting_settings_dataframe(session_state: Any, *, area_mm2: float) -> pd.DataFrame:
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    span = float(system.span_length_m)
    lift_a = span * float(system.lifting_point_ratio)
    summary_rows = [
        ("Active preset", " | ".join(_active_preset_labels(session_state)) or "Not identified", "", "Non-Railway precast lifting report context"),
        ("Span length", span, "m", "Used for two-point lifting station actions"),
        ("Lifting point a/L", float(system.lifting_point_ratio), "ratio", "Distance from each end divided by span"),
        ("Lifting point distance a", lift_a, "m", "a = (a/L) × span"),
        ("Lifting impact factor", float(system.lifting_impact_factor), "factor", "Applied only to individual precast unit self-weight"),
        ("Precast gross area", float(area_mm2), "mm²", "Area from active SectionGeometry gross summary"),
        ("Concrete unit weight", float(system.concrete_unit_weight_kN_m3), "kN/m³", "Used to derive precast unit self-weight"),
    ]
    return pd.DataFrame(
        [{"Setting": name, "Value": value, "Unit": unit, "Report note": note} for name, value, unit, note in summary_rows],
        columns=["Setting", "Value", "Unit", "Report note"],
    )


def generic_precast_lifting_load_basis_dataframe(session_state: Any, *, area_mm2: float) -> pd.DataFrame:
    breakdown = _load_breakdown(session_state, precast_area_mm2=area_mm2)
    rows = breakdown.as_rows()
    rows.append(
        {
            "Stage": "Lifting stage",
            "Component": "Excluded by guardrail",
            "w_kN/m per girder": "Wet slab/topping, barrier, wearing surface, SDL/LL, building service loads",
        }
    )
    return pd.DataFrame(rows, columns=["Stage", "Component", "w_kN/m per girder"])


def _lifting_stations(session_state: Any, span_length_m: float) -> list[float]:
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    a = float(system.lifting_point_ratio) * float(span_length_m)
    extra = [0.0, a, 0.5 * span_length_m, span_length_m - a, span_length_m]
    strand_table = _as_dataframe(_get(session_state, "girder_strand_layout_table"))
    if not strand_table.empty:
        try:
            extra.extend(station_candidates_from_debonding(strand_table, span_length_m))
        except Exception:
            pass
    return default_sls_station_grid(span_length_m, extra_stations_m=extra, divisions=20)


def generic_precast_lifting_station_stress_dataframe(session_state: Any, *, area_mm2: float) -> pd.DataFrame:
    geometry = _get(session_state, "section_geometry")
    basis_options = build_girder_service_stress_basis_options(
        geometry,
        _section_parameters(session_state),
        member_type=getattr(_session_mode(session_state), "member_type", "beam_girder"),
    )
    basis = basis_options.bases.get("precast_gross")
    if basis is None:
        return pd.DataFrame(
            [{"Station x (m)": 0.0, "Report status": "REVIEW", "Report note": "Precast gross stress basis is unavailable."}]
        )

    span = _span_length_m(session_state)
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    breakdown = _load_breakdown(session_state, precast_area_mm2=area_mm2)
    strand_table = _as_dataframe(_get(session_state, "girder_strand_layout_table"))
    strand_table_arg = None if strand_table.empty else strand_table
    rows: list[dict[str, Any]] = []
    for x_m in _lifting_stations(session_state, span):
        auto_mx = two_point_lifting_moment_kNm(breakdown.total_kN_m, x_m, span, system.lifting_point_ratio)
        auto_vy = two_point_lifting_shear_kN(breakdown.total_kN_m, x_m, span, system.lifting_point_ratio)
        service = run_basic_girder_service_stress(basis, M_kNm=auto_mx)
        pe_kN = 0.0
        yps = None
        ps_top = 0.0
        ps_bottom = 0.0
        active_groups = ""
        try:
            station = evaluate_girder_prestress_station(strand_table_arg, x_m=x_m, span_length_m=span)
            pe_kN = float(station.pe_transfer_eff_kN)
            yps = station.yps_eff_mm_from_bottom
            active_groups = station.active_group_ids
            if pe_kN > 0.0 and yps is not None:
                prestress = run_girder_prestress_stress_effect(
                    basis,
                    Pe_eff_kN=pe_kN,
                    tendon_y_from_bottom_mm=float(yps),
                )
                ps_top = prestress.top.total_stress_MPa
                ps_bottom = prestress.bottom.total_stress_MPa
        except Exception as exc:
            active_groups = f"Prestress unavailable: {exc}"
        top_total = service.top.total_stress_MPa + ps_top
        bottom_total = service.bottom.total_stress_MPa + ps_bottom
        station_type = "midspan"
        a = float(system.lifting_point_ratio) * span
        if abs(x_m) < 1e-6 or abs(x_m - span) < 1e-6:
            station_type = "end / overhang free end"
        elif abs(x_m - a) < 1e-6 or abs(x_m - (span - a)) < 1e-6:
            station_type = "lifting point"
        rows.append(
            {
                "Station x (m)": float(x_m),
                "Station type": station_type,
                "Basis": "Precast gross section",
                "Auto load w (kN/m)": float(breakdown.total_kN_m),
                "Auto Mx (kN-m)": float(auto_mx),
                "Auto Vy (kN)": float(auto_vy),
                "Pe transfer (kN)": float(pe_kN),
                "yps transfer (mm from bottom)": yps,
                "Top service stress (MPa)": float(service.top.total_stress_MPa),
                "Bottom service stress (MPa)": float(service.bottom.total_stress_MPa),
                "Top PS stress (MPa)": float(ps_top),
                "Bottom PS stress (MPa)": float(ps_bottom),
                "Top total stress (MPa)": float(top_total),
                "Bottom total stress (MPa)": float(bottom_total),
                "Max compression (MPa)": float(min(top_total, bottom_total)),
                "Max tension (MPa)": float(max(top_total, bottom_total)),
                "Active PS groups": active_groups,
                "Report note": "Engineering-review preview; local lifting hardware and insert checks excluded.",
            }
        )
    return pd.DataFrame(rows).sort_values("Station x (m)").reset_index(drop=True)


def generic_precast_lifting_governing_rows_dataframe(station_rows: pd.DataFrame) -> pd.DataFrame:
    if station_rows.empty or "Station x (m)" not in station_rows.columns:
        return pd.DataFrame(columns=["Demand", "Station x (m)", "Fiber", "Stress (MPa)", "Report status", "Report note"])
    rows: list[dict[str, Any]] = []
    comp_values = pd.to_numeric(station_rows.get("Max compression (MPa)"), errors="coerce")
    tens_values = pd.to_numeric(station_rows.get("Max tension (MPa)"), errors="coerce")
    if comp_values.notna().any():
        idx = comp_values.idxmin()
        row = station_rows.loc[idx]
        top = float(row.get("Top total stress (MPa)", 0.0) or 0.0)
        bottom = float(row.get("Bottom total stress (MPa)", 0.0) or 0.0)
        fiber = "Top" if top <= bottom else "Bottom"
        rows.append(
            {
                "Demand": "Governing compression",
                "Station x (m)": row.get("Station x (m)"),
                "Station type": row.get("Station type", ""),
                "Fiber": fiber,
                "Stress (MPa)": min(top, bottom),
                "Report status": "REVIEW",
                "Report note": "Compare against project transfer/lifting compression limit before certification.",
            }
        )
    if tens_values.notna().any():
        idx = tens_values.idxmax()
        row = station_rows.loc[idx]
        top = float(row.get("Top total stress (MPa)", 0.0) or 0.0)
        bottom = float(row.get("Bottom total stress (MPa)", 0.0) or 0.0)
        fiber = "Top" if top >= bottom else "Bottom"
        rows.append(
            {
                "Demand": "Governing tension",
                "Station x (m)": row.get("Station x (m)"),
                "Station type": row.get("Station type", ""),
                "Fiber": fiber,
                "Stress (MPa)": max(top, bottom),
                "Report status": "REVIEW",
                "Report note": "Compare against project transfer/lifting tension limit and crack-control/detailing requirements.",
            }
        )
    return pd.DataFrame(rows, columns=["Demand", "Station x (m)", "Station type", "Fiber", "Stress (MPa)", "Report status", "Report note"])


def generic_precast_lifting_closeout_guard_dataframe(*, warnings: list[str]) -> pd.DataFrame:
    rows = [
        {
            "Closeout Item": "Generic precast lifting report tables",
            "Status": "AVAILABLE",
            "Evidence / Boundary": "Scope, settings, load basis, station stress rows, and governing rows are generated for report/export.",
        },
        {
            "Closeout Item": "Load-basis guardrail",
            "Status": "LOCKED",
            "Evidence / Boundary": "Only individual precast unit self-weight × lifting IF is included. SDL/LL/deck/assembly loads are excluded.",
        },
        {
            "Closeout Item": "Certification boundary",
            "Status": "REVIEW",
            "Evidence / Boundary": "; ".join(GENERIC_PRECAST_LIFTING_REPORT_EXCLUSIONS),
        },
        {
            "Closeout Item": "Warnings",
            "Status": "REVIEW" if warnings else "CLEAR",
            "Evidence / Boundary": "; ".join(warnings) if warnings else "No package-generation warnings.",
        },
    ]
    return pd.DataFrame(rows, columns=["Closeout Item", "Status", "Evidence / Boundary"])


def build_generic_precast_lifting_report_package(session_state: Any) -> GenericPrecastLiftingReportPackage:
    """Build report/export tables for existing generic precast lifting preview."""

    if not is_generic_precast_lifting_report_context(session_state):
        return GenericPrecastLiftingReportPackage(False, "NOT_APPLICABLE")
    geometry = _get(session_state, "section_geometry")
    if geometry is None:
        return GenericPrecastLiftingReportPackage(False, "REVIEW", warnings=["Generic precast lifting report context was detected, but section geometry is missing."])
    warnings: list[str] = []
    try:
        summary = summarize_geometry(geometry)
        area_mm2 = float(summary.area_mm2)
        station_rows = generic_precast_lifting_station_stress_dataframe(session_state, area_mm2=area_mm2)
        governing = generic_precast_lifting_governing_rows_dataframe(station_rows)
    except Exception as exc:
        return GenericPrecastLiftingReportPackage(
            False,
            "REVIEW",
            warnings=[f"Generic precast lifting report package could not be generated: {exc}"],
        )
    if station_rows.empty:
        warnings.append("No generic lifting station stress rows were generated; review section geometry and span settings.")
    return GenericPrecastLiftingReportPackage(
        True,
        GENERIC_PRECAST_LIFTING_REPORT_STATUS,
        warnings=warnings,
        scope=generic_precast_lifting_scope_dataframe(),
        settings=generic_precast_lifting_settings_dataframe(session_state, area_mm2=area_mm2),
        load_basis=generic_precast_lifting_load_basis_dataframe(session_state, area_mm2=area_mm2),
        station_stress_rows=station_rows,
        governing_rows=governing,
        closeout_guard=generic_precast_lifting_closeout_guard_dataframe(warnings=warnings),
    )


def generic_precast_lifting_report_tables_to_dataframe(package: GenericPrecastLiftingReportPackage) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, table in package.tables().items():
        rows.append(
            {
                "Table Key": key,
                "Available": bool(package.available and isinstance(table, pd.DataFrame) and not table.empty),
                "Row Count": len(table) if isinstance(table, pd.DataFrame) else 0,
                "Report Status": package.status,
            }
        )
    return pd.DataFrame(rows, columns=["Table Key", "Available", "Row Count", "Report Status"])

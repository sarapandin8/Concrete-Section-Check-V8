"""Guarded Railway U-Girder ULS strength-check framework helpers.

ULS.RAIL.UGIRDER1 is a controlled bridge from the closed-out Railway U-Girder
SLS review package to a future final-design workflow.  It deliberately builds
code-basis/readiness/demand tables and a check matrix without promoting the
current application to final code-certified design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping

import pandas as pd
from shapely.geometry import LineString

from concrete_pmm_pro.analysis.capacity_check import check_uls_demands_against_rc_pmm
from concrete_pmm_pro.analysis.pmm_solver import run_rc_pmm_solver
from concrete_pmm_pro.analysis.uls_flexure_code_basis import apply_flexure_code_basis, beam_girder_flexure_code_basis
from concrete_pmm_pro.analysis.uls_strength_routing import bridge_beam_girder_uls_strength_route
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial, SectionGeometry
from concrete_pmm_pro.core.reinforcement_system import effective_prestress_for_analysis, effective_rebars_for_analysis, ordinary_rebar_enabled
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.serviceability.girder_prestress_station import (
    active_girder_strand_rows,
    active_strand_groups_at_station,
    debonded_strand_count_for_row,
)
from concrete_pmm_pro.serviceability.girder_sls_load_components import BEAM_GIRDER_SYSTEM_SETTINGS_KEY, system_settings_from_mapping

RAILWAY_UGIRDER_ULS_FRAMEWORK_STATUS = "Railway U-Girder ULS Strength Check Framework - Guarded Review Ready"
RAILWAY_UGIRDER_ULS_FRAMEWORK_WARNING = (
    "ULS.RAIL.UGIRDER1 provides a guarded ULS strength-check framework and traceability matrix only. "
    "It is not final code-certified design and must not be used as an engineer certification."
)
RAILWAY_UGIRDER_ULS_CERTIFICATION_BOUNDARY = (
    "Framework-ready means ULS demand routing, code-basis guardrails, and check-readiness evidence are visible. "
    "Final design still requires validated Railway U-Girder flexure, shear, torsion, V+T, prestress development, "
    "anchorage/end-zone, time-dependent behavior, and Engineer-of-Record review."
)
RAILWAY_UGIRDER_ULS_REQUIRED_FUTURE_CHECKS = [
    "Railway U-Girder flexure calculation evidence benchmark validation",
    "PSC shear route including prestress effects, dv policy, and end-region checks",
    "Railway U-Girder torsion and combined V+T interaction",
    "transfer length force ramp",
    "development length benchmark validation and debonded strand anchorage detailing beyond this guarded evidence table",
    "anchorage / end-zone bursting and spalling benchmark validation beyond guarded evidence",
    "lifting insert / local hardware check",
    "creep/shrinkage and time-dependent composite redistribution",
    "independent benchmark examples and final design report traceability",
]
RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_STATUS = "Railway U-Girder ULS Flexure Calculation Evidence - Engineering Review Ready"
RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_WARNING = (
    "ULS.RAIL.UGIRDER2 adds Railway U-Girder flexure section-strength calculation evidence using the existing "
    "strain-compatibility PMM engine and AASHTO LRFD prestressed flexure phi-routing layer. It remains engineering-review "
    "evidence only because Railway U-Girder-specific benchmark validation, development length, anchorage/end-zone, "
    "and time-dependent composite redistribution are not completed."
)
RAILWAY_UGIRDER_ULS_SHEAR_EVIDENCE_STATUS = "Railway U-Girder ULS PSC Shear Route Evidence - Engineering Review Ready"
RAILWAY_UGIRDER_ULS_SHEAR_EVIDENCE_WARNING = (
    "ULS.RAIL.UGIRDER3 adds a guarded Railway U-Girder PSC shear route using the active ULS Vuy station "
    "demand, active provided-stirrup zones, an AASHTO LRFD-compatible sectional shear gate, and explicit d/dv "
    "basis notes. It remains engineering-review evidence only because refined PSC Vci/Vcw/Vp, end-region, "
    "development length, anchorage, and benchmark validation are not completed."
)
RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_STATUS = "Railway U-Girder ULS Torsion / V+T Guard - Engineering Review Ready"
RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_WARNING = (
    "ULS.RAIL.UGIRDER4 adds a guarded Railway U-Girder torsion and combined V+T evidence gate using active Tu/Vuy "
    "station demands, active closed-hoop transverse zones, ordinary longitudinal rebar as the Al source of truth, "
    "and an explicit linear interaction review index. It remains engineering-review evidence only because Railway "
    "U-Girder-specific multi-cell/closed-path calibration, refined PSC torsion effects, V+T code calibration, "
    "development length, anchorage/end-zone, and benchmark validation are not completed."
)
RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_STATUS = "Railway U-Girder Prestress Transfer / Development Evidence - Engineering Review Ready"
RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_WARNING = (
    "PRESTRESS.DEVELOPMENT1 adds guarded transfer-length and development-length evidence for Railway U-Girder "
    "strand rows using the active strand/debonding table and a visible AASHTO/ACI-compatible screening basis. "
    "It does not ramp prestress force in the SLS/ULS solvers, does not certify debonded strand development, "
    "and does not replace anchorage/end-zone bursting or Engineer-of-Record review."
)
RAILWAY_UGIRDER_ANCHORAGE_END_ZONE_STATUS = "Railway U-Girder Anchorage / End-Zone Evidence - Engineering Review Ready"
RAILWAY_UGIRDER_ANCHORAGE_END_ZONE_WARNING = (
    "ANCHORAGE.RAIL.UGIRDER1 adds guarded anchorage/end-zone bursting and spalling evidence for Railway U-Girder "
    "pretensioned strand release zones using active strand/debonding rows, web f'ci, and visible end-zone force screens. "
    "It does not design final anchorage-zone reinforcement, does not validate debonded strand termination detailing, "
    "and does not replace project-specific end-region detailing or Engineer-of-Record review."
)
RAILWAY_UGIRDER_ULS_MAX_FLEXURE_EVIDENCE_ROWS = 8
RAILWAY_UGIRDER_ULS_MAX_SHEAR_EVIDENCE_ROWS = 12
RAILWAY_UGIRDER_ULS_MAX_TORSION_VT_GUARD_ROWS = 16
RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_MAX_ROWS = 24
_GIRDER_STRAND_FPU_MPA_DEFAULT = 1860.0
_GIRDER_STRAND_FPY_MPA_DEFAULT = 1670.0
_GIRDER_STRAND_EP_MPA_DEFAULT = 195000.0
_ULS_DEMAND_TOL = 1.0e-9

RAILWAY_UGIRDER_ULS_TABLE_KEYS = [
    "railway_u_girder_uls_closeout_boundary",
    "railway_u_girder_uls_code_basis",
    "railway_u_girder_uls_demand_summary",
    "railway_u_girder_uls_flexure_evidence",
    "railway_u_girder_uls_shear_evidence",
    "railway_u_girder_uls_torsion_vt_guard",
    "railway_u_girder_prestress_development_evidence",
    "railway_u_girder_anchorage_end_zone_evidence",
    "railway_u_girder_uls_check_matrix",
    "railway_u_girder_uls_future_checks",
]


@dataclass(frozen=True)
class RailwayUGirderULSFrameworkPackage:
    """Report-ready tables for the guarded Railway U-Girder ULS framework."""

    available: bool
    status: str
    closeout_boundary: pd.DataFrame = field(default_factory=pd.DataFrame)
    code_basis: pd.DataFrame = field(default_factory=pd.DataFrame)
    demand_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    flexure_evidence: pd.DataFrame = field(default_factory=pd.DataFrame)
    shear_evidence: pd.DataFrame = field(default_factory=pd.DataFrame)
    torsion_vt_guard: pd.DataFrame = field(default_factory=pd.DataFrame)
    prestress_development_evidence: pd.DataFrame = field(default_factory=pd.DataFrame)
    anchorage_end_zone_evidence: pd.DataFrame = field(default_factory=pd.DataFrame)
    check_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    future_checks: pd.DataFrame = field(default_factory=pd.DataFrame)
    warnings: list[str] = field(default_factory=list)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "railway_u_girder_uls_closeout_boundary": self.closeout_boundary,
            "railway_u_girder_uls_code_basis": self.code_basis,
            "railway_u_girder_uls_demand_summary": self.demand_summary,
            "railway_u_girder_uls_flexure_evidence": self.flexure_evidence,
            "railway_u_girder_uls_shear_evidence": self.shear_evidence,
            "railway_u_girder_uls_torsion_vt_guard": self.torsion_vt_guard,
            "railway_u_girder_prestress_development_evidence": self.prestress_development_evidence,
            "railway_u_girder_anchorage_end_zone_evidence": self.anchorage_end_zone_evidence,
            "railway_u_girder_uls_check_matrix": self.check_matrix,
            "railway_u_girder_uls_future_checks": self.future_checks,
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


def _to_dataframe(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(value).copy()
    except Exception:
        return pd.DataFrame()


def _float_or_zero(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(numeric):
        return 0.0
    return float(numeric)


def is_railway_u_girder_uls_context(session_state: Any) -> bool:
    """Return True when current project context is the Railway U-Girder preset."""

    geometry = _get(session_state, "section_geometry")
    metadata = getattr(geometry, "metadata", {}) or {}
    if isinstance(metadata, Mapping):
        for key in ("preset", "generator", "preset_key", "section_preset_key"):
            if str(metadata.get(key) or "").strip().casefold() == "railway_u_girder":
                return True
    geometry_name = str(getattr(geometry, "name", "") or "").casefold()
    if "railway" in geometry_name and "u-girder" in geometry_name:
        return True
    for state_key in ("section_preset_key", "section_preset_name", "active_section_preset_name"):
        text = str(_get(session_state, state_key, "") or "").casefold()
        if text == "railway_u_girder" or ("railway" in text and "u-girder" in text):
            return True
    params = _get(session_state, "section_parameters", {})
    if isinstance(params, Mapping):
        required = {"h1_step_height_mm", "h2_bottom_opening_mm", "h3_floor_side_thickness_mm", "h4_floor_center_thickness_mm"}
        if required.issubset({str(key) for key in params.keys()}):
            return True
    return False


def active_railway_u_girder_uls_demand_dataframe(session_state: Any) -> pd.DataFrame:
    """Return active ULS station-demand rows from Loads for Railway U-Girder checks."""

    columns = ["Active", "Station x (m)", "Case Name", "Mux", "Vuy", "Tu", "Muy", "Vux", "Nu", "Note"]
    table = _to_dataframe(_get(session_state, "beam_uls_loads_table", None))
    if not table.empty:
        for column in columns:
            if column not in table.columns:
                table[column] = "" if column in {"Case Name", "Note"} else 0.0
        table = table[columns].copy()
        active_mask = table["Active"].map(lambda value: bool(value) if not isinstance(value, str) else value.strip().casefold() not in {"false", "0", "no", "n", "off", ""})
        table = table.loc[active_mask].copy()
    else:
        rows: list[dict[str, Any]] = []
        for load in list(_get(session_state, "load_cases", []) or []):
            if not bool(_get(load, "active", True)):
                continue
            if str(_get(load, "load_type", "") or "").strip().upper() != "ULS":
                continue
            rows.append(
                {
                    "Active": True,
                    "Station x (m)": 0.0,
                    "Case Name": _get(load, "name", "ULS"),
                    "Mux": _float_or_zero(_get(load, "Mux_Nmm", 0.0)) / 1.0e6,
                    "Vuy": 0.0,
                    "Tu": 0.0,
                    "Muy": _float_or_zero(_get(load, "Muy_Nmm", 0.0)) / 1.0e6,
                    "Vux": 0.0,
                    "Nu": _float_or_zero(_get(load, "Pu_N", 0.0)) / 1.0e3,
                    "Note": _get(load, "note", "ULS LoadCase fallback; station/resultants should be defined in Loads table for girder design."),
                }
            )
        table = pd.DataFrame(rows, columns=columns)
    for numeric_column in ["Station x (m)", "Mux", "Vuy", "Tu", "Muy", "Vux", "Nu"]:
        table[numeric_column] = pd.to_numeric(table.get(numeric_column, pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    return table.reset_index(drop=True)




def _as_model(value: Any, model_type: Any) -> Any | None:
    if isinstance(value, model_type):
        return value
    if isinstance(value, Mapping):
        try:
            return model_type.model_validate(value)
        except Exception:
            return None
    return None


def _railway_uls_concrete_material_from_state(session_state: Any) -> ConcreteMaterial | None:
    """Return the concrete material used by the guarded ULS flexure evidence.

    ULS.RAIL.UGIRDER2 intentionally uses a single current PMM concrete material.
    For Railway U-Girder projects, the preferred source is the active concrete
    material if already assigned; otherwise the web f'c from stage settings is
    used.  The differential web/slab material model remains a certification
    blocker and is disclosed in the evidence table.
    """

    concrete = _as_model(_get(session_state, "concrete_material", None), ConcreteMaterial)
    if concrete is not None:
        return concrete
    stage = _get(session_state, "railway_u_girder_stage_settings", {}) or {}
    fc = _float_or_zero(_get(stage, "web_fc_MPa", 45.0)) or 45.0
    try:
        return ConcreteMaterial(name="Railway U-Girder ULS review concrete - web f'c", fc_MPa=float(fc))
    except Exception:
        return None


def _railway_uls_section_geometry_from_state(session_state: Any) -> SectionGeometry | None:
    return _as_model(_get(session_state, "section_geometry", None), SectionGeometry)


def _railway_uls_analysis_settings_from_state(session_state: Any) -> AnalysisSettings:
    raw = _get(session_state, "analysis_settings", None)
    if isinstance(raw, AnalysisSettings):
        settings = raw
    elif isinstance(raw, Mapping):
        try:
            settings = AnalysisSettings.model_validate(raw)
        except Exception:
            settings = AnalysisSettings()
    else:
        settings = AnalysisSettings()
    return settings.model_copy(
        update={
            "code": "AASHTO LRFD",
            "include_rebars": True,
            "include_prestress": True,
            "use_phi_factor": True,
            # Keep report/QA generation responsive while preserving the shared
            # strain-compatibility engine.  This is calculation evidence, not a
            # final certification benchmark run.
            "neutral_axis_angle_steps": 12,
            "neutral_axis_depth_steps": 36,
        }
    )


def _railway_uls_span_length_m(session_state: Any) -> float:
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY, None))
    try:
        span = float(system.span_length_m)
    except (TypeError, ValueError):
        span = 10.0
    return span if span > 0.0 else 10.0


def _railway_uls_section_bounds(geometry: SectionGeometry) -> tuple[float, float, float, float]:
    polygon = to_shapely_polygon(geometry)
    minx, miny, maxx, maxy = polygon.bounds
    return float(minx), float(miny), float(maxx), float(maxy)


def _railway_uls_model_list(value: Any, model_type: Any) -> list[Any]:
    rows = [] if value is None else list(value)
    models: list[Any] = []
    for row in rows:
        parsed = _as_model(row, model_type)
        if parsed is not None:
            models.append(parsed)
    return models


def _railway_uls_girder_strand_elements_for_station(
    session_state: Any,
    *,
    geometry: SectionGeometry,
    x_m: float,
    span_length_m: float,
) -> tuple[list[PrestressElement], list[str]]:
    table = _get(session_state, "girder_strand_layout_table", None)
    if table is None:
        return [], ["No dedicated girder strand layout table is available for ULS flexure evidence."]
    _, y_min, _, _ = _railway_uls_section_bounds(geometry)
    try:
        groups = active_strand_groups_at_station(table, x_m=float(x_m), span_length_m=float(span_length_m))
    except Exception as exc:
        return [], [f"Station strand participation could not be evaluated: {exc}"]
    elements: list[PrestressElement] = []
    for group in groups:
        if group.no_strands <= 0 or group.area_per_strand_mm2 <= 0.0:
            continue
        pe_final_per_strand_n = max(0.0, float(group.pe_eff_final_per_strand_kN)) * 1000.0
        initial_stress_mpa = pe_final_per_strand_n / float(group.area_per_strand_mm2) if group.area_per_strand_mm2 > 0.0 else 0.0
        elements.append(
            PrestressElement(
                x_mm=0.0,
                y_mm=float(y_min) + float(group.y_mm_from_bottom),
                area_mm2=float(group.area_per_strand_mm2),
                steel_type="strand",
                material_name="Girder strand layout",
                fpy_mpa=_GIRDER_STRAND_FPY_MPA_DEFAULT,
                fpu_mpa=_GIRDER_STRAND_FPU_MPA_DEFAULT,
                ep_mpa=_GIRDER_STRAND_EP_MPA_DEFAULT,
                pe_eff_n=pe_final_per_strand_n,
                initial_stress_mpa=initial_stress_mpa,
                initial_strain=initial_stress_mpa / _GIRDER_STRAND_EP_MPA_DEFAULT if initial_stress_mpa > 0.0 else 0.0,
                bonded=True,
                count=int(group.no_strands),
                label=f"{group.group_id} @ x={float(x_m):.3f} m",
            )
        )
    if not elements:
        return [], ["No effective bonded strand group is available at this station; debonding/development must be reviewed."]
    return elements, [f"{sum(element.count for element in elements)} effective strand(s) included at x={float(x_m):.3f} m by the PS5 step-function debonding handoff."]


def _railway_uls_analysis_input_for_flexure_row(
    session_state: Any,
    *,
    row: Mapping[str, Any],
) -> tuple[AnalysisInput | None, list[str]]:
    messages: list[str] = []
    geometry = _railway_uls_section_geometry_from_state(session_state)
    concrete = _railway_uls_concrete_material_from_state(session_state)
    if geometry is None:
        return None, ["Section geometry is missing."]
    if concrete is None:
        return None, ["Concrete material / web f'c stage setting is missing."]
    settings = _railway_uls_analysis_settings_from_state(session_state)
    rebars = _railway_uls_model_list(_get(session_state, "rebars", []) or [], Rebar)
    rebars = list(rebars)  # ordinary rebar is preserved when the engineer enabled it.
    rebar_materials = _railway_uls_model_list(_get(session_state, "rebar_materials", []) or [], RebarMaterial)
    generic_prestress = _railway_uls_model_list(_get(session_state, "prestress_elements", []) or [], PrestressElement)
    generic_prestress = effective_prestress_for_analysis(generic_prestress, session_state, settings)
    span_m = _railway_uls_span_length_m(session_state)
    station_m = _float_or_zero(row.get("Station x (m)"))
    station_m = max(0.0, min(float(station_m), span_m))
    strand_elements, strand_messages = _railway_uls_girder_strand_elements_for_station(
        session_state,
        geometry=geometry,
        x_m=station_m,
        span_length_m=span_m,
    )
    messages.extend(strand_messages)
    prestress_elements = [*generic_prestress, *strand_elements]
    if not rebars and not prestress_elements:
        return None, messages + ["No active ordinary rebar or bonded prestress is available for flexure evidence."]
    mux = _float_or_zero(row.get("Mux"))
    if abs(mux) <= _ULS_DEMAND_TOL:
        return None, messages + ["Mux demand is zero; zero-moment rows are tracked in demand summary but excluded from flexure D/C evidence."]
    nu = _float_or_zero(row.get("Nu"))
    case = str(row.get("Case Name") or "ULS").strip() or "ULS"
    load = LoadCase(
        name=f"{case} @ x={station_m:.3f} m",
        Pu_N=float(nu) * 1000.0,
        Mux_Nmm=float(mux) * 1_000_000.0,
        Muy_Nmm=0.0,
        load_type="ULS",
        active=True,
    )
    return (
        AnalysisInput(
            section_geometry=geometry,
            concrete_material=concrete,
            rebar_materials=rebar_materials,
            prestress_materials=[],
            rebars=rebars,
            prestress_elements=prestress_elements,
            load_cases=[load],
            settings=settings,
        ),
        messages,
    )



def _railway_uls_analysis_input_for_station_row(
    session_state: Any,
    *,
    row: Mapping[str, Any],
) -> tuple[AnalysisInput | None, list[str]]:
    """Return an AnalysisInput for non-PMM station evidence such as shear.

    Unlike the flexure-specific builder, this helper intentionally allows zero
    Mux rows because peak shear is normally near the supports where bending can
    be small or zero in imported station resultants.
    """

    messages: list[str] = []
    geometry = _railway_uls_section_geometry_from_state(session_state)
    concrete = _railway_uls_concrete_material_from_state(session_state)
    if geometry is None:
        return None, ["Section geometry is missing."]
    if concrete is None:
        return None, ["Concrete material / web f'c stage setting is missing."]
    settings = _railway_uls_analysis_settings_from_state(session_state)
    rebars = _railway_uls_model_list(_get(session_state, "rebars", []) or [], Rebar)
    rebar_materials = _railway_uls_model_list(_get(session_state, "rebar_materials", []) or [], RebarMaterial)
    generic_prestress = _railway_uls_model_list(_get(session_state, "prestress_elements", []) or [], PrestressElement)
    generic_prestress = effective_prestress_for_analysis(generic_prestress, session_state, settings)
    span_m = _railway_uls_span_length_m(session_state)
    station_m = _float_or_zero(row.get("Station x (m)"))
    station_m = max(0.0, min(float(station_m), span_m))
    strand_elements, strand_messages = _railway_uls_girder_strand_elements_for_station(
        session_state,
        geometry=geometry,
        x_m=station_m,
        span_length_m=span_m,
    )
    messages.extend(strand_messages)
    prestress_elements = [*generic_prestress, *strand_elements]
    if not rebars and not prestress_elements:
        return None, messages + ["No active ordinary rebar or bonded prestress is available for station evidence."]
    case = str(row.get("Case Name") or "ULS").strip() or "ULS"
    load = LoadCase(
        name=f"{case} @ x={station_m:.3f} m",
        Pu_N=float(_float_or_zero(row.get("Nu"))) * 1000.0,
        Mux_Nmm=float(_float_or_zero(row.get("Mux"))) * 1_000_000.0,
        Muy_Nmm=float(_float_or_zero(row.get("Muy"))) * 1_000_000.0,
        load_type="ULS",
        active=True,
    )
    return (
        AnalysisInput(
            section_geometry=geometry,
            concrete_material=concrete,
            rebar_materials=rebar_materials,
            prestress_materials=[],
            rebars=rebars,
            prestress_elements=prestress_elements,
            load_cases=[load],
            settings=settings,
        ),
        messages,
    )

def _railway_uls_nominal_flexure_capacity_nmm(analysis_input: AnalysisInput) -> tuple[float | None, list[str]]:
    messages: list[str] = []
    try:
        nominal_settings = analysis_input.settings.model_copy(update={"use_phi_factor": False})
        nominal_input = analysis_input.model_copy(update={"settings": nominal_settings})
        nominal_pmm = run_rc_pmm_solver(nominal_input)
        nominal_summary = check_uls_demands_against_rc_pmm(nominal_pmm, nominal_input.load_cases)
        nominal_result = nominal_summary.results[0] if nominal_summary.results else None
    except Exception as exc:
        return None, [f"Nominal flexure evidence solve failed: {exc}"]
    if nominal_result is None or nominal_result.capacity_phiMn_Nmm is None:
        return None, ["Nominal Mn could not be interpolated from the PMM point cloud."]
    if nominal_result.warning_count:
        messages.append(f"Nominal-capacity interpolation carried {nominal_result.warning_count} warning(s).")
    return float(nominal_result.capacity_phiMn_Nmm), messages


def _railway_uls_has_bonded_prestress(analysis_input: AnalysisInput | None) -> bool:
    if analysis_input is None:
        return False
    return any(element.bonded and element.count > 0 and element.area_mm2 > 0.0 for element in analysis_input.prestress_elements)


def _railway_uls_flexure_evidence_columns() -> list[str]:
    return [
        "Check",
        "Status",
        "Governing x (m)",
        "Case",
        "Demand Mux (kN-m)",
        "Nominal Mn (kN-m)",
        "φ",
        "φMn (kN-m)",
        "D/C",
        "Bending direction",
        "Tension face",
        "Effective strands",
        "Concrete basis",
        "Code basis",
        "Method",
        "Evidence status",
        "Blocked final claim",
        "Notes",
    ]


def railway_u_girder_uls_flexure_evidence_dataframe(session_state: Any, active_uls: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return guarded station flexure D/C evidence for Railway U-Girder ULS.

    ULS.RAIL.UGIRDER2 deliberately exposes calculation evidence, not final
    certification.  It uses the existing section PMM/strain-compatibility solver
    and the AASHTO LRFD prestressed flexure phi layer.  Remaining blockers are
    reported in every row so PASS/FAIL cannot be mistaken for code-certified
    girder design.
    """

    columns = _railway_uls_flexure_evidence_columns()
    active = active_uls.copy() if isinstance(active_uls, pd.DataFrame) else active_railway_u_girder_uls_demand_dataframe(session_state)
    if active.empty:
        return pd.DataFrame(columns=columns)
    active["__mux"] = pd.to_numeric(active.get("Mux", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    candidates = active.loc[active["__mux"].abs() > _ULS_DEMAND_TOL].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)
    if len(candidates.index) > RAILWAY_UGIRDER_ULS_MAX_FLEXURE_EVIDENCE_ROWS:
        candidates = candidates.head(RAILWAY_UGIRDER_ULS_MAX_FLEXURE_EVIDENCE_ROWS).copy()
    rows: list[dict[str, Any]] = []
    for _, demand_row in candidates.iterrows():
        case = str(demand_row.get("Case Name") or "ULS")
        station = _float_or_zero(demand_row.get("Station x (m)"))
        demand = _float_or_zero(demand_row.get("Mux"))
        analysis_input, input_messages = _railway_uls_analysis_input_for_flexure_row(session_state, row=demand_row)
        if analysis_input is None:
            rows.append(
                {
                    "Check": "ULS flexure",
                    "Status": "REVIEW",
                    "Governing x (m)": station,
                    "Case": case,
                    "Demand Mux (kN-m)": demand,
                    "Nominal Mn (kN-m)": float("nan"),
                    "φ": float("nan"),
                    "φMn (kN-m)": float("nan"),
                    "D/C": float("nan"),
                    "Bending direction": "Sagging (+Mux)" if demand > 0.0 else "Hogging (-Mux)",
                    "Tension face": "Bottom face" if demand > 0.0 else "Top face",
                    "Effective strands": 0,
                    "Concrete basis": "single-material PMM evidence",
                    "Code basis": "AASHTO LRFD prestressed flexure route - not certified",
                    "Method": "not ready",
                    "Evidence status": RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_STATUS,
                    "Blocked final claim": "No final certification without benchmarks, development length, anchorage/end-zone, and time-dependent checks.",
                    "Notes": "; ".join(input_messages),
                }
            )
            continue
        flexure_basis = beam_girder_flexure_code_basis(
            bridge_beam_girder_uls_strength_route(),
            has_bonded_prestress=_railway_uls_has_bonded_prestress(analysis_input),
        )
        try:
            pmm_result = run_rc_pmm_solver(analysis_input)
            dc_summary = check_uls_demands_against_rc_pmm(pmm_result, analysis_input.load_cases)
            dc_result = dc_summary.results[0] if dc_summary.results else None
        except Exception as exc:
            rows.append(
                {
                    "Check": "ULS flexure",
                    "Status": "REVIEW",
                    "Governing x (m)": station,
                    "Case": case,
                    "Demand Mux (kN-m)": demand,
                    "Nominal Mn (kN-m)": float("nan"),
                    "φ": float("nan"),
                    "φMn (kN-m)": float("nan"),
                    "D/C": float("nan"),
                    "Bending direction": "Sagging (+Mux)" if demand > 0.0 else "Hogging (-Mux)",
                    "Tension face": "Bottom face" if demand > 0.0 else "Top face",
                    "Effective strands": sum(element.count for element in analysis_input.prestress_elements),
                    "Concrete basis": "single-material PMM evidence",
                    "Code basis": flexure_basis.capacity_label,
                    "Method": "solver error",
                    "Evidence status": RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_STATUS,
                    "Blocked final claim": "No final certification from a failed evidence solve.",
                    "Notes": f"Flexure evidence solve failed: {exc}",
                }
            )
            continue
        nominal_nmm, nominal_messages = _railway_uls_nominal_flexure_capacity_nmm(analysis_input)
        phi_capacity_nmm = None if dc_result is None else dc_result.capacity_phiMn_Nmm
        routed_capacity_nmm, routed_note = apply_flexure_code_basis(
            phi_capacity_nmm=phi_capacity_nmm,
            nominal_capacity_nmm=nominal_nmm,
            basis=flexure_basis,
        )
        phi_value = float("nan")
        if nominal_nmm is not None and nominal_nmm > 0.0 and routed_capacity_nmm is not None:
            phi_value = float(routed_capacity_nmm) / float(nominal_nmm)
        capacity_kNm = float(routed_capacity_nmm) / 1_000_000.0 if routed_capacity_nmm is not None else float("nan")
        nominal_kNm = float(nominal_nmm) / 1_000_000.0 if nominal_nmm is not None else float("nan")
        dc_value = abs(float(demand)) / capacity_kNm if capacity_kNm and pd.notna(capacity_kNm) and capacity_kNm > 0.0 else float("nan")
        status = "Engineering Review PASS" if pd.notna(dc_value) and dc_value <= 1.0 else "Engineering Review FAIL" if pd.notna(dc_value) else "REVIEW"
        notes = [
            RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_WARNING,
            "Section-strength evidence uses current PMM single-concrete-material model; differential web/slab material and final composite calibration remain future work.",
            routed_note,
        ]
        notes.extend(input_messages)
        notes.extend(nominal_messages)
        rows.append(
            {
                "Check": "ULS flexure",
                "Status": status,
                "Governing x (m)": station,
                "Case": case,
                "Demand Mux (kN-m)": float(demand),
                "Nominal Mn (kN-m)": nominal_kNm,
                "φ": phi_value,
                "φMn (kN-m)": capacity_kNm,
                "D/C": dc_value,
                "Bending direction": "Sagging (+Mux)" if demand > 0.0 else "Hogging (-Mux)",
                "Tension face": "Bottom face" if demand > 0.0 else "Top face",
                "Effective strands": sum(element.count for element in analysis_input.prestress_elements),
                "Concrete basis": f"{analysis_input.concrete_material.name}; f'c={analysis_input.concrete_material.fc_MPa:g} MPa; single-material evidence",
                "Code basis": flexure_basis.capacity_label,
                "Method": flexure_basis.method_label,
                "Evidence status": RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_STATUS,
                "Blocked final claim": "No code-certified or engineer-certified PASS until flexure benchmarks, development length, anchorage/end-zone, and time-dependent composite checks are complete.",
                "Notes": "; ".join([str(item) for item in notes if str(item).strip()]),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _railway_uls_linework_length_mm(geometry: Any) -> float:
    if geometry is None or getattr(geometry, "is_empty", True):
        return 0.0
    geom_type = getattr(geometry, "geom_type", "")
    if geom_type in {"LineString", "LinearRing"}:
        try:
            return float(geometry.length)
        except Exception:
            return 0.0
    if hasattr(geometry, "geoms"):
        return sum(_railway_uls_linework_length_mm(item) for item in geometry.geoms)
    return 0.0


def _railway_uls_web_width_mm(geometry: SectionGeometry) -> tuple[float | None, str]:
    """Estimate total vertical shear-web width for a Railway U-Girder polygon."""

    try:
        polygon = to_shapely_polygon(geometry)
        minx, miny, maxx, maxy = polygon.bounds
    except Exception:
        return None, "Web width unavailable: section polygon could not be read."
    h = float(maxy) - float(miny)
    b = float(maxx) - float(minx)
    if h <= 0.0 or b <= 0.0:
        return None, "Web width unavailable: invalid section bounds."
    widths: list[float] = []
    # Avoid the bottom slab/flange and the open top; sample through the side-wall region.
    for ratio in (0.40, 0.50, 0.60, 0.67, 0.75, 0.82):
        y = float(miny) + ratio * h
        line = LineString([(float(minx) - b, y), (float(maxx) + b, y)])
        try:
            width = _railway_uls_linework_length_mm(polygon.intersection(line))
        except Exception:
            width = 0.0
        if width > 1.0:
            widths.append(width)
    if not widths:
        return None, "Web width unavailable: no positive horizontal material width found through the side-wall region."
    return float(min(widths)), "Total web width estimated from minimum material intercept through the Railway U-Girder side-wall region."


def _railway_uls_reinforcement_y_centroid_for_face(analysis_input: AnalysisInput, *, tension_face: str) -> float | None:
    try:
        _, y_min, _, y_max = _railway_uls_section_bounds(analysis_input.section_geometry)
    except Exception:
        return None
    h = float(y_max) - float(y_min)
    if h <= 0.0:
        return None
    if tension_face == "top":
        limit = float(y_min) + 0.55 * h
        candidates = [(float(bar.y_mm), float(bar.area_mm2)) for bar in analysis_input.rebars if float(bar.y_mm) >= limit]
        candidates.extend((float(ps.y_mm), float(ps.area_mm2) * int(ps.count)) for ps in analysis_input.prestress_elements if float(ps.y_mm) >= limit)
    else:
        limit = float(y_min) + 0.45 * h
        candidates = [(float(bar.y_mm), float(bar.area_mm2)) for bar in analysis_input.rebars if float(bar.y_mm) <= limit]
        candidates.extend((float(ps.y_mm), float(ps.area_mm2) * int(ps.count)) for ps in analysis_input.prestress_elements if float(ps.y_mm) <= limit)
    area = sum(area for _, area in candidates if area > 0.0)
    if area <= 0.0:
        return None
    return sum(y * area for y, area in candidates if area > 0.0) / area


def _railway_uls_bridge_dv_from_depth_mm(d_eff_mm: float, h_mm: float) -> float:
    if not all(math.isfinite(value) and value > 0.0 for value in [d_eff_mm, h_mm]):
        return float("nan")
    return max(0.72 * float(h_mm), min(0.90 * float(d_eff_mm), float(d_eff_mm)))


def _railway_uls_effective_shear_depth_values_mm(
    session_state: Any,
    analysis_input: AnalysisInput,
    *,
    mux_kNm: float,
) -> dict[str, Any]:
    try:
        _, y_min, _, y_max = _railway_uls_section_bounds(analysis_input.section_geometry)
    except Exception:
        return {"d_mm": float("nan"), "dv_mm": float("nan"), "h_mm": float("nan"), "tension_face": "-", "note": "Effective shear depth unavailable: section bounds could not be read."}
    h = float(y_max) - float(y_min)
    if h <= 0.0:
        return {"d_mm": float("nan"), "dv_mm": float("nan"), "h_mm": float("nan"), "tension_face": "-", "note": "Effective shear depth unavailable: invalid section depth."}
    tension = "top" if float(mux_kNm) < -_ULS_DEMAND_TOL else "bottom"
    settings = _get(session_state, "beam_girder_shear_depth_settings", {}) or {}
    d_manual = _float_or_zero(_get(settings, "d_mm", 0.0))
    dv_manual = _float_or_zero(_get(settings, "dv_mm", 0.0))
    notes: list[str] = []
    if str(_get(settings, "mode", "") or "").strip() == "Manual d / dv" and 0.0 < d_manual <= 1.05 * h:
        d_eff = float(d_manual)
        notes.append("Effective d read from manual Beam/Girder shear-depth settings.")
    else:
        y_tension = _railway_uls_reinforcement_y_centroid_for_face(analysis_input, tension_face=tension)
        if y_tension is None:
            d_eff = 0.80 * h
            notes.append("Effective d estimated as 0.80h because no active local tension reinforcement centroid was available.")
        elif tension == "top":
            d_eff = float(y_tension) - float(y_min)
            notes.append("Effective d estimated from active reinforcement centroid at top tension face.")
        else:
            d_eff = float(y_max) - float(y_tension)
            notes.append("Effective d estimated from active reinforcement centroid at bottom tension face.")
        d_eff = min(max(float(d_eff), 0.50 * h), 0.95 * h)
    if dv_manual > 0.0:
        dv_eff = float(dv_manual)
        notes.append("Effective dv read from manual Beam/Girder shear-depth settings.")
    else:
        dv_eff = _railway_uls_bridge_dv_from_depth_mm(float(d_eff), h)
        notes.append("Effective dv derived from d and total section depth using the current AASHTO-compatible basis.")
    if _get(settings, "note", ""):
        notes.append(f"Basis note: {_get(settings, 'note')}")
    return {"d_mm": float(d_eff), "dv_mm": float(dv_eff), "h_mm": h, "tension_face": f"{tension} face", "note": " ".join(notes)}


def _railway_uls_shear_reinforcement_dataframe_from_state(session_state: Any) -> pd.DataFrame:
    raw = _get(session_state, "beam_girder_shear_reinforcement_table", None)
    if raw is None:
        raw = (_get(session_state, "project_metadata", {}) or {}).get("beam_girder_shear_reinforcement_table")
    columns = ["Active", "Zone", "x_start_m", "x_end_m", "Bar Size", "Diameter_mm", "Legs", "Spacing_mm", "fy_MPa", "Note"]
    df = pd.DataFrame(raw if raw is not None else [], columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = None
    df = df[columns].copy()
    df["Active"] = df["Active"].map(lambda value: bool(value) if not isinstance(value, str) else value.strip().casefold() not in {"false", "0", "no", "n", "off", ""})
    for column in ["x_start_m", "x_end_m", "Diameter_mm", "Legs", "Spacing_mm", "fy_MPa"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["Zone"] = df["Zone"].map(lambda value: str(value or "").strip())
    df["Bar Size"] = df["Bar Size"].map(lambda value: str(value or "").strip())
    df["Note"] = df["Note"].map(lambda value: str(value or "").strip())
    return df


def _railway_uls_active_shear_zone_for_station(session_state: Any, x_m: float) -> dict[str, Any] | None:
    zones = _railway_uls_shear_reinforcement_dataframe_from_state(session_state)
    if zones.empty:
        return None
    active = zones[zones["Active"]].copy()
    if active.empty:
        return None
    active = active[pd.to_numeric(active["x_start_m"], errors="coerce").notna() & pd.to_numeric(active["x_end_m"], errors="coerce").notna()]
    if active.empty:
        return None
    active["__covers"] = active.apply(lambda row: float(row["x_start_m"]) - 1.0e-9 <= float(x_m) <= float(row["x_end_m"]) + 1.0e-9, axis=1)
    covered = active[active["__covers"]].copy()
    if covered.empty:
        return None
    return covered.sort_values(["x_start_m", "x_end_m"], kind="stable").iloc[0].to_dict()


def _railway_uls_stirrup_area_mm2(zone: Mapping[str, Any]) -> float:
    diameter = _float_or_zero(zone.get("Diameter_mm"))
    if diameter <= 0.0:
        text = str(zone.get("Bar Size") or "").strip().upper().replace("DB", "")
        diameter = _float_or_zero(text)
    if diameter <= 0.0:
        return float("nan")
    return math.pi * diameter * diameter / 4.0


def _railway_uls_shear_detailing_guard(
    *,
    fc_MPa: float,
    bv_mm: float,
    d_eff_mm: float,
    dv_mm: float,
    spacing_mm: float,
    avs_mm2_per_mm: float,
    fy_MPa: float,
) -> dict[str, Any]:
    if not all(math.isfinite(value) and value > 0.0 for value in [fc_MPa, bv_mm, d_eff_mm, dv_mm, spacing_mm, avs_mm2_per_mm, fy_MPa]):
        return {
            "Detailing status": "REVIEW",
            "Av/s required mm2/mm": float("nan"),
            "Av/s required mm2/m": float("nan"),
            "Av/s min D/C": float("nan"),
            "s max mm": float("nan"),
            "Spacing D/C": float("nan"),
            "Detailing D/C value": float("nan"),
            "Detailing notes": "Detailing guard needs finite f'c, bv, d, dv, spacing, Av/s, and fy.",
        }
    avs_required = 0.083 * math.sqrt(float(fc_MPa)) * float(bv_mm) / float(fy_MPa)
    s_max = min(0.80 * float(dv_mm), 600.0)
    avs_dc = float(avs_required) / float(avs_mm2_per_mm) if avs_mm2_per_mm > 0.0 else float("nan")
    spacing_dc = float(spacing_mm) / float(s_max) if s_max > 0.0 else float("nan")
    finite_dcs = [value for value in [avs_dc, spacing_dc] if math.isfinite(value)]
    detailing_dc = max(finite_dcs) if finite_dcs else float("nan")
    if not finite_dcs:
        status = "REVIEW"
        note = "Could not evaluate minimum Av/s or maximum spacing guard."
    elif detailing_dc <= 1.0 + 1.0e-9:
        status = "PASS"
        note = "AASHTO-compatible shear detailing gate checks minimum Av/s and maximum spacing for the active provided zone."
    else:
        status = "FAIL"
        note = "Provided stirrups do not satisfy the AASHTO-compatible minimum Av/s and/or maximum spacing gate."
    return {
        "Detailing status": status,
        "Av/s required mm2/mm": float(avs_required),
        "Av/s required mm2/m": float(avs_required) * 1000.0,
        "Av/s min D/C": avs_dc,
        "s max mm": float(s_max),
        "Spacing D/C": spacing_dc,
        "Detailing D/C value": detailing_dc,
        "Detailing notes": note,
    }


def _railway_u_girder_uls_shear_evidence_columns() -> list[str]:
    return [
        "Check",
        "Status",
        "Strength status",
        "Detailing status",
        "Governing x (m)",
        "Case",
        "Demand Vuy (kN)",
        "φVn (kN)",
        "φVc (kN)",
        "φVs (kN)",
        "Vc (kN)",
        "Vs (kN)",
        "Vn (kN)",
        "Vn limit (kN)",
        "D/C",
        "Strength D/C",
        "Detailing D/C",
        "Zone",
        "Stirrup",
        "Av/s provided (mm2/m)",
        "Av/s required (mm2/m)",
        "Spacing D/C",
        "bv (mm)",
        "d (mm)",
        "dv (mm)",
        "β",
        "θ (deg)",
        "φ",
        "Tension face",
        "Code basis",
        "Method",
        "PSC shear basis",
        "Evidence status",
        "Blocked final claim",
        "Notes",
    ]


def railway_u_girder_uls_shear_evidence_dataframe(session_state: Any, active_uls: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return guarded Railway U-Girder PSC shear route evidence.

    ULS.RAIL.UGIRDER3 intentionally exposes a sectional shear route for
    engineering review only.  It does not implement final PSC Vci/Vcw/Vp,
    end-region, development-length, anchorage, or benchmark certification.
    """

    columns = _railway_u_girder_uls_shear_evidence_columns()
    active = active_uls.copy() if isinstance(active_uls, pd.DataFrame) else active_railway_u_girder_uls_demand_dataframe(session_state)
    if active.empty:
        return pd.DataFrame(columns=columns)
    active["__vuy"] = pd.to_numeric(active.get("Vuy", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    candidates = active.loc[active["__vuy"].abs() > _ULS_DEMAND_TOL].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)
    if len(candidates.index) > RAILWAY_UGIRDER_ULS_MAX_SHEAR_EVIDENCE_ROWS:
        candidates = candidates.head(RAILWAY_UGIRDER_ULS_MAX_SHEAR_EVIDENCE_ROWS).copy()
    rows: list[dict[str, Any]] = []
    for _, demand_row in candidates.iterrows():
        station = _float_or_zero(demand_row.get("Station x (m)"))
        case = str(demand_row.get("Case Name") or "ULS").strip() or "ULS"
        vu_kN = _float_or_zero(demand_row.get("Vuy"))
        mux_kNm = _float_or_zero(demand_row.get("Mux"))
        zone = _railway_uls_active_shear_zone_for_station(session_state, station)
        analysis_input, input_messages = _railway_uls_analysis_input_for_station_row(session_state, row=demand_row)
        base = {
            "Check": "ULS PSC shear",
            "Governing x (m)": float(station),
            "Case": case,
            "Demand Vuy (kN)": float(vu_kN),
            "Code basis": "AASHTO LRFD-compatible PSC shear route - guarded engineering review",
            "Method": "AASHTO LRFD-compatible simplified sectional shear with provided stirrups",
            "PSC shear basis": "Vp = 0 unless included in imported Vuy; refined Vci/Vcw/Vp and end-region route are future work.",
            "Evidence status": RAILWAY_UGIRDER_ULS_SHEAR_EVIDENCE_STATUS,
            "Blocked final claim": "No code-certified or engineer-certified shear PASS until PSC shear benchmarks, Vci/Vcw/Vp, development length, anchorage/end-zone, and critical-section checks are complete.",
        }
        if zone is None:
            rows.append({
                **base,
                "Status": "LAYOUT REQUIRED",
                "Strength status": "REVIEW",
                "Detailing status": "REVIEW",
                "φVn (kN)": float("nan"),
                "φVc (kN)": float("nan"),
                "φVs (kN)": float("nan"),
                "Vc (kN)": float("nan"),
                "Vs (kN)": float("nan"),
                "Vn (kN)": float("nan"),
                "Vn limit (kN)": float("nan"),
                "D/C": float("nan"),
                "Strength D/C": float("nan"),
                "Detailing D/C": float("nan"),
                "Zone": "-",
                "Stirrup": "-",
                "Av/s provided (mm2/m)": float("nan"),
                "Av/s required (mm2/m)": float("nan"),
                "Spacing D/C": float("nan"),
                "bv (mm)": float("nan"),
                "d (mm)": float("nan"),
                "dv (mm)": float("nan"),
                "β": float("nan"),
                "θ (deg)": float("nan"),
                "φ": float("nan"),
                "Tension face": "-",
                "Notes": "No active shear reinforcement zone covers this ULS shear station. Define active provided-stirrup zones in Sections → Rebar before relying on shear evidence.",
            })
            continue
        if analysis_input is None:
            rows.append({
                **base,
                "Status": "REVIEW",
                "Strength status": "REVIEW",
                "Detailing status": "REVIEW",
                "φVn (kN)": float("nan"),
                "φVc (kN)": float("nan"),
                "φVs (kN)": float("nan"),
                "Vc (kN)": float("nan"),
                "Vs (kN)": float("nan"),
                "Vn (kN)": float("nan"),
                "Vn limit (kN)": float("nan"),
                "D/C": float("nan"),
                "Strength D/C": float("nan"),
                "Detailing D/C": float("nan"),
                "Zone": str(zone.get("Zone") or "-"),
                "Stirrup": "-",
                "Av/s provided (mm2/m)": float("nan"),
                "Av/s required (mm2/m)": float("nan"),
                "Spacing D/C": float("nan"),
                "bv (mm)": float("nan"),
                "d (mm)": float("nan"),
                "dv (mm)": float("nan"),
                "β": float("nan"),
                "θ (deg)": float("nan"),
                "φ": float("nan"),
                "Tension face": "-",
                "Notes": "; ".join(input_messages) or "Section/material/strand input not ready for shear route evidence.",
            })
            continue
        concrete = analysis_input.concrete_material
        fc = float(concrete.fc_MPa)
        bv_mm, bv_note = _railway_uls_web_width_mm(analysis_input.section_geometry)
        depth = _railway_uls_effective_shear_depth_values_mm(session_state, analysis_input, mux_kNm=mux_kNm)
        d_eff = float(depth.get("d_mm", float("nan")))
        dv_eff = float(depth.get("dv_mm", float("nan")))
        stirrup_area = _railway_uls_stirrup_area_mm2(zone)
        legs = _float_or_zero(zone.get("Legs"))
        spacing = _float_or_zero(zone.get("Spacing_mm"))
        fy = _float_or_zero(zone.get("fy_MPa"))
        if bv_mm is None or not all(math.isfinite(value) and value > 0.0 for value in [fc, bv_mm, d_eff, dv_eff, stirrup_area, legs, spacing, fy]):
            rows.append({
                **base,
                "Status": "REVIEW",
                "Strength status": "REVIEW",
                "Detailing status": "REVIEW",
                "φVn (kN)": float("nan"),
                "φVc (kN)": float("nan"),
                "φVs (kN)": float("nan"),
                "Vc (kN)": float("nan"),
                "Vs (kN)": float("nan"),
                "Vn (kN)": float("nan"),
                "Vn limit (kN)": float("nan"),
                "D/C": float("nan"),
                "Strength D/C": float("nan"),
                "Detailing D/C": float("nan"),
                "Zone": str(zone.get("Zone") or "-"),
                "Stirrup": f"{zone.get('Bar Size') or '-'} × {int(legs) if legs > 0 else '-'} legs @ {spacing:.0f} mm" if spacing > 0.0 else str(zone.get("Bar Size") or "-"),
                "Av/s provided (mm2/m)": float("nan"),
                "Av/s required (mm2/m)": float("nan"),
                "Spacing D/C": float("nan"),
                "bv (mm)": float(bv_mm) if bv_mm is not None else float("nan"),
                "d (mm)": d_eff,
                "dv (mm)": dv_eff,
                "β": float("nan"),
                "θ (deg)": float("nan"),
                "φ": float("nan"),
                "Tension face": str(depth.get("tension_face") or "-"),
                "Notes": "; ".join([bv_note, str(depth.get("note") or ""), "Active stirrup zone or concrete/geometry input is incomplete.", *input_messages]),
            })
            continue
        avs = float(stirrup_area) * float(legs) / float(spacing)
        phi = 0.90
        beta = 2.0
        theta = 45.0
        cot_theta = 1.0
        vc_n = 0.083 * beta * math.sqrt(fc) * float(bv_mm) * float(dv_eff)
        vs_n = avs * float(fy) * float(dv_eff) * cot_theta
        vn_uncapped_n = max(0.0, vc_n + vs_n)
        vn_limit_n = 0.25 * fc * float(bv_mm) * float(dv_eff)
        vn_n = min(vn_uncapped_n, vn_limit_n) if vn_limit_n > 0.0 else vn_uncapped_n
        phi_vn_kN = phi * vn_n / 1000.0
        strength_dc = abs(float(vu_kN)) / phi_vn_kN if phi_vn_kN > 0.0 else float("nan")
        strength_status = "PASS" if math.isfinite(strength_dc) and strength_dc <= 1.0 else "FAIL" if math.isfinite(strength_dc) else "REVIEW"
        detailing = _railway_uls_shear_detailing_guard(
            fc_MPa=fc,
            bv_mm=float(bv_mm),
            d_eff_mm=float(d_eff),
            dv_mm=float(dv_eff),
            spacing_mm=float(spacing),
            avs_mm2_per_mm=float(avs),
            fy_MPa=float(fy),
        )
        detailing_status = str(detailing.get("Detailing status") or "REVIEW")
        detailing_dc = _float_or_zero(detailing.get("Detailing D/C value"))
        finite_dcs = [value for value in [strength_dc, detailing_dc] if math.isfinite(value)]
        governing_dc = max(finite_dcs) if finite_dcs else float("nan")
        if strength_status == "FAIL" or detailing_status == "FAIL":
            status = "Engineering Review FAIL"
        elif strength_status == "PASS" and detailing_status == "PASS":
            status = "Engineering Review PASS"
        else:
            status = "REVIEW"
        notes = [
            RAILWAY_UGIRDER_ULS_SHEAR_EVIDENCE_WARNING,
            bv_note,
            str(depth.get("note") or ""),
            "AASHTO-compatible gate uses Vc = 0.083β√f'c bv dv with β=2.0 and θ=45°, plus provided Av/s, Vn capped at 0.25f'c bv dv.",
            "Prestress vertical component Vp is treated as zero unless the engineer includes it in imported Vuy resultants.",
            str(detailing.get("Detailing notes") or ""),
            *input_messages,
        ]
        rows.append({
            **base,
            "Status": status,
            "Strength status": strength_status,
            "Detailing status": detailing_status,
            "φVn (kN)": phi_vn_kN,
            "φVc (kN)": phi * vc_n / 1000.0,
            "φVs (kN)": phi * vs_n / 1000.0,
            "Vc (kN)": vc_n / 1000.0,
            "Vs (kN)": vs_n / 1000.0,
            "Vn (kN)": vn_n / 1000.0,
            "Vn limit (kN)": vn_limit_n / 1000.0,
            "D/C": governing_dc,
            "Strength D/C": strength_dc,
            "Detailing D/C": detailing_dc,
            "Zone": str(zone.get("Zone") or "Zone"),
            "Stirrup": f"{zone.get('Bar Size') or '-'} × {int(float(legs))} legs @ {float(spacing):.0f} mm",
            "Av/s provided (mm2/m)": avs * 1000.0,
            "Av/s required (mm2/m)": detailing.get("Av/s required mm2/m", float("nan")),
            "Spacing D/C": detailing.get("Spacing D/C", float("nan")),
            "bv (mm)": float(bv_mm),
            "d (mm)": float(d_eff),
            "dv (mm)": float(dv_eff),
            "β": beta,
            "θ (deg)": theta,
            "φ": phi,
            "Tension face": str(depth.get("tension_face") or "-"),
            "Notes": "; ".join(str(item) for item in notes if str(item).strip()),
        })
    return pd.DataFrame(rows, columns=columns)


def _railway_uls_outer_polygon_metrics(geometry: SectionGeometry) -> dict[str, Any]:
    """Return outside concrete Acp/Pcp metrics for torsion threshold screens.

    ULS.RAIL.UGIRDER4 intentionally keeps this as a visible guarded estimate.
    Hollow/multi-cell U-Girder torsion still needs a dedicated calibrated closed
    torsion-cell route before final certification.
    """

    try:
        outer = to_shapely_polygon(SectionGeometry(name=geometry.name, outer_polygon=geometry.outer_polygon, holes=[]))
    except Exception:
        outer = None
    if outer is None or outer.is_empty or outer.area <= 0.0 or not outer.is_valid:
        return {"Acp mm2": float("nan"), "Pcp mm": float("nan"), "Note": "Outside polygon torsion metrics are not available."}
    try:
        pcp = float(outer.exterior.length)
    except Exception:
        pcp = float("nan")
    return {
        "Acp mm2": float(outer.area),
        "Pcp mm": pcp,
        "Note": "Acp/Pcp from outside concrete perimeter; Railway U-Girder multi-cell torsion calibration remains future work.",
    }


def _railway_uls_torsion_hoop_geometry(section_geometry: SectionGeometry, *, stirrup_diameter_mm: float) -> dict[str, Any]:
    """Return guarded first-pass closed-hoop geometry for torsion evidence."""

    metrics = _railway_uls_outer_polygon_metrics(section_geometry)
    notes = [str(metrics.get("Note") or "")]
    acp = _float_or_zero(metrics.get("Acp mm2"))
    pcp = _float_or_zero(metrics.get("Pcp mm"))
    try:
        outer = to_shapely_polygon(SectionGeometry(name=section_geometry.name, outer_polygon=section_geometry.outer_polygon, holes=[]))
    except Exception:
        outer = None
    if outer is None or outer.is_empty or outer.area <= 0.0 or not outer.is_valid:
        return {
            "Acp mm2": acp,
            "Pcp mm": pcp,
            "Aoh mm2": float("nan"),
            "Ao mm2": float("nan"),
            "ph mm": float("nan"),
            "offset mm": float("nan"),
            "Note": " ".join(note for note in notes if note) + " Closed-hoop centerline geometry could not be derived.",
        }
    minx, miny, maxx, maxy = outer.bounds
    min_dim = min(float(maxx) - float(minx), float(maxy) - float(miny))
    dia = float(stirrup_diameter_mm) if math.isfinite(float(stirrup_diameter_mm)) and float(stirrup_diameter_mm) > 0.0 else 12.0
    offset = max(45.0 + 0.5 * dia, 0.04 * min_dim)
    if math.isfinite(min_dim) and min_dim > 0.0:
        offset = min(offset, 0.20 * min_dim)
    try:
        inset = outer.buffer(-float(offset), join_style=2)
        if inset.is_empty or inset.area <= 0.0:
            raise ValueError("empty inset")
        if getattr(inset, "geoms", None):
            inset = max(inset.geoms, key=lambda geom: float(geom.area))
            notes.append("Inset closed-hoop path split into multiple regions; largest region used for guarded torsion geometry.")
        aoh = float(inset.area)
        ph = float(inset.exterior.length)
        ao = 0.85 * aoh
        notes.append(f"Aoh estimated from outside polygon offset {offset:.1f} mm to assumed closed hoop centerline; Ao = 0.85Aoh.")
    except Exception:
        aoh = float("nan")
        ph = float("nan")
        ao = float("nan")
        notes.append("Closed-hoop centerline offset failed; define dedicated torsion hoop geometry before relying on torsion evidence.")
    return {
        "Acp mm2": acp,
        "Pcp mm": pcp,
        "Aoh mm2": aoh,
        "Ao mm2": ao,
        "ph mm": ph,
        "offset mm": float(offset),
        "Note": " ".join(note for note in notes if note),
    }


def _railway_uls_rebar_area_mm2(item: Any) -> float:
    area = getattr(item, "area_mm2", None)
    if area is not None:
        area_value = _float_or_zero(area)
        if math.isfinite(area_value) and area_value > 0.0:
            return float(area_value)
    diameter = getattr(item, "diameter_mm", None)
    if diameter is None and isinstance(item, Mapping):
        diameter = item.get("diameter_mm", item.get("Diameter_mm"))
    diameter_value = _float_or_zero(diameter)
    if not math.isfinite(diameter_value) or diameter_value <= 0.0:
        return float("nan")
    return math.pi * diameter_value * diameter_value / 4.0


def _railway_uls_torsion_longitudinal_review(session_state: Any, al_req_mm2: float) -> dict[str, Any]:
    if not math.isfinite(float(al_req_mm2)) or float(al_req_mm2) <= 0.0:
        return {
            "status": "NOT CHECKED",
            "provided_mm2": float("nan"),
            "utilization": float("nan"),
            "description": "Longitudinal torsion reinforcement is not required by the current torsion row.",
        }
    if not ordinary_rebar_enabled(session_state, default=True):
        return {
            "status": "LAYOUT REQUIRED",
            "provided_mm2": 0.0,
            "utilization": float("nan"),
            "description": "Enable ordinary rebar / longitudinal Al in Section Builder and define active Rebar rows for torsion Al review.",
        }
    raw_rebars = _railway_uls_model_list(_get(session_state, "rebars", []) or [], Rebar)
    try:
        effective = effective_rebars_for_analysis(raw_rebars, session_state)
    except Exception:
        effective = raw_rebars
    provided = 0.0
    counted = 0
    for bar in effective:
        area = _railway_uls_rebar_area_mm2(bar)
        if math.isfinite(area) and area > 0.0:
            provided += float(area)
            counted += 1
    if counted == 0 or provided <= 0.0:
        return {
            "status": "LAYOUT REQUIRED",
            "provided_mm2": provided,
            "utilization": float("nan"),
            "description": "No active ordinary rebar rows are available for longitudinal torsion Al review; use the Rebar table as the single source of truth.",
        }
    utilization = float(al_req_mm2) / provided if provided > 0.0 else float("nan")
    status = "PASS" if math.isfinite(utilization) and utilization <= 1.0 + 1.0e-9 else "FAIL"
    return {
        "status": status,
        "provided_mm2": provided,
        "utilization": utilization,
        "description": (
            f"Longitudinal torsion Al provided is taken from {counted} active ordinary rebar bar(s); "
            f"Al,req/Al,prov = {utilization:.3f}. Verify these bars are detailed around the closed torsion path before final design."
        ),
    }


def _railway_uls_torsion_detailing_gate(
    *,
    zone: Mapping[str, Any] | None,
    x_m: float,
    spacing_mm: float,
    ph_mm: float,
    at_per_s_mm2_per_mm: float,
    at_req_mm2_per_mm: float,
) -> dict[str, Any]:
    notes: list[str] = []
    if zone is None:
        return {
            "status": "LAYOUT REQUIRED",
            "s_max_mm": float("nan"),
            "spacing_dc": float("nan"),
            "at_dc": float("nan"),
            "dc": float("nan"),
            "notes": "No active closed-hoop transverse reinforcement zone is available for torsion.",
        }
    x_start = _float_or_zero(zone.get("x_start_m"))
    x_end = _float_or_zero(zone.get("x_end_m"))
    covers = math.isfinite(float(x_m)) and x_start - 1.0e-9 <= float(x_m) <= x_end + 1.0e-9
    if not covers:
        notes.append("The active transverse zone does not cover this station; add/extend a closed-hoop torsion zone.")
    if not all(math.isfinite(value) and value > 0.0 for value in [spacing_mm, ph_mm, at_per_s_mm2_per_mm]):
        return {
            "status": "LAYOUT REQUIRED",
            "s_max_mm": float("nan"),
            "spacing_dc": float("nan"),
            "at_dc": float("nan"),
            "dc": float("nan"),
            "notes": "; ".join(notes + ["Torsion detailing needs finite spacing, ph, and At/s."]),
        }
    s_max = min(float(ph_mm) / 8.0, 300.0)
    spacing_dc = float(spacing_mm) / float(s_max) if s_max > 0.0 else float("nan")
    at_dc = float(at_req_mm2_per_mm) / float(at_per_s_mm2_per_mm) if math.isfinite(float(at_req_mm2_per_mm)) and float(at_per_s_mm2_per_mm) > 0.0 else float("nan")
    finite_dcs = [value for value in [spacing_dc, at_dc] if math.isfinite(value)]
    dc = max(finite_dcs) if finite_dcs else float("nan")
    if not covers:
        status = "LAYOUT REQUIRED"
    elif math.isfinite(dc) and dc <= 1.0 + 1.0e-9:
        status = "PASS"
    else:
        status = "FAIL"
        if math.isfinite(spacing_dc) and spacing_dc > 1.0 + 1.0e-9:
            notes.append("Closed-hoop spacing exceeds torsion spacing limit s <= min(ph/8, 300 mm).")
        if math.isfinite(at_dc) and at_dc > 1.0 + 1.0e-9:
            notes.append("Provided At/s is less than required torsion At/s.")
    if not notes:
        notes.append("Closed-hoop zone covers the station and passes At/s plus spacing guard.")
    return {"status": status, "s_max_mm": s_max, "spacing_dc": spacing_dc, "at_dc": at_dc, "dc": dc, "notes": "; ".join(notes)}


def _railway_uls_match_shear_evidence_row(shear_evidence: pd.DataFrame, *, case: str, station_m: float) -> Mapping[str, Any] | None:
    if not isinstance(shear_evidence, pd.DataFrame) or shear_evidence.empty:
        return None
    df = shear_evidence.copy()
    if "Case" in df.columns:
        exact = df[df["Case"].astype(str) == str(case)]
        if not exact.empty:
            return exact.iloc[0].to_dict()
    if "Governing x (m)" in df.columns:
        df["__dx"] = pd.to_numeric(df["Governing x (m)"], errors="coerce").sub(float(station_m)).abs()
        if df["__dx"].notna().any():
            return df.sort_values("__dx").iloc[0].drop(labels=["__dx"], errors="ignore").to_dict()
    return None


def _railway_u_girder_uls_torsion_vt_guard_columns() -> list[str]:
    return [
        "Check",
        "Status",
        "Governing x (m)",
        "Case",
        "Demand Vuy (kN)",
        "Demand Tu (kN-m)",
        "φTn (kN-m)",
        "φTcr (kN-m)",
        "Torsion D/C",
        "Shear D/C",
        "V+T interaction index",
        "Threshold status",
        "Transverse status",
        "Longitudinal Al status",
        "Detailing status",
        "Zone",
        "Stirrup",
        "Ao (mm2)",
        "Aoh (mm2)",
        "ph (mm)",
        "At/s provided (mm2/m)",
        "At/s required (mm2/m)",
        "Al required (mm2)",
        "Al provided (mm2)",
        "Spacing D/C",
        "φ",
        "Code basis",
        "Method",
        "Evidence status",
        "Blocked final claim",
        "Notes",
    ]


def railway_u_girder_uls_torsion_vt_guard_dataframe(
    session_state: Any,
    active_uls: pd.DataFrame | None = None,
    shear_evidence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return guarded torsion and combined V+T evidence for Railway U-Girder ULS.

    ULS.RAIL.UGIRDER4 intentionally exposes engineering-review evidence only.
    It must not be read as final torsion or combined shear/torsion certification.
    """

    columns = _railway_u_girder_uls_torsion_vt_guard_columns()
    active = active_uls.copy() if isinstance(active_uls, pd.DataFrame) else active_railway_u_girder_uls_demand_dataframe(session_state)
    if active.empty:
        return pd.DataFrame(columns=columns)
    active["__tu"] = pd.to_numeric(active.get("Tu", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    active["__vuy"] = pd.to_numeric(active.get("Vuy", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    candidates = active.loc[(active["__tu"].abs() > _ULS_DEMAND_TOL) | (active["__vuy"].abs() > _ULS_DEMAND_TOL)].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)
    if len(candidates.index) > RAILWAY_UGIRDER_ULS_MAX_TORSION_VT_GUARD_ROWS:
        candidates = candidates.head(RAILWAY_UGIRDER_ULS_MAX_TORSION_VT_GUARD_ROWS).copy()
    if shear_evidence is None:
        shear_evidence = railway_u_girder_uls_shear_evidence_dataframe(session_state, active)
    rows: list[dict[str, Any]] = []
    for _, demand_row in candidates.iterrows():
        case = str(demand_row.get("Case Name") or "ULS")
        station = _float_or_zero(demand_row.get("Station x (m)"))
        vu = abs(_float_or_zero(demand_row.get("Vuy")))
        tu = abs(_float_or_zero(demand_row.get("Tu")))
        analysis_input, input_messages = _railway_uls_analysis_input_for_station_row(session_state, row=demand_row)
        zone = _railway_uls_active_shear_zone_for_station(session_state, station)
        shear_row = _railway_uls_match_shear_evidence_row(shear_evidence, case=case, station_m=station)
        shear_dc = _float_or_zero((shear_row or {}).get("Strength D/C", (shear_row or {}).get("D/C", float("nan")))) if shear_row is not None else float("nan")
        shear_status = str((shear_row or {}).get("Strength status", (shear_row or {}).get("Status", "REVIEW"))) if shear_row is not None else "REVIEW"
        phi = 0.90
        base = {
            "Governing x (m)": station,
            "Case": case,
            "Demand Vuy (kN)": vu,
            "Demand Tu (kN-m)": tu,
            "Evidence status": RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_STATUS,
            "Blocked final claim": "No code-certified or engineer-certified PASS until torsion/V+T benchmarks, dedicated closed torsion-cell calibration, development length, and anchorage/end-zone checks are complete.",
        }
        if tu <= _ULS_DEMAND_TOL:
            interaction = shear_dc if math.isfinite(shear_dc) else float("nan")
            rows.append({
                **base,
                "Check": "Combined V+T guard",
                "Status": "NO TORSION DEMAND" if vu <= _ULS_DEMAND_TOL else "SHEAR ONLY REVIEW",
                "φTn (kN-m)": float("nan"),
                "φTcr (kN-m)": float("nan"),
                "Torsion D/C": 0.0,
                "Shear D/C": shear_dc,
                "V+T interaction index": interaction,
                "Threshold status": "NO TORSION DEMAND",
                "Transverse status": "NOT CHECKED",
                "Longitudinal Al status": "NOT CHECKED",
                "Detailing status": "NOT CHECKED",
                "Zone": str((zone or {}).get("Zone") or "-"),
                "Stirrup": "-",
                "Ao (mm2)": float("nan"),
                "Aoh (mm2)": float("nan"),
                "ph (mm)": float("nan"),
                "At/s provided (mm2/m)": float("nan"),
                "At/s required (mm2/m)": float("nan"),
                "Al required (mm2)": float("nan"),
                "Al provided (mm2)": float("nan"),
                "Spacing D/C": float("nan"),
                "φ": phi,
                "Code basis": "AASHTO LRFD-compatible V+T guard - not certified",
                "Method": "No torsion demand; shear route governs this row if Vuy exists.",
                "Notes": "; ".join([RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_WARNING, f"Source shear status: {shear_status}.", *input_messages]),
            })
            continue
        if analysis_input is None:
            rows.append({
                **base,
                "Check": "ULS torsion / V+T guard",
                "Status": "REVIEW",
                "φTn (kN-m)": float("nan"),
                "φTcr (kN-m)": float("nan"),
                "Torsion D/C": float("nan"),
                "Shear D/C": shear_dc,
                "V+T interaction index": float("nan"),
                "Threshold status": "REVIEW",
                "Transverse status": "NOT READY",
                "Longitudinal Al status": "NOT CHECKED",
                "Detailing status": "NOT READY",
                "Zone": str((zone or {}).get("Zone") or "-"),
                "Stirrup": "-",
                "Ao (mm2)": float("nan"),
                "Aoh (mm2)": float("nan"),
                "ph (mm)": float("nan"),
                "At/s provided (mm2/m)": float("nan"),
                "At/s required (mm2/m)": float("nan"),
                "Al required (mm2)": float("nan"),
                "Al provided (mm2)": float("nan"),
                "Spacing D/C": float("nan"),
                "φ": phi,
                "Code basis": "AASHTO LRFD-compatible torsion/V+T guard - not certified",
                "Method": "Input not ready",
                "Notes": "; ".join(input_messages) or "Section/material/strand input not ready for torsion/V+T guard.",
            })
            continue
        concrete = analysis_input.concrete_material
        fc = float(concrete.fc_MPa)
        if zone is None:
            stirrup_area = legs = spacing = fy = diameter = float("nan")
        else:
            stirrup_area = _railway_uls_stirrup_area_mm2(zone)
            legs = _float_or_zero(zone.get("Legs"))
            spacing = _float_or_zero(zone.get("Spacing_mm"))
            fy = _float_or_zero(zone.get("fy_MPa"))
            diameter = _float_or_zero(zone.get("Diameter_mm"))
        geometry = _railway_uls_torsion_hoop_geometry(analysis_input.section_geometry, stirrup_diameter_mm=diameter)
        acp = _float_or_zero(geometry.get("Acp mm2"))
        pcp = _float_or_zero(geometry.get("Pcp mm"))
        ao = _float_or_zero(geometry.get("Ao mm2"))
        aoh = _float_or_zero(geometry.get("Aoh mm2"))
        ph = _float_or_zero(geometry.get("ph mm"))
        tcr = float("nan")
        if all(math.isfinite(value) and value > 0.0 for value in [fc, acp, pcp]):
            tcr = phi * (0.083 * math.sqrt(fc) * acp * acp / pcp) / 1.0e6
        threshold_status = "BELOW THRESHOLD" if math.isfinite(tcr) and tu <= tcr + 1.0e-9 else "DESIGN REQUIRED"
        code_basis = "AASHTO LRFD-compatible closed-hoop torsion/V+T guard - not certified"
        method = "Closed-hoop torsion truss guard with ordinary rebar Al and linear V+T review index"
        if not all(math.isfinite(value) and value > 0.0 for value in [stirrup_area, spacing, fy, ao, ph]) and threshold_status != "BELOW THRESHOLD":
            rows.append({
                **base,
                "Check": "ULS torsion / V+T guard",
                "Status": "LAYOUT REQUIRED",
                "φTn (kN-m)": float("nan"),
                "φTcr (kN-m)": tcr,
                "Torsion D/C": float("nan"),
                "Shear D/C": shear_dc,
                "V+T interaction index": float("nan"),
                "Threshold status": threshold_status,
                "Transverse status": "LAYOUT REQUIRED",
                "Longitudinal Al status": "NOT CHECKED",
                "Detailing status": "LAYOUT REQUIRED",
                "Zone": str((zone or {}).get("Zone") or "-"),
                "Stirrup": "-" if zone is None else f"{zone.get('Bar Size') or '-'} closed hoop @ {spacing:.0f} mm",
                "Ao (mm2)": ao,
                "Aoh (mm2)": aoh,
                "ph (mm)": ph,
                "At/s provided (mm2/m)": float("nan"),
                "At/s required (mm2/m)": float("nan"),
                "Al required (mm2)": float("nan"),
                "Al provided (mm2)": float("nan"),
                "Spacing D/C": float("nan"),
                "φ": phi,
                "Code basis": code_basis,
                "Method": method,
                "Notes": "; ".join([RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_WARNING, str(geometry.get("Note") or ""), "Active closed-hoop transverse zone or torsion geometry is incomplete.", *input_messages]),
            })
            continue
        at_per_s = float(stirrup_area) / float(spacing) if spacing > 0.0 and math.isfinite(stirrup_area) else float("nan")
        phi_tn = float("nan")
        torsion_dc = float("nan")
        at_req = float("nan")
        al_req = float("nan")
        transverse_status = "THRESHOLD OK" if threshold_status == "BELOW THRESHOLD" else "REVIEW"
        longitudinal_status = "NOT CHECKED"
        detailing_status = "THRESHOLD OK" if threshold_status == "BELOW THRESHOLD" else "REVIEW"
        al_review = {"provided_mm2": float("nan"), "utilization": float("nan"), "description": ""}
        detail = {"spacing_dc": float("nan"), "dc": float("nan"), "notes": ""}
        if threshold_status == "BELOW THRESHOLD":
            torsion_dc = 0.0
            status = "BELOW THRESHOLD" if vu <= _ULS_DEMAND_TOL else "SHEAR + TORSION THRESHOLD REVIEW"
        else:
            phi_tn = phi * (2.0 * float(ao) * float(at_per_s) * float(fy)) / 1.0e6
            torsion_dc = tu / phi_tn if phi_tn > 0.0 else float("nan")
            transverse_status = "PASS" if math.isfinite(torsion_dc) and torsion_dc <= 1.0 + 1.0e-9 else "FAIL" if math.isfinite(torsion_dc) else "REVIEW"
            at_req = tu * 1.0e6 / (phi * 2.0 * float(ao) * float(fy)) if all(math.isfinite(value) and value > 0.0 for value in [ao, fy]) else float("nan")
            al_req = at_per_s * float(ph) if math.isfinite(ph) and ph > 0.0 and math.isfinite(at_per_s) else float("nan")
            al_review = _railway_uls_torsion_longitudinal_review(session_state, al_req)
            longitudinal_status = str(al_review.get("status") or "LAYOUT REQUIRED")
            detail = _railway_uls_torsion_detailing_gate(zone=zone, x_m=station, spacing_mm=float(spacing), ph_mm=float(ph), at_per_s_mm2_per_mm=float(at_per_s), at_req_mm2_per_mm=float(at_req))
            detailing_status = str(detail.get("status") or "LAYOUT REQUIRED")
            if "FAIL" in {transverse_status, longitudinal_status, detailing_status}:
                status = "Engineering Review FAIL"
            elif any(value in {"LAYOUT REQUIRED", "NOT CHECKED", "NOT READY"} for value in [longitudinal_status, detailing_status]):
                status = "LAYOUT REQUIRED"
            elif transverse_status == "PASS" and longitudinal_status == "PASS" and detailing_status == "PASS":
                status = "Engineering Review PASS"
            else:
                status = "REVIEW"
        interaction_terms = []
        if math.isfinite(shear_dc) and vu > _ULS_DEMAND_TOL:
            interaction_terms.append(shear_dc)
        if math.isfinite(torsion_dc) and tu > _ULS_DEMAND_TOL:
            interaction_terms.append(torsion_dc)
        interaction_index = sum(interaction_terms) if interaction_terms else float("nan")
        if tu > _ULS_DEMAND_TOL and vu > _ULS_DEMAND_TOL and status == "Engineering Review PASS" and shear_status in {"PASS", "Engineering Review PASS"}:
            status = "Engineering Review PASS" if math.isfinite(interaction_index) and interaction_index <= 1.0 + 1.0e-9 else "Engineering Review FAIL"
        notes = [
            RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_WARNING,
            str(geometry.get("Note") or ""),
            f"Source shear status: {shear_status}.",
            "Torsion At is taken as one closed-hoop bar area per spacing; shear leg count is not multiplied into At.",
            "Combined V+T index is a guarded linear review index only; it is not final code-certified interaction design.",
            str(al_review.get("description") or ""),
            str(detail.get("notes") or ""),
            *input_messages,
        ]
        rows.append({
            **base,
            "Check": "ULS torsion / V+T guard",
            "Status": status,
            "φTn (kN-m)": phi_tn,
            "φTcr (kN-m)": tcr,
            "Torsion D/C": torsion_dc,
            "Shear D/C": shear_dc,
            "V+T interaction index": interaction_index,
            "Threshold status": threshold_status,
            "Transverse status": transverse_status,
            "Longitudinal Al status": longitudinal_status,
            "Detailing status": detailing_status,
            "Zone": str((zone or {}).get("Zone") or "-"),
            "Stirrup": "-" if zone is None else f"{zone.get('Bar Size') or '-'} closed hoop @ {float(spacing):.0f} mm",
            "Ao (mm2)": ao,
            "Aoh (mm2)": aoh,
            "ph (mm)": ph,
            "At/s provided (mm2/m)": at_per_s * 1000.0 if math.isfinite(at_per_s) else float("nan"),
            "At/s required (mm2/m)": at_req * 1000.0 if math.isfinite(at_req) else float("nan"),
            "Al required (mm2)": al_req,
            "Al provided (mm2)": al_review.get("provided_mm2", float("nan")),
            "Spacing D/C": detail.get("spacing_dc", float("nan")),
            "φ": phi,
            "Code basis": code_basis,
            "Method": method,
            "Notes": "; ".join(str(item) for item in notes if str(item).strip()),
        })
    return pd.DataFrame(rows, columns=columns)

def _railway_prestress_development_columns() -> list[str]:
    return [
        "Check",
        "Status",
        "Group ID",
        "Total strands",
        "Debonded strands",
        "Strand diameter (mm)",
        "Area/strand (mm2)",
        "fpe final (MPa)",
        "fps review (MPa)",
        "Left debond (m)",
        "Right debond (m)",
        "Transfer length lt (m)",
        "Development length ld (m)",
        "Left full-development station (m)",
        "Right full-development station (m)",
        "Available left bond to midspan (m)",
        "Available right bond to midspan (m)",
        "Left development D/C",
        "Right development D/C",
        "Development status",
        "Transfer zone status",
        "Code basis",
        "Method",
        "Evidence status",
        "Blocked final claim",
        "Notes",
    ]


def _railway_strand_diameter_mm_from_row(row: Mapping[str, Any]) -> float:
    for key in ("Diameter_mm", "Strand Diameter_mm", "Strand diameter (mm)"):
        value = _float_or_zero(row.get(key))
        if math.isfinite(value) and value > 0.0:
            return float(value)
    text = str(row.get("Strand Size") or row.get("Product") or "")
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        try:
            parsed = float(match.group(1))
            if parsed > 0.0:
                return parsed
        except ValueError:
            pass
    return 12.7


def _railway_strand_fpu_mpa_from_row(row: Mapping[str, Any]) -> float:
    for key in ("fpu_MPa", "fpu", "Fpu_MPa"):
        value = _float_or_zero(row.get(key))
        if math.isfinite(value) and value > 0.0:
            return float(value)
    return _GIRDER_STRAND_FPU_MPA_DEFAULT


def _railway_strand_fpy_mpa_from_row(row: Mapping[str, Any]) -> float:
    for key in ("fpy_MPa", "fpy", "Fpy_MPa"):
        value = _float_or_zero(row.get(key))
        if math.isfinite(value) and value > 0.0:
            return float(value)
    return _GIRDER_STRAND_FPY_MPA_DEFAULT


def _railway_development_lengths_for_row(row: Mapping[str, Any]) -> dict[str, float]:
    diameter_mm = _railway_strand_diameter_mm_from_row(row)
    aps_mm2 = _float_or_zero(row.get("Area/Strand_mm2"))
    if not math.isfinite(aps_mm2) or aps_mm2 <= 0.0:
        aps_mm2 = 98.7
    pe_final_kN = _float_or_zero(row.get("Pe_eff_final/strand_kN"))
    fpe_mpa = pe_final_kN * 1000.0 / aps_mm2 if aps_mm2 > 0.0 and pe_final_kN > 0.0 else 0.0
    fpy_mpa = _railway_strand_fpy_mpa_from_row(row)
    fpu_mpa = _railway_strand_fpu_mpa_from_row(row)
    fps_review_mpa = min(float(fpy_mpa), 0.90 * float(fpu_mpa)) if fpy_mpa > 0.0 and fpu_mpa > 0.0 else _GIRDER_STRAND_FPY_MPA_DEFAULT
    # Guarded code-compatible screen.  The stress term is converted from MPa to ksi
    # because common strand development equations use ksi/in.  This table is an
    # evidence gate only and does not ramp prestress force in the solvers.
    ksi_per_mpa = 1.0 / 6.895
    transfer_by_stress_mm = max(0.0, fpe_mpa * ksi_per_mpa * diameter_mm / 3.0)
    transfer_60db_mm = 60.0 * diameter_mm
    lt_mm = max(transfer_60db_mm, transfer_by_stress_mm)
    ld_mm = max(lt_mm, max(0.0, (fps_review_mpa - 2.0 * fpe_mpa / 3.0) * ksi_per_mpa * diameter_mm))
    return {
        "diameter_mm": float(diameter_mm),
        "aps_mm2": float(aps_mm2),
        "fpe_mpa": float(fpe_mpa),
        "fps_review_mpa": float(fps_review_mpa),
        "lt_m": float(lt_mm) / 1000.0,
        "ld_m": float(ld_mm) / 1000.0,
    }


def railway_u_girder_prestress_development_evidence_dataframe(session_state: Any) -> pd.DataFrame:
    """Return guarded transfer/development evidence for Railway U-Girder strand rows.

    PRESTRESS.DEVELOPMENT1 intentionally reports visible evidence only.  It does
    not change the existing station-participation model, does not ramp Pe in the
    SLS/ULS solvers, and does not certify debonded strand anchorage.
    """

    columns = _railway_prestress_development_columns()
    span_m = _railway_uls_span_length_m(session_state)
    rows_in = active_girder_strand_rows(_get(session_state, "girder_strand_layout_table", None))
    if not rows_in:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    half_span = 0.5 * span_m
    for source_row in rows_in[:RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_MAX_ROWS]:
        group_id = str(source_row.get("Group ID") or "strand group")
        total_strands = int(max(0, round(_float_or_zero(source_row.get("No. Strands")))))
        debonded = int(debonded_strand_count_for_row(source_row))
        left_debond = min(max(_float_or_zero(source_row.get("Left debond m")), 0.0), span_m)
        right_debond = min(max(_float_or_zero(source_row.get("Right debond m")), 0.0), span_m)
        lengths = _railway_development_lengths_for_row(source_row)
        lt = float(lengths["lt_m"])
        ld = float(lengths["ld_m"])
        left_full = left_debond + ld
        right_full = span_m - right_debond - ld
        available_left = max(0.0, half_span - left_debond)
        available_right = max(0.0, half_span - right_debond)
        left_dc = ld / available_left if available_left > 0.0 else float("inf")
        right_dc = ld / available_right if available_right > 0.0 else float("inf")
        finite_dcs = [value for value in (left_dc, right_dc) if math.isfinite(value)]
        governing_dc = max(finite_dcs) if finite_dcs else float("inf")
        has_debond = debonded > 0 or left_debond > 1.0e-9 or right_debond > 1.0e-9
        if total_strands <= 0:
            status = "REVIEW"
            development_status = "NO STRANDS"
        elif math.isfinite(governing_dc) and governing_dc <= 1.0 + 1.0e-9:
            status = "Engineering Review PASS"
            development_status = "SCREEN OK"
        else:
            status = "Engineering Review FAIL"
            development_status = "INSUFFICIENT BONDED LENGTH"
        transfer_status = "TRANSFER ZONE VISIBLE" if lt > 0.0 else "REVIEW"
        notes = [
            RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_WARNING,
            "Development D/C compares ld to bonded length from sleeve termination/end to midspan; project-specific critical sections must still be checked.",
            "Existing SLS/ULS solvers still use the previous station participation handoff; no Pe force ramp is applied by this milestone.",
        ]
        if has_debond:
            notes.append("Debonded/sleeved row detected; verify individual strand selection, stagger, and end-zone detailing before final design.")
        else:
            notes.append("Fully bonded row screen; transfer/development zones are reported for traceability.")
        rows.append(
            {
                "Check": "Prestress transfer / development evidence",
                "Status": status,
                "Group ID": group_id,
                "Total strands": total_strands,
                "Debonded strands": debonded,
                "Strand diameter (mm)": lengths["diameter_mm"],
                "Area/strand (mm2)": lengths["aps_mm2"],
                "fpe final (MPa)": lengths["fpe_mpa"],
                "fps review (MPa)": lengths["fps_review_mpa"],
                "Left debond (m)": left_debond,
                "Right debond (m)": right_debond,
                "Transfer length lt (m)": lt,
                "Development length ld (m)": ld,
                "Left full-development station (m)": left_full,
                "Right full-development station (m)": right_full,
                "Available left bond to midspan (m)": available_left,
                "Available right bond to midspan (m)": available_right,
                "Left development D/C": left_dc,
                "Right development D/C": right_dc,
                "Development status": development_status,
                "Transfer zone status": transfer_status,
                "Code basis": "AASHTO/ACI-compatible transfer/development length screen - not certified",
                "Method": "lt = max(60db, fpe·db/3); ld = max(lt, (fps - 2/3 fpe)db), stress converted MPa→ksi; row-level guarded evidence",
                "Evidence status": RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_STATUS,
                "Blocked final claim": "No code-certified or engineer-certified PASS until development benchmark validation, debonded strand anchorage, end-zone bursting/spalling, and Engineer-of-Record review are complete.",
                "Notes": "; ".join(notes),
            }
        )
    return pd.DataFrame(rows, columns=columns)



def _railway_anchorage_end_zone_columns() -> list[str]:
    return [
        "Check",
        "Status",
        "End",
        "Effective end strands",
        "Debonded / sleeved strands",
        "End-zone Pe transfer (kN)",
        "Sleeve termination Pe transfer (kN)",
        "Bursting tie demand Tb (kN)",
        "Sleeve termination tie demand (kN)",
        "Required end-zone As (mm2)",
        "Required sleeve As (mm2)",
        "Assumed tie fy (MPa)",
        "End-zone length (m)",
        "Web fci (MPa)",
        "Concrete stress preview (MPa)",
        "Stress ratio vs 0.60fci",
        "Concrete stress status",
        "Reinforcement status",
        "Sleeve termination status",
        "Code basis",
        "Method",
        "Evidence status",
        "Blocked final claim",
        "Notes",
    ]


def _railway_web_fci_mpa_from_state(session_state: Any) -> float:
    stage = _get(session_state, "railway_u_girder_stage_settings", {}) or {}
    for key in ("web_fci_MPa", "web_fci_mpa", "web_fci", "Web fci MPa"):
        value = _float_or_zero(_get(stage, key, 0.0))
        if math.isfinite(value) and value > 0.0:
            return float(value)
    return 36.0


def _railway_end_zone_tie_fy_mpa(session_state: Any) -> float:
    # Use an explicit future setting when available; otherwise use common SD40 fy.
    settings = _get(session_state, "railway_u_girder_anchorage_settings", {}) or {}
    value = _float_or_zero(_get(settings, "tie_fy_MPa", 0.0))
    if math.isfinite(value) and value > 0.0:
        return float(value)
    return 390.0


def _railway_pe_transfer_per_strand_kN(row: Mapping[str, Any]) -> float:
    for key in (
        "Pe_eff_transfer/strand_kN",
        "Pe_transfer/strand_kN",
        "Pe_release/strand_kN",
        "P_release/strand_kN",
        "Pe_construction/strand_kN",
    ):
        value = _float_or_zero(row.get(key))
        if math.isfinite(value) and value > 0.0:
            return float(value)
    final_value = _float_or_zero(row.get("Pe_eff_final/strand_kN"))
    # Release/transfer force is normally higher than final effective force.  When
    # only final Pe exists, use a visible review factor and disclose it in Notes.
    return 1.15 * float(final_value) if math.isfinite(final_value) and final_value > 0.0 else 0.0


def _railway_end_zone_geometry_basis(session_state: Any) -> dict[str, Any]:
    geometry = _railway_uls_section_geometry_from_state(session_state)
    if geometry is None:
        return {
            "h_mm": float("nan"),
            "bv_mm": float("nan"),
            "area_mm2": float("nan"),
            "end_zone_length_m": float("nan"),
            "note": "Section geometry is missing; end-zone stress preview is unavailable.",
        }
    try:
        _, y_min, _, y_max = _railway_uls_section_bounds(geometry)
        h_mm = max(0.0, float(y_max) - float(y_min))
    except Exception:
        h_mm = float("nan")
    bv_mm, bv_note = _railway_uls_web_width_mm(geometry)
    if bv_mm is None:
        bv_mm = float("nan")
    area = float(bv_mm) * float(h_mm) if math.isfinite(float(bv_mm)) and math.isfinite(float(h_mm)) and bv_mm > 0.0 and h_mm > 0.0 else float("nan")
    end_zone_length = max(1.0, float(h_mm) / 1000.0) if math.isfinite(float(h_mm)) and h_mm > 0.0 else float("nan")
    return {
        "h_mm": float(h_mm),
        "bv_mm": float(bv_mm),
        "area_mm2": area,
        "end_zone_length_m": float(end_zone_length),
        "note": f"End-zone concrete area uses total web width times full section depth for a guarded stress screen. {bv_note}",
    }


def _railway_anchorage_end_aggregate(rows_in: list[Mapping[str, Any]], *, end: str, span_m: float) -> dict[str, Any]:
    effective_strands = 0
    sleeved_strands = 0
    p_end = 0.0
    p_sleeve = 0.0
    sleeve_stations: list[float] = []
    final_fallback_used = False
    for source_row in rows_in:
        total = int(max(0, round(_float_or_zero(source_row.get("No. Strands")))))
        debonded = min(total, int(debonded_strand_count_for_row(source_row)))
        if total <= 0:
            continue
        if end == "Left":
            debond_length = min(max(_float_or_zero(source_row.get("Left debond m")), 0.0), span_m)
            sleeve_station = debond_length
        else:
            debond_length = min(max(_float_or_zero(source_row.get("Right debond m")), 0.0), span_m)
            sleeve_station = max(0.0, span_m - debond_length)
        pe_transfer = _railway_pe_transfer_per_strand_kN(source_row)
        if pe_transfer > 0.0 and _float_or_zero(source_row.get("Pe_eff_transfer/strand_kN")) <= 0.0 and _float_or_zero(source_row.get("Pe_transfer/strand_kN")) <= 0.0 and _float_or_zero(source_row.get("Pe_release/strand_kN")) <= 0.0:
            final_fallback_used = True
        sleeved = debonded if debond_length > 1.0e-9 else 0
        bonded = max(0, total - sleeved)
        effective_strands += bonded
        sleeved_strands += sleeved
        p_end += bonded * pe_transfer
        if sleeved > 0:
            p_sleeve += sleeved * pe_transfer
            sleeve_stations.append(sleeve_station)
    return {
        "effective_strands": effective_strands,
        "sleeved_strands": sleeved_strands,
        "p_end_kN": p_end,
        "p_sleeve_kN": p_sleeve,
        "sleeve_stations": sleeve_stations,
        "final_fallback_used": final_fallback_used,
    }


def railway_u_girder_anchorage_end_zone_evidence_dataframe(session_state: Any) -> pd.DataFrame:
    """Return guarded anchorage/end-zone bursting/spalling evidence.

    ANCHORAGE.RAIL.UGIRDER1 intentionally reports end-zone review evidence only.
    It does not design final anchorage-zone reinforcement, does not validate
    debonded strand termination detailing, and does not change force transfer in
    the SLS/ULS solvers.
    """

    columns = _railway_anchorage_end_zone_columns()
    span_m = _railway_uls_span_length_m(session_state)
    rows_in = active_girder_strand_rows(_get(session_state, "girder_strand_layout_table", None))
    if not rows_in:
        return pd.DataFrame(columns=columns)
    geometry = _railway_end_zone_geometry_basis(session_state)
    fci = _railway_web_fci_mpa_from_state(session_state)
    tie_fy = _railway_end_zone_tie_fy_mpa(session_state)
    phi_tie = 0.90
    rows: list[dict[str, Any]] = []
    for end in ("Left", "Right"):
        agg = _railway_anchorage_end_aggregate(rows_in, end=end, span_m=span_m)
        p_end = float(agg["p_end_kN"])
        p_sleeve = float(agg["p_sleeve_kN"])
        tb = 0.25 * p_end
        sleeve_tb = 0.25 * p_sleeve
        as_req = tb * 1000.0 / (phi_tie * tie_fy) if tie_fy > 0.0 else float("nan")
        as_sleeve = sleeve_tb * 1000.0 / (phi_tie * tie_fy) if tie_fy > 0.0 else float("nan")
        area = _float_or_zero(geometry.get("area_mm2"))
        stress = p_end * 1000.0 / area if area > 0.0 else float("nan")
        stress_ratio = stress / (0.60 * fci) if math.isfinite(stress) and fci > 0.0 else float("nan")
        if math.isfinite(stress_ratio) and stress_ratio > 1.0 + 1.0e-9:
            concrete_status = "REVIEW — HIGH END-ZONE STRESS"
            status = "Engineering Review FAIL"
        elif math.isfinite(stress_ratio):
            concrete_status = "SCREEN OK"
            status = "REVIEW"
        else:
            concrete_status = "REVIEW"
            status = "REVIEW"
        reinforcement_status = "DEDICATED END-ZONE REINFORCEMENT LAYOUT REQUIRED" if p_end > 0.0 else "NO END FORCE"
        if p_sleeve > 0.0:
            sleeve_status = "SLEEVE TERMINATION DETAILING REQUIRED"
        else:
            sleeve_status = "NO DEBONDED SLEEVE TERMINATION FORCE"
        notes = [
            RAILWAY_UGIRDER_ANCHORAGE_END_ZONE_WARNING,
            str(geometry.get("note") or ""),
            "Bursting tie demand is a guarded screen Tb = 0.25P; it is not a final strut-and-tie or anchorage-zone reinforcement design.",
            "Required As uses φ=0.90 and the displayed tie fy; define actual end-zone bars, confinement, splitting steel, and local bursting layout before final design.",
            "Concrete stress preview uses end-face bonded strand transfer force divided by total web area; validate with project-specific end-region model.",
        ]
        if agg.get("final_fallback_used"):
            notes.append("No explicit transfer/release Pe per strand was found for at least one row; transfer force used 1.15×final Pe as a visible review fallback.")
        if p_sleeve > 0.0:
            stations = ", ".join(f"{float(item):.3f}" for item in agg.get("sleeve_stations", []))
            notes.append(f"Debonded/sleeved strand termination force is reported separately at station(s) {stations} m from the left end; local splitting reinforcement must be detailed there.")
        rows.append({
            "Check": "Anchorage / end-zone bursting evidence",
            "Status": status,
            "End": end,
            "Effective end strands": int(agg["effective_strands"]),
            "Debonded / sleeved strands": int(agg["sleeved_strands"]),
            "End-zone Pe transfer (kN)": p_end,
            "Sleeve termination Pe transfer (kN)": p_sleeve,
            "Bursting tie demand Tb (kN)": tb,
            "Sleeve termination tie demand (kN)": sleeve_tb,
            "Required end-zone As (mm2)": as_req,
            "Required sleeve As (mm2)": as_sleeve,
            "Assumed tie fy (MPa)": tie_fy,
            "End-zone length (m)": geometry.get("end_zone_length_m", float("nan")),
            "Web fci (MPa)": fci,
            "Concrete stress preview (MPa)": stress,
            "Stress ratio vs 0.60fci": stress_ratio,
            "Concrete stress status": concrete_status,
            "Reinforcement status": reinforcement_status,
            "Sleeve termination status": sleeve_status,
            "Code basis": "AASHTO/ACI-compatible anchorage-zone bursting/spalling review screen - not certified",
            "Method": "Pretensioned end-zone evidence: bonded end force P, Tb=0.25P, As=Tb/(φfy); debonded sleeve termination force reported separately; no solver force-ramp change.",
            "Evidence status": RAILWAY_UGIRDER_ANCHORAGE_END_ZONE_STATUS,
            "Blocked final claim": "No code-certified or engineer-certified PASS until project-specific anchorage-zone reinforcement, debonded strand termination detailing, end-region benchmarks, and Engineer-of-Record review are complete.",
            "Notes": "; ".join(str(item) for item in notes if str(item).strip()),
        })
    return pd.DataFrame(rows, columns=columns)

def railway_u_girder_uls_code_basis_dataframe() -> pd.DataFrame:
    route = bridge_beam_girder_uls_strength_route()
    rows = [
        {"Item": "Workflow route", "Value": route.workflow_label, "Status": "LOCKED", "Evidence / Boundary": "Railway U-Girder is routed through Bridge Beam/Girder ULS, not Building ULS."},
        {"Item": "Design code basis", "Value": route.display_code_label, "Status": "GUARDED", "Evidence / Boundary": "Project-specific railway criteria and owner requirements still govern final adoption."},
        {"Item": "ULS load source", "Value": route.uls_load_source_label, "Status": "SOURCE OF TRUTH", "Evidence / Boundary": "Analysis consumes active station-resultant ULS rows from Loads."},
        {"Item": "Default strength combo label", "Value": route.default_combo_label, "Status": "REVIEW", "Evidence / Boundary": "Actual project load combinations must be reviewed before final design."},
        {"Item": "Flexure route", "Value": route.flexure_engine_label, "Status": "FRAMEWORK READY", "Evidence / Boundary": route.flexure_basis_note},
        {"Item": "Shear route", "Value": route.shear_engine_label, "Status": "ENGINEERING REVIEW READY", "Evidence / Boundary": "ULS.RAIL.UGIRDER3 provides guarded PSC shear route evidence using active Vuy demands and provided stirrup zones; final Vci/Vcw/Vp/end-region certification remains future work."},
        {"Item": "Torsion route", "Value": route.torsion_engine_label, "Status": "ENGINEERING REVIEW READY", "Evidence / Boundary": "ULS.RAIL.UGIRDER4 provides guarded torsion / V+T evidence using active Tu/Vuy demands, closed-hoop zones, and ordinary rebar Al; final multi-cell/PSC/V+T calibration remains future work."},
        {"Item": "Prestress development route", "Value": "Transfer / development length evidence", "Status": "ENGINEERING REVIEW READY", "Evidence / Boundary": "PRESTRESS.DEVELOPMENT1 provides guarded row-level transfer/development length evidence from the active strand/debonding table; it does not apply Pe force ramps or certify anchorage/end-zone detailing."},
        {"Item": "Anchorage / end-zone route", "Value": "Bursting / spalling evidence", "Status": "ENGINEERING REVIEW READY", "Evidence / Boundary": "ANCHORAGE.RAIL.UGIRDER1 provides guarded end-zone force, bursting tie demand, concrete stress, and debond sleeve-termination review evidence; final anchorage-zone reinforcement design and benchmark validation remain future work."},
        {"Item": "Certification boundary", "Value": "Not engineer-certified", "Status": "NOT CERTIFIED", "Evidence / Boundary": RAILWAY_UGIRDER_ULS_CERTIFICATION_BOUNDARY},
    ]
    return pd.DataFrame(rows, columns=["Item", "Value", "Status", "Evidence / Boundary"])


def railway_u_girder_uls_demand_summary_dataframe(active_uls: pd.DataFrame) -> pd.DataFrame:
    active_uls = active_uls.copy() if isinstance(active_uls, pd.DataFrame) else pd.DataFrame()
    if active_uls.empty:
        rows = [
            {"Demand Item": "Active ULS station rows", "Value": 0.0, "Unit": "rows", "Governing Case": "-", "Governing x (m)": "-", "Status": "INPUT REQUIRED"},
            {"Demand Item": "ULS demand readiness", "Value": "No active ULS Loads rows", "Unit": "-", "Governing Case": "-", "Governing x (m)": "-", "Status": "NOT READY"},
        ]
        return pd.DataFrame(rows, columns=["Demand Item", "Value", "Unit", "Governing Case", "Governing x (m)", "Status"])
    rows: list[dict[str, Any]] = [
        {"Demand Item": "Active ULS station rows", "Value": float(len(active_uls.index)), "Unit": "rows", "Governing Case": "-", "Governing x (m)": "-", "Status": "AVAILABLE"},
    ]
    demand_columns = [
        ("Mux", "Peak |Mux|", "kN-m"),
        ("Vuy", "Peak |Vuy|", "kN"),
        ("Tu", "Peak |Tu|", "kN-m"),
        ("Muy", "Peak |Muy|", "kN-m"),
        ("Vux", "Peak |Vux|", "kN"),
        ("Nu", "Peak |Nu|", "kN"),
    ]
    for column, label, unit in demand_columns:
        series = pd.to_numeric(active_uls.get(column, pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        if series.empty:
            peak = 0.0
            idx = None
        else:
            abs_series = series.abs()
            idx = abs_series.idxmax()
            peak = float(abs_series.loc[idx]) if idx is not None else 0.0
        row = active_uls.loc[idx] if idx is not None and idx in active_uls.index else {}
        rows.append(
            {
                "Demand Item": label,
                "Value": peak,
                "Unit": unit,
                "Governing Case": str(_get(row, "Case Name", "-")),
                "Governing x (m)": float(_get(row, "Station x (m)", 0.0)) if idx is not None else "-",
                "Status": "AVAILABLE" if peak > 0.0 else "ZERO / REVIEW",
            }
        )
    return pd.DataFrame(rows, columns=["Demand Item", "Value", "Unit", "Governing Case", "Governing x (m)", "Status"])


def railway_u_girder_uls_check_matrix_dataframe(active_uls: pd.DataFrame) -> pd.DataFrame:
    has_loads = isinstance(active_uls, pd.DataFrame) and not active_uls.empty
    demand_status = "DEMAND AVAILABLE" if has_loads else "INPUT REQUIRED"
    rows = [
        {
            "Check Area": "ULS flexure",
            "Current Framework Status": "FRAMEWORK READY" if has_loads else "INPUT REQUIRED",
            "Demand Source": demand_status,
            "Capacity / Code Route": "ULS.RAIL.UGIRDER2 uses existing PMM strain-compatibility solver plus AASHTO LRFD prestressed flexure phi layer; Railway-specific benchmark validation still required",
            "Allowed Decision Wording": "Engineering Review PASS / FAIL allowed for flexure evidence only; not Certified PASS",
            "Blocked Final Claim": "No final design certification until Railway U-Girder flexure benchmarks, development length, anchorage/end-zone, and time-dependent checks are complete.",
        },
        {
            "Check Area": "ULS shear",
            "Current Framework Status": "ENGINEERING REVIEW READY" if has_loads else "INPUT REQUIRED",
            "Demand Source": demand_status,
            "Capacity / Code Route": "ULS.RAIL.UGIRDER3 uses an AASHTO LRFD-compatible PSC shear route with active Vuy demands, provided stirrups, explicit bv/dv basis, φVc/φVs, detailing guard, and Vn cap; refined Vci/Vcw/Vp and end-region route remain future work",
            "Allowed Decision Wording": "Engineering Review PASS / FAIL allowed for shear route evidence only; not Certified PASS",
            "Blocked Final Claim": "No final shear certification until PSC shear benchmarks, refined Vci/Vcw/Vp, development length, anchorage/end-zone, and critical-section checks pass.",
        },
        {
            "Check Area": "ULS torsion",
            "Current Framework Status": "ENGINEERING REVIEW READY" if has_loads else "INPUT REQUIRED",
            "Demand Source": demand_status,
            "Capacity / Code Route": "ULS.RAIL.UGIRDER4 uses an AASHTO LRFD-compatible closed-hoop torsion guard with active Tu demands, active transverse zones, threshold screen, ordinary rebar Al, and detailing gates; final Railway multi-cell/PSC torsion calibration remains future work",
            "Allowed Decision Wording": "Engineering Review PASS / FAIL allowed for torsion guard evidence only; not Certified PASS",
            "Blocked Final Claim": "No final torsion certification until section-type torsion route, closed torsion cell, PSC effects, development length, anchorage/end-zone, and benchmarks are validated.",
        },
        {
            "Check Area": "Combined V+T",
            "Current Framework Status": "GUARDED PREVIEW" if has_loads else "INPUT REQUIRED",
            "Demand Source": demand_status,
            "Capacity / Code Route": "ULS.RAIL.UGIRDER4 exposes a linear V+T review index from the guarded shear and torsion source rows; it is not final calibrated code interaction design",
            "Allowed Decision Wording": "Engineering Review PASS / FAIL allowed for V+T guard evidence only; not Certified PASS",
            "Blocked Final Claim": "Separate guarded shear/torsion/V+T rows must not be read as final combined V+T certification until calibrated code interaction and benchmarks are complete.",
        },
        {
            "Check Area": "Prestress transfer / development",
            "Current Framework Status": "ENGINEERING REVIEW READY",
            "Demand Source": "Active strand/debonding table from the Prestress workflow",
            "Capacity / Code Route": "PRESTRESS.DEVELOPMENT1 provides guarded transfer-length and development-length evidence; force ramping, anchorage/end-zone bursting, and benchmark certification remain outside this milestone",
            "Allowed Decision Wording": "Engineering Review PASS / FAIL allowed for development evidence only; not Certified PASS",
            "Blocked Final Claim": "No final prestressed girder design until development benchmark validation, debonded anchorage detailing, and end-zone checks are complete.",
        },
        {
            "Check Area": "Anchorage / end-zone",
            "Current Framework Status": "ENGINEERING REVIEW READY",
            "Demand Source": "Active strand/debonding table, stage web f'ci, and current Railway U-Girder geometry",
            "Capacity / Code Route": "ANCHORAGE.RAIL.UGIRDER1 provides guarded end-zone bursting/spalling force screens, required tie-steel evidence, concrete stress ratio, and debond sleeve-termination review notes; final reinforcement layout design remains outside this milestone",
            "Allowed Decision Wording": "Engineering Review / reinforcement layout required; not Certified PASS",
            "Blocked Final Claim": "No final prestressed girder design without project-specific anchorage-zone reinforcement detailing, debonded strand termination validation, benchmarks, and Engineer-of-Record review.",
        },
        {
            "Check Area": "Independent benchmark validation",
            "Current Framework Status": "FUTURE WORK",
            "Demand Source": "Future published/reference examples and independent hand calculations",
            "Capacity / Code Route": "Railway U-Girder flexure, shear, torsion/V+T, development, and anchorage/end-zone evidence still need independent benchmark validation before final certification wording",
            "Allowed Decision Wording": "Excluded from current framework",
            "Blocked Final Claim": "No final code-certified design claim without benchmark validation and Engineer-of-Record review.",
        },
        {
            "Check Area": "Final design certification",
            "Current Framework Status": "NOT CERTIFIED",
            "Demand Source": "Framework evidence only",
            "Capacity / Code Route": "Requires Engineer-of-Record review, project load criteria, validated benchmarks, and final report",
            "Allowed Decision Wording": "Ready for engineering review",
            "Blocked Final Claim": "Do not use code-certified pass wording or final-design pass wording in this milestone.",
        },
    ]
    return pd.DataFrame(rows)


def railway_u_girder_uls_future_checks_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Priority": index,
                "Required Future Check": item,
                "Reason Final Certification Is Blocked": "Required before Railway U-Girder final code-certified design can be claimed.",
            }
            for index, item in enumerate(RAILWAY_UGIRDER_ULS_REQUIRED_FUTURE_CHECKS, start=1)
        ],
        columns=["Priority", "Required Future Check", "Reason Final Certification Is Blocked"],
    )


def railway_u_girder_uls_closeout_boundary_dataframe() -> pd.DataFrame:
    rows = [
        {"Item": "ULS framework milestone", "Status": RAILWAY_UGIRDER_ULS_FRAMEWORK_STATUS, "Evidence / Boundary": RAILWAY_UGIRDER_ULS_FRAMEWORK_WARNING},
        {"Item": "Allowed use", "Status": "READY FOR ENGINEERING REVIEW", "Evidence / Boundary": "Use for ULS workflow planning, demand traceability, and guarded design-check review."},
        {"Item": "Prohibited claim", "Status": "NOT CERTIFIED", "Evidence / Boundary": "Do not use code-certified pass wording, final-design pass wording, or engineer-certified wording from this milestone."},
        {"Item": "Final certification boundary", "Status": "FUTURE WORK", "Evidence / Boundary": RAILWAY_UGIRDER_ULS_CERTIFICATION_BOUNDARY},
    ]
    return pd.DataFrame(rows, columns=["Item", "Status", "Evidence / Boundary"])


def build_railway_u_girder_uls_framework_package(session_state: Any) -> RailwayUGirderULSFrameworkPackage:
    """Build guarded ULS framework tables for the active Railway U-Girder project."""

    if not is_railway_u_girder_uls_context(session_state):
        return RailwayUGirderULSFrameworkPackage(
            available=False,
            status="Not applicable — Railway U-Girder context not detected",
            warnings=["Railway U-Girder ULS framework package is only available for the Railway U-Girder preset."],
        )
    active_uls = active_railway_u_girder_uls_demand_dataframe(session_state)
    warnings = [RAILWAY_UGIRDER_ULS_FRAMEWORK_WARNING, RAILWAY_UGIRDER_ULS_FLEXURE_EVIDENCE_WARNING, RAILWAY_UGIRDER_ULS_SHEAR_EVIDENCE_WARNING, RAILWAY_UGIRDER_ULS_TORSION_VT_GUARD_WARNING, RAILWAY_UGIRDER_PRESTRESS_DEVELOPMENT_WARNING, RAILWAY_UGIRDER_ANCHORAGE_END_ZONE_WARNING]
    if active_uls.empty:
        warnings.append("No active ULS Loads rows were found; define Strength ULS station-resultant rows before running design checks.")
    flexure_evidence = railway_u_girder_uls_flexure_evidence_dataframe(session_state, active_uls)
    shear_evidence = railway_u_girder_uls_shear_evidence_dataframe(session_state, active_uls)
    if flexure_evidence.empty and not active_uls.empty:
        warnings.append("No nonzero Mux station rows were available for ULS.RAIL.UGIRDER2 flexure evidence.")
    torsion_vt_guard = railway_u_girder_uls_torsion_vt_guard_dataframe(session_state, active_uls, shear_evidence)
    prestress_development_evidence = railway_u_girder_prestress_development_evidence_dataframe(session_state)
    anchorage_end_zone_evidence = railway_u_girder_anchorage_end_zone_evidence_dataframe(session_state)
    if shear_evidence.empty and not active_uls.empty:
        warnings.append("No nonzero Vuy station rows were available for ULS.RAIL.UGIRDER3 PSC shear route evidence.")
    if torsion_vt_guard.empty and not active_uls.empty:
        warnings.append("No nonzero Tu or Vuy station rows were available for ULS.RAIL.UGIRDER4 torsion / V+T guard evidence.")
    if prestress_development_evidence.empty:
        warnings.append("No active strand rows were available for PRESTRESS.DEVELOPMENT1 transfer/development evidence.")
    if anchorage_end_zone_evidence.empty:
        warnings.append("No active strand rows were available for ANCHORAGE.RAIL.UGIRDER1 anchorage/end-zone evidence.")
    return RailwayUGirderULSFrameworkPackage(
        available=True,
        status=RAILWAY_UGIRDER_ULS_FRAMEWORK_STATUS,
        closeout_boundary=railway_u_girder_uls_closeout_boundary_dataframe(),
        code_basis=railway_u_girder_uls_code_basis_dataframe(),
        demand_summary=railway_u_girder_uls_demand_summary_dataframe(active_uls),
        flexure_evidence=flexure_evidence,
        shear_evidence=shear_evidence,
        torsion_vt_guard=torsion_vt_guard,
        prestress_development_evidence=prestress_development_evidence,
        anchorage_end_zone_evidence=anchorage_end_zone_evidence,
        check_matrix=railway_u_girder_uls_check_matrix_dataframe(active_uls),
        future_checks=railway_u_girder_uls_future_checks_dataframe(),
        warnings=warnings,
    )

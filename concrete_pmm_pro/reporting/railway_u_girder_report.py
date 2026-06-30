"""Railway U-Girder SLS engineering-review report helpers.

REPORT.RAIL.UGIRDER1 converts the accepted Railway U-Girder staged SLS
workflow into report-ready tables while preserving the guarded status.  These
helpers intentionally reuse the existing Railway U-Girder SLS preview functions;
they do not add final code-certified design checks, transfer/development length,
anchorage/end-zone, or time-dependent redistribution logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd

from concrete_pmm_pro.core.models import LoadCase, SectionGeometry
from concrete_pmm_pro.serviceability.girder_prestress_station import evaluate_girder_prestress_station
from concrete_pmm_pro.serviceability.girder_sls_load_components import BEAM_GIRDER_SYSTEM_SETTINGS_KEY, system_settings_from_mapping
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    RailwayUGirderStageBasisSet,
    railway_u_girder_final_service_accumulation_dataframe,
    railway_u_girder_final_service_governing_rows,
    railway_u_girder_final_service_limit_check_dataframe,
    railway_u_girder_parameter_snapshot_from_geometry,
    railway_u_girder_stage_basis_set,
    railway_u_girder_stage_limit_governing_rows,
    railway_u_girder_stage_governing_rows,
    railway_u_girder_staged_stress_limit_check_dataframe,
    railway_u_girder_staged_stress_preview_dataframe,
    railway_u_girder_sls_decision_summary_dataframe,
)

RAILWAY_UGIRDER_REPORT_STATUS = "SLS engineering-review report-ready; not final code-certified"
RAILWAY_UGIRDER_REPORT_CAPABILITY = (
    "Railway U-Girder staged SLS workflow is available for engineering-review preview. "
    "It includes geometry, material/assembly settings, strand/debonding input, "
    "station-based strand participation, transfer/lifting/construction/service staged "
    "stress previews, service multi-fiber stress plotting, and guarded decision summaries."
)
RAILWAY_UGIRDER_REPORT_EXCLUSIONS = [
    "transfer length force ramp",
    "development length",
    "anchorage / end-zone bursting",
    "lifting insert/local hardware check",
    "creep/shrinkage redistribution",
    "full time-dependent transformed composite analysis",
    "ULS Railway U-Girder PMM/shear coupling",
    "final code-certified design checks",
]

RAILWAY_UGIRDER_CLOSEOUT_STATUS = "Railway U-Girder SLS Engineering Review Package - Closeout Ready"
RAILWAY_UGIRDER_CLOSEOUT_SCOPE = (
    "Closeout-ready means the Railway U-Girder SLS engineering-review workflow has report tables, "
    "Word export, QA guardrails, and regression evidence for the current preview scope. "
    "It does not mean final code-certified design."
)

RAILWAY_UGIRDER_REPORT_TABLE_KEYS = [
    "railway_u_girder_closeout_status",
    "railway_u_girder_sls_scope",
    "railway_u_girder_geometry_summary",
    "railway_u_girder_material_stage_settings",
    "railway_u_girder_stage_quantities",
    "railway_u_girder_prestress_debonding_summary",
    "railway_u_girder_sls_stage_governing",
    "railway_u_girder_sls_limit_governing",
    "railway_u_girder_sls_final_service_governing",
    "railway_u_girder_sls_decision_summary",
    "railway_u_girder_service_multifiber_summary",
]


def _get(mapping: Any, key: str, default: Any = None) -> Any:
    if mapping is None:
        return default
    if hasattr(mapping, "get"):
        try:
            return mapping.get(key, default)
        except (AttributeError, TypeError, ValueError):
            return default
    return getattr(mapping, key, default)


def _is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, bytes)):
        return bool(value)
    if isinstance(value, (int, float)):
        return value != 0
    empty = getattr(value, "empty", None)
    if isinstance(empty, bool):
        return not empty
    try:
        return bool(value)
    except (TypeError, ValueError):
        return False


def _to_dataframe(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(value).copy()
    except Exception:
        return pd.DataFrame()


def _float_or_none(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _float_or_default(value: Any, default: float) -> float:
    numeric = _float_or_none(value)
    return float(default) if numeric is None else float(numeric)


def _positive_float(value: Any, default: float) -> float:
    numeric = _float_or_default(value, default)
    return numeric if numeric > 0.0 else float(default)


def _section_metadata(geometry: SectionGeometry | None) -> Mapping[str, Any]:
    metadata = getattr(geometry, "metadata", {}) or {}
    return metadata if isinstance(metadata, Mapping) else {}


def is_railway_u_girder_report_context(session_state: Any) -> bool:
    """Return True when current context is the Railway U-Girder workflow."""

    geometry = _get(session_state, "section_geometry")
    metadata = _section_metadata(geometry)
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
    for params_key in ("section_parameters", "active_section_parameters"):
        params = _get(session_state, params_key, {})
        if isinstance(params, Mapping):
            keys = {str(key) for key in params.keys()}
            if {"h1_step_height_mm", "h2_bottom_opening_mm", "h3_floor_side_thickness_mm", "h4_floor_center_thickness_mm"}.issubset(keys):
                return True
    settings = _get(session_state, "railway_u_girder_stage_settings", {})
    if isinstance(settings, Mapping):
        method = str(settings.get("construction_method") or "").casefold()
        has_triplet = all(key in settings for key in ("web_fc_MPa", "web_fci_MPa", "slab_fc_MPa"))
        if has_triplet and ("wet slab" in method or "precast web" in method or "case b" in method):
            return True
    return False


def _span_length_from_session(session_state: Any) -> float:
    system = system_settings_from_mapping(_get(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY, None))
    if system.span_length_m > 0.0:
        return float(system.span_length_m)
    ps_settings = _get(session_state, "girder_prestress_system_settings", {})
    if isinstance(ps_settings, Mapping):
        span = _float_or_none(ps_settings.get("span_length_m"))
        if span and span > 0.0:
            return float(span)
    return 10.0


def _stage_settings_from_session(session_state: Any) -> dict[str, Any]:
    settings = _get(session_state, "railway_u_girder_stage_settings", {})
    if not isinstance(settings, Mapping):
        settings = {}
    defaults: dict[str, Any] = {
        "web_fc_MPa": 45.0,
        "web_fci_MPa": 36.0,
        "slab_fc_MPa": 35.0,
        "concrete_unit_weight_kN_m3": 24.0,
        "support_condition": "Simply supported",
        "construction_method": "Case B - wet slab carried by precast webs",
        "wet_slab_distribution_each_web": 0.5,
        "formwork_construction_load_kN_m2": 2.5,
        "lifting_point_ratio": 0.20,
        "lifting_impact_factor": 1.10,
    }
    defaults.update(dict(settings))
    return defaults


def _active_sls_load_cases_from_session(session_state: Any) -> list[Any]:
    load_cases = list(_get(session_state, "load_cases", []) or [])
    active = []
    for item in load_cases:
        load_type = str(_get(item, "load_type", "") or "").strip().upper()
        is_active = bool(_get(item, "active", True))
        if is_active and load_type == "SLS":
            active.append(item)
    if active:
        return active

    table = _to_dataframe(_get(session_state, "beam_sls_loads_table", None))
    if table.empty:
        return []
    rows: list[dict[str, Any]] = []
    for idx, row in table.iterrows():
        is_active = bool(row.get("Active", True))
        stage = str(row.get("Stage") or "").casefold()
        if not is_active or (stage and "service" not in stage):
            continue
        rows.append(
            {
                "name": str(row.get("Case Name") or f"SLS-{idx + 1}"),
                "load_type": "SLS",
                "active": True,
                "Pu_N": 1000.0 * _float_or_default(row.get("N"), 0.0),
                "Mux_Nmm": 1_000_000.0 * _float_or_default(row.get("Mx"), 0.0),
                "Muy_Nmm": 1_000_000.0 * _float_or_default(row.get("My"), 0.0),
            }
        )
    return rows


def _default_report_station(span_length_m: float) -> float:
    return max(float(span_length_m), 0.001) / 2.0


def railway_u_girder_scope_dataframe(*, active_sls_count: int = 0) -> pd.DataFrame:
    rows = [
        {"Item": "Report status", "Value": RAILWAY_UGIRDER_REPORT_STATUS},
        {"Item": "Capability statement", "Value": RAILWAY_UGIRDER_REPORT_CAPABILITY},
        {"Item": "Active SLS load cases", "Value": int(active_sls_count)},
        {"Item": "Decision wording", "Value": "Preview PASS / REVIEW only; not final code-certified."},
        {"Item": "Double-counting guard", "Value": "Final service Loads-tab values are treated as additional post-composite service actions; do not include auto web/wet-slab self-weight again unless intentionally checking total-resultant cases."},
    ]
    rows.extend({"Item": "Excluded from current report", "Value": item} for item in RAILWAY_UGIRDER_REPORT_EXCLUSIONS)
    return pd.DataFrame(rows, columns=["Item", "Value"])



def railway_u_girder_closeout_status_dataframe(
    *,
    active_sls_count: int = 0,
    warnings: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Return the Railway U-Girder closeout status table.

    CLOSEOUT.RAIL.UGIRDER1 is a project-delivery guard, not a design-strength
    upgrade.  The table makes the closing state explicit in the report package
    so reviewers cannot confuse "report-ready" with "code-certified".
    """

    warning_count = len(list(warnings or []))
    rows = [
        {
            "Closeout Item": "Package status",
            "Status": RAILWAY_UGIRDER_CLOSEOUT_STATUS,
            "Evidence / Boundary": RAILWAY_UGIRDER_CLOSEOUT_SCOPE,
        },
        {
            "Closeout Item": "Design certification status",
            "Status": "NOT CERTIFIED",
            "Evidence / Boundary": "Engineering-review evidence only; independent engineer review and project-specific code validation are still required.",
        },
        {
            "Closeout Item": "Implemented Railway U-Girder scope",
            "Status": "READY FOR ENGINEERING REVIEW",
            "Evidence / Boundary": "Geometry, material/stage settings, strand/debonding handoff, staged SLS previews, service multi-fiber summary, Word report section, and report QA guards are present.",
        },
        {
            "Closeout Item": "Allowed decision wording",
            "Status": "GUARDED",
            "Evidence / Boundary": "Use Preview PASS / REVIEW / not final code-certified. Do not use Final Design PASS or code-certified approval wording.",
        },
        {
            "Closeout Item": "Active SLS service load cases",
            "Status": "AVAILABLE" if int(active_sls_count) > 0 else "REVIEW",
            "Evidence / Boundary": f"Active SLS load case count = {int(active_sls_count)}. Final service rows remain REVIEW when no active SLS service action is supplied.",
        },
        {
            "Closeout Item": "Open report warnings",
            "Status": "REVIEW" if warning_count else "NONE RECORDED",
            "Evidence / Boundary": f"Report package warning count = {warning_count}.",
        },
        {
            "Closeout Item": "Explicit exclusions",
            "Status": "DISCLOSED",
            "Evidence / Boundary": "; ".join(RAILWAY_UGIRDER_REPORT_EXCLUSIONS),
        },
    ]
    return pd.DataFrame(rows, columns=["Closeout Item", "Status", "Evidence / Boundary"])


def railway_u_girder_geometry_summary_dataframe(geometry: SectionGeometry | None) -> pd.DataFrame:
    params = railway_u_girder_parameter_snapshot_from_geometry(geometry)
    labels = {
        "width_mm": "Overall width B",
        "depth_mm": "Overall depth H",
        "top_wall_width_mm": "Top side-wall width",
        "bottom_side_width_mm": "Bottom side block width",
        "inner_half_width_mm": "Inner clear half width",
        "haunch_x_mm": "Haunch X",
        "haunch_y_mm": "Haunch Y",
        "h1_step_height_mm": "h1 step from bottom",
        "h2_bottom_opening_mm": "h2 bottom recess",
        "h3_floor_side_thickness_mm": "h3 side floor thickness",
        "h4_floor_center_thickness_mm": "h4 center floor thickness",
    }
    rows = [
        {"Parameter": label, "Value": float(params[key]), "Unit": "mm", "Source": "Railway U-Girder geometry metadata/default"}
        for key, label in labels.items()
        if key in params
    ]
    rows.append({"Parameter": "Fixed chamfer", "Value": 25.0, "Unit": "mm", "Source": "Accepted Railway U-Girder drawing detail"})
    return pd.DataFrame(rows, columns=["Parameter", "Value", "Unit", "Source"])


def railway_u_girder_material_stage_settings_dataframe(settings: Mapping[str, Any]) -> pd.DataFrame:
    rows = [
        ("Precast web f'c", _positive_float(settings.get("web_fc_MPa"), 45.0), "MPa", "Final web concrete strength"),
        ("Precast web f'ci", _positive_float(settings.get("web_fci_MPa"), 36.0), "MPa", "Transfer/release and lifting strength; protected from 45 MPa routing regression"),
        ("CIP slab f'c", _positive_float(settings.get("slab_fc_MPa"), 35.0), "MPa", "Service multi-fiber slab limit basis"),
        ("Concrete unit weight", _positive_float(settings.get("concrete_unit_weight_kN_m3"), 24.0), "kN/m3", "Self-weight basis"),
        ("Formwork/construction load", _positive_float(settings.get("formwork_construction_load_kN_m2"), 2.5), "kN/m2", "Wet slab construction stage"),
        ("Wet slab distribution to each web", _positive_float(settings.get("wet_slab_distribution_each_web"), 0.5), "ratio", "Case B distribution"),
        ("Lifting point a/L", _positive_float(settings.get("lifting_point_ratio"), 0.20), "ratio", "Two-point lifting preview"),
        ("Lifting impact factor", _positive_float(settings.get("lifting_impact_factor"), 1.10), "factor", "Temporary lifting preview"),
        ("Construction method", str(settings.get("construction_method") or "Case B - wet slab carried by precast webs"), "text", "Workflow assumption"),
    ]
    return pd.DataFrame(
        [{"Setting": name, "Value": value, "Unit": unit, "Report note": note} for name, value, unit, note in rows],
        columns=["Setting", "Value", "Unit", "Report note"],
    )


def railway_u_girder_stage_quantities_dataframe(basis_set: RailwayUGirderStageBasisSet, *, span_length_m: float, settings: Mapping[str, Any]) -> pd.DataFrame:
    q = basis_set.quantities
    lift_factor = _positive_float(settings.get("lifting_impact_factor"), 1.10)
    lift_ratio = _positive_float(settings.get("lifting_point_ratio"), 0.20)
    rows = [
        ("Precast web area (one side)", q.web_area_mm2 / 1_000_000.0, "m2", "Transfer/lifting/wet slab web-only basis"),
        ("CIP slab area", q.slab_area_mm2 / 1_000_000.0, "m2", "Cast-in-place slab between webs"),
        ("Full U-girder gross area", q.full_area_mm2 / 1_000_000.0, "m2", "Service gross reference"),
        ("Web self-weight (one side)", q.web_self_weight_kN_m, "kN/m", "Transfer automatic load"),
        ("Wet slab self-weight to each web", q.wet_slab_to_each_web_kN_m, "kN/m", "Case B, 50/50 distribution by default"),
        ("Formwork/construction load to each web", q.formwork_to_each_web_kN_m, "kN/m", "Construction temporary load"),
        ("Lifting web load with impact", q.web_self_weight_kN_m * lift_factor, "kN/m", f"Two-point lifting at a={lift_ratio * span_length_m:.3f} m from each end"),
        ("Projected slab width", q.projected_slab_width_m, "m", "Used for wet slab/formwork load conversion"),
    ]
    return pd.DataFrame(
        [{"Quantity": name, "Value": value, "Unit": unit, "Stage use": note} for name, value, unit, note in rows],
        columns=["Quantity", "Value", "Unit", "Stage use"],
    )


def railway_u_girder_prestress_debonding_summary_dataframe(strand_table: pd.DataFrame | None, *, span_length_m: float) -> pd.DataFrame:
    df = _to_dataframe(strand_table)
    if df.empty:
        return pd.DataFrame(columns=["Item", "Value", "Unit", "Note"])
    active_mask = df.get("Active", True)
    if isinstance(active_mask, pd.Series):
        active_df = df[active_mask.astype(bool)].copy()
    else:
        active_df = df.copy()
    strands = pd.to_numeric(active_df.get("No. Strands"), errors="coerce").fillna(0.0)
    aps = pd.to_numeric(active_df.get("Total Aps_mm2"), errors="coerce").fillna(0.0)
    debond_text = active_df.get("Debonded strand nos", pd.Series([], dtype=object)).astype(str).str.strip() if "Debonded strand nos" in active_df.columns else pd.Series([], dtype=object)
    debond_rows = int((debond_text != "").sum()) if len(debond_text) else 0
    rows = [
        {"Item": "Active strand rows", "Value": int(len(active_df)), "Unit": "rows", "Note": "Rows included in station participation"},
        {"Item": "Total active strands", "Value": int(strands.sum()), "Unit": "strands", "Note": "Expected default Railway U-Girder total = 72"},
        {"Item": "Total Aps", "Value": float(aps.sum()), "Unit": "mm2", "Note": "Active prestressing steel area"},
        {"Item": "Rows with debonded strand numbers", "Value": debond_rows, "Unit": "rows", "Note": "Station participation is reduced inside debonded zones"},
    ]
    try:
        mid = evaluate_girder_prestress_station(active_df, x_m=max(float(span_length_m), 0.001) / 2.0, span_length_m=max(float(span_length_m), 0.001))
        near = evaluate_girder_prestress_station(active_df, x_m=min(max(float(span_length_m) * 0.05, 0.0), max(float(span_length_m), 0.001)), span_length_m=max(float(span_length_m), 0.001))
        rows.extend(
            [
                {"Item": "Effective strands near end", "Value": int(getattr(near, "effective_strands", 0) or 0), "Unit": "strands", "Note": "Station-based debonding participation sample"},
                {"Item": "Effective strands at midspan", "Value": int(getattr(mid, "effective_strands", 0) or 0), "Unit": "strands", "Note": "Station-based debonding participation sample"},
                {"Item": "Pe_final at midspan", "Value": float(getattr(mid, "pe_eff_final_eff_kN", 0.0) or 0.0), "Unit": "kN", "Note": "Effective final prestress handoff"},
            ]
        )
    except Exception as exc:
        rows.append({"Item": "Station participation", "Value": "REVIEW", "Unit": "status", "Note": f"Unable to evaluate station participation: {exc}"})
    return pd.DataFrame(rows, columns=["Item", "Value", "Unit", "Note"])


def railway_u_girder_service_multifiber_summary_dataframe(final_df: pd.DataFrame, settings: Mapping[str, Any], *, geometry: SectionGeometry | None = None) -> pd.DataFrame:
    """Return report table for top/bottom web and top/bottom slab service fibers.

    The table uses the same linear-through-depth sampling basis as the UI
    service multi-fiber plot.  It is a report summary, not a new solver.
    """

    df = _to_dataframe(final_df)
    if df.empty:
        return pd.DataFrame(columns=["Load Case", "Station x (m)", "Fiber", "Concrete component", "f'c basis (MPa)", "Stress (MPa)", "Report basis"])
    params = railway_u_girder_parameter_snapshot_from_geometry(geometry)
    depth = _positive_float(params.get("depth_mm"), 1600.0)
    h2 = _positive_float(params.get("h2_bottom_opening_mm"), 305.0)
    h4 = _positive_float(params.get("h4_floor_center_thickness_mm"), 450.0)
    slab_bottom = max(depth - h4, depth - h2 - h4, 0.0)
    slab_top = min(depth, max(depth - h2, slab_bottom))
    y_positions = {
        "Top web fiber": depth,
        "Bottom web fiber": 0.0,
        "CIP slab top fiber": slab_top,
        "CIP slab bottom fiber": slab_bottom,
    }
    web_fc = _positive_float(settings.get("web_fc_MPa"), 45.0)
    slab_fc = _positive_float(settings.get("slab_fc_MPa"), 35.0)
    top_col = "Final top (MPa)" if "Final top (MPa)" in df.columns else "Top total (MPa)"
    bottom_col = "Final bottom (MPa)" if "Final bottom (MPa)" in df.columns else "Bottom total (MPa)"
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        top = _float_or_default(row.get(top_col), 0.0)
        bottom = _float_or_default(row.get(bottom_col), 0.0)
        for fiber, y in y_positions.items():
            stress = bottom + (top - bottom) * (float(y) / depth)
            component = "Web" if "web" in fiber.casefold() else "CIP slab"
            rows.append(
                {
                    "Load Case": row.get("Load Case", row.get("Stage", "Service")),
                    "Station x (m)": row.get("Station x (m)"),
                    "Fiber": fiber,
                    "Concrete component": component,
                    "f'c basis (MPa)": web_fc if component == "Web" else slab_fc,
                    "Stress (MPa)": stress,
                    "Report basis": "Full gross U-section elastic service preview; linear fiber interpolation for report table",
                }
            )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class RailwayUGirderSLSReportPackage:
    available: bool
    status: str
    warnings: list[str] = field(default_factory=list)
    closeout_status: pd.DataFrame = field(default_factory=pd.DataFrame)
    scope: pd.DataFrame = field(default_factory=pd.DataFrame)
    geometry_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    material_stage_settings: pd.DataFrame = field(default_factory=pd.DataFrame)
    stage_quantities: pd.DataFrame = field(default_factory=pd.DataFrame)
    prestress_debonding_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    stage_governing: pd.DataFrame = field(default_factory=pd.DataFrame)
    limit_governing: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_service_governing: pd.DataFrame = field(default_factory=pd.DataFrame)
    decision_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    service_multifiber_summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "railway_u_girder_closeout_status": self.closeout_status,
            "railway_u_girder_sls_scope": self.scope,
            "railway_u_girder_geometry_summary": self.geometry_summary,
            "railway_u_girder_material_stage_settings": self.material_stage_settings,
            "railway_u_girder_stage_quantities": self.stage_quantities,
            "railway_u_girder_prestress_debonding_summary": self.prestress_debonding_summary,
            "railway_u_girder_sls_stage_governing": self.stage_governing,
            "railway_u_girder_sls_limit_governing": self.limit_governing,
            "railway_u_girder_sls_final_service_governing": self.final_service_governing,
            "railway_u_girder_sls_decision_summary": self.decision_summary,
            "railway_u_girder_service_multifiber_summary": self.service_multifiber_summary,
        }


def build_railway_u_girder_sls_report_package(session_state: Any) -> RailwayUGirderSLSReportPackage:
    """Build report-ready Railway U-Girder SLS tables from current state."""

    if not is_railway_u_girder_report_context(session_state):
        return RailwayUGirderSLSReportPackage(False, "NOT_APPLICABLE")
    geometry = _get(session_state, "section_geometry")
    if geometry is None:
        return RailwayUGirderSLSReportPackage(False, "REVIEW", warnings=["Railway U-Girder report context was detected, but section geometry is missing."])
    settings = _stage_settings_from_session(session_state)
    span = _span_length_from_session(session_state)
    strand_table = _to_dataframe(_get(session_state, "girder_strand_layout_table", None))
    strand_table_arg = None if strand_table.empty else strand_table
    load_cases = _active_sls_load_cases_from_session(session_state)
    warnings: list[str] = []
    try:
        basis_set = railway_u_girder_stage_basis_set(geometry, settings)
        preview = railway_u_girder_staged_stress_preview_dataframe(
            geometry=geometry,
            settings=settings,
            strand_table=strand_table_arg,
            span_length_m=span,
        )
        stage_limit = railway_u_girder_staged_stress_limit_check_dataframe(preview, settings=settings)
        final_service = railway_u_girder_final_service_accumulation_dataframe(
            geometry=geometry,
            settings=settings,
            strand_table=strand_table_arg,
            span_length_m=span,
            load_cases=load_cases,
            station_m=_default_report_station(span),
        )
        final_limits = railway_u_girder_final_service_limit_check_dataframe(final_service, settings=settings)
        decisions = railway_u_girder_sls_decision_summary_dataframe(
            stage_limit_df=stage_limit,
            final_service_limit_df=final_limits,
            active_sls_count=len(load_cases),
        )
        multifiber_source = final_service
        if multifiber_source.empty:
            service_ref = preview[preview["Stage"].astype(str).str.casefold() == "service pe reference"].copy()
            if not service_ref.empty:
                service_ref["Load Case"] = "Service Pe reference"
                multifiber_source = service_ref.rename(columns={"Top total (MPa)": "Final top (MPa)", "Bottom total (MPa)": "Final bottom (MPa)"})
                warnings.append("No active SLS load case was available; service multi-fiber report table uses Pe-only service reference rows.")
    except Exception as exc:
        return RailwayUGirderSLSReportPackage(
            False,
            "REVIEW",
            warnings=[f"Railway U-Girder SLS report package could not be generated: {exc}"],
        )

    if not load_cases:
        warnings.append("No active SLS load case is available; final service remains REVIEW until Loads contains active SLS service actions.")
    return RailwayUGirderSLSReportPackage(
        True,
        RAILWAY_UGIRDER_REPORT_STATUS,
        warnings=warnings,
        closeout_status=railway_u_girder_closeout_status_dataframe(active_sls_count=len(load_cases), warnings=warnings),
        scope=railway_u_girder_scope_dataframe(active_sls_count=len(load_cases)),
        geometry_summary=railway_u_girder_geometry_summary_dataframe(geometry),
        material_stage_settings=railway_u_girder_material_stage_settings_dataframe(settings),
        stage_quantities=railway_u_girder_stage_quantities_dataframe(basis_set, span_length_m=span, settings=settings),
        prestress_debonding_summary=railway_u_girder_prestress_debonding_summary_dataframe(strand_table_arg, span_length_m=span),
        stage_governing=railway_u_girder_stage_governing_rows(preview),
        limit_governing=railway_u_girder_stage_limit_governing_rows(stage_limit),
        final_service_governing=railway_u_girder_final_service_governing_rows(final_service),
        decision_summary=decisions,
        service_multifiber_summary=railway_u_girder_service_multifiber_summary_dataframe(multifiber_source, settings, geometry=geometry),
    )


def railway_u_girder_report_tables_to_dataframe(package: RailwayUGirderSLSReportPackage) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, table in package.tables().items():
        rows.append(
            {
                "Table Key": key,
                "Available": bool(package.available and not table.empty),
                "Row Count": len(table) if isinstance(table, pd.DataFrame) else 0,
                "Report Status": package.status,
            }
        )
    return pd.DataFrame(rows, columns=["Table Key", "Available", "Row Count", "Report Status"])

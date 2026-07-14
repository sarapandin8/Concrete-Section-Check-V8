"""Project JSON serialization helpers."""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from dataclasses import asdict
from typing import Any

import pandas as pd
from pydantic import ValidationError

from concrete_pmm_pro.analysis.capacity_check import DemandCapacityResult, DemandCapacitySummary
from concrete_pmm_pro.analysis.preflight import build_analysis_input_from_session_state
from concrete_pmm_pro.analysis.result_models import PMMSolverResult
from concrete_pmm_pro.analysis.runtime import analysis_input_hash
from concrete_pmm_pro.core.analysis import AnalysisModeSettings, AnalysisSettings
from concrete_pmm_pro.core.concrete_materials import c45_precast_material, ensure_concrete_material_library
from concrete_pmm_pro.core.design_code import (
    PROJECT_CODE_EDITION_STATE_KEY,
    PROJECT_DESIGN_CODE_STATE_KEY,
    normalize_project_code_edition,
    normalize_project_design_code,
    project_code_edition_from_session,
    project_design_code_from_session,
)
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
    REINFORCEMENT_FLAGS_PRESET_KEY,
)
from concrete_pmm_pro.core.models import LoadCase, PrestressElement, Rebar
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.core.units import N_to_kN, Nmm_to_kNm
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    CB_SECLIB_LOADED_ID_KEY,
    CB_SECLIB_MIGRATION_KEY,
    SECLIB_METADATA_KEY,
    SECLIB_SCHEMA_VERSION,
    canonical_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.data.prestress_tendon_products import (
    DEFAULT_STRAND_DIAMETER_MM,
    DEFAULT_STRAND_EP_MPA,
    DEFAULT_STRAND_FPU_MPA,
    DEFAULT_STRAND_FPY_MPA,
    equivalent_steel_diameter_mm,
    get_tendon_product,
    is_tendon_6n_label,
    tendon_product_display_label,
)
from concrete_pmm_pro.serviceability.models import ServiceabilitySettings, ServiceabilitySummary
from concrete_pmm_pro.serviceability.points import stress_check_points_to_dataframe
from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BEAM_GIRDER_SYSTEM_SETTINGS_KEY,
    BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY,
    BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY,
    auto_load_settings_from_mapping,
    building_service_load_settings_from_mapping,
    system_settings_from_mapping,
)
from concrete_pmm_pro.state.dirty_state import (
    ANALYSIS_STATUS_KEY,
    CHANGED_GROUPS_KEY,
    CURRENT_INPUT_HASH_KEY,
    LAST_ANALYSIS_HASH_KEY,
    LAST_REFRESHED_WORKSPACE_KEY,
    PREVIOUS_INPUT_HASH_KEY,
    REPORT_STATUS_KEY,
    project_input_hash,
)


class ProjectIOError(ValueError):
    """Raised when project JSON cannot be parsed or validated."""


def _get_session_value(session_state: Any, key: str, default: Any = None) -> Any:
    if hasattr(session_state, "get"):
        return session_state.get(key, default)
    return getattr(session_state, key, default)


def _session_has_key(session_state: Any, key: str) -> bool:
    if hasattr(session_state, "__contains__"):
        try:
            return key in session_state
        except Exception:
            pass
    return hasattr(session_state, key)


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _clean_table_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, dict):
        return {str(key): _clean_table_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_table_value(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


SHEAR_REINFORCEMENT_TABLE_KEY = "beam_girder_shear_reinforcement_table"
RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY = "railway_u_girder_stage_settings"
LONGITUDINAL_REBAR_TABLE_METADATA_KEY = "longitudinal_rebar_table"
PRESTRESS_TABLE_METADATA_KEY = "prestress_table_metadata"
REBAR_TABLE_COLUMNS = [
    "Active",
    "Label",
    "x_mm",
    "y_mm",
    "Bar Size",
    "Diameter_mm",
    "Material",
    "Count",
    "Note",
]
PRESTRESS_TABLE_METADATA_COLUMNS = [
    "Active",
    "Label",
    "Steel Type",
    "Product",
    "x_mm",
    "y_mm",
    "Area_mm2",
    "Diameter_mm",
    "Eq Steel Dia_mm",
    "fpy_MPa",
    "fpu_MPa",
    "Ep_MPa",
    "Input Mode",
    "Pe_eff_kN",
    "fpe_MPa",
    "fpj_ratio",
    "loss_percent",
    "Bonded",
    "Count",
    "Strand Count",
    "Strand Diameter_mm",
    "Strand Area_mm2",
    "Breaking Load_kN",
    "Duct Type",
    "Duct ID_mm",
    "Tendon Description",
    "Typical Use",
    "Note",
]

ANALYSIS_RESULTS_METADATA_KEY = "analysis_results"
ANALYSIS_RESULTS_SCHEMA_VERSION = 1

WORKFLOW_LOAD_TABLE_METADATA_KEYS = (
    "column_uls_loads_table",
    "column_sls_loads_table",
    "beam_uls_loads_table",
    "beam_sls_loads_table",
)

CROSSBEAM_LENGTH_STATE_KEY = "crossbeam_ui1_length_m"
CROSSBEAM_SEGMENT_ROWS_STATE_KEY = "crossbeam_ui1_segment_layout_rows"
CROSSBEAM_SEGMENT_REVISION_STATE_KEY = "crossbeam_ui1_segment_editor_revision"


def _crossbeam_input_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize workflow-scoped Crossbeam geometry inputs only."""

    definitions = canonical_section_definitions(_get_session_value(session_state, CB_SECLIB_DEFINITIONS_KEY, []))
    segment_rows = _clean_table_value(_get_session_value(session_state, CROSSBEAM_SEGMENT_ROWS_STATE_KEY, []))
    if not definitions and not segment_rows:
        return {}
    migrated_segments = migrate_segment_rows_to_library(segment_rows or [], definitions) if definitions else list(segment_rows or [])
    return {
        "schema_version": SECLIB_SCHEMA_VERSION,
        "section_definitions": _clean_table_value(definitions),
        "active_section_id": _get_session_value(session_state, CB_SECLIB_ACTIVE_ID_KEY, None),
        "length_m": _clean_table_value(_get_session_value(session_state, CROSSBEAM_LENGTH_STATE_KEY, None)),
        "segment_rows": _clean_table_value(migrated_segments),
    }


def _workflow_load_table_metadata_from_session(session_state: Any) -> dict[str, list[dict[str, Any]]]:
    """Serialize workflow-specific load tables without changing the solver LoadCase schema."""

    tables: dict[str, list[dict[str, Any]]] = {}
    for key in WORKFLOW_LOAD_TABLE_METADATA_KEYS:
        table = _get_session_value(session_state, key, None)
        if table is None:
            continue
        df = pd.DataFrame(table)
        tables[key] = df.to_dict(orient="records")
    return tables


def _demand_capacity_summary_to_metadata(summary: DemandCapacitySummary) -> dict[str, Any]:
    """Serialize a stored PMM demand/capacity summary as plain project JSON."""

    return asdict(summary)


def _demand_capacity_summary_from_metadata(value: Any) -> DemandCapacitySummary | None:
    """Restore a stored PMM demand/capacity summary from project metadata."""

    if not isinstance(value, dict):
        return None
    try:
        result_rows = [DemandCapacityResult(**item) for item in value.get("results", []) if isinstance(item, dict)]
        return DemandCapacitySummary(
            results=result_rows,
            governing_combo=value.get("governing_combo"),
            max_dcr=value.get("max_dcr"),
            overall_status=str(value.get("overall_status") or "NOT_CHECKED"),
            warnings=list(value.get("warnings") or []),
            info=list(value.get("info") or []),
        )
    except Exception:
        return None



def _dataframe_to_analysis_metadata(value: Any) -> dict[str, Any] | None:
    """Serialize a cached analysis dataframe as plain JSON metadata."""

    if not isinstance(value, pd.DataFrame):
        return None
    return {
        "__kind__": "dataframe",
        "columns": [str(column) for column in value.columns],
        "records": value.to_dict(orient="records"),
    }


def _dataframe_from_analysis_metadata(value: Any) -> pd.DataFrame | None:
    """Restore a cached analysis dataframe from project metadata."""

    if not isinstance(value, dict) or value.get("__kind__") != "dataframe":
        return None
    records = value.get("records")
    columns = value.get("columns")
    if not isinstance(records, list):
        return None
    try:
        df = pd.DataFrame(records)
        if isinstance(columns, list):
            for column in columns:
                if column not in df.columns:
                    df[column] = None
            df = df[[column for column in columns if column in df.columns]]
        return df
    except Exception:
        return None


def _analysis_cache_entry_to_metadata(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    serialized: dict[str, Any] = {}
    for key, value in entry.items():
        df_meta = _dataframe_to_analysis_metadata(value)
        if df_meta is not None:
            serialized[str(key)] = df_meta
        else:
            serialized[str(key)] = _clean_table_value(value)
    return serialized


def _analysis_cache_entry_from_metadata(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    restored: dict[str, Any] = {}
    for key, value in entry.items():
        df = _dataframe_from_analysis_metadata(value)
        restored[str(key)] = df if df is not None else value
    return restored


def _beam_uls_cache_metadata_from_session(session_state: Any) -> dict[str, Any]:
    cache = _get_session_value(session_state, "_beam_girder_uls_manual_calculation_cache", None)
    if not isinstance(cache, dict):
        return {}
    result: dict[str, Any] = {}
    for check_name, entry in cache.items():
        serialized = _analysis_cache_entry_to_metadata(entry)
        if serialized:
            result[str(check_name)] = serialized
    return result


def _beam_uls_cache_from_metadata(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    cache: dict[str, dict[str, Any]] = {}
    for check_name, entry in value.items():
        restored = _analysis_cache_entry_from_metadata(entry)
        if restored is not None:
            cache[str(check_name)] = restored
    return cache


def _analysis_results_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize restorable analysis outputs without rerunning solver logic.

    Stored results are cache artifacts, not engineering inputs.  Result caches
    are restored only when the loaded project input hash still matches the
    saved inputs.
    """

    metadata: dict[str, Any] = {
        "schema_version": ANALYSIS_RESULTS_SCHEMA_VERSION,
        "project_input_hash": project_input_hash(session_state),
        "analysis_accuracy_preset": _get_session_value(session_state, "analysis_accuracy_preset", None),
        "analysis_runtime_last_status": _get_session_value(session_state, "analysis_runtime_last_status", None),
        "analysis_runtime_last_time_seconds": _get_session_value(session_state, "analysis_runtime_last_time_seconds", None),
        "analysis_runtime_last_run_at": _get_session_value(session_state, "analysis_runtime_last_run_at", None),
        "analysis_runtime_last_preset": _get_session_value(session_state, "analysis_runtime_last_preset", None),
        "analysis_runtime_timings": _get_session_value(session_state, "analysis_runtime_timings", None),
    }

    result = _get_session_value(session_state, "rc_pmm_result", None)
    result_hash = (
        _get_session_value(session_state, "rc_pmm_result_input_hash", None)
        or _get_session_value(session_state, "pmm_last_analysis_hash", None)
    )
    if isinstance(result, PMMSolverResult) and result_hash:
        metadata.update(
            {
                "rc_pmm_result": result.model_dump(mode="json"),
                "pmm_result_input_hash": result_hash,
                "pmm_last_analysis_hash": _get_session_value(session_state, "pmm_last_analysis_hash", result_hash),
            }
        )

    rc_only_result = _get_session_value(session_state, "rc_only_comparison_result", None)
    if isinstance(rc_only_result, PMMSolverResult):
        metadata["rc_only_comparison_result"] = rc_only_result.model_dump(mode="json")
    comparison = _get_session_value(session_state, "prestress_comparison_summary", None)
    if isinstance(comparison, dict):
        metadata["prestress_comparison_summary"] = dict(comparison)

    dc_summary = _get_session_value(session_state, "rc_demand_capacity_result", None)
    if isinstance(dc_summary, DemandCapacitySummary):
        metadata["rc_demand_capacity_result"] = _demand_capacity_summary_to_metadata(dc_summary)
        metadata["rc_demand_capacity_result_hash"] = _get_session_value(session_state, "rc_demand_capacity_result_hash", None)
        metadata["rc_demand_capacity_input_hash"] = _get_session_value(session_state, "rc_demand_capacity_input_hash", None)
        metadata["rc_demand_capacity_pmm_result_hash"] = _get_session_value(session_state, "rc_demand_capacity_pmm_result_hash", None)

    beam_uls_cache = _beam_uls_cache_metadata_from_session(session_state)
    if beam_uls_cache:
        metadata["beam_girder_uls_manual_calculation_cache"] = beam_uls_cache

    serviceability = _get_session_value(session_state, "serviceability_summary", None)
    if isinstance(serviceability, ServiceabilitySummary):
        metadata["serviceability_summary"] = serviceability.model_dump(mode="json")
        metadata["serviceability_summary_hash"] = _get_session_value(session_state, "serviceability_summary_hash", None)
        metadata["serviceability_runtime_cache_status"] = _get_session_value(session_state, "serviceability_runtime_cache_status", None)

    # If there are no actual result caches, do not write a placeholder metadata block.
    cache_payload_keys = {
        "rc_pmm_result",
        "rc_demand_capacity_result",
        "beam_girder_uls_manual_calculation_cache",
        "serviceability_summary",
    }
    if not any(key in metadata for key in cache_payload_keys):
        return {}

    return {key: _clean_table_value(value) for key, value in metadata.items() if value is not None}


def _restore_pmm_analysis_results_metadata(metadata: dict[str, Any], session_state: MutableMapping[str, Any]) -> bool:
    """Restore PMM/cache outputs from metadata when their analysis hash matches."""

    stored_hash = str(metadata.get("pmm_result_input_hash") or metadata.get("pmm_last_analysis_hash") or "").strip()
    if not stored_hash or metadata.get("rc_pmm_result") is None:
        return False

    analysis_input = build_analysis_input_from_session_state(session_state)
    if analysis_input is not None:
        current_hash = analysis_input_hash(analysis_input, str(session_state.get("analysis_accuracy_preset") or "Standard"))
        if current_hash != stored_hash:
            session_state["analysis_runtime_cache_status"] = "Saved PMM result is stale for loaded inputs"
            session_state["analysis_runtime_last_status"] = "Saved result stale"
            return False

    try:
        result = PMMSolverResult.model_validate(metadata.get("rc_pmm_result"))
    except Exception:
        return False

    session_state["rc_pmm_result"] = result
    session_state["rc_pmm_result_input_hash"] = stored_hash
    session_state["pmm_last_analysis_hash"] = stored_hash
    session_state["analysis_force_recalculate"] = False
    session_state["analysis_runtime_cache_status"] = "Loaded cached result"
    session_state["analysis_runtime_last_status"] = "Loaded cached result"

    rc_only_data = metadata.get("rc_only_comparison_result")
    if rc_only_data is not None:
        try:
            session_state["rc_only_comparison_result"] = PMMSolverResult.model_validate(rc_only_data)
        except Exception:
            session_state.pop("rc_only_comparison_result", None)
    if isinstance(metadata.get("prestress_comparison_summary"), dict):
        session_state["prestress_comparison_summary"] = dict(metadata.get("prestress_comparison_summary") or {})

    dc_summary = _demand_capacity_summary_from_metadata(metadata.get("rc_demand_capacity_result"))
    if dc_summary is not None:
        session_state["rc_demand_capacity_result"] = dc_summary
        session_state["demand_capacity_summary"] = dc_summary
        for key in (
            "rc_demand_capacity_result_hash",
            "rc_demand_capacity_input_hash",
            "rc_demand_capacity_pmm_result_hash",
        ):
            if metadata.get(key) is not None:
                session_state[key] = metadata.get(key)
        session_state["analysis_runtime_dc_cache_status"] = "Loaded cached D/C result"

    return True


def _restore_analysis_results_metadata(project: ProjectModel, session_state: MutableMapping[str, Any]) -> bool:
    """Restore saved analysis caches only when they match the loaded inputs."""

    metadata = project.metadata.get(ANALYSIS_RESULTS_METADATA_KEY)
    if not isinstance(metadata, dict):
        return False
    if metadata.get("schema_version") not in {ANALYSIS_RESULTS_SCHEMA_VERSION, None}:
        return False

    preset = metadata.get("analysis_accuracy_preset") or metadata.get("analysis_runtime_last_preset")
    if isinstance(preset, str) and preset:
        session_state["analysis_accuracy_preset"] = preset

    restored_any = _restore_pmm_analysis_results_metadata(metadata, session_state)

    # Beam/Girder ULS and SLS summaries are project-file cache artifacts.
    # They are restored with the saved project inputs so users can reopen a
    # completed design review without rerunning every Analysis subcheck.  ULS
    # cache entries still carry their own per-check input hashes for Analysis
    # pages to validate before reuse.
    beam_cache = _beam_uls_cache_from_metadata(metadata.get("beam_girder_uls_manual_calculation_cache"))
    if beam_cache:
        session_state["_beam_girder_uls_manual_calculation_cache"] = beam_cache
        session_state["beam_girder_uls_runtime_cache_status"] = "Loaded cached Beam/Girder ULS results"
        restored_any = True

    sls_data = metadata.get("serviceability_summary")
    if sls_data is not None:
        try:
            serviceability_summary = ServiceabilitySummary.model_validate(sls_data)
        except Exception:
            serviceability_summary = None
        if serviceability_summary is not None:
            session_state["serviceability_summary"] = serviceability_summary
            if metadata.get("serviceability_summary_hash") is not None:
                session_state["serviceability_summary_hash"] = metadata.get("serviceability_summary_hash")
            session_state["serviceability_runtime_cache_status"] = (
                metadata.get("serviceability_runtime_cache_status") or "Loaded cached SLS result"
            )
            restored_any = True

    for key in (
        "analysis_runtime_last_time_seconds",
        "analysis_runtime_last_run_at",
        "analysis_runtime_last_preset",
    ):
        if metadata.get(key) is not None:
            session_state[key] = metadata.get(key)
    if isinstance(metadata.get("analysis_runtime_timings"), dict):
        session_state["analysis_runtime_timings"] = dict(metadata.get("analysis_runtime_timings") or {})

    return restored_any


def _beam_girder_shear_reinforcement_metadata_from_session(session_state: Any) -> list[dict[str, Any]]:
    value = _get_session_value(session_state, SHEAR_REINFORCEMENT_TABLE_KEY, None)
    if value is None:
        return []
    try:
        return pd.DataFrame(value).to_dict(orient="records")
    except Exception:
        return []


def _ensure_rebar_table_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a rebar input table with the project-save column contract.

    This duplicates the visible Rebar editor contract intentionally so project
    save/load can preserve the engineer's raw input table without importing UI
    code from the IO layer.
    """

    table = df.copy()
    for column in REBAR_TABLE_COLUMNS:
        if column not in table.columns:
            table[column] = None
    return table[REBAR_TABLE_COLUMNS]


def _longitudinal_rebar_table_metadata_from_session(session_state: Any) -> list[dict[str, Any]]:
    """Serialize the raw Longitudinal Rebar editor table.

    ``ProjectModel.rebars`` stores parsed individual bar objects, which is good
    for analysis but loses editor-level information such as Bar Size dropdown,
    Count, inactive rows, and notes.  The raw editor table is therefore stored
    as metadata and restored preferentially on project load.
    """

    value = _get_session_value(session_state, "rebar_table", None)
    if value is None:
        return []
    try:
        df = _ensure_rebar_table_columns(pd.DataFrame(value))
    except Exception:
        return []
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        entry = {column: _clean_table_value(row.get(column)) for column in REBAR_TABLE_COLUMNS}
        if any(not _is_blank(value) for value in entry.values()):
            rows.append(entry)
    return rows


def _girder_prestress_force_states_metadata_from_session(session_state: Any) -> list[dict[str, Any]]:
    """Serialize GIRDER.PS2A stage prestress force states as project metadata."""

    table = _get_session_value(session_state, "girder_prestress_force_states_table", None)
    if table is None:
        return []
    df = pd.DataFrame(table)
    if df.empty:
        return []
    columns = ["Check Stage", "Prestress State", "Pe_kN", "yps_mm_from_bottom", "Note"]
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        entry = {column: _clean_table_value(row.get(column)) for column in columns if column in df.columns}
        if any(not _is_blank(value) for value in entry.values()):
            rows.append(entry)
    return rows




def _girder_strand_layout_metadata_from_session(session_state: Any) -> list[dict[str, Any]]:
    """Serialize GIRDER.PS3A strand layout/debonding metadata."""

    table = _get_session_value(session_state, "girder_strand_layout_table", None)
    if table is None:
        return []
    df = pd.DataFrame(table)
    if df.empty:
        return []
    columns = [
        "Active",
        "Group ID",
        "Layer",
        "Strand Size",
        "No. Strands",
        "Area/Strand_mm2",
        "Total Aps_mm2",
        "x_mm",
        "Row center x_mm",
        "Strand x positions mm",
        "y_mm_from_bottom",
        "Edge CL_mm",
        "Min spacing_mm",
        "Computed spacing_mm",
        "Pe_transfer/strand_kN",
        "Pe_construction/strand_kN",
        "Pe_eff_final/strand_kN",
        "Left debond m",
        "Right debond m",
        "Debonded strand nos",
        "Debond pattern mm",
        "Note",
    ]
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        entry = {column: _clean_table_value(row.get(column)) for column in columns if column in df.columns}
        if any(not _is_blank(value) for value in entry.values()):
            rows.append(entry)
    return rows


def _girder_prestress_system_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize simple-supported girder prestress/debonding system settings."""

    settings = _get_session_value(session_state, "girder_prestress_system_settings", None)
    if not isinstance(settings, dict):
        return {}
    allowed = {"girder_system", "prestress_type", "span_length_m", "station_convention", "debond_model"}
    return {key: _clean_table_value(value) for key, value in settings.items() if key in allowed and not _is_blank(value)}


def _railway_u_girder_stage_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize STAGE.RAIL.UGIRDER1 staged-construction settings."""

    settings = _get_session_value(session_state, RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY, None)
    if not isinstance(settings, dict):
        return {}
    allowed = {
        "web_fc_MPa",
        "web_fci_MPa",
        "slab_fc_MPa",
        "concrete_unit_weight_kN_m3",
        "support_condition",
        "construction_method",
        "wet_slab_distribution_each_web",
        "formwork_construction_load_kN_m2",
        "lifting_point_ratio",
        "lifting_impact_factor",
    }
    return {key: _clean_table_value(value) for key, value in settings.items() if key in allowed and not _is_blank(value)}



def _girder_prestress_code_loss_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize selected prestress-loss settings such as local code basis."""

    settings = _get_session_value(session_state, "girder_prestress_code_loss_settings", None)
    if not isinstance(settings, dict):
        return {}
    allowed = {
        "method",
        "loss_code_basis",
        "fci_MPa",
        "fpj_ratio",
        "humidity_percent",
        "relaxation_class",
        "refined_coefficient_source",
        "refined_coefficient_preset",
    }
    return {key: _clean_table_value(value) for key, value in settings.items() if key in allowed and not _is_blank(value)}




def _beam_girder_system_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize single-source Beam/Girder system settings."""

    settings = _get_session_value(session_state, BEAM_GIRDER_SYSTEM_SETTINGS_KEY, None)
    if not isinstance(settings, dict):
        return {}
    return {key: _clean_table_value(value) for key, value in system_settings_from_mapping(settings).as_metadata().items() if not _is_blank(value)}


def _beam_girder_sls_auto_load_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize Beam/Girder SLS auto-load component settings."""

    settings = _get_session_value(session_state, BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY, None)
    if not isinstance(settings, dict):
        return {}
    return {key: _clean_table_value(value) for key, value in auto_load_settings_from_mapping(settings).as_metadata().items() if not _is_blank(value)}


def _building_beam_girder_service_load_settings_metadata_from_session(session_state: Any) -> dict[str, Any]:
    """Serialize Building Beam/Girder service SDL/LL settings."""

    settings = _get_session_value(session_state, BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY, None)
    if not isinstance(settings, dict):
        return {}
    return {
        key: _clean_table_value(value)
        for key, value in building_service_load_settings_from_mapping(settings).as_metadata().items()
        if not _is_blank(value)
    }


def _prestress_table_metadata_from_session(session_state: Any) -> list[dict[str, Any]]:
    table = _get_session_value(session_state, "prestress_table", None)
    if table is None:
        return []
    df = pd.DataFrame(table)
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        entry = {column: _clean_table_value(row.get(column)) for column in PRESTRESS_TABLE_METADATA_COLUMNS if column in df.columns}
        if "Product" in entry and not _is_blank(entry.get("Product")):
            entry["Product"] = tendon_product_display_label(entry.get("Product"))
        if any(not _is_blank(value) for value in entry.values()):
            rows.append(entry)
    return rows


def project_from_session_state(session_state: Any) -> ProjectModel:
    metadata = dict(_get_session_value(session_state, "project_metadata", {}) or {})
    for flag_name in (
        "rebars_valid_for_analysis",
        "prestress_valid_for_analysis",
        ORDINARY_REBAR_FLAG_KEY,
        PRESTRESSING_STEEL_FLAG_KEY,
        REINFORCEMENT_FLAGS_PRESET_KEY,
        "section_builder_steel_systems_user_overridden",
    ):
        flag_value = _get_session_value(session_state, flag_name, None)
        if flag_value is not None:
            metadata[flag_name] = flag_value
    prestress_table_metadata = _prestress_table_metadata_from_session(session_state)
    if prestress_table_metadata:
        metadata[PRESTRESS_TABLE_METADATA_KEY] = prestress_table_metadata
    workflow_load_tables = _workflow_load_table_metadata_from_session(session_state)
    if workflow_load_tables:
        metadata["workflow_load_tables"] = workflow_load_tables
    if _session_has_key(session_state, "rebar_table"):
        metadata[LONGITUDINAL_REBAR_TABLE_METADATA_KEY] = _longitudinal_rebar_table_metadata_from_session(session_state)
    if _session_has_key(session_state, SHEAR_REINFORCEMENT_TABLE_KEY):
        metadata[SHEAR_REINFORCEMENT_TABLE_KEY] = _beam_girder_shear_reinforcement_metadata_from_session(session_state)
    girder_prestress_force_states = _girder_prestress_force_states_metadata_from_session(session_state)
    if girder_prestress_force_states:
        metadata["girder_prestress_force_states_table"] = girder_prestress_force_states
    girder_strand_layout = _girder_strand_layout_metadata_from_session(session_state)
    if girder_strand_layout:
        metadata["girder_strand_layout_table"] = girder_strand_layout
    girder_prestress_system_settings = _girder_prestress_system_settings_metadata_from_session(session_state)
    if girder_prestress_system_settings:
        metadata["girder_prestress_system_settings"] = girder_prestress_system_settings
    railway_u_girder_stage_settings = _railway_u_girder_stage_settings_metadata_from_session(session_state)
    if railway_u_girder_stage_settings:
        metadata[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = railway_u_girder_stage_settings
    girder_prestress_code_loss_settings = _girder_prestress_code_loss_settings_metadata_from_session(session_state)
    if girder_prestress_code_loss_settings:
        metadata["girder_prestress_code_loss_settings"] = girder_prestress_code_loss_settings
    beam_girder_system_settings = _beam_girder_system_settings_metadata_from_session(session_state)
    if beam_girder_system_settings:
        metadata[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = beam_girder_system_settings
    beam_girder_sls_auto_load_settings = _beam_girder_sls_auto_load_settings_metadata_from_session(session_state)
    if beam_girder_sls_auto_load_settings:
        metadata[BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY] = beam_girder_sls_auto_load_settings
    building_service_load_settings = _building_beam_girder_service_load_settings_metadata_from_session(session_state)
    if building_service_load_settings:
        metadata[BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY] = building_service_load_settings
    crossbeam_input_metadata = _crossbeam_input_metadata_from_session(session_state)
    if crossbeam_input_metadata:
        metadata[SECLIB_METADATA_KEY] = crossbeam_input_metadata
    else:
        metadata.pop(SECLIB_METADATA_KEY, None)
    analysis_results_metadata = _analysis_results_metadata_from_session(session_state)
    if analysis_results_metadata:
        metadata[ANALYSIS_RESULTS_METADATA_KEY] = analysis_results_metadata
    else:
        metadata.pop(ANALYSIS_RESULTS_METADATA_KEY, None)

    concrete_materials_value = _coerce_list(_get_session_value(session_state, "concrete_materials", []))
    preserve_existing_primary = not bool(concrete_materials_value)
    concrete_library = ensure_concrete_material_library(
        concrete_material=_get_session_value(session_state, "concrete_material", c45_precast_material()),
        concrete_materials=concrete_materials_value,
        active_concrete_material_name=_get_session_value(session_state, "active_concrete_material_name", None),
        deck_topping_material_name=_get_session_value(session_state, "deck_topping_material_name", None),
        preserve_existing_primary=preserve_existing_primary,
    )

    return ProjectModel(
        project_name=_get_session_value(session_state, "project_name", "Untitled Project") or "Untitled Project",
        designer=_get_session_value(session_state, "designer", None),
        description=_get_session_value(session_state, "description", None),
        code=project_design_code_from_session(session_state),
        code_edition=project_code_edition_from_session(session_state),
        section_preset_key=_get_session_value(session_state, "section_preset_key", None),
        section_preset_name=_get_session_value(session_state, "section_preset_name", None),
        section_parameters=dict(_get_session_value(session_state, "section_parameters", {}) or {}),
        section_geometry=_get_session_value(session_state, "section_geometry", None),
        concrete_material=concrete_library.active_material,
        concrete_materials=concrete_library.materials,
        active_concrete_material_name=concrete_library.active_concrete_material_name,
        deck_topping_material_name=concrete_library.deck_topping_material_name,
        rebar_materials=_coerce_list(_get_session_value(session_state, "rebar_materials", [])),
        prestress_materials=_coerce_list(_get_session_value(session_state, "prestress_materials", [])),
        active_rebar_material_name=_get_session_value(session_state, "active_rebar_material_name", None),
        active_prestress_material_name=_get_session_value(session_state, "active_prestress_material_name", None),
        loads=_coerce_list(_get_session_value(session_state, "load_cases", [])),
        rebars=_coerce_list(_get_session_value(session_state, "rebars", [])),
        prestress_elements=_coerce_list(_get_session_value(session_state, "prestress_elements", [])),
        analysis_mode_settings=_get_session_value(session_state, "analysis_mode_settings", AnalysisModeSettings()),
        analysis_settings=_get_session_value(session_state, "analysis_settings", AnalysisSettings()),
        serviceability_settings=_get_session_value(session_state, "serviceability_settings", ServiceabilitySettings()),
        custom_stress_check_points=_coerce_list(_get_session_value(session_state, "custom_stress_check_points", [])),
        include_default_stress_check_points=bool(
            _get_session_value(session_state, "include_default_stress_check_points", True)
        ),
        metadata=metadata,
    )


def project_to_json(project: ProjectModel) -> str:
    return project.model_dump_json(indent=2)


def _migrate_legacy_data(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    legacy_project_fields = {
        "load_cases": "loads",
        "prestress": "prestress_elements",
        "tendons": "prestress_elements",
        "geometry": "section_geometry",
        "preset_key": "section_preset_key",
        "preset_name": "section_preset_name",
        "parameters": "section_parameters",
        "design_code": "code",
        "design_code_edition": "code_edition",
    }
    for old_name, new_name in legacy_project_fields.items():
        if old_name in migrated and new_name not in migrated:
            migrated[new_name] = migrated.pop(old_name)

    prestress_items = migrated.get("prestress_elements")
    if isinstance(prestress_items, list):
        for item in prestress_items:
            if not isinstance(item, dict):
                continue
            if "Pe_eff_N" in item and "pe_eff_n" not in item:
                item["pe_eff_n"] = item.pop("Pe_eff_N")
            if "Ep_MPa" in item and "ep_mpa" not in item:
                item["ep_mpa"] = item.pop("Ep_MPa")
            if "fpy_MPa" in item and "fpy_mpa" not in item:
                item["fpy_mpa"] = item.pop("fpy_MPa")
            if "fpu_MPa" in item and "fpu_mpa" not in item:
                item["fpu_mpa"] = item.pop("fpu_MPa")

    return migrated


def project_from_json(json_text: str) -> ProjectModel:
    try:
        raw_data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ProjectIOError(f"Invalid project JSON: {exc.msg}") from exc

    if not isinstance(raw_data, dict):
        raise ProjectIOError("Invalid project JSON: root value must be an object.")

    try:
        return ProjectModel.model_validate(_migrate_legacy_data(raw_data))
    except ValidationError as exc:
        first_error = exc.errors()[0]
        location = ".".join(str(part) for part in first_error.get("loc", ())) or "project"
        raise ProjectIOError(f"Invalid project data at {location}: {first_error.get('msg', 'validation failed')}") from exc


def _loads_to_table(loads: list[LoadCase]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": load_case.active,
                "Combo Name": load_case.name,
                "Pu": N_to_kN(load_case.Pu_N),
                "Mux": Nmm_to_kNm(load_case.Mux_Nmm),
                "Muy": Nmm_to_kNm(load_case.Muy_Nmm),
                "Load Type": load_case.load_type,
                "Note": load_case.note or "",
            }
            for load_case in loads
        ]
    )


def _rebars_to_table(rebars: list[Rebar]) -> pd.DataFrame:
    return _ensure_rebar_table_columns(
        pd.DataFrame(
            [
                {
                    "Active": True,
                    "Label": rebar.label or f"B{index}",
                    "x_mm": rebar.x_mm,
                    "y_mm": rebar.y_mm,
                    "Bar Size": "Custom",
                    "Diameter_mm": rebar.diameter_mm,
                    "Material": rebar.material_name,
                    "Count": 1,
                    "Note": "",
                }
                for index, rebar in enumerate(rebars, start=1)
            ]
        )
    )


def _prestress_metadata_for_row(
    table_metadata: list[dict[str, Any]],
    index: int,
    label: str,
) -> dict[str, Any]:
    for row in table_metadata:
        if str(row.get("Label") or "").strip() == label:
            return row
    if index - 1 < len(table_metadata):
        return table_metadata[index - 1]
    return {}


def _prestress_metadata_row_key(row: dict[str, Any], index: int) -> str:
    label = str(row.get("Label") or "").strip()
    return f"label:{label}" if label else f"index:{index}"


def _restore_tendon_product_metadata(row: dict[str, Any]) -> dict[str, Any]:
    product = str(row.get("Product") or "").strip()
    tendon_product = get_tendon_product(product)
    if tendon_product is None:
        return row
    restored = dict(row)
    restored["Product"] = tendon_product.label
    restored["Steel Type"] = "tendon_group"
    restored["Area_mm2"] = tendon_product.tendon_area_mm2
    restored["Diameter_mm"] = None
    restored["Eq Steel Dia_mm"] = equivalent_steel_diameter_mm(tendon_product.tendon_area_mm2)
    restored["fpy_MPa"] = tendon_product.fpy_MPa
    restored["fpu_MPa"] = tendon_product.fpu_MPa
    restored["Ep_MPa"] = tendon_product.Ep_MPa
    restored["Strand Count"] = tendon_product.strand_count
    restored["Strand Diameter_mm"] = tendon_product.strand_diameter_mm
    restored["Strand Area_mm2"] = tendon_product.strand_area_mm2
    restored["Breaking Load_kN"] = tendon_product.breaking_load_kN
    restored["Duct Type"] = tendon_product.duct_type or ""
    restored["Duct ID_mm"] = tendon_product.duct_id_mm
    restored["Tendon Description"] = tendon_product.description
    restored["Typical Use"] = tendon_product.typical_use or ""
    return restored


def _looks_like_15_2mm_tendon_group(row: dict[str, Any]) -> bool:
    if str(row.get("Steel Type") or "").strip() != "tendon_group":
        return False
    product = str(row.get("Product") or "").strip()
    if get_tendon_product(product) is not None or is_tendon_6n_label(product):
        return True
    strand_count = row.get("Strand Count")
    if _is_blank(strand_count):
        return False
    strand_diameter = row.get("Strand Diameter_mm")
    if _is_blank(strand_diameter):
        return True
    try:
        return abs(float(strand_diameter) - DEFAULT_STRAND_DIAMETER_MM) < 1e-6
    except (TypeError, ValueError):
        return False


def _normalize_tendon_group_table_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if str(normalized.get("Steel Type") or "").strip() != "tendon_group":
        return normalized
    normalized["Diameter_mm"] = None
    area = normalized.get("Area_mm2")
    try:
        normalized["Eq Steel Dia_mm"] = equivalent_steel_diameter_mm(float(area)) if not _is_blank(area) else None
    except (TypeError, ValueError):
        normalized["Eq Steel Dia_mm"] = None
    if _looks_like_15_2mm_tendon_group(normalized):
        if _is_blank(normalized.get("fpy_MPa")):
            normalized["fpy_MPa"] = DEFAULT_STRAND_FPY_MPA
        if _is_blank(normalized.get("fpu_MPa")):
            normalized["fpu_MPa"] = DEFAULT_STRAND_FPU_MPA
        if _is_blank(normalized.get("Ep_MPa")):
            normalized["Ep_MPa"] = DEFAULT_STRAND_EP_MPA
    return normalized


def _prestress_to_table(elements: list[PrestressElement], table_metadata: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    metadata_rows = table_metadata or []
    rows: list[dict[str, Any]] = []
    consumed_metadata_keys: set[str] = set()
    for index, element in enumerate(elements, start=1):
        label = element.label or f"PS{index}"
        row = {
            "Active": True,
            "Label": label,
            "Steel Type": element.steel_type,
            "Product": element.material_name or "Custom",
            "x_mm": element.x_mm,
            "y_mm": element.y_mm,
            "Area_mm2": element.area_mm2,
            "Diameter_mm": element.diameter_mm,
            "Eq Steel Dia_mm": None,
            "fpy_MPa": element.fpy_mpa,
            "fpu_MPa": element.fpu_mpa,
            "Ep_MPa": element.ep_mpa,
            "Input Mode": "Effective Force Pe" if element.pe_eff_n > 0 else "Passive",
            "Pe_eff_kN": N_to_kN(element.pe_eff_n),
            "fpe_MPa": element.initial_stress_mpa or 0.0,
            "fpj_ratio": 0.75,
            "loss_percent": 15.0,
            "Bonded": element.bonded,
            "Count": element.count,
            "Strand Count": None,
            "Strand Diameter_mm": None,
            "Strand Area_mm2": None,
            "Breaking Load_kN": None,
            "Duct Type": "",
            "Duct ID_mm": None,
            "Tendon Description": "",
            "Typical Use": "",
            "Note": "",
        }
        row = _restore_tendon_product_metadata(row)
        metadata = _prestress_metadata_for_row(metadata_rows, index, label)
        if metadata:
            consumed_metadata_keys.add(_prestress_metadata_row_key(metadata, index))
        for column in (
            "Active",
            "x_mm",
            "y_mm",
            "Area_mm2",
            "Diameter_mm",
            "Eq Steel Dia_mm",
            "Input Mode",
            "Pe_eff_kN",
            "fpe_MPa",
            "fpj_ratio",
            "loss_percent",
            "Bonded",
            "Count",
        ):
            value = metadata.get(column)
            if not _is_blank(value):
                row[column] = value
        for column in (
            "Product",
            "Steel Type",
            "fpy_MPa",
            "fpu_MPa",
            "Ep_MPa",
            "Strand Count",
            "Strand Diameter_mm",
            "Strand Area_mm2",
            "Breaking Load_kN",
            "Duct Type",
            "Duct ID_mm",
            "Tendon Description",
            "Typical Use",
            "Note",
        ):
            value = metadata.get(column)
            if not _is_blank(value):
                row[column] = tendon_product_display_label(value) if column == "Product" else value
        rows.append(_normalize_tendon_group_table_row(row))
    for index, metadata in enumerate(metadata_rows, start=1):
        metadata_key = _prestress_metadata_row_key(metadata, index)
        if metadata_key in consumed_metadata_keys:
            continue
        row = {column: _clean_table_value(metadata.get(column)) for column in PRESTRESS_TABLE_METADATA_COLUMNS if column in metadata}
        if "Product" in row and not _is_blank(row.get("Product")):
            row["Product"] = tendon_product_display_label(row.get("Product"))
        if any(not _is_blank(value) for value in row.values()):
            rows.append(_normalize_tendon_group_table_row(row))
    return pd.DataFrame(rows)


def _sync_section_girder_length_from_setup_span(session_state: MutableMapping[str, Any], span_length_m: Any) -> None:
    """Keep Section Builder girder-length display locked to Setup span on project load."""

    try:
        span_mm = float(span_length_m) * 1000.0
    except (TypeError, ValueError):
        return
    if span_mm <= 0.0:
        return

    section_parameters = dict(session_state.get("section_parameters", {}) or {})
    preset_key = str(session_state.get("section_preset_key") or "").strip()
    if section_parameters:
        section_parameters["girder_length_mm"] = span_mm
        session_state["section_parameters"] = section_parameters
        if preset_key:
            session_state["section_parameters_preset_key"] = preset_key

    if preset_key:
        session_state[f"{preset_key}_girder_length_mm"] = span_mm
        session_state[f"{preset_key}_girder_length_mm_locked_from_setup"] = span_mm


def _reset_loaded_project_dirty_state(session_state: MutableMapping[str, Any], *, analysis_restored: bool = False) -> None:
    """Reset dirty-state keys after project load without discarding valid saved results."""

    for key in (
        CURRENT_INPUT_HASH_KEY,
        PREVIOUS_INPUT_HASH_KEY,
        LAST_ANALYSIS_HASH_KEY,
        LAST_REFRESHED_WORKSPACE_KEY,
        "_perf_input_group_hashes",
    ):
        session_state.pop(key, None)
    current_hash = project_input_hash(session_state)
    session_state[CURRENT_INPUT_HASH_KEY] = current_hash
    if analysis_restored:
        session_state[LAST_ANALYSIS_HASH_KEY] = current_hash
        session_state[ANALYSIS_STATUS_KEY] = "Current"
        session_state[REPORT_STATUS_KEY] = "Out of date"
        session_state[LAST_REFRESHED_WORKSPACE_KEY] = "Loaded saved analysis cache"
    else:
        session_state[ANALYSIS_STATUS_KEY] = "Not run"
        session_state[REPORT_STATUS_KEY] = "Not run"
    session_state[CHANGED_GROUPS_KEY] = []


def apply_project_to_session_state(project: ProjectModel, session_state: MutableMapping[str, Any]) -> None:
    session_state["project_name"] = project.project_name
    session_state["designer"] = project.designer or ""
    session_state["description"] = project.description or ""
    restored_code = normalize_project_design_code(project.code)
    restored_edition = normalize_project_code_edition(restored_code, project.code_edition)
    session_state[PROJECT_DESIGN_CODE_STATE_KEY] = restored_code
    session_state[PROJECT_CODE_EDITION_STATE_KEY] = restored_edition
    session_state["design_code"] = restored_code
    session_state["code_edition"] = restored_edition

    session_state["section_preset_key"] = project.section_preset_key
    session_state["section_preset_name"] = project.section_preset_name
    session_state["section_parameters"] = dict(project.section_parameters)
    session_state["section_parameters_preset_key"] = project.section_preset_key
    session_state["section_geometry"] = project.section_geometry
    session_state["section_dimensions"] = []
    if project.section_preset_key:
        for name, value in project.section_parameters.items():
            session_state[f"{project.section_preset_key}_{name}"] = value

    session_state["concrete_material"] = project.concrete_material
    session_state["concrete_materials"] = list(project.concrete_materials)
    session_state["active_concrete_material_name"] = project.active_concrete_material_name
    session_state["primary_concrete_material_name"] = project.active_concrete_material_name
    session_state["deck_topping_material_name"] = project.deck_topping_material_name
    session_state["rebar_materials"] = list(project.rebar_materials)
    session_state["prestress_materials"] = list(project.prestress_materials)
    session_state["active_rebar_material_name"] = project.active_rebar_material_name
    session_state["active_prestress_material_name"] = project.active_prestress_material_name

    session_state["load_cases"] = list(project.loads)
    session_state["rebars"] = list(project.rebars)
    session_state["prestress_elements"] = list(project.prestress_elements)
    session_state["analysis_mode_settings"] = project.analysis_mode_settings or AnalysisModeSettings()
    session_state["analysis_settings"] = project.analysis_settings or AnalysisSettings()
    session_state["serviceability_settings"] = project.serviceability_settings or ServiceabilitySettings()
    session_state["custom_stress_check_points"] = list(project.custom_stress_check_points)
    session_state["include_default_stress_check_points"] = project.include_default_stress_check_points

    crossbeam_input = project.metadata.get(SECLIB_METADATA_KEY)
    if isinstance(crossbeam_input, dict):
        definitions = canonical_section_definitions(crossbeam_input.get("section_definitions") or [])
        if definitions:
            session_state[CB_SECLIB_DEFINITIONS_KEY] = definitions
            active_id = str(crossbeam_input.get("active_section_id") or "")
            valid_ids = {row["Section ID"] for row in definitions}
            session_state[CB_SECLIB_ACTIVE_ID_KEY] = active_id if active_id in valid_ids else definitions[0]["Section ID"]
            session_state.pop(CB_SECLIB_LOADED_ID_KEY, None)
            session_state[CB_SECLIB_MIGRATION_KEY] = True
        length_m = crossbeam_input.get("length_m")
        if length_m is not None:
            session_state[CROSSBEAM_LENGTH_STATE_KEY] = length_m
        segment_rows = crossbeam_input.get("segment_rows")
        if isinstance(segment_rows, list):
            session_state[CROSSBEAM_SEGMENT_ROWS_STATE_KEY] = (
                migrate_segment_rows_to_library(segment_rows, definitions) if definitions else list(segment_rows)
            )
            session_state[CROSSBEAM_SEGMENT_REVISION_STATE_KEY] = int(
                session_state.get(CROSSBEAM_SEGMENT_REVISION_STATE_KEY, 0) or 0
            ) + 1

    session_state["loads_table"] = _loads_to_table(project.loads)
    workflow_load_tables = project.metadata.get("workflow_load_tables")
    if isinstance(workflow_load_tables, dict):
        for key in WORKFLOW_LOAD_TABLE_METADATA_KEYS:
            if key in workflow_load_tables:
                session_state[key] = pd.DataFrame(workflow_load_tables.get(key) or [])
    shear_reinforcement = project.metadata.get(SHEAR_REINFORCEMENT_TABLE_KEY)
    if isinstance(shear_reinforcement, list):
        session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = pd.DataFrame(shear_reinforcement)
        session_state["beam_girder_shear_reinforcement_editor_revision"] = int(
            session_state.get("beam_girder_shear_reinforcement_editor_revision", 0) or 0
        ) + 1
    girder_prestress_force_states = project.metadata.get("girder_prestress_force_states_table")
    if isinstance(girder_prestress_force_states, list):
        session_state["girder_prestress_force_states_table"] = pd.DataFrame(girder_prestress_force_states)
    girder_strand_layout = project.metadata.get("girder_strand_layout_table")
    if isinstance(girder_strand_layout, list):
        session_state["girder_strand_layout_table"] = pd.DataFrame(girder_strand_layout)
    girder_prestress_system_settings = project.metadata.get("girder_prestress_system_settings")
    if isinstance(girder_prestress_system_settings, dict):
        session_state["girder_prestress_system_settings"] = dict(girder_prestress_system_settings)
    railway_u_girder_stage_settings = project.metadata.get(RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY)
    if isinstance(railway_u_girder_stage_settings, dict):
        session_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = dict(railway_u_girder_stage_settings)
    girder_prestress_code_loss_settings = project.metadata.get("girder_prestress_code_loss_settings")
    if isinstance(girder_prestress_code_loss_settings, dict):
        session_state["girder_prestress_code_loss_settings"] = dict(girder_prestress_code_loss_settings)
    beam_girder_system_settings = project.metadata.get(BEAM_GIRDER_SYSTEM_SETTINGS_KEY)
    if isinstance(beam_girder_system_settings, dict):
        normalized_system = system_settings_from_mapping(beam_girder_system_settings).as_metadata()
        session_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = normalized_system
        # Keep legacy prestress-span consumers synchronized to the Setup single source.
        existing_ps_system = dict(session_state.get("girder_prestress_system_settings", {}) or {})
        existing_ps_system["span_length_m"] = normalized_system.get("span_length_m")
        session_state["girder_prestress_system_settings"] = existing_ps_system
        _sync_section_girder_length_from_setup_span(session_state, normalized_system.get("span_length_m"))
    beam_girder_sls_auto_load_settings = project.metadata.get(BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY)
    if isinstance(beam_girder_sls_auto_load_settings, dict):
        session_state[BEAM_GIRDER_SLS_AUTO_LOAD_SETTINGS_KEY] = auto_load_settings_from_mapping(beam_girder_sls_auto_load_settings).as_metadata()
    building_service_load_settings = project.metadata.get(BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY)
    if isinstance(building_service_load_settings, dict):
        session_state[BUILDING_BEAM_GIRDER_SERVICE_LOAD_SETTINGS_KEY] = building_service_load_settings_from_mapping(building_service_load_settings).as_metadata()
    raw_rebar_table = project.metadata.get(LONGITUDINAL_REBAR_TABLE_METADATA_KEY)
    if isinstance(raw_rebar_table, list):
        session_state["rebar_table"] = _ensure_rebar_table_columns(pd.DataFrame(raw_rebar_table))
    else:
        session_state["rebar_table"] = _rebars_to_table(project.rebars)
    session_state["rebar_editor_revision"] = int(session_state.get("rebar_editor_revision", 0) or 0) + 1
    session_state["prestress_table"] = _prestress_to_table(
        project.prestress_elements,
        _coerce_list(project.metadata.get(PRESTRESS_TABLE_METADATA_KEY)),
    )
    session_state["prestress_editor_revision"] = int(session_state.get("prestress_editor_revision", 0) or 0) + 1
    session_state["custom_stress_check_points_table"] = stress_check_points_to_dataframe(project.custom_stress_check_points)

    for flag_name in ("rebars_valid_for_analysis", "prestress_valid_for_analysis", ORDINARY_REBAR_FLAG_KEY, PRESTRESSING_STEEL_FLAG_KEY):
        if flag_name in project.metadata:
            session_state[flag_name] = bool(project.metadata[flag_name])
    if REINFORCEMENT_FLAGS_PRESET_KEY in project.metadata:
        session_state[REINFORCEMENT_FLAGS_PRESET_KEY] = project.metadata[REINFORCEMENT_FLAGS_PRESET_KEY]
    session_state["project_metadata"] = dict(project.metadata)
    analysis_restored = _restore_analysis_results_metadata(project, session_state)
    _reset_loaded_project_dirty_state(session_state, analysis_restored=analysis_restored)

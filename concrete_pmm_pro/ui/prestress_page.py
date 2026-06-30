"""Prestress tab UI and parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import sqrt
from pathlib import Path
from typing import Any
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pydantic import ValidationError
from shapely.geometry import LineString, Point, Polygon

from concrete_pmm_pro.core.models import PrestressElement, SectionGeometry
from concrete_pmm_pro.core.design_code import (
    PROJECT_CODE_AASHTO_LRFD,
    PROJECT_CODE_ACI318,
    normalize_project_design_code,
    project_design_code_from_session,
    workflow_project_design_code_from_session,
)
from concrete_pmm_pro.core.reinforcement_system import ordinary_rebar_enabled, prestressing_steel_enabled
from concrete_pmm_pro.core.units import kN_to_N
from concrete_pmm_pro.data.prestress_tendon_products import (
    DEFAULT_STRAND_AREA_MM2,
    DEFAULT_STRAND_DIAMETER_MM,
    DEFAULT_STRAND_EP_MPA,
    DEFAULT_STRAND_FPY_MPA,
    DEFAULT_STRAND_FPU_MPA,
    TendonProduct,
    apply_tendon_product_to_row,
    equivalent_steel_diameter_mm,
    get_tendon_product,
    is_tendon_6n_label,
    list_tendon_products,
    make_custom_tendon_product,
    standard_tendon_label,
    tendon_product_display_label,
    tendon_product_options,
)
from concrete_pmm_pro.geometry.rebar_layout import generate_perimeter_rebar_layout
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.serviceability.section_properties import compute_gross_section_properties
from concrete_pmm_pro.serviceability.girder_prestress_losses import (
    GirderApproximateLossInput,
    GirderLossStrandGroupInput,
    LOSS_INPUT_AUDIT_COLUMNS,
    RefinedAashtoCoefficientInput,
    RefinedAashtoManualCoefficientInput,
    calculate_aci_pci_approximate_prestress_loss,
    calculate_approximate_prestress_loss,
    calculate_refined_aashto_time_dependent_loss,
    estimate_refined_aashto_coefficients,
    estimate_aci_pci_guided_loss_inputs,
    estimate_volume_surface_ratio_mm,
    loss_result_dataframe_to_force_state_table,
)
from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BEAM_GIRDER_SYSTEM_SETTINGS_KEY,
    girder_self_weight_kN_m,
    simple_span_udl_moment_kNm,
    system_settings_from_mapping,
)
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_sls_decision_summary_dataframe,
    railway_u_girder_final_service_accumulation_dataframe,
    railway_u_girder_final_service_governing_rows,
    railway_u_girder_final_service_limit_check_dataframe,
    railway_u_girder_locked_in_governing_rows,
    railway_u_girder_locked_in_stress_accumulation_dataframe,
    railway_u_girder_service_load_governing_rows,
    railway_u_girder_service_load_handoff_dataframe,
    railway_u_girder_service_load_limit_check_dataframe,
    railway_u_girder_stage_governing_rows,
    railway_u_girder_stage_limit_governing_rows,
    railway_u_girder_staged_stress_limit_check_dataframe,
    railway_u_girder_staged_stress_preview_dataframe,
)
from concrete_pmm_pro.serviceability.girder_prestress_station import (
    debonded_strand_count_for_row,
    debonded_strand_numbers_for_row,
    explicit_debonded_strand_numbers,
    girder_advisory_debonding_recommendation_dataframe,
    girder_critical_transfer_station_dataframe,
    girder_debonding_preview_status,
    girder_debonding_rule_audit_dataframe,
    girder_debonding_zones_for_row,
    girder_prestress_station_dataframe,
    girder_stage_pe_mapping_dataframe,
    girder_station_participation_dataframe,
    girder_stage_pe_mapping_status,
    station_candidates_from_debonding,
    strand_group_effective_at_station,
)
from concrete_pmm_pro.visualization import create_section_preview
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRESTRESS_DB_PATH = REPO_ROOT / "data" / "prestress_steel_database.csv"

STEEL_TYPE_OPTIONS = ["wire", "strand", "prestressing_bar", "tendon_group", "custom"]
JACKING_LOSS_INPUT_MODE = "Jacking + Total Loss %"
LEGACY_JACKING_LOSS_INPUT_MODE = "Jacking Stress + Losses"
INPUT_MODE_OPTIONS = ["Passive", "Pe_eff", "fpe", JACKING_LOSS_INPUT_MODE]
INPUT_MODE_DISPLAY_LABELS = {
    "Passive": "Passive",
    "Pe_eff": "Pe_eff",
    "fpe": "fpe",
    JACKING_LOSS_INPUT_MODE: JACKING_LOSS_INPUT_MODE,
}
LEGACY_VERBOSE_INPUT_MODE_ALIASES = {
    "Passive - no prestress force": "Passive",
    "Pe_eff - enter effective force after losses (kN)": "Pe_eff",
    "fpe - enter effective stress after losses (MPa)": "fpe",
    "Jacking + Total Loss % - compute Pe_eff from fpj and total loss": JACKING_LOSS_INPUT_MODE,
}
INPUT_MODE_EDITOR_OPTIONS = list(INPUT_MODE_DISPLAY_LABELS.values())
LEGACY_INPUT_MODE_ALIASES = {
    "Effective Force Pe": "Pe_eff",
    "Effective Stress fpe": "fpe",
    LEGACY_JACKING_LOSS_INPUT_MODE: JACKING_LOSS_INPUT_MODE,
    **LEGACY_VERBOSE_INPUT_MODE_ALIASES,
    **{display_label: value for value, display_label in INPUT_MODE_DISPLAY_LABELS.items()},
}
LEGACY_INPUT_MODE_OPTIONS = [LEGACY_JACKING_LOSS_INPUT_MODE]
TENDON_PRODUCT_CREATION_MODES = ["Standard tendon product", "Custom tendon"]
MANUAL_PRESTRESS_LAYOUT_METHOD = "Manual table"
AUTO_PERIMETER_PRESTRESS_LAYOUT_METHOD = "Auto perimeter layout"
PLANNED_PRESTRESS_LAYOUT_METHODS = ["Linear layout", "Circular layout"]
PRESTRESS_LAYOUT_METHOD_OPTIONS = [MANUAL_PRESTRESS_LAYOUT_METHOD, AUTO_PERIMETER_PRESTRESS_LAYOUT_METHOD, *PLANNED_PRESTRESS_LAYOUT_METHODS]
PRESTRESS_LAYOUT_METHOD_STATE_KEY = "prestress_layout_method"
PRESTRESS_LAYOUT_METHOD_NOTICE_KEY = "prestress_layout_method_planned_notice"
PRESTRESS_FORCE_INPUT_METHOD_STATE_KEY = "prestress_force_input_method"

PRESTRESS_COMPACT_EDITOR_COLUMNS = [
    "Active",
    "Label",
    "Product",
    "x_mm",
    "y_mm",
    "Area_mm2",
    "Input Mode",
    "Pe_eff_kN",
    "fpe_MPa",
    "fpj_ratio",
    "loss_percent",
    "Bonded",
    "Count",
]
PRESTRESS_REFERENCE_DETAIL_COLUMNS = [
    "Label",
    "Steel Type",
    "Product",
    "Diameter_mm",
    "Eq Steel Dia_mm",
    "fpy_MPa",
    "fpu_MPa",
    "Ep_MPa",
    "fpj_ratio",
    "loss_percent",
    "Strand Count",
    "Strand Diameter_mm",
    "Strand Area_mm2",
    "Breaking Load_kN",
    "Duct Type",
    "Duct ID_mm",
]

GIRDER_PRESTRESS_FORCE_STATE_COLUMNS = [
    "Check Stage",
    "Prestress State",
    "Pe_kN",
    "yps_mm_from_bottom",
    "Note",
]

GIRDER_PRESTRESS_FORCE_STATE_SPECS = [
    (
        "Transfer stage",
        "Pe_transfer / P_release",
        "Initial prestress at transfer/release. Use with precast self-weight and precast gross section.",
    ),
    (
        "Construction stage",
        "Pe_construction",
        "Engineer-controlled prestress force during deck casting/construction stage; no automatic loss calculation.",
    ),
    (
        "Service stage",
        "Pe_eff_final",
        "Effective prestress after losses for final service. Do not also include prestress in Loads resultant.",
    ),
]

GIRDER_LOSS_INPUT_MODE_OPTIONS = ["Manual stage Pe", "Percentage loss", "Approximate code-based loss", "Refined AASHTO time-dependent loss"]
GIRDER_LOSS_BASIS_USE_PROJECT = "Use project design code"
GIRDER_LOSS_BASIS_AASHTO = PROJECT_CODE_AASHTO_LRFD
GIRDER_LOSS_BASIS_ACI_PCI = "ACI 318 / PCI-style"
GIRDER_LOSS_BASIS_MANUAL = "Manual / project-specific"
GIRDER_LOSS_CODE_BASIS_OPTIONS = [
    GIRDER_LOSS_BASIS_USE_PROJECT,
    GIRDER_LOSS_BASIS_AASHTO,
    GIRDER_LOSS_BASIS_ACI_PCI,
    GIRDER_LOSS_BASIS_MANUAL,
]
DEFAULT_CODE_LOSS_FPJ_RATIO = 0.75
ACI_PCI_INPUT_SOURCE_AUTO = "Auto from current section / material"
ACI_PCI_INPUT_SOURCE_MANUAL = "Manual override"
ACI_PCI_INPUT_SOURCE_OPTIONS = [ACI_PCI_INPUT_SOURCE_AUTO, ACI_PCI_INPUT_SOURCE_MANUAL]
ACI_PCI_RH_PRESETS = {
    "Thailand Central / Bangkok typical (75%)": 75.0,
    "Thailand North typical (72%)": 72.0,
    "Thailand South / coastal typical (80%)": 80.0,
    "Manual project RH": None,
}

REFINED_COEFFICIENT_USER_DEFINED = "User-defined / project-specific"
REFINED_COEFFICIENT_PRESETS: dict[str, dict[str, float]] = {
    "Thailand high humidity typical (RH ≈ 75%)": {
        "humidity_percent": 75.0,
        "Kid": 0.85,
        "Kdf": 0.85,
        "eps_bid_microstrain": 80.0,
        "eps_bdf_microstrain": 60.0,
        "psi_td_ti": 0.60,
        "psi_tf_ti": 1.60,
        "psi_tf_td": 1.00,
        "delta_fcd_MPa": 0.0,
        "delta_fcdf_MPa": 0.0,
    },
    "Moderate humidity (RH ≈ 60%)": {
        "humidity_percent": 60.0,
        "Kid": 0.85,
        "Kdf": 0.85,
        "eps_bid_microstrain": 100.0,
        "eps_bdf_microstrain": 75.0,
        "psi_td_ti": 0.70,
        "psi_tf_ti": 1.80,
        "psi_tf_td": 1.10,
        "delta_fcd_MPa": 0.0,
        "delta_fcdf_MPa": 0.0,
    },
    "Dry climate conservative (RH ≈ 45%)": {
        "humidity_percent": 45.0,
        "Kid": 0.85,
        "Kdf": 0.85,
        "eps_bid_microstrain": 130.0,
        "eps_bdf_microstrain": 95.0,
        "psi_td_ti": 0.85,
        "psi_tf_ti": 2.10,
        "psi_tf_td": 1.25,
        "delta_fcd_MPa": 0.0,
        "delta_fcdf_MPa": 0.0,
    },
}
REFINED_COEFFICIENT_PRESET_OPTIONS = [*REFINED_COEFFICIENT_PRESETS.keys(), REFINED_COEFFICIENT_USER_DEFINED]
DEFAULT_REFINED_COEFFICIENT_PRESET = "Thailand high humidity typical (RH ≈ 75%)"
REFINED_COEFFICIENT_SOURCE_AUTO = "Auto-estimated from RH/time/section"
REFINED_COEFFICIENT_SOURCE_PRESET = "Preset coefficient set"
REFINED_COEFFICIENT_SOURCE_MANUAL = "Manual override"
REFINED_COEFFICIENT_SOURCE_OPTIONS = [
    REFINED_COEFFICIENT_SOURCE_AUTO,
    REFINED_COEFFICIENT_SOURCE_PRESET,
    REFINED_COEFFICIENT_SOURCE_MANUAL,
]
REFINED_STRESS_EFFECT_NOT_INCLUDED = "Not included / use 0.00 MPa"
REFINED_STRESS_EFFECT_MANUAL = "Manual input"
REFINED_STRESS_EFFECT_AUTO_FUTURE = "Auto from Loads / staged effects (future)"
REFINED_STRESS_EFFECT_SOURCE_OPTIONS = [
    REFINED_STRESS_EFFECT_NOT_INCLUDED,
    REFINED_STRESS_EFFECT_MANUAL,
    REFINED_STRESS_EFFECT_AUTO_FUTURE,
]
REFINED_PRESET_WIDGET_KEYS = {
    "Kid": "girder_refined_kid",
    "Kdf": "girder_refined_kdf",
    "eps_bid_microstrain": "girder_refined_eps_bid",
    "eps_bdf_microstrain": "girder_refined_eps_bdf",
    "psi_td_ti": "girder_refined_psi_td_ti",
    "psi_tf_ti": "girder_refined_psi_tf_ti",
    "psi_tf_td": "girder_refined_psi_tf_td",
    "delta_fcd_MPa": "girder_refined_delta_fcd",
    "delta_fcdf_MPa": "girder_refined_delta_fcdf",
}
GIRDER_LOSS_FORCE_STATE_COLUMNS = [
    "Active",
    "Group ID",
    "No. strands",
    "Pjack/strand_kN",
    "Transfer loss %",
    "Pe_transfer/strand_kN",
    "Construction loss %",
    "Pe_construction/strand_kN",
    "Long-term loss %",
    "Pe_eff_final/strand_kN",
    "Total loss %",
    "QA status",
    "Note",
]

GIRDER_STRAND_LAYOUT_COLUMNS = [
    "Active",
    "Group ID",
    "Layer",
    "Strand Size",
    "No. Strands",
    "Area/Strand_mm2",
    "Total Aps_mm2",
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

GIRDER_STRAND_LAYOUT_NUMERIC_COLUMNS = [
    "No. Strands",
    "Area/Strand_mm2",
    "Total Aps_mm2",
    "Row center x_mm",
    "y_mm_from_bottom",
    "Edge CL_mm",
    "Min spacing_mm",
    "Computed spacing_mm",
    "Pe_transfer/strand_kN",
    "Pe_construction/strand_kN",
    "Pe_eff_final/strand_kN",
    "Left debond m",
    "Right debond m",
]

# Compact editor columns shown by default. The debond pattern shown to the
# engineer is now derived from left/right debond length + debonded strand
# numbers. Legacy Debond pattern metadata remains in the backend table for
# old project compatibility, but it is intentionally not an editable primary
# input column.
GIRDER_STRAND_LAYOUT_EDITOR_COLUMNS = [
    "Active",
    "Group ID",
    "Strand Size",
    "No. Strands",
    "Strand x positions mm",
    "y_mm_from_bottom",
    "Left debond m",
    "Right debond m",
    "Debonded strand nos",
    "Note",
]

GIRDER_STRAND_LAYOUT_AUDIT_COLUMNS = [
    "Group ID",
    "Layer",
    "No. Strands",
    "Area/Strand_mm2",
    "Total Aps_mm2",
    "Row center x_mm",
    "Strand x positions mm",
    "y_mm_from_bottom",
    "Edge CL_mm",
    "Min spacing_mm",
    "Computed spacing_mm",
    "Left debond m",
    "Right debond m",
    "Debonded strand nos",
]

GIRDER_DEBOND_MODE_OPTIONS = [
    "No debonding",
    "Symmetric left/right",
    "Left/right independent",
]

GIRDER_PRESTRESS_SYSTEM_DEFAULTS = {
    "girder_system": "Simple supported precast girder",
    "prestress_type": "Pretensioned straight strands",
    "span_length_m": 30.0,
    "station_convention": "x = 0 at left support, x = L at right support",
    "debond_model": "Left/right independent",
}

RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M = 10.0
RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY = "railway_u_girder_stage_settings"
RAILWAY_U_GIRDER_STAGE_DEFAULTS: dict[str, Any] = {
    "web_fc_MPa": 45.0,
    "web_fci_MPa": 36.0,
    "slab_fc_MPa": 35.0,
    "concrete_unit_weight_kN_m3": 24.0,
    "support_condition": "Simply supported",
    "construction_method": "Case B - wet slab carried by precast webs",
    "wet_slab_distribution_each_web": 0.50,
    "formwork_construction_load_kN_m2": 2.5,
    "lifting_point_ratio": 0.20,
    "lifting_impact_factor": 1.10,
}

GIRDER_STRAND_SIZE_OPTIONS = [
    "12.7 mm low-relaxation strand",
    "15.2 mm low-relaxation strand",
]

GIRDER_STRAND_SIZE_PROPERTIES = {
    "12.7 mm low-relaxation strand": {
        "diameter_mm": 12.7,
        "area_mm2": 98.7,
        "fpu_mpa": 1860.0,
        "fpy_mpa": 1670.0,
        "ep_mpa": DEFAULT_STRAND_EP_MPA,
        "recommended_edge_cl_mm": 45.0,
        "recommended_min_spacing_mm": 50.0,
    },
    "15.2 mm low-relaxation strand": {
        "diameter_mm": 15.2,
        "area_mm2": 140.0,
        "fpu_mpa": 1860.0,
        "fpy_mpa": 1670.0,
        "ep_mpa": DEFAULT_STRAND_EP_MPA,
        "recommended_edge_cl_mm": 45.0,
        "recommended_min_spacing_mm": 55.0,
    },
}

DEFAULT_GIRDER_STRAND_SIZE = "12.7 mm low-relaxation strand"
DEFAULT_GIRDER_STRAND_ROW_COUNT = 2
DEFAULT_GIRDER_STRAND_FIRST_ROW_Y_MM = 50.0
DEFAULT_GIRDER_STRAND_ROW_VERTICAL_SPACING_MM = 50.0
DEFAULT_GIRDER_STRAND_X_SPACING_MM = 50.0
DEFAULT_GIRDER_STRAND_EDGE_CL_MM = 45.0
DEFAULT_GIRDER_STRAND_FALLBACK_COUNTS = [8, 6]

BOX_PLANK_PRACTICAL_DEBOND_PATTERN = "Symmetric spaced pairs"
PRECAST_BOX_BEAM_PRESET_KEYS = frozenset({"box_section_fillet", "precast_box_beam_exterior"})
PRECAST_PLANK_GIRDER_PRESET_KEYS = frozenset(
    {
        "parametric_plank_girder_interior",
        "parametric_plank_girder_exterior",
        "parametric_plank_girder_voided_interior",
        "parametric_plank_girder_voided_exterior",
    }
)
BOX_PLANK_PRACTICAL_DEBOND_LENGTH_M = 1.0
RAILWAY_U_GIRDER_PRESET_KEY = "railway_u_girder"
RAILWAY_U_GIRDER_STRAND_SPACING_MM = 55.0
RAILWAY_U_GIRDER_STRAND_EDGE_OUTER_MM = 130.0
RAILWAY_U_GIRDER_STRAND_EDGE_INNER_MM = 80.0
RAILWAY_U_GIRDER_ROW_Y_FROM_BOTTOM_MM = (95.0, 150.0, 205.0, 260.0, 315.0)
RAILWAY_U_GIRDER_ROW_INDEX_SETS = (
    tuple(range(9)),
    tuple(range(9)),
    tuple(range(1, 8)),
    tuple(range(1, 8)),
    (2, 3, 5, 6),  # drawing Row 5 uses columns 3, 4, 6, and 7
)
RAILWAY_U_GIRDER_DEBOND_SYMBOLS_MM = {
    0: ("Bonded", "circle-open"),
    1000: ("Debonded at 1000 mm", "cross-open"),
    2000: ("Debonded at 2000 mm", "asterisk-open"),
    3000: ("Debonded at 3000 mm", "x-open"),
    4000: ("Debonded at 4000 mm", "triangle-down-open"),
    5000: ("Debonded at 5000 mm", "triangle-up-open"),
}
RAILWAY_U_GIRDER_DEBOND_ROW_STEP_M = 0.5

GIRDER_PRESTRESS_UI_PRESET_KEYS = frozenset(
    {
        "parametric_i_girder",
        "u_girder",
        RAILWAY_U_GIRDER_PRESET_KEY,
        "box_section_fillet",
        "precast_box_beam_exterior",
        "parametric_plank_girder_interior",
        "parametric_plank_girder_exterior",
        "parametric_plank_girder_voided_interior",
        "parametric_plank_girder_voided_exterior",
        "psc_i_girder",
        "single_cell_box_girder",
    }
)


def _session_member_type() -> str:
    """Return the current Project-page member workflow from session state."""

    settings = st.session_state.get("analysis_mode_settings")
    if hasattr(settings, "member_type"):
        return str(getattr(settings, "member_type") or "").strip()
    if isinstance(settings, dict):
        return str(settings.get("member_type") or "").strip()
    return "column_pier_pmm"


def _current_section_preset_key() -> str:
    """Return the active Section Builder preset key without importing Section Builder."""

    return str(st.session_state.get("section_preset_key") or "").strip()


def _is_girder_prestress_layout_workflow_active() -> bool:
    """Return whether the dedicated girder strand/debonding UI should be shown.

    The strand/debonding editor is a prestressed-girder detailing workflow, not
    a bridge-load workflow.  It is available for Bridge Beam/Girder presets and
    for explicitly shared prestressed girder geometry under Building
    Beam/Girder, while remaining hidden for Column/Pier/Wall/Pylon members.
    """

    member_type = _session_member_type()
    preset_key = _current_section_preset_key()
    if preset_key not in GIRDER_PRESTRESS_UI_PRESET_KEYS:
        return False
    if member_type == "beam_girder":
        return True
    if member_type == "building_beam_girder" and preset_key == "parametric_i_girder":
        return True
    return False


def _has_active_prestress_force(elements: list[PrestressElement]) -> bool:
    """Return whether any prestress row has an actual prestress force/state.

    Passive catalog/example rows are useful reference data but should not force
    a large default section preview on non-prestressed members.
    """

    for element in elements:
        if abs(float(element.pe_eff_n or 0.0)) > 1.0:
            return True
        if abs(float(element.initial_stress_mpa or 0.0)) > 1e-6:
            return True
        if abs(float(element.initial_strain or 0.0)) > 1e-12:
            return True
    return False


def _prestress_force_state_label(elements: list[PrestressElement]) -> PrestressMetric:
    """Return a user-facing status for active versus reference-only prestress rows."""

    if not elements:
        return PrestressMetric(
            "Force status",
            "No active rows",
            detail="prestress not used",
            status="neutral",
            strong=True,
        )
    if _has_active_prestress_force(elements):
        return PrestressMetric(
            "Force status",
            "Active Pe available",
            detail="used by analysis",
            status="ready",
            strong=True,
        )
    return PrestressMetric(
        "Force status",
        "Reference only",
        detail="no active Pe assigned",
        status="warning",
        strong=True,
    )


def _empty_prestress_parse_result(info: list[str] | None = None) -> "PrestressParseResult":
    """Return an empty section-level prestress parse result.

    Precast girder workflows use the dedicated strand-layout/debonding table.
    Section-level tendon rows may still exist in old projects, but they are
    hidden and ignored in this workflow so legacy PS1/PS2 rows cannot pollute
    the main prestress status or preview.
    """

    return PrestressParseResult(elements=[], errors=[], warnings=[], info=list(info or []))



@dataclass(frozen=True)
class PrestressParseResult:
    elements: list[PrestressElement]
    errors: list[str]
    warnings: list[str]
    info: list[str]


@dataclass(frozen=True)
class AutoPrestressLayoutResult:
    table: pd.DataFrame
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    info: tuple[str, ...] = ()
    perimeter_length_mm: float | None = None
    actual_spacing_mm: float | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class PrestressMetric:
    title: str
    value: str
    detail: str = ""
    status: str = "neutral"
    strong: bool = False


_PRESTRESS_PAGE_CSS = """
<style>
.cpmm-prestress-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.55rem;
  margin-bottom: 0.75rem;
}
.cpmm-prestress-chip {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.58rem 0.7rem;
  min-height: 76px;
}
.cpmm-prestress-chip-label {
  color: #667085;
  font-size: 0.74rem;
  font-weight: 650;
  letter-spacing: 0;
  margin-bottom: 0.18rem;
}
.cpmm-prestress-chip-value {
  color: #101828;
  font-size: 0.96rem;
  font-weight: 720;
  line-height: 1.22;
  overflow-wrap: anywhere;
}
.cpmm-prestress-chip-detail {
  color: #667085;
  font-size: 0.74rem;
  line-height: 1.25;
  margin-top: 0.16rem;
}
.cpmm-prestress-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.12rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0;
}
.cpmm-prestress-badge.ready { color: #1f5f2a; background: #e7f5e8; }
.cpmm-prestress-badge.warning { color: #7a4b00; background: #fff4d6; }
.cpmm-prestress-badge.danger { color: #9f1f17; background: #fde8e7; }
.cpmm-prestress-badge.info { color: #1849a9; background: #e8f1ff; }
.cpmm-prestress-badge.neutral { color: #475467; background: #eef1f5; }
.cpmm-prestress-kv-panel {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.64rem 0.84rem;
}
.cpmm-prestress-kv-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  gap: 0.8rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.32rem 0;
}
.cpmm-prestress-kv-row:last-child { border-bottom: 0; }
.cpmm-prestress-kv-label {
  color: #667085;
  font-size: 0.82rem;
  font-weight: 600;
}
.cpmm-prestress-kv-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 650;
  text-align: right;
  overflow-wrap: anywhere;
}
.cpmm-prestress-note-panel {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #fbfcfe;
  padding: 0.68rem 0.84rem;
}
.cpmm-prestress-note-item {
  color: #475467;
  font-size: 0.82rem;
  line-height: 1.35;
  padding: 0.2rem 0;
}
.cpmm-prestress-message-list {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fbfcfe;
  padding: 0.62rem 0.78rem;
  margin-top: 0.55rem;
}
.cpmm-prestress-message-item {
  color: #475467;
  font-size: 0.82rem;
  line-height: 1.35;
  padding: 0.18rem 0;
}
.cpmm-prestress-quiet-note {
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.35;
}

.cpmm-prestress-table-note {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fbfcfe;
  padding: 0.52rem 0.7rem;
  margin: 0.42rem 0 0.65rem 0;
  color: #667085;
  font-size: 0.80rem;
  line-height: 1.35;
}
.cpmm-prestress-mode-guide {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.5rem;
  margin: 0.55rem 0 0.65rem 0;
}
.cpmm-prestress-mode-card {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.52rem 0.65rem;
}
.cpmm-prestress-mode-title {
  color: #101828;
  font-size: 0.82rem;
  font-weight: 720;
  margin-bottom: 0.16rem;
}
.cpmm-prestress-mode-text {
  color: #667085;
  font-size: 0.78rem;
  line-height: 1.32;
}
@media (max-width: 980px) {
  .cpmm-prestress-mode-guide { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 1320px) {
  .cpmm-prestress-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .cpmm-prestress-strip { grid-template-columns: minmax(0, 1fr); }
}
</style>
"""


def load_prestress_steel_database(path: Path | str = DEFAULT_PRESTRESS_DB_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def _project_prestress_materials_dataframe(materials: list[Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for material in materials:
        rows.append(
            {
                "name": material.name,
                "type": material.steel_type,
                "diameter_mm": material.diameter_mm,
                "area_mm2": material.area_mm2,
                "grade": material.grade,
                "fpy_MPa": material.fpy_MPa,
                "fpu_MPa": material.fpu_MPa,
                "Ep_MPa": material.Ep_MPa,
                "source": material.source or "project_material",
                "area_source": material.area_source or "project_material",
                "is_catalog_verified": material.is_catalog_verified,
            }
        )
    return pd.DataFrame(rows)


def _combined_prestress_database(database: pd.DataFrame, project_materials: list[Any]) -> pd.DataFrame:
    project_df = _project_prestress_materials_dataframe(project_materials)
    if project_df.empty:
        return database
    return pd.concat([database, project_df], ignore_index=True).drop_duplicates(subset=["name"], keep="last")


def _default_prestress_table(prestress_db: pd.DataFrame) -> pd.DataFrame:
    first_product = str(prestress_db.iloc[0]["name"])
    second_product = "PS Bar 32 - 1080/1230" if "PS Bar 32 - 1080/1230" in set(prestress_db["name"]) else first_product
    first = prestress_db.loc[prestress_db["name"] == first_product].iloc[0]
    second = prestress_db.loc[prestress_db["name"] == second_product].iloc[0]
    return pd.DataFrame(
        [
            {
                "Active": False,
                "Label": "PS1",
                "Steel Type": first["type"],
                "Product": first_product,
                "x_mm": -100.0,
                "y_mm": -250.0,
                "Area_mm2": float(first["area_mm2"]),
                "Diameter_mm": float(first["diameter_mm"]),
                "Eq Steel Dia_mm": None,
                "fpy_MPa": float(first["fpy_MPa"]),
                "fpu_MPa": float(first["fpu_MPa"]),
                "Ep_MPa": float(first["Ep_MPa"]),
                "Input Mode": "Passive",
                "Pe_eff_kN": 0.0,
                "fpe_MPa": 0.0,
                "fpj_ratio": 0.75,
                "loss_percent": 15.0,
                "Bonded": True,
                "Count": 1,
                "Strand Count": None,
                "Breaking Load_kN": None,
                "Duct Type": "",
                "Duct ID_mm": None,
                "Note": "",
            },
            {
                "Active": False,
                "Label": "PS2",
                "Steel Type": second["type"],
                "Product": second_product,
                "x_mm": 100.0,
                "y_mm": -250.0,
                "Area_mm2": float(second["area_mm2"]),
                "Diameter_mm": float(second["diameter_mm"]),
                "Eq Steel Dia_mm": None,
                "fpy_MPa": float(second["fpy_MPa"]),
                "fpu_MPa": float(second["fpu_MPa"]),
                "Ep_MPa": float(second["Ep_MPa"]),
                "Input Mode": "Passive",
                "Pe_eff_kN": 0.0,
                "fpe_MPa": 0.0,
                "fpj_ratio": 0.75,
                "loss_percent": 15.0,
                "Bonded": True,
                "Count": 1,
                "Strand Count": None,
                "Breaking Load_kN": None,
                "Duct Type": "",
                "Duct ID_mm": None,
                "Note": "",
            },
        ]
    )


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _row_is_blank(row: pd.Series) -> bool:
    columns = [
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
        "Pe_eff",
        "fpe_MPa",
        "fpj_ratio",
        "loss_percent",
        "Count",
        "Note",
    ]
    return all(_is_blank(row.get(column)) for column in columns)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_blank(value):
        return False
    if str(value).strip().lower() in {"true", "1", "yes"}:
        return True
    if str(value).strip().lower() in {"false", "0", "no"}:
        return False
    return bool(value)


def _to_bool_default_true(value: Any) -> bool:
    if _is_blank(value):
        return True
    return _to_bool(value)


def _to_float(value: Any) -> float | None:
    if _is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_count(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return 1
    if parsed < 1 or int(parsed) != parsed:
        return None
    return int(parsed)


def _normalize_input_mode_label(value: Any) -> str:
    mode = "Passive" if _is_blank(value) else str(value).strip()
    return LEGACY_INPUT_MODE_ALIASES.get(mode, mode)


def _input_mode_display_label(value: Any) -> str:
    """Return the user-facing editor label for a stored input mode value."""

    mode = _normalize_input_mode_label(value)
    return INPUT_MODE_DISPLAY_LABELS.get(mode, INPUT_MODE_DISPLAY_LABELS["Passive"])


def _is_planned_prestress_layout_method(method: Any) -> bool:
    return str(method or "").strip() in PLANNED_PRESTRESS_LAYOUT_METHODS


def _planned_prestress_layout_message(method: Any) -> str:
    method_label = str(method or "").strip() or "Selected layout"
    return (
        f"{method_label} is planned for a later milestone and is not used for analysis yet. "
        "The section-level Manual table remains the active prestress input workflow."
    )


def _guard_prestress_layout_method_selection() -> None:
    selected = st.session_state.get(PRESTRESS_LAYOUT_METHOD_STATE_KEY, MANUAL_PRESTRESS_LAYOUT_METHOD)
    if _is_planned_prestress_layout_method(selected):
        st.session_state[PRESTRESS_LAYOUT_METHOD_NOTICE_KEY] = selected
        st.session_state[PRESTRESS_LAYOUT_METHOD_STATE_KEY] = MANUAL_PRESTRESS_LAYOUT_METHOD


def _apply_force_input_method_to_active_rows(table: pd.DataFrame, input_mode: Any) -> pd.DataFrame:
    """Apply a canonical force input mode to active prestress rows only."""

    applied = pd.DataFrame(table).copy()
    if applied.empty:
        return applied
    mode = _normalize_input_mode_label(input_mode)
    if mode not in INPUT_MODE_OPTIONS:
        return applied
    if "Input Mode" not in applied.columns:
        applied["Input Mode"] = "Passive"
    if "Active" not in applied.columns:
        applied["Active"] = True
    for column, default in (("fpj_ratio", 0.75), ("loss_percent", 15.0)):
        if column not in applied.columns:
            applied[column] = default
    active_mask = applied["Active"].map(_to_bool)
    applied.loc[active_mask, "Input Mode"] = mode
    if mode == JACKING_LOSS_INPUT_MODE:
        for column, default in (("fpj_ratio", 0.75), ("loss_percent", 15.0)):
            blank_mask = active_mask & applied[column].map(_is_blank)
            applied.loc[blank_mask, column] = default
    return applied


def _auto_prestress_layout_empty_table() -> pd.DataFrame:
    columns = [
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
        "Breaking Load_kN",
        "Duct Type",
        "Duct ID_mm",
        "Note",
    ]
    return pd.DataFrame(columns=columns)


def _auto_layout_product_diameter_mm(product: str, prestress_db: pd.DataFrame) -> float | None:
    tendon_product = get_tendon_product(product)
    if tendon_product is not None:
        return equivalent_steel_diameter_mm(tendon_product.tendon_area_mm2)
    database_row = _product_row(product, prestress_db)
    if database_row is None:
        return None
    diameter = _to_float(database_row.get("diameter_mm"))
    if diameter is not None and diameter > 0.0:
        return diameter
    area = _to_float(database_row.get("area_mm2"))
    return equivalent_steel_diameter_mm(area) if area is not None and area > 0.0 else None


def generate_auto_perimeter_prestress_layout(
    geometry: SectionGeometry | None,
    prestress_db: pd.DataFrame,
    *,
    product: str,
    edge_offset_mm: float = 75.0,
    target_spacing_mm: float = 150.0,
    min_elements: int = 4,
    label_prefix: str = "PS-AUTO-",
    input_mode: str = "Passive",
    bonded: bool = True,
) -> AutoPrestressLayoutResult:
    """Generate section-level prestress rows along the inward offset perimeter."""

    empty_table = _auto_prestress_layout_empty_table()
    product_label = "" if _is_blank(product) else str(product).strip()
    mode = _normalize_input_mode_label(input_mode)
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if not product_label or product_label == "Custom":
        return AutoPrestressLayoutResult(
            table=empty_table,
            errors=("Select a catalog prestress product before generating an auto perimeter prestress layout.",),
        )
    if mode not in INPUT_MODE_OPTIONS:
        return AutoPrestressLayoutResult(
            table=empty_table,
            errors=(f"Prestress input mode must be one of {', '.join(INPUT_MODE_OPTIONS)}.",),
        )
    diameter_mm = _auto_layout_product_diameter_mm(product_label, prestress_db)
    if diameter_mm is None or diameter_mm <= 0.0:
        return AutoPrestressLayoutResult(
            table=empty_table,
            errors=(f"Could not resolve a positive equivalent diameter for product '{product_label}'.",),
        )

    perimeter_result = generate_perimeter_rebar_layout(
        geometry,
        bar_size=product_label,
        diameter_mm=float(diameter_mm),
        material="Prestress",
        edge_offset_mm=float(edge_offset_mm),
        target_spacing_mm=float(target_spacing_mm),
        min_bars=int(min_elements),
        label_prefix="PS",
    )
    if perimeter_result.errors:
        return AutoPrestressLayoutResult(
            table=empty_table,
            errors=tuple(perimeter_result.errors),
            warnings=tuple(perimeter_result.warnings),
            info=tuple(perimeter_result.info),
            perimeter_length_mm=perimeter_result.perimeter_length_mm,
            actual_spacing_mm=perimeter_result.actual_spacing_mm,
        )

    prefix = str(label_prefix or "PS-AUTO-").strip() or "PS-AUTO-"
    rows: list[dict[str, Any]] = []
    for index, source_row in enumerate(perimeter_result.table.to_dict(orient="records"), start=1):
        row = _blank_prestress_row(f"{prefix}{index:02d}")
        row.update(
            {
                "Active": True,
                "Product": product_label,
                "x_mm": source_row.get("x_mm"),
                "y_mm": source_row.get("y_mm"),
                "Input Mode": mode,
                "Bonded": bool(bonded),
                "Count": 1,
                "Note": (
                    f"Auto perimeter prestress: offset={edge_offset_mm:g} mm, target spacing={target_spacing_mm:g} mm, "
                    f"product={product_label}, mode={mode}. Review cover, spacing, ducts, anchorage, and detailing before final design."
                ),
            }
        )
        rows.append(row)

    normalized = normalize_prestress_table_for_effective_input_sync(pd.DataFrame(rows, columns=empty_table.columns), prestress_db)
    info.extend(perimeter_result.info)
    info.append(
        f"Generated {len(normalized.index):,} prestress row(s) along an inward offset perimeter; no manual rows are changed until Apply is pressed."
    )
    warnings.extend(perimeter_result.warnings)
    if get_tendon_product(product_label) is not None:
        warnings.append(
            "Tendon-group auto layout places one tendon group at each generated point; duct spacing, anchorage zones, and constructability require engineering review."
        )
    return AutoPrestressLayoutResult(
        table=normalized,
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(info),
        perimeter_length_mm=perimeter_result.perimeter_length_mm,
        actual_spacing_mm=perimeter_result.actual_spacing_mm,
    )


def _prestress_table_for_editor(table: pd.DataFrame) -> pd.DataFrame:
    """Create a display-only editor copy with compact input-mode labels.

    The backing table intentionally stores compact canonical values
    (Passive/Pe_eff/fpe) so analysis, project I/O, and tests remain stable.
    Detailed explanations stay in guide cards and tooltips so table cells stay
    readable.
    """

    editor_table = pd.DataFrame(table).copy()
    if "Input Mode" in editor_table.columns:
        editor_table["Input Mode"] = editor_table["Input Mode"].map(_input_mode_display_label)
    return editor_table


def _effective_prestress_columns() -> list[str]:
    return ["Input Mode", "Pe_eff_kN", "fpe_MPa", "fpj_ratio", "loss_percent"]


def _product_row(product: str, prestress_db: pd.DataFrame) -> pd.Series | None:
    if _is_blank(product) or product == "Custom":
        return None
    matches = prestress_db.loc[prestress_db["name"] == product]
    if matches.empty:
        return None
    return matches.iloc[0]


def _blank_prestress_row(label: str = "PS") -> dict[str, Any]:
    return {
        "Active": True,
        "Label": label,
        "Steel Type": "custom",
        "Product": "Custom",
        "x_mm": 0.0,
        "y_mm": 0.0,
        "Area_mm2": None,
        "Diameter_mm": None,
        "Eq Steel Dia_mm": None,
        "fpy_MPa": None,
        "fpu_MPa": DEFAULT_STRAND_FPU_MPA,
        "Ep_MPa": DEFAULT_STRAND_EP_MPA,
        "Input Mode": "Passive",
        "Pe_eff_kN": 0.0,
        "fpe_MPa": 0.0,
        "fpj_ratio": 0.75,
        "loss_percent": 15.0,
        "Bonded": True,
        "Count": 1,
        "Strand Count": None,
        "Breaking Load_kN": None,
        "Duct Type": "",
        "Duct ID_mm": None,
        "Note": "",
    }


def _append_prestress_row(table: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    table_columns = list(table.columns)
    row_columns = [column for column in row if column not in table_columns]
    columns = [*table_columns, *row_columns]
    if table.empty:
        return pd.DataFrame([row], columns=columns)
    expanded = table.copy()
    for column in row_columns:
        expanded[column] = None
    return pd.concat([expanded, pd.DataFrame([row], columns=columns)], ignore_index=True)


def _tendon_6n_count_from_label(label: Any) -> int | None:
    """Return the strand count for Tendon 6-n labels used in product sorting.

    This UI helper intentionally accepts both the current display label
    (``Tendon 6-12``) and the legacy project label (``6-12``). Keeping this
    local parser avoids exposing database internals while still letting the
    Product dropdown present the full tendon catalog in a predictable
    engineering order.
    """

    text = str(label or "").strip()
    if not text:
        return None
    if text.lower().startswith("tendon "):
        text = text.split(None, 1)[1].strip()
    if not text.startswith("6-"):
        return None
    try:
        count = int(text.split("-", 1)[1])
    except (TypeError, ValueError):
        return None
    return count if 1 <= count <= 55 else None


def _canonical_product_option_label(product: Any) -> str:
    """Return the dropdown label to show for a product value.

    Legacy tendon labels are migrated to ``Tendon 6-n`` in the editor options,
    while non-tendon database labels and user custom labels are preserved.
    """

    if _is_blank(product):
        return ""
    label = str(product).strip()
    if _tendon_6n_count_from_label(label) is not None:
        return tendon_product_display_label(label)
    return label


def _product_option_sort_key(label: str) -> tuple[int, int, str]:
    """Sort Product options by engineering use rather than raw insertion order."""

    if label == "":
        return (0, 0, label)
    if label == "Custom":
        return (1, 0, label)
    tendon_count = _tendon_6n_count_from_label(label)
    if tendon_count is not None:
        return (2, tendon_count, label)
    lowered = label.lower()
    if "strand" in lowered:
        return (3, 0, label)
    if "bar" in lowered:
        return (4, 0, label)
    return (5, 0, label)


def _product_options_for_table(prestress_db: pd.DataFrame, prestress_table: pd.DataFrame | None) -> list[str]:
    """Build Product dropdown options with stable ordering and legacy support.

    The dropdown should be fast to scan: blank/custom first, then the complete
    standard ``Tendon 6-1`` to ``Tendon 6-55`` catalog, then strand/bar database
    products, then any current custom labels. Legacy labels such as ``6-12``
    are not shown as duplicate choices; they are displayed as ``Tendon 6-12``
    and normalized by the existing product-sync logic.
    """

    options: list[str] = ["", "Custom"]
    options.extend(tendon_product_options())
    if "name" in prestress_db.columns:
        options.extend(_canonical_product_option_label(name) for name in prestress_db["name"].tolist() if not _is_blank(name))
    if prestress_table is not None and "Product" in prestress_table.columns:
        options.extend(_canonical_product_option_label(product) for product in prestress_table["Product"].tolist() if not _is_blank(product))
    unique = list(dict.fromkeys(option for option in options if option is not None))
    return sorted(unique, key=_product_option_sort_key)


def _custom_tendon_product_from_label(product: str, row: pd.Series | None = None) -> TendonProduct | None:
    label = str(product).strip()
    parse_label = label.split(None, 1)[1].strip() if label.lower().startswith("tendon ") else label
    if not parse_label.startswith("6-"):
        return None
    try:
        strand_count = int(parse_label.split("-", 1)[1])
    except (TypeError, ValueError):
        return None
    if strand_count < 1:
        return None
    duct_id = _to_float(row.get("Duct ID_mm")) if row is not None else None
    duct_type = None if row is None or _is_blank(row.get("Duct Type")) else str(row.get("Duct Type")).strip()
    return make_custom_tendon_product(strand_count, label=label, duct_id_mm=duct_id, duct_type=duct_type)


def _apply_database_product_to_display_row(normalized: pd.DataFrame, index: Any, database_row: pd.Series) -> None:
    normalized.at[index, "Steel Type"] = str(database_row["type"])
    normalized.at[index, "Area_mm2"] = float(database_row["area_mm2"])
    normalized.at[index, "Diameter_mm"] = None if pd.isna(database_row["diameter_mm"]) else float(database_row["diameter_mm"])
    normalized.at[index, "Eq Steel Dia_mm"] = None
    normalized.at[index, "fpy_MPa"] = None if pd.isna(database_row["fpy_MPa"]) else float(database_row["fpy_MPa"])
    normalized.at[index, "fpu_MPa"] = None if pd.isna(database_row["fpu_MPa"]) else float(database_row["fpu_MPa"])
    normalized.at[index, "Ep_MPa"] = float(database_row["Ep_MPa"])
    normalized.at[index, "Strand Count"] = None
    normalized.at[index, "Strand Diameter_mm"] = None
    normalized.at[index, "Strand Area_mm2"] = None
    normalized.at[index, "Breaking Load_kN"] = None
    normalized.at[index, "Duct Type"] = ""
    normalized.at[index, "Duct ID_mm"] = None


def _looks_like_15_2mm_tendon_group(row: pd.Series) -> bool:
    steel_type = "" if _is_blank(row.get("Steel Type")) else str(row.get("Steel Type")).strip()
    if steel_type != "tendon_group":
        return False
    product = "" if _is_blank(row.get("Product")) else str(row.get("Product")).strip()
    if get_tendon_product(product) is not None or is_tendon_6n_label(product):
        return True
    strand_count = _to_float(row.get("Strand Count"))
    strand_diameter = _to_float(row.get("Strand Diameter_mm"))
    if strand_count is None:
        return False
    return strand_diameter is None or abs(strand_diameter - DEFAULT_STRAND_DIAMETER_MM) < 1e-6


def _sync_effective_inputs_for_row(normalized: pd.DataFrame, index: Any) -> None:
    mode = _normalize_input_mode_label(normalized.at[index, "Input Mode"] if "Input Mode" in normalized.columns else "Passive")
    if mode not in INPUT_MODE_OPTIONS and mode not in LEGACY_INPUT_MODE_OPTIONS:
        return
    if mode in INPUT_MODE_OPTIONS:
        normalized.at[index, "Input Mode"] = mode
    area_mm2 = _to_float(normalized.at[index, "Area_mm2"] if "Area_mm2" in normalized.columns else None)
    pe_kn = _pe_eff_kn_from_row(normalized.loc[index])
    fpe_mpa = _to_float(normalized.at[index, "fpe_MPa"] if "fpe_MPa" in normalized.columns else None)

    if mode == "Passive":
        normalized.at[index, "Pe_eff_kN"] = 0.0
        normalized.at[index, "fpe_MPa"] = 0.0
        return

    if mode == "Pe_eff":
        pe_kn = pe_kn if pe_kn is not None else 0.0
        normalized.at[index, "Pe_eff_kN"] = pe_kn
        normalized.at[index, "fpe_MPa"] = (pe_kn * 1000.0 / area_mm2) if area_mm2 and area_mm2 > 0 else None
        return

    if mode == "fpe":
        fpe_mpa = fpe_mpa if fpe_mpa is not None else 0.0
        normalized.at[index, "fpe_MPa"] = fpe_mpa
        normalized.at[index, "Pe_eff_kN"] = (area_mm2 * fpe_mpa / 1000.0) if area_mm2 and area_mm2 > 0 else None
        return

    if mode == JACKING_LOSS_INPUT_MODE:
        fpu_mpa = _to_float(normalized.at[index, "fpu_MPa"] if "fpu_MPa" in normalized.columns else None)
        fpj_ratio = _to_float(normalized.at[index, "fpj_ratio"] if "fpj_ratio" in normalized.columns else None)
        loss_percent = _to_float(normalized.at[index, "loss_percent"] if "loss_percent" in normalized.columns else None)
        fpj_ratio = 0.75 if fpj_ratio is None else fpj_ratio
        loss_percent = 15.0 if loss_percent is None else loss_percent
        normalized.at[index, "fpj_ratio"] = fpj_ratio
        normalized.at[index, "loss_percent"] = loss_percent
        if area_mm2 and area_mm2 > 0 and fpu_mpa and fpu_mpa > 0 and fpj_ratio >= 0.0 and 0.0 <= loss_percent <= 100.0:
            fpe_mpa = fpj_ratio * fpu_mpa * (1.0 - loss_percent / 100.0)
            normalized.at[index, "fpe_MPa"] = fpe_mpa
            normalized.at[index, "Pe_eff_kN"] = area_mm2 * fpe_mpa / 1000.0
        else:
            normalized.at[index, "fpe_MPa"] = None
            normalized.at[index, "Pe_eff_kN"] = None


def _normalize_prestress_table_for_display(table: pd.DataFrame, prestress_db: pd.DataFrame | None = None) -> pd.DataFrame:
    normalized = pd.DataFrame(table).copy()
    if normalized.empty:
        return normalized
    for column in (
        "Diameter_mm",
        "fpy_MPa",
        "fpu_MPa",
        "Ep_MPa",
        "Input Mode",
        "Pe_eff_kN",
        "fpe_MPa",
        "fpj_ratio",
        "loss_percent",
        "Strand Count",
        "Strand Diameter_mm",
        "Strand Area_mm2",
        "Breaking Load_kN",
        "Duct Type",
        "Duct ID_mm",
        "Count",
        "Note",
    ):
        if column not in normalized.columns:
            normalized[column] = None
    if "Pe_eff_kN" in normalized.columns and "Pe_eff" in normalized.columns:
        missing_pe = normalized["Pe_eff_kN"].map(_is_blank)
        normalized.loc[missing_pe, "Pe_eff_kN"] = normalized.loc[missing_pe, "Pe_eff"]
    normalized["Diameter_mm"] = normalized["Diameter_mm"].astype("object")
    if "Eq Steel Dia_mm" not in normalized.columns:
        insert_at = normalized.columns.get_loc("Diameter_mm") + 1 if "Diameter_mm" in normalized.columns else len(normalized.columns)
        normalized.insert(insert_at, "Eq Steel Dia_mm", None)
    for index, row in normalized.iterrows():
        normalized.at[index, "Input Mode"] = _normalize_input_mode_label(row.get("Input Mode"))
        count = _to_count(row.get("Count"))
        normalized.at[index, "Count"] = 1 if count is None else count
        normalized.at[index, "Note"] = "" if _is_blank(row.get("Note")) else str(row.get("Note")).strip()
        product = "" if _is_blank(row.get("Product")) else str(row.get("Product")).strip()
        tendon_product = get_tendon_product(product) or _custom_tendon_product_from_label(product, row)
        database_row = _product_row(product, prestress_db) if prestress_db is not None else None
        is_tendon_group = str(row.get("Steel Type") or "").strip() == "tendon_group" or tendon_product is not None
        if is_tendon_group:
            normalized.at[index, "Steel Type"] = "tendon_group"
            normalized.at[index, "Diameter_mm"] = None
            if tendon_product is not None:
                normalized.at[index, "Product"] = tendon_product.label
                normalized.at[index, "Area_mm2"] = tendon_product.tendon_area_mm2
                normalized.at[index, "fpy_MPa"] = tendon_product.fpy_MPa
                normalized.at[index, "fpu_MPa"] = tendon_product.fpu_MPa
                normalized.at[index, "Ep_MPa"] = tendon_product.Ep_MPa
                normalized.at[index, "Strand Count"] = tendon_product.strand_count
                normalized.at[index, "Strand Diameter_mm"] = tendon_product.strand_diameter_mm
                normalized.at[index, "Strand Area_mm2"] = tendon_product.strand_area_mm2
                normalized.at[index, "Breaking Load_kN"] = tendon_product.breaking_load_kN
                normalized.at[index, "Duct Type"] = tendon_product.duct_type or ""
                normalized.at[index, "Duct ID_mm"] = tendon_product.duct_id_mm
            elif _looks_like_15_2mm_tendon_group(normalized.loc[index]):
                if _is_blank(normalized.at[index, "fpy_MPa"]):
                    normalized.at[index, "fpy_MPa"] = DEFAULT_STRAND_FPY_MPA
                if _is_blank(normalized.at[index, "fpu_MPa"]):
                    normalized.at[index, "fpu_MPa"] = DEFAULT_STRAND_FPU_MPA
                if _is_blank(normalized.at[index, "Ep_MPa"]):
                    normalized.at[index, "Ep_MPa"] = DEFAULT_STRAND_EP_MPA
        elif database_row is not None:
            _apply_database_product_to_display_row(normalized, index, database_row)
        area_mm2 = _to_float(normalized.at[index, "Area_mm2"] if "Area_mm2" in normalized.columns else None)
        normalized.at[index, "Eq Steel Dia_mm"] = equivalent_steel_diameter_mm(area_mm2) if is_tendon_group else None
        _sync_effective_inputs_for_row(normalized, index)
    return normalized


def normalize_prestress_table_for_effective_input_sync(table: pd.DataFrame, prestress_db: pd.DataFrame) -> pd.DataFrame:
    """Synchronize product defaults and effective prestress display fields.

    Product data controls area/material reference values. Input Mode controls
    only the dependent Pe_eff/fpe display value. Jacking + Total Loss % derives
    Pe_eff from fpu, area, fpj_ratio, and loss_percent; it never derives
    prestress from product breaking load.
    """

    return _normalize_prestress_table_for_display(table, prestress_db)




def _compact_column_order_for_table(table: pd.DataFrame) -> list[str]:
    """Return visible editor columns without dropping hidden engineering data.

    Streamlit's ``column_order`` is used only to keep the Advanced Prestress
    editor readable. The backing session-state table still carries the full
    prestress product/material metadata required by product sync, validation,
    analysis, report export, and section preview.
    """

    available = set(pd.DataFrame(table).columns)
    return [column for column in PRESTRESS_COMPACT_EDITOR_COLUMNS if column in available]


def _prestress_reference_detail_dataframe(table: pd.DataFrame) -> pd.DataFrame:
    """Build a read-only detail view for product/material reference columns."""

    detail = pd.DataFrame(table).copy()
    if detail.empty:
        return detail
    columns = [column for column in PRESTRESS_REFERENCE_DETAIL_COLUMNS if column in detail.columns]
    return detail.loc[:, columns]


def _section_bottom_y_from_geometry(geometry: SectionGeometry | None) -> float:
    """Return section bottom y-coordinate in the geometry coordinate system."""

    if geometry is None:
        return 0.0
    try:
        polygon = to_shapely_polygon(geometry)
        return float(polygon.bounds[1])
    except Exception:
        return 0.0


def _area_weighted_prestress_y_from_bottom(elements: list[PrestressElement], geometry: SectionGeometry | None) -> float | None:
    """Return tendon centroid by steel area for stage-force state defaults.

    This helper intentionally uses tendon geometry/area only. It does not infer
    transfer or effective prestress force from product breaking load, duct ID,
    or strand-count metadata.
    """

    bottom_y = _section_bottom_y_from_geometry(geometry)
    total_area = 0.0
    weighted_y = 0.0
    for element in elements:
        if not element.bonded:
            continue
        try:
            area = float(element.total_area_mm2)
            y_from_bottom = float(element.y_mm) - bottom_y
        except (TypeError, ValueError):
            continue
        if area <= 0.0:
            continue
        total_area += area
        weighted_y += area * y_from_bottom
    if total_area <= 0.0:
        return None
    return weighted_y / total_area


def _total_effective_prestress_from_elements_kN(elements: list[PrestressElement]) -> float:
    """Return total final effective prestress from valid elements only."""

    total_pe_n = 0.0
    for element in elements:
        if not element.bonded:
            continue
        try:
            pe_n = float(element.pe_eff_n or 0.0) * int(element.count or 1)
        except (TypeError, ValueError):
            continue
        if pe_n > 0.0:
            total_pe_n += pe_n
    return total_pe_n / 1000.0


def _force_state_existing_rows_by_stage(table: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if table is None:
        return {}
    df = pd.DataFrame(table)
    if df.empty or "Check Stage" not in df.columns:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        stage = "" if _is_blank(row.get("Check Stage")) else str(row.get("Check Stage")).strip()
        if stage:
            rows[stage] = row.to_dict()
    return rows


def _normalize_girder_prestress_force_state_table(
    table: pd.DataFrame | None,
    elements: list[PrestressElement],
    geometry: SectionGeometry | None,
) -> pd.DataFrame:
    """Return the fixed three-stage girder prestress force-state table.

    GIRDER.PS2A keeps these values as engineer-controlled stage forces. It
    does not perform prestress-loss calculation and does not modify PMM
    prestress elements.
    """

    existing = _force_state_existing_rows_by_stage(table)
    y_default = _area_weighted_prestress_y_from_bottom(elements, geometry)
    if y_default is None:
        y_default = 0.0
    final_pe_default = _total_effective_prestress_from_elements_kN(elements)
    rows: list[dict[str, Any]] = []
    for stage, force_state, note in GIRDER_PRESTRESS_FORCE_STATE_SPECS:
        current = existing.get(stage, {})
        pe_default = final_pe_default if stage == "Service stage" else 0.0
        pe_value = _to_float(current.get("Pe_kN"))
        y_value = _to_float(current.get("yps_mm_from_bottom"))
        rows.append(
            {
                "Check Stage": stage,
                "Prestress State": force_state,
                "Pe_kN": pe_default if pe_value is None else pe_value,
                "yps_mm_from_bottom": y_default if y_value is None else y_value,
                "Note": note if _is_blank(current.get("Note")) else str(current.get("Note")).strip(),
            }
        )
    return pd.DataFrame(rows, columns=GIRDER_PRESTRESS_FORCE_STATE_COLUMNS)


def _render_girder_prestress_force_state_inputs(
    elements: list[PrestressElement],
    geometry: SectionGeometry | None,
) -> None:
    """Render engineer-controlled prestress force states for girder SLS stages."""

    st.markdown("#### Girder SLS Prestress Force States")
    st.markdown(
        '<div class="cpmm-prestress-table-note">'
        "Define the internal prestress force to use for each girder SLS stage. "
        "These values are not external loads and must not be entered again in Loads. "
        "No automatic loss calculation is performed in this milestone; Pe values are engineer-controlled."
        "</div>",
        unsafe_allow_html=True,
    )
    current = st.session_state.get("girder_prestress_force_states_table")
    table = _normalize_girder_prestress_force_state_table(pd.DataFrame(current) if current is not None else None, elements, geometry)
    edited = st.data_editor(
        table,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_order=GIRDER_PRESTRESS_FORCE_STATE_COLUMNS,
        column_config={
            "Check Stage": st.column_config.TextColumn("Check Stage", disabled=True),
            "Prestress State": st.column_config.TextColumn("Prestress State", disabled=True),
            "Pe_kN": st.column_config.NumberColumn(
                "Pe_kN (compression +)",
                min_value=0.0,
                step=100.0,
                format="%.3f",
                help="Stage prestress force to use in Analysis. Use Pe_transfer/P_release for transfer, Pe_construction for construction, and Pe_eff_final for final service.",
            ),
            "yps_mm_from_bottom": st.column_config.NumberColumn(
                "yps from bottom (mm)",
                step=10.0,
                format="%.3f",
                help="Prestress centroid measured upward from the selected section-basis bottom fiber.",
            ),
            "Note": st.column_config.TextColumn("Note"),
        },
        key="girder_prestress_force_states_editor",
    )
    normalized = _normalize_girder_prestress_force_state_table(edited, elements, geometry)
    st.session_state["girder_prestress_force_states_table"] = normalized
    positive_states = normalized.loc[pd.to_numeric(normalized["Pe_kN"], errors="coerce").fillna(0.0).gt(0.0)]
    ready_count = len(positive_states)
    st.caption(
        f"{ready_count} stage prestress force state(s) have positive Pe. Analysis will auto-enable prestress for stages with positive Pe."
    )



def _default_pjack_per_strand_kn(strand_size: Any) -> float:
    props = _strand_size_properties(strand_size)
    return 0.75 * float(props.get("fpu_mpa", DEFAULT_STRAND_FPU_MPA)) * float(props.get("area_mm2", DEFAULT_STRAND_AREA_MM2)) / 1000.0


def _safe_loss_percent(reference: float, current: float) -> float:
    if reference <= 1e-9:
        return 0.0
    return (1.0 - current / reference) * 100.0


def _loss_force_state_existing_rows_by_group(table: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if table is None:
        return {}
    df = pd.DataFrame(table)
    if df.empty or "Group ID" not in df.columns:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        group = "" if _is_blank(row.get("Group ID")) else str(row.get("Group ID")).strip()
        if group:
            rows[group] = row.to_dict()
    return rows


def _girder_force_state_qa_status(pjack: float, pe_transfer: float, pe_construction: float, pe_final: float) -> tuple[str, str]:
    if pjack <= 1e-9:
        return "REVIEW", "Pjack is required."
    if pe_transfer <= 1e-9 or pe_final <= 1e-9:
        return "REVIEW", "Transfer/final Pe must be positive before SLS stress use."
    if pe_transfer - pjack > 1e-6:
        return "REVIEW", "Pe_transfer exceeds Pjack."
    if pe_construction - pe_transfer > 1e-6:
        return "REVIEW", "Pe_construction exceeds Pe_transfer."
    if pe_final - pe_construction > 1e-6:
        return "REVIEW", "Pe_final exceeds Pe_construction."
    total_loss = _safe_loss_percent(pjack, pe_final)
    if total_loss < -1e-6:
        return "REVIEW", "Total loss is negative."
    if total_loss > 45.0:
        return "REVIEW", "Total loss exceeds 45%; verify force states."
    if total_loss < 5.0:
        return "REVIEW", "Total loss is below 5%; verify if this is intentional."
    return "OK", "Manual/advisory force state order is consistent."


def _normalize_girder_loss_force_state_table(
    table: pd.DataFrame | None,
    strand_table: pd.DataFrame | None,
    mode: str = "Manual stage Pe",
) -> pd.DataFrame:
    """Return GIRDER.LOSS1A manual/percentage force-state rows per strand group.

    LOSS1A is a stage-force workflow only.  It does not calculate AASHTO/ACI
    prestress losses, transfer-length force build-up, development, shear, or
    end-zone reinforcement.  Values can be applied back to the strand layout
    table for downstream SLS previews.
    """

    existing = _loss_force_state_existing_rows_by_group(table)
    active = _active_girder_strand_layout_rows(strand_table if strand_table is not None else pd.DataFrame())
    rows: list[dict[str, Any]] = []
    for _, row in active.iterrows():
        group = str(row.get("Group ID") or "strand group")
        current = existing.get(group, {})
        count = int(_to_float(row.get("No. Strands")) or 0)
        pe_transfer_seed = float(_to_float(row.get("Pe_transfer/strand_kN")) or 0.0)
        pe_construction_seed = float(_to_float(row.get("Pe_construction/strand_kN")) or 0.0)
        pe_final_seed = float(_to_float(row.get("Pe_eff_final/strand_kN")) or 0.0)
        pjack_default = max(
            _default_pjack_per_strand_kn(row.get("Strand Size")),
            pe_transfer_seed,
            pe_construction_seed,
            pe_final_seed,
        )
        pjack = float(_to_float(current.get("Pjack/strand_kN")) or pjack_default)
        pe_transfer = float(_to_float(current.get("Pe_transfer/strand_kN")) or pe_transfer_seed)
        pe_construction = float(_to_float(current.get("Pe_construction/strand_kN")) or pe_construction_seed)
        pe_final = float(_to_float(current.get("Pe_eff_final/strand_kN")) or pe_final_seed)

        transfer_loss = _to_float(current.get("Transfer loss %"))
        construction_loss = _to_float(current.get("Construction loss %"))
        long_term_loss = _to_float(current.get("Long-term loss %"))
        if transfer_loss is None:
            transfer_loss = _safe_loss_percent(pjack, pe_transfer)
        if construction_loss is None:
            construction_loss = _safe_loss_percent(pe_transfer, pe_construction)
        if long_term_loss is None:
            long_term_loss = _safe_loss_percent(pe_construction, pe_final)

        if mode == "Percentage loss":
            transfer_loss = max(float(transfer_loss), 0.0)
            construction_loss = max(float(construction_loss), 0.0)
            long_term_loss = max(float(long_term_loss), 0.0)
            pe_transfer = max(pjack * (1.0 - transfer_loss / 100.0), 0.0)
            pe_construction = max(pe_transfer * (1.0 - construction_loss / 100.0), 0.0)
            pe_final = max(pe_construction * (1.0 - long_term_loss / 100.0), 0.0)
        else:
            transfer_loss = _safe_loss_percent(pjack, pe_transfer)
            construction_loss = _safe_loss_percent(pe_transfer, pe_construction)
            long_term_loss = _safe_loss_percent(pe_construction, pe_final)

        total_loss = _safe_loss_percent(pjack, pe_final)
        status, message = _girder_force_state_qa_status(pjack, pe_transfer, pe_construction, pe_final)
        note = "" if _is_blank(current.get("Note")) else str(current.get("Note")).strip()
        if not note:
            note = message
        rows.append(
            {
                "Active": bool(row.get("Active", True)),
                "Group ID": group,
                "No. strands": count,
                "Pjack/strand_kN": pjack,
                "Transfer loss %": float(transfer_loss),
                "Pe_transfer/strand_kN": pe_transfer,
                "Construction loss %": float(construction_loss),
                "Pe_construction/strand_kN": pe_construction,
                "Long-term loss %": float(long_term_loss),
                "Pe_eff_final/strand_kN": pe_final,
                "Total loss %": total_loss,
                "QA status": status,
                "Note": note,
            }
        )
    return pd.DataFrame(rows, columns=GIRDER_LOSS_FORCE_STATE_COLUMNS)



def _persist_girder_loss_force_state_table(normalized_table: pd.DataFrame) -> None:
    """Persist the normalized girder loss/force-state table without forcing a rerun."""

    st.session_state["girder_prestress_loss_force_state_table"] = pd.DataFrame(normalized_table).reset_index(drop=True)


def _sync_girder_loss_force_state_editor_to_table(strand_table: pd.DataFrame, mode: str) -> None:
    """Persist first data-editor edits for LOSS1A force states.

    Streamlit stores an ``edited_rows`` patch dict in session state during
    ``on_change``.  Reconstruct the force-state table from the canonical table
    and the patch so manual Pe edits and percentage-loss edits persist on the
    first edit, rather than requiring a second input.
    """

    edited = st.session_state.get("girder_prestress_loss_force_state_editor")
    current = st.session_state.get("girder_prestress_loss_force_state_table")
    fallback = (
        pd.DataFrame(current).reset_index(drop=True)
        if current is not None
        else _normalize_girder_loss_force_state_table(None, strand_table, mode=str(mode))
    )
    edited_df = _data_editor_payload_to_dataframe(edited, fallback)
    normalized = _normalize_girder_loss_force_state_table(edited_df, strand_table, mode=str(mode))
    _persist_girder_loss_force_state_table(normalized)
    st.session_state["girder_prestress_loss_force_state_apply_status"] = "Pending apply"


def _apply_girder_loss_force_states_to_strand_layout(strand_table: pd.DataFrame, force_table: pd.DataFrame) -> pd.DataFrame:
    updated = pd.DataFrame(strand_table).copy()
    if updated.empty or force_table is None or pd.DataFrame(force_table).empty:
        return updated
    force_by_group = _loss_force_state_existing_rows_by_group(pd.DataFrame(force_table))
    for idx, row in updated.iterrows():
        group = "" if _is_blank(row.get("Group ID")) else str(row.get("Group ID")).strip()
        state = force_by_group.get(group)
        if not state:
            continue
        for source, target in [
            ("Pe_transfer/strand_kN", "Pe_transfer/strand_kN"),
            ("Pe_construction/strand_kN", "Pe_construction/strand_kN"),
            ("Pe_eff_final/strand_kN", "Pe_eff_final/strand_kN"),
        ]:
            value = _to_float(state.get(source))
            if value is not None and value >= 0.0:
                updated.at[idx, target] = float(value)
    return updated


def _girder_loss_force_state_qa_summary(table: pd.DataFrame) -> tuple[str, list[str]]:
    df = pd.DataFrame(table)
    if df.empty:
        return "MISSING", ["No active strand rows are available for force-state definition."]
    messages: list[str] = []
    statuses = set(str(value) for value in df.get("QA status", pd.Series(dtype=str)).tolist())
    for _, row in df.iterrows():
        if str(row.get("QA status")) != "OK":
            group = str(row.get("Group ID") or "strand group")
            messages.append(f"{group}: {row.get('Note') or 'force state requires review.'}")
    return ("OK" if statuses == {"OK"} else "REVIEW"), messages




def _girder_force_states_match_strand_layout(strand_table: pd.DataFrame, force_table: pd.DataFrame) -> bool:
    """Return True when strand-layout Pe columns match current force-state rows."""

    strand = pd.DataFrame(strand_table)
    forces = pd.DataFrame(force_table)
    if strand.empty or forces.empty:
        return False
    force_by_group = _loss_force_state_existing_rows_by_group(forces)
    pe_columns = [
        "Pe_transfer/strand_kN",
        "Pe_construction/strand_kN",
        "Pe_eff_final/strand_kN",
    ]
    active = _active_girder_strand_layout_rows(strand)
    if active.empty:
        return False
    for _, row in active.iterrows():
        group = "" if _is_blank(row.get("Group ID")) else str(row.get("Group ID")).strip()
        state = force_by_group.get(group)
        if not state:
            return False
        for column in pe_columns:
            left = _to_float(row.get(column))
            right = _to_float(state.get(column))
            if left is None or right is None:
                return False
            if abs(float(left) - float(right)) > 1e-6:
                return False
    return True


def _stage_pe_mapping_metrics_from_table(table: pd.DataFrame, *, sls_feed_ready: bool | None = None) -> list[PrestressMetric]:
    """Return compact metrics for LOSS1B stage Pe mapping readiness."""

    mapping = girder_stage_pe_mapping_dataframe(table)
    metrics: list[PrestressMetric] = []
    status_by_stage = {str(row.get("Stage")): str(row.get("Status")) for _, row in mapping.iterrows()}
    total_by_stage = {str(row.get("Stage")): float(_to_float(row.get("Pe total kN")) or 0.0) for _, row in mapping.iterrows()}
    for stage, label in [
        ("Transfer", "Transfer Pe"),
        ("Construction", "Construction Pe"),
        ("Final service", "Service Pe"),
    ]:
        status = status_by_stage.get(stage, "MISSING")
        metric_status = "ready" if status == "READY" else ("review" if status == "REVIEW" else "danger")
        metrics.append(PrestressMetric(label, status, f"{total_by_stage.get(stage, 0.0):,.1f} kN", metric_status, strong=status == "READY"))
    if sls_feed_ready is not None:
        metrics.append(
            PrestressMetric(
                "SLS feed",
                "Ready" if sls_feed_ready else "Apply needed",
                "strand table Pe columns",
                "ready" if sls_feed_ready else "review",
                strong=sls_feed_ready,
            )
        )
    return metrics


def _render_stage_pe_mapping_audit(table: pd.DataFrame, *, expanded: bool = False) -> None:
    """Render LOSS1B stage Pe mapping audit table."""

    mapping = girder_stage_pe_mapping_dataframe(table)
    if mapping.empty:
        st.warning("No active girder strand groups are available for stage Pe mapping.")
        return
    with st.expander("Stage Pe mapping audit", expanded=expanded):
        st.dataframe(mapping, use_container_width=True, hide_index=True)
        st.caption(
            "LOSS1B only audits Pe source availability by stage. It does not perform AASHTO/ACI loss calculation, transfer-length ramping, or stress checks."
        )




def _girder_code_loss_settings_from_session() -> dict[str, Any]:
    settings = dict(st.session_state.get("girder_prestress_code_loss_settings", {}) or {})
    settings.setdefault("method", "Approximate code-based loss")
    concrete = st.session_state.get("concrete_material")
    fc_default = float(getattr(concrete, "fc_MPa", 45.0) or 45.0)
    settings.setdefault("fci_MPa", 0.8 * fc_default)
    settings.setdefault("humidity_percent", 70.0)
    settings.setdefault("relaxation_class", "Low relaxation")
    settings.setdefault("age_transfer_days", 1.0)
    settings.setdefault("age_deck_days", 30.0)
    settings.setdefault("final_age_days", 10000.0)
    settings.setdefault("refined_coefficient_source", REFINED_COEFFICIENT_SOURCE_AUTO)
    settings.setdefault("refined_coefficient_preset", DEFAULT_REFINED_COEFFICIENT_PRESET)
    settings.setdefault("vs_override_mm", 0.0)
    refined_defaults = REFINED_COEFFICIENT_PRESETS[DEFAULT_REFINED_COEFFICIENT_PRESET]
    settings.setdefault("Kid", refined_defaults["Kid"])
    settings.setdefault("Kdf", refined_defaults["Kdf"])
    settings.setdefault("eps_bid_microstrain", refined_defaults["eps_bid_microstrain"])
    settings.setdefault("eps_bdf_microstrain", refined_defaults["eps_bdf_microstrain"])
    settings.setdefault("psi_td_ti", refined_defaults["psi_td_ti"])
    settings.setdefault("psi_tf_ti", refined_defaults["psi_tf_ti"])
    settings.setdefault("psi_tf_td", refined_defaults["psi_tf_td"])
    settings.setdefault("delta_fcd_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)
    settings.setdefault("delta_fcdf_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)
    settings.setdefault("delta_fcd_MPa", refined_defaults["delta_fcd_MPa"])
    settings.setdefault("delta_fcdf_MPa", refined_defaults["delta_fcdf_MPa"])
    settings.setdefault("fpy_MPa", DEFAULT_STRAND_FPY_MPA)
    settings.setdefault("fpj_ratio", DEFAULT_CODE_LOSS_FPJ_RATIO)
    settings.setdefault("loss_code_basis", GIRDER_LOSS_BASIS_USE_PROJECT)
    return settings




def _effective_girder_loss_code_basis(settings: dict[str, Any]) -> str:
    """Return the actual code basis used by the loss workflow selector."""

    selected = str(settings.get("loss_code_basis", GIRDER_LOSS_BASIS_USE_PROJECT) or GIRDER_LOSS_BASIS_USE_PROJECT)
    if selected == GIRDER_LOSS_BASIS_USE_PROJECT:
        return workflow_project_design_code_from_session(st.session_state)
    if selected == GIRDER_LOSS_BASIS_ACI_PCI:
        return PROJECT_CODE_ACI318
    if selected == GIRDER_LOSS_BASIS_AASHTO:
        return PROJECT_CODE_AASHTO_LRFD
    return GIRDER_LOSS_BASIS_MANUAL


def _render_girder_loss_code_basis_selector(settings: dict[str, Any], *, method: str) -> tuple[dict[str, Any], str, bool]:
    """Render the local prestress-loss code-basis selector.

    The loss-basis selector is deliberately controlled by calculation basis,
    not by workflow alone.  ACI/PCI-style approximate loss can be used for
    Building projects by default and as a Bridge cross-check when explicitly
    selected; refined time-dependent loss remains AASHTO-only in the current
    implementation.
    """

    project_code = workflow_project_design_code_from_session(st.session_state)
    current = str(settings.get("loss_code_basis", GIRDER_LOSS_BASIS_USE_PROJECT) or GIRDER_LOSS_BASIS_USE_PROJECT)
    if current not in GIRDER_LOSS_CODE_BASIS_OPTIONS:
        current = GIRDER_LOSS_BASIS_USE_PROJECT
    selected = st.selectbox(
        "🟨 Prestress loss code basis",
        GIRDER_LOSS_CODE_BASIS_OPTIONS,
        index=GIRDER_LOSS_CODE_BASIS_OPTIONS.index(current),
        key="girder_prestress_loss_code_basis",
        help="Default inherits the Project Design Code from Setup. Override only when the project specification requires a different loss basis.",
    )
    settings["loss_code_basis"] = str(selected)
    effective_basis = _effective_girder_loss_code_basis(settings)
    if selected != GIRDER_LOSS_BASIS_USE_PROJECT and effective_basis != project_code:
        st.warning("Prestress loss basis differs from Project Design Code — Engineering review required.")
    approximate_mode = method == "Approximate code-based loss"
    if effective_basis == PROJECT_CODE_AASHTO_LRFD:
        st.info("AASHTO LRFD loss basis selected. Existing approximate/refined loss calculators remain engineering-preview workflows, not final code-certified loss design.")
        return settings, effective_basis, True
    if effective_basis == PROJECT_CODE_ACI318:
        if approximate_mode:
            st.info(
                "ACI 318 / PCI-style approximate loss basis selected. The app will use a separate PCI-style ES + CR + SH + RE preview; "
                "it is not the AASHTO approximate formula renamed as ACI."
            )
            return settings, effective_basis, True
        st.warning(
            "Refined time-dependent loss is currently AASHTO-only. Use Approximate code-based loss for ACI/PCI-style estimates, "
            "or enter reviewed force states manually."
        )
        return settings, effective_basis, False
    st.warning(
        "Manual / project-specific loss basis selected. Enter reviewed force states manually; calculate-and-use buttons are disabled for this basis."
    )
    return settings, effective_basis, False


def _apply_refined_coefficient_preset(
    settings: dict[str, Any],
    preset_name: str,
    *,
    sync_widget_state: bool = False,
) -> dict[str, Any]:
    """Apply LOSS3A.2 refined coefficient preset values to settings.

    Presets are starting values for the manual-coefficient refined workflow,
    not automatic AASHTO coefficient prediction.
    """

    if preset_name not in REFINED_COEFFICIENT_PRESETS:
        settings["refined_coefficient_preset"] = REFINED_COEFFICIENT_USER_DEFINED
        return settings
    settings["refined_coefficient_preset"] = preset_name
    for key, value in REFINED_COEFFICIENT_PRESETS[preset_name].items():
        settings[key] = float(value)
        widget_key = REFINED_PRESET_WIDGET_KEYS.get(key)
        if sync_widget_state and widget_key:
            st.session_state[widget_key] = float(value)
    return settings


def _refined_coefficient_review_messages(settings: dict[str, Any]) -> list[str]:
    """Return practical REVIEW messages for LOSS3A refined manual coefficients."""

    messages: list[str] = []
    eps_total = float(settings.get("eps_bid_microstrain", 0.0) or 0.0) + float(settings.get("eps_bdf_microstrain", 0.0) or 0.0)
    if eps_total > 250.0:
        messages.append("Shrinkage strain sum exceeds 250 microstrain; review humidity, V/S, concrete age, and project-specific shrinkage assumptions.")
    if float(settings.get("psi_tf_ti", 0.0) or 0.0) > 2.5:
        messages.append("Ψb(tf,ti) exceeds 2.5; review creep coefficient source before relying on refined loss results.")
    if float(settings.get("Kid", 0.0) or 0.0) > 1.0 or float(settings.get("Kdf", 0.0) or 0.0) > 1.0:
        messages.append("Kid/Kdf above 1.0 may amplify losses; verify transformed-section interaction coefficients.")
    if str(settings.get("delta_fcd_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)) != REFINED_STRESS_EFFECT_MANUAL:
        messages.append("Δfcd is not included or is marked future-auto; staged SDL/deck stress effect is 0.00 MPa in this preview.")
    if str(settings.get("delta_fcdf_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)) != REFINED_STRESS_EFFECT_MANUAL:
        messages.append("Δfcdf is not included or is marked future-auto; deck shrinkage interaction stress effect is 0.00 MPa in this preview.")
    humidity = float(settings.get("humidity_percent", 0.0) or 0.0)
    if humidity < 40.0 or humidity > 100.0:
        messages.append("Preset RH basis is outside 40%–100%; use project/site mean relative humidity.")
    return messages


def _refined_coefficient_preset_dataframe() -> pd.DataFrame:
    rows = []
    for name, values in REFINED_COEFFICIENT_PRESETS.items():
        rows.append(
            {
                "Preset": name,
                "RH basis %": values["humidity_percent"],
                "Kid": values["Kid"],
                "Kdf": values["Kdf"],
                "εbid με": values["eps_bid_microstrain"],
                "εbdf με": values["eps_bdf_microstrain"],
                "Ψb(td,ti)": values["psi_td_ti"],
                "Ψb(tf,ti)": values["psi_tf_ti"],
                "Ψb(tf,td)": values["psi_tf_td"],
                "Use case": "Typical Thailand/high RH" if "Thailand" in name else ("Moderate RH" if "Moderate" in name else "Dry/conservative check"),
            }
        )
    return pd.DataFrame(rows)






def _refined_stress_effect_source_status(source: str) -> tuple[str, str]:
    if source == REFINED_STRESS_EFFECT_MANUAL:
        return "Manual", "READY"
    if source == REFINED_STRESS_EFFECT_AUTO_FUTURE:
        return "Future auto", "REVIEW"
    return "Not included", "REVIEW"


def _refined_stress_effect_input_dataframe(settings: dict[str, Any]) -> pd.DataFrame:
    fcd_source = str(settings.get("delta_fcd_source", REFINED_STRESS_EFFECT_NOT_INCLUDED))
    fcdf_source = str(settings.get("delta_fcdf_source", REFINED_STRESS_EFFECT_NOT_INCLUDED))
    fcd_src, fcd_status = _refined_stress_effect_source_status(fcd_source)
    fcdf_src, fcdf_status = _refined_stress_effect_source_status(fcdf_source)
    return pd.DataFrame(
        [
            {
                "Effect": "Δfcd",
                "Value MPa": float(settings.get("delta_fcd_MPa", 0.0) or 0.0),
                "Source": fcd_src,
                "Status": fcd_status,
                "Engineering note": "Concrete stress change at prestress centroid from SDL/deck-stage effects after deck placement.",
            },
            {
                "Effect": "Δfcdf",
                "Value MPa": float(settings.get("delta_fcdf_MPa", 0.0) or 0.0),
                "Source": fcdf_src,
                "Status": fcdf_status,
                "Engineering note": "Deck slab shrinkage interaction stress effect at prestress centroid.",
            },
        ]
    )


def _render_refined_deck_sdl_stress_effect_inputs(settings: dict[str, Any], *, key_prefix: str) -> dict[str, Any]:
    """Render guided Δfcd/Δfcdf source selectors for LOSS3B.2.

    These values are deliberately not silently estimated in LOSS3B because
    they require staged load/composite stress effects.  The default 0.0 MPa
    represents not included / preliminary review, not a final recommendation.
    """

    st.markdown("###### Deck / SDL stress effects")
    st.caption(
        "Δfcd and Δfcdf are refined AASHTO stress-effect terms at the prestress centroid. "
        "Use 0.00 MPa only when these effects are intentionally not included in the current preview."
    )
    source_cols = st.columns(2)
    with source_cols[0]:
        current = str(settings.get("delta_fcd_source", REFINED_STRESS_EFFECT_NOT_INCLUDED))
        if current not in REFINED_STRESS_EFFECT_SOURCE_OPTIONS:
            current = REFINED_STRESS_EFFECT_NOT_INCLUDED
        settings["delta_fcd_source"] = st.selectbox(
            "🟨 Δfcd source",
            REFINED_STRESS_EFFECT_SOURCE_OPTIONS,
            index=REFINED_STRESS_EFFECT_SOURCE_OPTIONS.index(current),
            key=f"{key_prefix}_delta_fcd_source",
            help="Δfcd is concrete stress change at the prestress centroid from superimposed dead/deck-stage load effects after deck placement.",
        )
        if settings["delta_fcd_source"] == REFINED_STRESS_EFFECT_MANUAL:
            settings["delta_fcd_MPa"] = st.number_input(
                "🟨 Δfcd (MPa)",
                min_value=0.0,
                step=0.1,
                value=float(settings.get("delta_fcd_MPa", 0.0) or 0.0),
                format="%.3f",
                key=f"{key_prefix}_delta_fcd_value",
                help="Use a project-specific stress at the prestress centroid from staged SDL/deck effects.",
            )
        else:
            settings["delta_fcd_MPa"] = 0.0
            if settings["delta_fcd_source"] == REFINED_STRESS_EFFECT_AUTO_FUTURE:
                st.info("Auto Δfcd from Loads/composite staged stress is a future milestone; 0.00 MPa is used in this preview.")
            else:
                st.warning("Δfcd is not included in this refined preview; 0.00 MPa is used and engineering review is required.")
    with source_cols[1]:
        current = str(settings.get("delta_fcdf_source", REFINED_STRESS_EFFECT_NOT_INCLUDED))
        if current not in REFINED_STRESS_EFFECT_SOURCE_OPTIONS:
            current = REFINED_STRESS_EFFECT_NOT_INCLUDED
        settings["delta_fcdf_source"] = st.selectbox(
            "🟨 Δfcdf source",
            REFINED_STRESS_EFFECT_SOURCE_OPTIONS,
            index=REFINED_STRESS_EFFECT_SOURCE_OPTIONS.index(current),
            key=f"{key_prefix}_delta_fcdf_source",
            help="Δfcdf is the deck slab shrinkage interaction stress effect at the prestress centroid.",
        )
        if settings["delta_fcdf_source"] == REFINED_STRESS_EFFECT_MANUAL:
            settings["delta_fcdf_MPa"] = st.number_input(
                "🟨 Δfcdf (MPa)",
                min_value=0.0,
                step=0.1,
                value=float(settings.get("delta_fcdf_MPa", 0.0) or 0.0),
                format="%.3f",
                key=f"{key_prefix}_delta_fcdf_value",
                help="Use a project-specific deck-shrinkage interaction stress effect.",
            )
        else:
            settings["delta_fcdf_MPa"] = 0.0
            if settings["delta_fcdf_source"] == REFINED_STRESS_EFFECT_AUTO_FUTURE:
                st.info("Auto Δfcdf from deck shrinkage/composite interaction is a future milestone; 0.00 MPa is used in this preview.")
            else:
                st.warning("Δfcdf is not included in this refined preview; 0.00 MPa is used and engineering review is required.")
    st.dataframe(_loss_display_dataframe(_refined_stress_effect_input_dataframe(settings)), use_container_width=True, hide_index=True)
    with st.expander("Δfcd / Δfcdf guidance", expanded=False):
        st.markdown(
            "- **Δfcd**: concrete stress change at the prestress centroid from superimposed dead/deck-stage effects after deck placement.\n"
            "- **Δfcdf**: concrete stress change at the prestress centroid from deck slab shrinkage interaction.\n"
            "- Use **Not included / use 0.00 MPa** for preliminary checks when staged load/composite effects are not available.\n"
            "- Use **Manual input** only when values are available from project-specific calculation or specification.\n"
            "- Load/composite-derived automatic values are intentionally deferred to avoid hiding sign-convention or staged-stress assumptions."
        )
    return settings


def _section_exposed_outer_perimeter_mm(geometry: SectionGeometry | None) -> float:
    """Return the outer exposed perimeter estimate for LOSS3B V/S.

    Voids are intentionally excluded in LOSS3B because whether the void
    perimeter is exposed depends on production/curing details and requires a
    project-specific surface model.
    """

    if geometry is None:
        return 0.0
    try:
        return float(to_shapely_polygon(geometry).exterior.length)
    except Exception:
        return 0.0


def _girder_strand_total_aps_yps_ep(strand_table: pd.DataFrame) -> tuple[float, float, float]:
    active = _active_girder_strand_layout_rows(strand_table)
    total_aps = 0.0
    weighted_y = 0.0
    weighted_ep = 0.0
    for _, row in active.iterrows():
        strand_size = row.get("Strand Size") or row.get("strand_size") or DEFAULT_GIRDER_STRAND_SIZE
        props = _strand_size_properties(strand_size)
        count = int(_to_float(row.get("No. Strands")) or _to_float(row.get("No. strands")) or 0)
        area = float(_to_float(row.get("Area/Strand_mm2")) or _to_float(row.get("area_per_strand_mm2")) or props.get("area_mm2", 0.0) or 0.0)
        y = float(_to_float(row.get("y_mm_from_bottom")) or _to_float(row.get("y from bottom (mm)")) or 0.0)
        # _strand_size_properties returns normalized lower-case product keys.
        # Keep this helper tolerant of compact display rows so LOSS3B auto-
        # coefficient estimation reports REVIEW/missing data instead of
        # crashing with KeyError when a display table omits Strand Size.
        ep = float(props.get("ep_mpa", DEFAULT_STRAND_EP_MPA) or DEFAULT_STRAND_EP_MPA)
        aps = max(count, 0) * max(area, 0.0)
        total_aps += aps
        weighted_y += aps * y
        weighted_ep += aps * ep
    if total_aps <= 1.0e-9:
        return 0.0, 0.0, DEFAULT_STRAND_EP_MPA
    return total_aps, weighted_y / total_aps, weighted_ep / total_aps


def _auto_estimated_refined_coefficients_from_context(
    *,
    geometry: SectionGeometry | None,
    strand_table: pd.DataFrame,
    settings: dict[str, Any],
) -> Any | None:
    if geometry is None:
        return None
    try:
        props = compute_gross_section_properties(geometry)
    except Exception:
        return None
    total_aps, yps, Ep = _girder_strand_total_aps_yps_ep(strand_table)
    if total_aps <= 0.0:
        return None
    bottom_y = _section_bottom_y_from_geometry(geometry)
    cy_from_bottom = float(props.centroid_y_mm) - bottom_y
    fci = float(settings.get("fci_MPa", 0.0) or 0.0)
    concrete = st.session_state.get("concrete_material")
    fc = float(getattr(concrete, "fc_MPa", 0.0) or max(fci, 1.0))
    Eci = 4700.0 * max(fci, 1.0) ** 0.5
    Ec = 4700.0 * max(fc, 1.0) ** 0.5
    perimeter = _section_exposed_outer_perimeter_mm(geometry)
    auto_vs = estimate_volume_surface_ratio_mm(float(props.area_mm2), perimeter)
    vs_override = float(settings.get("vs_override_mm", 0.0) or 0.0)
    if vs_override > 0.0:
        perimeter = float(props.area_mm2) / vs_override if vs_override > 1.0e-9 else perimeter
    return estimate_refined_aashto_coefficients(
        RefinedAashtoCoefficientInput(
            section_area_mm2=float(props.area_mm2),
            exposed_perimeter_mm=float(perimeter),
            section_Ix_mm4=float(props.Ix_mm4),
            centroid_y_from_bottom_mm=cy_from_bottom,
            total_aps_mm2=total_aps,
            yps_mm_from_bottom=yps,
            Ep_MPa=Ep,
            Eci_MPa=Eci,
            Ec_MPa=Ec,
            fci_MPa=fci,
            fc_MPa=fc,
            humidity_percent=float(settings.get("humidity_percent", 75.0) or 75.0),
            age_transfer_days=float(settings.get("age_transfer_days", 1.0) or 1.0),
            age_deck_days=float(settings.get("age_deck_days", 30.0) or 30.0),
            final_age_days=float(settings.get("final_age_days", 10000.0) or 10000.0),
        )
    )




def _refined_current_coefficient_dataframe(settings: dict[str, Any], *, source: str) -> pd.DataFrame:
    rows = [
        {"Coefficient": "Kid", "Value": float(settings.get("Kid", 0.0) or 0.0), "Source": source, "Status": "READY", "Engineering note": "Transfer-to-deck interaction coefficient."},
        {"Coefficient": "Kdf", "Value": float(settings.get("Kdf", 0.0) or 0.0), "Source": source, "Status": "READY", "Engineering note": "Deck-to-final interaction coefficient."},
        {"Coefficient": "εbid", "Value": f"{float(settings.get('eps_bid_microstrain', 0.0) or 0.0):.1f} microstrain", "Source": source, "Status": "READY", "Engineering note": "Transfer-to-deck shrinkage strain."},
        {"Coefficient": "εbdf", "Value": f"{float(settings.get('eps_bdf_microstrain', 0.0) or 0.0):.1f} microstrain", "Source": source, "Status": "READY", "Engineering note": "Deck-to-final shrinkage strain."},
        {"Coefficient": "Ψb(td,ti)", "Value": float(settings.get("psi_td_ti", 0.0) or 0.0), "Source": source, "Status": "READY", "Engineering note": "Transfer-to-deck creep coefficient."},
        {"Coefficient": "Ψb(tf,ti)", "Value": float(settings.get("psi_tf_ti", 0.0) or 0.0), "Source": source, "Status": "READY", "Engineering note": "Total transfer-to-final creep coefficient."},
        {"Coefficient": "Ψb(tf,td)", "Value": float(settings.get("psi_tf_td", 0.0) or 0.0), "Source": source, "Status": "READY", "Engineering note": "Deck-to-final creep coefficient."},
    ]
    fcd_source, fcd_status = _refined_stress_effect_source_status(str(settings.get("delta_fcd_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)))
    fcdf_source, fcdf_status = _refined_stress_effect_source_status(str(settings.get("delta_fcdf_source", REFINED_STRESS_EFFECT_NOT_INCLUDED)))
    rows.extend([
        {"Coefficient": "Δfcd", "Value": f"{float(settings.get('delta_fcd_MPa', 0.0) or 0.0):.3f} MPa", "Source": fcd_source, "Status": fcd_status, "Engineering note": "SDL/deck-stage stress effect at prestress centroid."},
        {"Coefficient": "Δfcdf", "Value": f"{float(settings.get('delta_fcdf_MPa', 0.0) or 0.0):.3f} MPa", "Source": fcdf_source, "Status": fcdf_status, "Engineering note": "Deck shrinkage interaction stress effect at prestress centroid."},
    ])
    return pd.DataFrame(rows)

def _active_force_state_rows_by_group(force_table: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    return _loss_force_state_existing_rows_by_group(force_table)


def _girder_approximate_loss_groups_from_tables(
    strand_table: pd.DataFrame,
    force_table: pd.DataFrame,
    *,
    fpj_ratio: float | None = None,
) -> list[GirderLossStrandGroupInput]:
    force_by_group = _active_force_state_rows_by_group(force_table)
    groups: list[GirderLossStrandGroupInput] = []
    for _, row in _active_girder_strand_layout_rows(strand_table).iterrows():
        group = str(row.get("Group ID") or "strand group")
        force = force_by_group.get(group, {})
        area = float(_to_float(row.get("Area/Strand_mm2")) or _strand_size_properties(row.get("Strand Size"))["area_mm2"])
        count = int(_to_float(row.get("No. Strands")) or 0)
        y_from_bottom = float(_to_float(row.get("y_mm_from_bottom")) or 0.0)
        props = _strand_size_properties(row.get("Strand Size"))
        if fpj_ratio is None:
            pjack = float(_to_float(force.get("Pjack/strand_kN")) or _default_pjack_per_strand_kn(row.get("Strand Size")))
        else:
            # Code-based loss modes own the jacking stress assumption.  Derive
            # Pjack from fpj = ratio*fpu so users do not have to edit duplicate
            # Pjack values in the manual/percentage force-state table.
            pjack = max(float(fpj_ratio), 0.0) * float(props.get("fpu_mpa", DEFAULT_STRAND_FPU_MPA) or DEFAULT_STRAND_FPU_MPA) * area / 1000.0
        groups.append(
            GirderLossStrandGroupInput(
                group_id=group,
                no_strands=count,
                area_per_strand_mm2=area,
                y_mm_from_bottom=y_from_bottom,
                pjack_per_strand_kN=pjack,
                Ep_MPa=float(props.get("ep_mpa", DEFAULT_STRAND_EP_MPA) or DEFAULT_STRAND_EP_MPA),
                fpu_MPa=float(props.get("fpu_mpa", DEFAULT_STRAND_FPU_MPA) or DEFAULT_STRAND_FPU_MPA),
            )
        )
    return groups


def _girder_code_loss_input_audit_dataframe(
    *,
    geometry: SectionGeometry | None,
    strand_table: pd.DataFrame,
    force_table: pd.DataFrame,
    fci_MPa: float,
    humidity_percent: float,
    relaxation_class: str,
    fpj_ratio: float | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    concrete = st.session_state.get("concrete_material")
    fc = float(getattr(concrete, "fc_MPa", 0.0) or 0.0)
    try:
        props = compute_gross_section_properties(geometry) if geometry is not None else None
    except Exception:
        props = None
    groups = _girder_approximate_loss_groups_from_tables(strand_table, force_table, fpj_ratio=fpj_ratio)
    total_aps = sum(group.total_aps_mm2 for group in groups)
    rows.extend(
        [
            {
                "Item": "Concrete f'c",
                "Value": f"{fc:.1f} MPa" if fc > 0 else "—",
                "Source": "Materials page" if fc > 0 else "Missing",
                "Status": "READY" if fc > 0 else "MISSING",
                "Engineering note": "Final concrete strength for strength-factor context.",
            },
            {
                "Item": "Concrete f'ci",
                "Value": f"{float(fci_MPa):.1f} MPa",
                "Source": "Loss workspace input",
                "Status": "READY" if float(fci_MPa) > 0 else "MISSING",
                "Engineering note": "Release strength used by elastic shortening and approximate long-term loss factors.",
            },
            {
                "Item": "Relative humidity",
                "Value": f"{float(humidity_percent):.0f}%",
                "Source": "Loss workspace input",
                "Status": "READY" if 40.0 <= float(humidity_percent) <= 100.0 else "REVIEW",
                "Engineering note": "Advisory range is 40%–100% for this approximate estimate.",
            },
            {
                "Item": "Jacking stress fpj",
                "Value": f"{float(fpj_ratio if fpj_ratio is not None else DEFAULT_CODE_LOSS_FPJ_RATIO):.2f} fpu",
                "Source": "Loss workspace input",
                "Status": "READY" if 0.0 < float(fpj_ratio if fpj_ratio is not None else DEFAULT_CODE_LOSS_FPJ_RATIO) <= 0.90 else "REVIEW",
                "Engineering note": "Code-based/refined modes derive Pjack per strand from fpj ratio, strand fpu, and strand area.",
            },
            {
                "Item": "Gross section Ag / Ix",
                "Value": f"Ag={props.area_mm2:,.0f} mm², Ix={props.Ix_mm4:,.0f} mm⁴" if props is not None else "—",
                "Source": "Section geometry",
                "Status": "READY" if props is not None else "MISSING",
                "Engineering note": "Net gross section including voids/holes.",
            },
            {
                "Item": "Prestressing steel",
                "Value": f"{len(groups)} row(s), Aps={total_aps:,.1f} mm²",
                "Source": "Strand layout + Force States",
                "Status": "READY" if groups and total_aps > 0 else "MISSING",
                "Engineering note": "Code-based loss modes derive Pjack from fpj/fpu, strand fpu, and strand area; manual/percentage modes still use Force States Pjack.",
            },
            {
                "Item": "Relaxation class",
                "Value": str(relaxation_class),
                "Source": "Loss workspace input",
                "Status": "READY",
                "Engineering note": "Low relaxation uses 2.4 ksi relaxation loss in LOSS2A; stress-relieved uses 10 ksi.",
            },
        ]
    )
    return pd.DataFrame(rows, columns=LOSS_INPUT_AUDIT_COLUMNS)


def _self_weight_midspan_moment_for_loss_kNm(geometry: SectionGeometry | None, section_area_mm2: float) -> float:
    """Return simple-span self-weight midspan moment for loss fcir relief."""

    try:
        system = system_settings_from_mapping(st.session_state.get(BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
        w_self = girder_self_weight_kN_m(float(section_area_mm2), system.concrete_unit_weight_kN_m3)
        return simple_span_udl_moment_kNm(w_self, system.span_length_m / 2.0, system.span_length_m)
    except Exception:
        return 0.0


def _build_girder_approximate_loss_input(
    *,
    geometry: SectionGeometry | None,
    strand_table: pd.DataFrame,
    force_table: pd.DataFrame,
    fci_MPa: float,
    humidity_percent: float,
    relaxation_class: str,
    fpj_ratio: float | None = None,
    volume_surface_ratio_mm: float | None = None,
    kcir: float | None = None,
    kcr: float | None = None,
    ksh: float | None = None,
    fcds_MPa: float | None = None,
) -> GirderApproximateLossInput | None:
    if geometry is None:
        return None
    try:
        props = compute_gross_section_properties(geometry)
    except Exception:
        return None
    concrete = st.session_state.get("concrete_material")
    fc = float(getattr(concrete, "fc_MPa", 0.0) or max(float(fci_MPa), 1.0))
    Eci = 4700.0 * max(float(fci_MPa), 1.0) ** 0.5
    bottom_y = _section_bottom_y_from_geometry(geometry)
    cy_from_bottom = float(props.centroid_y_mm) - bottom_y
    groups = tuple(_girder_approximate_loss_groups_from_tables(
        strand_table,
        force_table,
        fpj_ratio=float(fpj_ratio if fpj_ratio is not None else DEFAULT_CODE_LOSS_FPJ_RATIO),
    ))
    if not groups:
        return None
    if volume_surface_ratio_mm is None or float(volume_surface_ratio_mm) <= 0.0:
        try:
            perimeter = _section_exposed_outer_perimeter_mm(geometry)
            volume_surface_ratio_mm = estimate_volume_surface_ratio_mm(float(props.area_mm2), perimeter)
        except Exception:
            volume_surface_ratio_mm = 88.9
    return GirderApproximateLossInput(
        groups=groups,
        section_area_mm2=float(props.area_mm2),
        section_Ix_mm4=float(props.Ix_mm4),
        centroid_y_from_bottom_mm=cy_from_bottom,
        fci_MPa=float(fci_MPa),
        fc_MPa=fc,
        Eci_MPa=Eci,
        humidity_percent=float(humidity_percent),
        relaxation_class=str(relaxation_class),
        volume_surface_ratio_mm=float(volume_surface_ratio_mm or 88.9),
        kcir=float(kcir if kcir is not None else 0.90),
        kcr=float(kcr if kcr is not None else 2.0),
        ksh=float(ksh if ksh is not None else 1.0),
        fcds_MPa=float(fcds_MPa if fcds_MPa is not None else 0.0),
        self_weight_moment_kNm=_self_weight_midspan_moment_for_loss_kNm(geometry, float(props.area_mm2)),
    )


def _render_girder_loss_apply_workflow_guidance(
    *,
    mode: str,
    force_table: pd.DataFrame,
    strand_table: pd.DataFrame,
) -> None:
    """Render mode-specific LOSS2A.2 apply-sequence guidance."""

    synced = _girder_force_states_match_strand_layout(strand_table, force_table)
    status = "Applied / SLS feed ready" if synced else "Pending apply"
    if mode in {"Approximate code-based loss", "Refined AASHTO time-dependent loss"}:
        refined = mode == "Refined AASHTO time-dependent loss"
        step_1 = "Confirm refined inputs" if refined else "Confirm code-loss inputs"
        step_2 = "Calculate and use refined losses" if refined else "Calculate and use loss estimate"
        step_3 = "Confirm SLS feed"
        status_detail = (
            "Code-based Pe values are the active force-state source for the strand table."
            if synced
            else "Calculate and use an estimate to update the active force states and strand table in one step."
        )
        button_text = "Calculate and use refined AASHTO losses" if refined else "Calculate and use approximate losses"
        st.info(
            f"Code-based loss workflow: 1) confirm detected inputs and required assumptions → "
            f"2) press {button_text} → "
            f"3) review the loss breakdown → "
            f"4) confirm SLS feed is Ready. No separate Apply button is required in this mode."
        )
    else:
        step_1 = "Edit force-state table"
        step_2 = "Review force states"
        step_3 = "Apply table values"
        status_detail = (
            "The strand table Pe columns match the reviewed force-state table."
            if synced
            else "The force-state table has reviewed values that still need to be applied to the strand table."
        )
        st.info(
            "Manual / percentage workflow: 1) edit the force-state table → "
            "2) review the calculated stage Pe values → "
            "3) press the Apply manual / percentage button directly below the table → "
            "4) confirm SLS feed is Ready."
        )
    cols = st.columns(4)
    cols[0].markdown(f"**Step 1**  \n{step_1}")
    cols[1].markdown(f"**Step 2**  \n{step_2}")
    cols[2].markdown(f"**Step 3**  \n{step_3}")
    cols[3].markdown(f"**Current status**  \n{status}")
    st.caption(status_detail)


def _build_girder_refined_aashto_loss_input(
    *,
    geometry: SectionGeometry | None,
    strand_table: pd.DataFrame,
    force_table: pd.DataFrame,
    settings: dict[str, Any],
) -> RefinedAashtoManualCoefficientInput | None:
    """Build a LOSS3A refined AASHTO manual-coefficient input bundle."""

    if geometry is None:
        return None
    try:
        props = compute_gross_section_properties(geometry)
    except Exception:
        return None
    concrete = st.session_state.get("concrete_material")
    fci = float(settings.get("fci_MPa", 0.0) or 0.0)
    fc = float(getattr(concrete, "fc_MPa", 0.0) or max(fci, 1.0))
    Eci = 4700.0 * max(fci, 1.0) ** 0.5
    Ec = 4700.0 * max(fc, 1.0) ** 0.5
    bottom_y = _section_bottom_y_from_geometry(geometry)
    cy_from_bottom = float(props.centroid_y_mm) - bottom_y
    groups = tuple(_girder_approximate_loss_groups_from_tables(strand_table, force_table, fpj_ratio=float(settings.get("fpj_ratio", DEFAULT_CODE_LOSS_FPJ_RATIO) or DEFAULT_CODE_LOSS_FPJ_RATIO)))
    if not groups:
        return None
    return RefinedAashtoManualCoefficientInput(
        groups=groups,
        section_area_mm2=float(props.area_mm2),
        section_Ix_mm4=float(props.Ix_mm4),
        centroid_y_from_bottom_mm=cy_from_bottom,
        fci_MPa=fci,
        fc_MPa=fc,
        Eci_MPa=Eci,
        Ec_MPa=Ec,
        fpy_MPa=float(settings.get("fpy_MPa", DEFAULT_STRAND_FPY_MPA) or DEFAULT_STRAND_FPY_MPA),
        relaxation_class=str(settings.get("relaxation_class", "Low relaxation")),
        age_transfer_days=float(settings.get("age_transfer_days", 1.0) or 1.0),
        age_deck_days=float(settings.get("age_deck_days", 30.0) or 30.0),
        final_age_days=float(settings.get("final_age_days", 10000.0) or 10000.0),
        Kid=float(settings.get("Kid", 1.0) or 1.0),
        Kdf=float(settings.get("Kdf", 1.0) or 1.0),
        eps_bid=float(settings.get("eps_bid_microstrain", 150.0) or 0.0) * 1.0e-6,
        eps_bdf=float(settings.get("eps_bdf_microstrain", 100.0) or 0.0) * 1.0e-6,
        psi_td_ti=float(settings.get("psi_td_ti", 1.0) or 0.0),
        psi_tf_ti=float(settings.get("psi_tf_ti", 2.0) or 0.0),
        psi_tf_td=float(settings.get("psi_tf_td", 1.0) or 0.0),
        delta_fcd_MPa=float(settings.get("delta_fcd_MPa", 0.0) or 0.0),
        delta_fcdf_MPa=float(settings.get("delta_fcdf_MPa", 0.0) or 0.0),
    )


def _loss_display_dataframe(table: pd.DataFrame) -> pd.DataFrame:
    """Return a rounded display copy for loss result/audit tables.

    Pandas 3 removes/strictly validates ``errors="ignore"`` in
    ``to_numeric``.  LOSS3A refined audit tables may legitimately mix numeric
    losses with text placeholders/status/formula cells, so display formatting
    must be value-safe instead of coercing whole columns blindly.
    """

    def _format_loss_value(value: Any) -> Any:
        if value is None or pd.isna(value):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped in {"", "-", "—", "N/A", "n/a"}:
                return value
            try:
                return round(float(stripped.replace(",", "")), 3)
            except ValueError:
                return value
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return value

    display_df = pd.DataFrame(table).copy()
    for column in display_df.columns:
        if any(token in str(column) for token in ["kN", "MPa", "%", "loss"]):
            display_df[column] = display_df[column].map(_format_loss_value)
    return display_df


def _render_girder_code_based_loss_estimate(
    strand_table: pd.DataFrame,
    force_table: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    method: str = "Approximate code-based loss",
) -> None:
    refined_mode = method == "Refined AASHTO time-dependent loss"
    heading = "Refined AASHTO Time-Dependent Loss" if refined_mode else "Code-Based Loss Estimate"
    st.markdown(f"##### {heading}")
    if refined_mode:
        st.caption(
            "LOSS3B adds auto-estimated refined AASHTO coefficients from RH/time/section data, while still allowing preset or manual override. "
            "Load-derived deck stress effects remain manual inputs and refined results require engineering review."
        )
    else:
        st.caption(
            "LOSS2A adds an approximate code-based estimate for pretensioned girders only. "
            "This estimate is not a final code-certified design."
        )

    settings = _girder_code_loss_settings_from_session()
    settings["method"] = str(method)
    settings, effective_loss_basis, loss_calculation_enabled = _render_girder_loss_code_basis_selector(settings, method=str(method))
    concrete = st.session_state.get("concrete_material")
    fc_detected = float(getattr(concrete, "fc_MPa", 45.0) or 45.0)

    common_cols = st.columns(4)
    with common_cols[0]:
        fci = st.number_input(
            "🟨 f'ci at transfer (MPa)",
            min_value=1.0,
            step=1.0,
            value=float(settings.get("fci_MPa", 0.8 * fc_detected)),
            format="%.1f",
            key="girder_code_loss_fci_mpa",
        )
    with common_cols[1]:
        fpj_ratio = st.number_input(
            "🟨 fpj / fpu",
            min_value=0.0,
            max_value=0.90,
            step=0.01,
            value=float(settings.get("fpj_ratio", DEFAULT_CODE_LOSS_FPJ_RATIO)),
            format="%.2f",
            key="girder_code_loss_fpj_ratio",
            help="Jacking stress assumption for code-based loss modes. Default fpj = 0.75 fpu; Pjack/strand is derived from fpj ratio, strand fpu, and strand area.",
        )
    st.caption(
        f"Jacking stress assumption: fpj = {float(fpj_ratio):.2f} fpu. "
        "Code-based loss modes derive Pjack/strand from this value; manual/percentage modes still allow direct Pjack editing."
    )
    if refined_mode:
        with common_cols[2]:
            relaxation = st.selectbox(
                "🟨 Strand relaxation class",
                ["Low relaxation", "Stress-relieved"],
                index=0 if str(settings.get("relaxation_class", "Low relaxation")) != "Stress-relieved" else 1,
                key="girder_code_loss_relaxation_class",
            )
        with common_cols[3]:
            fpy = st.number_input(
                "🟨 fpy (MPa)",
                min_value=1.0,
                step=10.0,
                value=float(settings.get("fpy_MPa", DEFAULT_STRAND_FPY_MPA)),
                format="%.1f",
                key="girder_refined_loss_fpy_mpa",
            )
        settings.update({"fci_MPa": float(fci), "fpj_ratio": float(fpj_ratio), "relaxation_class": str(relaxation), "fpy_MPa": float(fpy)})

        source_previous = str(settings.get("refined_coefficient_source", REFINED_COEFFICIENT_SOURCE_AUTO))
        if source_previous not in REFINED_COEFFICIENT_SOURCE_OPTIONS:
            source_previous = REFINED_COEFFICIENT_SOURCE_AUTO
        coefficient_source = st.selectbox(
            "🟨 Coefficient source",
            REFINED_COEFFICIENT_SOURCE_OPTIONS,
            index=REFINED_COEFFICIENT_SOURCE_OPTIONS.index(source_previous),
            key="girder_refined_coefficient_source",
            help="Auto-estimate coefficients from RH/time/section where possible, use climate presets, or manually override project-specific refined coefficients.",
        )
        settings["refined_coefficient_source"] = str(coefficient_source)

        time_cols = st.columns(3)
        with time_cols[0]:
            settings["age_transfer_days"] = st.number_input("🟨 Age at transfer ti (days)", min_value=0.0, step=1.0, value=float(settings.get("age_transfer_days", 1.0)), format="%.1f", key="girder_refined_age_transfer_days")
        with time_cols[1]:
            settings["age_deck_days"] = st.number_input("🟨 Age at deck placement td (days)", min_value=0.0, step=1.0, value=float(settings.get("age_deck_days", 30.0)), format="%.1f", key="girder_refined_age_deck_days")
        with time_cols[2]:
            settings["final_age_days"] = st.number_input("🟨 Final age tf (days)", min_value=0.0, step=100.0, value=float(settings.get("final_age_days", 10000.0)), format="%.1f", key="girder_refined_final_age_days")

        if coefficient_source == REFINED_COEFFICIENT_SOURCE_AUTO:
            auto_cols = st.columns(3)
            with auto_cols[0]:
                settings["humidity_percent"] = st.number_input(
                    "🟨 Relative humidity H (%)",
                    min_value=20.0,
                    max_value=100.0,
                    step=5.0,
                    value=float(settings.get("humidity_percent", 75.0)),
                    format="%.0f",
                    key="girder_refined_auto_humidity_percent",
                    help="Use project/site mean relative humidity. Lower RH generally increases shrinkage-related loss.",
                )
            with auto_cols[1]:
                auto_vs_preview = 0.0
                try:
                    props_preview = compute_gross_section_properties(geometry) if geometry is not None else None
                    if props_preview is not None:
                        auto_vs_preview = estimate_volume_surface_ratio_mm(float(props_preview.area_mm2), _section_exposed_outer_perimeter_mm(geometry))
                except Exception:
                    auto_vs_preview = 0.0
                settings["vs_override_mm"] = st.number_input(
                    "V/S override (mm, 0 = auto)",
                    min_value=0.0,
                    step=5.0,
                    value=float(settings.get("vs_override_mm", 0.0) or 0.0),
                    format="%.1f",
                    key="girder_refined_vs_override_mm",
                    help=f"Auto V/S from gross section outer perimeter is approximately {auto_vs_preview:.1f} mm. Voids are not included in the exposed perimeter estimate in LOSS3B.",
                )
            with auto_cols[2]:
                st.metric("Coefficient basis", "Auto-estimated", "RH/time/section")
            auto_result = _auto_estimated_refined_coefficients_from_context(geometry=geometry, strand_table=strand_table, settings=settings)
            if auto_result is None:
                st.warning("Auto-estimated refined coefficients require section geometry and active strand layout. Switch to preset/manual coefficients if data is incomplete.")
            else:
                for key, value in auto_result.as_settings_update().items():
                    settings[key] = float(value)
                st.dataframe(_loss_display_dataframe(auto_result.audit_dataframe()), use_container_width=True, hide_index=True)
                if auto_result.messages:
                    st.warning("Auto coefficient REVIEW: " + " ".join(auto_result.messages))
                else:
                    st.info("Auto-estimated refined coefficients are available; review deck/SDL stress-effect source status below before relying on refined loss results.")
            settings = _render_refined_deck_sdl_stress_effect_inputs(settings, key_prefix="girder_refined_auto")
            st.caption("LOSS3B auto-estimates creep/shrinkage/Kid/Kdf from RH, time, and gross section properties. Δfcd/Δfcdf are guided source inputs until staged load-derived stress is implemented.")

        elif coefficient_source == REFINED_COEFFICIENT_SOURCE_PRESET:
            preset_previous = str(settings.get("refined_coefficient_preset", DEFAULT_REFINED_COEFFICIENT_PRESET))
            if preset_previous not in REFINED_COEFFICIENT_PRESET_OPTIONS:
                preset_previous = DEFAULT_REFINED_COEFFICIENT_PRESET
            preset = st.selectbox(
                "🟨 Refined coefficient preset",
                [name for name in REFINED_COEFFICIENT_PRESET_OPTIONS if name != REFINED_COEFFICIENT_USER_DEFINED],
                index=[name for name in REFINED_COEFFICIENT_PRESET_OPTIONS if name != REFINED_COEFFICIENT_USER_DEFINED].index(preset_previous if preset_previous != REFINED_COEFFICIENT_USER_DEFINED else DEFAULT_REFINED_COEFFICIENT_PRESET),
                help="Preset coefficient sets include an RH basis to help match site/production climate. They are starter values, not automatic AASHTO coefficient prediction.",
                key="girder_refined_coefficient_preset",
            )
            settings = _apply_refined_coefficient_preset(settings, preset, sync_widget_state=True)
            settings["refined_coefficient_preset_applied"] = True
            st.caption(
                f"Preset RH basis: {float(settings.get('humidity_percent', 75.0)):.0f}%. "
                "Lower RH generally increases shrinkage-related prestress loss. Use project/site mean RH where available."
            )
            with st.expander("Preset coefficient guide", expanded=False):
                st.dataframe(_loss_display_dataframe(_refined_coefficient_preset_dataframe()), use_container_width=True, hide_index=True)
                st.caption("These are practical starter values for the LOSS3B refined workflow; choose Auto-estimated when section/RH/time-derived coefficients are preferred.")
            st.dataframe(_loss_display_dataframe(_refined_current_coefficient_dataframe(settings, source="Preset")), use_container_width=True, hide_index=True)
            settings = _render_refined_deck_sdl_stress_effect_inputs(settings, key_prefix="girder_refined_preset")

        else:
            settings["humidity_percent"] = st.number_input(
                "🟨 RH basis H (%)",
                min_value=20.0,
                max_value=100.0,
                step=5.0,
                value=float(settings.get("humidity_percent", 75.0)),
                format="%.0f",
                key="girder_refined_user_humidity_percent",
                help="Use project/site mean relative humidity when manual refined coefficients are project-specific.",
            )
            st.caption("Manual override: use project-specific AASHTO coefficient calculations or approved design assumptions.")
            st.markdown("###### Refined AASHTO manual coefficients")
            coeff_cols = st.columns(4)
            with coeff_cols[0]:
                settings["Kid"] = st.number_input("🟨 Kid", min_value=0.0, step=0.05, value=float(settings.get("Kid", 0.85)), format="%.3f", key="girder_refined_kid", help="Refined transformed-section interaction coefficient for transfer-to-deck interval.")
            with coeff_cols[1]:
                settings["Kdf"] = st.number_input("🟨 Kdf", min_value=0.0, step=0.05, value=float(settings.get("Kdf", 0.85)), format="%.3f", key="girder_refined_kdf", help="Refined transformed-section interaction coefficient for deck-to-final interval.")
            with coeff_cols[2]:
                settings["eps_bid_microstrain"] = st.number_input("🟨 εbid (microstrain)", min_value=0.0, step=10.0, value=float(settings.get("eps_bid_microstrain", 80.0)), format="%.1f", key="girder_refined_eps_bid", help="Shrinkage strain for transfer-to-deck interval.")
            with coeff_cols[3]:
                settings["eps_bdf_microstrain"] = st.number_input("🟨 εbdf (microstrain)", min_value=0.0, step=10.0, value=float(settings.get("eps_bdf_microstrain", 60.0)), format="%.1f", key="girder_refined_eps_bdf", help="Shrinkage strain for deck-to-final interval.")
            creep_cols = st.columns(5)
            with creep_cols[0]:
                settings["psi_td_ti"] = st.number_input("🟨 Ψb(td,ti)", min_value=0.0, step=0.05, value=float(settings.get("psi_td_ti", 0.60)), format="%.3f", key="girder_refined_psi_td_ti")
            with creep_cols[1]:
                settings["psi_tf_ti"] = st.number_input("🟨 Ψb(tf,ti)", min_value=0.0, step=0.05, value=float(settings.get("psi_tf_ti", 1.60)), format="%.3f", key="girder_refined_psi_tf_ti")
            with creep_cols[2]:
                settings["psi_tf_td"] = st.number_input("🟨 Ψb(tf,td)", min_value=0.0, step=0.05, value=float(settings.get("psi_tf_td", 1.00)), format="%.3f", key="girder_refined_psi_tf_td")
            settings = _render_refined_deck_sdl_stress_effect_inputs(settings, key_prefix="girder_refined_manual")

        review_messages = _refined_coefficient_review_messages(settings)
        if review_messages:
            st.warning("Refined coefficient REVIEW: " + " ".join(review_messages))
        elif coefficient_source != REFINED_COEFFICIENT_SOURCE_AUTO:
            st.success("Refined coefficient check: values are within the LOSS3B advisory range.")
        st.session_state["girder_prestress_code_loss_settings"] = settings
    else:
        aci_pci_mode = effective_loss_basis == PROJECT_CODE_ACI318
        if aci_pci_mode:
            rh_previous = str(settings.get("aci_pci_rh_source", "Thailand Central / Bangkok typical (75%)"))
            if rh_previous not in ACI_PCI_RH_PRESETS:
                rh_previous = "Thailand Central / Bangkok typical (75%)"
            with common_cols[2]:
                rh_source = st.selectbox(
                    "🟨 Relative humidity source",
                    list(ACI_PCI_RH_PRESETS.keys()),
                    index=list(ACI_PCI_RH_PRESETS.keys()).index(rh_previous),
                    key="girder_aci_pci_rh_source",
                    help="Use project/site mean relative humidity. Presets are starter values for Thai climate regions; use Manual project RH for project-specific data.",
                )
            preset_rh = ACI_PCI_RH_PRESETS.get(str(rh_source))
            if preset_rh is None:
                humidity = st.number_input(
                    "🟨 Manual project RH (%)",
                    min_value=20.0,
                    max_value=100.0,
                    step=5.0,
                    value=float(settings.get("humidity_percent", 75.0)),
                    format="%.0f",
                    key="girder_aci_pci_manual_humidity_percent",
                    help="Use project/site mean annual relative humidity, not maximum daily RH.",
                )
            else:
                humidity = float(preset_rh)
                st.caption(f"ACI/PCI RH basis: {rh_source} → H = {humidity:.0f}%.")
            settings["aci_pci_rh_source"] = str(rh_source)
        else:
            with common_cols[2]:
                humidity = st.number_input(
                    "🟨 Relative humidity H (%)",
                    min_value=20.0,
                    max_value=100.0,
                    step=5.0,
                    value=float(settings.get("humidity_percent", 70.0)),
                    format="%.0f",
                    key="girder_code_loss_humidity_percent",
                )
        with common_cols[3]:
            relaxation = st.selectbox(
                "🟨 Strand relaxation class",
                ["Low relaxation", "Stress-relieved"],
                index=0 if str(settings.get("relaxation_class", "Low relaxation")) != "Stress-relieved" else 1,
                key="girder_code_loss_relaxation_class",
            )
        settings.update({"fci_MPa": float(fci), "fpj_ratio": float(fpj_ratio), "humidity_percent": float(humidity), "relaxation_class": str(relaxation)})
        if aci_pci_mode:
            st.markdown("###### ACI/PCI loss input assistant")
            source_previous = str(settings.get("aci_pci_input_source", ACI_PCI_INPUT_SOURCE_AUTO))
            if source_previous not in ACI_PCI_INPUT_SOURCE_OPTIONS:
                source_previous = ACI_PCI_INPUT_SOURCE_AUTO
            input_source = st.selectbox(
                "🟨 ACI/PCI input source",
                ACI_PCI_INPUT_SOURCE_OPTIONS,
                index=ACI_PCI_INPUT_SOURCE_OPTIONS.index(source_previous),
                key="girder_aci_pci_input_source",
                help="Default lets the app calculate V/S and select Kcir, Kcr, and Ksh from section/material assumptions. Manual override is available for project-specific PCI/ACI criteria.",
            )
            settings["aci_pci_input_source"] = str(input_source)
            props_preview = None
            perimeter_preview = 0.0
            try:
                props_preview = compute_gross_section_properties(geometry) if geometry is not None else None
                perimeter_preview = _section_exposed_outer_perimeter_mm(geometry)
            except Exception:
                props_preview = None
                perimeter_preview = 0.0
            concrete_density = float(getattr(concrete, "density_kg_m3", 2400.0) or 2400.0)
            guided = estimate_aci_pci_guided_loss_inputs(
                section_area_mm2=float(props_preview.area_mm2) if props_preview is not None else None,
                exposed_perimeter_mm=float(perimeter_preview) if perimeter_preview else None,
                section_preset_key=st.session_state.get("section_preset_key"),
                section_category=st.session_state.get("section_category"),
                concrete_density_kg_m3=concrete_density,
            )
            if input_source == ACI_PCI_INPUT_SOURCE_AUTO:
                vs_in = guided.volume_surface_ratio_in
                kcir = guided.kcir
                kcr = guided.kcr
                ksh = guided.ksh
                st.dataframe(_loss_display_dataframe(guided.audit_dataframe()), use_container_width=True, hide_index=True)
                if guided.messages:
                    st.warning("ACI/PCI input REVIEW: " + " ".join(guided.messages))
                else:
                    st.success("ACI/PCI input assistant: V/S and coefficients are auto-selected from current section/material assumptions.")
            else:
                st.warning("Manual ACI/PCI input override is active. Verify V/S units: enter inches; the app stores the value internally in mm.")
                aci_cols = st.columns(4)
                with aci_cols[0]:
                    vs_in = st.number_input(
                        "🟨 V/S for PCI shrinkage (in.)",
                        min_value=0.1,
                        step=0.1,
                        value=float(settings.get("aci_pci_vs_in", guided.volume_surface_ratio_in)),
                        format="%.2f",
                        key="girder_aci_pci_vs_in",
                        help=(
                            f"Auto V/S from gross section outer perimeter is about {guided.volume_surface_ratio_in:.2f} in. "
                            "The app computes A/P in mm and converts to inches using 25.4 mm = 1 in."
                        ),
                    )
                with aci_cols[1]:
                    kcir = st.number_input("Kcir", min_value=0.0, max_value=1.5, step=0.05, value=float(settings.get("aci_pci_kcir", guided.kcir)), format="%.2f", key="girder_aci_pci_kcir")
                with aci_cols[2]:
                    kcr = st.number_input("Kcr", min_value=0.0, max_value=4.0, step=0.10, value=float(settings.get("aci_pci_kcr", guided.kcr)), format="%.2f", key="girder_aci_pci_kcr")
                with aci_cols[3]:
                    ksh = st.number_input("Ksh", min_value=0.0, max_value=2.0, step=0.05, value=float(settings.get("aci_pci_ksh", guided.ksh)), format="%.2f", key="girder_aci_pci_ksh")
                manual_audit = guided.audit_dataframe().copy()
                manual_audit.loc[manual_audit["Item"] == "V/S", ["Value", "Source", "Status", "Engineering note"]] = [
                    f"{float(vs_in):.2f} in. ({float(vs_in) * 25.4:.1f} mm)",
                    "Manual override",
                    "REVIEW",
                    "Manual V/S entered in inches; confirm exposed drying surface and section-family range.",
                ]
                manual_audit.loc[manual_audit["Item"] == "Kcir", ["Value", "Source", "Status"]] = [f"{float(kcir):.2f}", "Manual override", "REVIEW"]
                manual_audit.loc[manual_audit["Item"] == "Kcr", ["Value", "Source", "Status"]] = [f"{float(kcr):.2f}", "Manual override", "REVIEW"]
                manual_audit.loc[manual_audit["Item"] == "Ksh", ["Value", "Source", "Status"]] = [f"{float(ksh):.2f}", "Manual override", "REVIEW"]
                st.dataframe(_loss_display_dataframe(manual_audit), use_container_width=True, hide_index=True)
            settings.update({
                "aci_pci_vs_in": float(vs_in),
                "aci_pci_volume_surface_ratio_mm": float(vs_in) * 25.4,
                "aci_pci_kcir": float(kcir),
                "aci_pci_kcr": float(kcr),
                "aci_pci_ksh": float(ksh),
                "aci_pci_fcds_MPa": float(settings.get("aci_pci_fcds_MPa", 0.0) or 0.0),
            })
            st.caption(
                "ACI/PCI-style approximate loss uses ES + CR + SH + RE. The assistant computes V/S from section geometry where possible, "
                "selects Kcr from concrete density/type assumption, and keeps all values auditable/overridable."
            )
    audit = _girder_code_loss_input_audit_dataframe(
        geometry=geometry,
        strand_table=strand_table,
        force_table=force_table,
        fci_MPa=float(settings.get("fci_MPa", fci)),
        humidity_percent=float(settings.get("humidity_percent", 70.0)),
        relaxation_class=str(settings.get("relaxation_class", "Low relaxation")),
        fpj_ratio=float(settings.get("fpj_ratio", DEFAULT_CODE_LOSS_FPJ_RATIO) or DEFAULT_CODE_LOSS_FPJ_RATIO),
    )
    with st.expander("Auto-detected loss inputs", expanded=False):
        st.dataframe(audit, use_container_width=True, hide_index=True)

    if refined_mode:
        calc_clicked = st.button(
            "Calculate and use refined AASHTO losses",
            key="calculate_girder_refined_aashto_loss_estimate",
            type="primary",
            use_container_width=True,
            disabled=not loss_calculation_enabled,
        )
        if calc_clicked:
            loss_input = _build_girder_refined_aashto_loss_input(
                geometry=geometry,
                strand_table=strand_table,
                force_table=force_table,
                settings=settings,
            )
            if loss_input is None:
                st.error("Refined AASHTO loss estimate requires section geometry, gross properties, active strand rows, and Pjack values.")
            else:
                result = calculate_refined_aashto_time_dependent_loss(loss_input)
                result_df_to_apply = result.result_dataframe()
                st.session_state["girder_prestress_code_loss_result_table"] = result_df_to_apply
                st.session_state["girder_prestress_code_loss_summary_table"] = result.summary_dataframe()
                st.session_state["girder_prestress_refined_loss_interval_table"] = result.interval_dataframe()
                st.session_state["girder_prestress_code_loss_messages"] = list(result.messages)
                st.session_state["girder_prestress_code_loss_result_basis"] = "AASHTO LRFD refined"
                mapped = loss_result_dataframe_to_force_state_table(result_df_to_apply, force_table)
                normalized = _normalize_girder_loss_force_state_table(mapped, strand_table, mode="Manual stage Pe")
                st.session_state["girder_prestress_loss_force_state_table"] = normalized
                st.session_state["girder_strand_layout_table"] = _apply_girder_loss_force_states_to_strand_layout(strand_table, normalized)
                st.session_state["girder_prestress_code_loss_apply_status"] = "Applied"
                st.session_state["girder_prestress_loss_force_state_apply_status"] = "Applied"
                st.session_state["girder_prestress_active_pe_source"] = "Refined AASHTO time-dependent loss"
                st.session_state.pop("girder_strand_layout_editor", None)
                st.session_state.pop("girder_prestress_loss_force_state_editor", None)
                st.success("Refined AASHTO losses calculated and set as the active Pe source for Force States, strand table, and Effective Prestress Preview.")
                rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
                if callable(rerun):
                    rerun()
    else:
        loss_input = _build_girder_approximate_loss_input(
            geometry=geometry,
            strand_table=strand_table,
            force_table=force_table,
            fci_MPa=float(settings.get("fci_MPa", fci)),
            humidity_percent=float(settings.get("humidity_percent", 70.0)),
            relaxation_class=str(settings.get("relaxation_class", "Low relaxation")),
            fpj_ratio=float(settings.get("fpj_ratio", DEFAULT_CODE_LOSS_FPJ_RATIO) or DEFAULT_CODE_LOSS_FPJ_RATIO),
            volume_surface_ratio_mm=float(settings.get("aci_pci_volume_surface_ratio_mm", 0.0) or 0.0),
            kcir=float(settings.get("aci_pci_kcir", 0.90) or 0.90),
            kcr=float(settings.get("aci_pci_kcr", 2.0) or 2.0),
            ksh=float(settings.get("aci_pci_ksh", 1.0) or 1.0),
            fcds_MPa=float(settings.get("aci_pci_fcds_MPa", 0.0) or 0.0),
        )
        calc_clicked = st.button(
            "Calculate and use approximate losses",
            key="calculate_girder_code_loss_estimate",
            type="primary",
            use_container_width=True,
            disabled=not loss_calculation_enabled,
        )
        if calc_clicked:
            if loss_input is None:
                st.error("Approximate loss estimate requires section geometry, gross properties, active strand rows, and Pjack values.")
            else:
                if effective_loss_basis == PROJECT_CODE_ACI318:
                    result = calculate_aci_pci_approximate_prestress_loss(loss_input)
                    result_basis_label = "ACI 318 / PCI-style approximate"
                else:
                    result = calculate_approximate_prestress_loss(loss_input)
                    result_basis_label = "AASHTO LRFD approximate"
                result_df_to_apply = result.result_dataframe()
                st.session_state["girder_prestress_code_loss_result_table"] = result_df_to_apply
                st.session_state["girder_prestress_code_loss_summary_table"] = result.summary_dataframe()
                st.session_state["girder_prestress_refined_loss_interval_table"] = pd.DataFrame()
                st.session_state["girder_prestress_code_loss_messages"] = list(result.messages)
                st.session_state["girder_prestress_code_loss_result_basis"] = result_basis_label
                mapped = loss_result_dataframe_to_force_state_table(result_df_to_apply, force_table)
                normalized = _normalize_girder_loss_force_state_table(mapped, strand_table, mode="Manual stage Pe")
                st.session_state["girder_prestress_loss_force_state_table"] = normalized
                updated_strands = _apply_girder_loss_force_states_to_strand_layout(strand_table, normalized)
                st.session_state["girder_strand_layout_table"] = updated_strands
                st.session_state["girder_prestress_code_loss_apply_status"] = "Applied"
                st.session_state["girder_prestress_loss_force_state_apply_status"] = "Applied"
                st.session_state["girder_prestress_active_pe_source"] = result_basis_label
                st.session_state.pop("girder_strand_layout_editor", None)
                st.session_state.pop("girder_prestress_loss_force_state_editor", None)
                st.success("Approximate losses calculated and set as the active Pe source for Force States, strand table, and Effective Prestress Preview.")
                rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
                if callable(rerun):
                    rerun()

    result_table = st.session_state.get("girder_prestress_code_loss_result_table")
    expected_result_basis = (
        "AASHTO LRFD refined"
        if refined_mode
        else ("ACI 318 / PCI-style approximate" if effective_loss_basis == PROJECT_CODE_ACI318 else "AASHTO LRFD approximate")
    )
    stored_result_basis = st.session_state.get("girder_prestress_code_loss_result_basis")
    if result_table is None or pd.DataFrame(result_table).empty:
        st.info("Calculate and use a loss estimate to populate the active Pe_transfer, Pe_construction, and Pe_final values.")
        return
    if stored_result_basis and stored_result_basis != expected_result_basis:
        st.info(
            f"Existing loss result was calculated with {stored_result_basis}. Recalculate to use {expected_result_basis}; stale results are hidden to avoid mixing loss bases."
        )
        return
    result_df = pd.DataFrame(result_table)
    st.dataframe(_loss_display_dataframe(result_df), use_container_width=True, hide_index=True)
    if refined_mode:
        interval_table = st.session_state.get("girder_prestress_refined_loss_interval_table")
        if interval_table is not None and not pd.DataFrame(interval_table).empty:
            st.markdown("###### Refined interval loss audit")
            st.dataframe(_loss_display_dataframe(pd.DataFrame(interval_table)), use_container_width=True, hide_index=True)
    summary_table = st.session_state.get("girder_prestress_code_loss_summary_table")
    if summary_table is not None and not pd.DataFrame(summary_table).empty:
        st.dataframe(pd.DataFrame(summary_table), use_container_width=True, hide_index=True)
    active_source = st.session_state.get("girder_prestress_active_pe_source", "Approximate code-based loss")
    st.success(f"Active Pe source: {active_source}. The values shown above are already synchronized to Force States and the strand table.")
    with st.expander("Loss assumptions / formula audit", expanded=False):
        if refined_mode:
            st.markdown(
                "- Refined AASHTO manual-coefficient preview for pretensioned girders.\n"
                "- Elastic shortening is iterated using post-ES prestress and gross-section properties.\n"
                "- Kid, Kdf, shrinkage strains, creep coefficients, and deck stress effects are user-supplied manual coefficients in LOSS3A.\n"
                "- Automatic AASHTO creep/shrinkage coefficient prediction and load-derived Δfcd/Δfcdf are future milestones.\n"
                "- This is an engineering preview requiring review, not final clause-certified loss design."
            )
        else:
            if expected_result_basis == "ACI 318 / PCI-style approximate":
                st.markdown(
                    "- ACI/PCI-style pretensioned girder approximation: ES + CR + SH + RE.\n"
                    "- Elastic shortening uses PCI Kcir shortcut with gross-section properties and self-weight relief where span/system data are available.\n"
                    "- Creep uses Kcr × Eps/Ec × (fcir − fcds); current fcds default is 0.00 MPa unless project-specific review is added.\n"
                    "- Shrinkage uses PCI-style V/S and RH term; relaxation uses PCI Kre/J/C-factor table interpolation.\n"
                    "- This is an engineering estimate requiring review, not final code-certified loss design."
                )
            else:
                st.markdown(
                    "- Pretensioned girder approximation only: ES + long-term loss.\n"
                    "- Elastic shortening is iterated using post-ES prestress and gross-section properties.\n"
                    "- Approximate long-term loss is evaluated with AASHTO-style humidity, strength, Aps/Ag, and relaxation terms.\n"
                    "- Construction Pe is set equal to transfer Pe in LOSS2A; interval splitting is reserved for refined AASHTO LOSS3A.\n"
                    "- This is an engineering estimate requiring review, not final code-certified loss design."
                )

def _render_girder_force_states_losses_workspace(strand_table: pd.DataFrame, geometry: SectionGeometry | None = None) -> None:
    st.markdown("#### Prestress Force States / Losses")
    st.markdown(
        '<div class="cpmm-prestress-table-note">'
        "Define stage prestress per strand for girder SLS. Select one loss input mode at a time so the page shows only the workflow you are using. "
        "Refined AASHTO loss, transfer-length ramp, development, shear, and end-zone reinforcement are future milestones."
        "</div>",
        unsafe_allow_html=True,
    )
    settings = st.session_state.get("girder_prestress_loss_settings", {}) or {}
    mode_default = settings.get("mode", "Manual stage Pe")
    if mode_default not in GIRDER_LOSS_INPUT_MODE_OPTIONS:
        mode_default = "Manual stage Pe"
    mode = st.selectbox(
        "Loss input mode",
        GIRDER_LOSS_INPUT_MODE_OPTIONS,
        index=GIRDER_LOSS_INPUT_MODE_OPTIONS.index(mode_default),
        help="Choose one workflow. Manual and percentage modes edit the force-state table; approximate code-based loss calculates a reviewed estimate and applies it directly.",
        key="girder_prestress_loss_input_mode",
    )
    settings["mode"] = str(mode)
    st.session_state["girder_prestress_loss_settings"] = settings

    current = st.session_state.get("girder_prestress_loss_force_state_table")
    force_table = _normalize_girder_loss_force_state_table(
        pd.DataFrame(current) if current is not None else None,
        strand_table,
        mode="Percentage loss" if mode == "Percentage loss" else "Manual stage Pe",
    )
    _render_girder_loss_apply_workflow_guidance(mode=str(mode), force_table=force_table, strand_table=strand_table)

    if mode in {"Approximate code-based loss", "Refined AASHTO time-dependent loss"}:
        _render_girder_code_based_loss_estimate(strand_table, force_table, geometry, method=str(mode))
        synced_force_table = _normalize_girder_loss_force_state_table(
            pd.DataFrame(st.session_state.get("girder_prestress_loss_force_state_table", force_table)),
            strand_table,
            mode="Manual stage Pe",
        )
        status, messages = _girder_loss_force_state_qa_summary(synced_force_table)
        mapping_status, mapping_messages = girder_stage_pe_mapping_status(synced_force_table)
        sls_feed_ready = status == "OK" and mapping_status == "READY" and _girder_force_states_match_strand_layout(strand_table, synced_force_table)
        loss_settings = _girder_code_loss_settings_from_session()
        effective_loss_basis = _effective_girder_loss_code_basis(loss_settings)
        metrics = [
            PrestressMetric("Loss mode", "Refined AASHTO" if mode == "Refined AASHTO time-dependent loss" else "Code estimate", "LOSS3A refined workflow" if mode == "Refined AASHTO time-dependent loss" else "approximate LOSS2A workflow", "info", strong=True),
            PrestressMetric("Loss basis", effective_loss_basis, "inherits from workflow-compatible project code unless overridden", "warning" if effective_loss_basis != workflow_project_design_code_from_session(st.session_state) else "info"),
            PrestressMetric("Apply status", st.session_state.get("girder_prestress_code_loss_apply_status", "Pending apply"), "calculated loss result"),
        ]
        metrics.extend(_stage_pe_mapping_metrics_from_table(synced_force_table, sls_feed_ready=sls_feed_ready))
        st.markdown(_metric_strip_html(metrics), unsafe_allow_html=True)
        if messages or mapping_messages:
            with st.expander("Force-state QA / stage Pe mapping review messages", expanded=False):
                for message in messages:
                    st.warning(message)
                for message in mapping_messages:
                    st.warning(message)
        _render_stage_pe_mapping_audit(synced_force_table, expanded=False)
        if mode == "Refined AASHTO time-dependent loss":
            st.warning(
                "LOSS3B refined AASHTO results may use auto-estimated, preset, or manual coefficients and remain engineering-preview values. "
                "Automatic coefficient prediction and load-derived deck stress effects are future milestones."
            )
        else:
            if effective_loss_basis == PROJECT_CODE_ACI318:
                st.warning(
                    "ACI/PCI-style approximate loss results are engineering-preview values for pretensioned girders. "
                    "They may be used for Building default workflow or Bridge cross-check when intentionally selected; final project criteria still require engineering review."
                )
            else:
                st.warning(
                    "AASHTO approximate code-based loss results are engineering-preview values. "
                    "The Calculate-and-use action is the single source of truth for this mode."
                )
        return

    pe_disabled = mode == "Percentage loss"
    loss_disabled = mode == "Manual stage Pe"
    edited = st.data_editor(
        force_table,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_order=GIRDER_LOSS_FORCE_STATE_COLUMNS,
        column_config={
            "Active": st.column_config.CheckboxColumn("Active", disabled=True),
            "Group ID": st.column_config.TextColumn("Group ID", disabled=True),
            "No. strands": st.column_config.NumberColumn("No. strands", disabled=True, format="%d"),
            "Pjack/strand_kN": st.column_config.NumberColumn("🟨 Pjack / strand (kN)", min_value=0.0, step=5.0, format="%.3f"),
            "Transfer loss %": st.column_config.NumberColumn(("🟨 " if not loss_disabled else "") + "Transfer loss %", min_value=0.0, max_value=60.0, step=1.0, format="%.2f", disabled=loss_disabled),
            "Pe_transfer/strand_kN": st.column_config.NumberColumn(("🟨 " if not pe_disabled else "") + "Pe_transfer / strand (kN)", min_value=0.0, step=5.0, format="%.3f", disabled=pe_disabled),
            "Construction loss %": st.column_config.NumberColumn(("🟨 " if not loss_disabled else "") + "Construction loss %", min_value=0.0, max_value=60.0, step=1.0, format="%.2f", disabled=loss_disabled),
            "Pe_construction/strand_kN": st.column_config.NumberColumn(("🟨 " if not pe_disabled else "") + "Pe_construction / strand (kN)", min_value=0.0, step=5.0, format="%.3f", disabled=pe_disabled),
            "Long-term loss %": st.column_config.NumberColumn(("🟨 " if not loss_disabled else "") + "Long-term loss %", min_value=0.0, max_value=60.0, step=1.0, format="%.2f", disabled=loss_disabled),
            "Pe_eff_final/strand_kN": st.column_config.NumberColumn(("🟨 " if not pe_disabled else "") + "Pe_final / strand (kN)", min_value=0.0, step=5.0, format="%.3f", disabled=pe_disabled),
            "Total loss %": st.column_config.NumberColumn("Total loss %", disabled=True, format="%.2f"),
            "QA status": st.column_config.TextColumn("QA status", disabled=True),
            "Note": st.column_config.TextColumn("Note", disabled=True),
        },
        key="girder_prestress_loss_force_state_editor",
        on_change=_sync_girder_loss_force_state_editor_to_table,
        args=(pd.DataFrame(strand_table).reset_index(drop=True), str(mode)),
    )
    edited_df = _data_editor_payload_to_dataframe(edited, force_table)
    normalized = _normalize_girder_loss_force_state_table(edited_df, strand_table, mode=str(mode))
    _persist_girder_loss_force_state_table(normalized)

    apply_col, note_col = st.columns([1.2, 4.0])
    with apply_col:
        apply_clicked = st.button(
            "Apply manual / percentage force states to strand table",
            key="apply_girder_force_states_to_strand_table",
            type="primary",
            use_container_width=True,
        )
    with note_col:
        st.caption("Use this button only after editing the manual/percentage force-state table. Switch to Approximate code-based loss to calculate and apply code-based estimates instead.")
    if apply_clicked:
        updated = _apply_girder_loss_force_states_to_strand_layout(strand_table, normalized)
        st.session_state["girder_strand_layout_table"] = updated
        st.session_state["girder_prestress_loss_force_state_apply_status"] = "Applied"
        st.session_state.pop("girder_strand_layout_editor", None)
        st.success("Manual / percentage force states applied to strand layout Pe columns.")
        rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()

    status, messages = _girder_loss_force_state_qa_summary(normalized)
    total_strands = int(pd.to_numeric(normalized.get("No. strands", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not normalized.empty else 0
    pe_transfer_total = float((pd.to_numeric(normalized.get("No. strands", pd.Series(dtype=float)), errors="coerce").fillna(0) * pd.to_numeric(normalized.get("Pe_transfer/strand_kN", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if not normalized.empty else 0.0
    pe_final_total = float((pd.to_numeric(normalized.get("No. strands", pd.Series(dtype=float)), errors="coerce").fillna(0) * pd.to_numeric(normalized.get("Pe_eff_final/strand_kN", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if not normalized.empty else 0.0
    total_losses = pd.to_numeric(normalized.get("Total loss %", pd.Series(dtype=float)), errors="coerce").dropna() if not normalized.empty else pd.Series(dtype=float)
    loss_range = "—" if total_losses.empty else f"{float(total_losses.min()):.1f}%–{float(total_losses.max()):.1f}%"
    mapping_status, mapping_messages = girder_stage_pe_mapping_status(normalized)
    sls_feed_ready = status == "OK" and mapping_status == "READY" and _girder_force_states_match_strand_layout(strand_table, normalized)
    metrics = [
        PrestressMetric("Force states", status, "manual / percentage workflow", "ready" if status == "OK" else "review", strong=True),
        PrestressMetric("Active strands", f"{total_strands:,}", "force-state rows"),
        PrestressMetric("Pe_transfer total", f"{pe_transfer_total:,.1f} kN", "sum by group"),
        PrestressMetric("Pe_final total", f"{pe_final_total:,.1f} kN", "sum by group"),
        PrestressMetric("Loss range", loss_range, "per strand group"),
    ]
    metrics.extend(_stage_pe_mapping_metrics_from_table(normalized, sls_feed_ready=sls_feed_ready))
    st.markdown(_metric_strip_html(metrics), unsafe_allow_html=True)
    if messages or mapping_messages:
        with st.expander("Force-state QA / stage Pe mapping review messages", expanded=False):
            for message in messages:
                st.warning(message)
            for message in mapping_messages:
                st.warning(message)
    _render_stage_pe_mapping_audit(normalized, expanded=False)
    st.warning(
        "LOSS1/LOSS2 force states are engineering-preview values, not final code-certified AASHTO/ACI loss calculations. "
        "Only this manual/percentage workspace is active in the current mode."
    )



def _girder_prestress_system_settings_from_session() -> dict[str, Any]:
    """Return normalized simple-supported girder prestress-system settings.

    GIRDER.PS3A intentionally defines the longitudinal convention and span
    metadata needed by debonding preview only. It does not compute losses or
    alter Analysis stress equations. Railway U-Girder uses a shorter practical
    default span because the user-defined through U-girder family is normally
    used around 10--15 m; existing project/session values are preserved.
    """

    current = st.session_state.get("girder_prestress_system_settings", {}) or {}
    defaults = dict(GIRDER_PRESTRESS_SYSTEM_DEFAULTS)
    if _current_section_preset_key() == RAILWAY_U_GIRDER_PRESET_KEY and _is_blank(current.get("span_length_m")):
        defaults["span_length_m"] = RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M
    settings = dict(defaults)
    settings.update({key: current.get(key, default) for key, default in defaults.items()})
    span = _to_float(settings.get("span_length_m"))
    settings["span_length_m"] = float(defaults["span_length_m"]) if span is None or span <= 0.0 else span
    if settings.get("debond_model") not in GIRDER_DEBOND_MODE_OPTIONS:
        settings["debond_model"] = "Left/right independent"
    return settings


def _aci_concrete_ec_mpa(fc_mpa: Any) -> float:
    """Return ACI normal-weight concrete Ec = 4700 sqrt(f'c) in MPa."""

    fc = _to_float(fc_mpa)
    if fc is None or fc <= 0.0:
        fc = 1.0
    return 4700.0 * sqrt(float(fc))


def _railway_u_girder_stage_settings_from_session() -> dict[str, Any]:
    """Return editable Railway U-Girder staged-construction defaults.

    STAGE.RAIL.UGIRDER1 is metadata/UI only.  The values describe the staged
    construction basis to be consumed by a later guarded stress-preview
    milestone; they do not alter Pe, loss, SLS, or PMM solvers.
    """

    current = st.session_state.get(RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY, {}) or {}
    settings = dict(RAILWAY_U_GIRDER_STAGE_DEFAULTS)
    settings.update({key: current.get(key, default) for key, default in RAILWAY_U_GIRDER_STAGE_DEFAULTS.items()})
    for key in (
        "web_fc_MPa",
        "web_fci_MPa",
        "slab_fc_MPa",
        "concrete_unit_weight_kN_m3",
        "wet_slab_distribution_each_web",
        "formwork_construction_load_kN_m2",
        "lifting_point_ratio",
        "lifting_impact_factor",
    ):
        value = _to_float(settings.get(key))
        default = float(RAILWAY_U_GIRDER_STAGE_DEFAULTS[key])
        if value is None or (key != "formwork_construction_load_kN_m2" and value <= 0.0) or (key == "formwork_construction_load_kN_m2" and value < 0.0):
            value = default
        settings[key] = float(value)
    settings["wet_slab_distribution_each_web"] = min(max(float(settings["wet_slab_distribution_each_web"]), 0.0), 1.0)
    settings["lifting_point_ratio"] = min(max(float(settings["lifting_point_ratio"]), 0.05), 0.45)
    settings["support_condition"] = "Simply supported"
    settings["construction_method"] = "Case B - wet slab carried by precast webs"
    return settings


def _railway_u_girder_parameter_snapshot(geometry: SectionGeometry | None) -> dict[str, float]:
    """Return Railway U-Girder drawing parameters from current geometry metadata."""

    metadata = getattr(geometry, "metadata", {}) or {}
    params = dict(metadata.get("parameters", {}) or {})
    derived = dict(metadata.get("derived_details", {}) or {})
    width = _to_float(params.get("width_mm")) or _section_width_from_geometry(geometry, fallback_mm=5500.0)
    depth = _to_float(params.get("depth_mm")) or _section_depth_from_geometry(geometry, fallback_mm=1600.0)
    top_wall = _to_float(params.get("top_wall_width_mm")) or 600.0
    bottom_side = _to_float(params.get("bottom_side_width_mm")) or 650.0
    h1 = _to_float(params.get("h1_step_height_mm")) or 670.0
    h2 = _to_float(params.get("h2_bottom_opening_mm")) or 305.0
    h3 = _to_float(params.get("h3_floor_side_thickness_mm")) or 395.0
    h4 = _to_float(params.get("h4_floor_center_thickness_mm")) or 450.0
    haunch_x = _to_float(params.get("haunch_x_mm")) or 300.0
    haunch_y = _to_float(params.get("haunch_y_mm")) or 300.0
    inner_half = _to_float(derived.get("inner_half_width_mm")) or max(float(width) / 2.0 - float(bottom_side), 0.0)
    return {
        "width_mm": float(width),
        "depth_mm": float(depth),
        "top_wall_width_mm": float(top_wall),
        "bottom_side_width_mm": float(bottom_side),
        "h1_step_height_mm": float(h1),
        "h2_bottom_opening_mm": float(h2),
        "h3_floor_side_thickness_mm": float(h3),
        "h4_floor_center_thickness_mm": float(h4),
        "haunch_x_mm": float(haunch_x),
        "haunch_y_mm": float(haunch_y),
        "inner_half_width_mm": float(inner_half),
    }


def _railway_u_girder_stage_quantities_dataframe(
    geometry: SectionGeometry | None,
    settings: dict[str, Any],
    *,
    span_length_m: float,
) -> pd.DataFrame:
    """Return non-solver stage quantities for Railway U-Girder construction review."""

    p = _railway_u_girder_parameter_snapshot(geometry)
    depth = p["depth_mm"]
    half_width = p["width_mm"] / 2.0
    bottom_side = p["bottom_side_width_mm"]
    top_wall = p["top_wall_width_mm"]
    notch = max(bottom_side - top_wall, 0.0)
    upper_outer_half = half_width - notch
    inner_half = p["inner_half_width_mm"]
    chamfer = 25.0
    h1 = p["h1_step_height_mm"]
    web_right_points = [
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
    try:
        web_area_mm2 = float(Polygon(web_right_points).area)
    except Exception:
        web_area_mm2 = max(float(top_wall) * float(depth), 0.0)

    full_area_mm2 = 0.0
    try:
        if geometry is not None:
            full_area_mm2 = float(compute_gross_section_properties(geometry).area_mm2)
    except Exception:
        full_area_mm2 = 0.0
    if full_area_mm2 <= 0.0:
        full_area_mm2 = 2.0 * web_area_mm2

    floor_underside_y = p["depth_mm"] - p["h2_bottom_opening_mm"]
    floor_side_top_y = floor_underside_y - p["h3_floor_side_thickness_mm"]
    floor_center_top_y = floor_underside_y - p["h4_floor_center_thickness_mm"]
    haunch_start_y = floor_side_top_y - p["haunch_y_mm"]
    slab_points = [
        (-inner_half, haunch_start_y),
        (-(inner_half - p["haunch_x_mm"]), floor_side_top_y),
        (0.0, floor_center_top_y),
        (inner_half - p["haunch_x_mm"], floor_side_top_y),
        (inner_half, haunch_start_y),
        (inner_half, floor_underside_y),
        (-inner_half, floor_underside_y),
    ]
    try:
        slab_area_mm2 = max(float(Polygon(slab_points).area), 0.0)
    except Exception:
        slab_area_mm2 = max(full_area_mm2 - 2.0 * web_area_mm2, 0.0)
    if slab_area_mm2 <= 0.0 and full_area_mm2 > 2.0 * web_area_mm2:
        slab_area_mm2 = max(full_area_mm2 - 2.0 * web_area_mm2, 0.0)

    gamma = float(settings.get("concrete_unit_weight_kN_m3", 24.0) or 24.0)
    formwork_q = float(settings.get("formwork_construction_load_kN_m2", 2.5) or 0.0)
    distribution = float(settings.get("wet_slab_distribution_each_web", 0.5) or 0.5)
    lifting_factor = float(settings.get("lifting_impact_factor", 1.10) or 1.10)
    lifting_ratio = float(settings.get("lifting_point_ratio", 0.20) or 0.20)
    projected_slab_width_m = 2.0 * inner_half / 1000.0
    web_sw = web_area_mm2 / 1_000_000.0 * gamma
    slab_wet_total = slab_area_mm2 / 1_000_000.0 * gamma
    formwork_total = projected_slab_width_m * formwork_q
    full_sw = full_area_mm2 / 1_000_000.0 * gamma
    return pd.DataFrame(
        [
            {
                "Quantity": "Precast web area (one side)",
                "Value": web_area_mm2 / 1_000_000.0,
                "Unit": "m²",
                "Stage use": "Transfer / lifting / wet slab casting",
            },
            {
                "Quantity": "CIP slab area",
                "Value": slab_area_mm2 / 1_000_000.0,
                "Unit": "m²",
                "Stage use": "Wet slab casting then full U composite",
            },
            {
                "Quantity": "Web self-weight (one side)",
                "Value": web_sw,
                "Unit": "kN/m",
                "Stage use": "Web-only stages",
            },
            {
                "Quantity": "Lifting web load with impact",
                "Value": web_sw * lifting_factor,
                "Unit": "kN/m",
                "Stage use": f"Two-point lifting, a={lifting_ratio * span_length_m:.3f} m from each end",
            },
            {
                "Quantity": "Wet slab self-weight to each web",
                "Value": slab_wet_total * distribution,
                "Unit": "kN/m",
                "Stage use": "Case B before composite action",
            },
            {
                "Quantity": "Formwork/construction load to each web",
                "Value": formwork_total * distribution,
                "Unit": "kN/m",
                "Stage use": "Case B before composite action",
            },
            {
                "Quantity": "Full U self-weight",
                "Value": full_sw,
                "Unit": "kN/m",
                "Stage use": "Composite / service reference",
            },
        ]
    )


def _railway_u_girder_stage_summary_dataframe(settings: dict[str, Any]) -> pd.DataFrame:
    """Return the guarded staged-construction section-basis map for Railway U-Girder."""

    return pd.DataFrame(
        [
            {
                "Stage": "Transfer",
                "Section basis": "One precast web only",
                "Automatic loads": "web self-weight + Pe_transfer",
                "Concrete basis": "web f'ci",
                "Status": "Defined for future stress preview",
            },
            {
                "Stage": "Lifting",
                "Section basis": "One precast web only",
                "Automatic loads": "web self-weight × lifting impact + Pe_lifting",
                "Concrete basis": "web f'ci / engineer review",
                "Status": "Defined for future stress preview",
            },
            {
                "Stage": "Wet slab casting",
                "Section basis": "One precast web only",
                "Automatic loads": "web self-weight + 50% wet slab + 50% formwork/construction + Pe_construction",
                "Concrete basis": "web f'c after transfer",
                "Status": "Case B metadata only",
            },
            {
                "Stage": "Composite construction",
                "Section basis": "Full Railway U-Girder",
                "Automatic loads": "locked-in prior loads; no service loads yet",
                "Concrete basis": "web f'c + slab f'c",
                "Status": "Defined for future stress preview",
            },
            {
                "Stage": "Service",
                "Section basis": "Full Railway U-Girder",
                "Automatic loads": "Loads tab service components + Pe_eff_final",
                "Concrete basis": "web f'c + slab f'c",
                "Status": "Defined for future stress preview",
            },
        ]
    )


def _strand_size_properties(strand_size: str | None) -> dict[str, float]:
    """Return normalized strand properties for the girder layout table."""

    label = str(strand_size or DEFAULT_GIRDER_STRAND_SIZE).strip()
    if label not in GIRDER_STRAND_SIZE_PROPERTIES:
        label = DEFAULT_GIRDER_STRAND_SIZE
    return dict(GIRDER_STRAND_SIZE_PROPERTIES[label])


def _default_pe_transfer_per_strand_kn(strand_size: str | None) -> float:
    """Return a practical editable starter value for transfer force per strand.

    This is a UI convenience only. Automatic loss calculation and force-state
    design remain future milestones; the value is intentionally editable and
    must be confirmed by the engineer.
    """

    props = _strand_size_properties(strand_size)
    return round(props["area_mm2"] * 0.70 * props["fpu_mpa"] / 1000.0, 3)


def _default_pe_final_per_strand_kn(strand_size: str | None) -> float:
    props = _strand_size_properties(strand_size)
    return round(props["area_mm2"] * 0.60 * props["fpu_mpa"] / 1000.0, 3)


def _default_strand_count_for_row(geometry: SectionGeometry | None, y_from_bottom_mm: float, *, fallback_count: int) -> int:
    """Return a section-based starter strand count for one row.

    Defaults are generated from the currently selected section geometry using
    the practical girder strand detailing convention: 45 mm edge centerline and
    50 mm horizontal strand spacing for the default 12.7 mm low-relaxation
    strand.  This is a starting layout only; the engineer can edit the row
    count and the app will re-check fit immediately.
    """

    bottom_y = _section_bottom_y_from_geometry(geometry)
    y_abs = bottom_y + float(y_from_bottom_mm)
    segment = _section_horizontal_segment_at_y(geometry, y_abs)
    if segment is None:
        return max(1, int(fallback_count))
    left_edge, right_edge = segment
    available_width = max(0.0, float(right_edge) - float(left_edge) - 2.0 * DEFAULT_GIRDER_STRAND_EDGE_CL_MM)
    if available_width <= 0.0:
        return max(1, int(fallback_count))
    return max(1, int(available_width // DEFAULT_GIRDER_STRAND_X_SPACING_MM) + 1)


def _geometry_preset_key(geometry: SectionGeometry | None) -> str:
    if geometry is None:
        return ""
    metadata = getattr(geometry, "metadata", {}) or {}
    return str(metadata.get("preset") or metadata.get("section_preset_key") or "").strip()


def _current_or_geometry_section_preset_key(geometry: SectionGeometry | None = None) -> str:
    # Geometry metadata is the safest source for default rebuilding because
    # tests and imported UI helpers can leave a stale section_preset_key in
    # session state.  Fall back to session only when geometry has no preset.
    return _geometry_preset_key(geometry) or _current_section_preset_key()


def _section_bounds_from_geometry(geometry: SectionGeometry | None) -> tuple[float, float, float, float] | None:
    if geometry is None:
        return None
    try:
        polygon = to_shapely_polygon(geometry)
        minx, miny, maxx, maxy = polygon.bounds
        return float(minx), float(miny), float(maxx), float(maxy)
    except Exception:
        return None


def _section_depth_from_geometry(geometry: SectionGeometry | None, *, fallback_mm: float) -> float:
    bounds = _section_bounds_from_geometry(geometry)
    if bounds is None:
        return float(fallback_mm)
    _, miny, _, maxy = bounds
    return float(maxy - miny)


def _section_width_from_geometry(geometry: SectionGeometry | None, *, fallback_mm: float) -> float:
    bounds = _section_bounds_from_geometry(geometry)
    if bounds is None:
        return float(fallback_mm)
    minx, _, maxx, _ = bounds
    return float(maxx - minx)


def _symmetric_no_center_positions(count: int, spacing_mm: float) -> list[float]:
    """Return symmetric x positions with no strand on the centerline for even counts."""

    strand_count = max(0, int(count))
    if strand_count <= 0:
        return []
    if strand_count == 1:
        return [0.0]
    spacing = max(float(spacing_mm), 0.0)
    return [(float(i) - (float(strand_count) - 1.0) / 2.0) * spacing for i in range(strand_count)]


def _symmetric_spread_no_center_positions(count: int, outer_offset_mm: float) -> list[float]:
    """Return evenly spread symmetric positions between +/-outer_offset, avoiding CL."""

    strand_count = max(0, int(count))
    if strand_count <= 0:
        return []
    if strand_count == 1:
        return [0.0]
    half_count = strand_count // 2
    if strand_count % 2:
        half_count = strand_count // 2
        side = [float(outer_offset_mm) * (i + 1) / max(half_count, 1) for i in range(half_count)]
        return [-value for value in reversed(side)] + [0.0] + side
    step = float(outer_offset_mm) / max(half_count - 0.5, 0.5)
    positive = [(i + 0.5) * step for i in range(half_count)]
    return [-value for value in reversed(positive)] + positive


def _format_mm_compact(value: float) -> str:
    """Return compact mm text for table display.

    Strand detailing coordinates are shown as whole millimetres in the main
    editor to keep the girder strand table readable.  Computation still parses
    the text as float values, but preset/generated values should not clutter
    the UI with trailing .000 decimals.
    """

    return f"{int(round(float(value)))}"


def _format_explicit_x_positions(values: list[float]) -> str:
    return ",".join(_format_mm_compact(value) for value in values)


def _parse_explicit_x_positions(value: Any, expected_count: int) -> list[float]:
    if value is None:
        return []
    text_value = str(value).strip()
    if not text_value:
        return []
    tokens = [part.strip() for part in text_value.replace(";", ",").replace("|", ",").split(",") if part.strip()]
    parsed: list[float] = []
    for token in tokens:
        try:
            parsed.append(float(token))
        except (TypeError, ValueError):
            return []
    if len(parsed) != int(expected_count):
        return []
    return parsed


def _auto_strand_x_positions_text(count: int, *, center_x_mm: float = 0.0, spacing_mm: float = DEFAULT_GIRDER_STRAND_X_SPACING_MM) -> str:
    """Return editable comma-separated x coordinates for the strand row.

    The values are intentionally stored as text because a row may contain many
    individual strand x coordinates.  Users can edit the list directly, and the
    first edit is persisted by the data-editor sync callback.
    """

    strand_count = max(0, int(count))
    if strand_count <= 0:
        return ""
    positions = [float(center_x_mm) + value for value in _symmetric_no_center_positions(strand_count, float(spacing_mm))]
    return _format_explicit_x_positions(positions)


def _box_plank_practical_debonded_numbers(count: int) -> str:
    """Return Option 2 spaced symmetric pairs for four practical debonded strands."""

    strand_count = int(count)
    if strand_count >= 18:
        return "1,3,16,18"
    if strand_count >= 16:
        return "1,3,14,16"
    if strand_count >= 4:
        return f"1,3,{strand_count - 2},{strand_count}"
    return ""


def _format_debond_pattern_mm(values: list[int | float]) -> str:
    """Return compact comma-separated drawing debond symbols in mm."""

    cleaned: list[str] = []
    for value in values:
        try:
            length = int(round(float(value)))
        except (TypeError, ValueError):
            length = 0
        cleaned.append(str(length))
    return ",".join(cleaned)


def _strand_row_number_from_group_id(group_id: Any) -> int | None:
    """Return 1-based strand row number parsed from labels such as ``L Row 3``."""

    text = str(group_id or "").strip()
    match = re.search(r"\brow\s*(\d+)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        number = int(match.group(1))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _railway_u_girder_default_debond_length_for_row_m(row_number: int | None, span_length_m: float) -> float:
    """Return the user-approved Railway U-Girder default debond length for a row.

    Row 1 is the bottom strand row and gets the longest default length L/5.
    Each higher row is reduced by 0.5 m.  The value is a detailing/default
    helper only; it is applied to a row only after the engineer selects
    debonded strand numbers for that row.
    """

    if row_number is None or row_number <= 0:
        return 0.0
    span = max(float(span_length_m), 0.0)
    return max(0.0, span / 5.0 - RAILWAY_U_GIRDER_DEBOND_ROW_STEP_M * float(row_number - 1))


def _is_railway_u_girder_geometry(geometry: SectionGeometry | None = None) -> bool:
    return _current_or_geometry_section_preset_key(geometry) == RAILWAY_U_GIRDER_PRESET_KEY


def _parse_debond_pattern_mm(value: Any, expected_count: int) -> list[int]:
    """Parse optional per-strand drawing debond lengths in millimetres.

    This is preview metadata only.  It maps drawing symbols such as 1000, 2000,
    3000, 4000, and 5000 mm to strand markers.  It intentionally does not
    alter row-based station/debonding calculations, which continue to use the
    existing Left/Right debond fields until a station-based pattern milestone.
    """

    if value is None:
        return []
    text_value = str(value).strip()
    if not text_value:
        return []
    text_value = text_value.replace("bonded", "0").replace("Bonded", "0")
    tokens = [part.strip() for part in re.split(r"[,;|\s]+", text_value) if part.strip()]
    parsed: list[int] = []
    for token in tokens:
        try:
            length = int(round(float(token)))
        except (TypeError, ValueError):
            return []
        if length not in RAILWAY_U_GIRDER_DEBOND_SYMBOLS_MM:
            return []
        parsed.append(length)
    if len(parsed) != int(expected_count):
        return []
    return parsed


def _railway_u_girder_side_x_positions(side: str, index_set: tuple[int, ...]) -> list[float]:
    """Return Railway U-Girder strand x positions ordered outer face to inner face."""

    width = 5500.0
    bottom_side_width = 650.0
    half_width = width / 2.0
    left_outer = -half_width + RAILWAY_U_GIRDER_STRAND_EDGE_OUTER_MM
    right_outer = half_width - RAILWAY_U_GIRDER_STRAND_EDGE_OUTER_MM
    if side.upper() == "L":
        base = [left_outer + i * RAILWAY_U_GIRDER_STRAND_SPACING_MM for i in range(9)]
    else:
        base = [right_outer - i * RAILWAY_U_GIRDER_STRAND_SPACING_MM for i in range(9)]
    # The drawing check is deliberately kept here: 130 + 8@55 + 80 = 650 mm.
    _ = bottom_side_width - RAILWAY_U_GIRDER_STRAND_EDGE_OUTER_MM - 8.0 * RAILWAY_U_GIRDER_STRAND_SPACING_MM
    return [float(base[index]) for index in index_set]


def _railway_u_girder_default_strand_layout_table(geometry: SectionGeometry | None = None) -> pd.DataFrame:
    """Return the drawing-based Railway U-Girder 72-strand starter layout.

    The layout is based on the user-supplied railway through U-girder drawing:
    36 strands per side, 12.7 mm ASTM A416 Grade 270 low-relaxation strand,
    five rows at 95/150/205/260/315 mm from the bottom fiber, and a 9-column
    strand grid using 130 mm outside edge distance, 8 @ 55 mm spacing, and
    80 mm inside edge distance.  Row 5 follows the drawing columns 3, 4,
    6, and 7 rather than a continuous four-strand block.  Debond pattern symbols are preview metadata
    only and are left bonded/blank until the project-specific debonding pattern
    is entered.
    """

    _ = geometry
    strand_size = DEFAULT_GIRDER_STRAND_SIZE
    props = _strand_size_properties(strand_size)
    pe_transfer = _default_pe_transfer_per_strand_kn(strand_size)
    pe_final = _default_pe_final_per_strand_kn(strand_size)
    rows: list[dict[str, Any]] = []
    for side in ("L", "R"):
        side_label = "Left" if side == "L" else "Right"
        for row_index, (y_from_bottom, index_set) in enumerate(
            zip(RAILWAY_U_GIRDER_ROW_Y_FROM_BOTTOM_MM, RAILWAY_U_GIRDER_ROW_INDEX_SETS, strict=True),
            start=1,
        ):
            x_positions = _railway_u_girder_side_x_positions(side, index_set)
            count = len(x_positions)
            rows.append(
                {
                    "Active": True,
                    "Group ID": f"{side} Row {row_index}",
                    "Layer": f"Railway U-Girder {side_label} {row_index}st row" if row_index == 1 else f"Railway U-Girder {side_label} Row {row_index}",
                    "Strand Size": strand_size,
                    "No. Strands": count,
                    "Area/Strand_mm2": props["area_mm2"],
                    "Total Aps_mm2": count * props["area_mm2"],
                    "Row center x_mm": sum(x_positions) / max(count, 1),
                    "Strand x positions mm": _format_explicit_x_positions(x_positions),
                    "y_mm_from_bottom": y_from_bottom,
                    "Edge CL_mm": props["recommended_edge_cl_mm"],
                    "Min spacing_mm": props["recommended_min_spacing_mm"],
                    "Computed spacing_mm": 0.0,
                    "Pe_transfer/strand_kN": pe_transfer,
                    "Pe_construction/strand_kN": pe_transfer,
                    "Pe_eff_final/strand_kN": pe_final,
                    "Left debond m": 0.0,
                    "Right debond m": 0.0,
                    "Debonded strand nos": "",
                    "Debond pattern mm": "",
                    "Note": "Railway U-Girder drawing default: 12.7 mm ASTM A416 Gr.270 LR strand; if debonded strands are selected, row default length = max(0, L/5 - 0.5 m per row above Row 1).",
                }
            )
    return pd.DataFrame(rows, columns=GIRDER_STRAND_LAYOUT_COLUMNS)


def _practical_box_beam_strand_layout_table(geometry: SectionGeometry | None) -> pd.DataFrame:
    strand_size = DEFAULT_GIRDER_STRAND_SIZE
    props = _strand_size_properties(strand_size)
    pe_transfer = _default_pe_transfer_per_strand_kn(strand_size)
    pe_final = _default_pe_final_per_strand_kn(strand_size)
    width = _section_width_from_geometry(geometry, fallback_mm=990.0)
    depth = _section_depth_from_geometry(geometry, fallback_mm=700.0)
    top_pair_x = max(0.0, width / 2.0 - 145.0)
    row2_outer = max(150.0, width / 2.0 - 145.0)
    rows = [
        {
            "Active": True,
            "Group ID": "Row 1",
            "Layer": "Bottom row practical box preset",
            "Strand Size": strand_size,
            "No. Strands": 18,
            "Area/Strand_mm2": props["area_mm2"],
            "Total Aps_mm2": 18 * props["area_mm2"],
            "Row center x_mm": 0.0,
            "Strand x positions mm": _format_explicit_x_positions(_symmetric_no_center_positions(18, 50.0)),
            "y_mm_from_bottom": 50.0,
            "Edge CL_mm": props["recommended_edge_cl_mm"],
            "Min spacing_mm": props["recommended_min_spacing_mm"],
            "Computed spacing_mm": 0.0,
            "Pe_transfer/strand_kN": pe_transfer,
            "Pe_construction/strand_kN": pe_transfer,
            "Pe_eff_final/strand_kN": pe_final,
            "Left debond m": BOX_PLANK_PRACTICAL_DEBOND_LENGTH_M,
            "Right debond m": BOX_PLANK_PRACTICAL_DEBOND_LENGTH_M,
            "Debonded strand nos": _box_plank_practical_debonded_numbers(18),
            "Note": "BP1 practical box preset: Row 1 only debonded, Option 2 spaced symmetric pairs.",
        },
        {
            "Active": True,
            "Group ID": "Row 2",
            "Layer": "Middle row practical box preset",
            "Strand Size": strand_size,
            "No. Strands": 6,
            "Area/Strand_mm2": props["area_mm2"],
            "Total Aps_mm2": 6 * props["area_mm2"],
            "Row center x_mm": 0.0,
            "Strand x positions mm": _format_explicit_x_positions(_symmetric_spread_no_center_positions(6, row2_outer)),
            "y_mm_from_bottom": 100.0,
            "Edge CL_mm": props["recommended_edge_cl_mm"],
            "Min spacing_mm": props["recommended_min_spacing_mm"],
            "Computed spacing_mm": 0.0,
            "Pe_transfer/strand_kN": pe_transfer,
            "Pe_construction/strand_kN": pe_transfer,
            "Pe_eff_final/strand_kN": pe_final,
            "Left debond m": 0.0,
            "Right debond m": 0.0,
            "Debonded strand nos": "",
            "Note": "BP1 practical box preset: distributed middle row, no strand on CL.",
        },
        {
            "Active": True,
            "Group ID": "Row 3",
            "Layer": "Top row practical box preset",
            "Strand Size": strand_size,
            "No. Strands": 2,
            "Area/Strand_mm2": props["area_mm2"],
            "Total Aps_mm2": 2 * props["area_mm2"],
            "Row center x_mm": 0.0,
            "Strand x positions mm": _format_explicit_x_positions([-top_pair_x, top_pair_x]),
            "y_mm_from_bottom": max(0.0, depth - 50.0),
            "Edge CL_mm": props["recommended_edge_cl_mm"],
            "Min spacing_mm": props["recommended_min_spacing_mm"],
            "Computed spacing_mm": 0.0,
            "Pe_transfer/strand_kN": pe_transfer,
            "Pe_construction/strand_kN": pe_transfer,
            "Pe_eff_final/strand_kN": pe_final,
            "Left debond m": 0.0,
            "Right debond m": 0.0,
            "Debonded strand nos": "",
            "Note": "BP1.1 practical box preset: top pair 145 mm from left/right top corners.",
        },
    ]
    return pd.DataFrame(rows, columns=GIRDER_STRAND_LAYOUT_COLUMNS)


def _practical_plank_girder_strand_layout_table(geometry: SectionGeometry | None) -> pd.DataFrame:
    strand_size = DEFAULT_GIRDER_STRAND_SIZE
    props = _strand_size_properties(strand_size)
    pe_transfer = _default_pe_transfer_per_strand_kn(strand_size)
    pe_final = _default_pe_final_per_strand_kn(strand_size)
    width = _section_width_from_geometry(geometry, fallback_mm=990.0)
    depth = _section_depth_from_geometry(geometry, fallback_mm=450.0)
    edge_bottom = 70.0
    nearest_cl = 75.0
    half_count = 8
    left_positions = [-(nearest_cl + 50.0 * i) for i in reversed(range(half_count))]
    right_positions = [(nearest_cl + 50.0 * i) for i in range(half_count)]
    bottom_positions = left_positions + right_positions
    # If the current section width differs from the 990 mm practical plank detail,
    # shift only the outer pair to preserve the user's 70 mm edge convention.
    target_outer = max(0.0, width / 2.0 - edge_bottom)
    scale = target_outer / 425.0 if abs(target_outer - 425.0) > 1e-9 and target_outer > 0.0 else 1.0
    if scale != 1.0:
        bottom_positions = [round(value * scale, 3) for value in bottom_positions]
    preset_key = _current_or_geometry_section_preset_key(geometry)
    top_edge_offset_mm = 190.0 if str(preset_key).endswith("_exterior") else 120.0
    top_pair_x = max(0.0, width / 2.0 - top_edge_offset_mm)
    rows = [
        {
            "Active": True,
            "Group ID": "Row 1",
            "Layer": "Bottom row practical plank preset",
            "Strand Size": strand_size,
            "No. Strands": 16,
            "Area/Strand_mm2": props["area_mm2"],
            "Total Aps_mm2": 16 * props["area_mm2"],
            "Row center x_mm": 0.0,
            "Strand x positions mm": _format_explicit_x_positions(bottom_positions),
            "y_mm_from_bottom": 50.0,
            "Edge CL_mm": props["recommended_edge_cl_mm"],
            "Min spacing_mm": props["recommended_min_spacing_mm"],
            "Computed spacing_mm": 0.0,
            "Pe_transfer/strand_kN": pe_transfer,
            "Pe_construction/strand_kN": pe_transfer,
            "Pe_eff_final/strand_kN": pe_final,
            "Left debond m": BOX_PLANK_PRACTICAL_DEBOND_LENGTH_M,
            "Right debond m": BOX_PLANK_PRACTICAL_DEBOND_LENGTH_M,
            "Debonded strand nos": _box_plank_practical_debonded_numbers(16),
            "Note": "BP1 practical plank preset: Row 1 only debonded, Option 2 spaced symmetric pairs.",
        },
        {
            "Active": True,
            "Group ID": "Row 2",
            "Layer": "Top row practical plank preset",
            "Strand Size": strand_size,
            "No. Strands": 2,
            "Area/Strand_mm2": props["area_mm2"],
            "Total Aps_mm2": 2 * props["area_mm2"],
            "Row center x_mm": 0.0,
            "Strand x positions mm": _format_explicit_x_positions([-top_pair_x, top_pair_x]),
            "y_mm_from_bottom": max(0.0, depth - 50.0),
            "Edge CL_mm": props["recommended_edge_cl_mm"],
            "Min spacing_mm": props["recommended_min_spacing_mm"],
            "Computed spacing_mm": 0.0,
            "Pe_transfer/strand_kN": pe_transfer,
            "Pe_construction/strand_kN": pe_transfer,
            "Pe_eff_final/strand_kN": pe_final,
            "Left debond m": 0.0,
            "Right debond m": 0.0,
            "Debonded strand nos": "",
            "Note": f"BP1.1 practical plank preset: top pair {top_edge_offset_mm:.0f} mm from left/right top corners.",
        },
    ]
    return pd.DataFrame(rows, columns=GIRDER_STRAND_LAYOUT_COLUMNS)


def _practical_box_plank_default_girder_strand_layout_table(geometry: SectionGeometry | None = None) -> pd.DataFrame | None:
    preset_key = _current_or_geometry_section_preset_key(geometry)
    if preset_key == RAILWAY_U_GIRDER_PRESET_KEY:
        return _railway_u_girder_default_strand_layout_table(geometry)
    if preset_key in PRECAST_BOX_BEAM_PRESET_KEYS:
        return _practical_box_beam_strand_layout_table(geometry)
    if preset_key in PRECAST_PLANK_GIRDER_PRESET_KEYS:
        return _practical_plank_girder_strand_layout_table(geometry)
    return None


def _default_girder_strand_layout_table(geometry: SectionGeometry | None = None) -> pd.DataFrame:
    """Return a section-based starter strand-row layout for simple-supported girders.

    The starter layout uses the current practical convention requested for
    precast girders: 12.7 mm low-relaxation strand, two rows, first row at
    50 mm above the bottom fiber, 50 mm vertical spacing, 45 mm edge CL, and
    50 mm horizontal strand spacing.  Row counts are seeded from the current
    section width at each row elevation, then remain editable by the engineer.
    """

    practical = _practical_box_plank_default_girder_strand_layout_table(geometry)
    if practical is not None:
        return practical

    strand_size = DEFAULT_GIRDER_STRAND_SIZE
    props = _strand_size_properties(strand_size)
    pe_transfer = _default_pe_transfer_per_strand_kn(strand_size)
    pe_final = _default_pe_final_per_strand_kn(strand_size)
    rows: list[dict[str, Any]] = []
    for idx in range(DEFAULT_GIRDER_STRAND_ROW_COUNT):
        y_from_bottom = DEFAULT_GIRDER_STRAND_FIRST_ROW_Y_MM + idx * DEFAULT_GIRDER_STRAND_ROW_VERTICAL_SPACING_MM
        fallback = DEFAULT_GIRDER_STRAND_FALLBACK_COUNTS[idx] if idx < len(DEFAULT_GIRDER_STRAND_FALLBACK_COUNTS) else DEFAULT_GIRDER_STRAND_FALLBACK_COUNTS[-1]
        count = _default_strand_count_for_row(geometry, y_from_bottom, fallback_count=fallback)
        rows.append(
            {
                "Active": True,
                "Group ID": f"Row {idx + 1}",
                "Layer": "Bottom row" if idx == 0 else f"Row {idx + 1}",
                "Strand Size": strand_size,
                "No. Strands": count,
                "Area/Strand_mm2": props["area_mm2"],
                "Total Aps_mm2": count * props["area_mm2"],
                "Row center x_mm": 0.0,
                "Strand x positions mm": _auto_strand_x_positions_text(count, center_x_mm=0.0, spacing_mm=props["recommended_min_spacing_mm"]),
                "y_mm_from_bottom": y_from_bottom,
                "Edge CL_mm": props["recommended_edge_cl_mm"],
                "Min spacing_mm": props["recommended_min_spacing_mm"],
                "Computed spacing_mm": 0.0,
                "Pe_transfer/strand_kN": pe_transfer,
                "Pe_construction/strand_kN": pe_transfer,
                "Pe_eff_final/strand_kN": pe_final,
                "Left debond m": 0.0,
                "Right debond m": 0.0,
                "Debonded strand nos": "",
                "Note": "Auto section default row; edit count/debond/force as needed.",
            }
        )
    return pd.DataFrame(rows, columns=GIRDER_STRAND_LAYOUT_COLUMNS)


def _looks_like_legacy_starter_strand_layout(table: pd.DataFrame | None) -> bool:
    """Return True for the old PS3A 3-row example layout so it can migrate.

    The old starter rows were examples, not project data.  Migrating only this
    exact shape lets new sections start with the section-based two-row default
    without overwriting user-edited layouts.
    """

    if table is None:
        return False
    df = pd.DataFrame(table)
    if len(df.index) != 3:
        return False
    expected_notes = {"Fully bonded starter row", "Example symmetric debond row", "Example longer debond row"}
    notes = {str(value or "").strip() for value in df.get("Note", pd.Series(dtype=object)).tolist()}
    if not expected_notes.issubset(notes):
        return False
    counts = [int(_to_float(value) or 0) for value in df.get("No. Strands", pd.Series(dtype=object)).tolist()]
    y_values = [round(float(_to_float(value) or 0.0), 6) for value in df.get("y_mm_from_bottom", pd.Series(dtype=object)).tolist()]
    return counts == [12, 8, 4] and y_values == [100.0, 150.0, 200.0]

def _strand_layout_existing_rows_by_group(table: pd.DataFrame | None) -> list[dict[str, Any]]:
    if table is None:
        return []
    df = pd.DataFrame(table)
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        if any(not _is_blank(row_dict.get(column)) for column in GIRDER_STRAND_LAYOUT_COLUMNS if column in df.columns):
            rows.append(row_dict)
    return rows



def _mirror_railway_u_girder_symmetric_debonding_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mirror Railway U-Girder debond metadata between L/R rows.

    In symmetric Railway U-Girder detailing mode, the left web is the primary
    editing side.  The opposite web is kept matched automatically so users do
    not have to enter the same debonded strand numbers and sleeve lengths twice.
    If legacy data contains only an R-row value, the value is copied back to the
    L row rather than silently discarded.
    """

    by_row: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        group = str(row.get("Group ID") or "").strip()
        row_number = _strand_row_number_from_group_id(group)
        if row_number is None:
            continue
        side = ""
        if group.upper().startswith("L "):
            side = "L"
        elif group.upper().startswith("R "):
            side = "R"
        if side:
            by_row.setdefault(row_number, {})[side] = row

    mirror_fields = ["Left debond m", "Right debond m", "Debonded strand nos", "Debond pattern mm"]

    def has_debond_metadata(row: dict[str, Any] | None) -> bool:
        if not row:
            return False
        left = float(_to_float(row.get("Left debond m")) or 0.0)
        right = float(_to_float(row.get("Right debond m")) or 0.0)
        selected = str(row.get("Debonded strand nos") or "").strip()
        pattern = str(row.get("Debond pattern mm") or "").strip()
        return left > 1e-9 or right > 1e-9 or bool(selected) or bool(pattern)

    for pair in by_row.values():
        left_row = pair.get("L")
        right_row = pair.get("R")
        if left_row is None or right_row is None:
            continue
        source = left_row if has_debond_metadata(left_row) or not has_debond_metadata(right_row) else right_row
        target = right_row if source is left_row else left_row
        for field in mirror_fields:
            target[field] = source.get(field)
        # Keep the sleeve convention symmetric at each end for both sides.
        for row in (left_row, right_row):
            left_length = float(_to_float(row.get("Left debond m")) or 0.0)
            right_length = float(_to_float(row.get("Right debond m")) or 0.0)
            controlling = max(left_length, right_length)
            row["Left debond m"] = controlling
            row["Right debond m"] = controlling
            note = str(row.get("Note") or "")
            mirror_note = "Railway U-Girder symmetric mode: L/R debond metadata is mirrored automatically."
            if mirror_note not in note:
                row["Note"] = (note + " " + mirror_note).strip()
    return rows

def _normalize_girder_strand_layout_table(
    table: pd.DataFrame | None,
    *,
    span_length_m: float,
    debond_model: str = "Left/right independent",
    geometry: SectionGeometry | None = None,
) -> pd.DataFrame:
    """Normalize the editable strand layout/debonding table.

    This table is metadata for the Beam/Girder SLS workflow. GIRDER.PS3A does
    not use it to change PMM, SLS stress kernels, or prestress force-state
    calculations yet.
    """

    existing = _strand_layout_existing_rows_by_group(table)
    if not existing or _looks_like_legacy_starter_strand_layout(pd.DataFrame(existing)):
        existing = _default_girder_strand_layout_table(geometry).to_dict(orient="records")
    rows: list[dict[str, Any]] = []
    for i, current in enumerate(existing, start=1):
        active = _to_bool_default_true(current.get("Active"))
        group_id = str(current.get("Group ID") or f"Row {i}").strip() or f"Row {i}"
        no_strands = _to_float(current.get("No. Strands"))
        no_strands = 0.0 if no_strands is None or no_strands < 0 else float(int(round(no_strands)))
        strand_size = str(current.get("Strand Size") or DEFAULT_GIRDER_STRAND_SIZE).strip()
        if strand_size not in GIRDER_STRAND_SIZE_OPTIONS:
            strand_size = DEFAULT_GIRDER_STRAND_SIZE
        strand_props = _strand_size_properties(strand_size)
        # Area is controlled by the selected standard strand size. This avoids
        # hidden diameter/area mismatch when the user changes the dropdown.
        area_per = float(strand_props["area_mm2"])
        total_aps = no_strands * area_per
        left_debond = _to_float(current.get("Left debond m"))
        right_debond = _to_float(current.get("Right debond m"))
        left_debond = 0.0 if left_debond is None or left_debond < 0.0 else min(float(left_debond), span_length_m)
        explicit_debond_selection = str(current.get("Debonded strand nos") or "").strip()
        if debond_model == "No debonding":
            left_debond = 0.0
            right_debond = 0.0
        elif debond_model == "Symmetric left/right":
            right_debond = left_debond
        else:
            right_debond = 0.0 if right_debond is None or right_debond < 0.0 else min(float(right_debond), span_length_m)
        if (
            _is_railway_u_girder_geometry(geometry)
            and explicit_debond_selection
            and debond_model != "No debonding"
            and left_debond <= 1e-9
            and right_debond <= 1e-9
        ):
            row_number = _strand_row_number_from_group_id(group_id)
            default_debond = _railway_u_girder_default_debond_length_for_row_m(row_number, span_length_m)
            left_debond = min(default_debond, float(span_length_m))
            right_debond = left_debond if debond_model == "Symmetric left/right" else min(default_debond, float(span_length_m))
        y_from_bottom = _to_float(current.get("y_mm_from_bottom"))
        x_mm = _to_float(current.get("Row center x_mm"))
        if x_mm is None:
            x_mm = _to_float(current.get("x_mm"))
        strand_x_positions = str(current.get("Strand x positions mm") or "").strip()
        parsed_x_positions = _parse_explicit_x_positions(strand_x_positions, int(no_strands)) if strand_x_positions and no_strands > 0 else []
        if parsed_x_positions:
            strand_x_positions = _format_explicit_x_positions(parsed_x_positions)
        # Detailing aids are controlled by the selected standard strand size.
        # Current default convention: edge CL = 45 mm for both sizes; practical
        # minimum strand spacing = 50 mm for 12.7 mm strand and 55 mm for
        # 15.2 mm strand. These values are rounded-up detailing defaults that
        # satisfy the 3db minimum spacing check for the two supported sizes.
        edge_cl = float(strand_props["recommended_edge_cl_mm"])
        min_spacing = float(strand_props["recommended_min_spacing_mm"])
        if not strand_x_positions and no_strands > 0:
            strand_x_positions = _auto_strand_x_positions_text(int(no_strands), center_x_mm=0.0 if x_mm is None else float(x_mm), spacing_mm=min_spacing)
        pe_transfer = _to_float(current.get("Pe_transfer/strand_kN"))
        pe_construction = _to_float(current.get("Pe_construction/strand_kN"))
        pe_final = _to_float(current.get("Pe_eff_final/strand_kN"))
        raw_debond_pattern = "" if _is_blank(current.get("Debond pattern mm")) else str(current.get("Debond pattern mm")).strip()
        parsed_debond_pattern = _parse_debond_pattern_mm(raw_debond_pattern, int(no_strands)) if raw_debond_pattern else []
        normalized_debond_pattern = _format_debond_pattern_mm(parsed_debond_pattern) if parsed_debond_pattern else raw_debond_pattern
        rows.append(
            {
                "Active": active,
                "Group ID": group_id,
                "Layer": str(current.get("Layer") or "").strip(),
                "Strand Size": strand_size,
                "No. Strands": int(no_strands),
                "Area/Strand_mm2": area_per,
                "Total Aps_mm2": total_aps,
                "Row center x_mm": 0.0 if x_mm is None else x_mm,
                "Strand x positions mm": strand_x_positions,
                "y_mm_from_bottom": 0.0 if y_from_bottom is None else y_from_bottom,
                "Edge CL_mm": edge_cl,
                "Min spacing_mm": min_spacing,
                "Computed spacing_mm": _to_float(current.get("Computed spacing_mm")) or 0.0,
                "Pe_transfer/strand_kN": pe_transfer if pe_transfer is not None and pe_transfer >= 0.0 else _default_pe_transfer_per_strand_kn(strand_size),
                "Pe_construction/strand_kN": pe_construction if pe_construction is not None and pe_construction >= 0.0 else _default_pe_transfer_per_strand_kn(strand_size),
                "Pe_eff_final/strand_kN": pe_final if pe_final is not None and pe_final >= 0.0 else _default_pe_final_per_strand_kn(strand_size),
                "Left debond m": left_debond,
                "Right debond m": right_debond,
                "Debonded strand nos": explicit_debond_selection,
                "Debond pattern mm": normalized_debond_pattern,
                "Note": str(current.get("Note") or "").strip(),
            }
        )
    if _is_railway_u_girder_geometry(geometry) and debond_model == "Symmetric left/right":
        rows = _mirror_railway_u_girder_symmetric_debonding_rows(rows)
    return pd.DataFrame(rows, columns=GIRDER_STRAND_LAYOUT_COLUMNS)


def _active_girder_strand_layout_rows(table: pd.DataFrame | None) -> pd.DataFrame:
    df = pd.DataFrame(table)
    if df.empty:
        return pd.DataFrame(columns=GIRDER_STRAND_LAYOUT_COLUMNS)
    if "Active" in df.columns:
        df = df.loc[df["Active"].map(_to_bool_default_true)].copy()
    return df.reset_index(drop=True)


def _station_candidates_from_debonding(table: pd.DataFrame, span_length_m: float) -> list[float]:
    """Compatibility wrapper around the PS5A station-based prestress core."""

    return station_candidates_from_debonding(table, span_length_m)


def _strand_group_effective_at_station(row: pd.Series, x_m: float, span_length_m: float) -> bool:
    """Compatibility wrapper around the PS5A station-based prestress core."""

    return strand_group_effective_at_station(row.to_dict() if hasattr(row, "to_dict") else row, x_m, span_length_m)


def _section_horizontal_segments_at_y(geometry: SectionGeometry | None, y_abs_mm: float) -> list[tuple[float, float]]:
    """Return all concrete horizontal segments at a given absolute y."""

    if geometry is None:
        return []
    try:
        polygon = to_shapely_polygon(geometry)
        minx, miny, maxx, maxy = polygon.bounds
        if y_abs_mm < miny - 1e-9 or y_abs_mm > maxy + 1e-9:
            return []
        extension = max(maxx - minx, maxy - miny, 1000.0) * 2.0
        line = LineString([(minx - extension, y_abs_mm), (maxx + extension, y_abs_mm)])
        intersection = polygon.intersection(line)
        segments: list[tuple[float, float]] = []
        geoms = getattr(intersection, "geoms", [intersection])
        for geom in geoms:
            if geom.is_empty:
                continue
            if geom.geom_type == "LineString":
                xs = [coord[0] for coord in geom.coords]
                if xs:
                    segments.append((float(min(xs)), float(max(xs))))
            elif geom.geom_type == "Point":
                segments.append((float(geom.x), float(geom.x)))
        return sorted(segments, key=lambda item: item[0])
    except Exception:
        return []


def _section_horizontal_segment_at_y(geometry: SectionGeometry | None, y_abs_mm: float) -> tuple[float, float] | None:
    """Return the widest horizontal section segment at a given absolute y."""

    segments = _section_horizontal_segments_at_y(geometry, y_abs_mm)
    if not segments:
        return None
    return max(segments, key=lambda item: item[1] - item[0])


def _section_horizontal_segment_for_points_at_y(geometry: SectionGeometry | None, y_abs_mm: float, points_x: list[float]) -> tuple[float, float] | None:
    """Return the segment containing the strand points, or the widest segment."""

    segments = _section_horizontal_segments_at_y(geometry, y_abs_mm)
    if not segments:
        return None
    if points_x:
        x_min = min(points_x)
        x_max = max(points_x)
        for left, right in segments:
            if x_min >= left - 1e-9 and x_max <= right + 1e-9:
                return (left, right)
    return max(segments, key=lambda item: item[1] - item[0])


def _section_vertical_segments_at_x(geometry: SectionGeometry | None, x_abs_mm: float) -> list[tuple[float, float]]:
    """Return all concrete vertical segments at a given absolute x."""

    if geometry is None:
        return []
    try:
        polygon = to_shapely_polygon(geometry)
        minx, miny, maxx, maxy = polygon.bounds
        if x_abs_mm < minx - 1e-9 or x_abs_mm > maxx + 1e-9:
            return []
        extension = max(maxx - minx, maxy - miny, 1000.0) * 2.0
        line = LineString([(x_abs_mm, miny - extension), (x_abs_mm, maxy + extension)])
        intersection = polygon.intersection(line)
        segments: list[tuple[float, float]] = []
        geoms = getattr(intersection, "geoms", [intersection])
        for geom in geoms:
            if geom.is_empty:
                continue
            if geom.geom_type == "LineString":
                ys = [coord[1] for coord in geom.coords]
                if ys:
                    segments.append((float(min(ys)), float(max(ys))))
            elif geom.geom_type == "Point":
                segments.append((float(geom.y), float(geom.y)))
        return sorted(segments, key=lambda item: item[0])
    except Exception:
        return []


def _section_vertical_segment_for_points_at_x(geometry: SectionGeometry | None, x_abs_mm: float, points_y: list[float]) -> tuple[float, float] | None:
    """Return the vertical concrete segment containing the strand rows, or the tallest segment."""

    segments = _section_vertical_segments_at_x(geometry, x_abs_mm)
    if not segments:
        return None
    if points_y:
        y_min = min(points_y)
        y_max = max(points_y)
        for bottom, top in segments:
            if y_min >= bottom - 1e-9 and y_max <= top + 1e-9:
                return (bottom, top)
    return max(segments, key=lambda item: item[1] - item[0])


def _strand_point_clearance_review_messages(
    *,
    group: str,
    points_x: list[float],
    y_abs_mm: float,
    geometry: SectionGeometry | None,
    strand_radius_mm: float,
    required_edge_cl_mm: float,
) -> list[str]:
    """Return void-aware strand placement review messages for one row.

    GIRDER.PS4A is a geometry/QA gate only.  It checks the *individual strand
    circles* against the current concrete polygon, including internal voids and
    chamfers, but it does not change prestress forces, losses, PMM, SLS stress,
    or report logic.
    """

    if geometry is None or not points_x:
        return []
    try:
        polygon = to_shapely_polygon(geometry)
    except Exception:
        return [f"REVIEW: {group}: concrete polygon could not be resolved for void-aware strand validation."]

    center_outside_count = 0
    circle_outside_count = 0
    low_clearance_count = 0
    min_clearance: float | None = None
    for x_value in points_x:
        point = Point(float(x_value), float(y_abs_mm))
        if not polygon.covers(point):
            center_outside_count += 1
            continue
        clearance = float(polygon.boundary.distance(point))
        min_clearance = clearance if min_clearance is None else min(min_clearance, clearance)
        if clearance + 1e-9 < required_edge_cl_mm:
            low_clearance_count += 1
        strand_circle = point.buffer(float(strand_radius_mm), quad_segs=16)
        if not polygon.covers(strand_circle):
            circle_outside_count += 1

    messages: list[str] = []
    if center_outside_count:
        messages.append(
            f"REVIEW: {group}: {center_outside_count} strand center(s) fall outside concrete or inside a void/chamfer; "
            "reduce the number of strands or adjust the row elevation/center."
        )
    if circle_outside_count:
        messages.append(
            f"REVIEW: {group}: {circle_outside_count} strand diameter circle(s) overlap a concrete boundary, void, or chamfer; "
            "adjust row elevation/center or reduce the strand count."
        )
    if low_clearance_count and min_clearance is not None:
        messages.append(
            f"REVIEW: {group}: minimum strand centerline clearance to concrete boundary/void is {min_clearance:.1f} mm, "
            f"below the configured {required_edge_cl_mm:.1f} mm edge CL; confirm cover and void clearance."
        )
    return messages


def _strand_row_point_layout(row: pd.Series, geometry: SectionGeometry | None) -> tuple[list[dict[str, Any]], float, list[str]]:
    """Expand one strand row/group into individual strand points.

    Strand rows are placed from the girder centerline outward.  A two-strand
    row is therefore placed close to the centerline rather than stretched to
    the outer edges.  The selected strand size controls the practical minimum
    center-to-center spacing; section geometry is used to check width, cover,
    and void/chamfer clearance.
    """

    messages: list[str] = []
    group = str(row.get("Group ID") or "strand group")
    count = int(_to_float(row.get("No. Strands")) or 0)
    if count <= 0:
        return [], 0.0, messages
    y_from_bottom = float(_to_float(row.get("y_mm_from_bottom")) or 0.0)
    bottom_y = _section_bottom_y_from_geometry(geometry)
    y_abs = bottom_y + y_from_bottom
    center_x_value = _to_float(row.get("Row center x_mm"))
    if center_x_value is None:
        center_x_value = _to_float(row.get("x_mm"))
    center_x = float(0.0 if center_x_value is None else center_x_value)
    props = _strand_size_properties(row.get("Strand Size"))
    edge_cl = float(props["recommended_edge_cl_mm"])
    min_spacing = float(props["recommended_min_spacing_mm"])
    explicit_positions = _parse_explicit_x_positions(row.get("Strand x positions mm"), count)
    if explicit_positions:
        points_x = explicit_positions
        if count > 1:
            sorted_x = sorted(points_x)
            spacing = min(abs(sorted_x[i + 1] - sorted_x[i]) for i in range(len(sorted_x) - 1))
        else:
            spacing = 0.0
    else:
        spacing = min_spacing if count > 1 else 0.0
        offsets = [(float(i) - (float(count) - 1.0) / 2.0) * spacing for i in range(count)]
        points_x = [center_x + offset for offset in offsets]

    segment = _section_horizontal_segment_for_points_at_y(geometry, y_abs, points_x)
    if segment is not None:
        left_edge, right_edge = segment
        left_limit = left_edge + edge_cl
        right_limit = right_edge - edge_cl
        available_width = max(0.0, right_limit - left_limit)
        required_width = spacing * float(count - 1) if count > 1 else 0.0
        max_count = int(available_width // min_spacing) + 1 if available_width >= 0.0 else 1
        if center_x < left_limit - 1e-9 or center_x > right_limit + 1e-9:
            messages.append(f"REVIEW: {group}: row center is outside the available section width after 45 mm edge CL at this y-level.")
        if points_x and (min(points_x) < left_limit - 1e-9 or max(points_x) > right_limit + 1e-9):
            messages.append(
                f"REVIEW: {group}: {count} strands at {spacing:.1f} mm spacing do not fit within the available section width after 45 mm edge CL; "
                f"reduce the number of strands in this row"
                + (f" to {max_count} or fewer" if max_count > 0 else "")
                + " or adjust the row center/section width."
            )
        elif count > 1 and required_width > available_width + 1e-9:
            messages.append(
                f"REVIEW: {group}: strand row requires {required_width:.1f} mm but only {available_width:.1f} mm is available after edge CL; "
                f"reduce the number of strands in this row"
                + (f" to {max_count} or fewer" if max_count > 0 else "")
                + "."
            )
    else:
        messages.append(f"REVIEW: {group}: section width at this y-level could not be resolved; centered layout uses minimum spacing only.")

    messages.extend(
        _strand_point_clearance_review_messages(
            group=group,
            points_x=points_x,
            y_abs_mm=y_abs,
            geometry=geometry,
            strand_radius_mm=float(props["diameter_mm"]) / 2.0,
            required_edge_cl_mm=edge_cl,
        )
    )

    debonded_numbers = set(debonded_strand_numbers_for_row(row.to_dict() if hasattr(row, "to_dict") else row))
    drawing_pattern = _parse_debond_pattern_mm(row.get("Debond pattern mm"), count)
    if not drawing_pattern:
        drawing_pattern = [0 for _ in range(count)]
    points = [
        {
            "Group ID": group,
            "Strand no.": i + 1,
            "x_mm": points_x[i],
            "y_mm_abs": y_abs,
            "y_mm_from_bottom": y_from_bottom,
            "Computed spacing_mm": spacing,
            "Min spacing_mm": min_spacing,
            "Edge CL_mm": edge_cl,
            "Strand Size": str(row.get("Strand Size") or DEFAULT_GIRDER_STRAND_SIZE),
            "Debonded selected": (i + 1) in debonded_numbers,
            "Drawing debond length mm": int(drawing_pattern[i]) if i < len(drawing_pattern) else 0,
        }
        for i in range(count)
    ]
    return points, spacing, messages

def _girder_strand_point_layout_dataframe(table: pd.DataFrame, geometry: SectionGeometry | None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in _active_girder_strand_layout_rows(table).iterrows():
        points, _, _ = _strand_row_point_layout(row, geometry)
        rows.extend(points)
    return pd.DataFrame(rows)


def _apply_computed_girder_strand_spacing(table: pd.DataFrame, geometry: SectionGeometry | None) -> pd.DataFrame:
    df = pd.DataFrame(table).copy()
    if df.empty:
        return df
    for index, row in df.iterrows():
        _, spacing, _ = _strand_row_point_layout(row, geometry)
        df.at[index, "Computed spacing_mm"] = spacing
    return df

def _persist_girder_strand_layout_table(normalized_table: pd.DataFrame) -> None:
    """Persist the normalized girder strand table without forcing a rerun."""

    st.session_state["girder_strand_layout_table"] = pd.DataFrame(normalized_table).reset_index(drop=True)


def _data_editor_payload_to_dataframe(payload: Any, fallback_table: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a dataframe from a Streamlit data_editor return/state payload.

    ``st.data_editor`` returns a normal dataframe from the widget call, but the
    widget value stored under ``st.session_state[key]`` during ``on_change`` is a
    patch dictionary such as ``edited_rows`` / ``added_rows`` / ``deleted_rows``.
    Passing that patch dictionary directly to ``pd.DataFrame`` raises Pandas'
    ``Mixing dicts with non-Series`` ValueError.  This helper reconstructs the
    edited table from the canonical fallback table plus the patch payload.
    """

    if isinstance(payload, pd.DataFrame):
        return payload.reset_index(drop=True).copy()
    if payload is None:
        return pd.DataFrame(fallback_table).reset_index(drop=True).copy() if fallback_table is not None else pd.DataFrame()
    if isinstance(payload, list):
        return pd.DataFrame(payload).reset_index(drop=True)
    if not isinstance(payload, dict):
        return pd.DataFrame(payload).reset_index(drop=True)

    patch_keys = {"edited_rows", "added_rows", "deleted_rows"}
    if patch_keys.intersection(payload.keys()):
        df = pd.DataFrame(fallback_table).reset_index(drop=True).copy() if fallback_table is not None else pd.DataFrame()
        edited_rows = payload.get("edited_rows") or {}
        for raw_index, changes in edited_rows.items():
            try:
                row_index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if row_index < 0:
                continue
            while row_index >= len(df.index):
                df.loc[len(df.index)] = {column: None for column in df.columns}
            if isinstance(changes, dict):
                for column, value in changes.items():
                    if column not in df.columns:
                        df[column] = None
                    df.at[row_index, column] = value
        deleted_rows = payload.get("deleted_rows") or []
        delete_indices: list[int] = []
        for raw_index in deleted_rows:
            try:
                delete_indices.append(int(raw_index))
            except (TypeError, ValueError):
                continue
        if delete_indices and not df.empty:
            df = df.drop(index=[index for index in set(delete_indices) if index in df.index]).reset_index(drop=True)
        added_rows = payload.get("added_rows") or []
        if added_rows:
            df = pd.concat([df, pd.DataFrame(added_rows)], ignore_index=True)
        return df.reset_index(drop=True)

    try:
        return pd.DataFrame(payload).reset_index(drop=True)
    except ValueError:
        return pd.DataFrame([payload]).reset_index(drop=True)


def _sync_girder_strand_layout_editor_to_table(
    span_length_m: float,
    debond_model: str,
    geometry: SectionGeometry | None,
) -> None:
    """Persist current data-editor edits during the first edit callback."""

    edited = st.session_state.get("girder_strand_layout_editor")
    if edited is None:
        return
    current = st.session_state.get("girder_strand_layout_table")
    fallback = pd.DataFrame(current) if current is not None else None
    edited_df = _data_editor_payload_to_dataframe(edited, fallback)
    normalized = _normalize_girder_strand_layout_table(
        edited_df,
        span_length_m=float(span_length_m),
        debond_model=str(debond_model),
        geometry=geometry,
    )
    normalized = _apply_computed_girder_strand_spacing(normalized, geometry)
    _persist_girder_strand_layout_table(normalized)


def _store_girder_strand_layout_and_rerun_on_change(previous_table: pd.DataFrame | None, normalized_table: pd.DataFrame) -> None:
    """Persist normalized strand editor output without interrupting active edits.

    PS5B.1 deliberately avoids an immediate ``st.rerun()`` here.  PS5B.4 adds an
    ``on_change`` sync callback to persist the first data-editor edit before the
    next run.  This helper remains as the no-rerun persistence path for the
    already-returned edited dataframe.
    """

    _persist_girder_strand_layout_table(normalized_table)
    # Keep the historical helper name for regression compatibility, but avoid
    # programmatic reruns that steal focus from editable debond-length cells.
    _ = previous_table


def _girder_effective_prestress_preview_dataframe(table: pd.DataFrame, span_length_m: float) -> pd.DataFrame:
    """Return PS5A station preview of strand count, Pe(x), and yps(x).

    The calculation is owned by serviceability.girder_prestress_station so the
    solver-adjacent station logic is not embedded in Streamlit UI code.
    Transfer/development length transition and prestress losses are not modeled
    in this milestone.
    """

    return girder_prestress_station_dataframe(table, span_length_m=span_length_m)


def _debonded_strand_selection_review_message(row: pd.Series) -> str | None:
    raw = str(row.get("Debonded strand nos") or "").strip()
    if not raw:
        return None
    count = int(_to_float(row.get("No. Strands")) or 0)
    invalid: list[str] = []
    out_of_range: list[int] = []
    text = raw.replace(";", ",").replace(" ", ",")
    for token in [part.strip() for part in text.split(",") if part.strip()]:
        if "-" in token:
            parts = [part.strip() for part in token.split("-", 1)]
            try:
                start, end = int(parts[0]), int(parts[1])
            except (TypeError, ValueError):
                invalid.append(token)
                continue
            lo, hi = sorted((start, end))
            for value in range(lo, hi + 1):
                if value < 1 or value > count:
                    out_of_range.append(value)
            continue
        try:
            value = int(token)
        except (TypeError, ValueError):
            invalid.append(token)
            continue
        if value < 1 or value > count:
            out_of_range.append(value)
    selected = explicit_debonded_strand_numbers(row.to_dict())
    group = row.get("Group ID") or "strand group"
    if invalid:
        return f"{group}: invalid debonded strand token(s): {', '.join(invalid)}; use values like 1,2,18,19 or 1-4."
    if out_of_range:
        unique = ", ".join(str(value) for value in sorted(set(out_of_range)))
        return f"{group}: debonded strand number(s) {unique} are outside 1..{count}."
    if not selected:
        return f"{group}: debonded strand nos could not be parsed; use values like 1,2,18,19 or 1-4."
    return None


def _validate_girder_strand_layout(table: pd.DataFrame, *, span_length_m: float, geometry: SectionGeometry | None) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    active = _active_girder_strand_layout_rows(table)
    if active.empty:
        warnings.append("No active strand group is defined for the simple-supported girder layout.")
        return errors, warnings
    section_depth = None
    if geometry is not None:
        try:
            polygon = to_shapely_polygon(geometry)
            miny, maxy = polygon.bounds[1], polygon.bounds[3]
            section_depth = maxy - miny
        except Exception:
            section_depth = None
    for _, row in active.iterrows():
        group = str(row.get("Group ID") or "strand group")
        count = int(_to_float(row.get("No. Strands")) or 0)
        if count <= 0:
            errors.append(f"{group}: No. Strands must be greater than zero.")
        selection_message = _debonded_strand_selection_review_message(row)
        if selection_message:
            warnings.append(selection_message)
        left = float(_to_float(row.get("Left debond m")) or 0.0)
        right = float(_to_float(row.get("Right debond m")) or 0.0)
        if left + right >= span_length_m:
            errors.append(f"{group}: left + right debond length leaves no bonded zone within the span.")
        if left > span_length_m or right > span_length_m:
            errors.append(f"{group}: debond length must not exceed the span length.")
        y = float(_to_float(row.get("y_mm_from_bottom")) or 0.0)
        if y < 0.0:
            errors.append(f"{group}: y from bottom must not be negative.")
        if section_depth is not None and y > section_depth:
            warnings.append(f"{group}: y from bottom is outside the current section depth ({section_depth:.1f} mm).")
        raw_x_positions = str(row.get("Strand x positions mm") or "").strip()
        if raw_x_positions and count > 0 and not _parse_explicit_x_positions(raw_x_positions, count):
            warnings.append(
                f"{group}: x coordinates must contain exactly {count} numeric value(s); "
                "layout preview falls back to the row center and practical spacing until corrected."
            )
        raw_debond_pattern = "" if _is_blank(row.get("Debond pattern mm")) else str(row.get("Debond pattern mm")).strip()
        if raw_debond_pattern and count > 0 and not _parse_debond_pattern_mm(raw_debond_pattern, count):
            warnings.append(
                f"{group}: debond pattern must contain exactly {count} value(s), each one of 0/1000/2000/3000/4000/5000 mm. "
                "This drawing-symbol metadata is ignored until corrected."
            )
        _, _, row_layout_messages = _strand_row_point_layout(row, geometry)
        warnings.extend(row_layout_messages)
        pe_transfer = float(_to_float(row.get("Pe_transfer/strand_kN")) or 0.0)
        pe_final = float(_to_float(row.get("Pe_eff_final/strand_kN")) or 0.0)
        if pe_transfer > 0.0 and pe_final > pe_transfer:
            warnings.append(f"{group}: final effective Pe per strand exceeds transfer Pe per strand; confirm losses/force states.")
    support_preview = _girder_effective_prestress_preview_dataframe(active, span_length_m)
    if not support_preview.empty:
        first = support_preview.iloc[0]
        if float(first.get("Pe_transfer_eff_kN") or 0.0) <= 0.0:
            warnings.append("Transfer Pe at x=0 is zero in the debonding preview; support transfer stress may still need manual review.")
    return errors, warnings


def _debond_status_from_row(row: pd.Series | dict[str, Any]) -> tuple[str, str]:
    left = float(_to_float(row.get("Left debond m")) or 0.0)
    right = float(_to_float(row.get("Right debond m")) or 0.0)
    if left > 1e-9 and right > 1e-9:
        return "Debonded both ends", "diamond"
    if left > 1e-9:
        return "Left debonded", "triangle-left"
    if right > 1e-9:
        return "Right debonded", "triangle-right"
    return "Fully bonded", "circle"


def _girder_debonding_schedule_dataframe(table: pd.DataFrame, span_length_m: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in _active_girder_strand_layout_rows(table).iterrows():
        row_dict = row.to_dict()
        group = str(row.get("Group ID") or "strand group")
        count = int(_to_float(row.get("No. Strands")) or 0)
        left = min(max(float(_to_float(row.get("Left debond m")) or 0.0), 0.0), float(span_length_m))
        right = min(max(float(_to_float(row.get("Right debond m")) or 0.0), 0.0), float(span_length_m))
        bonded_start = left
        bonded_end = max(left, float(span_length_m) - right)
        status, _ = _debond_status_from_row(row)
        debonded_numbers = debonded_strand_numbers_for_row(row_dict)
        explicit_numbers = explicit_debonded_strand_numbers(row_dict)
        debonded_count = len(debonded_numbers)
        bonded_count = max(0, count - debonded_count)
        row_number = _strand_row_number_from_group_id(group)
        default_row_debond = _railway_u_girder_default_debond_length_for_row_m(row_number, span_length_m) if row_number is not None else None
        summary = "Bonded only"
        if debonded_count > 0:
            if abs(left - right) <= 1e-9:
                summary = f"{debonded_count} strand(s) @ {left:.3f} m each end"
            else:
                summary = f"{debonded_count} strand(s): left {left:.3f} m / right {right:.3f} m"
        rows.append(
            {
                "Group ID": group,
                "No. strands": count,
                "Bonded strands": bonded_count,
                "Debonded strands": debonded_count,
                "Debonded strand nos": ", ".join(str(value) for value in debonded_numbers) if debonded_numbers else "—",
                "Selection mode": "Individual" if explicit_numbers else ("Row-based all" if debonded_count else "None"),
                "Debond status": status,
                "Debond summary": summary,
                "Default row debond m": "—" if default_row_debond is None else f"{default_row_debond:.3f}",
                "Left debond m": left,
                "Right debond m": right,
                "Bonded zone m": f"{bonded_start:.3f} → {bonded_end:.3f}",
            }
        )
    return pd.DataFrame(rows)


def _render_girder_debonding_rule_dashboard(table: pd.DataFrame, span_length_m: float) -> None:
    """Render PS6A debonding QA without claiming code certification."""

    status = girder_debonding_preview_status(table, span_length_m=span_length_m)
    audit = girder_debonding_rule_audit_dataframe(table, span_length_m=span_length_m)
    critical = girder_critical_transfer_station_dataframe(table, span_length_m=span_length_m)
    active = _active_girder_strand_layout_rows(table)
    debonded_rows = 0
    max_debond = 0.0
    for _, row in active.iterrows():
        left = float(_to_float(row.get("Left debond m")) or 0.0)
        right = float(_to_float(row.get("Right debond m")) or 0.0)
        if left > 1e-9 or right > 1e-9:
            debonded_rows += 1
        max_debond = max(max_debond, left, right)
    tone = "ready" if status == "OK" else ("danger" if status == "ERROR" else "review")
    metrics = [
        PrestressMetric("Debonding QA", status, "Individual preview only", tone, strong=True),
        PrestressMetric("Debonded rows", f"{debonded_rows} / {len(active)}", "Active row groups", "info"),
        PrestressMetric("Max debond length", f"{max_debond:.3f} m", f"L/5 = {span_length_m / 5.0:.3f} m", "neutral"),
        PrestressMetric("Critical stations", str(len(critical.index)), "End faces + sleeve transitions", "info"),
    ]
    st.markdown(_metric_strip_html(metrics), unsafe_allow_html=True)
    if status == "ERROR":
        st.error("Debonding QA found preview input errors. Review before using the prestress preview.")
    elif status == "REVIEW":
        st.warning("Debonding QA requires engineering review. This is not a final AASHTO/ACI code-certified debonding check.")
    else:
        st.success("Debonding QA preview has no input errors. Final code-certified checks and auto-recommendation are still future milestones.")

    with st.expander("Debonding rule audit — individual preview", expanded=status != "OK"):
        st.dataframe(audit, use_container_width=True, hide_index=True)
        st.caption(
            "PS6A can use optional individual strand numbers within each row for preview ratio checks. "
            "Blank debonded strand numbers preserve PS5 row-based all-strands behavior for backward compatibility. This is still not a final code-certified debonding check."
        )
    with st.expander("Critical transfer station audit", expanded=False):
        st.dataframe(critical, use_container_width=True, hide_index=True)
        st.caption(
            "Critical stations are prepared for future transfer stress checks. "
            "Transfer-length force build-up after sleeve transitions is not modeled in this milestone."
        )


def _apply_girder_advisory_debonding_recommendation(
    table: pd.DataFrame,
    recommendation: pd.DataFrame,
    *,
    span_length_m: float,
    debond_model: str,
    geometry: SectionGeometry | None,
) -> pd.DataFrame:
    """Apply PS6B advisory recommendation to a copy of the strand layout table."""

    updated = pd.DataFrame(table).copy()
    if updated.empty or recommendation.empty:
        return _normalize_girder_strand_layout_table(updated, span_length_m=span_length_m, debond_model=debond_model, geometry=geometry)
    recommendation_by_group = {str(row.get("Group ID") or ""): row.to_dict() for _, row in recommendation.iterrows()}
    for index, row in updated.iterrows():
        group = str(row.get("Group ID") or "")
        rec = recommendation_by_group.get(group)
        if rec is None:
            continue
        selected = str(rec.get("Recommended debonded strand nos") or "").strip()
        count = int(_to_float(rec.get("Recommended count")) or 0)
        if count <= 0 or selected in {"", "—"}:
            continue
        updated.at[index, "Debonded strand nos"] = selected
        updated.at[index, "Left debond m"] = float(_to_float(rec.get("Left debond m")) or 0.0)
        updated.at[index, "Right debond m"] = float(_to_float(rec.get("Right debond m")) or 0.0)
        note = str(row.get("Note") or "").strip()
        advisory_note = "PS6B advisory candidate applied; verify final code checks."
        updated.at[index, "Note"] = advisory_note if not note else f"{note} | {advisory_note}"
    normalized = _normalize_girder_strand_layout_table(updated, span_length_m=span_length_m, debond_model=debond_model, geometry=geometry)
    normalized = _apply_computed_girder_strand_spacing(normalized, geometry)
    return normalized


def _render_girder_advisory_debonding_recommendation(
    table: pd.DataFrame,
    *,
    span_length_m: float,
    debond_model: str,
    geometry: SectionGeometry | None,
) -> None:
    """Render PS6B code-aware advisory recommendation workflow."""

    st.markdown("#### Code-aware advisory debonding recommendation")
    st.caption(
        "PS6B proposes candidate debonded strand pairs using code guardrails only: total ≤25%, per-row ≤40%, symmetric outer pairs, and debond length ≤L/5. "
        "It is not a final automatic design; transfer stress, development, shear, end-zone reinforcement, and loss checks remain engineering review items."
    )
    col1, col2 = st.columns([1, 2])
    with col1:
        max_pairs = st.number_input(
            "Max symmetric pairs per row",
            min_value=1,
            max_value=3,
            value=1,
            step=1,
            key="girder_ps6b_max_pairs_per_row",
            help="Conservative starter: one outer pair per eligible row. Increase only for advisory exploration.",
        )
    with col2:
        st.info(
            "Recommendation order is bottom row upward. The app does not claim final PASS; it only prepares a reviewable candidate layout.",
            icon="ℹ️",
        )

    generated = girder_advisory_debonding_recommendation_dataframe(
        table,
        span_length_m=span_length_m,
        max_pairs_per_row=int(max_pairs),
    )
    proposed_count = int(generated.get("Recommended count", pd.Series(dtype=float)).sum()) if not generated.empty else 0
    total_strands = int(_active_girder_strand_layout_rows(table).get("No. Strands", pd.Series(dtype=float)).sum()) if not _active_girder_strand_layout_rows(table).empty else 0
    ratio = proposed_count / total_strands if total_strands > 0 else 0.0
    metrics = [
        PrestressMetric("Advisory status", "PREVIEW", "Code guardrails only", "review", strong=True),
        PrestressMetric("Proposed debonded", f"{proposed_count} / {total_strands}", f"ratio = {ratio:.1%}", "info"),
        PrestressMetric("Total limit", f"≤ {int(total_strands * 0.25)} strands", "25% preview guardrail", "neutral"),
        PrestressMetric("Length limit", f"≤ {span_length_m / 5.0:.3f} m", "L/5 preview guardrail", "neutral"),
    ]
    st.markdown(_metric_strip_html(metrics), unsafe_allow_html=True)
    st.dataframe(generated, use_container_width=True, hide_index=True)
    st.warning(
        "This is an advisory starter layout, not final code-certified debonding design. Apply only after engineering review.",
        icon="⚠️",
    )
    if proposed_count <= 0:
        st.info("No candidate strands were selected by the conservative code-aware starter rule.")
        return
    if st.button("Apply advisory layout to strand table", type="primary", key="girder_ps6b_apply_advisory_layout"):
        applied = _apply_girder_advisory_debonding_recommendation(
            table,
            generated,
            span_length_m=span_length_m,
            debond_model=debond_model,
            geometry=geometry,
        )
        _persist_girder_strand_layout_table(applied)
        st.session_state.pop("girder_strand_layout_editor", None)
        st.success("Advisory debonding layout applied to the strand table. Re-check Debonding QA before using results.")
        rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()



def _girder_strand_cross_section_row_info(table: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Return row-level strand/debond metadata used by cross-section dashboards."""

    row_info: dict[str, dict[str, Any]] = {}
    active_rows = _active_girder_strand_layout_rows(table)
    if active_rows.empty:
        return row_info
    for _, row in active_rows.iterrows():
        group = str(row.get("Group ID") or "strand group")
        row_dict = row.to_dict()
        status, _ = _debond_status_from_row(row)
        left = float(_to_float(row.get("Left debond m")) or 0.0)
        right = float(_to_float(row.get("Right debond m")) or 0.0)
        count = int(_to_float(row.get("No. Strands")) or 0)
        debonded_numbers = tuple(debonded_strand_numbers_for_row(row_dict))
        explicit_numbers = tuple(explicit_debonded_strand_numbers(row_dict))
        row_info[group] = {
            "status": status,
            "left": left,
            "right": right,
            "count": count,
            "debonded_numbers": debonded_numbers,
            "explicit": bool(explicit_numbers),
            "group": group,
        }
    return row_info


def _strand_cross_section_hover(point: pd.Series, row_info: dict[str, dict[str, Any]]) -> str:
    """Return compact hover text for strand dashboard plots."""

    group = str(point.get("Group ID") or "strand group")
    info = row_info.get(group, {"status": "Fully bonded", "left": 0.0, "right": 0.0})
    state = "Debonded" if bool(point.get("Debonded selected")) else "Bonded"
    details = [
        f"{group} · strand #{int(float(point.get('Strand no.') or 0))}",
        f"State = {state}",
        f"x = {float(point.get('x_mm') or 0.0):.1f} mm",
        f"y = {float(point.get('y_mm_abs') or 0.0):.1f} mm",
    ]
    drawing_length = int(float(point.get("Drawing debond length mm") or 0.0))
    if drawing_length > 0:
        details.append(f"Drawing debond symbol = {drawing_length} mm")
    left = float(info.get("left") or 0.0)
    right = float(info.get("right") or 0.0)
    if left > 1e-9 or right > 1e-9:
        details.append(f"Row status = {info.get('status') or 'Review'}")
        details.append(f"Debond L/R = {left:.3f} / {right:.3f} m")
    return "<br>".join(details)


def _add_concrete_schematic_trace(
    fig: go.Figure,
    geometry: SectionGeometry | None,
    *,
    showlegend: bool = True,
    fillcolor: str = "rgba(15, 76, 129, 0.055)",
    linecolor: str = "rgba(15, 76, 129, 0.58)",
    linewidth: float = 1.6,
) -> tuple[float, float, float, float] | None:
    """Add a low-contrast concrete outline and return polygon bounds."""

    if geometry is None:
        return None
    try:
        polygon = to_shapely_polygon(geometry)
    except Exception:
        return None
    try:
        x, y = polygon.exterior.xy
        fig.add_trace(
            go.Scatter(
                x=list(x),
                y=list(y),
                mode="lines",
                fill="toself",
                fillcolor=fillcolor,
                line={"color": linecolor, "width": linewidth},
                name="Concrete",
                hoverinfo="skip",
                showlegend=showlegend,
            )
        )
        for index, interior in enumerate(polygon.interiors, start=1):
            hx, hy = interior.xy
            fig.add_trace(
                go.Scatter(
                    x=list(hx),
                    y=list(hy),
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(255,255,255,0.98)",
                    line={"color": "rgba(15, 76, 129, 0.50)", "width": max(1.0, linewidth - 0.2), "dash": "solid"},
                    name=f"Void {index}",
                    hoverinfo="skip",
                    showlegend=False,
                    xaxis=xaxis_name,
                    yaxis=yaxis_name,
                )
            )
        minx, miny, maxx, maxy = polygon.bounds
        return float(minx), float(miny), float(maxx), float(maxy)
    except Exception:
        return None


def _add_strand_state_marker_traces(
    fig: go.Figure,
    points: pd.DataFrame,
    row_info: dict[str, dict[str, Any]],
    *,
    marker_size: int,
    bonded_fill: str,
    debonded_fill: str,
    bonded_line: str = "#2563eb",
    debonded_line: str = "#dc2626",
    bonded_width: float = 1.8,
    debonded_width: float = 2.0,
    showlegend: bool = True,
    xaxis_name: str = "x",
    yaxis_name: str = "y",
) -> None:
    """Add bonded/debonded strand markers as two clean Plotly traces."""

    if points.empty:
        return
    state_defs = [
        (False, "Bonded", bonded_fill, bonded_line, bonded_width),
        (True, "Debonded", debonded_fill, debonded_line, debonded_width),
    ]
    for debonded, name, fill, line, width in state_defs:
        selected = points.loc[points["Debonded selected"].fillna(False).astype(bool) == debonded].copy()
        if selected.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=selected["x_mm"].astype(float).tolist(),
                y=selected["y_mm_abs"].astype(float).tolist(),
                mode="markers",
                marker={
                    "size": marker_size,
                    "color": fill,
                    "symbol": "circle",
                    "line": {"color": line, "width": width},
                },
                name=name,
                text=[_strand_cross_section_hover(point, row_info) for _, point in selected.iterrows()],
                hovertemplate="%{text}<extra></extra>",
                showlegend=showlegend,
                xaxis=xaxis_name,
                yaxis=yaxis_name,
            )
        )


def _add_drawing_debond_symbol_trace(
    fig: go.Figure,
    points: pd.DataFrame,
    *,
    marker_size: int = 8,
    showlegend: bool = False,
    xaxis_name: str = "x",
    yaxis_name: str = "y",
) -> None:
    """Add lightweight drawing-symbol overlays only when drawing metadata exists."""

    if points.empty or "Drawing debond length mm" not in points.columns:
        return
    drawing_symbol_traces: dict[int, list[tuple[float, float, str]]] = {}
    for _, point in points.iterrows():
        drawing_length = int(float(point.get("Drawing debond length mm") or 0.0))
        if drawing_length <= 0:
            continue
        drawing_symbol_traces.setdefault(drawing_length, []).append(
            (
                float(point["x_mm"]),
                float(point["y_mm_abs"]),
                f"{point['Group ID']} #{int(point['Strand no.'])}<br>Drawing debond = {drawing_length} mm",
            )
        )
    for drawing_length in sorted(drawing_symbol_traces):
        label, symbol = RAILWAY_U_GIRDER_DEBOND_SYMBOLS_MM.get(drawing_length, (f"Debonded at {drawing_length} mm", "x-open"))
        trace_points = drawing_symbol_traces[drawing_length]
        fig.add_trace(
            go.Scatter(
                x=[item[0] for item in trace_points],
                y=[item[1] for item in trace_points],
                mode="markers",
                marker={
                    "size": marker_size,
                    "color": "rgba(15, 23, 42, 0.64)",
                    "symbol": symbol,
                    "line": {"color": "rgba(15, 23, 42, 0.66)", "width": 0.9},
                },
                name=label,
                text=[item[2] for item in trace_points],
                hovertemplate="%{text}<br>x=%{x:.1f} mm<br>y=%{y:.1f} mm<extra></extra>",
                showlegend=showlegend,
                xaxis=xaxis_name,
                yaxis=yaxis_name,
            )
        )


def _strand_block_side_label(points: pd.DataFrame) -> str:
    """Return a compact left/right/all label for a subset of strand points."""

    if points.empty or "x_mm" not in points.columns:
        return "All"
    x_min = float(points["x_mm"].min())
    x_max = float(points["x_mm"].max())
    if x_max < 0.0:
        return "Left"
    if x_min > 0.0:
        return "Right"
    return "All"


def _girder_strand_row_summary_dataframe(table: pd.DataFrame, geometry: SectionGeometry | None) -> pd.DataFrame:
    """Return the dashboard row summary shown beside the overall schematic."""

    points = _girder_strand_point_layout_dataframe(table, geometry)
    if points.empty:
        return pd.DataFrame(
            columns=[
                "Row",
                "Side groups",
                "Total strands",
                "Bonded",
                "Debonded",
                "Left debond (m)",
                "Right debond (m)",
                "Selection",
            ]
        )
    row_info = _girder_strand_cross_section_row_info(table)
    buckets: dict[tuple[int, float], dict[str, Any]] = {}
    for group, group_points in points.groupby("Group ID", as_index=False):
        group_name = str(group)
        y_value = round(float(group_points["y_mm_abs"].mean()), 6)
        row_number = _strand_row_number_from_group_id(group_name)
        sort_number = int(row_number) if row_number is not None else len(buckets) + 1
        key = (sort_number, y_value)
        info = row_info.get(group_name, {"left": 0.0, "right": 0.0, "explicit": False})
        debonded_count = int(group_points["Debonded selected"].fillna(False).astype(bool).sum())
        total_count = int(len(group_points.index))
        bucket = buckets.setdefault(
            key,
            {
                "row_number": row_number,
                "groups": [],
                "total": 0,
                "bonded": 0,
                "debonded": 0,
                "left": 0.0,
                "right": 0.0,
                "explicit": False,
            },
        )
        bucket["groups"].append(group_name)
        bucket["total"] += total_count
        bucket["bonded"] += max(0, total_count - debonded_count)
        bucket["debonded"] += debonded_count
        bucket["left"] = max(float(bucket["left"]), float(info.get("left") or 0.0))
        bucket["right"] = max(float(bucket["right"]), float(info.get("right") or 0.0))
        bucket["explicit"] = bool(bucket["explicit"]) or bool(info.get("explicit"))

    rows: list[dict[str, Any]] = []
    for key in sorted(buckets):
        bucket = buckets[key]
        groups = [str(item) for item in bucket["groups"]]
        if bucket["row_number"] is not None:
            row_label = f"Row {int(bucket['row_number'])}"
        else:
            normalized_names = [name.replace("L ", "").replace("R ", "") for name in groups]
            row_label = normalized_names[0] if len(set(normalized_names)) == 1 else " / ".join(groups)
        selection = "Individual" if bool(bucket["explicit"]) else ("Row fallback" if int(bucket["debonded"]) else "None")
        rows.append(
            {
                "Row": row_label,
                "Side groups": " / ".join(groups),
                "Total strands": int(bucket["total"]),
                "Bonded": int(bucket["bonded"]),
                "Debonded": int(bucket["debonded"]),
                "Left debond (m)": float(bucket["left"]),
                "Right debond (m)": float(bucket["right"]),
                "Selection": selection,
            }
        )
    return pd.DataFrame(rows)


def _should_split_girder_strand_detail(points: pd.DataFrame, geometry: SectionGeometry | None) -> bool:
    """Return True only for layouts that need separate left/right strand-detail panels.

    The split detail dashboard is intended for physically separated strand
    pockets such as Railway U-Girder webs.  Symmetric bottom clusters in I-,
    plank-, and box-style girders stay merged so the user reads one complete
    strand block rather than two artificial halves.
    """

    if points.empty or "x_mm" not in points.columns:
        return False
    if not _is_railway_u_girder_geometry(geometry):
        return False
    left_exists = bool((points["x_mm"].astype(float) < 0.0).any())
    right_exists = bool((points["x_mm"].astype(float) > 0.0).any())
    return left_exists and right_exists


def _format_dimension_mm(value: float | int | None) -> str:
    """Return compact millimetre text for detail dimensions."""

    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(numeric - round(numeric)) < 0.05:
        return f"{int(round(numeric))}"
    return f"{numeric:.1f}"


def _add_detail_dimension_line(
    fig: go.Figure,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    label: str,
    orientation: str,
    tick_length: float,
    font_size: int = 9,
    xref: str = "x",
    yref: str = "y",
) -> None:
    """Add a restrained engineering dimension line to a strand detail figure."""

    if not label:
        return
    if abs(float(x1) - float(x0)) < 1e-9 and abs(float(y1) - float(y0)) < 1e-9:
        return
    color = "rgba(180,83,9,0.90)"
    fig.add_shape(
        type="line",
        x0=float(x0),
        x1=float(x1),
        y0=float(y0),
        y1=float(y1),
        xref=xref,
        yref=yref,
        line={"color": color, "width": 1.0},
        layer="above",
    )
    if orientation == "h":
        for x_value in (float(x0), float(x1)):
            fig.add_shape(
                type="line",
                x0=x_value,
                x1=x_value,
                y0=float(y0) - tick_length / 2.0,
                y1=float(y0) + tick_length / 2.0,
                xref=xref,
                yref=yref,
                line={"color": color, "width": 1.0},
                layer="above",
            )
    else:
        for y_value in (float(y0), float(y1)):
            fig.add_shape(
                type="line",
                x0=float(x0) - tick_length / 2.0,
                x1=float(x0) + tick_length / 2.0,
                y0=y_value,
                y1=y_value,
                xref=xref,
                yref=yref,
                line={"color": color, "width": 1.0},
                layer="above",
            )
    fig.add_annotation(
        x=(float(x0) + float(x1)) / 2.0,
        y=(float(y0) + float(y1)) / 2.0,
        xref=xref,
        yref=yref,
        text=label,
        showarrow=False,
        font={"size": font_size, "color": "rgba(146,64,14,0.98)"},
        bgcolor="rgba(255,255,255,0.90)",
        bordercolor="rgba(251,191,36,0.55)",
        borderwidth=1,
        borderpad=2,
    )



def _iter_polygon_geometries(geometry_object: Any) -> list[Any]:
    """Return polygon members from a shapely geometry object."""

    if geometry_object is None or getattr(geometry_object, "is_empty", True):
        return []
    geom_type = getattr(geometry_object, "geom_type", "")
    if geom_type == "Polygon":
        return [geometry_object]
    polygons: list[Any] = []
    for member in getattr(geometry_object, "geoms", []) or []:
        polygons.extend(_iter_polygon_geometries(member))
    return polygons


def _local_strand_zone_geometry(
    points: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    side: str = "All",
    full_section: bool = False,
) -> tuple[Any | None, tuple[float, float, float, float] | None]:
    """Return the concrete envelope used by the strand-detail panel.

    Non-split girder sections should read against the full section outline so
    the strand group is understood in its true structural context.  Railway
    U-Girder split views instead show a clipped left/right web detail rather
    than a tiny strand cluster floating inside a full-width plot.
    """

    if geometry is None or points.empty:
        return None, None
    try:
        polygon = to_shapely_polygon(geometry)
    except Exception:
        return None, None
    if polygon.is_empty:
        return None, None

    section_minx, section_miny, section_maxx, section_maxy = [float(value) for value in polygon.bounds]
    if full_section:
        return polygon, (section_minx, section_miny, section_maxx, section_maxy)

    strand_xs = [float(value) for value in points["x_mm"].astype(float).tolist()]
    strand_ys = [float(value) for value in points["y_mm_abs"].astype(float).tolist()]
    if not strand_xs or not strand_ys:
        return None, None

    y_values = sorted({round(value, 6) for value in strand_ys})
    side_key = str(side or "All").strip().lower()

    if side_key in {"left", "right"}:
        # Split detail panels are intended to show a single web/block region,
        # not the full girder width.  Use the strand spread itself as the local
        # x-anchor because some sections (notably Railway U-Girder) have a
        # continuous floor slab at the strand y-level that would otherwise pull
        # the clipping window across the entire section.  Keep the bottom fiber
        # visible, but crop the upper part of the web so row spacing and
        # dimension labels remain legible.
        x0 = min(strand_xs)
        x1 = max(strand_xs)
        x_pad = max(90.0, 0.24 * max(x1 - x0, 120.0))
        x0 = max(section_minx, x0 - x_pad)
        x1 = min(section_maxx, x1 + x_pad)
        if x1 - x0 < 200.0:
            mid_x = (x0 + x1) / 2.0
            x0 = max(section_minx, mid_x - 100.0)
            x1 = min(section_maxx, mid_x + 100.0)
        section_depth = max(section_maxy - section_miny, 1.0)
        y0 = section_miny
        # Final split-detail crop: keep enough web boundary for orientation, but
        # reduce unused headroom so the strand grid and labels remain dominant.
        y1 = min(section_maxy, max(strand_ys) + max(165.0, 0.105 * section_depth))
        if y1 - y0 < 340.0:
            y1 = min(section_maxy, y0 + 340.0)
        clip = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        try:
            clipped = polygon.intersection(clip)
        except Exception:
            return None, (x0, y0, x1, y1)
        return clipped, (x0, y0, x1, y1)

    horizontal_segments: list[tuple[float, float]] = []
    for y_value in y_values:
        row_points = points.loc[(points["y_mm_abs"].astype(float) - float(y_value)).abs() < 1e-6]
        segment = _section_horizontal_segment_for_points_at_y(
            geometry,
            float(y_value),
            [float(value) for value in row_points["x_mm"].astype(float).tolist()],
        )
        if segment is not None:
            horizontal_segments.append((float(segment[0]), float(segment[1])))

    if horizontal_segments:
        x0 = min(left for left, _ in horizontal_segments)
        x1 = max(right for _, right in horizontal_segments)
    else:
        strand_span = max(max(strand_xs) - min(strand_xs), 120.0)
        x_pad = max(80.0, 0.22 * strand_span)
        x0 = min(strand_xs) - x_pad
        x1 = max(strand_xs) + x_pad
    x0 = max(section_minx, float(x0))
    x1 = min(section_maxx, float(x1))
    if x1 - x0 < 80.0:
        mid_x = (x0 + x1) / 2.0
        x0 = max(section_minx, mid_x - 40.0)
        x1 = min(section_maxx, mid_x + 40.0)

    block_center_x = (min(strand_xs) + max(strand_xs)) / 2.0
    vertical_segment = _section_vertical_segment_for_points_at_x(geometry, block_center_x, y_values)
    if vertical_segment is not None:
        y0 = float(vertical_segment[0])
    else:
        y0 = section_miny

    strand_height = max(max(strand_ys) - min(strand_ys), 80.0)
    top_pad = max(90.0, 0.18 * strand_height)
    y1 = min(section_maxy, max(strand_ys) + top_pad)
    if section_maxy - y1 < max(70.0, 0.08 * max(section_maxy - section_miny, 1.0)):
        y1 = section_maxy
    if y1 - y0 < 120.0:
        y1 = min(section_maxy, y0 + 120.0)
    if y1 <= y0:
        y0 = min(strand_ys) - 60.0
        y1 = max(strand_ys) + 90.0

    clip = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
    try:
        clipped = polygon.intersection(clip)
    except Exception:
        return None, (x0, y0, x1, y1)
    return clipped, (x0, y0, x1, y1)


def _add_local_concrete_zone_trace(
    fig: go.Figure,
    points: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    side: str = "All",
    full_section: bool = False,
    xaxis_name: str = "x",
    yaxis_name: str = "y",
) -> tuple[float, float, float, float] | None:
    """Add the concrete envelope used by the zoomed strand-detail panel."""

    clipped, fallback_bounds = _local_strand_zone_geometry(points, geometry, side=side, full_section=full_section)
    polygons = _iter_polygon_geometries(clipped)
    if not polygons:
        return fallback_bounds

    minx_values: list[float] = []
    miny_values: list[float] = []
    maxx_values: list[float] = []
    maxy_values: list[float] = []
    for index, polygon in enumerate(polygons):
        x, y = polygon.exterior.xy
        fig.add_trace(
            go.Scatter(
                x=list(x),
                y=list(y),
                mode="lines",
                fill="toself",
                fillcolor="rgba(15, 76, 129, 0.035)",
                line={"color": "rgba(15, 76, 129, 0.42)", "width": 1.15},
                name="Local concrete envelope" if index == 0 else "Local concrete envelope part",
                hoverinfo="skip",
                showlegend=False,
                xaxis=xaxis_name,
                yaxis=yaxis_name,
            )
        )
        for interior_index, interior in enumerate(polygon.interiors, start=1):
            hx, hy = interior.xy
            fig.add_trace(
                go.Scatter(
                    x=list(hx),
                    y=list(hy),
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(255,255,255,0.98)",
                    line={"color": "rgba(15, 76, 129, 0.35)", "width": 1.0},
                    name=f"Local void {interior_index}",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        minx, miny, maxx, maxy = [float(value) for value in polygon.bounds]
        minx_values.append(minx)
        miny_values.append(miny)
        maxx_values.append(maxx)
        maxy_values.append(maxy)
    return min(minx_values), min(miny_values), max(maxx_values), max(maxy_values)

def _is_deep_web_non_u_detail(points: pd.DataFrame, geometry: SectionGeometry | None) -> bool:
    """Return True for non-U sections that need a lower-zone focused detail view."""

    if geometry is None or points.empty or _is_railway_u_girder_geometry(geometry):
        return False
    try:
        polygon = to_shapely_polygon(geometry)
    except Exception:
        return False
    if polygon.is_empty:
        return False
    _, section_miny, _, section_maxy = [float(value) for value in polygon.bounds]
    section_depth = max(section_maxy - section_miny, 1.0)
    strand_top = float(points["y_mm_abs"].astype(float).max())
    lower_zone_depth = max(strand_top - section_miny, 1.0)
    top_headroom = max(0.0, section_maxy - strand_top)
    return (section_depth / lower_zone_depth) >= 1.65 and (top_headroom / section_depth) >= 0.48


def _add_non_split_section_context_trace(
    fig: go.Figure,
    points: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    lower_focused: bool,
) -> tuple[float, float, float, float] | None:
    """Add full or lower-focused context geometry for non-split strand details."""

    if geometry is None:
        return None
    try:
        polygon = to_shapely_polygon(geometry)
    except Exception:
        return None
    if polygon.is_empty:
        return None

    section_minx, section_miny, section_maxx, section_maxy = [float(value) for value in polygon.bounds]
    rendered = polygon
    bounds = (section_minx, section_miny, section_maxx, section_maxy)

    if lower_focused and not points.empty:
        strand_top = float(points["y_mm_abs"].astype(float).max())
        strand_bottom = float(points["y_mm_abs"].astype(float).min())
        strand_left = float(points["x_mm"].astype(float).min())
        strand_right = float(points["x_mm"].astype(float).max())
        section_depth = max(section_maxy - section_miny, 1.0)
        strand_band_depth = max(strand_top - strand_bottom, 60.0)
        y0 = section_miny
        y1 = min(section_maxy, strand_top + max(92.0, 0.065 * section_depth, 1.35 * strand_band_depth))
        if y1 - y0 < 225.0:
            y1 = min(section_maxy, y0 + 225.0)

        segment = _section_horizontal_segment_for_points_at_y(
            geometry,
            float(points["y_mm_abs"].astype(float).min()),
            points["x_mm"].astype(float).tolist(),
        )
        if segment is not None:
            local_left, local_right = float(segment[0]), float(segment[1])
        else:
            local_left, local_right = section_minx, section_maxx
        local_width = max(local_right - local_left, strand_right - strand_left, 120.0)
        pad_x = max(36.0, 0.075 * local_width)
        x0 = max(section_minx, local_left - pad_x)
        x1 = min(section_maxx, local_right + pad_x)
        if x1 - x0 < max(220.0, local_width + 2.0 * pad_x):
            mid_x = 0.5 * (x0 + x1)
            half = 0.5 * max(220.0, local_width + 2.0 * pad_x)
            x0 = max(section_minx, mid_x - half)
            x1 = min(section_maxx, mid_x + half)

        clip = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        try:
            rendered = polygon.intersection(clip)
            bounds = (x0, y0, x1, y1)
        except Exception:
            rendered = polygon
            bounds = (section_minx, section_miny, section_maxx, section_maxy)

    polygons = _iter_polygon_geometries(rendered)
    if not polygons:
        return bounds
    minx_values: list[float] = []
    miny_values: list[float] = []
    maxx_values: list[float] = []
    maxy_values: list[float] = []
    for index, poly in enumerate(polygons):
        x, y = poly.exterior.xy
        fig.add_trace(
            go.Scatter(
                x=list(x),
                y=list(y),
                mode="lines",
                fill="toself",
                fillcolor="rgba(15, 76, 129, 0.035)",
                line={"color": "rgba(15, 76, 129, 0.42)", "width": 1.15},
                name="Full section context" if index == 0 else "Full section context part",
                hoverinfo="skip",
                showlegend=False,
            )
        )
        for interior_index, interior in enumerate(poly.interiors, start=1):
            hx, hy = interior.xy
            fig.add_trace(
                go.Scatter(
                    x=list(hx),
                    y=list(hy),
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(255,255,255,0.98)",
                    line={"color": "rgba(15, 76, 129, 0.35)", "width": 1.0},
                    name=f"Section void {interior_index}",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        minx, miny, maxx, maxy = [float(value) for value in poly.bounds]
        minx_values.append(minx)
        miny_values.append(miny)
        maxx_values.append(maxx)
        maxy_values.append(maxy)
    return min(minx_values), min(miny_values), max(maxx_values), max(maxy_values)

def _strand_detail_dimension_references(
    points: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    side: str = "All",
    full_section: bool = False,
) -> dict[str, Any]:
    """Return representative x/y spacing and edge references for strand-detail panels."""

    refs: dict[str, Any] = {"x_values": [], "y_values": []}
    if points.empty:
        return refs
    y_values = sorted({round(float(value), 6) for value in points["y_mm_abs"].astype(float).tolist()})
    refs["row_y_values"] = y_values
    x_min = float(points["x_mm"].min())
    x_max = float(points["x_mm"].max())
    y_min = float(points["y_mm_abs"].min())
    y_max = float(points["y_mm_abs"].max())
    refs["x_values"].extend([x_min, x_max])
    refs["y_values"].extend([y_min, y_max])
    _, local_bounds = _local_strand_zone_geometry(points, geometry, side=side, full_section=full_section)
    if local_bounds is not None:
        refs["local_bounds"] = tuple(float(value) for value in local_bounds)
        refs["x_values"].extend([float(local_bounds[0]), float(local_bounds[2])])
        refs["y_values"].extend([float(local_bounds[1]), float(local_bounds[3])])

    bottom_row_y = y_values[0] if y_values else y_min
    bottom_row = points.loc[(points["y_mm_abs"].astype(float) - bottom_row_y).abs() < 1e-6].copy()
    bottom_xs = sorted(float(value) for value in bottom_row["x_mm"].astype(float).tolist())
    refs["bottom_row_y"] = bottom_row_y
    refs["bottom_row_xs"] = bottom_xs

    if bottom_xs:
        segment = _section_horizontal_segment_for_points_at_y(geometry, bottom_row_y, bottom_xs)
        if segment is not None:
            refs["bottom_row_segment"] = segment
            refs["x_values"].extend([float(segment[0]), float(segment[1])])

    block_center_x = (x_min + x_max) / 2.0
    vertical_segment = _section_vertical_segment_for_points_at_x(geometry, block_center_x, y_values)
    if vertical_segment is not None:
        refs["vertical_segment"] = vertical_segment
        # The detail panel should remain zoomed around the strand block.
        # Include the nearest bottom edge needed for the eb dimension, but do
        # not force the full girder depth into the zoomed axis range.
        refs["y_values"].append(float(vertical_segment[0]))
    else:
        bottom_y = _section_bottom_y_from_geometry(geometry)
        refs["vertical_segment"] = (bottom_y, max(y_max, bottom_y))
        refs["y_values"].append(float(bottom_y))
    return refs


def _add_strand_detail_dimensions(
    fig: go.Figure,
    points: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    side: str = "All",
    full_section: bool = False,
    xref: str = "x",
    yref: str = "y",
) -> dict[str, Any]:
    """Add compact x/y spacing and edge-distance dimensions to a zoomed strand-detail panel."""

    refs = _strand_detail_dimension_references(points, geometry, side=side, full_section=full_section)
    bottom_xs = list(refs.get("bottom_row_xs") or [])
    y_values = list(refs.get("row_y_values") or [])
    if points.empty or not bottom_xs or not y_values:
        return refs

    x_min = min(float(value) for value in refs.get("x_values", bottom_xs))
    x_max = max(float(value) for value in refs.get("x_values", bottom_xs))
    y_min = min(float(value) for value in refs.get("y_values", y_values))
    y_max = max(float(value) for value in refs.get("y_values", y_values))
    x_span = max(x_max - x_min, 160.0)
    y_span = max(y_max - y_min, 160.0)
    point_x_span = max(max(bottom_xs) - min(bottom_xs), 120.0)
    point_y_span = max(max(y_values) - min(y_values), 120.0)
    h_tick = max(7.0, 0.022 * y_span)
    v_tick = max(7.0, 0.020 * x_span)
    bottom_row_y = float(refs.get("bottom_row_y") or y_values[0])
    side_key = str(side or "All").strip().lower()
    split_side_detail = side_key in {"left", "right"} and not full_section
    non_split_full_detail = bool(full_section and not split_side_detail and side_key == "all")

    # Horizontal strand spacing: show one typical gap for each unique spacing
    # and choose the pair nearest the row center to keep labels away from edge
    # distance and cover annotations.
    seen_spacings: set[int] = set()
    for y_value in y_values:
        row_points = points.loc[(points["y_mm_abs"].astype(float) - float(y_value)).abs() < 1e-6]
        xs = sorted(float(value) for value in row_points["x_mm"].astype(float).tolist())
        if len(xs) < 2:
            continue
        spacings = [abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1)]
        if not spacings:
            continue
        spacing = min(spacings)
        spacing_key = int(round(spacing * 10.0))
        if spacing_key in seen_spacings:
            continue
        seen_spacings.add(spacing_key)
        target_center = (xs[0] + xs[-1]) / 2.0
        candidate_pairs = [(xs[i], xs[i + 1]) for i in range(len(xs) - 1) if abs((xs[i + 1] - xs[i]) - spacing) < 1e-6]
        x0, x1 = min(candidate_pairs, key=lambda pair: abs(((pair[0] + pair[1]) / 2.0) - target_center))
        if split_side_detail:
            dim_y = max(y_values) + max(32.0, 0.070 * y_span)
        elif non_split_full_detail:
            row_index = y_values.index(y_value)
            dim_y = float(y_value) + max(16.0, 0.14 * point_y_span) + row_index * max(14.0, 0.05 * point_y_span)
        else:
            dim_y = float(y_value) + max(18.0, 0.055 * y_span)
        _add_detail_dimension_line(
            fig,
            x0=x0,
            x1=x1,
            y0=dim_y,
            y1=dim_y,
            label=f"typ. s = {_format_dimension_mm(spacing)} mm",
            orientation="h",
            tick_length=h_tick,
            font_size=8,
            xref=xref,
            yref=yref,
        )

    # Horizontal edge CL at the bottom/prestress datum row. These distances are
    # measured to the actual local concrete segment instead of floating in the
    # chart background.
    segment = refs.get("bottom_row_segment")
    if segment is not None:
        left_edge, right_edge = float(segment[0]), float(segment[1])
        left_strand = float(min(bottom_xs))
        right_strand = float(max(bottom_xs))
        bottom_clearance = max(0.0, bottom_row_y - (refs.get("vertical_segment") or (bottom_row_y, bottom_row_y))[0])
        if split_side_detail:
            bottom_edge = float((refs.get("vertical_segment") or (bottom_row_y, bottom_row_y))[0])
            edge_y = bottom_edge + max(10.0, min(20.0, 0.022 * y_span))
        elif non_split_full_detail:
            edge_y = bottom_row_y - max(26.0, 0.18 * point_y_span)
        elif bottom_clearance > 35.0:
            edge_y = bottom_row_y - min(bottom_clearance * 0.42, max(30.0, 0.070 * y_span))
        else:
            edge_y = bottom_row_y - max(22.0, 0.052 * y_span)
        left_edge_distance = max(0.0, left_strand - left_edge)
        right_edge_distance = max(0.0, right_edge - right_strand)
        left_edge_y = edge_y
        right_edge_y = edge_y
        if left_edge_distance > 1e-6 and right_edge_distance > 1e-6:
            if non_split_full_detail:
                offset = max(20.0, 0.12 * point_y_span)
                right_edge_y = edge_y
                left_edge_y = edge_y - offset
            else:
                offset = max(24.0, 0.065 * y_span)
                right_edge_y = edge_y + offset if split_side_detail else edge_y - offset
        if left_edge_distance > 1e-6:
            _add_detail_dimension_line(
                fig,
                x0=left_edge,
                x1=left_strand,
                y0=left_edge_y,
                y1=left_edge_y,
                label=f"eL = {_format_dimension_mm(left_edge_distance)} mm",
                orientation="h",
                tick_length=h_tick,
                font_size=7,
                xref=xref,
                yref=yref,
            )
        if right_edge_distance > 1e-6:
            _add_detail_dimension_line(
                fig,
                x0=right_strand,
                x1=right_edge,
                y0=right_edge_y,
                y1=right_edge_y,
                label=f"eR = {_format_dimension_mm(right_edge_distance)} mm",
                orientation="h",
                tick_length=h_tick,
                font_size=7,
                xref=xref,
                yref=yref,
            )

    # Vertical bottom edge and row spacing dimensions.
    vertical_segment = refs.get("vertical_segment")
    if vertical_segment is not None:
        bottom_edge = float(vertical_segment[0])
        if split_side_detail and refs.get("bottom_row_segment") is not None:
            vertical_x = float(refs["bottom_row_segment"][0]) - max(145.0, 0.19 * x_span)
        elif non_split_full_detail and refs.get("bottom_row_segment") is not None:
            vertical_x = float(refs["bottom_row_segment"][0]) - max(90.0, 0.14 * x_span)
        else:
            vertical_x = min(bottom_xs) - max(52.0, 0.070 * x_span)
        refs.setdefault("x_values", []).append(float(vertical_x))
        bottom_cover = max(0.0, bottom_row_y - bottom_edge)
        if bottom_cover > 1e-6:
            _add_detail_dimension_line(
                fig,
                x0=vertical_x,
                x1=vertical_x,
                y0=bottom_edge,
                y1=bottom_row_y,
                label=f"eb = {_format_dimension_mm(bottom_cover)} mm",
                orientation="v",
                tick_length=v_tick,
                font_size=7,
                xref=xref,
                yref=yref,
            )
        # Show all row-to-row vertical gaps for a small number of rows.  For
        # larger layouts, keep only unique representative values to prevent the
        # detail from turning into an annotation cloud.
        seen_vertical_gaps: set[int] = set()
        for lower, upper in zip(y_values, y_values[1:]):
            gap = float(upper) - float(lower)
            if gap <= 1e-6:
                continue
            gap_key = int(round(gap * 10.0))
            if len(y_values) > 4 and gap_key in seen_vertical_gaps:
                continue
            seen_vertical_gaps.add(gap_key)
            _add_detail_dimension_line(
                fig,
                x0=vertical_x,
                x1=vertical_x,
                y0=float(lower),
                y1=float(upper),
                label=f"v = {_format_dimension_mm(gap)} mm",
                orientation="v",
                tick_length=v_tick,
                font_size=7,
                xref=xref,
                yref=yref,
            )
    return refs


def _plot_girder_strand_cross_section_layout(table: pd.DataFrame, geometry: SectionGeometry | None) -> go.Figure:
    """Return the PRESTRESS.VIZ2 overall section schematic.

    This plot is intentionally not the strand-detail view.  It shows where the
    strand blocks sit in the complete section, while row counts and detailed
    bonded/debonded reading live in the adjacent table and zoomed panels.
    """

    fig = go.Figure()
    row_info = _girder_strand_cross_section_row_info(table)
    points = _girder_strand_point_layout_dataframe(table, geometry)
    bounds = _add_concrete_schematic_trace(fig, geometry, showlegend=True)

    if not points.empty:
        split_detail = _should_split_girder_strand_detail(points, geometry)
        if split_detail:
            block_specs = [
                ("Left strand block", points.loc[points["x_mm"].astype(float) < 0.0]),
                ("Right strand block", points.loc[points["x_mm"].astype(float) > 0.0]),
            ]
        else:
            block_specs = [("Strand zone", points)]

        for side_name, subset in block_specs:
            if subset.empty:
                continue
            x_min = float(subset["x_mm"].min())
            x_max = float(subset["x_mm"].max())
            y_min = float(subset["y_mm_abs"].min())
            y_max = float(subset["y_mm_abs"].max())
            x_pad = max(44.0, 0.10 * max(x_max - x_min, 80.0))
            y_pad = max(36.0, 0.16 * max(y_max - y_min, 80.0))
            fig.add_shape(
                type="rect",
                x0=x_min - x_pad,
                x1=x_max + x_pad,
                y0=y_min - y_pad,
                y1=y_max + y_pad,
                line={"color": "rgba(37, 99, 235, 0.56)", "width": 1.25, "dash": "dash"},
                fillcolor="rgba(37, 99, 235, 0.035)",
                layer="below",
            )
            if split_detail:
                fig.add_annotation(
                    x=(x_min + x_max) / 2.0,
                    y=y_max + y_pad,
                    text=side_name,
                    showarrow=False,
                    yshift=8,
                    font={"size": 9, "color": "rgba(15, 23, 42, 0.68)"},
                    bgcolor="rgba(255,255,255,0.86)",
                    bordercolor="rgba(203,213,225,0.86)",
                    borderwidth=1,
                    borderpad=2,
                )

        _add_strand_state_marker_traces(
            fig,
            points,
            row_info,
            marker_size=5,
            bonded_fill="rgba(255,255,255,0.0)",
            debonded_fill="rgba(255,255,255,0.0)",
            bonded_line="#2563eb",
            debonded_line="#dc2626",
            bonded_width=1.05,
            debonded_width=1.20,
            showlegend=True,
        )

    if bounds is not None:
        section_x_min, section_y_min, section_x_max, section_y_max = bounds
    elif not points.empty:
        section_x_min = float(points["x_mm"].min())
        section_x_max = float(points["x_mm"].max())
        section_y_min = min(float(points["y_mm_abs"].min()), _section_bottom_y_from_geometry(geometry))
        section_y_max = float(points["y_mm_abs"].max())
    else:
        section_x_min, section_y_min, section_x_max, section_y_max = -1000.0, -600.0, 1000.0, 600.0
    section_width = max(section_x_max - section_x_min, 200.0)
    section_depth = max(section_y_max - section_y_min, 200.0)
    x_pad = max(240.0, 0.06 * section_width)
    # Keep the overall section schematic clear of the title/legend strip.
    # The top clearance is intentionally larger than the bottom clearance so
    # every preset opens slightly lower in the plotting area without changing
    # the section geometry or aspect ratio.
    y_bottom_pad = max(130.0, 0.08 * section_depth)
    y_top_pad = max(260.0, 0.24 * section_depth)
    fig.update_xaxes(range=[section_x_min - x_pad, section_x_max + x_pad])
    fig.update_yaxes(range=[section_y_min - y_bottom_pad, section_y_max + y_top_pad])

    fig.update_layout(
        title={
            "text": "Overall section schematic",
            "x": 0.0,
            "xanchor": "left",
            "y": 0.985,
            "yanchor": "top",
            "font": {"size": 11, "color": "#101828"},
        },
        height=390,
        margin={"l": 45, "r": 16, "t": 96, "b": 40},
        xaxis_title="section x (mm)",
        yaxis_title="section y (mm)",
        showlegend=True,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.08,
            "xanchor": "right",
            "x": 0.99,
            "bgcolor": "rgba(255,255,255,0.90)",
            "bordercolor": "rgba(203,213,225,0.72)",
            "borderwidth": 1,
            "font": {"size": 8},
        },
        plot_bgcolor="white",
    )
    fig.update_xaxes(gridcolor="rgba(15,23,42,0.06)", zerolinecolor="rgba(15,23,42,0.16)")
    fig.update_yaxes(scaleanchor="x", scaleratio=1, gridcolor="rgba(15,23,42,0.06)", zerolinecolor="rgba(15,23,42,0.16)")
    return fig


def _plot_girder_strand_block_detail(
    table: pd.DataFrame,
    geometry: SectionGeometry | None,
    *,
    side: str = "All",
) -> go.Figure:
    """Return a zoomed strand-block panel for reading individual strand rows."""

    fig = go.Figure()
    all_points = _girder_strand_point_layout_dataframe(table, geometry)
    row_info = _girder_strand_cross_section_row_info(table)
    side_key = str(side or "All").strip().lower()
    if side_key == "left":
        points = all_points.loc[all_points["x_mm"].astype(float) < 0.0].copy() if not all_points.empty else all_points
        title = "Left strand block detail"
    elif side_key == "right":
        points = all_points.loc[all_points["x_mm"].astype(float) > 0.0].copy() if not all_points.empty else all_points
        title = "Right strand block detail"
    else:
        points = all_points.copy()
        title = "Strand block detail"

    if points.empty:
        fig.update_layout(
            title={"text": title, "x": 0.0, "xanchor": "left", "font": {"size": 13, "color": "#101828"}},
            height=360,
            margin={"l": 40, "r": 20, "t": 56, "b": 38},
            plot_bgcolor="white",
        )
        return fig

    split_detail = _should_split_girder_strand_detail(all_points, geometry)
    full_section_detail = bool(geometry is not None and not split_detail)
    y_values = sorted({round(float(value), 6) for value in points["y_mm_abs"].astype(float).tolist()})

    def _tick_rows(current_points: pd.DataFrame, *, compact: bool) -> list[tuple[float, str]]:
        rows: list[tuple[float, str]] = []
        local_y_values = sorted({round(float(value), 6) for value in current_points["y_mm_abs"].astype(float).tolist()})
        for y_value in local_y_values:
            current = current_points.loc[(current_points["y_mm_abs"].astype(float) - y_value).abs() < 1e-6]
            groups = sorted(set(str(group) for group in current["Group ID"].tolist()))
            row_numbers = [_strand_row_number_from_group_id(group) for group in groups]
            row_numbers = [number for number in row_numbers if number is not None]
            if row_numbers and len(set(row_numbers)) == 1:
                label = f"R{int(row_numbers[0])}" if compact else f"Row {int(row_numbers[0])}"
            else:
                normalized = [group.replace("L ", "").replace("R ", "") for group in groups]
                label = normalized[0] if len(set(normalized)) == 1 else " / ".join(normalized)
            debonded_count = int(current["Debonded selected"].fillna(False).astype(bool).sum())
            total_count = int(len(current.index))
            tick_text = f"{label} · {total_count - debonded_count}B/{debonded_count}U" if compact else f"{label}  ·  B {total_count - debonded_count} / U {debonded_count}"
            rows.append((y_value, tick_text))
        return rows

    def _row_guides(axis_x: str, axis_y: str, *, current_points: pd.DataFrame, bounds: tuple[float, float, float, float] | None, compact: bool) -> None:
        local_y_values = sorted({round(float(value), 6) for value in current_points["y_mm_abs"].astype(float).tolist()})
        for y_value in local_y_values:
            row_points = current_points.loc[(current_points["y_mm_abs"].astype(float) - y_value).abs() < 1e-6]
            segment = _section_horizontal_segment_for_points_at_y(geometry, y_value, row_points["x_mm"].astype(float).tolist())
            if segment is None:
                continue
            left_edge, right_edge = float(segment[0]), float(segment[1])
            if compact and bounds is not None:
                strand_left = float(row_points["x_mm"].astype(float).min())
                strand_right = float(row_points["x_mm"].astype(float).max())
                guide_pad = max(85.0, 0.16 * max(strand_right - strand_left, 160.0))
                left_edge = max(float(bounds[0]), strand_left - guide_pad)
                right_edge = min(float(bounds[2]), strand_right + guide_pad)
                row_line_width = 0.75
                row_line_color = "rgba(100,116,139,0.070)"
            elif bounds is not None:
                row_line_width = 1.0
                row_line_color = "rgba(100,116,139,0.11)"
            else:
                row_line_width = 1.6
                row_line_color = "rgba(100,116,139,0.14)"
            fig.add_trace(
                go.Scatter(
                    x=[left_edge, right_edge],
                    y=[float(y_value), float(y_value)],
                    mode="lines",
                    line={"color": row_line_color, "width": row_line_width},
                    name="Row datum in concrete",
                    hoverinfo="skip",
                    showlegend=False,
                    xaxis=axis_x,
                    yaxis=axis_y,
                )
            )

    if full_section_detail and side_key == "all":
        deep_web_detail = _is_deep_web_non_u_detail(points, geometry)
        context_bounds = _add_non_split_section_context_trace(fig, points, geometry, lower_focused=deep_web_detail)
        _row_guides("x", "y", current_points=points, bounds=context_bounds, compact=False)
        _add_strand_state_marker_traces(
            fig,
            points,
            row_info,
            marker_size=12,
            bonded_fill="rgba(37, 99, 235, 0.14)",
            debonded_fill="rgba(220, 38, 38, 0.16)",
            bonded_line="#2563eb",
            debonded_line="#dc2626",
            bonded_width=1.8,
            debonded_width=2.0,
            showlegend=False,
        )
        _add_drawing_debond_symbol_trace(fig, points, marker_size=7, showlegend=False)
        dimension_refs = _add_strand_detail_dimensions(fig, points, geometry, side=side, full_section=True)
        tick_rows = _tick_rows(points, compact=False)

        x_values = list(dimension_refs.get("x_values") or []) + points["x_mm"].astype(float).tolist()
        y_values_for_range = list(dimension_refs.get("y_values") or []) + points["y_mm_abs"].astype(float).tolist()
        if context_bounds is not None:
            x_values.extend([float(context_bounds[0]), float(context_bounds[2])])
            y_values_for_range.extend([float(context_bounds[1]), float(context_bounds[3])])
        x_min = min(float(value) for value in x_values)
        x_max = max(float(value) for value in x_values)
        y_min = min(float(value) for value in y_values_for_range)
        y_max = max(float(value) for value in y_values_for_range)
        x_span = max(x_max - x_min, 260.0)
        y_span = max(y_max - y_min, 260.0)
        if deep_web_detail:
            x_pad = max(28.0, 0.035 * x_span)
            y_pad_bottom = max(28.0, 0.060 * y_span)
            y_pad_top = max(26.0, 0.045 * y_span)
        else:
            x_pad = max(70.0, 0.08 * x_span)
            y_pad_bottom = max(55.0, 0.08 * y_span)
            y_pad_top = max(48.0, 0.08 * y_span)
        fig.update_xaxes(
            range=[x_min - x_pad, x_max + x_pad],
            tickfont={"size": 9},
            title_font={"size": 10},
            title_text="section x (mm)",
        )
        fig.update_yaxes(
            range=[y_min - y_pad_bottom, y_max + y_pad_top],
            tickmode="array",
            tickvals=[item[0] for item in tick_rows],
            ticktext=[item[1] for item in tick_rows],
            tickfont={"size": 8},
            title_text="section y (mm)",
        )
        fig.update_layout(
            title={"text": title, "x": 0.0, "xanchor": "left", "font": {"size": 11, "color": "#101828"}},
            height=500,
            margin={"l": 98, "r": 24, "t": 44, "b": 44},
            xaxis_title="section x (mm)",
            yaxis_title="section y (mm)",
            showlegend=False,
            plot_bgcolor="white",
            font={"size": 9},
        )
        fig.update_xaxes(gridcolor="rgba(15,23,42,0.055)", zerolinecolor="rgba(15,23,42,0.12)")
        fig.update_yaxes(scaleanchor="x", scaleratio=1, gridcolor="rgba(15,23,42,0.055)", zerolinecolor="rgba(15,23,42,0.12)")
        return fig

    # Existing split-detail rendering path (and generic fallback when geometry is missing).
    local_bounds = _add_local_concrete_zone_trace(fig, points, geometry, side=side, full_section=full_section_detail)
    _row_guides("x", "y", current_points=points, bounds=local_bounds, compact=bool(split_detail and side_key in {"left", "right"}))

    _add_strand_state_marker_traces(
        fig,
        points,
        row_info,
        marker_size=13,
        bonded_fill="rgba(37, 99, 235, 0.14)",
        debonded_fill="rgba(220, 38, 38, 0.16)",
        bonded_line="#2563eb",
        debonded_line="#dc2626",
        bonded_width=1.9,
        debonded_width=2.1,
        showlegend=False,
    )
    _add_drawing_debond_symbol_trace(fig, points, marker_size=7, showlegend=False)
    dimension_refs = _add_strand_detail_dimensions(fig, points, geometry, side=side, full_section=full_section_detail)
    tick_rows = _tick_rows(points, compact=bool(split_detail and side_key in {"left", "right"}))

    x_values = list(dimension_refs.get("x_values") or []) + points["x_mm"].astype(float).tolist()
    y_values_for_range = list(dimension_refs.get("y_values") or []) + points["y_mm_abs"].astype(float).tolist()
    if local_bounds is not None:
        x_values.extend([float(local_bounds[0]), float(local_bounds[2])])
        y_values_for_range.extend([float(local_bounds[1]), float(local_bounds[3])])
    x_min = min(float(value) for value in x_values)
    x_max = max(float(value) for value in x_values)
    y_min = min(float(value) for value in y_values_for_range)
    y_max = max(float(value) for value in y_values_for_range)
    x_span = max(x_max - x_min, 220.0)
    y_span = max(y_max - y_min, 220.0)
    fig.update_xaxes(
        range=[x_min - max(66.0, 0.105 * x_span), x_max + max(66.0, 0.105 * x_span)],
        tickfont={"size": 9},
        title_font={"size": 10},
    )
    fig.update_yaxes(
        range=[y_min - max(52.0, 0.090 * y_span), y_max + max(50.0, 0.090 * y_span)],
        tickmode="array",
        tickvals=[item[0] for item in tick_rows],
        ticktext=[item[1] for item in tick_rows],
        tickfont={"size": 7},
    )
    detail_height = 520 if split_detail and side_key in {"left", "right"} else 440
    fig.update_layout(
        title={"text": title, "x": 0.0, "xanchor": "left", "font": {"size": 11, "color": "#101828"}},
        height=detail_height,
        margin={"l": 108, "r": 24, "t": 44, "b": 44},
        xaxis_title="strand x (mm)",
        yaxis_title="",
        showlegend=False,
        plot_bgcolor="white",
        font={"size": 9},
    )
    fig.update_xaxes(gridcolor="rgba(15,23,42,0.055)", zerolinecolor="rgba(15,23,42,0.12)")
    fig.update_yaxes(scaleanchor="x", scaleratio=1, gridcolor="rgba(15,23,42,0.055)", zerolinecolor="rgba(15,23,42,0.12)")
    return fig

def _render_girder_strand_cross_section_dashboard(table: pd.DataFrame, geometry: SectionGeometry | None) -> None:
    """Render PRESTRESS.VIZ2 split schematic + row/detail dashboard."""

    points = _girder_strand_point_layout_dataframe(table, geometry)
    row_summary = _girder_strand_row_summary_dataframe(table, geometry)
    active_rows = _active_girder_strand_layout_rows(table)
    bonded_count = int((~points["Debonded selected"].fillna(False).astype(bool)).sum()) if not points.empty else 0
    debonded_count = int(points["Debonded selected"].fillna(False).astype(bool).sum()) if not points.empty else 0
    total_count = bonded_count + debonded_count
    status_tone = "review" if debonded_count else "ready"
    st.markdown(
        """
        <style>
        .prestress-viz-card-title {font-size: 1.02rem; font-weight: 600; color: #0f172a; margin: 0.10rem 0 0.15rem 0;}
        .prestress-viz-section-title {font-size: 0.93rem; font-weight: 600; color: #0f172a; margin: 0.10rem 0 0.22rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="prestress-viz-card-title">Prestress strand dashboard</div>', unsafe_allow_html=True)
    st.caption(
        "Split view: the full section is only a location schematic; row data and zoomed block panels carry the strand-reading work. "
        "Blue = fully bonded/effective in the cross-section preview; red = strand selections debonded near member ends from the row metadata."
    )
    st.markdown(
        _metric_strip_html(
            [
                PrestressMetric("Visual model", "Split dashboard", "Overall + detail panels", "info", strong=True),
                PrestressMetric("Fully bonded throughout", f"{bonded_count:,}", f"of {total_count:,} total", "ready"),
                PrestressMetric("Debonded near ends", f"{debonded_count:,}", "selected by row metadata", status_tone),
                PrestressMetric("Row groups", f"{len(active_rows):,}", "active strand groups", "neutral"),
            ]
        ),
        unsafe_allow_html=True,
    )

    top_left, top_right = st.columns([1.55, 1.0])
    with top_left:
        st.plotly_chart(
            _plot_girder_strand_cross_section_layout(table, geometry),
            use_container_width=True,
            config={"displayModeBar": True, "responsive": True},
        )
    with top_right:
        st.markdown('<div class="prestress-viz-section-title">Strand row summary</div>', unsafe_allow_html=True)
        if row_summary.empty:
            st.info("No active strand rows are available for the current section.")
        else:
            st.dataframe(
                row_summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total strands": st.column_config.NumberColumn("Total", format="%d"),
                    "Bonded": st.column_config.NumberColumn("Bonded", format="%d"),
                    "Debonded": st.column_config.NumberColumn("Debonded", format="%d"),
                    "Left debond (m)": st.column_config.NumberColumn("L debond (m)", format="%.3f"),
                    "Right debond (m)": st.column_config.NumberColumn("R debond (m)", format="%.3f"),
                },
            )
            st.caption("B = fully bonded-throughout strands in the row; U/debonded = strands selected for end debonding. L/R rows with the same row number are summarized together.")

    if points.empty:
        return
    left_points = points.loc[points["x_mm"].astype(float) < 0.0]
    right_points = points.loc[points["x_mm"].astype(float) > 0.0]
    split_detail = _should_split_girder_strand_detail(points, geometry)
    st.markdown('<div class="prestress-viz-section-title">Zoomed strand block detail</div>', unsafe_allow_html=True)
    if split_detail and not left_points.empty and not right_points.empty:
        st.plotly_chart(
            _plot_girder_strand_block_detail(table, geometry, side="Left"),
            use_container_width=True,
            config={"displayModeBar": True, "responsive": True},
        )
        st.plotly_chart(
            _plot_girder_strand_block_detail(table, geometry, side="Right"),
            use_container_width=True,
            config={"displayModeBar": True, "responsive": True},
        )
    else:
        st.plotly_chart(
            _plot_girder_strand_block_detail(table, geometry, side="All"),
            use_container_width=True,
            config={"displayModeBar": True, "responsive": True},
        )

def _debond_lengths_for_display(row: pd.Series | dict[str, Any], span_length_m: float) -> tuple[float, float]:
    """Return clamped left/right debond lengths for plotting and tables."""

    span = max(float(span_length_m), 0.0)
    left = min(max(float(_to_float(row.get("Left debond m")) or 0.0), 0.0), span)
    right = min(max(float(_to_float(row.get("Right debond m")) or 0.0), 0.0), span)
    return left, right


def _representative_rows_for_debonding_elevation(table: pd.DataFrame, *, one_side_schematic: bool) -> list[pd.Series]:
    """Return strand rows for the longitudinal debonding schematic.

    Generic sections keep the existing row/group listing.  Railway U-Girder can
    be displayed as one web only because the current drawing default is
    left/right symmetric; the summary table still reports the active data rows.
    """

    active = _active_girder_strand_layout_rows(table)
    if active.empty or not one_side_schematic:
        return [row for _, row in active.iterrows()]

    grouped: dict[int, list[pd.Series]] = {}
    ungrouped: list[pd.Series] = []
    for _, row in active.iterrows():
        row_number = _strand_row_number_from_group_id(row.get("Group ID"))
        if row_number is None:
            ungrouped.append(row)
            continue
        grouped.setdefault(row_number, []).append(row)

    rows: list[pd.Series] = []
    for row_number in sorted(grouped):
        candidates = grouped[row_number]
        representative = next((row for row in candidates if str(row.get("Group ID") or "").strip().upper().startswith("L ")), candidates[0])
        row_copy = representative.copy()
        row_copy["Group ID"] = f"Row {row_number}"
        row_copy["Layer"] = f"Railway U-Girder representative Row {row_number} (one web; left/right symmetric)"
        rows.append(row_copy)
    rows.extend(ungrouped)
    return rows


def _plot_girder_longitudinal_debonding_layout(
    table: pd.DataFrame,
    span_length_m: float,
    *,
    one_side_schematic: bool = False,
) -> go.Figure:
    """Return an elevation-style debonding schematic for girder strands.

    PRESTRESS.DEBOND.VIEW1 deliberately changes this from a generic line chart
    into an engineering schematic: solid blue means bonded/effective, red dashed
    end segments mean debonded sleeve length from the beam end, and row labels
    state how many strands in that row are debonded.  It remains a detailing
    preview and does not change any solver/effective-prestress calculation.
    """

    fig = go.Figure()
    active = _active_girder_strand_layout_rows(table)
    rows = _representative_rows_for_debonding_elevation(active, one_side_schematic=one_side_schematic)
    span = max(float(span_length_m), 1e-6)
    if not rows:
        fig.update_layout(height=320, margin={"l": 20, "r": 20, "t": 40, "b": 36}, plot_bgcolor="white")
        return fig

    bonded_color = "#1f77b4"
    bonded_through_color = "rgba(37, 99, 235, 0.34)"
    debonded_color = "#dc2626"
    outline_color = "rgba(15, 23, 42, 0.28)"
    dimension_color = "rgba(180, 83, 9, 0.95)"
    y_tick_values: list[float] = []
    y_tick_labels: list[str] = []
    legend_seen: set[str] = set()
    # Keep row spacing generous enough for engineering labels even when the app
    # viewport is compressed.  Labels are drawn as paper-referenced annotations
    # rather than y-axis tick text so they do not collide with the plot axis.
    row_gap = 0.50
    row_base = 0.72
    row_y_values = [row_base + i * row_gap for i in range(len(rows))]
    outline_bottom = 0.28
    outline_top = row_base + row_gap * (len(rows) + 1.35)

    # Simplified girder elevation envelope, not a stress/stiffness section.
    fig.add_trace(
        go.Scatter(
            x=[0.0, span, span, 0.0, 0.0],
            y=[outline_bottom, outline_bottom, outline_top, outline_top, outline_bottom],
            mode="lines",
            line={"color": outline_color, "width": 1.3},
            fill="toself",
            fillcolor="rgba(148, 163, 184, 0.07)",
            name="Girder elevation outline",
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_shape(type="line", x0=span / 2.0, x1=span / 2.0, y0=outline_bottom - 0.12, y1=outline_top + 0.32, line={"color": "rgba(75,85,99,0.65)", "width": 1})
    fig.add_annotation(x=span / 2.0, y=outline_top + 0.36, text="CL", showarrow=False, font={"size": 10, "color": "#475569"})

    unique_left_dims: set[float] = set()
    unique_right_dims: set[float] = set()
    for display_index, (row, y) in enumerate(zip(rows, row_y_values, strict=True), start=1):
        group = str(row.get("Group ID") or f"Row {display_index}")
        count = int(_to_float(row.get("No. Strands")) or 0)
        debonded_numbers = debonded_strand_numbers_for_row(row.to_dict() if hasattr(row, "to_dict") else row)
        debonded_count = len(debonded_numbers)
        bonded_count = max(0, count - debonded_count)
        left, right = _debond_lengths_for_display(row, span)
        if debonded_count <= 0:
            left = 0.0
            right = 0.0
        bonded_start = min(max(left, 0.0), span)
        bonded_end = max(bonded_start, span - min(max(right, 0.0), span))
        status, _ = _debond_status_from_row(row)
        if debonded_count == 0:
            status = "Fully bonded"

        y_tick_values.append(y)
        tick_suffix = " · one web" if one_side_schematic else ""
        y_tick_labels.append(f"{escape(group)} · {debonded_count} debonded{tick_suffix}")

        if bonded_count > 0 and debonded_count > 0:
            name = "Bonded throughout"
            fig.add_trace(
                go.Scatter(
                    x=[0.0, span],
                    y=[y - 0.045, y - 0.045],
                    mode="lines",
                    line={"color": bonded_through_color, "width": 4},
                    name=name,
                    showlegend=name not in legend_seen,
                    hovertemplate=(
                        f"{escape(group)}<br>Bonded throughout strands = {bonded_count}<br>"
                        f"Total strands = {count}<extra></extra>"
                    ),
                )
            )
            legend_seen.add(name)

        if debonded_count > 0 and (left > 1e-9 or right > 1e-9):
            if left > 1e-9:
                name = "Debonded sleeve"
                fig.add_trace(
                    go.Scatter(
                        x=[0.0, left],
                        y=[y, y],
                        mode="lines",
                        line={"color": debonded_color, "width": 6, "dash": "dash"},
                        name=name,
                        showlegend=name not in legend_seen,
                        hovertemplate=(
                            f"{escape(group)}<br>Debonded strands = {debonded_count}/{count}<br>"
                            f"Left sleeve = {left:.3f} m<extra></extra>"
                        ),
                    )
                )
                legend_seen.add(name)
                unique_left_dims.add(round(left, 6))
            if bonded_end > bonded_start + 1e-9:
                name = "Bonded after sleeve"
                fig.add_trace(
                    go.Scatter(
                        x=[bonded_start, bonded_end],
                        y=[y, y],
                        mode="lines",
                        line={"color": bonded_color, "width": 6},
                        name=name,
                        showlegend=name not in legend_seen,
                        hovertemplate=(
                            f"{escape(group)}<br>Debonded strands = {debonded_count}/{count}<br>"
                            f"Bonded zone = {bonded_start:.3f} → {bonded_end:.3f} m<extra></extra>"
                        ),
                    )
                )
                legend_seen.add(name)
            if right > 1e-9:
                name = "Debonded sleeve"
                fig.add_trace(
                    go.Scatter(
                        x=[span - right, span],
                        y=[y, y],
                        mode="lines",
                        line={"color": debonded_color, "width": 6, "dash": "dash"},
                        name=name,
                        showlegend=name not in legend_seen,
                        hovertemplate=(
                            f"{escape(group)}<br>Debonded strands = {debonded_count}/{count}<br>"
                            f"Right sleeve = {right:.3f} m<extra></extra>"
                        ),
                    )
                )
                legend_seen.add(name)
                unique_right_dims.add(round(right, 6))
        else:
            name = "Bonded"
            fig.add_trace(
                go.Scatter(
                    x=[0.0, span],
                    y=[y, y],
                    mode="lines",
                    line={"color": bonded_color, "width": 6},
                    name=name,
                    showlegend=name not in legend_seen,
                    hovertemplate=f"{escape(group)}<br>Bonded strands = {count}/{count}<extra></extra>",
                )
            )
            legend_seen.add(name)

        # Row-end count label, kept compact to avoid CAD-style clutter.
        debond_text = "bonded only" if debonded_count == 0 else f"{debonded_count} of {count} debonded"
        fig.add_annotation(
            x=1.006,
            y=y,
            xref="paper",
            yref="y",
            text=f"{escape(group)}: {debond_text}",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            align="left",
            font={"size": 10, "color": "#334155"},
        )

    # Compact dimension ticks from each end for the unique sleeve lengths in view.
    dim_y0 = outline_bottom - 0.18
    dim_drop = 0.16
    for level, length in enumerate(sorted(value for value in unique_left_dims if value > 1e-9), start=1):
        y_dim = dim_y0 - dim_drop * level
        fig.add_shape(type="line", x0=0.0, x1=length, y0=y_dim, y1=y_dim, line={"color": dimension_color, "width": 1})
        fig.add_shape(type="line", x0=0.0, x1=0.0, y0=y_dim - 0.035, y1=y_dim + 0.035, line={"color": dimension_color, "width": 1})
        fig.add_shape(type="line", x0=length, x1=length, y0=y_dim - 0.035, y1=y_dim + 0.035, line={"color": dimension_color, "width": 1})
        fig.add_annotation(
            x=length / 2.0,
            y=y_dim - 0.055,
            text=f"{length * 1000:.0f} mm from left end",
            showarrow=False,
            xanchor="center",
            yanchor="top",
            font={"size": 10, "color": "#92400e"},
        )
    for level, length in enumerate(sorted(value for value in unique_right_dims if value > 1e-9), start=1):
        y_dim = dim_y0 - dim_drop * level
        fig.add_shape(type="line", x0=span - length, x1=span, y0=y_dim, y1=y_dim, line={"color": dimension_color, "width": 1})
        fig.add_shape(type="line", x0=span - length, x1=span - length, y0=y_dim - 0.035, y1=y_dim + 0.035, line={"color": dimension_color, "width": 1})
        fig.add_shape(type="line", x0=span, x1=span, y0=y_dim - 0.035, y1=y_dim + 0.035, line={"color": dimension_color, "width": 1})
        fig.add_annotation(
            x=span - length / 2.0,
            y=y_dim - 0.055,
            text=f"{length * 1000:.0f} mm from right end",
            showarrow=False,
            xanchor="center",
            yanchor="top",
            font={"size": 10, "color": "#92400e"},
        )

    title_text = "Debonding elevation schematic"
    if one_side_schematic:
        title_text += " — one web shown, mirrored to the opposite web"
    fig.update_layout(
        height=max(500, 230 + 64 * max(len(rows), 1)),
        margin={"l": 182, "r": 190, "t": 66, "b": 118},
        xaxis_title="station x from left support (m)",
        yaxis={"tickmode": "array", "tickvals": y_tick_values, "ticktext": y_tick_labels, "title": "strand row"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.03, "xanchor": "left", "x": 0.0},
        showlegend=True,
        title={"text": title_text, "font": {"size": 14}},
        plot_bgcolor="white",
    )
    fig.update_xaxes(range=[-0.02 * span, 1.02 * span], gridcolor="rgba(0,0,0,0.08)", zeroline=False)
    y_min = dim_y0 - dim_drop * (max(len(unique_left_dims), len(unique_right_dims), 1) + 0.55)
    fig.update_yaxes(range=[y_min, outline_top + 0.62], gridcolor="rgba(0,0,0,0.08)")
    return fig


def _render_railway_u_girder_stage_model_ui(geometry: SectionGeometry | None, *, span_length_m: float) -> None:
    """Render STAGE.RAIL.UGIRDER1 staged-construction metadata controls.

    This panel intentionally stops at stage definitions, editable defaults, and
    auto-load attribution.  It does not calculate concrete stresses and does
    not change any prestress loss, SLS, PMM, or report result.
    """

    st.markdown("##### Railway U-Girder Staged Construction Model")
    st.caption(
        "STAGE.RAIL.UGIRDER1 defines the construction-stage basis for the through U-girder. "
        "Transfer, lifting, and wet-slab casting use one precast web only; composite construction "
        "and service use the full Railway U-Girder. This is metadata/UI for the next staged-stress preview, not a solver change."
    )
    settings = _railway_u_girder_stage_settings_from_session()

    material_cols = st.columns(3)
    with material_cols[0]:
        settings["web_fc_MPa"] = st.number_input(
            "Web f'c (MPa)",
            min_value=10.0,
            value=float(settings["web_fc_MPa"]),
            step=1.0,
            format="%.1f",
            key="rail_ugirder_stage_web_fc_mpa",
        )
        st.caption(f"Ec(web) = {_aci_concrete_ec_mpa(settings['web_fc_MPa']):,.0f} MPa")
    with material_cols[1]:
        settings["web_fci_MPa"] = st.number_input(
            "Web f'ci (MPa)",
            min_value=10.0,
            value=float(settings["web_fci_MPa"]),
            step=1.0,
            format="%.1f",
            key="rail_ugirder_stage_web_fci_mpa",
        )
        st.caption(f"Eci(web) = {_aci_concrete_ec_mpa(settings['web_fci_MPa']):,.0f} MPa")
    with material_cols[2]:
        settings["slab_fc_MPa"] = st.number_input(
            "Slab f'c (MPa)",
            min_value=10.0,
            value=float(settings["slab_fc_MPa"]),
            step=1.0,
            format="%.1f",
            key="rail_ugirder_stage_slab_fc_mpa",
        )
        st.caption(f"Ec(slab) = {_aci_concrete_ec_mpa(settings['slab_fc_MPa']):,.0f} MPa")

    stage_cols = st.columns(4)
    with stage_cols[0]:
        st.text_input("Support condition", value="Simply supported", disabled=True, key="rail_ugirder_stage_support_condition")
    with stage_cols[1]:
        settings["concrete_unit_weight_kN_m3"] = st.number_input(
            "Concrete unit weight (kN/m³)",
            min_value=1.0,
            value=float(settings["concrete_unit_weight_kN_m3"]),
            step=0.5,
            format="%.2f",
            key="rail_ugirder_stage_concrete_unit_weight",
        )
    with stage_cols[2]:
        settings["formwork_construction_load_kN_m2"] = st.number_input(
            "Formwork load (kN/m²)",
            min_value=0.0,
            value=float(settings["formwork_construction_load_kN_m2"]),
            step=0.5,
            format="%.2f",
            key="rail_ugirder_stage_formwork_load",
        )
    with stage_cols[3]:
        st.text_input("Wet slab case", value="Case B: 50/50 to webs", disabled=True, key="rail_ugirder_stage_wet_slab_case")

    lift_cols = st.columns(4)
    with lift_cols[0]:
        st.metric("Span L", f"{float(span_length_m):.3f} m", "controlled by strand/debonding span above")
    with lift_cols[1]:
        settings["lifting_point_ratio"] = st.number_input(
            "Lifting a/L",
            min_value=0.05,
            max_value=0.45,
            value=float(settings["lifting_point_ratio"]),
            step=0.01,
            format="%.3f",
            key="rail_ugirder_stage_lifting_ratio",
        )
    with lift_cols[2]:
        st.metric("Lifting a", f"{float(settings['lifting_point_ratio']) * float(span_length_m):.3f} m", "from each end")
    with lift_cols[3]:
        settings["lifting_impact_factor"] = st.number_input(
            "Lifting impact factor",
            min_value=1.0,
            value=float(settings["lifting_impact_factor"]),
            step=0.05,
            format="%.2f",
            key="rail_ugirder_stage_lifting_impact",
        )

    settings = _railway_u_girder_stage_settings_from_session() | settings
    st.session_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = dict(settings)

    metric_cols = [
        PrestressMetric("Stage model", "Ready", "metadata only", "ready", strong=True),
        PrestressMetric("Transfer basis", "Web only", "precast self-weight + Pe_transfer", "info"),
        PrestressMetric("Wet slab", "Case B", "50/50 to left/right web", "review"),
        PrestressMetric("Service basis", "Full U", "service loads remain in Loads tab", "info"),
    ]
    st.markdown(_metric_strip_html(metric_cols), unsafe_allow_html=True)

    st.markdown("**Stage basis summary**")
    st.dataframe(_railway_u_girder_stage_summary_dataframe(settings), use_container_width=True, hide_index=True)

    quantities = _railway_u_girder_stage_quantities_dataframe(geometry, settings, span_length_m=float(span_length_m))
    st.markdown("**Auto-load attribution preview**")
    st.dataframe(quantities, use_container_width=True, hide_index=True, column_config={"Value": st.column_config.NumberColumn("Value", format="%.3f")})

    st.markdown("**Railway U-Girder staged SLS stress preview**")
    st.caption(
        "SLS.RAIL.UGIRDER1 consumes station-based debonded strand participation; SLS.RAIL.UGIRDER2 consumes station-based debonded strand participation and adds stage-aware editable stress-limit checks; SLS.RAIL.UGIRDER3 adds a locked-in staged stress accumulation handoff. "
        "Transfer, lifting, and wet slab casting use one precast web only; the service row is still a full-U Pe reference until locked-in service-load superposition is finalized. "
        "Locked-in staged stress superposition is still limited to this guarded handoff; transfer-length ramping, development length, anchorage/end-zone bursting, and final code-certified checks remain future scope."
    )
    strand_table = st.session_state.get("girder_strand_layout_table")
    try:
        stress_df = railway_u_girder_staged_stress_preview_dataframe(
            geometry=geometry,
            settings=settings,
            strand_table=strand_table,
            span_length_m=float(span_length_m),
        )
    except Exception as exc:
        st.warning(f"Railway U-Girder staged stress preview is not available: {exc}")
        stress_df = pd.DataFrame()
    if not stress_df.empty:
        governing = railway_u_girder_stage_governing_rows(stress_df)
        st.dataframe(
            governing,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Max compression (MPa)": st.column_config.NumberColumn("Max compression (MPa)", format="%.3f"),
                "Max tension (MPa)": st.column_config.NumberColumn("Max tension (MPa)", format="%.3f"),
            },
        )
        limit_df = railway_u_girder_staged_stress_limit_check_dataframe(stress_df, settings=settings)
        if not limit_df.empty:
            st.markdown("**Stage stress-limit preview**")
            st.caption(
                "Editable preview limits are assigned by stage: transfer/lifting use f'ci(web), wet slab casting uses f'c(web), "
                "and the full-U Pe reference uses min(f'c web, f'c slab). Review project specifications before final design."
            )
            limit_governing = railway_u_girder_stage_limit_governing_rows(limit_df)
            st.dataframe(
                limit_governing,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Max utilization": st.column_config.NumberColumn("Max utilization", format="%.3f"),
                    "Concrete strength used (MPa)": st.column_config.NumberColumn("Concrete strength used (MPa)", format="%.2f"),
                },
            )
        st.markdown("**Locked-in staged stress accumulation preview**")
        st.caption(
            "SLS.RAIL.UGIRDER3 separates true web-stage locked-in increments from the later full-U Pe handoff. "
            "Transfer and wet-slab casting rows accumulate on the one-web basis; the final Pe row is a full-U service increment and is not algebraically summed with web-locked fibers. "
            "Service loads from the Loads tab, transfer-length ramping, time-dependent redistribution, and final code-certified checks remain guarded future scope."
        )
        try:
            locked_df = railway_u_girder_locked_in_stress_accumulation_dataframe(
                geometry=geometry,
                settings=settings,
                strand_table=strand_table,
                span_length_m=float(span_length_m),
            )
        except Exception as exc:
            st.warning(f"Locked-in staged stress accumulation preview is not available: {exc}")
            locked_df = pd.DataFrame()
        if not locked_df.empty:
            locked_governing = railway_u_girder_locked_in_governing_rows(locked_df)
            st.dataframe(
                locked_governing,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Governing compression (MPa)": st.column_config.NumberColumn("Governing compression (MPa)", format="%.3f"),
                    "Governing tension (MPa)": st.column_config.NumberColumn("Governing tension (MPa)", format="%.3f"),
                },
            )

        st.markdown("**Service load handoff from Loads tab**")
        st.caption(
            "SLS.RAIL.UGIRDER4 consumes active SLS load cases from Loads as full-U service resultants and combines them with station-based Pe_final. "
            "SLS.RAIL.UGIRDER5 then provides a guarded final accumulated service preview using locked web stresses + final Pe increment + service load increments. "
            "Legacy SLS.RAIL.UGIRDER4 handoff note: web-stage locked-in stresses are not transformed and summed in the standalone handoff rows. "
            "Review load attribution carefully to avoid double-counting self-weight already captured by automatic stage loads."
        )
        active_sls_count = sum(
            1
            for load_case in st.session_state.get("load_cases", []) or []
            if bool(getattr(load_case, "active", False)) and str(getattr(load_case, "load_type", "")).upper() == "SLS"
        )
        service_station = st.number_input(
            "Service Pe station x for debond participation (m)",
            min_value=0.0,
            max_value=float(span_length_m),
            value=float(span_length_m) / 2.0,
            step=max(float(span_length_m) / 20.0, 0.1),
            format="%.3f",
            key="rail_ugirder_service_load_station_m",
            help="The SLS load cases already contain service resultants. This station is used to evaluate debonded-strand participation for Pe_final only.",
        )
        try:
            service_df = railway_u_girder_service_load_handoff_dataframe(
                geometry=geometry,
                settings=settings,
                strand_table=strand_table,
                span_length_m=float(span_length_m),
                load_cases=st.session_state.get("load_cases", []) or [],
                station_m=float(service_station),
            )
        except Exception as exc:
            st.warning(f"Railway U-Girder service load handoff preview is not available: {exc}")
            service_df = pd.DataFrame()
        if service_df.empty:
            st.info(f"No active SLS load case is available in Loads tab for service handoff. Active SLS rows = {active_sls_count}.")
            service_limit_df = pd.DataFrame()
        else:
            service_governing = railway_u_girder_service_load_governing_rows(service_df)
            st.dataframe(
                service_governing,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Pu (kN)": st.column_config.NumberColumn("Pu (kN)", format="%.3f"),
                    "Mux (kN-m)": st.column_config.NumberColumn("Mux (kN-m)", format="%.3f"),
                    "Pe_final (kN)": st.column_config.NumberColumn("Pe_final (kN)", format="%.1f"),
                    "Top total (MPa)": st.column_config.NumberColumn("Top total (MPa)", format="%.3f"),
                    "Bottom total (MPa)": st.column_config.NumberColumn("Bottom total (MPa)", format="%.3f"),
                    "Max compression (MPa)": st.column_config.NumberColumn("Max compression (MPa)", format="%.3f"),
                    "Max tension (MPa)": st.column_config.NumberColumn("Max tension (MPa)", format="%.3f"),
                },
            )
            service_limit_df = railway_u_girder_service_load_limit_check_dataframe(service_df, settings=settings)
            if not service_limit_df.empty:
                with st.expander("Service load stress-limit preview", expanded=False):
                    st.dataframe(
                        service_limit_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Concrete strength used (MPa)": st.column_config.NumberColumn("Concrete strength used (MPa)", format="%.2f"),
                            "Top total (MPa)": st.column_config.NumberColumn("Top total (MPa)", format="%.3f"),
                            "Bottom total (MPa)": st.column_config.NumberColumn("Bottom total (MPa)", format="%.3f"),
                            "Max utilization": st.column_config.NumberColumn("Max utilization", format="%.3f"),
                        },
                    )

        st.markdown("**Final staged service accumulation preview**")
        st.caption(
            "SLS.RAIL.UGIRDER5 adds locked-in web stresses from transfer/wet casting to later full-U incremental service actions. "
            "Loads tab SLS cases are treated as additional service increments after composite action; do not include auto-counted web/wet-slab self-weight again unless intended. "
            "This is still a guarded engineering-review preview, not a final code-certified staged composite check."
        )
        try:
            final_df = railway_u_girder_final_service_accumulation_dataframe(
                geometry=geometry,
                settings=settings,
                strand_table=strand_table,
                span_length_m=float(span_length_m),
                load_cases=st.session_state.get("load_cases", []) or [],
                station_m=float(service_station),
            )
        except Exception as exc:
            st.warning(f"Final Railway U-Girder staged service accumulation preview is not available: {exc}")
            final_df = pd.DataFrame()
        if final_df.empty:
            st.info("Final accumulated service preview will appear after active SLS load cases are available in Loads tab.")
            final_limit_df = pd.DataFrame()
        else:
            final_governing = railway_u_girder_final_service_governing_rows(final_df)
            st.dataframe(
                final_governing,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Locked top (MPa)": st.column_config.NumberColumn("Locked top (MPa)", format="%.3f"),
                    "Locked bottom (MPa)": st.column_config.NumberColumn("Locked bottom (MPa)", format="%.3f"),
                    "Service load top (MPa)": st.column_config.NumberColumn("Service load top (MPa)", format="%.3f"),
                    "Service load bottom (MPa)": st.column_config.NumberColumn("Service load bottom (MPa)", format="%.3f"),
                    "Final top (MPa)": st.column_config.NumberColumn("Final top (MPa)", format="%.3f"),
                    "Final bottom (MPa)": st.column_config.NumberColumn("Final bottom (MPa)", format="%.3f"),
                    "Max compression (MPa)": st.column_config.NumberColumn("Max compression (MPa)", format="%.3f"),
                    "Max tension (MPa)": st.column_config.NumberColumn("Max tension (MPa)", format="%.3f"),
                },
            )
            final_limit_df = railway_u_girder_final_service_limit_check_dataframe(final_df, settings=settings)
            if not final_limit_df.empty:
                with st.expander("Final staged service stress-limit preview", expanded=False):
                    st.dataframe(
                        final_limit_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Concrete strength used (MPa)": st.column_config.NumberColumn("Concrete strength used (MPa)", format="%.2f"),
                            "Final top (MPa)": st.column_config.NumberColumn("Final top (MPa)", format="%.3f"),
                            "Final bottom (MPa)": st.column_config.NumberColumn("Final bottom (MPa)", format="%.3f"),
                            "Max utilization": st.column_config.NumberColumn("Max utilization", format="%.3f"),
                        },
                    )
        decision_df = railway_u_girder_sls_decision_summary_dataframe(
            stage_limit_df=limit_df,
            final_service_limit_df=final_limit_df,
            active_sls_count=active_sls_count,
        )
        # RESULT.SUMMARY2: cache normalized staged SLS decision tables so the
        # Result Summary dashboard can remain read-only while still reflecting
        # the Railway U-Girder SLS graphs/tables already produced here.
        st.session_state["railway_u_girder_sls_decision_summary_df"] = decision_df.copy()
        st.session_state["railway_u_girder_sls_stage_governing_df"] = governing.copy()
        if not limit_df.empty:
            st.session_state["railway_u_girder_sls_limit_governing_df"] = limit_governing.copy()
        if not final_df.empty:
            st.session_state["railway_u_girder_sls_final_service_governing_df"] = final_governing.copy()
        st.session_state["railway_u_girder_sls_report_package_available"] = bool(not decision_df.empty)
        st.markdown("**Railway U-Girder SLS decision summary**")
        st.caption(
            "SLS.RAIL.UGIRDER6 condenses Transfer, Lifting, Wet slab casting, and Final service into a guarded decision view. "
            "Statuses are `Preview PASS` or `REVIEW` for engineering review only; they are not code-certified design approvals."
        )
        st.dataframe(
            decision_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Max utilization": st.column_config.NumberColumn("Max utilization", format="%.3f"),
                "Compression (MPa)": st.column_config.NumberColumn("Compression (MPa)", format="%.3f"),
                "Tension (MPa)": st.column_config.NumberColumn("Tension (MPa)", format="%.3f"),
            },
        )
        if (decision_df.get("Decision", pd.Series(dtype=str)).astype(str) == "REVIEW").any():
            st.warning(
                "One or more Railway U-Girder SLS stages need review. Check the governing row, stress-limit profile, load attribution, and project-specific limits before using the result."
            )
        else:
            st.success("All reported Railway U-Girder SLS preview stages are available for engineering review.")

        with st.expander("Station-by-station staged stress, limits, locked-in, service handoff, and final service accumulation", expanded=False):
            st.dataframe(
                stress_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Auto load w (kN/m)": st.column_config.NumberColumn("Auto load w (kN/m)", format="%.3f"),
                    "Auto Mx (kN-m)": st.column_config.NumberColumn("Auto Mx (kN-m)", format="%.3f"),
                    "Pe stage (kN)": st.column_config.NumberColumn("Pe stage (kN)", format="%.1f"),
                    "Top total (MPa)": st.column_config.NumberColumn("Top total (MPa)", format="%.3f"),
                    "Bottom total (MPa)": st.column_config.NumberColumn("Bottom total (MPa)", format="%.3f"),
                },
            )
            if not limit_df.empty:
                st.dataframe(
                    limit_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Concrete strength used (MPa)": st.column_config.NumberColumn("Concrete strength used (MPa)", format="%.2f"),
                        "Top total (MPa)": st.column_config.NumberColumn("Top total (MPa)", format="%.3f"),
                        "Bottom total (MPa)": st.column_config.NumberColumn("Bottom total (MPa)", format="%.3f"),
                        "Max utilization": st.column_config.NumberColumn("Max utilization", format="%.3f"),
                    },
                )
            if not locked_df.empty:
                st.dataframe(
                    locked_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Load increment w (kN/m)": st.column_config.NumberColumn("Load increment w (kN/m)", format="%.3f"),
                        "Moment increment (kN-m)": st.column_config.NumberColumn("Moment increment (kN-m)", format="%.3f"),
                        "Pe increment (kN)": st.column_config.NumberColumn("Pe increment (kN)", format="%.1f"),
                        "Top increment (MPa)": st.column_config.NumberColumn("Top increment (MPa)", format="%.3f"),
                        "Bottom increment (MPa)": st.column_config.NumberColumn("Bottom increment (MPa)", format="%.3f"),
                        "Cumulative top (MPa)": st.column_config.NumberColumn("Cumulative top (MPa)", format="%.3f"),
                        "Cumulative bottom (MPa)": st.column_config.NumberColumn("Cumulative bottom (MPa)", format="%.3f"),
                    },
                )
            if 'service_df' in locals() and not service_df.empty:
                st.dataframe(
                    service_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Pu (kN)": st.column_config.NumberColumn("Pu (kN)", format="%.3f"),
                        "Mux (kN-m)": st.column_config.NumberColumn("Mux (kN-m)", format="%.3f"),
                        "Pe_final (kN)": st.column_config.NumberColumn("Pe_final (kN)", format="%.1f"),
                        "Load top (MPa)": st.column_config.NumberColumn("Load top (MPa)", format="%.3f"),
                        "Load bottom (MPa)": st.column_config.NumberColumn("Load bottom (MPa)", format="%.3f"),
                        "Pe top (MPa)": st.column_config.NumberColumn("Pe top (MPa)", format="%.3f"),
                        "Pe bottom (MPa)": st.column_config.NumberColumn("Pe bottom (MPa)", format="%.3f"),
                        "Top total (MPa)": st.column_config.NumberColumn("Top total (MPa)", format="%.3f"),
                        "Bottom total (MPa)": st.column_config.NumberColumn("Bottom total (MPa)", format="%.3f"),
                    },
                )
            if 'final_df' in locals() and not final_df.empty:
                st.dataframe(
                    final_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Pu (kN)": st.column_config.NumberColumn("Pu (kN)", format="%.3f"),
                        "Mux (kN-m)": st.column_config.NumberColumn("Mux (kN-m)", format="%.3f"),
                        "Locked top (MPa)": st.column_config.NumberColumn("Locked top (MPa)", format="%.3f"),
                        "Locked bottom (MPa)": st.column_config.NumberColumn("Locked bottom (MPa)", format="%.3f"),
                        "Service load top (MPa)": st.column_config.NumberColumn("Service load top (MPa)", format="%.3f"),
                        "Service load bottom (MPa)": st.column_config.NumberColumn("Service load bottom (MPa)", format="%.3f"),
                        "Final Pe increment top (MPa)": st.column_config.NumberColumn("Final Pe increment top (MPa)", format="%.3f"),
                        "Final Pe increment bottom (MPa)": st.column_config.NumberColumn("Final Pe increment bottom (MPa)", format="%.3f"),
                        "Final top (MPa)": st.column_config.NumberColumn("Final top (MPa)", format="%.3f"),
                        "Final bottom (MPa)": st.column_config.NumberColumn("Final bottom (MPa)", format="%.3f"),
                    },
                )
    else:
        st.info("Staged stress preview will appear after a valid strand layout / force-state table is available.")

    with st.expander("Guardrails for staged stress calculation", expanded=False):
        st.write("- Transfer, lifting, and wet slab casting must not use the full U-section inertia.")
        st.write("- Wet slab self-weight and formwork load are applied to the two precast webs before composite action for Case B.")
        st.write("- Service preview treats Loads tab SLS rows as additional full-U service increments; avoid double-counting self-weight already captured by automatic stage loads.")
        st.write("- Stage stress-limit rows are editable preview checks, not final code certification.")
        st.write("- Final staged service accumulation is also an editable preview check, not final code certification.")
        st.write("- Debonded strands are consumed through station-based participation as a step-function preview; transfer-length force ramping is not modeled yet.")


def _render_girder_strand_layout_and_debonding_ui(geometry: SectionGeometry | None) -> None:
    """Render GIRDER.PS3A strand layout/debonding workflow.

    This is intentionally UI/metadata only. It prepares commercial-style
    strand layout data for later station-based effective prestress and SLS
    stress graphs, but does not change current Analysis results.
    """

    st.markdown("#### Simple-Supported Girder Strand Layout & Debonding")
    st.markdown(
        '<div class="cpmm-prestress-table-note">'
        "GIRDER.PS3A defines pretensioned strand groups and left/right debonded lengths for simple-supported precast girders. "
        "Debonded strands are internal prestress metadata, not external Loads. Automatic losses and transfer/development length transition are future milestones."
        "</div>",
        unsafe_allow_html=True,
    )
    settings = _girder_prestress_system_settings_from_session()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.text_input("Girder system", value=settings["girder_system"], disabled=True, key="girder_prestress_system_label")
    with col2:
        st.text_input("Prestress type", value=settings["prestress_type"], disabled=True, key="girder_prestress_type_label")
    with col3:
        span = st.number_input(
            "Span length L (m)",
            min_value=0.1,
            value=float(settings["span_length_m"]),
            step=1.0,
            format="%.3f",
            key="girder_prestress_span_length_m_input",
        )
    with col4:
        debond_model = st.selectbox(
            "Debonding model",
            GIRDER_DEBOND_MODE_OPTIONS,
            index=GIRDER_DEBOND_MODE_OPTIONS.index(settings["debond_model"]),
            key="girder_prestress_debond_model_input",
        )
    settings["span_length_m"] = float(span)
    settings["debond_model"] = str(debond_model)
    st.session_state["girder_prestress_system_settings"] = settings

    if st.button(
        "Rebuild default strand layout from current section",
        help="Replace the current strand table with the current section's practical strand preset. Railway U-Girder uses the drawing-based 72-strand layout; Box/Plank use BP1 practical layouts; other girders use the section-based starter layout.",
        key="rebuild_girder_strand_layout_defaults",
    ):
        seeded = _apply_computed_girder_strand_spacing(_default_girder_strand_layout_table(geometry), geometry)
        st.session_state["girder_strand_layout_table"] = seeded
        st.session_state.pop("girder_strand_layout_editor", None)
        rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()

    current = st.session_state.get("girder_strand_layout_table")
    table = _normalize_girder_strand_layout_table(
        pd.DataFrame(current) if current is not None else None,
        span_length_m=float(span),
        debond_model=str(debond_model),
        geometry=geometry,
    )
    st.caption(
        "🟨 Primary input columns: strand size, number of strands, editable strand x coordinates, y-position, left/right debond lengths, optional debonded strand numbers, and stage Pe per strand. "
        "Defaults use 12.7 mm low-relaxation strand. Railway U-Girder uses the drawing-based 72-strand layout; Box/Plank presets use practical BP1 layouts; other girders use 2 rows at y=50/100 mm, 45 mm edge CL, and 50 mm x/y spacing. "
        "For Railway U-Girder symmetric detailing, enter debonding on L rows; matching R rows are auto-mirrored. "
        "Area, minimum spacing, total Aps, and row debond summaries are auto-calculated."
    )
    edited = st.data_editor(
        table,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_order=GIRDER_STRAND_LAYOUT_EDITOR_COLUMNS,
        column_config={
            "Active": st.column_config.CheckboxColumn("Active"),
            "Group ID": st.column_config.TextColumn("Group ID"),
            "Layer": st.column_config.TextColumn("Layer / row"),
            "Strand Size": st.column_config.SelectboxColumn("🟨 Strand size", options=GIRDER_STRAND_SIZE_OPTIONS),
            "No. Strands": st.column_config.NumberColumn("🟨 No. strands", min_value=0, step=1),
            "Area/Strand_mm2": st.column_config.NumberColumn("Area/strand (mm²)", disabled=True, format="%.3f"),
            "Total Aps_mm2": st.column_config.NumberColumn("Total Aps (mm²)", disabled=True, format="%.3f"),
            "Row center x_mm": st.column_config.NumberColumn("Row center x (mm)", step=10.0, format="%.0f"),
            "Strand x positions mm": st.column_config.TextColumn(
                "🟨 x coordinates (mm)",
                help="Comma-separated individual strand x coordinates for this row, measured from the section centerline. Leave blank to regenerate an auto centered row.",
            ),
            "y_mm_from_bottom": st.column_config.NumberColumn("🟨 y from bottom (mm)", min_value=0.0, step=10.0, format="%.0f"),
            "Edge CL_mm": st.column_config.NumberColumn("Edge CL (mm)", disabled=True, format="%.0f"),
            "Min spacing_mm": st.column_config.NumberColumn("Min spacing (mm)", disabled=True, format="%.0f"),
            "Computed spacing_mm": st.column_config.NumberColumn("Layout spacing (mm)", disabled=True, format="%.0f"),
            "Pe_transfer/strand_kN": st.column_config.NumberColumn("🟨 Pe_transfer / strand (kN)", min_value=0.0, step=10.0, format="%.3f"),
            "Pe_construction/strand_kN": st.column_config.NumberColumn("Pe_construction / strand (kN)", min_value=0.0, step=10.0, format="%.3f"),
            "Pe_eff_final/strand_kN": st.column_config.NumberColumn("🟨 Pe_eff_final / strand (kN)", min_value=0.0, step=10.0, format="%.3f"),
            "Left debond m": st.column_config.NumberColumn("🟨 Left debond (m)", min_value=0.0, max_value=float(span), step=0.5, format="%.3f"),
            "Right debond m": st.column_config.NumberColumn("🟨 Right debond (m)", min_value=0.0, max_value=float(span), step=0.5, format="%.3f"),
            "Debonded strand nos": st.column_config.TextColumn(
                "🟨 Debonded strand nos",
                help="Optional PS6A individual selection, e.g. 1,2,18,19 or 1-4. Blank keeps PS5 row-based all-strands debonding when L/R debond length is nonzero.",
            ),
            "Note": st.column_config.TextColumn("Note"),
        },
        key="girder_strand_layout_editor",
        on_change=_sync_girder_strand_layout_editor_to_table,
        args=(float(span), str(debond_model), geometry),
    )
    normalized = _normalize_girder_strand_layout_table(edited, span_length_m=float(span), debond_model=str(debond_model), geometry=geometry)
    normalized = _apply_computed_girder_strand_spacing(normalized, geometry)
    _store_girder_strand_layout_and_rerun_on_change(current, normalized)

    with st.expander("Computed detailing / advanced strand row data", expanded=False):
        audit_columns = [column for column in GIRDER_STRAND_LAYOUT_AUDIT_COLUMNS if column in normalized.columns]
        st.dataframe(normalized[audit_columns], use_container_width=True, hide_index=True)

    errors, warnings = _validate_girder_strand_layout(normalized, span_length_m=float(span), geometry=geometry)
    preview_status = girder_debonding_preview_status(normalized, span_length_m=float(span))
    metrics = [
        PrestressMetric("Active strand groups", str(len(_active_girder_strand_layout_rows(normalized))), "Rows used by debond preview", "info", strong=True),
        PrestressMetric("Total strands", f"{int((_active_girder_strand_layout_rows(normalized)['No. Strands']).sum())}" if not _active_girder_strand_layout_rows(normalized).empty else "0", "Active groups only", "info"),
        PrestressMetric("Span convention", "x = 0 → L", "Left support to right support", "neutral"),
        PrestressMetric("Debonding QA", preview_status, f"{len(errors)} layout error(s), {len(warnings)} warning(s)", "ready" if preview_status == "OK" else ("danger" if preview_status == "ERROR" else "review"), strong=True),
    ]
    st.markdown(_metric_strip_html(metrics), unsafe_allow_html=True)
    if errors:
        for message in errors:
            st.error(message)
    if warnings:
        with st.expander("Strand layout / debonding warnings", expanded=False):
            for message in warnings:
                st.warning(message)

    is_railway_stage_model = _current_or_geometry_section_preset_key(geometry) == RAILWAY_U_GIRDER_PRESET_KEY
    tab_labels = ["Cross-section layout"]
    if is_railway_stage_model:
        tab_labels.append("Rail U-Girder stages")
    tab_labels.extend(["Debonding along span", "Debonding QA", "Force States / Losses", "Advisory recommendation", "Effective prestress preview"])
    tabs = st.tabs(tab_labels)
    tab_layout = tabs[0]
    offset = 1
    if is_railway_stage_model:
        tab_stage = tabs[1]
        offset = 2
    else:
        tab_stage = None
    tab_debond, tab_rules, tab_losses, tab_advisory, tab_effective = tabs[offset : offset + 5]
    with tab_layout:
        _render_girder_strand_cross_section_dashboard(normalized, geometry)
        with st.expander("Plot assumptions", expanded=False):
            st.caption(
                "PRESTRESS.VIZ2 separates the full-section location schematic from zoomed strand-block detail. "
                "The overall plot is not intended for reading every strand; use the row summary and block detail panels for bonded/debonded review. "
                "Blue markers are bonded/effective strands; red markers are debonded/sleeved selections from PS6A row metadata. "
                "Railway U-Girder drawing debond symbols (0/1000/2000/3000/4000/5000 mm) remain preview metadata only until a station-based pattern milestone. "
                "PS6A supports optional individual bonded/unbonded strand selection within a row. "
                "Blank debonded strand numbers keep the previous row-based all-strands debonding fallback when L/R debond length is nonzero."
            )
    if tab_stage is not None:
        with tab_stage:
            _render_railway_u_girder_stage_model_ui(geometry, span_length_m=float(span))
    with tab_debond:
        if is_railway_stage_model:
            st.caption(
                "Railway U-Girder debonding is shown as a one-web elevation schematic because the default layout is symmetric left/right. "
                "When debonded strand numbers are entered for a row and the debond length is left at zero, the row default is max(0, L/5 - 0.5 m × (row - 1))."
            )
        st.plotly_chart(_plot_girder_longitudinal_debonding_layout(normalized, float(span), one_side_schematic=is_railway_stage_model), use_container_width=True)
        schedule = _girder_debonding_schedule_dataframe(normalized, float(span))
        if not schedule.empty:
            st.dataframe(schedule, use_container_width=True, hide_index=True)
        with st.expander("Plot assumptions", expanded=False):
            st.caption(
                "Solid blue segments are bonded/effective; red dashed end segments are debonded sleeves. "
                "The schematic is a detailing/preview view only. Transfer-length force build-up after each sleeve transition remains a future milestone."
            )
    with tab_rules:
        _render_girder_debonding_rule_dashboard(normalized, float(span))
    with tab_losses:
        _render_girder_force_states_losses_workspace(normalized, geometry)
    with tab_advisory:
        _render_girder_advisory_debonding_recommendation(
            normalized,
            span_length_m=float(span),
            debond_model=str(debond_model),
            geometry=geometry,
        )
    with tab_effective:
        st.caption(
            "Station-based participation preview: debonded strand selections reduce effective Aps and Pe(x) only inside the left/right sleeve zones. "
            "Transfer/development length transition is not modeled yet. Stage Pe values come from the Force States / Losses workflow."
        )
        st.markdown(_metric_strip_html(_stage_pe_mapping_metrics_from_table(normalized)), unsafe_allow_html=True)
        _render_stage_pe_mapping_audit(normalized, expanded=False)
        preview = _girder_effective_prestress_preview_dataframe(normalized, float(span))
        st.dataframe(preview, use_container_width=True, hide_index=True)
        with st.expander("Row-level station participation / analysis handoff", expanded=False):
            st.caption(
                "This table is the solver-adjacent handoff from debonding metadata to station-based SLS/ULS preview workflows. "
                "It is still a step-function model; transfer length, development length, anchorage, and final code-certified debonding checks remain separate."
            )
            participation = girder_station_participation_dataframe(normalized, span_length_m=float(span))
            st.dataframe(participation, use_container_width=True, hide_index=True)

def _dataframes_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    left_norm = pd.DataFrame(left).reset_index(drop=True).astype("object")
    right_norm = pd.DataFrame(right).reset_index(drop=True).astype("object")
    left_norm = left_norm.where(pd.notna(left_norm), None)
    right_norm = right_norm.where(pd.notna(right_norm), None)
    if list(left_norm.columns) != list(right_norm.columns):
        return False
    return left_norm.equals(right_norm)


def _tendon_product_summary_dataframe(products: list[TendonProduct]) -> pd.DataFrame:
    return pd.DataFrame([product.as_dict() for product in products])


def _product_from_row_label(product: str) -> TendonProduct | None:
    return get_tendon_product(product) or _custom_tendon_product_from_label(product)


def _pe_eff_kn_from_row(row: pd.Series) -> float | None:
    if "Pe_eff_kN" in row.index and not _is_blank(row.get("Pe_eff_kN")):
        return _to_float(row.get("Pe_eff_kN"))
    return _to_float(row.get("Pe_eff"))


def _resolve_product_values(row: pd.Series, prestress_db: pd.DataFrame, row_number: int) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    product = "" if _is_blank(row.get("Product")) else str(row.get("Product")).strip()
    tendon_product = _product_from_row_label(product)
    database_row = _product_row(product, prestress_db)

    requested_steel_type = "" if _is_blank(row.get("Steel Type")) else str(row.get("Steel Type")).strip()
    values: dict[str, Any] = {
        "material_name": None if _is_blank(product) or product == "Custom" else product,
        "steel_type": requested_steel_type or "custom",
        "area_mm2": _to_float(row.get("Area_mm2")),
        "diameter_mm": _to_float(row.get("Diameter_mm")),
        "fpy_mpa": _to_float(row.get("fpy_MPa")),
        "fpu_mpa": _to_float(row.get("fpu_MPa")),
        "ep_mpa": _to_float(row.get("Ep_MPa")) or 195000.0,
    }

    if tendon_product is not None:
        if requested_steel_type and requested_steel_type != "tendon_group":
            warnings.append(f"Row {row_number}: Steel Type differs from tendon product type; using tendon_group.")
        values.update(
            {
                "material_name": tendon_product.label,
                "steel_type": "tendon_group",
                "area_mm2": tendon_product.tendon_area_mm2,
                "diameter_mm": None,
                "fpy_mpa": tendon_product.fpy_MPa,
                "fpu_mpa": tendon_product.fpu_MPa,
                "ep_mpa": tendon_product.Ep_MPa,
            }
        )
        return values, errors, warnings

    if database_row is not None:
        database_type = str(database_row["type"])
        if not requested_steel_type:
            values["steel_type"] = database_type
        elif requested_steel_type != database_type:
            warnings.append(f"Row {row_number}: Steel Type differs from database product type; using user-selected Steel Type.")
        values.update(
            {
                "material_name": product,
                "area_mm2": float(database_row["area_mm2"]),
                "diameter_mm": None if pd.isna(database_row["diameter_mm"]) else float(database_row["diameter_mm"]),
                "fpy_mpa": None if pd.isna(database_row["fpy_MPa"]) else float(database_row["fpy_MPa"]),
                "fpu_mpa": None if pd.isna(database_row["fpu_MPa"]) else float(database_row["fpu_MPa"]),
                "ep_mpa": float(database_row["Ep_MPa"]),
            }
        )
        return values, errors, warnings

    if product and product != "Custom":
        if values["area_mm2"] is not None:
            values["material_name"] = product
            if values["steel_type"] == "tendon_group" and not _is_blank(row.get("Strand Count")):
                values["diameter_mm"] = None
                if _looks_like_15_2mm_tendon_group(row):
                    if values["fpy_mpa"] is None:
                        values["fpy_mpa"] = DEFAULT_STRAND_FPY_MPA
                    if values["fpu_mpa"] is None:
                        values["fpu_mpa"] = DEFAULT_STRAND_FPU_MPA
                    values["ep_mpa"] = values["ep_mpa"] or DEFAULT_STRAND_EP_MPA
                return values, errors, warnings
            warnings.append(f"Row {row_number}: Product '{product}' is not in the database; using manual values as custom prestress steel.")
        else:
            errors.append(f"Row {row_number}: Product '{product}' is not in the database and Area_mm2 is blank.")
    elif values["area_mm2"] is None:
        errors.append(f"Row {row_number}: Product or Area_mm2 is required.")

    return values, errors, warnings


def _resolve_initial_state(
    row: pd.Series,
    values: dict[str, Any],
    row_number: int,
) -> tuple[float, float, float, list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    area_mm2 = float(values["area_mm2"] or 0.0)
    ep_mpa = float(values["ep_mpa"] or 195000.0)
    fpu_mpa = values.get("fpu_mpa")
    input_mode = _normalize_input_mode_label(row.get("Input Mode"))

    if input_mode not in INPUT_MODE_OPTIONS and input_mode not in LEGACY_INPUT_MODE_OPTIONS:
        errors.append(f"Row {row_number}: Input Mode must be one of {', '.join(INPUT_MODE_OPTIONS)}.")
        return 0.0, 0.0, 0.0, errors, warnings, info

    if input_mode == "Passive":
        return 0.0, 0.0, 0.0, errors, warnings, info

    if input_mode == "Pe_eff":
        pe_kn = _pe_eff_kn_from_row(row)
        if pe_kn is None:
            warnings.append(f"Row {row_number}: Pe_eff mode has blank Pe_eff_kN; using zero effective prestress.")
            pe_kn = 0.0
        if pe_kn < 0:
            errors.append(f"Row {row_number}: Pe_eff_kN must be greater than or equal to zero.")
            return 0.0, 0.0, 0.0, errors, warnings, info
        if area_mm2 <= 0:
            errors.append(f"Row {row_number}: Area_mm2 must be positive for Pe_eff mode.")
            return 0.0, 0.0, 0.0, errors, warnings, info
        pe_eff_n = kN_to_N(pe_kn)
        initial_stress_mpa = pe_eff_n / area_mm2
        if fpu_mpa is not None:
            fpu_value = float(fpu_mpa)
            if initial_stress_mpa > fpu_value:
                max_pe_eff_kn = area_mm2 * fpu_value / 1000.0
                errors.append(
                    f"Row {row_number}: Initial prestress stress from Pe_eff exceeds fpu_MPa "
                    f"({initial_stress_mpa:,.1f} > {fpu_value:,.1f} MPa). "
                    f"Maximum Pe_eff for Area_mm2 and fpu_MPa is {max_pe_eff_kn:,.1f} kN; "
                    "this row is excluded from the analysis summary until corrected."
                )
                return 0.0, 0.0, 0.0, errors, warnings, info
            if initial_stress_mpa > 0.75 * fpu_value:
                warnings.append(
                    f"Row {row_number}: Effective prestress stress is greater than 0.75 x fpu_MPa; "
                    "high relative to fpu_MPa; verify effective prestress and loss assumptions."
                )
        if pe_eff_n == 0:
            warnings.append(f"Row {row_number}: Pe_eff mode has zero Pe_eff_kN.")
        return pe_eff_n, initial_stress_mpa, initial_stress_mpa / ep_mpa, errors, warnings, info

    if input_mode == "fpe":
        fpe_mpa = _to_float(row.get("fpe_MPa"))
        if fpe_mpa is None:
            warnings.append(f"Row {row_number}: fpe mode has blank fpe_MPa; using zero effective prestress.")
            fpe_mpa = 0.0
        if fpe_mpa < 0:
            errors.append(f"Row {row_number}: fpe_MPa must be greater than or equal to zero.")
        if area_mm2 <= 0:
            errors.append(f"Row {row_number}: Area_mm2 must be positive for fpe mode.")
        if fpu_mpa is not None and fpe_mpa > float(fpu_mpa):
            errors.append(f"Row {row_number}: fpe_MPa must not exceed fpu_MPa.")
        if fpu_mpa is not None and fpe_mpa > 0.75 * float(fpu_mpa):
            warnings.append(
                f"Row {row_number}: fpe_MPa is greater than 0.75 x fpu_MPa; "
                "verify effective prestress and loss assumptions."
            )
        if errors:
            return 0.0, 0.0, 0.0, errors, warnings, info
        if fpe_mpa == 0:
            warnings.append(f"Row {row_number}: fpe mode has zero fpe_MPa.")
        return area_mm2 * fpe_mpa, fpe_mpa, fpe_mpa / ep_mpa, errors, warnings, info

    fpj_ratio = _to_float(row.get("fpj_ratio"))
    loss_percent = _to_float(row.get("loss_percent"))
    if fpu_mpa is None:
        errors.append(f"Row {row_number}: fpu_MPa is required for {JACKING_LOSS_INPUT_MODE} mode.")
    if fpj_ratio is None:
        errors.append(f"Row {row_number}: fpj_ratio must be numeric.")
    elif fpj_ratio < 0:
        errors.append(f"Row {row_number}: fpj_ratio must be greater than or equal to zero.")
    elif fpj_ratio > 1.10:
        errors.append(f"Row {row_number}: fpj_ratio is too high.")
    if loss_percent is None:
        errors.append(f"Row {row_number}: loss_percent must be numeric.")
    elif loss_percent < 0 or loss_percent > 100:
        errors.append(f"Row {row_number}: loss_percent must be between 0 and 100.")
    if errors:
        return 0.0, 0.0, 0.0, errors, warnings, info

    fpu_value = float(fpu_mpa)
    assert fpj_ratio is not None
    assert loss_percent is not None
    fpj_mpa = fpj_ratio * fpu_value
    fpe_mpa = fpj_mpa * (1.0 - loss_percent / 100.0)
    if fpj_ratio > 1.0:
        info.append(f"Row {row_number}: fpj_ratio is greater than 1.0; review jacking stress assumptions.")
    if fpe_mpa > fpu_value:
        errors.append(f"Row {row_number}: effective stress after losses must not exceed fpu_MPa.")
        return 0.0, 0.0, 0.0, errors, warnings, info
    if fpe_mpa > 0.75 * fpu_value:
        warnings.append(
            f"Row {row_number}: effective stress after total loss is greater than 0.75 x fpu_MPa; "
            "verify jacking stress and total loss assumptions."
        )
    if fpe_mpa == 0:
        warnings.append(f"Row {row_number}: {JACKING_LOSS_INPUT_MODE} mode produces zero effective prestress.")
    return area_mm2 * fpe_mpa, fpe_mpa, fpe_mpa / float(values["ep_mpa"]), errors, warnings, info


def prestress_elements_from_dataframe(df: pd.DataFrame, prestress_db: pd.DataFrame) -> PrestressParseResult:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    elements: list[PrestressElement] = []

    for index, row in df.iterrows():
        row_number = int(index) + 1
        if _row_is_blank(row):
            continue
        if not _to_bool(row.get("Active")):
            continue

        x_mm = _to_float(row.get("x_mm"))
        y_mm = _to_float(row.get("y_mm"))
        if x_mm is None:
            errors.append(f"Row {row_number}: x_mm must be numeric.")
        if y_mm is None:
            errors.append(f"Row {row_number}: y_mm must be numeric.")

        count = _to_count(row.get("Count"))
        if count is None:
            errors.append(f"Row {row_number}: Count must be an integer greater than or equal to 1.")
            count = 1

        values, value_errors, value_warnings = _resolve_product_values(row, prestress_db, row_number)
        errors.extend(value_errors)
        warnings.extend(value_warnings)

        steel_type = str(values.get("steel_type") or "").strip()
        if steel_type not in STEEL_TYPE_OPTIONS:
            errors.append(f"Row {row_number}: Steel Type must be one of {', '.join(STEEL_TYPE_OPTIONS)}.")

        area_mm2 = values.get("area_mm2")
        ep_mpa = values.get("ep_mpa")
        if area_mm2 is None or float(area_mm2) <= 0:
            errors.append(f"Row {row_number}: Area_mm2 must be positive.")
        if ep_mpa is None or float(ep_mpa) <= 0:
            errors.append(f"Row {row_number}: Ep_MPa must be positive.")
            values["ep_mpa"] = 195000.0
        if values.get("fpy_mpa") is not None and values.get("fpu_mpa") is not None and float(values["fpy_mpa"]) >= float(values["fpu_mpa"]):
            errors.append(f"Row {row_number}: fpy_MPa must be less than fpu_MPa.")

        if any(error.startswith(f"Row {row_number}:") for error in errors):
            continue

        pe_eff_n, initial_stress_mpa, initial_strain, state_errors, state_warnings, state_info = _resolve_initial_state(row, values, row_number)
        errors.extend(state_errors)
        warnings.extend(state_warnings)
        info.extend(state_info)
        if state_errors:
            continue

        base_label = str(row.get("Label")).strip() if not _is_blank(row.get("Label")) else f"PS{len(elements) + 1}"
        try:
            elements.append(
                PrestressElement(
                    x_mm=float(x_mm),
                    y_mm=float(y_mm),
                    area_mm2=float(values["area_mm2"]),
                    diameter_mm=None if values.get("diameter_mm") is None else float(values["diameter_mm"]),
                    material_name=values.get("material_name"),
                    steel_type=steel_type,
                    fpy_mpa=None if values.get("fpy_mpa") is None else float(values["fpy_mpa"]),
                    fpu_mpa=None if values.get("fpu_mpa") is None else float(values["fpu_mpa"]),
                    ep_mpa=float(values["ep_mpa"]),
                    pe_eff_n=pe_eff_n,
                    initial_stress_mpa=initial_stress_mpa,
                    initial_strain=initial_strain,
                    bonded=_to_bool_default_true(row.get("Bonded")),
                    count=count,
                    label=base_label,
                )
            )
        except ValidationError as exc:
            errors.append(f"Row {row_number}: {exc.errors()[0]['msg']}")

    active_count = len(elements)
    total_aps = sum(element.total_area_mm2 for element in elements)
    total_pe = sum(element.pe_eff_n * element.count for element in elements)
    info.extend([f"{active_count} active prestress element(s).", f"Total Aps = {total_aps:,.1f} mm^2.", f"Total Pe_eff = {total_pe:,.1f} N."])
    return PrestressParseResult(elements=elements, errors=errors, warnings=warnings, info=info)


def validate_prestress_against_geometry(elements: list[PrestressElement], geometry: SectionGeometry | None) -> list[str]:
    if geometry is None:
        return []
    section = to_shapely_polygon(geometry)
    hole_polygons = [Polygon([point.as_tuple() for point in hole]) for hole in geometry.holes]
    errors: list[str] = []
    for index, element in enumerate(elements, start=1):
        label = element.label or f"Prestress {index}"
        point = Point(element.x_mm, element.y_mm)
        if any(hole.covers(point) for hole in hole_polygons):
            errors.append(f"{label}: prestress element is inside a void/hole.")
        elif not section.covers(point):
            errors.append(f"{label}: prestress element is outside concrete.")
    return errors


def prestress_valid_for_analysis(parse_result: PrestressParseResult, geometry_errors: list[str]) -> bool:
    return not parse_result.errors and not geometry_errors


def _prestress_analysis_role(element: PrestressElement) -> str:
    """Return a user-facing role for a prestress row in the analysis model."""

    pe_eff = float(element.pe_eff_n or 0.0)
    initial_stress = float(element.initial_stress_mpa or 0.0)
    initial_strain = float(element.initial_strain or 0.0)
    if pe_eff > 0.0 or initial_stress > 0.0 or initial_strain > 0.0:
        return "Active bonded prestress" if element.bonded else "Active unbonded prestress (ignored)"
    return "Passive bonded high-strength steel" if element.bonded else "Passive unbonded steel (ignored)"


def prestress_summary_dataframe(elements: list[PrestressElement]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Label": element.label,
                "Analysis role": _prestress_analysis_role(element),
                "material_name": element.material_name,
                "steel_type": element.steel_type,
                "x_mm": element.x_mm,
                "y_mm": element.y_mm,
                "area_mm2": element.area_mm2,
                "diameter_mm": element.diameter_mm,
                "fpy_mpa": element.fpy_mpa,
                "fpu_mpa": element.fpu_mpa,
                "ep_mpa": element.ep_mpa,
                "pe_eff_n": element.pe_eff_n,
                "total_area_mm2": element.total_area_mm2,
                "total_pe_eff_n": element.pe_eff_n * element.count,
                "initial_stress_mpa": element.initial_stress_mpa,
                "initial_strain": element.initial_strain,
                "bonded": element.bonded,
                "count": element.count,
            }
            for element in elements
        ]
    )


def _safe_status(status: str) -> str:
    return status if status in {"ready", "warning", "danger", "info", "neutral"} else "neutral"


def _badge_html(value: str, status: str) -> str:
    return f'<span class="cpmm-prestress-badge {_safe_status(status)}">{escape(value)}</span>'


def _metric_strip_html(metrics: list[PrestressMetric]) -> str:
    chips: list[str] = []
    for metric in metrics:
        status = _safe_status(metric.status)
        value_html = _badge_html(metric.value, status) if metric.strong else escape(metric.value)
        detail_html = f'<div class="cpmm-prestress-chip-detail">{escape(metric.detail)}</div>' if metric.detail else ""
        chips.append(
            '<div class="cpmm-prestress-chip">'
            f'<div class="cpmm-prestress-chip-label">{escape(metric.title)}</div>'
            f'<div class="cpmm-prestress-chip-value">{value_html}</div>'
            f"{detail_html}"
            "</div>"
        )
    return '<div class="cpmm-prestress-strip">' + "".join(chips) + "</div>"


def _status_panel_html(rows: list[PrestressMetric]) -> str:
    row_html: list[str] = []
    for row in rows:
        value_html = _badge_html(row.value, row.status) if row.strong else escape(row.value)
        row_html.append(
            '<div class="cpmm-prestress-kv-row">'
            f'<div class="cpmm-prestress-kv-label">{escape(row.title)}</div>'
            f'<div class="cpmm-prestress-kv-value">{value_html}</div>'
            "</div>"
        )
    return '<div class="cpmm-prestress-kv-panel">' + "".join(row_html) + "</div>"


def _message_list_html(messages: list[str]) -> str:
    if not messages:
        return ""
    items = "".join(f'<div class="cpmm-prestress-message-item">{escape(message)}</div>' for message in messages)
    return f'<div class="cpmm-prestress-message-list">{items}</div>'


def _engineering_notes_html() -> str:
    notes = [
        "Choose Passive for non-prestressed steel contribution. Choose Pe_eff to enter effective force directly.",
        "Choose fpe to enter effective stress and compute Pe_eff from Area_mm2; Pe_eff is after selected losses.",
        "Choose Jacking + Total Loss % to compute fpe from fpj_ratio x fpu and total loss percentage.",
        "Product breaking load is reference data only and is never used as Pe_eff.",
        "Duct ID is duct reference information and is not steel diameter.",
        "For tendon_group rows, Area_mm2 controls steel area; Eq Steel Dia_mm is display and preview information only.",
        "Prestress is treated as internal section action, not external Pu demand.",
    ]
    items = "".join(f'<div class="cpmm-prestress-note-item">{escape(note)}</div>' for note in notes)
    return f'<div class="cpmm-prestress-note-panel">{items}</div>'


def _input_mode_guide_html() -> str:
    cards = [
        ("Passive", "No effective prestress force. The steel is included as passive high-strength steel only."),
        ("Pe_eff", "Enter effective prestress force in kN after losses. fpe is computed from Pe_eff / Area."),
        ("fpe", "Enter effective prestress stress in MPa after losses. Pe_eff is computed from Area x fpe."),
        ("Jacking + Total Loss %", "Enter fpj_ratio and total loss percentage. Pe_eff is computed from Area x fpj_ratio x fpu x (1 - loss%)."),
    ]
    card_html = "".join(
        '<div class="cpmm-prestress-mode-card">'
        f'<div class="cpmm-prestress-mode-title">{escape(title)}</div>'
        f'<div class="cpmm-prestress-mode-text">{escape(text)}</div>'
        '</div>'
        for title, text in cards
    )
    return f'<div class="cpmm-prestress-mode-guide">{card_html}</div>'


def _product_selection_guide_html(product_options: list[str]) -> str:
    """Return a compact guide explaining Product dropdown organization."""

    tendon_count = sum(1 for option in product_options if _tendon_6n_count_from_label(option) is not None)
    strand_count = sum(1 for option in product_options if "strand" in option.lower() and _tendon_6n_count_from_label(option) is None)
    bar_count = sum(1 for option in product_options if "bar" in option.lower())
    cards = [
        ("Tendon catalog", f"{tendon_count} standard choices: Tendon 6-1 to Tendon 6-55."),
        ("PT / PS bars", f"{bar_count} bar product choices follow the tendon list."),
        ("Compatibility", "Legacy labels such as 6-12 are accepted and displayed as Tendon 6-12."),
    ]
    if strand_count:
        cards.insert(1, ("Single strand", f"{strand_count} strand product choice(s) remain available."))
    card_html = "".join(
        '<div class="cpmm-prestress-mode-card">'
        f'<div class="cpmm-prestress-mode-title">{escape(title)}</div>'
        f'<div class="cpmm-prestress-mode-text">{escape(text)}</div>'
        '</div>'
        for title, text in cards
    )
    return f'<div class="cpmm-prestress-mode-guide">{card_html}</div>'


def _row_numbers_from_errors(errors: list[str]) -> set[int]:
    row_numbers: set[int] = set()
    for message in errors:
        match = re.match(r"Row\s+(\d+):", message)
        if match:
            row_numbers.add(int(match.group(1)))
    return row_numbers


def _invalid_prestress_rows_dataframe(table: pd.DataFrame, errors: list[str]) -> pd.DataFrame:
    """Return user-facing rows excluded from analysis because of validation errors."""

    row_numbers = _row_numbers_from_errors(errors)
    if not row_numbers:
        return pd.DataFrame()
    source = pd.DataFrame(table).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for row_number in sorted(row_numbers):
        if row_number < 1 or row_number > len(source):
            continue
        row = source.iloc[row_number - 1]
        reasons = [message for message in errors if message.startswith(f"Row {row_number}:")]
        rows.append(
            {
                "Row": row_number,
                "Label": row.get("Label"),
                "Product": row.get("Product"),
                "Input Mode": row.get("Input Mode"),
                "Area_mm2": row.get("Area_mm2"),
                "Pe_eff_kN": row.get("Pe_eff_kN"),
                "fpe_MPa": row.get("fpe_MPa"),
                "Reason excluded": " | ".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def _build_prestress_summary_metrics(
    result: PrestressParseResult,
    geometry_errors: list[str],
    valid_for_analysis: bool,
    active_rebar_count: int = 0,
) -> list[PrestressMetric]:
    total_aps = sum(element.total_area_mm2 for element in result.elements)
    total_pe_kn = sum(element.pe_eff_n * element.count for element in result.elements) / 1000.0
    tendon_group_count = sum(1 for element in result.elements if element.steel_type == "tendon_group")
    strand_pt_count = sum(1 for element in result.elements if element.steel_type in {"strand", "prestressing_bar"})
    bonded_count = sum(1 for element in result.elements if element.bonded)
    unbonded_count = sum(1 for element in result.elements if not element.bonded)
    error_count = len(result.errors) + len(geometry_errors)
    warning_count = len(result.warnings)
    if not result.elements and active_rebar_count == 0:
        warning_count += 1
    return [
        _prestress_force_state_label(result.elements),
        PrestressMetric("Valid elements", f"{len(result.elements):,}", detail="used in analysis", status="info"),
        PrestressMetric("Total Aps", f"{total_aps:,.1f} mm2"),
        PrestressMetric("Total Pe_eff", f"{total_pe_kn:,.1f} kN", detail="valid rows only"),
        PrestressMetric("Analysis readiness", "Yes" if valid_for_analysis else "No", status="ready" if valid_for_analysis else "danger", strong=True),
        PrestressMetric("Tendon groups", f"{tendon_group_count:,}", detail=f"Strand/PT bars: {strand_pt_count:,}"),
        PrestressMetric("Bonded state", f"{bonded_count:,} / {unbonded_count:,}", detail="bonded / unbonded", status="warning" if unbonded_count else "neutral"),
        PrestressMetric("Input modes", "See table", detail="Passive / Pe_eff / fpe / Jacking + loss"),
        PrestressMetric("Validation", f"{error_count:,} error(s)", detail=f"{warning_count:,} warning(s)", status="danger" if error_count else ("warning" if warning_count else "ready"), strong=bool(error_count)),
    ]


def _build_prestress_status_rows(
    result: PrestressParseResult,
    geometry_errors: list[str],
    geometry_available: bool,
    valid_for_analysis: bool,
    active_rebar_count: int = 0,
    *,
    girder_workflow: bool = False,
) -> list[PrestressMetric]:
    if girder_workflow:
        rows = [
            PrestressMetric(
                "Overall readiness",
                "Ready" if geometry_available else "Not ready",
                detail="girder strand workflow",
                status="ready" if geometry_available else "danger",
                strong=True,
            ),
            PrestressMetric(
                "Section-level tendon table",
                "Hidden / ignored",
                detail="precast girder uses strand layout",
                status="neutral",
                strong=True,
            ),
        ]
        rows.extend(_girder_strand_layout_status_metrics())
        return rows

    all_errors = [*result.errors, *geometry_errors]
    warnings = list(result.warnings)
    if not result.elements and active_rebar_count == 0:
        warnings.append("No active longitudinal reinforcement is defined. Activate ordinary rebar or prestress before final analysis.")
    if not geometry_available:
        warnings.append("Section geometry is not available yet.")
    total_aps = sum(element.total_area_mm2 for element in result.elements)
    total_pe_kn = sum(element.pe_eff_n * element.count for element in result.elements) / 1000.0
    tendon_group_count = sum(1 for element in result.elements if element.steel_type == "tendon_group")
    bonded_count = sum(1 for element in result.elements if element.bonded)
    unbonded_count = sum(1 for element in result.elements if not element.bonded)
    rows = [
        PrestressMetric("Overall readiness", "Ready" if valid_for_analysis else "Not ready", status="ready" if valid_for_analysis else "danger", strong=True),
        _prestress_force_state_label(result.elements),
        PrestressMetric("Validation errors", f"{len(all_errors):,}", status="danger" if all_errors else "ready", strong=bool(all_errors)),
        PrestressMetric("Warnings", f"{len(warnings):,}", status="warning" if warnings else "ready", strong=bool(warnings)),
        PrestressMetric("Valid elements", f"{len(result.elements):,}"),
        PrestressMetric("Total Aps", f"{total_aps:,.1f} mm2", detail="section-level table"),
        PrestressMetric("Valid Pe_eff", f"{total_pe_kn:,.1f} kN", detail="section-level table"),
        PrestressMetric("Tendon groups", f"{tendon_group_count:,}"),
        PrestressMetric("Bonded / unbonded", f"{bonded_count:,} / {unbonded_count:,}"),
    ]
    rows.extend(_girder_strand_layout_status_metrics())
    return rows




def _girder_strand_layout_status_metrics() -> list[PrestressMetric]:
    """Return compact status rows for the girder strand layout metadata.

    The section-level tendon table and the dedicated simple-supported girder
    strand layout are different input systems.  Showing the strand-layout
    counts separately prevents a misleading "No active rows" tendon-table
    message from being read as "no girder strands are defined".
    """

    if not _is_girder_prestress_layout_workflow_active():
        return []
    table = st.session_state.get("girder_strand_layout_table")
    if table is None:
        return [PrestressMetric("Girder strand layout", "Not defined", detail="metadata only", status="neutral")]
    try:
        active = _active_girder_strand_layout_rows(pd.DataFrame(table))
    except Exception:
        active = pd.DataFrame()
    if active.empty:
        return [PrestressMetric("Girder strand layout", "No active groups", detail="metadata only", status="neutral")]
    total_strands = int(sum(int(_to_float(row.get("No. Strands")) or 0) for _, row in active.iterrows()))
    total_aps = float(sum(float(_to_float(row.get("Total Aps_mm2")) or 0.0) for _, row in active.iterrows()))
    pe_transfer = float(
        sum(
            int(_to_float(row.get("No. Strands")) or 0) * float(_to_float(row.get("Pe_transfer/strand_kN")) or 0.0)
            for _, row in active.iterrows()
        )
    )
    pe_final = float(
        sum(
            int(_to_float(row.get("No. Strands")) or 0) * float(_to_float(row.get("Pe_eff_final/strand_kN")) or 0.0)
            for _, row in active.iterrows()
        )
    )
    return [
        PrestressMetric("Girder strand layout", f"{total_strands:,} strands", detail="layout metadata", status="info", strong=True),
        PrestressMetric("Layout Aps", f"{total_aps:,.1f} mm2", detail="from strand rows"),
        PrestressMetric("Layout Pe_transfer", f"{pe_transfer:,.1f} kN", detail="from strand force states"),
        PrestressMetric("Layout Pe_eff_final", f"{pe_final:,.1f} kN", detail="from strand force states"),
    ]

def _build_girder_prestress_summary_metrics() -> list[PrestressMetric]:
    rows = [
        PrestressMetric(
            "Prestress workflow",
            "Girder strand layout",
            detail="simple-supported precast girder",
            status="info",
            strong=True,
        ),
        PrestressMetric(
            "Section-level table",
            "Hidden / ignored",
            detail="no PS1/PS2 in main workflow",
            status="neutral",
        ),
    ]
    rows.extend(_girder_strand_layout_status_metrics())
    return rows


def _render_prestress_summary_strip(
    result: PrestressParseResult,
    geometry_errors: list[str],
    valid_for_analysis: bool,
    active_rebar_count: int = 0,
) -> None:
    st.markdown(
        _metric_strip_html(_build_prestress_summary_metrics(result, geometry_errors, valid_for_analysis, active_rebar_count)),
        unsafe_allow_html=True,
    )


def _render_tendon_product_tools() -> None:
    st.markdown("#### Tendon Product Creation")
    st.markdown(
        '<div class="cpmm-prestress-quiet-note">'
        "Select a standard or custom 15.2 mm tendon product to populate product metadata and total tendon steel area. "
        "Effective prestress remains controlled in the Advanced Prestress Table."
        "</div>",
        unsafe_allow_html=True,
    )
    mode = st.radio(
        "Product creation mode",
        TENDON_PRODUCT_CREATION_MODES,
        horizontal=True,
        key="prestress_tendon_product_mode",
    )
    products = list_tendon_products()
    with st.expander("Standard tendon product database", expanded=False):
        st.dataframe(_tendon_product_summary_dataframe(products), use_container_width=True, hide_index=True)

    current_table = st.session_state.get("prestress_table")
    if current_table is None:
        current_table = pd.DataFrame()
    next_label = f"PS{len(current_table) + 1}"
    base_row = _blank_prestress_row(next_label)

    if mode == "Standard tendon product":
        product_options = tendon_product_options()
        default_product = standard_tendon_label(12)
        product_label = st.selectbox(
            "Standard tendon product",
            product_options,
            index=product_options.index(default_product) if default_product in product_options else 0,
        )
        product = get_tendon_product(product_label)
        assert product is not None
        st.dataframe(_tendon_product_summary_dataframe([product]), use_container_width=True, hide_index=True)
        row = apply_tendon_product_to_row(base_row, product)
        if st.button("Add standard tendon to table", use_container_width=True, type="primary", key="ui_keys1_prestress_page_button_5494"):
            st.session_state["prestress_table"] = _normalize_prestress_table_for_display(_append_prestress_row(pd.DataFrame(current_table), row))
            st.success(f"Added tendon product {product.label}. Pe_eff remains user-controlled.")
        return

    custom_label = st.text_input("Custom label", value="", placeholder="6-25")
    custom_cols = st.columns(3)
    strand_count = int(custom_cols[0].number_input("Strand count", min_value=1, value=25, step=1))
    strand_area = float(custom_cols[1].number_input("Strand area (mm2)", min_value=1.0, value=140.0, step=1.0))
    strand_diameter = float(custom_cols[2].number_input("Strand diameter (mm)", min_value=1.0, value=15.2, step=0.1))
    ref_cols = st.columns(3)
    breaking_load_per_strand = float(ref_cols[0].number_input("Breaking load per strand (kN)", min_value=1.0, value=260.0, step=1.0))
    duct_id = ref_cols[1].number_input("Duct ID reference (mm)", min_value=0.0, value=0.0, step=1.0)
    duct_type = ref_cols[2].text_input("Duct type reference", value="")
    product = make_custom_tendon_product(
        strand_count=strand_count,
        label=custom_label or None,
        strand_area_mm2=strand_area,
        breaking_load_per_strand_kN=breaking_load_per_strand,
        strand_diameter_mm=strand_diameter,
        duct_id_mm=None if duct_id <= 0 else float(duct_id),
        duct_type=duct_type or None,
    )
    st.dataframe(_tendon_product_summary_dataframe([product]), use_container_width=True, hide_index=True)
    row = apply_tendon_product_to_row(base_row, product)
    if st.button("Add custom tendon to table", use_container_width=True, type="primary", key="ui_keys1_prestress_page_button_5519"):
        st.session_state["prestress_table"] = _normalize_prestress_table_for_display(_append_prestress_row(pd.DataFrame(current_table), row))
        st.success(f"Added custom tendon {product.label}. Pe_eff remains user-controlled.")


def _default_auto_prestress_product_option(product_options: list[str]) -> int:
    for preferred in ("15.2mm strand", "12.7mm strand", "PS Bar 32 - 1080/1230"):
        if preferred in product_options:
            return product_options.index(preferred)
    for index, option in enumerate(product_options):
        if option and option != "Custom":
            return index
    return 0


def _render_auto_perimeter_prestress_controls(
    prestress_db: pd.DataFrame,
    geometry: SectionGeometry | None,
    product_options: list[str],
) -> AutoPrestressLayoutResult:
    st.markdown("##### Auto perimeter prestress layout")
    st.caption(
        "Preview prestressing steel points offset from the current section perimeter, then append or replace the generated rows in the Prestress table. "
        "Manual rows are not changed unless you press an Apply button."
    )
    control_cols = st.columns([1.15, 0.85, 0.85, 0.75], gap="small")
    with control_cols[0]:
        product = st.selectbox(
            "Prestress product",
            product_options,
            index=_default_auto_prestress_product_option(product_options),
            key="prestress_auto_perimeter_product",
            help="Select a catalog strand, PT/PS bar, or tendon product. Custom rows are not generated automatically in this milestone.",
        )
    with control_cols[1]:
        edge_offset_mm = st.number_input(
            "Center offset (mm)",
            min_value=1.0,
            value=75.0,
            step=5.0,
            key="prestress_auto_perimeter_edge_offset_mm",
        )
    with control_cols[2]:
        target_spacing_mm = st.number_input(
            "Target spacing (mm)",
            min_value=1.0,
            value=150.0,
            step=10.0,
            key="prestress_auto_perimeter_target_spacing_mm",
        )
    with control_cols[3]:
        min_elements = st.number_input(
            "Minimum points",
            min_value=1,
            value=4,
            step=1,
            key="prestress_auto_perimeter_min_elements",
        )

    detail_cols = st.columns([0.9, 1.2, 0.65], gap="small")
    with detail_cols[0]:
        label_prefix = st.text_input("Label prefix", value="PS-AUTO-", key="prestress_auto_perimeter_label_prefix")
    with detail_cols[1]:
        input_mode = st.selectbox(
            "Generated force input mode",
            INPUT_MODE_EDITOR_OPTIONS,
            index=INPUT_MODE_EDITOR_OPTIONS.index(JACKING_LOSS_INPUT_MODE) if JACKING_LOSS_INPUT_MODE in INPUT_MODE_EDITOR_OPTIONS else 0,
            key="prestress_auto_perimeter_input_mode",
        )
    with detail_cols[2]:
        bonded = st.checkbox("Bonded", value=True, key="prestress_auto_perimeter_bonded")

    result = generate_auto_perimeter_prestress_layout(
        geometry,
        prestress_db,
        product=product,
        edge_offset_mm=float(edge_offset_mm),
        target_spacing_mm=float(target_spacing_mm),
        min_elements=int(min_elements),
        label_prefix=label_prefix,
        input_mode=input_mode,
        bonded=bool(bonded),
    )

    for error in result.errors:
        st.error(f"ERROR: {error}")
    for warning in result.warnings:
        st.warning(f"WARNING: {warning}")
    for info in result.info:
        st.info(f"INFO: {info}")

    if result.ok and not result.table.empty:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Generated points", f"{len(result.table.index):,}")
        metric_cols[1].metric("Actual spacing", f"{(result.actual_spacing_mm or 0.0):.1f} mm")
        metric_cols[2].metric("Offset", f"{edge_offset_mm:.1f} mm")
        total_pe = float(pd.to_numeric(result.table.get("Pe_eff_kN", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
        metric_cols[3].metric("Total Pe_eff", f"{total_pe:,.1f} kN")
        st.dataframe(
            result.table[["Active", "Label", "Product", "x_mm", "y_mm", "Area_mm2", "Input Mode", "Pe_eff_kN", "fpe_MPa", "Bonded", "Count", "Note"]],
            use_container_width=True,
            hide_index=True,
        )
        apply_cols = st.columns(2, gap="medium")
        with apply_cols[0]:
            if st.button("Append generated rows", type="primary", use_container_width=True, key="prestress_auto_append_perimeter_layout"):
                current = pd.DataFrame(st.session_state.get("prestress_table", pd.DataFrame()))
                combined = pd.concat([current, result.table], ignore_index=True, sort=False)
                st.session_state["prestress_table"] = normalize_prestress_table_for_effective_input_sync(combined, prestress_db)
                st.session_state["prestress_editor_revision"] = int(st.session_state.get("prestress_editor_revision", 0)) + 1
                st.rerun()
        with apply_cols[1]:
            if st.button("Replace table with generated rows", use_container_width=True, key="prestress_auto_replace_perimeter_layout"):
                st.session_state["prestress_table"] = normalize_prestress_table_for_effective_input_sync(result.table, prestress_db)
                st.session_state["prestress_editor_revision"] = int(st.session_state.get("prestress_editor_revision", 0)) + 1
                st.rerun()
    else:
        st.caption("No generated prestress perimeter layout is available yet.")

    return result


def _render_validation(
    result: PrestressParseResult,
    geometry_errors: list[str],
    geometry_available: bool,
    valid_for_analysis: bool,
    active_rebar_count: int = 0,
) -> None:
    st.markdown("#### Prestress Status")
    all_errors = [*result.errors, *geometry_errors]
    warnings = list(result.warnings)
    contextual_notes: list[str] = []
    girder_workflow = _is_girder_prestress_layout_workflow_active()
    if girder_workflow:
        contextual_notes.append(
            "Precast girder workflow uses the Simple-Supported Girder Strand Layout & Debonding table. "
            "Section-level tendon/prestress rows are hidden and ignored here."
        )
    elif not result.elements and active_rebar_count > 0:
        contextual_notes.append(
            "No active prestress elements. The section will be analyzed as RC-only unless prestress rows are activated."
        )
    elif not result.elements:
        warnings.append("No active longitudinal reinforcement is defined. Activate ordinary rebar or prestress before final analysis.")
    elif not _has_active_prestress_force(result.elements):
        contextual_notes.append(
            "Active prestress rows are reference/passive only. They are preserved and previewable, but they do not add Pe to analysis until Pe_eff, fpe, or initial stress is assigned."
        )
    if not geometry_available:
        warnings.append("Section geometry is not available yet; geometry validation will run after a valid section is generated.")
    st.markdown(
        _status_panel_html(
            _build_prestress_status_rows(
                result,
                geometry_errors,
                geometry_available,
                valid_for_analysis,
                active_rebar_count,
                girder_workflow=girder_workflow,
            )
        ),
        unsafe_allow_html=True,
    )
    messages = [f"ERROR: {error}" for error in all_errors] or ["No validation errors."]
    messages.extend(f"WARNING: {warning}" for warning in warnings)
    messages.extend(f"INFO: {note}" for note in contextual_notes)
    messages.extend(f"INFO: {item}" for item in result.info)
    st.markdown(_message_list_html(messages), unsafe_allow_html=True)



def _render_prestress_section_preview_panel(
    geometry: SectionGeometry | None,
    result: PrestressParseResult,
    *,
    show_combined_preview: bool = True,
) -> None:
    """Render Prestress-page previews with a clear preview policy.

    The Prestress page owns prestressing steel layout, so its default preview
    must not show ordinary rebar.  A combined reinforcement preview remains
    available in a collapsed expander for coordination checks only.  When
    Prestress is enabled, the section preview is rendered directly on the page
    even for passive/reference rows so users can immediately verify tendon
    locations after enabling the Prestress system in Section Builder.
    """

    st.markdown("#### Section Preview with Prestress")
    if geometry is None:
        st.caption("Section geometry is not available yet. Build a valid section before previewing prestress layout.")
        return

    # Prestress-page previews are steel-layout views, not dimension-review views.
    # Keep section dimension guides owned by Section Builder so tendon graphics are
    # not crowded by bridge-girder dimension annotations.
    preview_dimensions: list[Any] = []
    active_prestress = list(result.elements or [])

    if active_prestress:
        if _has_active_prestress_force(active_prestress):
            st.caption(
                "Default preview shows prestressing steel only. Ordinary rebar and dimension guides are intentionally hidden on the Prestress page."
            )
        else:
            st.caption(
                "Preview shows active prestress/reference rows immediately. Dimension guides are intentionally hidden; reference-only rows do not add Pe to analysis until Pe_eff, fpe, or initial stress is assigned."
            )
        fig = create_section_preview(
            geometry,
            preview_dimensions,
            "symbol_value",
            [],
            active_prestress,
        )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=34, b=8))
        st.plotly_chart(fig, use_container_width=True, key="prestress_only_section_preview")
    else:
        st.caption(
            "Prestress is enabled, but no active prestressing steel rows are available yet. Geometry-only preview is shown without dimension guides until tendon rows are activated."
        )
        fig = create_section_preview(
            geometry,
            preview_dimensions,
            "symbol_value",
            [],
            [],
        )
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=34, b=8))
        st.plotly_chart(fig, use_container_width=True, key="prestress_geometry_only_section_preview")

    if show_combined_preview and active_prestress and ordinary_rebar_enabled(st.session_state, default=True):
        rebars = list(st.session_state.get("rebars", []) or [])
        if rebars:
            with st.expander("Combined Reinforcement Preview", expanded=False):
                st.caption(
                    "Coordination view only: ordinary rebar and prestressing steel are shown together. "
                    "Default page previews remain separated to avoid mixing rebar and prestress workflows."
                )
                combined_fig = create_section_preview(
                    geometry,
                    preview_dimensions,
                    "symbol_value",
                    rebars,
                    active_prestress,
                )
                combined_fig.update_layout(height=380, margin=dict(l=10, r=10, t=34, b=8))
                st.plotly_chart(combined_fig, use_container_width=True, key="prestress_combined_reinforcement_preview")

def _commercial_prestress_dashboard_cards() -> list[dict[str, object]]:
    """Return visual-only dashboard cards for the Prestress workspace."""

    table = pd.DataFrame(st.session_state.get("prestress_table", []))
    active_rows = int(pd.Series(table.get("Active", pd.Series(dtype=bool))).fillna(False).astype(bool).sum()) if not table.empty else 0
    try:
        total_area = float(pd.to_numeric(table.get("Area_mm2", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
    except Exception:
        total_area = 0.0
    force_status = "Active" if prestressing_steel_enabled(st.session_state, default=True) else "Disabled"
    bonded_rows = 0
    if not table.empty and "Bonded" in table.columns:
        bonded_rows = int(pd.Series(table["Bonded"]).fillna(False).astype(bool).sum())
    input_modes = sorted({str(v) for v in table.get("Input Mode", pd.Series(dtype=str)).dropna().tolist() if str(v).strip()}) if not table.empty else []
    return [
        {"title": "Prestress status", "value": force_status, "detail": "Controlled by Section Builder steel systems", "status": "ready" if force_status == "Active" else "warning"},
        {"title": "Active elements", "value": f"{active_rows:,}", "detail": f"Bonded rows: {bonded_rows:,}", "status": "ready" if active_rows else "warning"},
        {"title": "Total Ap", "value": f"{total_area:,.1f} mm²", "detail": "From prestress table rows", "status": "info"},
        {"title": "Input modes", "value": f"{len(input_modes):,}", "detail": ", ".join(input_modes[:2]) if input_modes else "No active mode yet", "status": "neutral"},
    ]


def _render_engineering_notes() -> None:
    st.markdown("#### Engineering Notes")
    st.markdown(_engineering_notes_html(), unsafe_allow_html=True)


def render_prestress_page() -> None:
    st.markdown(_PRESTRESS_PAGE_CSS, unsafe_allow_html=True)
    render_page_header(
        "Prestress",
        "Manage strand/tendon force definitions, bonded state, loss method, and staged Pe handoff for SLS and strength checks.",
        icon="PS",
        kicker="Prestress workspace",
        badge="Force model",
        accent="purple",
    )
    render_metric_cards(_commercial_prestress_dashboard_cards())
    render_section_bar("Prestress input workflow", "Force rows, tendon products, losses, and stage Pe mapping are edited below.", mark="P")
    prestress_db = _combined_prestress_database(load_prestress_steel_database(), st.session_state.get("prestress_materials", []))

    if not prestressing_steel_enabled(st.session_state, default=True):
        st.info(
            "Prestressing steel is disabled for the current section in Section Builder. "
            "Stored Prestress table and girder strand/debonding data are preserved, but prestress is ignored by analysis until you enable it again."
        )
        with st.expander("Stored Prestress table preview", expanded=False):
            table = st.session_state.get("prestress_table")
            if table is None:
                st.caption("No stored Prestress table is available yet.")
            else:
                st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        with st.expander("Stored girder strand/debonding metadata", expanded=False):
            strand_table = st.session_state.get("girder_strand_layout_table")
            if strand_table is None:
                st.caption("No stored strand layout table is available yet.")
            else:
                st.dataframe(pd.DataFrame(strand_table), use_container_width=True, hide_index=True)
        st.session_state["prestress_valid_for_analysis"] = True
        return

    if "prestress_table" not in st.session_state:
        st.session_state["prestress_table"] = _default_prestress_table(prestress_db)
    st.session_state["prestress_table"] = normalize_prestress_table_for_effective_input_sync(pd.DataFrame(st.session_state["prestress_table"]), prestress_db)
    st.session_state.setdefault("prestress_editor_revision", 0)

    summary_slot = st.empty()
    main_col, side_col = st.columns([0.68, 0.32], gap="large")
    girder_prestress_layout_active = _is_girder_prestress_layout_workflow_active()

    edited_df = pd.DataFrame(st.session_state["prestress_table"])
    with main_col:
        if girder_prestress_layout_active:
            st.markdown("#### Precast Girder Prestress Workflow")
            st.info(
                "This precast girder section uses the Simple-Supported Girder Strand Layout & Debonding workflow. "
                "The legacy section-level tendon/prestress table is hidden and ignored for this section family."
            )
        else:
            with st.expander("Section-level tendon / prestress table", expanded=True):
                st.markdown("#### Prestress Input Workflow")
                if PRESTRESS_LAYOUT_METHOD_STATE_KEY not in st.session_state:
                    st.session_state[PRESTRESS_LAYOUT_METHOD_STATE_KEY] = MANUAL_PRESTRESS_LAYOUT_METHOD
                if _is_planned_prestress_layout_method(st.session_state.get(PRESTRESS_LAYOUT_METHOD_STATE_KEY)):
                    st.session_state[PRESTRESS_LAYOUT_METHOD_NOTICE_KEY] = st.session_state[PRESTRESS_LAYOUT_METHOD_STATE_KEY]
                    st.session_state[PRESTRESS_LAYOUT_METHOD_STATE_KEY] = MANUAL_PRESTRESS_LAYOUT_METHOD
                layout_method = st.selectbox(
                    "Prestress layout method",
                    PRESTRESS_LAYOUT_METHOD_OPTIONS,
                    key=PRESTRESS_LAYOUT_METHOD_STATE_KEY,
                    help=(
                        "Manual table is the implemented section-level prestress workflow. "
                        "Linear and circular auto-layout generators are planned and currently guarded."
                    ),
                    on_change=_guard_prestress_layout_method_selection,
                )
                planned_layout_notice = st.session_state.pop(PRESTRESS_LAYOUT_METHOD_NOTICE_KEY, None)
                if planned_layout_notice:
                    st.warning(_planned_prestress_layout_message(planned_layout_notice))
                st.caption(
                    "Use the table row Input Mode to define Passive, Pe_eff, fpe, or Jacking + Total Loss %. "
                    f"Active layout method: {layout_method}."
                )
                product_options = _product_options_for_table(prestress_db, pd.DataFrame(st.session_state["prestress_table"]))

                with st.expander("Tendon Product Creation / product database", expanded=False):
                    _render_tendon_product_tools()

                if layout_method == AUTO_PERIMETER_PRESTRESS_LAYOUT_METHOD:
                    _render_auto_perimeter_prestress_controls(prestress_db, st.session_state.get("section_geometry"), product_options)

                st.markdown("#### Advanced Prestress Table")
                st.markdown(
                    '<div class="cpmm-prestress-quiet-note">'
                    "Compact editor for the fields that normally control analysis: location, product, area, effective prestress, bonded state, and count. "
                    "Product/material reference fields are preserved in the backing table and shown below as read-only details."
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="cpmm-prestress-table-note">'
                    "Editing Product updates Area/material metadata through the existing product-sync logic. "
                    "Breaking Load and Duct ID remain reference data only; they are not used as Pe_eff or steel diameter."
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(_input_mode_guide_html(), unsafe_allow_html=True)
                st.markdown(_product_selection_guide_html(product_options), unsafe_allow_html=True)
                st.markdown("##### Prestress force input method")
                method_col, apply_col = st.columns([0.74, 0.26], gap="medium")
                with method_col:
                    selected_force_method = st.selectbox(
                        "Apply input method to active rows",
                        INPUT_MODE_EDITOR_OPTIONS,
                        key=PRESTRESS_FORCE_INPUT_METHOD_STATE_KEY,
                        help=(
                            "Use this control to assign the same force input method to every active prestress row. "
                            "Individual row Input Mode values remain editable after applying."
                        ),
                    )
                with apply_col:
                    st.write("")
                    st.write("")
                    if st.button("Apply to active rows", use_container_width=True, type="primary", key="prestress_apply_force_input_method"):
                        applied_table = _apply_force_input_method_to_active_rows(
                            pd.DataFrame(st.session_state["prestress_table"]),
                            selected_force_method,
                        )
                        st.session_state["prestress_table"] = normalize_prestress_table_for_effective_input_sync(applied_table, prestress_db)
                        st.session_state["prestress_editor_revision"] += 1
                        st.rerun()
                st.caption(
                    "This control changes active row Input Mode only. Pe_eff/fpe are then synchronized from the selected mode; "
                    "manual row edits remain available."
                )
                show_full_engineering_columns = st.checkbox(
                    "Show full engineering columns",
                    value=False,
                    help="Use only when editing catalog/material reference fields such as fpy, fpu, Ep, duct reference, or strand metadata.",
                    key="prestress_show_full_engineering_columns",
                )
                editor_table = _prestress_table_for_editor(st.session_state["prestress_table"])
                editor_column_order = None if show_full_engineering_columns else _compact_column_order_for_table(editor_table)
                editor_key = f"prestress_data_editor_{st.session_state['prestress_editor_revision']}"
                edited_df = st.data_editor(
                    editor_table,
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    column_order=editor_column_order,
                    column_config={
                        "Active": st.column_config.CheckboxColumn("Active"),
                        "Label": st.column_config.TextColumn("Label"),
                        "Steel Type": st.column_config.SelectboxColumn("Steel Type", options=STEEL_TYPE_OPTIONS),
                        "Product": st.column_config.SelectboxColumn(
                            "Product",
                            options=product_options,
                            help=(
                                "Select a prestress product. Standard tendons are listed as Tendon 6-1 to Tendon 6-55; "
                                "single strands and PT/PS bars follow. Legacy labels such as 6-12 are still accepted."
                            ),
                        ),
                        "x_mm": st.column_config.NumberColumn("x_mm"),
                        "y_mm": st.column_config.NumberColumn("y_mm"),
                        "Area_mm2": st.column_config.NumberColumn("Area_mm2"),
                        "Diameter_mm": st.column_config.NumberColumn("Diameter_mm"),
                        "Eq Steel Dia_mm": st.column_config.NumberColumn("Eq Steel Dia_mm", disabled=True),
                        "fpy_MPa": st.column_config.NumberColumn("fpy_MPa"),
                        "fpu_MPa": st.column_config.NumberColumn("fpu_MPa"),
                        "Ep_MPa": st.column_config.NumberColumn("Ep_MPa"),
                        "Input Mode": st.column_config.SelectboxColumn(
                            "Input Mode",
                            options=INPUT_MODE_EDITOR_OPTIONS,
                            help="Choose how effective prestress is entered. Jacking + Total Loss % computes fpe and Pe_eff from fpj_ratio, fpu, area, and total loss.",
                        ),
                        "Pe_eff_kN": st.column_config.NumberColumn(
                            "Pe_eff_kN",
                            help="Effective prestress force after losses. Enter directly in Pe_eff mode; otherwise this is computed from fpe or jacking/loss inputs.",
                        ),
                        "fpe_MPa": st.column_config.NumberColumn(
                            "fpe_MPa",
                            help="Effective prestress stress after losses. Enter directly in fpe mode; otherwise this is computed from Pe_eff or jacking/loss inputs.",
                        ),
                        "fpj_ratio": st.column_config.NumberColumn(
                            "fpj_ratio",
                            min_value=0.0,
                            step=0.01,
                            format="%.3f",
                            help="Jacking stress ratio fpj/fpu. Default 0.75. Used only by Jacking + Total Loss % mode.",
                        ),
                        "loss_percent": st.column_config.NumberColumn(
                            "loss_percent",
                            min_value=0.0,
                            max_value=100.0,
                            step=1.0,
                            format="%.1f",
                            help="Total prestress loss percentage from jacking stress to effective stress. Used only by Jacking + Total Loss % mode.",
                        ),
                        "Bonded": st.column_config.CheckboxColumn("Bonded"),
                        "Count": st.column_config.NumberColumn("Count", min_value=1, step=1),
                        "Strand Count": st.column_config.NumberColumn("Strand Count", disabled=True),
                        "Breaking Load_kN": st.column_config.NumberColumn("Breaking Load_kN", disabled=True),
                        "Duct Type": st.column_config.TextColumn("Duct Type", disabled=True),
                        "Duct ID_mm": st.column_config.NumberColumn("Duct ID_mm", disabled=True),
                        "Note": st.column_config.TextColumn(
                            "Remarks",
                            help="Optional engineering remark for this prestress row. It is not used in calculation.",
                        ),
                    },
                    key=editor_key,
                )
                edited_df = normalize_prestress_table_for_effective_input_sync(edited_df, prestress_db)
                if not _dataframes_equal(edited_df, pd.DataFrame(st.session_state["prestress_table"])):
                    st.session_state["prestress_table"] = edited_df
                    st.session_state["prestress_editor_revision"] += 1
                    st.rerun()
                st.session_state["prestress_table"] = edited_df

                if not show_full_engineering_columns:
                    with st.expander("Product / material reference details", expanded=False):
                        st.markdown(
                            '<div class="cpmm-prestress-quiet-note">'
                            "Read-only reference view for material/product fields hidden from the compact editor. "
                            "Turn on full engineering columns above only when you intentionally need to edit reference/material fields."
                            "</div>",
                            unsafe_allow_html=True,
                        )
                        st.dataframe(_prestress_reference_detail_dataframe(edited_df), use_container_width=True, hide_index=True)

    geometry = st.session_state.get("section_geometry")
    if girder_prestress_layout_active:
        result = _empty_prestress_parse_result([
            "Section-level tendon/prestress table is hidden and ignored for this precast girder workflow."
        ])
        geometry_errors = []
        valid_for_analysis = True
    else:
        result = prestress_elements_from_dataframe(edited_df, prestress_db)
        geometry_errors = validate_prestress_against_geometry(result.elements, geometry)
        valid_for_analysis = prestress_valid_for_analysis(result, geometry_errors)
    st.session_state["prestress_elements"] = result.elements
    st.session_state["prestress_valid_for_analysis"] = valid_for_analysis

    girder_prestress_layout_active = _is_girder_prestress_layout_workflow_active()
    with main_col:
        if girder_prestress_layout_active:
            _render_girder_strand_layout_and_debonding_ui(geometry)
        elif _session_member_type() in {"beam_girder", "building_beam_girder"}:
            st.info(
                "Dedicated strand layout and debonding tools are hidden for the current section preset. "
                "Use a supported prestressed girder preset such as Precast I-Girder, or use the generic prestress table if this member intentionally has prestressing."
            )

    active_rebar_count = len(st.session_state.get("rebars", []) or []) if ordinary_rebar_enabled(st.session_state, default=True) else 0

    with summary_slot.container():
        if girder_prestress_layout_active:
            st.markdown(_metric_strip_html(_build_girder_prestress_summary_metrics()), unsafe_allow_html=True)
        else:
            _render_prestress_summary_strip(result, geometry_errors, valid_for_analysis, active_rebar_count)

    with side_col:
        if girder_prestress_layout_active:
            st.markdown("#### Girder Strand Preview")
            st.caption("Use the Cross-section layout tab in the strand/debonding workflow. Legacy PS1/PS2 section-level previews are hidden for precast girders.")
        else:
            _render_prestress_section_preview_panel(geometry, result)
        _render_validation(result, geometry_errors, geometry is not None, valid_for_analysis, active_rebar_count)
        _render_engineering_notes()

    if not girder_prestress_layout_active:
        invalid_rows_df = _invalid_prestress_rows_dataframe(edited_df, result.errors)
        if not invalid_rows_df.empty:
            st.markdown("#### Rows Excluded from Analysis")
            st.warning(
                "Rows listed below have validation errors and are not included in Valid elements, Total Aps, Total Pe_eff, Prestress Summary, or PMM/SLS analysis."
            )
            st.dataframe(invalid_rows_df, use_container_width=True, hide_index=True)

        st.markdown("#### Prestress Summary")
        st.caption("Only valid active prestress rows used by analysis are shown here. Rows with validation errors are excluded until corrected.")
        st.dataframe(prestress_summary_dataframe(result.elements), use_container_width=True, hide_index=True)

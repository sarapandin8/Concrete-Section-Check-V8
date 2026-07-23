"""Metadata-driven Streamlit section builder."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import isfinite
from typing import Any

import streamlit as st

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.analysis_modes import (
    analysis_mode_label,
    is_bridge_beam_girder_workflow,
    is_building_beam_girder_workflow,
    is_portal_frame_crossbeam_workflow,
)
from concrete_pmm_pro.core.concrete_materials import (
    DEFAULT_DECK_TOPPING_MATERIAL,
    c45_precast_material,
    concrete_materials_by_name,
    ensure_concrete_material_library,
)
from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
    REINFORCEMENT_FLAGS_PRESET_KEY,
    default_section_reinforcement_flags,
    ordinary_rebar_enabled,
    prestressing_steel_enabled,
)
from concrete_pmm_pro.geometry import default_registry
from concrete_pmm_pro.geometry.effective_width import (
    EffectiveWidthInput,
    EffectiveWidthResult,
    calculate_aashto_effective_slab_width,
)
from concrete_pmm_pro.geometry.composite import (
    calculate_composite_transformed_section_from_geometry,
    composite_deck_input_from_parameters,
    composite_deck_is_active,
)
from concrete_pmm_pro.geometry.presets import load_section_categories, load_section_presets
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.geometry.validation import ValidationResult, validate_section_geometry
from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BEAM_GIRDER_SYSTEM_SETTINGS_KEY,
    DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3,
    DEFAULT_GIRDER_SPACING_M,
    DEFAULT_LIFTING_IMPACT_FACTOR,
    DEFAULT_LIFTING_POINT_RATIO,
    DEFAULT_NUMBER_OF_GIRDERS,
    DEFAULT_SPAN_LENGTH_M,
    system_settings_from_mapping,
)
from concrete_pmm_pro.visualization import create_section_preview
from concrete_pmm_pro.ui.crossbeam_section_library import (
    prepare_crossbeam_section_library_for_builder,
    render_crossbeam_section_library_panel,
    sync_crossbeam_section_library_after_builder,
)

RAILWAY_U_GIRDER_PRESET_KEY = "railway_u_girder"
RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY = "railway_u_girder_stage_settings"
SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY = "section_builder_ordinary_rebar_enabled"
SECTION_BUILDER_PRESTRESS_SYNC_KEY = "section_builder_prestressing_steel_enabled"
SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY = "section_builder_steel_systems_preset_key"
SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY = "section_builder_steel_systems_user_overridden"
SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY = "section_builder_steel_systems_override_preset_key"
RAILWAY_U_GIRDER_DEFAULT_WEB_FC_MPA = 45.0
RAILWAY_U_GIRDER_DEFAULT_WEB_FCI_MPA = 36.0
RAILWAY_U_GIRDER_DEFAULT_SLAB_FC_MPA = 35.0
RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M = 10.0
RAILWAY_U_GIRDER_DEFAULT_FORMWORK_LOAD_KN_M2 = 2.5
RAILWAY_U_GIRDER_DEFAULT_LIFTING_RATIO = 0.20
RAILWAY_U_GIRDER_DEFAULT_LIFTING_IMPACT = 1.10
RAILWAY_U_GIRDER_DEFAULT_WET_SLAB_DISTRIBUTION = 0.50


@dataclass(frozen=True)
class SectionMetric:
    title: str
    value: str
    detail: str = ""
    status: str = "neutral"
    strong: bool = False


_SECTION_BUILDER_CSS = """
<style>


.cpmm-section-page-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid rgba(22, 131, 58, 0.18);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(240, 253, 244, 0.94), #ffffff 62%);
  padding: 0.95rem 1.1rem;
  margin: 0.35rem 0 0.95rem 0;
  box-shadow: 0 9px 28px rgba(16, 24, 40, 0.07);
}
.cpmm-section-page-title {
  color: #092454;
  font-size: 1.20rem;
  font-weight: 900;
  line-height: 1.15;
  margin-bottom: 0.2rem;
}
.cpmm-section-page-subtitle {
  color: #475467;
  font-size: 0.86rem;
  line-height: 1.35;
}
.cpmm-section-page-mode {
  flex: 0 0 auto;
  align-self: center;
  border: 1px solid rgba(22, 131, 58, 0.22);
  border-radius: 999px;
  background: #ffffff;
  color: #166534;
  padding: 0.34rem 0.72rem;
  font-size: 0.72rem;
  font-weight: 850;
  box-shadow: 0 4px 12px rgba(22, 131, 58, 0.08);
}
.cpmm-commercial-section-step-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0.25rem 0 0.16rem 0;
}
.cpmm-commercial-section-step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #16833a, #22a447);
  font-weight: 950;
  box-shadow: 0 5px 14px rgba(22, 131, 58, 0.22);
}
.cpmm-commercial-section-step-heading {
  color: #101828;
  font-size: 1.05rem;
  font-weight: 900;
}
.cpmm-commercial-section-step-note {
  color: #475467;
  font-size: 0.84rem;
  line-height: 1.35;
  margin: 0 0 0.72rem 2.3rem;
}

/* UI.COMMERCIAL1/2: commercial section preset master-control styling. */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) {
  border: 2px solid #22a447 !important;
  border-radius: 20px !important;
  background:
    radial-gradient(circle at 42px 44px, rgba(34, 164, 71, 0.20), transparent 62px),
    linear-gradient(135deg, #effff4 0%, #ffffff 54%, #e9f9ef 100%) !important;
  box-shadow: 0 16px 36px rgba(22, 131, 58, 0.17), 0 0 0 5px rgba(34, 164, 71, 0.07) !important;
  padding: 0.84rem 0.92rem !important;
  margin-top: 0.35rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] {
  border: 1px solid rgba(22, 131, 58, 0.34);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.88);
  padding: 0.40rem 0.68rem 0.58rem 0.68rem;
  box-shadow: 0 8px 22px rgba(22, 131, 58, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] label {
  color: #166534 !important;
  font-size: 0.76rem !important;
  font-weight: 950 !important;
  letter-spacing: 0.055em;
  text-transform: uppercase;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  border: 2px solid rgba(22, 131, 58, 0.48) !important;
  border-radius: 13px !important;
  min-height: 3.05rem !important;
  background: linear-gradient(135deg, #f0fff4 0%, #dcfce7 100%) !important;
  box-shadow: 0 5px 15px rgba(22, 131, 58, 0.10) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
  border-color: rgba(22, 131, 58, 0.62) !important;
  background: linear-gradient(135deg, #ecfdf3 0%, #d1fadf 100%) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
  border-color: rgba(22, 131, 58, 0.78) !important;
  background: linear-gradient(135deg, #ecfdf3 0%, #d1fadf 100%) !important;
  box-shadow: 0 0 0 3px rgba(34, 164, 71, 0.14), 0 8px 18px rgba(22, 131, 58, 0.12) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div {
  color: #15803d !important;
  font-weight: 800 !important;
  font-size: 1.08rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-section) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div span {
  color: #15803d !important;
  font-weight: 800 !important;
  font-size: 1.08rem !important;
}
.cpmm-commercial-control-section {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.15rem;
  margin: 0.06rem 0 0.82rem 0;
}
.cpmm-commercial-section-icon {
  width: 72px;
  height: 72px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.72rem;
  font-weight: 950;
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
  color: #16833a;
  box-shadow: 0 7px 18px rgba(22, 131, 58, 0.16);
}
.cpmm-commercial-section-copy { min-width: 0; }
.cpmm-commercial-section-kicker {
  color: #16833a;
  font-size: 0.80rem;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.14rem;
}
.cpmm-commercial-section-value {
  color: #14532d;
  font-size: 1.26rem;
  font-weight: 950;
  line-height: 1.18;
  overflow-wrap: anywhere;
}
.cpmm-commercial-section-detail {
  color: #344054;
  font-size: 0.90rem;
  line-height: 1.36;
  margin-top: 0.30rem;
}
.cpmm-commercial-section-badge {
  align-self: start;
  border-radius: 999px;
  padding: 0.22rem 0.68rem;
  background: #16833a;
  color: #ffffff;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.06em;
  box-shadow: 0 4px 12px rgba(22, 131, 58, 0.22);
}
@media (max-width: 900px) {
  .cpmm-commercial-control-section { grid-template-columns: auto minmax(0, 1fr); }
  .cpmm-commercial-section-badge { grid-column: 2; justify-self: start; }
}

.cpmm-section-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.12rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0;
  margin-top: 0.45rem;
}
.cpmm-section-badge.ready { color: #1f5f2a; background: #e7f5e8; }
.cpmm-section-badge.warning { color: #7a4b00; background: #fff4d6; }
.cpmm-section-badge.danger { color: #9f1f17; background: #fde8e7; }
.cpmm-section-badge.info { color: #1849a9; background: #e8f1ff; }
.cpmm-section-badge.neutral { color: #475467; background: #eef1f5; }
.cpmm-section-kv-panel {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.64rem 0.84rem;
}
.cpmm-section-kv-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.32rem 0;
}
.cpmm-section-kv-row:last-child { border-bottom: 0; }
.cpmm-section-kv-label {
  color: #667085;
  font-size: 0.82rem;
  font-weight: 600;
}
.cpmm-section-kv-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 650;
  text-align: right;
  overflow-wrap: anywhere;
}
.cpmm-section-note {
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.35;
  margin-top: -0.2rem;
}
.cpmm-section-status-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.34rem 0;
}
.cpmm-section-status-row:last-child { border-bottom: 0; }
.cpmm-section-status-title {
  color: #667085;
  font-size: 0.82rem;
  font-weight: 650;
}
.cpmm-section-status-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 700;
  text-align: right;
}
.cpmm-section-message-list {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fbfcfe;
  padding: 0.62rem 0.78rem;
  margin-top: 0.55rem;
}
.cpmm-section-message-item {
  color: #475467;
  font-size: 0.82rem;
  line-height: 1.35;
  padding: 0.18rem 0;
}
.cpmm-section-property-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 0.42rem;
  margin-bottom: 0.36rem;
}
.cpmm-section-property-chip {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.46rem 0.56rem;
  min-height: 60px;
}
.cpmm-section-property-label {
  color: #667085;
  font-size: 0.74rem;
  font-weight: 650;
  letter-spacing: 0;
  margin-bottom: 0.18rem;
}
.cpmm-section-property-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 720;
  line-height: 1.18;
  overflow-wrap: anywhere;
}
.cpmm-section-property-detail {
  color: #667085;
  font-size: 0.71rem;
  line-height: 1.18;
  margin-top: 0.16rem;
}

/* UI.COMMERCIAL4.3.2: compact engineering summary cards.
   These replace oversized metric billboards for assembly/stage summaries so
   editable inputs remain visually primary. */
.cpmm-assembly-summary-card {
  border: 1px solid rgba(29, 111, 231, 0.30);
  border-radius: 12px;
  background: linear-gradient(135deg, #175cd3 0%, #1d6fe7 100%);
  color: #ffffff;
  padding: 0.58rem 0.68rem;
  min-height: 74px;
  box-shadow: 0 6px 14px rgba(29, 111, 231, 0.14);
}
.cpmm-assembly-summary-card.green {
  border-color: rgba(22, 131, 58, 0.28);
  background: linear-gradient(135deg, #16833a 0%, #22a447 100%);
  box-shadow: 0 6px 14px rgba(22, 131, 58, 0.13);
}
.cpmm-assembly-summary-label {
  color: rgba(255, 255, 255, 0.84);
  font-size: 0.64rem;
  font-weight: 950;
  letter-spacing: 0.055em;
  text-transform: uppercase;
  line-height: 1.15;
  margin-bottom: 0.20rem;
}
.cpmm-assembly-summary-value {
  color: #ffffff;
  font-size: 1.18rem;
  font-weight: 950;
  line-height: 1.14;
  overflow-wrap: anywhere;
}
.cpmm-assembly-summary-detail {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  margin-top: 0.34rem;
  padding: 0.13rem 0.44rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  color: #eef6ff;
  font-size: 0.66rem;
  font-weight: 850;
}

.cpmm-commercial-section-hero {
  border: 1px solid #d5dde8;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffffff 0%, #f6f9fc 100%);
  margin: 0.24rem 0 0.56rem 0;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
}
.cpmm-commercial-section-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 0.56rem 0.78rem;
}
.cpmm-commercial-section-title {
  color: #1f5f99;
  font-size: 1.05rem;
  font-weight: 760;
  letter-spacing: 0;
}
.cpmm-commercial-section-subtitle {
  color: #667085;
  font-size: 0.78rem;
  margin-top: 0.1rem;
}
.cpmm-commercial-section-mode {
  color: #475467;
  background: #eef5fb;
  border: 1px solid #d4e6f5;
  border-radius: 999px;
  padding: 0.18rem 0.62rem;
  font-size: 0.74rem;
  font-weight: 700;
  white-space: nowrap;
}
.cpmm-commercial-panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.24rem;
}
.cpmm-commercial-panel-title-main {
  color: #1f2937;
  font-size: 1.02rem;
  font-weight: 760;
}
.cpmm-commercial-panel-kicker {
  color: #667085;
  font-size: 0.72rem;
  font-weight: 720;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.cpmm-commercial-mini-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.cpmm-commercial-pill {
  border: 1px solid #d8e4ef;
  border-radius: 999px;
  background: #f6f9fc;
  color: #475467;
  font-size: 0.72rem;
  font-weight: 680;
  padding: 0.16rem 0.52rem;
}
.cpmm-commercial-preview-note {
  border-left: 3px solid #1f5f99;
  background: #f4f8fb;
  color: #667085;
  font-size: 0.78rem;
  padding: 0.36rem 0.52rem;
  margin: 0.22rem 0 0.42rem 0;
  border-radius: 6px;
}
.cpmm-section-preview-status-compact {
  margin-top: 0.34rem;
}
.cpmm-section-builder-compact-note {
  color: #667085;
  font-size: 0.74rem;
  line-height: 1.22;
  margin: 0.1rem 0 0.35rem 0;
}

.cpmm-context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.86rem;
  margin: 0.58rem 0 0.88rem 0;
}
.cpmm-context-card {
  position: relative;
  border: 2px solid #7ab7ff;
  border-left: 9px solid #175cd3;
  border-radius: 16px;
  background:
    radial-gradient(circle at 18px 18px, rgba(23, 92, 211, 0.12), transparent 28px),
    linear-gradient(135deg, #eff7ff 0%, #ffffff 54%, #eaf3ff 100%);
  padding: 1.0rem 1.1rem;
  box-shadow: 0 8px 24px rgba(23, 92, 211, 0.13), 0 0 0 3px rgba(23, 92, 211, 0.05);
  min-height: 132px;
}
.cpmm-context-card.section {
  border-color: #8ee2a6;
  border-left-color: #16833a;
  background:
    radial-gradient(circle at 18px 18px, rgba(22, 131, 58, 0.14), transparent 28px),
    linear-gradient(135deg, #effff4 0%, #ffffff 54%, #e9faee 100%);
  box-shadow: 0 8px 24px rgba(22, 131, 58, 0.13), 0 0 0 3px rgba(22, 131, 58, 0.06);
}
.cpmm-context-kicker {
  color: #1849a9;
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0.075em;
  text-transform: uppercase;
  margin-bottom: 0.34rem;
}
.cpmm-context-card.section .cpmm-context-kicker { color: #166534; }
.cpmm-context-value {
  color: #0b2f6b;
  font-size: 1.22rem;
  font-weight: 850;
  line-height: 1.18;
  overflow-wrap: anywhere;
}
.cpmm-context-card.section .cpmm-context-value { color: #14532d; }
.cpmm-context-detail {
  color: #667085;
  font-size: 0.78rem;
  line-height: 1.28;
  margin-top: 0.28rem;
}
.cpmm-context-badges {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}
.cpmm-context-required {
  display: inline-block;
  border-radius: 999px;
  padding: 0.18rem 0.62rem;
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.055em;
  background: #1849a9;
  color: #ffffff;
  box-shadow: 0 3px 10px rgba(24, 73, 169, 0.18);
}
.cpmm-context-card.section .cpmm-context-required { background: #16833a; box-shadow: 0 3px 10px rgba(22, 131, 58, 0.18); }
.cpmm-section-master-control-banner {
  border: 1px solid #86efac;
  border-left: 7px solid #16833a;
  border-radius: 12px;
  background: linear-gradient(135deg, #effff4 0%, #ffffff 58%, #e9faee 100%);
  padding: 0.72rem 0.86rem;
  margin: 0.30rem 0 0.54rem 0;
  box-shadow: 0 5px 16px rgba(22, 131, 58, 0.12), 0 0 0 2px rgba(22, 131, 58, 0.05);
}
.cpmm-section-master-control-title {
  color: #166534;
  font-size: 0.76rem;
  font-weight: 900;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 0.18rem;
}
.cpmm-section-master-control-text {
  color: #344054;
  font-size: 0.82rem;
  line-height: 1.32;
}
.cpmm-section-master-control-chip {
  display: inline-block;
  border-radius: 999px;
  padding: 0.12rem 0.52rem;
  margin-left: 0.42rem;
  background: #16833a;
  color: #ffffff;
  font-size: 0.66rem;
  font-weight: 900;
  letter-spacing: 0.055em;
}
.cpmm-context-chip {
  display: inline-block;
  border-radius: 999px;
  padding: 0.14rem 0.52rem;
  font-size: 0.68rem;
  font-weight: 760;
  background: rgba(255, 255, 255, 0.75);
  color: #475467;
  border: 1px solid rgba(102, 112, 133, 0.18);
}
@media (max-width: 900px) {
  .cpmm-context-grid { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 1200px) {
  .cpmm-section-property-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .cpmm-section-property-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
"""


SECTION_PARAMETERS_PRESET_KEY = "section_parameters_preset_key"


def _section_parameters_for_active_preset(preset_key: str) -> dict[str, Any]:
    """Return durable section parameters only when they belong to ``preset_key``.

    Streamlit deletes widget-owned keys when a page is not rendered.  The
    canonical section model must therefore restore widget defaults from the
    durable ``section_parameters`` payload rather than from preset defaults when
    the user returns to Section Builder after visiting Setup/Loads/Analysis.
    """

    params = st.session_state.get("section_parameters")
    if not isinstance(params, dict):
        return {}
    owner = st.session_state.get(SECTION_PARAMETERS_PRESET_KEY)
    if owner is None and st.session_state.get("section_preset_key") == preset_key:
        # Compatibility for project/session state saved before STATE.SECTION1.
        return params
    return params if owner == preset_key else {}


def _coerce_number_within_bounds(value: Any, *, min_value: float, max_value: float) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric):
        return None
    if numeric < min_value or numeric > max_value:
        return None
    return numeric


def _durable_number_default(
    name: str,
    preset_key: str,
    fallback: float,
    *,
    min_value: float,
    max_value: float,
) -> float:
    params = _section_parameters_for_active_preset(preset_key)
    durable = _coerce_number_within_bounds(params.get(name), min_value=min_value, max_value=max_value)
    if durable is not None:
        return durable
    fallback_number = _coerce_number_within_bounds(fallback, min_value=min_value, max_value=max_value)
    if fallback_number is not None:
        return fallback_number
    return min_value


def _durable_choice_default(name: str, preset_key: str, fallback: str, options: list[str]) -> str:
    params = _section_parameters_for_active_preset(preset_key)
    durable = str(params.get(name, ""))
    if durable in options:
        return durable
    return fallback if fallback in options else options[0]


def _durable_bool_default(name: str, preset_key: str, fallback: bool) -> bool:
    params = _section_parameters_for_active_preset(preset_key)
    durable = params.get(name)
    if isinstance(durable, bool):
        return durable
    return bool(fallback)


def _ensure_section_parameter_owner_from_session() -> None:
    """Backfill the durable parameter owner for older sessions/project files."""

    if SECTION_PARAMETERS_PRESET_KEY in st.session_state:
        return
    params = st.session_state.get("section_parameters")
    preset_key = st.session_state.get("section_preset_key")
    if isinstance(params, dict) and params and preset_key:
        st.session_state[SECTION_PARAMETERS_PRESET_KEY] = str(preset_key)


def _number_input(parameter: dict[str, Any], key_prefix: str) -> float:
    name = str(parameter["name"])
    min_value = float(parameter.get("min", 0.0))
    max_value = float(parameter.get("max", 1.0e9))
    widget_key = f"{key_prefix}_{name}"
    default_value = _durable_number_default(
        name,
        key_prefix,
        float(parameter.get("default", parameter.get("min", 0.0))),
        min_value=min_value,
        max_value=max_value,
    )
    # If Streamlit removed the widget-owned key while another workspace was
    # active, repopulate it from the durable section model before rendering.
    st.session_state.setdefault(widget_key, default_value)
    return float(
        st.number_input(
            parameter.get("label", parameter["name"]),
            min_value=min_value,
            max_value=max_value,
            value=float(st.session_state.get(widget_key, default_value)),
            step=float(parameter.get("step", 1.0)),
            help=parameter.get("description"),
            key=widget_key,
        )
    )


def _legacy_rectangular_chamfer_value() -> float | None:
    params = st.session_state.get("section_parameters", {})
    legacy_value = None
    if isinstance(params, dict):
        legacy_value = params.get("chamfer_mm")
    if legacy_value is None:
        legacy_value = st.session_state.get("rectangular_chamfered_chamfer_mm")
    try:
        return None if legacy_value is None else float(legacy_value)
    except (TypeError, ValueError):
        return None


def _sync_rectangular_chamfered_legacy_widget_defaults(preset: dict[str, Any]) -> None:
    if str(preset.get("key", "")) != "rectangular_chamfered":
        return
    legacy = _legacy_rectangular_chamfer_value()
    if legacy is None:
        return
    for name in ("chamfer_x_mm", "chamfer_y_mm"):
        key = f"rectangular_chamfered_{name}"
        if key not in st.session_state:
            st.session_state[key] = legacy


def _safe_status(status: str) -> str:
    return status if status in {"ready", "warning", "danger", "info", "neutral"} else "neutral"


def _validation_status(result: ValidationResult) -> str:
    if result.errors:
        return "danger"
    if result.warnings:
        return "warning"
    return "ready"


def _kv_panel_html(rows: list[tuple[str, str]]) -> str:
    row_html = []
    for label, value in rows:
        row_html.append(
            '<div class="cpmm-section-kv-row">'
            f'<div class="cpmm-section-kv-label">{escape(label)}</div>'
            f'<div class="cpmm-section-kv-value">{escape(value)}</div>'
            "</div>"
        )
    return '<div class="cpmm-section-kv-panel">' + "".join(row_html) + "</div>"


def _status_panel_html(rows: list[SectionMetric]) -> str:
    row_html = []
    for row in rows:
        status = _safe_status(row.status)
        if row.strong:
            value_html = f'<span class="cpmm-section-badge {status}">{escape(row.value)}</span>'
        else:
            value_html = escape(row.value)
        row_html.append(
            '<div class="cpmm-section-status-row">'
            f'<div class="cpmm-section-status-title">{escape(row.title)}</div>'
            f'<div class="cpmm-section-status-value">{value_html}</div>'
            "</div>"
        )
    return '<div class="cpmm-section-kv-panel">' + "".join(row_html) + "</div>"


def _message_list_html(messages: list[str]) -> str:
    items = "".join(f'<div class="cpmm-section-message-item">{escape(message)}</div>' for message in messages)
    return f'<div class="cpmm-section-message-list">{items}</div>'


def _property_strip_html(properties: list[SectionMetric]) -> str:
    chips: list[str] = []
    for property_item in properties:
        status = _safe_status(property_item.status)
        value_html = (
            f'<span class="cpmm-section-badge {status}">{escape(property_item.value)}</span>'
            if property_item.strong
            else escape(property_item.value)
        )
        detail_html = (
            f'<div class="cpmm-section-property-detail">{escape(property_item.detail)}</div>'
            if property_item.detail
            else ""
        )
        chips.append(
            '<div class="cpmm-section-property-chip">'
            f'<div class="cpmm-section-property-label">{escape(property_item.title)}</div>'
            f'<div class="cpmm-section-property-value">{value_html}</div>'
            f"{detail_html}"
            "</div>"
        )
    return '<div class="cpmm-section-property-grid">' + "".join(chips) + "</div>"




def _compact_summary_card_html(label: str, value: str, detail: str = "", *, accent: str = "blue") -> str:
    """Return a compact visual-only summary card for assembly/stage metadata."""
    accent_class = "green" if str(accent).lower() == "green" else ""
    detail_html = f'<div class="cpmm-assembly-summary-detail">{escape(detail)}</div>' if detail else ""
    return (
        f'<div class="cpmm-assembly-summary-card {accent_class}">'
        f'<div class="cpmm-assembly-summary-label">{escape(label)}</div>'
        f'<div class="cpmm-assembly-summary-value">{escape(value)}</div>'
        f'{detail_html}'
        '</div>'
    )

def _format_float(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}"


def _format_optional_mm(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f} mm"


def _signed_mm(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:+,.{decimals}f} mm"


def _format_parameter_value(value: Any) -> str:
    if isinstance(value, float):
        return _format_float(value, 2).rstrip("0").rstrip(".")
    return str(value)


def _format_ec(value: float) -> str:
    return f"{value:,.0f} MPa"


def _ensure_concrete_material_session() -> list[ConcreteMaterial]:
    library_state = ensure_concrete_material_library(
        concrete_material=st.session_state.get("concrete_material", c45_precast_material()),
        concrete_materials=st.session_state.get("concrete_materials", []),
        active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
        deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
        preserve_existing_primary=not bool(st.session_state.get("concrete_materials", [])),
    )
    st.session_state["concrete_materials"] = library_state.materials
    st.session_state["active_concrete_material_name"] = library_state.active_concrete_material_name
    st.session_state["primary_concrete_material_name"] = library_state.active_concrete_material_name
    st.session_state["deck_topping_material_name"] = library_state.deck_topping_material_name
    st.session_state["concrete_material"] = library_state.active_material
    return library_state.materials


def _material_select_index(names: list[str], preferred_name: str | None, fallback_index: int = 0) -> int:
    if preferred_name in names:
        return names.index(preferred_name)
    return min(max(fallback_index, 0), max(len(names) - 1, 0))


def _hidden_material_parameter_names(preset: dict[str, Any]) -> set[str]:
    if _is_parametric_plank_girder(preset):
        return {"Ebeam_MPa", "Edeck_MPa"}
    return set()


def _is_building_shared_precast_girder_preset(preset: dict[str, Any]) -> bool:
    """Return True for shared prestressed girder geometry in Building workflow."""

    return str(preset.get("key", "")).strip() in _BUILDING_SHARED_PRECAST_GIRDER_PRESET_KEYS


def _composite_metadata_enabled_for_workflow(
    preset: dict[str, Any], settings: AnalysisModeSettings | None = None
) -> bool:
    """Return True when composite deck/topping metadata controls should show.

    Bridge Beam/Girder exposes the full bridge composite metadata workflow,
    including the AASHTO effective-width helper.  Building Beam/Girder may reuse
    shared precast I-Girder geometry under ACI 318 and still needs generic
    deck/topping metadata and transformed-property display.  Bridge-only load
    components, staged SLS, and AASHTO Be automation remain hidden outside the
    Bridge workflow.
    """

    active_settings = settings or _analysis_mode_from_session_state()
    if not _is_composite_capable_preset(preset):
        return False
    if is_bridge_beam_girder_workflow(active_settings):
        return True
    return is_building_beam_girder_workflow(active_settings) and _is_building_shared_precast_girder_preset(preset)


def _aashto_effective_width_helper_enabled(
    preset: dict[str, Any], settings: AnalysisModeSettings | None = None
) -> bool:
    """Return True only for Bridge workflow AASHTO Be helper controls."""

    active_settings = settings or _analysis_mode_from_session_state()
    return _is_composite_capable_preset(preset) and is_bridge_beam_girder_workflow(active_settings)


def _is_railway_u_girder_preset(preset: dict[str, Any]) -> bool:
    return str(preset.get("key", "")).strip() == RAILWAY_U_GIRDER_PRESET_KEY


def _material_name_for_fc(material_map: dict[str, ConcreteMaterial], target_fc: float, fallback_name: str | None = None) -> str:
    if fallback_name in material_map:
        return str(fallback_name)
    for material in material_map.values():
        try:
            if abs(float(material.fc_MPa) - float(target_fc)) <= 1e-9:
                return material.name
        except (TypeError, ValueError):
            continue
    return next(iter(material_map))


def _sync_railway_u_girder_stage_material_settings(settings_update: dict[str, Any]) -> None:
    settings = dict(st.session_state.get(RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY, {}) or {})
    settings.update(settings_update)
    st.session_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = settings


def _sync_beam_girder_span_to_existing_sources(settings: dict[str, Any]) -> None:
    """Keep legacy span consumers synchronized with section-assembly settings."""

    try:
        span_length_m = float(settings.get("span_length_m", DEFAULT_SPAN_LENGTH_M) or DEFAULT_SPAN_LENGTH_M)
    except (TypeError, ValueError):
        span_length_m = DEFAULT_SPAN_LENGTH_M

    prestress_system = dict(st.session_state.get("girder_prestress_system_settings", {}) or {})
    prestress_system["span_length_m"] = span_length_m
    st.session_state["girder_prestress_system_settings"] = prestress_system

    section_params = dict(st.session_state.get("section_parameters", {}) or {})
    if section_params:
        section_params["girder_length_mm"] = span_length_m * 1000.0
        st.session_state["section_parameters"] = section_params
        preset_key = str(st.session_state.get("section_preset_key") or "").strip()
        if preset_key:
            st.session_state[f"{preset_key}_girder_length_mm"] = span_length_m * 1000.0


def _ensure_railway_u_girder_stage_settings_defaults() -> dict[str, Any]:
    """Initialize Railway U-Girder stage settings from section assembly.

    SECTION.ASSEMBLY2 keeps Railway U-Girder assembly controls rail-specific:
    span/lifting/construction-stage fields are shown, while generic repeated
    girder width and tributary-width fields are hidden for this preset.
    """

    existing = st.session_state.get(RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY)
    if not isinstance(existing, dict):
        existing = {}
    existing.setdefault("web_fc_MPa", RAILWAY_U_GIRDER_DEFAULT_WEB_FC_MPA)
    existing.setdefault("web_fci_MPa", RAILWAY_U_GIRDER_DEFAULT_WEB_FCI_MPA)
    existing.setdefault("slab_fc_MPa", RAILWAY_U_GIRDER_DEFAULT_SLAB_FC_MPA)
    existing.setdefault("concrete_unit_weight_kN_m3", DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3)
    existing.setdefault("support_condition", "Simply supported")
    existing.setdefault("construction_method", "Case B - wet slab carried by precast webs")
    existing.setdefault("wet_slab_distribution_each_web", RAILWAY_U_GIRDER_DEFAULT_WET_SLAB_DISTRIBUTION)
    existing.setdefault("formwork_construction_load_kN_m2", RAILWAY_U_GIRDER_DEFAULT_FORMWORK_LOAD_KN_M2)
    existing.setdefault("lifting_point_ratio", RAILWAY_U_GIRDER_DEFAULT_LIFTING_RATIO)
    existing.setdefault("lifting_impact_factor", RAILWAY_U_GIRDER_DEFAULT_LIFTING_IMPACT)
    st.session_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = dict(existing)
    return dict(existing)


def _railway_u_girder_default_span_from_sources(values: dict[str, Any], stage_settings: dict[str, Any]) -> float:
    """Return the Railway U-Girder span default, migrating the old generic 20 m default."""

    for candidate in (
        stage_settings.get("span_length_m"),
        values.get("span_length_m"),
        (st.session_state.get("girder_prestress_system_settings") or {}).get("span_length_m")
        if isinstance(st.session_state.get("girder_prestress_system_settings"), dict)
        else None,
    ):
        try:
            span = float(candidate)
        except (TypeError, ValueError):
            continue
        if span > 0.0:
            # The previous generic Beam/Girder panel defaulted Railway U-Girder
            # to 20 m.  For this rail preset that is a stale default, not a
            # meaningful user choice; use the agreed 10 m default instead.
            if abs(span - DEFAULT_SPAN_LENGTH_M) <= 1e-9:
                return RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M
            return span
    return RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M


def _normalize_railway_u_girder_assembly_settings(values: dict[str, Any], stage_settings: dict[str, Any]) -> dict[str, Any]:
    """Persist rail-specific assembly values under legacy metadata for downstream readers."""

    span = _railway_u_girder_default_span_from_sources(values, stage_settings)
    unit_weight = stage_settings.get("concrete_unit_weight_kN_m3", values.get("concrete_unit_weight_kN_m3"))
    try:
        unit_weight = float(unit_weight)
    except (TypeError, ValueError):
        unit_weight = DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3
    normalized = system_settings_from_mapping(
        {
            "span_length_m": span,
            # Hidden legacy fallbacks only. Railway U-Girder is not a repeated
            # I/box/plank system, so these are not user-facing controls.
            "girder_spacing_m": DEFAULT_GIRDER_SPACING_M,
            "number_of_girders": 2,
            "concrete_unit_weight_kN_m3": unit_weight,
            "tributary_width_m": None,
            "use_girder_spacing_as_tributary_width": False,
        }
    ).as_metadata()
    st.session_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = normalized
    _sync_beam_girder_span_to_existing_sources(normalized)
    return normalized


def _ensure_beam_girder_system_settings_defaults() -> dict[str, Any]:
    """Initialize section-specific Beam/Girder assembly settings.

    The settings remain serialized under the legacy metadata key so existing
    Loads/Prestress/SLS consumers keep working.  SECTION.ASSEMBLY1 moves the
    user-facing editor from Setup to Section Builder; it does not change solver
    equations or project schema.
    """

    existing = st.session_state.get(BEAM_GIRDER_SYSTEM_SETTINGS_KEY)
    if not isinstance(existing, dict):
        existing = {}
    if "span_length_m" not in existing:
        ps_settings = st.session_state.get("girder_prestress_system_settings") or {}
        span_from_ps = ps_settings.get("span_length_m") if isinstance(ps_settings, dict) else None
        section_params = st.session_state.get("section_parameters") or {}
        span_from_section = None
        if isinstance(section_params, dict):
            try:
                span_from_section = float(section_params.get("girder_length_mm", 0.0) or 0.0) / 1000.0
            except (TypeError, ValueError):
                span_from_section = None
        existing["span_length_m"] = span_from_ps or span_from_section or DEFAULT_SPAN_LENGTH_M
    existing.setdefault("girder_spacing_m", DEFAULT_GIRDER_SPACING_M)
    existing.setdefault("number_of_girders", DEFAULT_NUMBER_OF_GIRDERS)
    existing.setdefault("concrete_unit_weight_kN_m3", DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3)
    existing.setdefault("tributary_width_m", existing.get("girder_spacing_m", DEFAULT_GIRDER_SPACING_M))
    existing.setdefault("use_girder_spacing_as_tributary_width", False)
    existing.setdefault("lifting_point_ratio", DEFAULT_LIFTING_POINT_RATIO)
    existing.setdefault("lifting_impact_factor", DEFAULT_LIFTING_IMPACT_FACTOR)
    normalized = system_settings_from_mapping(existing).as_metadata()
    st.session_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = normalized
    _sync_beam_girder_span_to_existing_sources(normalized)
    return normalized


def _assembly_unit_label(preset: dict[str, Any], settings: AnalysisModeSettings) -> tuple[str, str, str]:
    """Return (count label, spacing label, summary noun) for the active assembly."""

    if is_building_beam_girder_workflow(settings):
        return "Number of precast beams", "Beam / girder spacing (m)", "Building member"
    if _is_parametric_plank_girder(preset):
        return "Number of planks", "Plank spacing / module width (m)", "Plank units"
    if _is_precast_box_beam(preset):
        return "Number of boxes", "Box spacing / module width (m)", "Box units"
    if _is_railway_u_girder_preset(preset):
        return "Precast webs", "Railway stage control (m)", "Railway U-Girder"
    return "Number of girders", "Girder spacing (m)", "Girder units"


def _render_railway_u_girder_assembly_panel(values: dict[str, Any]) -> None:
    """Render rail-specific Railway U-Girder assembly settings."""

    stage_settings = _ensure_railway_u_girder_stage_settings_defaults()
    rail_span_default = _railway_u_girder_default_span_from_sources(values, stage_settings)
    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Bridge Section Assembly", "Assembly", "Railway U-Girder", "Section-specific"),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Railway U-Girder is modeled as two precast prestressed webs connected by a cast-in-place slab. '
            'This rail-specific assembly panel intentionally hides generic girder spacing, overall system width, and tributary-width controls.</div>',
            unsafe_allow_html=True,
        )

        top_cols = st.columns(4)
        with top_cols[0]:
            span_length_m = st.number_input(
                "Span length L (m)",
                min_value=0.1,
                step=0.5,
                value=float(rail_span_default),
                format="%.3f",
                key="rail_ugirder_assembly_span_length_m_input",
                help="Default is 10.0 m for the Railway U-Girder family. This value also synchronizes prestress/debond station previews.",
            )
        with top_cols[1]:
            st.markdown(_compact_summary_card_html("Assembly units", "2 webs + CIP slab"), unsafe_allow_html=True)
        with top_cols[2]:
            stage_settings["concrete_unit_weight_kN_m3"] = st.number_input(
                "Concrete unit weight (kN/m³)",
                min_value=1.0,
                step=0.5,
                value=float(stage_settings.get("concrete_unit_weight_kN_m3", DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3)),
                format="%.2f",
                key="rail_ugirder_assembly_concrete_unit_weight_input",
                help="Used for web self-weight and wet slab load previews.",
            )
        with top_cols[3]:
            stage_settings["formwork_construction_load_kN_m2"] = st.number_input(
                "Formwork load (kN/m²)",
                min_value=0.0,
                step=0.5,
                value=float(stage_settings.get("formwork_construction_load_kN_m2", RAILWAY_U_GIRDER_DEFAULT_FORMWORK_LOAD_KN_M2)),
                format="%.2f",
                key="rail_ugirder_assembly_formwork_load_input",
                help="Editable construction load during wet slab casting. It is distributed 50/50 to the two precast webs in the stage model.",
            )

        lift_cols = st.columns(4)
        with lift_cols[0]:
            stage_settings["lifting_point_ratio"] = st.number_input(
                "Lifting a/L",
                min_value=0.05,
                max_value=0.45,
                value=float(stage_settings.get("lifting_point_ratio", RAILWAY_U_GIRDER_DEFAULT_LIFTING_RATIO)),
                step=0.01,
                format="%.3f",
                key="rail_ugirder_assembly_lifting_ratio_input",
                help="Default 0.20L from each end for two-point lifting of each precast web.",
            )
        with lift_cols[1]:
            st.markdown(_compact_summary_card_html("Lifting a", f"{float(stage_settings['lifting_point_ratio']) * float(span_length_m):.3f} m", "from each end"), unsafe_allow_html=True)
        with lift_cols[2]:
            stage_settings["lifting_impact_factor"] = st.number_input(
                "Lifting impact factor",
                min_value=1.0,
                value=float(stage_settings.get("lifting_impact_factor", RAILWAY_U_GIRDER_DEFAULT_LIFTING_IMPACT)),
                step=0.05,
                format="%.2f",
                key="rail_ugirder_assembly_lifting_impact_input",
                help="Applied to web self-weight in the lifting-stage preview.",
            )
        with lift_cols[3]:
            st.markdown(_compact_summary_card_html("Wet slab case", "Case B", "50/50 to left/right web"), unsafe_allow_html=True)

        stage_settings.update(
            {
                "span_length_m": float(span_length_m),
                "support_condition": "Simply supported",
                "construction_method": "Case B - wet slab carried by precast webs",
                "wet_slab_distribution_each_web": RAILWAY_U_GIRDER_DEFAULT_WET_SLAB_DISTRIBUTION,
            }
        )
        st.session_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY] = dict(stage_settings)
        normalized = _normalize_railway_u_girder_assembly_settings(values, stage_settings)
        summary = system_settings_from_mapping(normalized)
        st.markdown(
            _kv_panel_html(
                [
                    ("Assembly basis", "2 precast prestressed webs + CIP slab"),
                    ("Support / span", f"Simply supported | L = {summary.span_length_m:.3f} m"),
                    ("Wet slab casting", "Case B: wet slab + formwork carried by web-only sections"),
                    ("Load distribution", "50% to left web / 50% to right web"),
                    ("Lifting", f"a = {float(stage_settings['lifting_point_ratio']) * float(span_length_m):.3f} m from each end | IF = {float(stage_settings['lifting_impact_factor']):.2f}"),
                    ("Stage behavior", "Transfer/lifting/wet casting = web-only; composite/service = full U-girder"),
                ]
            ),
            unsafe_allow_html=True,
        )


def _render_bridge_section_assembly_panel(preset: dict[str, Any], settings: AnalysisModeSettings) -> None:
    """Render bridge-domain section assembly inputs in Section Builder."""

    values = _ensure_beam_girder_system_settings_defaults()
    if _is_railway_u_girder_preset(preset):
        _render_railway_u_girder_assembly_panel(values)
        return

    count_label, spacing_label, unit_noun = _assembly_unit_label(preset, settings)
    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Bridge Section Assembly", "Assembly", "Bridge", "Section-specific"),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Bridge section assembly settings belong with the selected section preset. '
            'Setup stays limited to project workflow and design-code choices.</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(4)
        with cols[0]:
            values["span_length_m"] = st.number_input(
                "Span length L (m)",
                min_value=0.1,
                step=0.5,
                value=float(values.get("span_length_m", DEFAULT_SPAN_LENGTH_M)),
                format="%.3f",
                key="section_assembly_span_length_m_input",
                help="Single source for simple-span SLS load diagrams and prestress/debonding station previews.",
            )
        with cols[1]:
            values["number_of_girders"] = int(
                st.number_input(
                    count_label,
                    min_value=1,
                    step=1,
                    value=int(values.get("number_of_girders", DEFAULT_NUMBER_OF_GIRDERS)),
                    key="section_assembly_number_of_girders_input",
                    help="Assembly count for equal-share load previews.  For plank/box presets this represents units per bridge cross-section.",
                )
            )
        with cols[2]:
            values["girder_spacing_m"] = st.number_input(
                spacing_label,
                min_value=0.1,
                step=0.1,
                value=float(values.get("girder_spacing_m", DEFAULT_GIRDER_SPACING_M)),
                format="%.3f",
                key="section_assembly_girder_spacing_m_input",
                help="Module spacing/width used by load take-down previews.  Effective slab width Be remains separate section metadata.",
            )
        with cols[3]:
            values["concrete_unit_weight_kN_m3"] = st.number_input(
                "Concrete unit weight (kN/m³)",
                min_value=1.0,
                step=0.5,
                value=float(values.get("concrete_unit_weight_kN_m3", DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3)),
                format="%.2f",
                key="section_assembly_concrete_unit_weight_input",
                help="Default unit weight for girder/web self-weight and wet concrete load previews.",
            )
        values["tributary_width_m"] = st.number_input(
            "Tributary width for load take-down (m)",
            min_value=0.1,
            step=0.1,
            value=float(values.get("tributary_width_m") or values.get("girder_spacing_m") or DEFAULT_GIRDER_SPACING_M),
            format="%.3f",
            key="section_assembly_tributary_width_m_input",
            help="Use module spacing by default unless project-specific load distribution requires an override.",
        )
        lift_cols = st.columns(4)
        with lift_cols[0]:
            values["lifting_point_ratio"] = st.number_input(
                "Lifting a/L",
                min_value=0.05,
                max_value=0.45,
                step=0.01,
                value=float(values.get("lifting_point_ratio", DEFAULT_LIFTING_POINT_RATIO)),
                format="%.3f",
                key="section_assembly_lifting_ratio_input",
                help="Two-point symmetric lifting point measured from each end. Used for individual precast unit lifting only.",
            )
        with lift_cols[1]:
            st.markdown(_compact_summary_card_html("Lifting a", f"{float(values['lifting_point_ratio']) * float(values['span_length_m']):.3f} m", "from each end"), unsafe_allow_html=True)
        with lift_cols[2]:
            values["lifting_impact_factor"] = st.number_input(
                "Lifting impact factor",
                min_value=1.0,
                step=0.05,
                value=float(values.get("lifting_impact_factor", DEFAULT_LIFTING_IMPACT_FACTOR)),
                format="%.2f",
                key="section_assembly_lifting_impact_input",
                help="Multiplier applied to individual precast unit self-weight during the lifting-stage stress preview.",
            )
        with lift_cols[3]:
            st.markdown(_compact_summary_card_html("Lifting basis", "Individual precast unit", "not bridge assembly", accent="green"), unsafe_allow_html=True)
        normalized = system_settings_from_mapping(values).as_metadata()
        st.session_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = normalized
        _sync_beam_girder_span_to_existing_sources(normalized)
        summary = system_settings_from_mapping(normalized)
        rows = [
            ("Assembly basis", unit_noun),
            ("Span source", f"{summary.span_length_m:.3f} m"),
            ("Load tributary width", f"{summary.effective_tributary_width_m:.3f} m"),
            ("Concrete unit weight", f"{summary.concrete_unit_weight_kN_m3:.2f} kN/m³"),
            ("Assembly count", f"{summary.number_of_girders:d}"),
            ("Lifting", f"a = {summary.lifting_point_ratio * summary.span_length_m:.3f} m from each end | IF = {summary.lifting_impact_factor:.2f}"),
        ]
        st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)


def _render_building_member_assembly_panel(preset: dict[str, Any], settings: AnalysisModeSettings) -> None:
    """Render building-domain member assembly inputs in Section Builder."""

    values = _ensure_beam_girder_system_settings_defaults()
    _count_label, spacing_label, _unit_noun = _assembly_unit_label(preset, settings)
    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Building Member Assembly", "Assembly", "Building", "Section-specific"),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Building member assembly settings are tied to the selected member/preset. '
            'Bridge-only girder counts, barrier, sidewalk, and wearing-surface assumptions remain outside this workflow.</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(3)
        with cols[0]:
            values["span_length_m"] = st.number_input(
                "Span length L (m)",
                min_value=0.1,
                step=0.5,
                value=float(values.get("span_length_m", DEFAULT_SPAN_LENGTH_M)),
                format="%.3f",
                key="building_member_assembly_span_length_m_input",
                help="Single source for simple-span service moment diagrams and prestress/debonding previews.",
            )
        with cols[1]:
            values["girder_spacing_m"] = st.number_input(
                spacing_label,
                min_value=0.1,
                step=0.1,
                value=float(values.get("girder_spacing_m") or values.get("tributary_width_m") or DEFAULT_GIRDER_SPACING_M),
                format="%.3f",
                key="building_member_assembly_spacing_m_input",
                help="Typical building beam/girder spacing for floor/roof load take-down.",
            )
        with cols[2]:
            values["concrete_unit_weight_kN_m3"] = st.number_input(
                "Concrete unit weight (kN/m³)",
                min_value=1.0,
                step=0.5,
                value=float(values.get("concrete_unit_weight_kN_m3", DEFAULT_CONCRETE_UNIT_WEIGHT_KN_M3)),
                format="%.2f",
                key="building_member_assembly_unit_weight_input",
                help="Default unit weight for precast member self-weight and wet topping load preview.",
            )
        values["use_girder_spacing_as_tributary_width"] = st.checkbox(
            "Use beam/girder spacing as tributary width",
            value=bool(values.get("use_girder_spacing_as_tributary_width", True)),
            key="building_member_assembly_use_spacing_as_tributary_width",
            help="Recommended default for ordinary interior building beams/girders.",
        )
        if values["use_girder_spacing_as_tributary_width"]:
            values["tributary_width_m"] = float(values["girder_spacing_m"])
            st.caption(f"Load tributary width is locked to member spacing = {float(values['girder_spacing_m']):.3f} m.")
        else:
            values["tributary_width_m"] = st.number_input(
                "Tributary width for SDL/LL load take-down (m)",
                min_value=0.1,
                step=0.1,
                value=float(values.get("tributary_width_m") or values.get("girder_spacing_m") or DEFAULT_GIRDER_SPACING_M),
                format="%.3f",
                key="building_member_assembly_tributary_width_m_input",
                help="Override only for edge beams, openings, or special load paths.",
            )
        lift_cols = st.columns(4)
        with lift_cols[0]:
            values["lifting_point_ratio"] = st.number_input(
                "Lifting a/L",
                min_value=0.05,
                max_value=0.45,
                step=0.01,
                value=float(values.get("lifting_point_ratio", DEFAULT_LIFTING_POINT_RATIO)),
                format="%.3f",
                key="building_member_assembly_lifting_ratio_input",
                help="Two-point symmetric lifting point measured from each end. Used for individual precast member lifting only.",
            )
        with lift_cols[1]:
            st.markdown(_compact_summary_card_html("Lifting a", f"{float(values['lifting_point_ratio']) * float(values['span_length_m']):.3f} m", "from each end"), unsafe_allow_html=True)
        with lift_cols[2]:
            values["lifting_impact_factor"] = st.number_input(
                "Lifting impact factor",
                min_value=1.0,
                step=0.05,
                value=float(values.get("lifting_impact_factor", DEFAULT_LIFTING_IMPACT_FACTOR)),
                format="%.2f",
                key="building_member_assembly_lifting_impact_input",
                help="Multiplier applied to individual precast member self-weight during the lifting-stage stress preview.",
            )
        with lift_cols[3]:
            st.markdown(_compact_summary_card_html("Lifting basis", "Individual precast member", "not floor assembly", accent="green"), unsafe_allow_html=True)
        values.setdefault("number_of_girders", DEFAULT_NUMBER_OF_GIRDERS)
        normalized = system_settings_from_mapping(values).as_metadata()
        st.session_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY] = normalized
        _sync_beam_girder_span_to_existing_sources(normalized)
        summary = system_settings_from_mapping(normalized)
        st.markdown(
            _kv_panel_html(
                [
                    ("Span source", f"{summary.span_length_m:.3f} m"),
                    ("Beam/girder spacing", f"{summary.girder_spacing_m:.3f} m"),
                    ("Load tributary width", f"{summary.effective_tributary_width_m:.3f} m"),
                    ("Concrete unit weight", f"{summary.concrete_unit_weight_kN_m3:.2f} kN/m³"),
                    ("Lifting", f"a = {summary.lifting_point_ratio * summary.span_length_m:.3f} m from each end | IF = {summary.lifting_impact_factor:.2f}"),
                ]
            ),
            unsafe_allow_html=True,
        )


def _render_section_assembly_panel(preset: dict[str, Any]) -> None:
    """Render workflow-specific assembly controls in Section Builder."""

    settings = _analysis_mode_from_session_state()
    if is_bridge_beam_girder_workflow(settings):
        _render_bridge_section_assembly_panel(preset, settings)
    elif is_building_beam_girder_workflow(settings):
        _render_building_member_assembly_panel(preset, settings)


def _render_concrete_material_assignment(preset: dict[str, Any]) -> dict[str, Any]:
    materials = _ensure_concrete_material_session()
    material_map = concrete_materials_by_name(materials)
    material_names = list(material_map)
    active_name = st.session_state.get("active_concrete_material_name")
    default_primary_index = _material_select_index(material_names, active_name)
    if active_name not in material_map:
        st.session_state["active_concrete_material_name"] = material_names[default_primary_index]

    st.markdown("##### Concrete Material Assignment")

    if _is_railway_u_girder_preset(preset):
        stage_settings = dict(st.session_state.get(RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY, {}) or {})
        web_default_name = _material_name_for_fc(
            material_map,
            RAILWAY_U_GIRDER_DEFAULT_WEB_FC_MPA,
            st.session_state.get("active_concrete_material_name") or stage_settings.get("web_concrete_material_name"),
        )
        slab_default_name = _material_name_for_fc(
            material_map,
            RAILWAY_U_GIRDER_DEFAULT_SLAB_FC_MPA,
            stage_settings.get("slab_concrete_material_name") or st.session_state.get("deck_topping_material_name"),
        )
        web_index = _material_select_index(material_names, web_default_name)
        slab_index = _material_select_index(material_names, slab_default_name, fallback_index=min(1, len(material_names) - 1))

        selected_web = st.selectbox(
            "Precast web concrete material",
            material_names,
            index=web_index,
            help="Concrete for the two precast prestressed side webs. Transfer, lifting, and wet slab casting stages use web-only section behavior.",
            key="active_concrete_material_name",
        )
        web_material = material_map[selected_web]
        st.session_state["primary_concrete_material_name"] = selected_web
        st.session_state["concrete_material"] = web_material

        selected_slab = st.selectbox(
            "CIP slab concrete material",
            material_names,
            index=slab_index,
            help="Concrete for the cast-in-place slab that connects the two precast webs into the full U-girder after hardening.",
            key="railway_u_girder_slab_material_name",
        )
        slab_material = material_map[selected_slab]
        st.session_state["deck_topping_material_name"] = selected_slab

        web_fci_default = float(stage_settings.get("web_fci_MPa", RAILWAY_U_GIRDER_DEFAULT_WEB_FCI_MPA) or RAILWAY_U_GIRDER_DEFAULT_WEB_FCI_MPA)
        web_fci = st.number_input(
            "Precast web f'ci at transfer (MPa)",
            min_value=1.0,
            value=float(web_fci_default),
            step=1.0,
            key="railway_u_girder_web_fci_MPa",
            help="Concrete compressive strength at prestress transfer/release for web-only transfer and lifting checks.",
        )

        assignment: dict[str, Any] = {
            "primary_material_name": selected_web,
            "primary_fc_MPa": web_material.fc_MPa,
            "Ebeam_MPa": web_material.effective_Ec_MPa,
            "is_composite_applicable": True,
            "railway_u_girder_stage_materials": True,
            "web_concrete_material_name": selected_web,
            "web_fc_MPa": web_material.fc_MPa,
            "web_fci_MPa": float(web_fci),
            "Eweb_MPa": web_material.effective_Ec_MPa,
            "Eweb_ci_MPa": 4700.0 * float(web_fci) ** 0.5,
            "slab_concrete_material_name": selected_slab,
            "slab_fc_MPa": slab_material.fc_MPa,
            "Eslab_MPa": slab_material.effective_Ec_MPa,
        }
        _sync_railway_u_girder_stage_material_settings(
            {
                "web_concrete_material_name": selected_web,
                "web_fc_MPa": float(web_material.fc_MPa),
                "web_fci_MPa": float(web_fci),
                "slab_concrete_material_name": selected_slab,
                "slab_fc_MPa": float(slab_material.fc_MPa),
            }
        )
        st.markdown(
            _kv_panel_html(
                [
                    ("Precast web", f"{selected_web} | f'c {web_material.fc_MPa:g} MPa | Ec {_format_ec(web_material.effective_Ec_MPa)}"),
                    ("Transfer web f'ci", f"{float(web_fci):g} MPa | Eci {_format_ec(assignment['Eweb_ci_MPa'])}"),
                    ("CIP slab", f"{selected_slab} | f'c {slab_material.fc_MPa:g} MPa | Ec {_format_ec(slab_material.effective_Ec_MPa)}"),
                    ("Stage routing", "Transfer/lifting/wet casting = web-only; service = full U-girder staged basis"),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Railway U-Girder material assignment is section-specific. '
            "Setup → Materials remains a library; this panel selects the material sources for this preset and syncs the staged-construction metadata.</div>",
            unsafe_allow_html=True,
        )
        return assignment

    selected_primary = st.selectbox(
        "Primary / section concrete material",
        material_names,
        index=default_primary_index,
        help="Material for the main concrete polygon. This is the concrete material used by PMM analysis.",
        key="active_concrete_material_name",
    )
    primary_material = material_map[selected_primary]
    # Do not assign to st.session_state["active_concrete_material_name"] here.
    # The selectbox owns that widget key; assigning to the same key after widget
    # instantiation raises StreamlitAPIException on Streamlit Cloud.
    st.session_state["primary_concrete_material_name"] = selected_primary
    st.session_state["concrete_material"] = primary_material

    bridge_composite_metadata = _composite_metadata_enabled_for_workflow(preset)
    assignment = {
        "primary_material_name": selected_primary,
        "primary_fc_MPa": primary_material.fc_MPa,
        "Ebeam_MPa": primary_material.effective_Ec_MPa,
        "is_composite_applicable": bridge_composite_metadata,
    }

    if bridge_composite_metadata:
        deck_name = st.session_state.get("deck_topping_material_name", DEFAULT_DECK_TOPPING_MATERIAL)
        deck_index = _material_select_index(material_names, deck_name, fallback_index=min(1, len(material_names) - 1))
        if deck_name not in material_map:
            st.session_state["deck_topping_material_name"] = material_names[deck_index]
        selected_deck = st.selectbox(
            "Deck / topping concrete material",
            material_names,
            index=deck_index,
            help="Used for Edeck, modular ratio n, and transformed-width metadata only in this milestone.",
            key="deck_topping_material_name",
        )
        deck_material = material_map[selected_deck]
        # The deck selectbox owns st.session_state["deck_topping_material_name"].
        # Do not reassign it after widget creation.
        assignment.update(
            {
                "deck_topping_material_name": selected_deck,
                "deck_fc_MPa": deck_material.fc_MPa,
                "Edeck_MPa": deck_material.effective_Ec_MPa,
            }
        )
        n_ratio = deck_material.effective_Ec_MPa / primary_material.effective_Ec_MPa
        assignment["n_Edeck_over_Ebeam"] = n_ratio
        st.markdown(
            _kv_panel_html(
                [
                    ("Primary material", f"{selected_primary} | f'c {primary_material.fc_MPa:g} MPa | Ec {_format_ec(primary_material.effective_Ec_MPa)}"),
                    ("Deck/topping material", f"{selected_deck} | f'c {deck_material.fc_MPa:g} MPa | Ec {_format_ec(deck_material.effective_Ec_MPa)}"),
                    ("n = Edeck/Ebeam", _format_float(n_ratio, 3)),
                    ("Composite scope", "Metadata only; slab/topping is not merged into gross properties or PMM"),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Deck/topping material is used for composite metadata and transformed-width '
            "calculation only in this milestone. Composite slab/topping is not yet merged into gross section properties "
            "or PMM solver.</div>",
            unsafe_allow_html=True,
        )
    else:
        settings = _analysis_mode_from_session_state()
        if _is_composite_capable_preset(preset) and is_building_beam_girder_workflow(settings):
            st.caption(
                "Deck / topping material: Hidden unless the preset is an explicitly shared prestressed girder geometry. "
                "Bridge AASHTO Be automation and staged bridge load workflows remain hidden under Building Beam/Girder."
            )
        else:
            st.caption("Deck / topping material: Not applicable for this section type.")
        st.markdown(
            _kv_panel_html(
                [
                    ("Primary material", f"{selected_primary} | f'c {primary_material.fc_MPa:g} MPa"),
                    ("Primary Ec", _format_ec(primary_material.effective_Ec_MPa)),
                    ("Solver material", "Primary / section concrete only"),
                ]
            ),
            unsafe_allow_html=True,
        )
    return assignment

def _render_section_builder_status_strip(preset: dict[str, Any], material_assignment: dict[str, Any]) -> None:
    """Render the compact default context strip for the definition workspace."""

    settings = _analysis_mode_from_session_state()
    primary = str(material_assignment.get("primary_material_name", "N/A"))
    deck = str(material_assignment.get("deck_topping_material_name", "N/A"))
    material_detail = f"Precast {primary}"
    if _composite_metadata_enabled_for_workflow(preset, settings):
        material_detail += f" / topping {deck}"

    rebar_status = "Enabled" if ordinary_rebar_enabled(st.session_state) else "Disabled"
    prestress_status = "Enabled" if prestressing_steel_enabled(st.session_state) else "Disabled"
    axis_value, axis_detail = _section_axis_status_for_workflow(settings)

    st.markdown("##### Section Workspace Status")
    st.markdown(
        _property_strip_html(
            [
                SectionMetric("Section", _workflow_specific_preset_display_name(preset, settings), str(preset.get("category", "General")), "info", True),
                SectionMetric("Workflow", analysis_mode_label(settings), _section_family_label_for_workflow(preset, settings), "ready", True),
                SectionMetric("Axis", axis_value, axis_detail, "neutral"),
                SectionMetric("Rebar / Prestress", f"{rebar_status} / {prestress_status}", "stored reinforcement is previewed on its own page", "ready" if prestress_status == "Enabled" or rebar_status == "Enabled" else "neutral"),
                SectionMetric("Concrete", material_detail, "visible in material assignment panel", "info"),
            ]
        ),
        unsafe_allow_html=True,
    )


def _workflow_specific_preset_display_name(
    preset: dict[str, Any], settings: AnalysisModeSettings | None = None
) -> str:
    """Return the preset display name for the active engineering workflow.

    Preset filtering must be driven by explicit metadata, not by brittle words
    embedded in display labels.  The display alias lets shared geometry such as
    the Precast I-Girder read as a Building or Bridge preset without duplicating
    geometry-generator code or changing solver routing keys.
    """

    display_names = preset.get("workflow_display_names")
    workflow_key = getattr(settings, "member_type", None) if settings is not None else None
    if isinstance(display_names, dict) and workflow_key:
        value = display_names.get(str(workflow_key))
        if value:
            return str(value)
    return str(preset.get("display_name", "N/A"))


def _preset_option_label(preset: dict[str, Any], settings: AnalysisModeSettings | None = None) -> str:
    """Return the user-facing label for a section preset selector option.

    Workflow-specific aliases may already include the preset family/category
    (for example, the Building/Bridge Precast I-Girder labels).  Do not append
    the same category again; duplicated labels are confusing and make the
    selector look like it is offering two different composite-girder concepts.
    """

    display_name = _workflow_specific_preset_display_name(preset, settings)
    category = str(preset.get('category', 'General'))
    if category and category.casefold() in display_name.casefold():
        return display_name
    return f"{display_name}  ·  {category}"


def _preset_maps(
    presets: list[dict[str, Any]], settings: AnalysisModeSettings | None = None
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, str]]:
    """Build stable key-based selector maps for Streamlit widgets.

    The Section Type / Preset selectbox must be keyed by immutable preset keys,
    not by display labels or a dynamically changing index. Otherwise Streamlit
    can require two user selections: the first rerun updates the stored preset,
    and the next rerun rebuilds the widget with a different default index.
    """
    preset_keys = [str(preset.get("key", "")) for preset in presets]
    preset_map = {str(preset.get("key", "")): preset for preset in presets}
    label_map = {key: _preset_option_label(preset_map[key], settings) for key in preset_keys}
    return preset_keys, preset_map, label_map


def _initial_preset_selector_key(preset_keys: list[str]) -> str:
    """Resolve the initial section preset selector value from session state."""
    if not preset_keys:
        return ""

    current_widget_value = st.session_state.get("section_preset_selector_key")
    if current_widget_value in preset_keys:
        return str(current_widget_value)

    loaded_preset_key = st.session_state.get("section_preset_key")
    if loaded_preset_key in preset_keys:
        return str(loaded_preset_key)

    return preset_keys[0]

def _is_parametric_i_girder(preset: dict[str, Any]) -> bool:
    return str(preset.get("key", "")) == "parametric_i_girder"


def _is_precast_u_girder(preset: dict[str, Any]) -> bool:
    return str(preset.get("key", "")) == "u_girder"


def _is_precast_box_beam(preset: dict[str, Any]) -> bool:
    return str(preset.get("key", "")) in {"box_section_fillet", "precast_box_beam_exterior"}


def _is_parametric_plank_girder(preset: dict[str, Any]) -> bool:
    return str(preset.get("key", "")).startswith("parametric_plank_girder_")


def _is_interior_plank_girder_key(preset_key: str) -> bool:
    return str(preset_key) in {"parametric_plank_girder_interior", "parametric_plank_girder_voided_interior"}


def _geometry_parameter_names(preset: dict[str, Any]) -> set[str]:
    """Return parameter names accepted by the section geometry generator.

    Section Builder may store additional analysis metadata, such as
    ``composite_enabled``, in ``section_parameters``.  Those metadata fields
    must not be passed into geometry/dimension generator functions because the
    accepted section polygons are intentionally unchanged.
    """

    return {str(parameter.get("name", "")) for parameter in preset.get("parameters", [])}


def _is_composite_capable_preset(preset: dict[str, Any]) -> bool:
    """Return whether the current preset has explicit deck/topping metadata."""

    # SECTION.COMPOSITE1C enables display-only transformed composite properties
    # for the Precast I-Girder as well as Precast Plank Girder presets.  The deck
    # metadata is still explicit UI input and remains separate from gross
    # section properties and all PMM/prestress solver paths.
    return (
        _is_parametric_i_girder(preset)
        or _is_precast_u_girder(preset)
        or _is_precast_box_beam(preset)
        or _is_parametric_plank_girder(preset)
    )


def _girder_section_family(preset: dict[str, Any]) -> str:
    """Classify the Beam/Girder section intent used by service-stage UI routing."""

    category = str(preset.get("category", "")).casefold()
    if _is_composite_capable_preset(preset) or category == "precast composite girder":
        return "precast_composite_girder"
    if "girder" in category:
        return "general_non_composite_girder"
    return "non_girder"


def _girder_section_family_label(preset: dict[str, Any]) -> str:
    """Return the user-facing section family label for Beam/Girder workflow."""

    family = _girder_section_family(preset)
    if family == "precast_composite_girder":
        return "Precast Composite Girder"
    if family == "general_non_composite_girder":
        return "General / Non-composite Girder"
    return "Column/Pier/Wall/Pylon section"


def _section_family_label_for_workflow(
    preset: dict[str, Any], settings: AnalysisModeSettings | None = None
) -> str:
    """Return a workflow-scoped section-family label without changing legacy routes.

    CROSSBEAM.WF1A keeps the established girder/column classification helpers
    untouched for existing workflows.  Portal Frame Crossbeam receives its own
    explicit family label so status cards do not fall through to Column/Pier.
    """

    active_settings = settings or _analysis_mode_from_session_state()
    if is_portal_frame_crossbeam_workflow(active_settings):
        return "Portal Frame Crossbeam"
    return _girder_section_family_label(preset)


def _section_axis_status_for_workflow(settings: AnalysisModeSettings) -> tuple[str, str]:
    """Return the visible coordinate convention for the active workflow."""

    if is_portal_frame_crossbeam_workflow(settings):
        return (
            "x/y + s",
            "x/y local cross-section axes; s longitudinal left→right",
        )
    return "x/y/z", "x horizontal, y vertical, z longitudinal"


def _recommended_service_basis_for_preset(preset: dict[str, Any]) -> str:
    """Return the default Service-stage basis implied by the selected section family."""

    if _girder_section_family(preset) == "precast_composite_girder":
        return "Composite transformed"
    return "Precast gross"


def _default_reinforcement_flags_for_preset(preset: dict[str, Any]) -> tuple[bool, bool]:
    settings = _analysis_mode_from_session_state()
    return default_section_reinforcement_flags(
        member_type=settings.member_type,
        section_category=str(preset.get("category", "")),
        section_preset_key=str(preset.get("key", "")),
        girder_section_family=_girder_section_family(preset),
    )


def _ensure_reinforcement_flags_for_preset(preset: dict[str, Any]) -> None:
    preset_key = str(preset.get("key", ""))
    default_rebar, default_prestress = _default_reinforcement_flags_for_preset(preset)
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    user_override_exists = bool(metadata.get(SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY, False)) or bool(
        st.session_state.get(SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY, False)
    )
    override_preset_key = str(
        st.session_state.get(SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY)
        or metadata.get(SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY)
        or metadata.get(REINFORCEMENT_FLAGS_PRESET_KEY)
        or ""
    )
    # A user override belongs to the preset on which it was made.  This keeps
    # same-preset navigation persistent while preventing a Column/Pier OFF state
    # from leaking into a newly selected Portal Frame Crossbeam preset.  Legacy
    # project files remain compatible because REINFORCEMENT_FLAGS_PRESET_KEY is
    # used as the fallback scope when the new key is absent.
    user_overridden = user_override_exists and override_preset_key == preset_key

    # These switches are explicit engineering input, not transient UI state.
    # Returning to Section Builder after Analysis must not silently reset them.
    #
    # Legacy sessions/projects may contain False from the older Beam/Girder
    # default.  When the active preset now defaults ON and the user has not
    # explicitly overridden the steel-system switches in this session/project,
    # upgrade the effective UI value to ON so mild longitudinal bars / torsion
    # Al and prestressing steel remain active by default.
    if ORDINARY_REBAR_FLAG_KEY not in st.session_state or (default_rebar and not user_overridden):
        st.session_state[ORDINARY_REBAR_FLAG_KEY] = bool(
            default_rebar if default_rebar and not user_overridden else metadata.get(ORDINARY_REBAR_FLAG_KEY, default_rebar)
        )
    if PRESTRESSING_STEEL_FLAG_KEY not in st.session_state or (default_prestress and not user_overridden):
        st.session_state[PRESTRESSING_STEEL_FLAG_KEY] = bool(
            default_prestress if default_prestress and not user_overridden else metadata.get(PRESTRESSING_STEEL_FLAG_KEY, default_prestress)
        )
    st.session_state[REINFORCEMENT_FLAGS_PRESET_KEY] = preset_key


def _on_reinforcement_flags_changed() -> None:
    st.session_state[SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY] = True
    active_preset_key = str(
        st.session_state.get(REINFORCEMENT_FLAGS_PRESET_KEY)
        or st.session_state.get("section_preset_key")
        or ""
    )
    st.session_state[SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY] = active_preset_key
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    metadata[SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY] = True
    metadata[SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY] = active_preset_key
    st.session_state["project_metadata"] = metadata
    _store_reinforcement_flags_metadata()


def _store_reinforcement_flags_metadata() -> None:
    """Mirror section-level steel-system switches into project metadata.

    The checkbox widget keys remain owned by Streamlit.  This helper copies
    their current values into durable metadata and non-widget mirror keys so
    downstream pages see the same include-rebar/include-prestress decision
    immediately after leaving Section Builder.
    """

    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    for flag_name in (
        ORDINARY_REBAR_FLAG_KEY,
        PRESTRESSING_STEEL_FLAG_KEY,
        REINFORCEMENT_FLAGS_PRESET_KEY,
        SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY,
        SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY,
    ):
        if flag_name in st.session_state:
            metadata[flag_name] = st.session_state[flag_name]

    preset_key = str(st.session_state.get(REINFORCEMENT_FLAGS_PRESET_KEY) or st.session_state.get("section_preset_key") or "").strip()
    ordinary_enabled = bool(st.session_state.get(ORDINARY_REBAR_FLAG_KEY, False))
    prestress_enabled = bool(st.session_state.get(PRESTRESSING_STEEL_FLAG_KEY, False))

    st.session_state[SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY] = ordinary_enabled
    st.session_state[SECTION_BUILDER_PRESTRESS_SYNC_KEY] = prestress_enabled
    st.session_state[SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY] = preset_key

    metadata[SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY] = ordinary_enabled
    metadata[SECTION_BUILDER_PRESTRESS_SYNC_KEY] = prestress_enabled
    metadata[SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY] = preset_key
    st.session_state["project_metadata"] = metadata


def _render_reinforcement_prestress_system_panel(preset: dict[str, Any]) -> None:
    """Render visible section-level rebar/prestress participation switches."""

    _ensure_reinforcement_flags_for_preset(preset)
    default_rebar, default_prestress = _default_reinforcement_flags_for_preset(preset)
    family_label = _section_family_label_for_workflow(preset)
    st.markdown("##### Section Steel Systems")
    st.markdown(
        '<div class="cpmm-section-note">Choose which internal steel systems are included in this section analysis. '
        'Disabling a system preserves existing Rebar/Prestress input tables but excludes that system from analysis input assembly. '
        'For precast girders, enable ordinary rebar when mild longitudinal bars or torsion Al are part of the design model.</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox(
            "Include ordinary rebar / longitudinal Al",
            value=ordinary_rebar_enabled(st.session_state, default=default_rebar),
            key=ORDINARY_REBAR_FLAG_KEY,
            help=(
                "When disabled, stored ordinary Rebar rows are kept but ignored by PMM/SLS analysis. "
                "Enable this for precast girders when mild longitudinal bars should participate in flexure/effective d or torsion Al review."
            ),
            on_change=_on_reinforcement_flags_changed,
        )
    with col2:
        st.checkbox(
            "Include prestressing steel",
            value=prestressing_steel_enabled(st.session_state, default=default_prestress),
            key=PRESTRESSING_STEEL_FLAG_KEY,
            help="When disabled, stored Prestress rows/strand layout data are kept but ignored by analysis and hidden from the default section preview.",
            on_change=_on_reinforcement_flags_changed,
        )

    _store_reinforcement_flags_metadata()

    rebar_status = "Enabled" if ordinary_rebar_enabled(st.session_state, default=default_rebar) else "Disabled"
    ps_status = "Enabled" if prestressing_steel_enabled(st.session_state, default=default_prestress) else "Disabled"
    st.markdown(
        _kv_panel_html(
            [
                ("Selected section family", family_label),
                ("Ordinary rebar / longitudinal Al", rebar_status),
                ("Prestressing steel", ps_status),
                ("Default for this preset", f"Rebar {'ON' if default_rebar else 'OFF'} / Prestress {'ON' if default_prestress else 'OFF'}"),
            ]
        ),
        unsafe_allow_html=True,
    )


_COLUMN_PIER_SECTION_CATEGORIES = frozenset({"Basic Solid", "Hollow / Voided", "Pier / Column", "Custom"})
_BRIDGE_BEAM_GIRDER_SECTION_CATEGORIES = frozenset(
    {"Precast Composite Girder", "General / Non-composite Girder", "Girder", "Box Girder", "Custom"}
)
_BUILDING_BEAM_GIRDER_SECTION_CATEGORIES = frozenset(
    {"Basic Solid", "Hollow / Voided", "General / Non-composite Girder", "Custom"}
)
_PORTAL_FRAME_CROSSBEAM_SECTION_CATEGORIES = frozenset({"Portal Frame Crossbeam"})
_BUILDING_SHARED_PRECAST_GIRDER_PRESET_KEYS = frozenset(
    {
        # Shared geometry only: available under Building Beam/Girder ACI workflow
        # without enabling bridge-specific AASHTO Be, staged SLS, or SDL tools.
        "parametric_i_girder",
    }
)


def _section_categories_for_member_type(settings: AnalysisModeSettings) -> set[str]:
    """Return the section preset categories allowed by the active member workflow.

    WORKFLOW.TYPE3 separates physical section geometry from design-code context.
    Bridge Beam/Girder exposes bridge girder categories under AASHTO LRFD.
    Building Beam/Girder exposes building beam categories under ACI 318 plus
    explicitly shared precast girder geometry such as Precast I-Girder.  Shared
    geometry does not activate bridge-only load/stage/effective-width tools.
    """

    if is_bridge_beam_girder_workflow(settings):
        return set(_BRIDGE_BEAM_GIRDER_SECTION_CATEGORIES)
    if is_building_beam_girder_workflow(settings):
        return set(_BUILDING_BEAM_GIRDER_SECTION_CATEGORIES | {"Precast Composite Girder"})
    if is_portal_frame_crossbeam_workflow(settings):
        return set(_PORTAL_FRAME_CROSSBEAM_SECTION_CATEGORIES)
    return set(_COLUMN_PIER_SECTION_CATEGORIES)


def _preset_allowed_workflows(preset: dict[str, Any]) -> set[str]:
    """Return explicit workflow metadata for a preset, when configured."""

    raw = preset.get("allowed_workflows")
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def _is_crossbeam_preset(preset: dict[str, Any]) -> bool:
    return "portal_frame_crossbeam" in _preset_allowed_workflows(preset) or str(preset.get("category", "")) == "Portal Frame Crossbeam"


def _preset_matches_member_type(preset: dict[str, Any], settings: AnalysisModeSettings) -> bool:
    """Return whether a section preset should be shown for the active workflow.

    PRESET.ROUTING1 uses explicit preset metadata where available.  Category
    filtering remains as a compatibility fallback for legacy/custom presets that
    do not yet declare ``allowed_workflows``.
    """

    workflow_key = str(settings.member_type)
    allowed_workflows = _preset_allowed_workflows(preset)
    if allowed_workflows:
        return workflow_key in allowed_workflows

    category = str(preset.get("category", "General"))
    preset_key = str(preset.get("key", ""))
    if is_building_beam_girder_workflow(settings):
        return category in _BUILDING_BEAM_GIRDER_SECTION_CATEGORIES or preset_key in _BUILDING_SHARED_PRECAST_GIRDER_PRESET_KEYS
    allowed_categories = _section_categories_for_member_type(settings)
    return category in allowed_categories


def _filter_presets_for_member_type(
    presets: list[dict[str, Any]], settings: AnalysisModeSettings
) -> list[dict[str, Any]]:
    """Filter section presets by active member workflow without changing presets."""

    filtered = [preset for preset in presets if _preset_matches_member_type(preset, settings)]
    return filtered or list(presets)


def _categories_for_filtered_presets(
    configured_categories: list[str], filtered_presets: list[dict[str, Any]]
) -> list[str]:
    """Keep the Section Category browser consistent with filtered presets."""

    visible_preset_categories = {str(preset.get("category", "General")) for preset in filtered_presets}
    categories = [category for category in configured_categories if category in visible_preset_categories]
    for category in visible_preset_categories:
        if category not in categories:
            categories.append(category)
    return categories or list(configured_categories)


def _member_type_filter_description(settings: AnalysisModeSettings) -> str:
    """Human-readable description of the active Section Type / Preset filter."""

    if is_building_beam_girder_workflow(settings):
        return (
            "Section Type / Preset is filtered by explicit workflow metadata. "
            "Building Beam/Girder hides bridge/railway/highway-only presets; shared precast girder geometry is shown with a Building-specific label. Bridge-specific load/stage/AASHTO Be tools stay hidden."
        )
    if is_portal_frame_crossbeam_workflow(settings):
        return (
            "Section Type / Preset is filtered to Portal Frame Crossbeam presets: rectangular solid with bottom fillets and rectangular hollow with wall-thickness-defined opening, bottom fillets, and inner chamfers."
        )
    allowed_categories = _section_categories_for_member_type(settings)
    category_text = ", ".join(sorted(allowed_categories))
    return f"Section Type / Preset is filtered to workflow-specific categories: {category_text}."



def _analysis_mode_from_session_state() -> AnalysisModeSettings:
    value = st.session_state.get("analysis_mode_settings")
    if isinstance(value, AnalysisModeSettings):
        return value
    if isinstance(value, dict):
        return AnalysisModeSettings.model_validate(value)
    return AnalysisModeSettings()


def _axis_convention_rows(settings: AnalysisModeSettings | None = None) -> list[tuple[str, str]]:
    """Return the workflow-scoped axis/action convention used by Section Builder."""

    active_settings = settings or _analysis_mode_from_session_state()
    if is_portal_frame_crossbeam_workflow(active_settings):
        return [
            ("x-axis", "Horizontal local coordinate in the cross-section; also used as tendon lateral position in plan"),
            ("y-axis", "Vertical local coordinate in the cross-section; positive upward"),
            ("s-axis", "Crossbeam longitudinal station, positive from left anchorage to right anchorage"),
            ("dtop(s)", "Tendon depth measured downward from the section top surface"),
            ("e(s)", "Calculated tendon eccentricity; positive below the active-section centroid"),
        ]
    return [
        ("x-axis", "Horizontal section width direction in the section preview"),
        ("y-axis", "Vertical section depth direction; positive upward in the section preview"),
        ("z-axis", "Member / girder longitudinal axis"),
        ("Mux", "Moment about x-axis; main vertical bending for typical girders"),
        ("Muy", "Moment about y-axis; lateral/minor bending for typical girders"),
        ("Vux", "Shear force in x-direction; lateral shear"),
        ("Vuy", "Shear force in y-direction; vertical shear"),
        ("Tu", "Torsion about the member longitudinal axis"),
    ]


def _render_axis_convention_card() -> None:
    """Display the section-axis basis before users enter Mux/Muy/Vux/Vuy loads."""

    st.markdown("##### Axis Convention")
    st.markdown(
        '<div class="cpmm-section-note">LOADS.WORKFLOW1A uses explicit x/y/z-axis action names. '
        "Confirm these axes against the live section preview before entering loads; major/minor labels are intentionally avoided.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_kv_panel_html(_axis_convention_rows(_analysis_mode_from_session_state())), unsafe_allow_html=True)


def _render_member_type_section_guidance(preset: dict[str, Any]) -> None:
    """Show non-invasive Section Builder guidance for the active member workflow."""
    settings = _analysis_mode_from_session_state()
    preset_key = str(preset.get("key", ""))
    is_girder_preset = "girder" in str(preset.get("category", "")).casefold() or "girder" in preset_key

    rows = [("Active member workflow", analysis_mode_label(settings))]
    if is_bridge_beam_girder_workflow(settings):
        family_label = _girder_section_family_label(preset)
        service_basis = _recommended_service_basis_for_preset(preset)
        rows.extend(
            [
                ("Design context", "Bridge Beam/Girder under AASHTO LRFD"),
                ("Selected girder family", family_label),
                ("Service-stage basis default", service_basis),
                ("Recommended section family", "Precast Composite Girder or General / Non-composite Girder presets"),
                ("Custom category", "Custom Girder section presets remain under this workflow"),
                ("Current geometry status", "Gross section polygon only; composite properties remain explicit metadata"),
                ("Girder design checks", "Stage-based SLS preview uses the selected family to guide service basis"),
                ("Current preset fit", "Good for Bridge Beam/Girder" if is_girder_preset else "Review: selected preset is not a girder preset"),
            ]
        )
        st.markdown("##### Member Workflow Guidance")
        st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)
        if not is_girder_preset:
            st.warning("Bridge Beam/Girder workflow is active, but the selected preset is not a dedicated girder preset. Use only with engineering judgment.")
        st.caption("WORKFLOW.TYPE3 routes shared geometry separately from design-code context. Bridge tools remain AASHTO LRFD / engineering-review previews until full engines are implemented.")
    elif is_building_beam_girder_workflow(settings):
        is_shared_precast = "building_beam_girder" in _preset_allowed_workflows(preset) and _is_parametric_i_girder(preset)
        rows.extend(
            [
                ("Design context", "Building Beam/Girder under ACI 318"),
                ("Geometry availability", "Workflow-specific metadata hides bridge/railway/highway-only presets"),
                ("Shared geometry preset", "Yes — Building-specific Precast I-Girder label" if is_shared_precast else "No"),
                ("Bridge-specific tools", "Hidden: bridge staged SLS, barrier/sidewalk/wearing surface, CSiBridge LL+IM"),
                ("Current preset fit", "Good for Building Beam/Girder" if (is_shared_precast or not is_girder_preset) else "Review: bridge-only girder preset"),
            ]
        )
        st.markdown("##### Member Workflow Guidance")
        st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)
        if is_shared_precast:
            st.info(
                "Precast I-Girder is shown with a Building-specific label for ACI 318 building work. "
                "Bridge load components, AASHTO effective-width helper, and staged bridge SLS tools are intentionally not active; prestressed girder layout/loss tools remain available as shared detailing workflow."
            )
        st.caption("WORKFLOW.TYPE3: same physical section geometry can be reused; design checks and load workflows remain workflow-specific.")
    elif is_portal_frame_crossbeam_workflow(settings):
        rows.extend(
            [
                ("Design context", "Portal frame prestressed crossbeam under ACI 318"),
                ("Geometry model", "Station-based solid/hollow crossbeam layout"),
                ("Tendon coordinate rule", "Depth from top surface is the user input; centroid eccentricity e(x) is calculated"),
                ("Prestress defaults", "7-wire low-relaxation strand, fpu 1860 MPa, Aps 140 mm²/strand, fpj default 0.75 fpu"),
                ("Current preset fit", "Good for Portal Frame Crossbeam" if _is_crossbeam_preset(preset) else "Review: selected preset is not a crossbeam preset"),
            ]
        )
        st.markdown("##### Member Workflow Guidance")
        st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)
        st.caption("CROSSBEAM.WF1 establishes layout and tendon profile source-of-truth only; SLS, ULS, prestress losses, anchorage zones, and D-region checks remain future guarded milestones.")
    else:
        rows.extend(
            [
                ("Primary analysis meaning", "Column / Pier / Wall / Pylon PMM"),
                ("PMM demand inputs", "Pu, Mux, Muy"),
                ("Custom category", "Custom PMM section presets remain under this workflow"),
                ("Concrete material used by PMM", "Primary / section concrete only"),
                ("Deck/topping material", "Ignored by PMM"),
            ]
        )
        st.markdown("##### Member Workflow Guidance")
        st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)

def _setup_span_length_mm_for_section_builder() -> float:
    """Return the Setup span length as the single source for girder span metadata."""

    system = system_settings_from_mapping(st.session_state.get(BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    span_m = float(system.span_length_m or DEFAULT_SPAN_LENGTH_M)
    if span_m <= 0.0:
        span_m = DEFAULT_SPAN_LENGTH_M
    return span_m * 1000.0


def _render_locked_setup_span_metadata(preset_key: str) -> float:
    """Show read-only girder span metadata sourced from Setup and mirror legacy keys."""

    span_mm = _setup_span_length_mm_for_section_builder()
    # Keep the legacy metadata key synchronized for effective-width helpers,
    # prestress previews, project save/load metadata, and old project files.
    st.session_state[f"{preset_key}_girder_length_mm"] = float(span_mm)
    st.session_state[f"{preset_key}_girder_length_mm_locked_from_setup"] = float(span_mm)
    st.number_input(
        "Girder length / span (mm)",
        min_value=1.0,
        max_value=1000000.0,
        value=float(span_mm),
        step=100.0,
        format="%.1f",
        disabled=True,
        key=f"{preset_key}_girder_length_mm_locked_from_setup",
        help="Read-only value from Setup → Span length L. Change the span in Setup, not in Section Builder.",
    )
    st.caption("Locked to Setup → 🟨 Span length L (m). Section Builder no longer owns girder span input.")
    return float(span_mm)


def _render_metadata_number_input(
    *,
    name: str,
    label: str,
    preset_key: str,
    default: float,
    min_value: float,
    max_value: float,
    step: float,
    help_text: str,
) -> float:
    """Render a metadata input that is intentionally not a geometry parameter."""

    min_float = float(min_value)
    max_float = float(max_value)
    widget_key = f"{preset_key}_{name}"
    default_value = _durable_number_default(
        name,
        preset_key,
        float(default),
        min_value=min_float,
        max_value=max_float,
    )
    st.session_state.setdefault(widget_key, default_value)
    return float(
        st.number_input(
            label,
            min_value=min_float,
            max_value=max_float,
            value=float(st.session_state.get(widget_key, default_value)),
            step=float(step),
            help=help_text,
            key=widget_key,
        )
    )



def _selectbox_with_safe_index(label: str, options: list[str], *, key: str, default: str, help_text: str | None = None) -> str:
    """Render a selectbox with stable key handling and no post-widget mutation."""

    index = options.index(default) if default in options else 0
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[index]
    index = options.index(str(st.session_state.get(key, options[index])))
    return str(st.selectbox(label, options, index=index, key=key, help=help_text))


def _effective_width_top_w(preset: dict[str, Any], params: dict[str, Any]) -> float:
    """Resolve the physical precast top contact width for Be helper metadata.

    This is deliberately auto-derived from the selected section geometry so the
    user does not have to guess a code-helper input.  The value is used only by
    the AASHTO.BE1 effective slab-width helper; it never changes the generated
    precast polygon.
    """

    if _is_parametric_i_girder(preset):
        return float(params.get("B1_mm", 0.0) or 0.0)
    if _is_precast_u_girder(preset):
        return float(params.get("top_" + "width" + "_mm", 0.0) or params.get("B1_mm", 0.0) or 0.0)
    if _is_precast_box_beam(preset):
        return float(params.get("width" + "_mm", 0.0) or params.get("B_mm", 0.0) or 0.0)
    if _is_parametric_plank_girder(preset):
        b = float(params.get("B_mm", 0.0) or 0.0)
        b1 = float(params.get("b1_mm", 0.0) or 0.0)
        if _is_interior_plank_girder_key(str(preset.get("key", ""))):
            return max(b - 2.0 * b1, 0.0)
        return max(b - b1, 0.0)
    return float(params.get("B_mm", 0.0) or 0.0)


def _effective_width_top_width_basis_note(preset: dict[str, Any]) -> str:
    """Return the engineering basis for the auto top-contact width."""

    if _is_parametric_i_girder(preset):
        return "Auto from I-Girder top flange width B1."
    if _is_precast_u_girder(preset):
        return "Auto from U-Girder top width."
    if _is_precast_box_beam(preset):
        return "Auto from Box Beam top slab width."
    if _is_parametric_plank_girder(preset):
        if _is_interior_plank_girder_key(str(preset.get("key", ""))):
            return "Auto from Interior Plank top width B - 2b1."
        return "Auto from Exterior Plank top contact width B - b1."
    return "Auto from selected section top width metadata."


def _precast_composite_girder_metadata_defaults(preset: dict[str, Any]) -> dict[str, float]:
    """Return UI-only default metadata for precast composite girder presets.

    These defaults seed Streamlit number inputs only; user-entered/session values
    still take precedence through stable widget keys. They do not change solver
    equations or effective-width formulas.
    """

    if _is_precast_box_beam(preset):
        return {"Tslab_mm": 200.0, "Be_mm": 1000.0, "girder_length_mm": 20000.0}
    return {"Tslab_mm": 200.0, "Be_mm": 1000.0, "girder_length_mm": 30000.0}


def _effective_width_default_spacing(preset: dict[str, Any], manual_be: float, auto_top_width: float) -> float:
    """Return the default girder spacing for the Be helper controls."""

    if _is_precast_box_beam(preset) or _is_parametric_plank_girder(preset):
        return 1000.0
    return max(manual_be, auto_top_width, 1.0)


def _effective_width_default_position(preset: dict[str, Any]) -> str:
    preset_key = str(preset.get("key", ""))
    if preset_key.endswith("_exterior"):
        return "exterior"
    return "interior"


def _render_effective_width_candidates(result: EffectiveWidthResult) -> None:
    rows = [("Effective width method", result.method), ("Governing limit", result.governing_limit)]
    rows.extend((candidate.label, f"{_format_float(candidate.value_mm, 1)} mm") for candidate in result.candidates)
    if result.warnings:
        rows.extend(("Review note", warning) for warning in result.warnings)
    st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)


def _render_effective_width_helper(preset: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Render AASHTO.BE1 effective slab-width controls and return metadata.

    The returned Be is used only for composite metadata/transformed-section
    display in the current milestone.  It does not modify PMM, prestress, rebar,
    load, or report calculations.
    """

    if not _is_composite_capable_preset(preset):
        return params

    preset_key = str(preset.get("key", "section"))
    manual_be = float(params.get("Be_mm", 0.0) or 0.0)
    tslab = float(params.get("Tslab_mm", 0.0) or 0.0)
    span = float(params.get("girder_length_mm", 0.0) or 0.0)
    auto_top_width = _effective_width_top_w(preset, params)
    top_width_basis = _effective_width_top_width_basis_note(preset)

    st.markdown("##### Effective Slab Width Helper")
    st.markdown(
        '<div class="cpmm-section-note">AASHTO.BE1 adds a transparent effective slab-width helper for composite metadata. '
        "Manual Be remains available; calculated Be is not used by PMM or prestress solvers. "
        "The precast top contact width b<sub>top</sub> is auto-calculated from the selected section geometry, "
        "with manual override available only under Advanced effective-width override.</div>",
        unsafe_allow_html=True,
    )

    mode_key = f"{preset_key}_Be_mode"
    mode = _selectbox_with_safe_index(
        "Be calculation mode",
        ["Manual", "AASHTO helper"],
        key=mode_key,
        default=_durable_choice_default("Be_mode", preset_key, str(st.session_state.get(mode_key, "Manual")), ["Manual", "AASHTO helper"]),
        help_text="Manual keeps the Be value entered above. AASHTO helper calculates a preliminary Be for composite metadata display.",
    )

    params["Be_mode"] = mode
    params["Be_manual_mm"] = manual_be
    params["Be_top_w_auto_mm"] = auto_top_width
    params["Be_top_w_mm"] = auto_top_width
    params["Be_top_w_source"] = "Auto from section geometry"

    if mode != "AASHTO helper":
        params["Be_effective_mm"] = manual_be
        params["Be_governing_limit"] = "Manual"
        st.markdown(
            _kv_panel_html(
                [
                    ("Be mode", "Manual"),
                    ("Manual Be", f"{_format_float(manual_be, 1)} mm"),
                    ("Auto precast top contact width b_top", f"{_format_float(auto_top_width, 1)} mm"),
                    ("b_top basis", top_width_basis),
                ]
            ),
            unsafe_allow_html=True,
        )
        return params

    position_default = _effective_width_default_position(preset)
    position_key = f"{preset_key}_Be_position"
    position_label = _selectbox_with_safe_index(
        "Girder position for Be helper",
        ["Interior", "Exterior"],
        key=position_key,
        default=_durable_choice_default("Be_position", preset_key, str(st.session_state.get(position_key, position_default.title())), ["Interior", "Exterior"]),
        help_text="Interior uses spacing on both sides. Exterior also uses deck overhang metadata.",
    )
    position = "exterior" if position_label == "Exterior" else "interior"

    default_spacing = _effective_width_default_spacing(preset, manual_be, auto_top_width)
    columns = st.columns(2)
    with columns[0]:
        spacing = _render_metadata_number_input(
            name="girder_spacing_mm",
            label="Girder spacing S (mm)",
            preset_key=preset_key,
            default=default_spacing,
            min_value=1.0,
            max_value=100000.0,
            step=10.0,
            help_text="Center-to-center spacing to adjacent girder. Used only by Be helper.",
        )
    with columns[1]:
        overhang = _render_metadata_number_input(
            name="deck_overhang_mm",
            label="Exterior deck overhang (mm)",
            preset_key=preset_key,
            default=500.0 if position == "exterior" else 0.0,
            min_value=0.0,
            max_value=100000.0,
            step=10.0,
            help_text="Deck width from exterior girder centerline/reference to free edge. Used only when position is Exterior.",
        )

    top_width_used = auto_top_width
    top_width_source = "Auto from section geometry"
    with st.expander("Advanced effective-width override", expanded=False):
        st.caption(
            "Precast top contact width b_top is normally calculated from the selected section geometry. "
            "Override it only when the design effective-width reference is intentionally different from the generated section."
        )
        st.markdown(
            _kv_panel_html(
                [
                    ("Auto b_top", f"{_format_float(auto_top_width, 1)} mm"),
                    ("Auto basis", top_width_basis),
                    ("Scope", "Used only by AASHTO.BE1 helper; does not change section geometry"),
                ]
            ),
            unsafe_allow_html=True,
        )
        top_width_source_key = f"{preset_key}_Be_top_width_source"
        top_width_source = _selectbox_with_safe_index(
            "Precast top contact width b_top source",
            ["Auto from section geometry", "Manual override"],
            key=top_width_source_key,
            default=_durable_choice_default(
                "Be_top_w_source",
                preset_key,
                str(st.session_state.get(top_width_source_key, "Auto from section geometry")),
                ["Auto from section geometry", "Manual override"],
            ),
            help_text="Keep Auto for normal use. Manual override is only for special effective-width assumptions.",
        )
        if top_width_source == "Manual override":
            top_width_used = _render_metadata_number_input(
                name="Be_top_contact_width_override_mm",
                label="Manual b_top override (mm)",
                preset_key=preset_key,
                default=max(auto_top_width, 1.0),
                min_value=1.0,
                max_value=100000.0,
                step=10.0,
                help_text="Manual physical top contact width used by Be helper only. It does not change the generated section polygon.",
            )
        else:
            top_width_used = auto_top_width

    params["Be_top_w_mm"] = top_width_used
    params["Be_top_w_source"] = top_width_source

    try:
        result = calculate_aashto_effective_slab_width(
            EffectiveWidthInput(
                span,
                tslab,
                spacing,
                top_width_used,
                position=position,
                deck_overhang_mm=overhang if position == "exterior" else 0.0,
            )
        )
    except ValueError as exc:
        st.warning(f"Effective slab width helper is paused: {exc}")
        params["Be_effective_mm"] = manual_be
        params["Be_governing_limit"] = "Manual fallback"
        return params

    calculated_be = getattr(result, "effective_" + "width" + "_mm")
    params["Be_mm"] = calculated_be
    params["Be_effective_mm"] = calculated_be
    params["Be_calculated_mm"] = calculated_be
    params["Be_governing_limit"] = result.governing_limit
    params["Be_position"] = result.position
    params["girder_spacing_mm"] = spacing
    params["deck_overhang_mm"] = overhang if position == "exterior" else 0.0
    st.markdown(_property_strip_html([
        SectionMetric("Calculated Be", f"{_format_float(calculated_be, 1)} mm", "Used for transformed composite metadata only", "ready", True),
        SectionMetric("Governing limit", result.governing_limit, "Review before design use", "info"),
        SectionMetric("b_top used", f"{_format_float(top_width_used, 1)} mm", top_width_source, "neutral"),
        SectionMetric("Manual Be kept", f"{_format_float(manual_be, 1)} mm", "Available by switching mode to Manual", "neutral"),
    ]), unsafe_allow_html=True)
    with st.expander("Effective slab width candidate limits", expanded=False):
        _render_effective_width_candidates(result)
    return params


def _render_precast_composite_girder_metadata_inputs(preset: dict[str, Any]) -> dict[str, float]:
    """Render explicit deck/topping metadata for precast composite girder presets.

    These values are not part of the precast girder polygon generator. They are
    stored in section_parameters only for display-only transformed composite
    properties and Beam/Girder SLS service-basis routing.
    """

    preset_key = str(preset.get("key", "precast_girder"))
    display_name = str(preset.get("display_name", "Precast girder"))
    st.markdown("##### Composite Deck / Topping Metadata")
    st.markdown(
        f'<div class="cpmm-section-note">{display_name} deck/topping metadata is explicit and display-only. '
        "It is not merged into the precast polygon and is not used by PMM, prestress, or report logic.</div>",
        unsafe_allow_html=True,
    )
    defaults = _precast_composite_girder_metadata_defaults(preset)
    columns = st.columns(2)
    with columns[0]:
        tslab = _render_metadata_number_input(
            name="Tslab_mm",
            label="Tslab Deck/topping thickness (mm)",
            preset_key=preset_key,
            default=defaults["Tslab_mm"],
            min_value=0.0,
            max_value=3000.0,
            step=5.0,
            help_text="Composite deck/topping thickness metadata. Not merged into the precast girder polygon.",
        )
        girder_length = _render_locked_setup_span_metadata(preset_key)
    with columns[1]:
        be = _render_metadata_number_input(
            name="Be_mm",
            label="Be Effective slab width (mm)",
            preset_key=preset_key,
            default=defaults["Be_mm"],
            min_value=1.0,
            max_value=50000.0,
            step=10.0,
            help_text="Manual effective width. AASHTO.BE1 helper can calculate Be below when selected.",
        )
    return {"Tslab_mm": tslab, "Be_mm": be, "girder_length_mm": girder_length}


def _render_composite_metadata_panel(params: dict[str, Any], composite_active: bool) -> None:
    """Show common calculated composite metadata for composite-capable girders."""

    tslab = float(params.get("Tslab_mm", 0.0))
    be = float(params.get("Be_mm", 0.0))
    ebeam = float(params.get("Ebeam_MPa", 0.0))
    edeck = float(params.get("Edeck_MPa", 0.0))
    n_ratio = edeck / ebeam if ebeam > 0 else 0.0
    st.markdown("##### Calculated Composite Metadata")
    st.markdown(
        _kv_panel_html(
            [
                ("Composite transformed properties", "Active" if composite_active else "Not active"),
                ("Tslab", f"{_format_float(tslab, 1)} mm"),
                ("Be", f"{_format_float(be, 1)} mm"),
                ("Ebeam", _format_ec(ebeam)),
                ("Edeck", _format_ec(edeck)),
                ("n = Edeck/Ebeam", _format_float(n_ratio, 3)),
                ("Btransformed = n x Be", f"{_format_float(n_ratio * be, 1)} mm"),
                ("Be mode", str(params.get("Be_mode", "Manual"))),
                ("Be governing limit", str(params.get("Be_governing_limit", "Manual"))),
            ]
        ),
        unsafe_allow_html=True,
    )


def _render_parametric_i_girder_dimension_qa(params: dict[str, Any]) -> None:
    """Show concise engineering-oriented checks for the parametric I-girder preset."""
    b1 = float(params.get("B1_mm", 0.0))
    b2 = float(params.get("B2_mm", 0.0))
    d1 = float(params.get("D1_mm", 0.0))
    d2 = float(params.get("D2_mm", 0.0))
    d3 = float(params.get("D3_mm", 0.0))
    d5 = float(params.get("D5_mm", 0.0))
    d6 = float(params.get("D6_mm", 0.0))
    t1 = float(params.get("T1_mm", 0.0))
    t2 = float(params.get("T2_mm", 0.0))
    c1 = float(params.get("C1_mm", 0.0))
    web_zone = d1 - d2 - d3 - d5 - d6

    checks = [
        SectionMetric("Depth stack", "OK" if web_zone > 0 else "Invalid", f"Web clear zone = {_format_float(web_zone, 1)} mm", "ready" if web_zone > 0 else "danger", True),
        SectionMetric("Top transition", "OK" if 0 < t1 <= min(b1, b2) else "Review", "T1 must connect within both flange widths", "ready" if 0 < t1 <= min(b1, b2) else "warning", True),
        SectionMetric("Bottom transition", "OK" if 0 < t2 <= min(b1, b2) else "Review", "T2 must connect within both flange widths", "ready" if 0 < t2 <= min(b1, b2) else "warning", True),
        SectionMetric("Chamfer", "None" if c1 == 0 else f"{_format_float(c1, 1)} mm", "C1 is used only at external bottom/top corners in this preset", "neutral" if c1 == 0 else "info"),
    ]

    st.markdown("##### I-Girder Dimension QA")
    st.markdown(
        '<div class="cpmm-section-note">Precast I-Girder is symmetric about the vertical centerline. '
        "Composite deck/topping metadata can be defined below for transformed-section display, but the generated polygon remains precast-only.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_property_strip_html(checks), unsafe_allow_html=True)
    with st.expander("I-Girder zone breakdown", expanded=False):
        st.markdown(
            _kv_panel_html(
                [
                    ("Top flange zone", f"B1 {_format_float(b1, 1)} mm × D2 {_format_float(d2, 1)} mm"),
                    ("Top haunch / taper", f"D3 {_format_float(d3, 1)} mm; taper from B1 to T1"),
                    ("Web clear zone", f"{_format_float(web_zone, 1)} mm between haunches"),
                    ("Web widths", f"T1 {_format_float(t1, 1)} mm / T2 {_format_float(t2, 1)} mm"),
                    ("Bottom haunch / taper", f"D6 {_format_float(d6, 1)} mm; taper from T2 to B2"),
                    ("Bottom flange zone", f"B2 {_format_float(b2, 1)} mm × D5 {_format_float(d5, 1)} mm"),
                ]
            ),
            unsafe_allow_html=True,
        )



def _render_parametric_plank_girder_dimension_qa(preset: dict[str, Any], params: dict[str, Any]) -> None:
    """Show concise QA and transformed-width metadata for plank girder presets."""
    b = float(params.get("B_mm", 0.0))
    b1 = float(params.get("b1_mm", 0.0))
    b2 = float(params.get("b2_mm", 0.0))
    b3 = float(params.get("b3_mm", 0.0))
    h = float(params.get("H_mm", 0.0))
    h1 = float(params.get("h1_mm", 0.0))
    h2 = float(params.get("h2_mm", 0.0))
    tslab = float(params.get("Tslab_mm", 0.0))
    be = float(params.get("Be_mm", 0.0))
    ebeam = float(params.get("Ebeam_MPa", 0.0))
    edeck = float(params.get("Edeck_MPa", 0.0))
    girder_length = float(params.get("girder_length_mm", 0.0))
    n_ratio = edeck / ebeam if ebeam > 0 else 0.0
    btransformed = n_ratio * be
    is_interior = _is_interior_plank_girder_key(str(preset.get("key", "")))
    width_rule = b - b3 - (2.0 * b2 if is_interior else b2)
    width_ok = abs(width_rule) <= max(2.0, 0.005 * max(b, 1.0))
    side_label = "Interior" if is_interior else "Exterior"

    checks = [
        SectionMetric("Plank type", side_label, "Precast-only polygon; deck slab retained as composite metadata", "info", True),
        SectionMetric("Width stack", "OK" if width_ok else "Review", f"B - b3 - {'2b2' if is_interior else 'b2'} = {_format_float(width_rule, 1)} mm", "ready" if width_ok else "warning", True),
        SectionMetric("Depth stack", "OK" if 0 <= h1 <= h2 < h else "Invalid", f"h1 {_format_float(h1, 1)} mm / h2 {_format_float(h2, 1)} mm / H {_format_float(h, 1)} mm", "ready" if 0 <= h1 <= h2 < h else "danger", True),
        SectionMetric("Composite mode", "Metadata only", "Tslab/Be/n are not merged into the precast polygon in this milestone", "info"),
        SectionMetric("n = Edeck/Ebeam", _format_float(n_ratio, 3), f"Edeck {_format_float(edeck, 0)} / Ebeam {_format_float(ebeam, 0)} MPa", "ready" if n_ratio > 0 else "danger"),
        SectionMetric("Btransformed", f"{_format_float(btransformed, 1)} mm", "Auto = n × Be", "ready" if btransformed > 0 else "danger"),
    ]

    st.markdown("##### Plank Girder Dimension / Composite QA")
    st.markdown(
        '<div class="cpmm-section-note">Precast Plank Girder is generated as a precast-only section. '
        "Be can be manual or calculated by the AASHTO.BE1 helper; n and Btransformed are calculated automatically for composite metadata.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_property_strip_html(checks), unsafe_allow_html=True)
    with st.expander("Plank geometry / transformed-width breakdown", expanded=False):
        st.markdown(
            _kv_panel_html(
                [
                    ("Precast geometry", f"B {_format_float(b, 1)} mm, b3 {_format_float(b3, 1)} mm, H {_format_float(h, 1)} mm"),
                    ("Side offsets", f"b1 {_format_float(b1, 1)} mm, b2 {_format_float(b2, 1)} mm"),
                    ("Side transition", f"h1 {_format_float(h1, 1)} mm, h2 {_format_float(h2, 1)} mm"),
                    ("Deck/topping metadata", f"Tslab {_format_float(tslab, 1)} mm"),
                    ("Effective width", f"Be {_format_float(be, 1)} mm ({params.get('Be_mode', 'Manual')})"),
                    ("Modular ratio", f"n = {_format_float(n_ratio, 4)}"),
                    ("Transformed width", f"Btransformed = {_format_float(btransformed, 1)} mm"),
                    ("Girder length", f"{_format_float(girder_length, 1)} mm"),
                ]
            ),
            unsafe_allow_html=True,
        )

def _inertia_display(value: str) -> str:
    return "Not calculated" if value == "TODO" else value


def _validation_label(result: ValidationResult) -> str:
    if result.errors:
        return "Error"
    if result.warnings:
        return "Warning"
    return "OK"


def _readiness_label(result: ValidationResult) -> str:
    if result.errors:
        return "Not Ready"
    if result.warnings:
        return "Warning"
    return "Ready"


def _render_validation_panel(result: ValidationResult) -> None:
    st.markdown(
        _status_panel_html(
            [
                SectionMetric("Validation", _validation_label(result), "", _validation_status(result), True),
                SectionMetric("Errors", f"{len(result.errors):,}", "", "danger" if result.errors else "neutral"),
                SectionMetric("Warnings", f"{len(result.warnings):,}", "", "warning" if result.warnings else "neutral"),
            ]
        ),
        unsafe_allow_html=True,
    )

    if result.errors:
        for error in result.errors:
            st.error(f"ERROR: {error}")

    if result.warnings:
        for warning in result.warnings:
            st.warning(f"WARNING: {warning}")

    if result.info and (result.errors or result.warnings):
        st.markdown(_message_list_html([f"INFO: {info}" for info in result.info]), unsafe_allow_html=True)


def _render_commercial_section_header() -> None:
    settings = _analysis_mode_from_session_state()
    st.markdown(
        f'''
        <div class="cpmm-section-page-hero">
          <div>
            <div class="cpmm-section-page-title">Section Builder</div>
            <div class="cpmm-section-page-subtitle">Definition workspace for the active section preset, geometry, material basis, and analysis-ready gross properties for the selected workflow.</div>
          </div>
          <div class="cpmm-section-page-mode">{escape(analysis_mode_label(settings))}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def _engineering_context_cards_html(
    *,
    workflow_label: str,
    preset_label: str | None = None,
    preset_family: str | None = None,
) -> str:
    """Render high-visibility master controls for Section Builder."""

    section_value = preset_label or "Select a Section Type / Preset"
    section_detail = preset_family or "Geometry basis and downstream SLS/ULS routes depend on this selection."
    return f"""
    <div class="cpmm-context-grid">
      <div class="cpmm-context-card workflow">
        <div class="cpmm-context-kicker">Active Member Workflow</div>
        <div class="cpmm-context-value">{escape(workflow_label)}</div>
        <div class="cpmm-context-detail">Master workflow for section filtering, design-code routing, loads, analysis, and report context.</div>
        <div class="cpmm-context-badges"><span class="cpmm-context-required">REQUIRED</span><span class="cpmm-context-chip">Primary Control</span></div>
      </div>
      <div class="cpmm-context-card section">
        <div class="cpmm-context-kicker">Section Type / Preset</div>
        <div class="cpmm-context-value">{escape(section_value)}</div>
        <div class="cpmm-context-detail">{escape(section_detail)}</div>
        <div class="cpmm-context-badges"><span class="cpmm-context-required">REQUIRED</span><span class="cpmm-context-chip">Geometry Basis</span></div>
      </div>
    </div>
    """


def _commercial_panel_title_html(title: str, kicker: str, *pills: str) -> str:
    pill_html = "".join(f'<span class="cpmm-commercial-pill">{escape(str(pill))}</span>' for pill in pills if str(pill))
    return (
        '<div class="cpmm-commercial-panel-title">'
        '<div>'
        f'<div class="cpmm-commercial-panel-kicker">{escape(kicker)}</div>'
        f'<div class="cpmm-commercial-panel-title-main">{escape(title)}</div>'
        '</div>'
        f'<div class="cpmm-commercial-mini-actions">{pill_html}</div>'
        '</div>'
    )


def _render_section_definition_panel(
    presets: list[dict[str, Any]],
    categories: list[str],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Render the compact top context panel and return the active preset/materials."""

    analysis_mode_settings = _analysis_mode_from_session_state()
    available_presets = _filter_presets_for_member_type(presets, analysis_mode_settings)
    available_categories = _categories_for_filtered_presets(categories, available_presets)

    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Section Definition", "Definition", "Preset", "Material", "System"),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="cpmm-commercial-section-step-title">
              <span class="cpmm-commercial-section-step-number">2</span>
              <span class="cpmm-commercial-section-step-heading">Section Type / Preset</span>
            </div>
            <div class="cpmm-commercial-section-step-note">Choose the concrete section type or preset. This master control defines geometry family, available dimensions, section basis, and downstream SLS/ULS workflow.</div>
            """,
            unsafe_allow_html=True,
        )

        preset_keys, preset_map, label_map = _preset_maps(available_presets, analysis_mode_settings)
        if not preset_keys:
            st.error("No section presets are available.")
            return None

        selector_state_key = "section_preset_selector_key"
        selector_initial_key = _initial_preset_selector_key(preset_keys)
        if st.session_state.get(selector_state_key) not in preset_keys:
            st.session_state[selector_state_key] = selector_initial_key

        current_preset_key = str(st.session_state.get(selector_state_key, selector_initial_key))
        current_preset = preset_map.get(current_preset_key, preset_map[str(selector_initial_key)])
        current_category = str(current_preset.get("category", "General"))
        st.markdown(
            _engineering_context_cards_html(
                workflow_label=analysis_mode_label(analysis_mode_settings),
                preset_label=_workflow_specific_preset_display_name(current_preset, analysis_mode_settings),
                preset_family=f"Geometry family: {current_category}",
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            f"Workflow filter: {_member_type_filter_description(analysis_mode_settings)}"
        )

        with st.container(border=True):
            st.markdown(
                f'''
                <div class="cpmm-commercial-control-section">
                  <div class="cpmm-commercial-section-icon">SEC</div>
                  <div class="cpmm-commercial-section-copy">
                    <div class="cpmm-commercial-section-kicker">Section Type / Preset</div>
                    <div class="cpmm-commercial-section-value">{escape(_workflow_specific_preset_display_name(current_preset, analysis_mode_settings))}</div>
                    <div class="cpmm-commercial-section-detail">Master control for geometry family, available dimensions, section basis, and downstream SLS/ULS workflow.</div>
                  </div>
                  <div class="cpmm-commercial-section-badge">REQUIRED</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )
            if is_portal_frame_crossbeam_workflow(analysis_mode_settings):
                selected_preset_key = current_preset_key
                st.markdown(
                    f"**Preset family:** {_workflow_specific_preset_display_name(current_preset, analysis_mode_settings)}"
                )
                st.caption(
                    "Controlled by the selected Crossbeam Project Section above. "
                    "Create a New Solid/New Hollow section instead of changing topology in place."
                )
            else:
                selected_preset_key = st.selectbox(
                    "Change Section Type / Preset",
                    preset_keys,
                    index=preset_keys.index(selector_initial_key),
                    format_func=lambda key: label_map.get(str(key), str(key)),
                    key=selector_state_key,
                    help=(
                        "Select the actual section geometry directly. The geometry family/category is shown "
                        "after the dot for reference only."
                    ),
                    label_visibility="visible",
                )
        preset = preset_map[str(selected_preset_key)]
        selected_category = str(preset.get("category", "General"))

        # Sync the selected preset key immediately, before geometry generation.
        # This prevents the direct Section Type / Preset selector from snapping
        # back to the previous preset and requiring a second click on rerun.
        st.session_state["section_preset_key"] = str(selected_preset_key)
        st.session_state["section_preset_name"] = _workflow_specific_preset_display_name(preset, analysis_mode_settings)

        st.caption(
            f"Geometry family: {selected_category} · "
            "Geometry inputs are edited in the definition workspace below."
        )

        with st.container(border=True):
            _render_reinforcement_prestress_system_panel(preset)

        with st.container(border=True):
            material_assignment = _render_concrete_material_assignment(preset)

        _render_section_assembly_panel(preset)

        _render_section_builder_status_strip(preset, material_assignment)

    return preset, material_assignment


def _render_geometry_parameters_workspace(
    preset: dict[str, Any],
    material_assignment: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Render the main geometry input workspace shown beside the live preview."""

    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Geometry Parameters", "Input", "Dimensions", "Live"),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Primary section dimensions are kept at the same level as the live preview. '
            'Reinforcement and section-specific material/assembly controls are shown in the definition panel above.</div>',
            unsafe_allow_html=True,
        )

        label_mode_label = st.selectbox("Dimension labels", ["Symbol + Value", "Symbol only", "Value only"], index=0)
        label_mode = {"Symbol + Value": "symbol_value", "Symbol only": "symbol", "Value only": "value"}[label_mode_label]

        params: dict[str, Any] = {}
        _sync_rectangular_chamfered_legacy_widget_defaults(preset)
        hidden_material_parameters = _hidden_material_parameter_names(preset)
        visible_parameters = [
            parameter for parameter in preset["parameters"] if parameter["name"] not in hidden_material_parameters
        ]
        parameter_columns = st.columns(2)
        for index, parameter in enumerate(visible_parameters):
            with parameter_columns[index % len(parameter_columns)]:
                if parameter.get("type", "number") == "number":
                    params[parameter["name"]] = _number_input(parameter, preset["key"])
                else:
                    st.warning(f"Unsupported parameter type: {parameter.get('type')}")

        if _composite_metadata_enabled_for_workflow(preset):
            params["Ebeam_MPa"] = float(material_assignment["Ebeam_MPa"])
            params["Edeck_MPa"] = float(material_assignment.get("Edeck_MPa", material_assignment["Ebeam_MPa"]))
            if _is_parametric_i_girder(preset) or _is_precast_u_girder(preset) or _is_precast_box_beam(preset):
                params.update(_render_precast_composite_girder_metadata_inputs(preset))

            if _aashto_effective_width_helper_enabled(preset):
                params = _render_effective_width_helper(preset, params)
            else:
                params["Be_mode"] = "Manual"
                params["Be_manual_mm"] = float(params.get("Be_mm", 0.0) or 0.0)
                params["Be_effective_mm"] = float(params.get("Be_mm", 0.0) or 0.0)
                params["Be_governing_limit"] = "Manual / ACI building context"
                st.markdown(
                    '<div class="cpmm-section-note">Building Beam/Girder uses shared precast I-Girder composite metadata under ACI 318. '
                    "AASHTO effective-width helper and bridge staged SLS/load workflows remain hidden; enter the slab/effective width appropriate for the building design basis.</div>",
                    unsafe_allow_html=True,
                )

            composite_key = f"{preset['key']}_composite_enabled"
            composite_default = _durable_bool_default(
                "composite_enabled",
                str(preset["key"]),
                bool(st.session_state.get(composite_key, True)),
            )
            st.session_state.setdefault(composite_key, composite_default)
            params["composite_enabled"] = bool(
                st.checkbox(
                    "Enable composite deck/topping transformed properties",
                    value=bool(st.session_state.get(composite_key, composite_default)),
                    help=(
                        "When enabled, Section Builder calculates transformed composite properties "
                        "from Tslab, Be, Ebeam, and Edeck. The result remains separate from gross "
                        "section properties and is not used by PMM in this milestone."
                    ),
                    key=composite_key,
                )
            )
            composite_active = composite_deck_is_active(
                params,
                member_type=_analysis_mode_from_session_state().member_type,
            )
            _render_composite_metadata_panel(params, composite_active)
        elif _is_composite_capable_preset(preset) and is_building_beam_girder_workflow(_analysis_mode_from_session_state()):
            st.info(
                "Shared precast girder geometry is active under the Building Beam/Girder ACI workflow. "
                "Bridge staged SLS inputs remain hidden for this workflow."
            )

        if _is_parametric_i_girder(preset):
            _render_parametric_i_girder_dimension_qa(params)
        if _is_parametric_plank_girder(preset):
            _render_parametric_plank_girder_dimension_qa(preset, params)

        return label_mode, params


def _render_crossbeam_member_geometry_workspace(
    settings: AnalysisModeSettings,
) -> None:
    """Render the Crossbeam member-level length source above section inputs."""

    if not is_portal_frame_crossbeam_workflow(settings):
        return

    # Local import keeps the generic Section Builder module independent from
    # Crossbeam page initialization for every other member workflow.
    from concrete_pmm_pro.ui.crossbeam_pages import (
        render_crossbeam_member_length_control,
    )

    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html(
                "Crossbeam Member Geometry",
                "Member Input",
                "Length",
                "Source of Truth",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-note">Crossbeam length L belongs to the complete member and is shared by Segment Layout, Tendon Profile, and Rebar Zone stationing. Section dimensions below remain owned by the selected Section ID.</div>',
            unsafe_allow_html=True,
        )
        render_crossbeam_member_length_control()


def _render_crossbeam_construction_support_workspace(settings: AnalysisModeSettings) -> None:
    """Render member-level construction/support source in Section Builder only."""

    if not is_portal_frame_crossbeam_workflow(settings):
        return
    from concrete_pmm_pro.ui.crossbeam_pages import (
        CB_LENGTH_KEY,
        render_crossbeam_construction_support_source_workspace,
    )

    length_m = float(st.session_state.get(CB_LENGTH_KEY, 20.0) or 20.0)
    render_crossbeam_construction_support_source_workspace(length_m)


def _build_geometry(
    preset: dict[str, Any],
    params: dict[str, Any],
) -> tuple[Any | None, list[Any], ValidationResult]:
    generator_name = preset["generator"]
    if generator_name == "rectangular_chamfered" and "chamfer_mm" in params:
        params = {
            **params,
            "chamfer_x_mm": params.get("chamfer_x_mm", params["chamfer_mm"]),
            "chamfer_y_mm": params.get("chamfer_y_mm", params["chamfer_mm"]),
        }
    generator_params = {name: params[name] for name in _geometry_parameter_names(preset) if name in params}
    try:
        geometry = default_registry.geometry(generator_name)(**generator_params, name=preset["display_name"])
        dimensions = default_registry.dimensions(preset["dimensions_generator"])(**generator_params)
    except ValueError as exc:
        return None, [], ValidationResult(
            is_valid=False,
            errors=[str(exc)],
            info=["Preview is paused until geometry inputs are valid."],
        )

    validation = validate_section_geometry(geometry)
    return geometry, dimensions, validation


def _store_valid_section_state(preset: dict[str, Any], params: dict[str, Any], geometry: Any, dimensions: list[Any]) -> None:
    st.session_state["section_preset_key"] = preset["key"]
    st.session_state["section_preset_name"] = _workflow_specific_preset_display_name(preset, _analysis_mode_from_session_state())
    st.session_state["section_category"] = str(preset.get("category", ""))
    st.session_state["girder_section_family"] = _girder_section_family(preset)
    st.session_state["girder_service_default_basis"] = _recommended_service_basis_for_preset(preset)
    # Do not write to Streamlit widget-owned reinforcement flag keys here.
    # The checkboxes in _render_reinforcement_prestress_system_panel already
    # initialize and own ORDINARY_REBAR_FLAG_KEY / PRESTRESSING_STEEL_FLAG_KEY.
    # Assigning those keys after widget creation raises StreamlitAPIException.
    if ORDINARY_REBAR_FLAG_KEY not in st.session_state or PRESTRESSING_STEEL_FLAG_KEY not in st.session_state:
        default_rebar, default_prestress = _default_reinforcement_flags_for_preset(preset)
        st.session_state.setdefault(ORDINARY_REBAR_FLAG_KEY, default_rebar)
        st.session_state.setdefault(PRESTRESSING_STEEL_FLAG_KEY, default_prestress)
    st.session_state["section_parameters"] = params
    st.session_state[SECTION_PARAMETERS_PRESET_KEY] = str(preset["key"])
    st.session_state["section_geometry"] = geometry
    st.session_state["section_dimensions"] = dimensions


def _clear_section_geometry_state() -> None:
    st.session_state["section_geometry"] = None
    st.session_state["section_dimensions"] = []


def _geometry_status_rows(
    geometry: Any | None,
    dimensions: list[Any],
    validation: ValidationResult,
) -> list[tuple[str, str]]:
    geometry_ready = geometry is not None and validation.is_valid
    return [
        ("Geometry", "Ready" if geometry_ready else "Not Ready"),
        ("Preview", "Geometry only" if geometry_ready else "Not Available"),
        ("Validation", _validation_label(validation)),
        ("Dimension guides", f"{len(dimensions):,}"),
        ("Rebar/prestress display", "Hidden in Section Builder"),
    ]


def _render_section_preview_panel(
    geometry: Any | None,
    dimensions: list[Any],
    label_mode: str,
    validation: ValidationResult,
) -> None:
    # Section Builder is intentionally a geometry/section-definition workspace.
    # Rebar and prestressing steel are edited and previewed on their own pages.
    # Keeping this preview geometry-only avoids confusing stale reinforcement
    # layouts with the active section definition while still preserving stored
    # rebar/prestress data for analysis when enabled by section flags.
    preview_rebars: list[Any] = []
    preview_prestress_elements: list[Any] = []

    with st.container(border=True):
        st.markdown(
            _commercial_panel_title_html("Live Section Preview", "Canvas", "Geometry only"),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-commercial-preview-note">Preview canvas shows the active concrete polygon and dimension guides. Rebar and prestress graphics remain controlled on their own pages.</div>',
            unsafe_allow_html=True,
        )
        if geometry is not None and validation.is_valid:
            preview_figure = create_section_preview(
                geometry,
                dimensions,
                label_mode,
                preview_rebars,
                preview_prestress_elements,
            )
            preview_figure.update_layout(height=430, margin=dict(l=10, r=10, t=28, b=6))
            st.plotly_chart(
                preview_figure,
                use_container_width=True,
                key="section_builder_preview",
            )
        else:
            st.info("Preview is paused until geometry inputs are valid.")

        st.markdown(
            '<div class="cpmm-section-builder-compact-note">Section Builder preview is locked to geometry only. Rebar and prestress graphics are controlled on their own pages.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cpmm-section-preview-status-compact">'
            + _property_strip_html(
                [
                    SectionMetric("Geometry", "Ready" if geometry is not None and validation.is_valid else "Not Ready", "active concrete polygon", "ready" if geometry is not None and validation.is_valid else "danger", True),
                    SectionMetric("Validation", _validation_label(validation), f"{len(validation.errors):,} errors / {len(validation.warnings):,} warnings", _validation_status(validation), True),
                    SectionMetric("Dimensions", f"{len(dimensions):,}", "visible dimension guides", "neutral"),
                    SectionMetric("Steel preview", "Hidden", "Rebar/Prestress pages own steel graphics", "info"),
                ]
            )
            + '</div>',
            unsafe_allow_html=True,
        )
        if validation.errors or validation.warnings or validation.info:
            with st.expander("Preview validation details", expanded=bool(validation.errors)):
                _render_validation_panel(validation)


def _parameter_rows(preset: dict[str, Any], params: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for parameter in preset["parameters"]:
        name = parameter["name"]
        label = parameter.get("label", name)
        if name in params:
            rows.append((label, _format_parameter_value(params[name])))
    return rows


def _render_composite_transformed_properties_summary(
    preset: dict[str, Any],
    params: dict[str, Any],
    geometry: Any | None,
    validation: ValidationResult,
) -> None:
    """Display transformed composite properties without changing gross/PMM properties."""

    settings = _analysis_mode_from_session_state()
    if not _composite_metadata_enabled_for_workflow(preset, settings):
        return

    st.subheader("Composite Transformed Section Properties")
    st.markdown(
        '<div class="cpmm-section-note">Transformed composite properties are calculated on the primary/precast concrete basis. '
        "The deck/topping rectangle is transformed by n = Edeck/Ebeam and placed above the precast top fiber. "
        "These values remain separate from PMM and from the Precast Gross Section Properties.</div>",
        unsafe_allow_html=True,
    )

    if geometry is None or not validation.is_valid:
        st.info("Composite transformed properties are paused until the precast geometry is valid.")
        return

    deck = composite_deck_input_from_parameters(params, member_type=settings.member_type)
    if not deck.enabled:
        st.info(
            "Composite deck/topping not active. Enable composite deck/topping and provide positive "
            "Tslab, Be, Ebeam, and Edeck values to calculate transformed composite properties."
        )
        return

    try:
        composite = calculate_composite_transformed_section_from_geometry(geometry, deck)
    except ValueError as exc:
        st.warning(f"Composite transformed properties could not be calculated: {exc}")
        return

    st.markdown(
        _property_strip_html(
            [
                SectionMetric("Composite Area", f"{composite.area_mm2:,.1f} mm^2", "precast + transformed deck area"),
                SectionMetric("Centroid yb", _format_optional_mm(composite.centroid_y_from_bottom_mm, 2), "from precast bottom fiber"),
                SectionMetric("Ix,tr", f"{composite.ix_mm4:,.3e} mm^4", "about transformed composite centroid"),
                SectionMetric("Iy,tr", f"{composite.iy_mm4:,.3e} mm^4", "about transformed composite centroid"),
                SectionMetric(
                    "Fiber distances",
                    f"ctop {_format_optional_mm(composite.c_top_mm, 1)} / cbottom {_format_optional_mm(composite.c_bottom_mm, 1)}",
                    "top fiber includes deck/topping; bottom fiber remains precast bottom",
                ),
                SectionMetric(
                    "Z top / bottom",
                    f"{composite.z_top_mm3:,.3e} / {composite.z_bottom_mm3:,.3e} mm^3"
                    if composite.z_top_mm3 and composite.z_bottom_mm3
                    else "N/A",
                    "transformed section modulus",
                ),
                SectionMetric("n = Edeck/Ebeam", _format_float(composite.modular_ratio, 4), "deck transformed to primary concrete basis", "info"),
                SectionMetric("Btransformed", f"{_format_float(getattr(composite, 'transformed_' + 'width' + '_mm'), 1)} mm", "n x Be", "info"),
                SectionMetric("Composite scope", "Display only", "not used by PMM/SLS solver yet", "info", True),
            ]
        ),
        unsafe_allow_html=True,
    )

    with st.expander("Composite transformed-section breakdown", expanded=False):
        st.markdown(
            _kv_panel_html(
                [
                    ("Basis", "Deck/topping transformed to primary/precast concrete"),
                    ("Precast area", f"{composite.precast_area_mm2:,.1f} mm^2"),
                    ("Precast centroid y", _format_optional_mm(composite.precast_centroid_y_mm, 2)),
                    ("Deck transformed area", f"{composite.deck_area_transformed_mm2:,.1f} mm^2"),
                    ("Deck centroid y", _format_optional_mm(composite.deck_centroid_y_mm, 2)),
                    ("Top fiber y", _format_optional_mm(composite.top_fiber_y_mm, 2)),
                    ("Bottom fiber y", _format_optional_mm(composite.bottom_fiber_y_mm, 2)),
                    ("Warning count", f"{len(composite.warnings):,}"),
                ]
            ),
            unsafe_allow_html=True,
        )
    if composite.warnings:
        st.markdown(_message_list_html([f"COMPOSITE WARNING: {warning}" for warning in composite.warnings]), unsafe_allow_html=True)


def _render_section_properties_summary(
    preset: dict[str, Any],
    params: dict[str, Any],
    geometry: Any | None,
    validation: ValidationResult,
) -> None:
    st.markdown(
        _commercial_panel_title_html("Precast Gross Section Properties", "Properties", "Gross", "Concrete polygon"),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cpmm-section-note">A, centroid, Ix, Iy, fiber distances, and section modulus shown here are based on the '
        'generated gross concrete polygon only. Composite slab/topping properties are metadata at this stage and are not included '
        'in the section properties below.</div>',
        unsafe_allow_html=True,
    )

    if geometry is None or not validation.is_valid:
        st.markdown(
            _property_strip_html(
                [
                    SectionMetric("Gross Area", "N/A", "Gross concrete polygon only"),
                    SectionMetric("Centroid", "N/A", "yb is measured upward from bottom fiber"),
                    SectionMetric("Ix", "Not calculated"),
                    SectionMetric("Iy", "Not calculated"),
                    SectionMetric("Holes / Voids", "N/A"),
                    SectionMetric("Active Preset", _workflow_specific_preset_display_name(preset, _analysis_mode_from_session_state()), "", "info"),
                    SectionMetric("Category", str(preset.get("category", "N/A")), "", "neutral"),
                    SectionMetric("Readiness", "Not Ready", "", "danger", True),
                ]
            ),
            unsafe_allow_html=True,
        )
        if rows := _parameter_rows(preset, params):
            st.markdown(_kv_panel_html(rows), unsafe_allow_html=True)
        return

    summary = summarize_geometry(geometry)
    c_top = summary.top_fiber_distance_mm
    c_bottom = summary.bottom_fiber_distance_mm
    yb = summary.centroid_y_from_bottom_mm
    y_mid_offset = summary.centroid_y_offset_from_mid_depth_mm
    x_mid_offset = getattr(summary, "centroid_x_offset_from_mid_" + "width" + "_mm")
    composite_detail = (
        "Tslab/Be/n/Btransformed excluded from gross A/I/Z"
        if _is_composite_capable_preset(preset)
        else "Concrete polygon only; no transformed deck/slab included"
    )

    settings = _analysis_mode_from_session_state()
    workflow_metrics: list[SectionMetric]
    if is_portal_frame_crossbeam_workflow(settings):
        workflow_metrics = [
            SectionMetric("ULS PMM", "Not active", "Crossbeam station-based ULS remains future guarded scope", "neutral"),
            SectionMetric("Crossbeam station model", "Layout foundation", "Segment assignment is defined separately from the section library", "info"),
        ]
    else:
        workflow_metrics = [
            SectionMetric("ULS PMM", "Supported", "Current section-analysis workflow", "ready"),
            SectionMetric(
                "Beam/Girder",
                "Planned" if _is_composite_capable_preset(preset) else "N/A",
                "Future station assignment",
                "info" if _is_composite_capable_preset(preset) else "neutral",
            ),
        ]

    st.markdown(
        _property_strip_html(
            [
                SectionMetric("Gross Area", f"{summary.area_mm2:,.1f} mm^2", "Precast/gross concrete polygon only"),
                SectionMetric(
                    "Centroid x",
                    _format_optional_mm(summary.centroid_x_mm, 2),
                    f"offset from mid-width = {_signed_mm(x_mid_offset, 2)}",
                ),
                SectionMetric(
                    "Centroid yb",
                    _format_optional_mm(yb, 2),
                    f"from bottom fiber; mid-depth offset = {_signed_mm(y_mid_offset, 2)}",
                ),
                SectionMetric("Ix", _inertia_display(summary.ix_display), "about centroidal x-axis"),
                SectionMetric("Iy", _inertia_display(summary.iy_display), "about centroidal y-axis"),
                SectionMetric(
                    "Fiber distances",
                    f"ctop {_format_optional_mm(c_top, 1)} / cbottom {_format_optional_mm(c_bottom, 1)}",
                    "Used directly for S = I / c stress checks",
                ),
                SectionMetric("Z top / bottom", f"{summary.z_top_display} / {summary.z_bottom_display}", "gross section modulus"),
                SectionMetric("Composite slab", "Excluded", composite_detail, "info"),
                SectionMetric("Holes / Voids", f"{len(geometry.holes):,}"),
                SectionMetric("Active Preset", _workflow_specific_preset_display_name(preset, settings)),
                SectionMetric("Category", str(preset.get("category", "N/A"))),
                *workflow_metrics,
                SectionMetric("Readiness", _readiness_label(validation), "", _validation_status(validation), True),
            ]
        ),
        unsafe_allow_html=True,
    )

    with st.expander("Section property convention", expanded=False):
        st.markdown(
            _kv_panel_html(
                [
                    ("Property basis", "Gross concrete / precast polygon only"),
                    ("Composite status", "Tslab, Be, n, and Btransformed are not merged into A, centroid, Ix, Iy, or Z"),
                    ("Coordinate y", "Positive upward in generated section coordinates"),
                    ("Centroid yb", f"{_format_optional_mm(yb, 2)} measured from bottom fiber"),
                    ("Mid-depth offset", _signed_mm(y_mid_offset, 2)),
                    ("Top fiber distance ctop", _format_optional_mm(c_top, 2)),
                    ("Bottom fiber distance cbottom", _format_optional_mm(c_bottom, 2)),
                    ("Section modulus", "Ztop = Ix / ctop; Zbottom = Ix / cbottom"),
                ]
            ),
            unsafe_allow_html=True,
        )

    if summary.warnings:
        st.markdown(_message_list_html([f"PROPERTY WARNING: {warning}" for warning in summary.warnings]), unsafe_allow_html=True)

    _render_composite_transformed_properties_summary(preset, params, geometry, validation)

    with st.expander("Geometry Inputs", expanded=False):
        st.markdown(
            _kv_panel_html(
                [
                    *_parameter_rows(preset, params),
                    ("Parameter count", f"{len(params):,}"),
                    ("Outer vertices", f"{len(geometry.outer_polygon):,}"),
                    ("Validation errors", f"{len(validation.errors):,}"),
                    ("Validation warnings", f"{len(validation.warnings):,}"),
                ]
            ),
            unsafe_allow_html=True,
        )




def render_section_builder() -> None:
    _ensure_section_parameter_owner_from_session()
    settings = _analysis_mode_from_session_state()
    prepare_crossbeam_section_library_for_builder(settings)
    st.markdown(_SECTION_BUILDER_CSS, unsafe_allow_html=True)
    _render_commercial_section_header()

    presets = load_section_presets()
    categories = load_section_categories()

    render_crossbeam_section_library_panel(settings)
    selection = _render_section_definition_panel(presets, categories)

    if selection is None:
        return

    preset, material_assignment = selection

    crossbeam_workflow = is_portal_frame_crossbeam_workflow(settings)
    if crossbeam_workflow:
        # Member-level sources belong together and must appear before the
        # selected Section-ID geometry so users do not mistake support data for
        # section-specific properties.
        _render_crossbeam_member_geometry_workspace(settings)
        _render_crossbeam_construction_support_workspace(settings)

    parameter_col, preview_col = st.columns([0.47, 0.53], gap="medium")
    with parameter_col:
        if not crossbeam_workflow:
            _render_crossbeam_member_geometry_workspace(settings)
        label_mode, params = _render_geometry_parameters_workspace(preset, material_assignment)

    geometry, dimensions, validation = _build_geometry(preset, params)

    if geometry is not None and validation.is_valid:
        _store_valid_section_state(preset, params, geometry, dimensions)
        sync_crossbeam_section_library_after_builder(
            settings,
            preset=preset,
            params=params,
            material_assignment=material_assignment,
        )
    else:
        _clear_section_geometry_state()

    with parameter_col:
        _render_section_properties_summary(preset, params, geometry, validation)

    with preview_col:
        _render_section_preview_panel(geometry, dimensions, label_mode, validation)

    if geometry is not None:
        with st.expander("Generated SectionGeometry"):
            st.json(geometry.model_dump())

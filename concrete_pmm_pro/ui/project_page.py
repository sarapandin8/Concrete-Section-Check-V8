"""Project save/load page."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import streamlit as st

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.design_code import (
    PROJECT_DESIGN_CODE_OPTIONS,
    PROJECT_CODE_EDITION_STATE_KEY,
    PROJECT_DESIGN_CODE_STATE_KEY,
    allowed_project_design_codes_for_workflow,
    code_edition_options_for,
    default_code_edition_for,
    default_project_design_code_for_workflow,
    normalize_project_code_edition,
    normalize_project_design_code,
    project_code_capability_cards,
    project_code_edition_from_session,
    project_design_code_from_session,
    sync_project_design_code_to_session,
    workflow_code_policy_message,
)
from concrete_pmm_pro.core.analysis_modes import analysis_mode_description, analysis_mode_label, analysis_mode_warnings
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.state.dirty_state import current_project_dirty_status, update_dirty_state_from_session
from concrete_pmm_pro.io.project_io import (
    ProjectIOError,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.reporting import build_result_traceability_snapshot, check_report_readiness


@dataclass(frozen=True)
class DashboardCard:
    title: str
    value: str
    detail: str = ""
    status: str = "info"
    strong: bool = False


_PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY = "_project_design_code_widget_sync"
_PROJECT_CODE_EDITION_WIDGET_SYNC_KEY = "_project_code_edition_widget_sync"


_DASHBOARD_CSS = """
<style>

.cpmm-setup-page-hero {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  border: 1px solid rgba(23, 92, 211, 0.18);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.92), #ffffff 62%);
  padding: 0.95rem 1.1rem;
  margin: 0.35rem 0 1.0rem 0;
  box-shadow: 0 9px 28px rgba(16, 24, 40, 0.07);
}
.cpmm-setup-page-icon {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #175cd3, #2f80ed);
  color: #ffffff;
  font-size: 1.35rem;
  font-weight: 950;
  box-shadow: 0 8px 20px rgba(23, 92, 211, 0.24);
}
.cpmm-setup-page-title {
  color: #092454;
  font-size: 1.24rem;
  font-weight: 900;
  line-height: 1.15;
  margin: 0.05rem 0 0.2rem 0;
}
.cpmm-setup-page-subtitle {
  color: #475467;
  font-size: 0.88rem;
  line-height: 1.35;
}
.cpmm-commercial-step-title {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0.25rem 0 0.18rem 0;
}
.cpmm-commercial-step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #175cd3, #2f80ed);
  font-weight: 950;
  box-shadow: 0 5px 14px rgba(23, 92, 211, 0.22);
}
.cpmm-commercial-step-heading {
  color: #101828;
  font-size: 1.05rem;
  font-weight: 900;
}
.cpmm-commercial-step-note {
  color: #475467;
  font-size: 0.84rem;
  line-height: 1.35;
  margin: 0 0 0.72rem 2.3rem;
}

.cpmm-workflow-hero {
  position: relative;
  border: 2px solid #7ab7ff;
  border-left: 9px solid #175cd3;
  border-radius: 16px;
  background:
    radial-gradient(circle at 18px 18px, rgba(23, 92, 211, 0.12), transparent 28px),
    linear-gradient(135deg, #eff7ff 0%, #ffffff 52%, #eaf3ff 100%);
  padding: 1.05rem 1.15rem 1.0rem 1.15rem;
  margin: 0.50rem 0 0.86rem 0;
  box-shadow: 0 8px 24px rgba(23, 92, 211, 0.14), 0 0 0 3px rgba(23, 92, 211, 0.05);
}
.cpmm-workflow-hero-kicker {
  color: #1849a9;
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0.075em;
  text-transform: uppercase;
  margin-bottom: 0.34rem;
}
.cpmm-workflow-hero-value {
  color: #0b2f6b;
  font-size: 1.26rem;
  font-weight: 850;
  line-height: 1.18;
  padding-right: 6.7rem;
}
.cpmm-workflow-hero-detail {
  color: #667085;
  font-size: 0.8rem;
  line-height: 1.3;
  margin-top: 0.3rem;
}
.cpmm-workflow-hero-badge {
  position: absolute;
  right: 1.0rem;
  top: 0.95rem;
  display: inline-block;
  border-radius: 999px;
  padding: 0.20rem 0.68rem;
  font-size: 0.70rem;
  font-weight: 900;
  letter-spacing: 0.055em;
  background: #175cd3;
  color: #ffffff;
  box-shadow: 0 3px 10px rgba(23, 92, 211, 0.22);
}

.cpmm-master-control-banner {
  border: 1px solid #93c5fd;
  border-left: 7px solid #175cd3;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 58%, #eaf3ff 100%);
  padding: 0.72rem 0.86rem;
  margin: 0.28rem 0 0.54rem 0;
  box-shadow: 0 5px 16px rgba(23, 92, 211, 0.12), 0 0 0 2px rgba(23, 92, 211, 0.04);
}
.cpmm-master-control-title {
  color: #1849a9;
  font-size: 0.76rem;
  font-weight: 900;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 0.18rem;
}
.cpmm-master-control-text {
  color: #344054;
  font-size: 0.82rem;
  line-height: 1.32;
}
.cpmm-master-control-chip {
  display: inline-block;
  border-radius: 999px;
  padding: 0.12rem 0.52rem;
  margin-left: 0.42rem;
  background: #175cd3;
  color: #ffffff;
  font-size: 0.66rem;
  font-weight: 900;
  letter-spacing: 0.055em;
}


/* UI.COMMERCIAL1: commercial master-control container styling.
   These rules target only Streamlit border containers that include the marker
   elements below, so regular containers and solver output widgets remain unchanged. */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) {
  border: 2px solid #1d6fe7 !important;
  border-radius: 20px !important;
  background:
    radial-gradient(circle at 42px 44px, rgba(47, 128, 237, 0.20), transparent 62px),
    linear-gradient(135deg, #edf6ff 0%, #ffffff 54%, #e8f2ff 100%) !important;
  box-shadow: 0 16px 36px rgba(23, 92, 211, 0.18), 0 0 0 5px rgba(47, 128, 237, 0.07) !important;
  padding: 0.84rem 0.92rem !important;
  margin-top: 0.35rem !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] {
  border: 1px solid rgba(23, 92, 211, 0.32);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.88);
  padding: 0.40rem 0.68rem 0.58rem 0.68rem;
  box-shadow: 0 8px 22px rgba(23, 92, 211, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] label {
  color: #1849a9 !important;
  font-size: 0.76rem !important;
  font-weight: 950 !important;
  letter-spacing: 0.055em;
  text-transform: uppercase;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  border: 2px solid rgba(23, 92, 211, 0.48) !important;
  border-radius: 13px !important;
  min-height: 3.05rem !important;
  background: linear-gradient(135deg, #ffffff 0%, #f7fbff 100%) !important;
  box-shadow: 0 5px 15px rgba(23, 92, 211, 0.08) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] div[role="combobox"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] div[role="button"] {
  color: #092454 !important;
  font-weight: 900 !important;
  font-size: 1.26rem !important;
  line-height: 1.22 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] > div span,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.cpmm-commercial-control-workflow) div[data-testid="stSelectbox"] div[data-baseweb="select"] p {
  color: #092454 !important;
  font-weight: 900 !important;
  font-size: 1.26rem !important;
  line-height: 1.22 !important;
}
.cpmm-commercial-control-workflow {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.15rem;
  margin: 0.06rem 0 0.82rem 0;
}
.cpmm-commercial-control-icon {
  width: 72px;
  height: 72px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.72rem;
  font-weight: 950;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #175cd3;
  box-shadow: 0 7px 18px rgba(23, 92, 211, 0.16);
}
.cpmm-commercial-control-copy { min-width: 0; }
.cpmm-commercial-control-kicker {
  color: #175cd3;
  font-size: 0.80rem;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.14rem;
}
.cpmm-commercial-control-value {
  color: #092454;
  font-size: 1.40rem;
  font-weight: 950;
  line-height: 1.18;
  overflow-wrap: anywhere;
}
.cpmm-commercial-control-detail {
  color: #344054;
  font-size: 0.90rem;
  line-height: 1.36;
  margin-top: 0.30rem;
}
.cpmm-commercial-control-badge {
  align-self: start;
  border-radius: 999px;
  padding: 0.22rem 0.68rem;
  background: #175cd3;
  color: #ffffff;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.06em;
  box-shadow: 0 4px 12px rgba(23, 92, 211, 0.22);
}
@media (max-width: 900px) {
  .cpmm-commercial-control-workflow { grid-template-columns: auto minmax(0, 1fr); }
  .cpmm-commercial-control-badge { grid-column: 2; justify-self: start; }
}

.cpmm-dashboard-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.80rem;
  align-items: flex-start;
  border: 1px solid #d9e2f2;
  border-left: 5px solid #7b8794;
  border-radius: 14px;
  padding: 0.98rem 1.0rem;
  background: linear-gradient(135deg, #ffffff 0%, #fbfdff 100%);
  min-height: 118px;
  box-shadow: 0 9px 24px rgba(16, 24, 40, 0.07);
}
.cpmm-dashboard-card.primary {
  min-height: 132px;
  background: #fbfcfe;
}
.cpmm-dashboard-card.ready { border-left-color: #24a148; background: linear-gradient(135deg, #ffffff 0%, #f0fff5 100%); }
.cpmm-dashboard-card.warning { border-left-color: #f59e0b; background: linear-gradient(135deg, #ffffff 0%, #fffbeb 100%); }
.cpmm-dashboard-card.danger { border-left-color: #d92d20; background: linear-gradient(135deg, #ffffff 0%, #fff3f2 100%); }
.cpmm-dashboard-card.info { border-left-color: #2f80ed; background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%); }
.cpmm-dashboard-card.neutral { border-left-color: #7b8794; background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); }
.cpmm-card-icon {
  width: 42px;
  height: 42px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 950;
  font-size: 1.16rem;
  background: #eef1f5;
  color: #475467;
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.08);
}
.cpmm-dashboard-card.ready .cpmm-card-icon { background: #dcfce7; color: #16833a; }
.cpmm-dashboard-card.warning .cpmm-card-icon { background: #fef3c7; color: #b45309; }
.cpmm-dashboard-card.danger .cpmm-card-icon { background: #fee4e2; color: #b42318; }
.cpmm-dashboard-card.info .cpmm-card-icon { background: #dbeafe; color: #175cd3; }
.cpmm-card-body { min-width: 0; }
.cpmm-summary-strip {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.7rem 0.85rem;
  margin-bottom: 0.25rem;
}
.cpmm-summary-title {
  color: #667085;
  font-size: 0.74rem;
  font-weight: 650;
  letter-spacing: 0;
  margin-bottom: 0.18rem;
}
.cpmm-summary-value {
  color: #101828;
  font-size: 1.02rem;
  font-weight: 720;
  line-height: 1.2;
  overflow-wrap: anywhere;
}
.cpmm-summary-detail {
  color: #667085;
  font-size: 0.76rem;
  line-height: 1.25;
  margin-top: 0.2rem;
}
.cpmm-card-title {
  color: #475467;
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0;
  margin-bottom: 0.35rem;
}
.cpmm-card-value {
  color: #101828;
  font-size: 1.14rem;
  font-weight: 900;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.cpmm-card-detail {
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.35;
  margin-top: 0.35rem;
}
.cpmm-status-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.13rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0;
  margin-top: 0.45rem;
}
.cpmm-status-badge.ready { color: #1f5f2a; background: #e7f5e8; }
.cpmm-status-badge.warning { color: #7a4b00; background: #fff4d6; }
.cpmm-status-badge.danger { color: #9f1f17; background: #fde8e7; }
.cpmm-status-badge.info { color: #1849a9; background: #e8f1ff; }
.cpmm-status-badge.neutral { color: #475467; background: #eef1f5; }
.cpmm-compact-panel {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.8rem 0.95rem;
  margin-bottom: 0.5rem;
}
.cpmm-kv-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.38rem 0;
}
.cpmm-kv-row:last-child { border-bottom: 0; }
.cpmm-kv-grid-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.45rem 0;
}
.cpmm-kv-grid-row:last-child { border-bottom: 0; }
.cpmm-kv-cell {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.8rem;
  min-width: 0;
}
.cpmm-kv-label {
  color: #667085;
  font-size: 0.82rem;
  font-weight: 600;
}
.cpmm-kv-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 650;
  text-align: right;
  overflow-wrap: anywhere;
}
</style>
"""


_MEMBER_TYPE_OPTIONS: dict[str, str] = {
    "Column / Pier / Wall / Pylon — RC / Prestressed Member": "column_pier_pmm",
    "Bridge Beam / Girder — RC / Prestressed Member": "beam_girder",
    "Building Beam / Girder — RC / Prestressed Member": "building_beam_girder",
}

_LEGACY_MEMBER_TYPE_LABELS: dict[str, str] = {
    "Column / Pier / Wall / Pylon - PMM Mode": "Column / Pier / Wall / Pylon — RC / Prestressed Member",
    "Beam / Girder - Future Design Workflow": "Bridge Beam / Girder — RC / Prestressed Member",
    "Beam / Girder - Flexure Mode Future": "Bridge Beam / Girder — RC / Prestressed Member",
}


_MEMBER_TYPE_REVERSE_OPTIONS: dict[str, str] = {value: label for label, value in _MEMBER_TYPE_OPTIONS.items()}


def _coerce_analysis_mode_settings(value: Any) -> AnalysisModeSettings:
    """Return a validated AnalysisModeSettings object from session/project data."""
    if isinstance(value, AnalysisModeSettings):
        return value
    if isinstance(value, dict):
        return AnalysisModeSettings.model_validate(value)
    return AnalysisModeSettings()


def _analysis_mode_label_for_member_type(member_type: str) -> str:
    return _MEMBER_TYPE_REVERSE_OPTIONS.get(member_type, _MEMBER_TYPE_REVERSE_OPTIONS["column_pier_pmm"])


def _mode_guidance_lines(settings: AnalysisModeSettings) -> list[str]:
    """Concise project-level guidance for the selected member workflow."""
    if settings.member_type == "beam_girder":
        return [
            "Bridge Beam/Girder workflow uses AASHTO LRFD design basis.",
            "Bridge-specific system settings, staged SLS loads, CSiBridge LL+IM workflow, prestress, and debonding tools are active only here.",
            "Current bridge girder ULS flexure, SHEAR.CODE2, TORSION.CODE2, staged SLS, deflection/camber, and prestress tools are guarded preview / engineering-review workflows.",
        ]
    if settings.member_type == "building_beam_girder":
        return [
            "Building Beam/Girder workflow uses ACI 318 design basis.",
            "Bridge-specific girder spacing, number of girders, barrier/sidewalk/wearing surface, CSiBridge, and staged composite assumptions are hidden.",
            "Building beam/girder ULS/SLS tools are guarded preview / engineering-review workflows; final code-certified design remains future scope.",
        ]
    return [
        "Column/Pier/Wall/Pylon mode uses the existing Pu, Mux, Muy PMM workflow.",
        "This workflow may use ACI 318 or AASHTO LRFD as project code basis; unsupported engines show capability guards.",
    ]


def _workflow_hero_html(label: str) -> str:
    return f"""
    <div class="cpmm-workflow-hero">
      <div class="cpmm-workflow-hero-kicker">Active Member Workflow</div>
      <div class="cpmm-workflow-hero-value">{escape(label)}</div>
      <div class="cpmm-workflow-hero-detail">Primary project control for section filtering, design-code routing, loads, analysis, and report context.</div>
      <span class="cpmm-workflow-hero-badge">REQUIRED</span>
    </div>
    """


def _setup_page_hero_html() -> str:
    return """
    <div class="cpmm-setup-page-hero">
      <div class="cpmm-setup-page-icon">⚙</div>
      <div>
        <div class="cpmm-setup-page-title">Setup Workspace</div>
        <div class="cpmm-setup-page-subtitle">Define the active engineering workflow and project-level design basis before creating sections, loads, analysis, and reports.</div>
      </div>
    </div>
    """


def _commercial_step_title_html(number: int, title: str, note: str) -> str:
    return f"""
    <div class="cpmm-commercial-step-title">
      <span class="cpmm-commercial-step-number">{number}</span>
      <span class="cpmm-commercial-step-heading">{escape(title)}</span>
    </div>
    <div class="cpmm-commercial-step-note">{escape(note)}</div>
    """


def _render_analysis_mode_selector(current: AnalysisModeSettings) -> AnalysisModeSettings:
    """Project-level Analysis Mode / Member Type selector.

    The app already has detailed analysis controls inside the Analysis workspace.
    This project-level selector makes the member workflow explicit before users
    start assigning sections, materials, loads, and reports.
    """
    labels = list(_MEMBER_TYPE_OPTIONS.keys())
    current_label = _analysis_mode_label_for_member_type(current.member_type)
    widget_key = "project_analysis_mode_member_type_label"
    note_key = "project_analysis_mode_note"
    sync_key = "project_analysis_mode_member_type_sync"

    legacy_label = st.session_state.get(widget_key)
    if legacy_label in _LEGACY_MEMBER_TYPE_LABELS:
        st.session_state[widget_key] = _LEGACY_MEMBER_TYPE_LABELS[str(legacy_label)]

    # Keep the Project-page widgets synchronized when a project is loaded. This
    # selector is the single editable owner of analysis_mode_settings; downstream
    # pages render this setting as read-only workflow context.
    if st.session_state.get(sync_key) != current.member_type or st.session_state.get(widget_key) not in labels:
        st.session_state[widget_key] = current_label
        st.session_state[note_key] = current.note or ""
        st.session_state[sync_key] = current.member_type

    with st.container(border=True):
        st.markdown(
            _commercial_step_title_html(
                1,
                "Active Member Workflow",
                "Select the primary engineering workflow. Workflow controls design-code routing and this master control determines available section presets, load workflow, analysis stages, and report context.",
            ),
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown(
                f'''
                <div class="cpmm-commercial-control-workflow">
                  <div class="cpmm-commercial-control-icon">WF</div>
                  <div class="cpmm-commercial-control-copy">
                    <div class="cpmm-commercial-control-kicker">Active Member Workflow</div>
                    <div class="cpmm-commercial-control-value">{escape(analysis_mode_label(current))}</div>
                    <div class="cpmm-commercial-control-detail">Master control for section presets, design-code routing, load workflow, analysis modules, and report context.</div>
                  </div>
                  <div class="cpmm-commercial-control-badge">REQUIRED</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )
            selected_label = st.selectbox(
                "Change active member workflow",
                labels,
                key=widget_key,
                help="Bridge Beam/Girder activates guarded AASHTO LRFD bridge girder tools. Building Beam/Girder activates guarded ACI 318 beam/girder tools. Column/Pier can use ACI 318 or AASHTO LRFD with capability guards.",
                label_visibility="visible",
            )
        note = st.session_state.get(note_key, current.note or "")
        selected_member_type = _MEMBER_TYPE_OPTIONS[_LEGACY_MEMBER_TYPE_LABELS.get(selected_label, selected_label)]
        settings = AnalysisModeSettings(member_type=selected_member_type, note=note or None)
        st.session_state["analysis_mode_settings"] = settings
        st.session_state[sync_key] = settings.member_type

        mode_cards = _analysis_configuration_cards(settings)
        st.markdown(_compact_panel_html(mode_cards, columns=2), unsafe_allow_html=True)
        st.info(analysis_mode_description(settings))
        for line in _mode_guidance_lines(settings):
            st.caption(f"• {line}")
        for warning in analysis_mode_warnings(settings):
            st.info(warning)

    return settings


def status_style_for_value(value: Any) -> str:
    text = str(value).strip().upper()
    if text in {"READY", "YES", "PASS", "PASSED", "VALID", "COMPLETE", "AVAILABLE"}:
        return "ready"
    if text in {"WARNING", "WARNINGS", "PARTIAL", "CAUTION"}:
        return "warning"
    if text in {"NOT_READY", "NO", "FAIL", "FAILED", "INVALID", "CRITICAL", "ERROR"}:
        return "danger"
    if text in {"N/A", "NA", "NONE", "NOT ACTIVE", "FUTURE / NOT IMPLEMENTED", "NOT APPLICABLE"}:
        return "neutral"
    return "info"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "Yes" if value else "No"


def _dashboard_card_html(card: DashboardCard) -> str:
    status = card.status if card.status in {"ready", "warning", "danger", "info", "neutral"} else "info"
    icon_map = {
        "ready": "✓",
        "warning": "!",
        "danger": "×",
        "info": "↻",
        "neutral": "–",
    }
    detail_html = f'<div class="cpmm-card-detail">{escape(card.detail)}</div>' if card.detail else ""
    badge_html = f'<span class="cpmm-status-badge {status}">{escape(status.upper())}</span>' if card.strong else ""
    primary_class = " primary" if card.strong else ""
    return (
        f'<div class="cpmm-dashboard-card {status}{primary_class}">'
        f'<div class="cpmm-card-icon">{escape(icon_map.get(status, "•"))}</div>'
        '<div class="cpmm-card-body">'
        f'<div class="cpmm-card-title">{escape(card.title)}</div>'
        f'<div class="cpmm-card-value">{escape(card.value)}</div>'
        f"{detail_html}"
        f"{badge_html}"
        '</div>'
        "</div>"
    )


def _summary_item_html(card: DashboardCard) -> str:
    detail_html = f'<div class="cpmm-summary-detail">{escape(card.detail)}</div>' if card.detail else ""
    return (
        '<div class="cpmm-summary-strip">'
        f'<div class="cpmm-summary-title">{escape(card.title)}</div>'
        f'<div class="cpmm-summary-value">{escape(card.value)}</div>'
        f"{detail_html}"
        "</div>"
    )


def _compact_panel_html(cards: list[DashboardCard], columns: int | None = None) -> str:
    """Render compact key-value cards.

    ``columns`` is accepted for small workflow panels that want a wider visual
    rhythm, but the function remains backward-compatible with the earlier
    single-column compact panel calls.  Keeping the parameter here avoids a
    Streamlit runtime TypeError if callers pass the layout hint.
    """
    if columns is not None and columns > 1:
        safe_columns = max(1, int(columns))
        rows: list[str] = []
        for start in range(0, len(cards), safe_columns):
            row_cards = cards[start : start + safe_columns]
            cells: list[str] = []
            for card in row_cards:
                badge = ""
                if card.strong:
                    status = card.status if card.status in {"ready", "warning", "danger", "info", "neutral"} else "info"
                    badge = f' <span class="cpmm-status-badge {status}">{escape(status.upper())}</span>'
                cells.append(
                    '<div class="cpmm-kv-cell">'
                    f'<div class="cpmm-kv-label">{escape(card.title)}</div>'
                    f'<div class="cpmm-kv-value">{escape(card.value)}{badge}</div>'
                    "</div>"
                )
            rows.append('<div class="cpmm-kv-grid-row">' + "".join(cells) + "</div>")
        return '<div class="cpmm-compact-panel">' + "".join(rows) + "</div>"

    rows: list[str] = []
    for card in cards:
        badge = ""
        if card.strong:
            status = card.status if card.status in {"ready", "warning", "danger", "info", "neutral"} else "info"
            badge = f' <span class="cpmm-status-badge {status}">{escape(status.upper())}</span>'
        rows.append(
            '<div class="cpmm-kv-row">'
            f'<div class="cpmm-kv-label">{escape(card.title)}</div>'
            f'<div class="cpmm-kv-value">{escape(card.value)}{badge}</div>'
            "</div>"
        )
    return '<div class="cpmm-compact-panel">' + "".join(rows) + "</div>"


def _render_dashboard_card(card: DashboardCard) -> None:
    st.markdown(_dashboard_card_html(card), unsafe_allow_html=True)


def _render_dashboard_section(title: str, cards: list[DashboardCard], columns: int = 4) -> None:
    st.subheader(title)
    for start in range(0, len(cards), columns):
        cols = st.columns(min(columns, len(cards) - start))
        for column, card in zip(cols, cards[start : start + columns]):
            with column:
                _render_dashboard_card(card)


def _render_summary_strip(title: str, cards: list[DashboardCard]) -> None:
    st.subheader(title)
    cols = st.columns(len(cards))
    for column, card in zip(cols, cards):
        with column:
            st.markdown(_summary_item_html(card), unsafe_allow_html=True)


def _render_compact_panel(title: str, cards: list[DashboardCard], columns: int = 1) -> None:
    st.subheader(title)
    chunk_size = max(1, (len(cards) + columns - 1) // columns)
    cols = st.columns(columns)
    for index, column in enumerate(cols):
        chunk = cards[index * chunk_size : (index + 1) * chunk_size]
        if chunk:
            with column:
                st.markdown(_compact_panel_html(chunk), unsafe_allow_html=True)


def _count_available(items: Any) -> int:
    return len([item for item in items if getattr(item, "available", False)])


def _project_overview_cards(
    project: ProjectModel,
    section_geometry: Any,
    load_cases: list[Any],
    rebars: list[Any],
    prestress_elements: list[Any],
    rebar_valid: bool | None,
    prestress_valid: bool | None,
) -> list[DashboardCard]:
    return [
        DashboardCard(
            "Geometry",
            "Yes" if section_geometry is not None else "No",
            "Generated section available" if section_geometry is not None else "Build section",
            status_style_for_value("Yes" if section_geometry is not None else "No"),
        ),
        DashboardCard("Load Cases", f"{len(load_cases):,}", "Stored load combinations", "ready" if load_cases else "neutral"),
        DashboardCard("Rebars", f"{len(rebars):,}", f"Valid for analysis: {_format_bool(rebar_valid)}", status_style_for_value(_format_bool(rebar_valid))),
        DashboardCard(
            "Prestress Elements",
            f"{len(prestress_elements):,}",
            f"Valid for analysis: {_format_bool(prestress_valid)}",
            status_style_for_value(_format_bool(prestress_valid)),
        ),
        DashboardCard("Version", project.version, "", "neutral"),
    ]


def _analysis_configuration_cards(analysis_mode: AnalysisModeSettings) -> list[DashboardCard]:
    if analysis_mode.member_type == "beam_girder":
        beam_status = "Bridge active"
        beam_detail = "Bridge-specific girder SLS/prestress tools are available as preview workflows"
    elif analysis_mode.member_type == "building_beam_girder":
        beam_status = "Building planned"
        beam_detail = "Building beam/girder engines are guarded; bridge-specific assumptions are hidden"
    else:
        beam_status = "Not active"
        beam_detail = "Select Bridge or Building Beam/Girder to activate beam/girder routing"
    pmm_value = "Available" if analysis_mode.allow_pmm_workflow else "Not applicable"
    pmm_detail = (
        "Column/Pier/Wall/Pylon PMM workspace availability"
        if analysis_mode.allow_pmm_workflow
        else "Reserved for Column/Pier/Wall/Pylon PMM workflow"
    )
    sls_value = "Yes" if analysis_mode.allow_sls_workflow else "Not selected"
    sls_detail = (
        "Beam/Girder staged SLS stress workflow availability"
        if analysis_mode.allow_sls_workflow
        else "Column/Pier workflow is governed here by ULS PMM; member SLS checks are not active in this workspace"
    )
    return [
        DashboardCard("Member Type", analysis_mode_label(analysis_mode), "Active analysis context", "info"),
        DashboardCard("Analysis Workflow", analysis_mode.analysis_workflow, "Configured workflow mode", "info"),
        DashboardCard(
            "PMM Workflow",
            pmm_value,
            pmm_detail,
            "ready" if analysis_mode.allow_pmm_workflow else "neutral",
            strong=False,
        ),
        DashboardCard(
            "SLS Workflow",
            sls_value,
            sls_detail,
            "ready" if analysis_mode.allow_sls_workflow else "neutral",
            strong=not analysis_mode.allow_sls_workflow,
        ),
        DashboardCard("Beam/Girder Workflow", beam_status, beam_detail, status_style_for_value(beam_status)),
    ]


def _sync_setup_design_code_widget_state_before_render(
    session_state: Any,
    *,
    member_type: object | None,
) -> tuple[str, str]:
    """Synchronize Setup design-code widgets without swallowing user changes.

    CODE.SYNC3 fixes a Streamlit ordering edge case: after the user changes the
    Setup ``design_code`` selectbox, the new value exists in the widget-owned
    key before the page body is rendered again.  If we blindly copy the durable
    ``project_design_code`` value back into that widget key at the top of the
    page, the selectbox snaps back to the old code and AASHTO cannot be chosen.

    A small sync marker records the durable value last copied into the widget.
    When the widget key differs from that marker and the marker still matches
    the durable value, the difference is treated as a real user selection and is
    promoted to the durable project key before the selectbox is created.
    """

    allowed_codes = set(allowed_project_design_codes_for_workflow(member_type))
    durable_code = default_project_design_code_for_workflow(
        member_type,
        session_state.get(PROJECT_DESIGN_CODE_STATE_KEY, session_state.get("design_code")),
    )
    widget_code_raw = session_state.get("design_code")
    widget_code = default_project_design_code_for_workflow(member_type, widget_code_raw)
    widget_sync_code = session_state.get(_PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY)

    code_from_user_widget = (
        widget_code_raw is not None
        and widget_sync_code == durable_code
        and widget_code != durable_code
        and widget_code in allowed_codes
    )
    selected_code = widget_code if code_from_user_widget else durable_code

    durable_edition = normalize_project_code_edition(
        selected_code,
        session_state.get(PROJECT_CODE_EDITION_STATE_KEY, session_state.get("code_edition")),
    )
    widget_edition_raw = session_state.get("code_edition")
    widget_edition = normalize_project_code_edition(selected_code, widget_edition_raw)
    widget_sync_edition = session_state.get(_PROJECT_CODE_EDITION_WIDGET_SYNC_KEY)
    edition_from_user_widget = (
        widget_edition_raw is not None
        and widget_sync_edition == durable_edition
        and widget_edition != durable_edition
        and widget_edition in code_edition_options_for(selected_code)
    )
    selected_edition = widget_edition if edition_from_user_widget else durable_edition

    code, edition = sync_project_design_code_to_session(
        session_state,
        member_type=member_type,
        selected_code=selected_code,
        selected_edition=selected_edition,
        sync_legacy_widget_keys=True,
    )
    session_state[_PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY] = code
    session_state[_PROJECT_CODE_EDITION_WIDGET_SYNC_KEY] = edition
    return code, edition


def _project_design_code_cards(project: ProjectModel, analysis_mode: AnalysisModeSettings) -> list[DashboardCard]:
    """Return CODE.SETUP1 source-of-truth and capability guard cards."""

    capability_rows = project_code_capability_cards(project.code, analysis_mode.member_type)
    cards: list[DashboardCard] = [
        DashboardCard("Design Code", project.code, "Project-level source of truth", "info", strong=True),
        DashboardCard("Code Edition", project.code_edition or "Project-specified", "Saved with project JSON", "info"),
    ]
    for row in capability_rows[2:]:
        cards.append(DashboardCard(row["title"], row["value"], row["detail"], row["status"], strong=row["status"] == "warning"))
    return cards


def _render_workflow_aware_design_code_selector(analysis_mode: AnalysisModeSettings) -> None:
    """Render Setup design-code selector after workflow is known.

    WORKFLOW.TYPE2 filters Design Code by active workflow:
    Bridge Beam/Girder -> AASHTO LRFD only; Building Beam/Girder -> ACI 318
    only; Column/Pier/Wall/Pylon -> ACI 318 or AASHTO LRFD.
    """

    allowed_codes = list(allowed_project_design_codes_for_workflow(analysis_mode.member_type))
    current_code, current_edition = _sync_setup_design_code_widget_state_before_render(
        st.session_state,
        member_type=analysis_mode.member_type,
    )
    edition_options = code_edition_options_for(current_code)
    if st.session_state.get("code_edition") not in edition_options:
        current_edition = default_code_edition_for(current_code)
        sync_project_design_code_to_session(
            st.session_state,
            member_type=analysis_mode.member_type,
            selected_code=current_code,
            selected_edition=current_edition,
        )

    with st.container(border=True):
        st.markdown("#### Project Design Code")
        st.caption(workflow_code_policy_message(analysis_mode.member_type))
        code_cols = st.columns(2)
        with code_cols[0]:
            selected_code = st.selectbox(
                "Design Code",
                allowed_codes,
                key="design_code",
                disabled=len(allowed_codes) == 1,
                help="Workflow-aware source of truth. Bridge Beam/Girder is AASHTO LRFD only; Building Beam/Girder is ACI 318 only; Column/Pier/Wall/Pylon may choose either code.",
            )
        sync_project_design_code_to_session(
            st.session_state,
            member_type=analysis_mode.member_type,
            selected_code=selected_code,
            selected_edition=st.session_state.get("code_edition"),
            sync_legacy_widget_keys=False,
        )
        with code_cols[1]:
            edition_options = code_edition_options_for(selected_code)
            if st.session_state.get("code_edition") not in edition_options:
                st.session_state["code_edition"] = default_code_edition_for(selected_code)
            selected_edition = st.selectbox(
                "Code Edition",
                list(edition_options),
                key="code_edition",
                help="Saved with the project JSON. Solver-specific edition calibration is added only by named future milestones.",
            )
        selected_code, selected_edition = sync_project_design_code_to_session(
            st.session_state,
            member_type=analysis_mode.member_type,
            selected_code=selected_code,
            selected_edition=selected_edition,
            sync_legacy_widget_keys=False,
        )
        st.session_state[_PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY] = selected_code
        st.session_state[_PROJECT_CODE_EDITION_WIDGET_SYNC_KEY] = selected_edition
        if len(allowed_codes) == 1:
            st.info(f"Design Code is locked by workflow: {selected_code}.")


def _sls_stress_point_cards(custom_points: list[Any], include_default_stress_points: bool) -> list[DashboardCard]:
    active_custom_count = len([point for point in custom_points if getattr(point, "active", False)])
    return [
        DashboardCard("Custom Points", f"{len(custom_points):,}", "User-defined SLS review points", "info" if custom_points else "neutral"),
        DashboardCard("Active Custom Points", f"{active_custom_count:,}", "Included in SLS review", "ready" if active_custom_count else "neutral"),
        DashboardCard(
            "Include Default Stress Points",
            "Yes" if include_default_stress_points else "No",
            "Automatic section review points",
            "ready" if include_default_stress_points else "neutral",
        ),
    ]


def _pre_report_readiness_cards(snapshot: Any, readiness: Any) -> list[DashboardCard]:
    warning_status = "warning" if snapshot.warning_count else "ready"
    limitation_status = "danger" if snapshot.high_or_critical_limitation_count else "ready"
    return [
        DashboardCard("Overall Status", readiness.overall_status, "Pre-report readiness result", status_style_for_value(readiness.overall_status), strong=True),
        DashboardCard("ULS PMM Result", "Yes" if snapshot.pmm_result_available else "No", "Stored PMM result available", status_style_for_value("Yes" if snapshot.pmm_result_available else "No"), strong=True),
        DashboardCard("SLS Result", "Yes" if snapshot.sls_result_available else "No", "Stored serviceability result available", status_style_for_value("Yes" if snapshot.sls_result_available else "No"), strong=True),
        DashboardCard("Warning Count", f"{snapshot.warning_count:,}", "Stored engineering warnings", warning_status, strong=bool(snapshot.warning_count)),
        DashboardCard(
            "High/Critical Limitations",
            f"{snapshot.high_or_critical_limitation_count:,}",
            "Limitations requiring attention",
            limitation_status,
            strong=bool(snapshot.high_or_critical_limitation_count),
        ),
    ]


def _report_foundation_cards(manifest: Any, snapshot: Any) -> list[DashboardCard]:
    tables = _count_available(getattr(manifest, "tables", [])) if manifest else 0
    figures = _count_available(getattr(manifest, "figures", [])) if manifest else 0
    limitations = len(getattr(manifest, "engineering_limitations", [])) if manifest else snapshot.limitation_count
    return [
        DashboardCard("Report Manifest", "Yes" if manifest is not None else "No", "Report registry built", status_style_for_value("Yes" if manifest is not None else "No"), strong=manifest is None),
        DashboardCard("Available Tables", f"{tables:,}", "Manifest table registry", "neutral"),
        DashboardCard("Available Figures", f"{figures:,}", "Manifest figure registry", "neutral"),
        DashboardCard("Engineering Limitations", f"{limitations:,}", "Report limitation registry", "warning" if limitations else "ready", strong=bool(limitations)),
    ]


def _next_action_cards(
    *,
    section_geometry: Any,
    load_cases: list[Any],
    rebars: list[Any],
    prestress_elements: list[Any],
    analysis_mode: AnalysisModeSettings,
    readiness: Any,
) -> list[DashboardCard]:
    """Return a compact project decision view for the top of the Project page."""

    status = current_project_dirty_status(st.session_state)
    reinforcement_count = len(rebars) + len(prestress_elements)
    if section_geometry is None:
        next_action = DashboardCard(
            "Next Action",
            "Build Section",
            "Open Sections -> Section Builder before running analysis.",
            "warning",
            strong=True,
        )
    elif reinforcement_count == 0:
        next_action = DashboardCard(
            "Next Action",
            "Define Reinforcement",
            "Add ordinary rebar or prestress before strength/service checks.",
            "warning",
            strong=True,
        )
    elif not load_cases:
        next_action = DashboardCard(
            "Next Action",
            "Define Loads",
            "Add ULS or SLS load cases before running analysis.",
            "warning",
            strong=True,
        )
    elif status.analysis_status == "Out of date":
        next_action = DashboardCard(
            "Next Action",
            "Run Analysis",
            "Inputs changed after the last calculated result.",
            "warning",
            strong=True,
        )
    elif readiness.overall_status == "READY":
        next_action = DashboardCard(
            "Next Action",
            "Review Results",
            "Results are available; review warnings and report readiness.",
            "ready",
            strong=True,
        )
    else:
        next_action = DashboardCard(
            "Next Action",
            "Review Setup",
            "Complete setup and analysis gates before report issue.",
            "info",
            strong=True,
        )

    setup_value = "Ready" if section_geometry is not None and reinforcement_count > 0 and load_cases else "Incomplete"
    return [
        next_action,
        DashboardCard(
            "Setup Completeness",
            setup_value,
            "Section, reinforcement, and loads are the minimum analysis inputs.",
            status_style_for_value("READY" if setup_value == "Ready" else "WARNING"),
            strong=setup_value != "Ready",
        ),
        DashboardCard(
            "Active Workflow",
            analysis_mode_label(analysis_mode),
            "Controls design-code routing and visible assumptions.",
            "info",
        ),
        DashboardCard(
            "Project File",
            "Save / Load",
            "Use project file actions before major edits or handoff.",
            "neutral",
        ),
    ]


def _render_project_information_panel() -> None:
    with st.container(border=True):
        st.markdown("#### Project Information")
        st.text_input("Project Name", key="project_name")
        st.text_input("Designer", key="designer")
        st.text_area("Description", key="description")
        if st.button("Update Project Info", use_container_width=False, type="primary", key="ui_keys1_project_page_button_670"):
            st.success("Project information updated.")


def _render_project_setup_editor(analysis_mode: AnalysisModeSettings) -> None:
    st.markdown("### Edit Project Setup")
    st.caption(
        "Review project identity and workflow-locked design code before defining detailed section, assembly, reinforcement, loads, or analysis inputs."
    )
    _render_project_information_panel()

    _render_workflow_aware_design_code_selector(analysis_mode)
    project = project_from_session_state(st.session_state)
    _render_compact_panel("Project Design Code / Capability Guard", _project_design_code_cards(project, analysis_mode), columns=2)



def _render_project_file_actions(project: ProjectModel) -> None:
    st.subheader("Save / Load Project")
    save_col, load_col = st.columns(2)
    with save_col:
        st.download_button(
            "Save Project",
            data=project_to_json(project),
            file_name="concrete_section_pro_project.json",
            mime="application/json",
            use_container_width=True,
            type="primary",
            key="ui_keys1_project_page_download_button_692",
        )
    with load_col:
        uploaded_file = st.file_uploader("Upload Project JSON", type=["json"])
        if uploaded_file is not None and st.button("Load Project JSON", use_container_width=True, type="primary", key="ui_keys1_project_page_button_701"):
            st.session_state["_pending_project_json"] = uploaded_file.getvalue().decode("utf-8")
            st.rerun()


def _apply_pending_project_load() -> None:
    pending_json = st.session_state.pop("_pending_project_json", None)
    if pending_json is None:
        return

    try:
        project = project_from_json(pending_json)
        apply_project_to_session_state(project, st.session_state)
    except ProjectIOError as exc:
        st.session_state["_project_load_error"] = str(exc)
        return

    st.session_state["_project_load_success"] = (
        "Project JSON loaded. Review Section Builder, Rebar, Prestress, and Loads tabs before future analysis."
    )


def _ensure_project_default_state(session_state: Any) -> None:
    session_state.setdefault("project_name", "Untitled Project")
    session_state.setdefault("designer", "")
    session_state.setdefault("description", "")
    # DESIGN.CODE.STATE2/3: durable keys are the analysis/report source of truth,
    # but Setup widget keys must not be overwritten at the top of the rerun.
    # A fresh selectbox change is delivered through the widget-owned key before
    # the selector is rendered; overwriting it here makes the dropdown snap back
    # to the old code.  Initialize missing keys only, then let the selector sync
    # any real widget change into the durable project keys before creating the
    # widgets.
    code = project_design_code_from_session(session_state)
    edition = project_code_edition_from_session(session_state)
    session_state.setdefault(PROJECT_DESIGN_CODE_STATE_KEY, code)
    session_state.setdefault(PROJECT_CODE_EDITION_STATE_KEY, normalize_project_code_edition(code, edition))
    session_state.setdefault("design_code", session_state[PROJECT_DESIGN_CODE_STATE_KEY])
    session_state.setdefault("code_edition", session_state[PROJECT_CODE_EDITION_STATE_KEY])


def _ensure_project_defaults() -> None:
    _ensure_project_default_state(st.session_state)




def _render_project_status_panel() -> None:
    """Render PERF.RERUN1 project/analysis dirty-state cards."""

    status = current_project_dirty_status(st.session_state)
    changed = ", ".join(status.changed_groups) if status.changed_groups else "None"
    affected = ", ".join(status.affected_checks) if status.affected_checks else "None"
    cards = [
        DashboardCard(
            "Model status",
            status.model_status,
            f"Changed groups: {changed}",
            "warning" if status.model_status == "Modified" else ("ready" if status.model_status == "Current" else "info"),
            strong=status.model_status == "Modified",
        ),
        DashboardCard(
            "Analysis status",
            status.analysis_status,
            f"Last refreshed: {status.last_refreshed_workspace or '-'}",
            "warning" if status.analysis_status == "Out of date" else ("ready" if status.analysis_status == "Current" else "neutral"),
            strong=status.analysis_status == "Out of date",
        ),
        DashboardCard(
            "Affected checks",
            affected,
            "Downstream checks are not recalculated on input pages",
            "warning" if status.affected_checks else "neutral",
        ),
        DashboardCard(
            "Recommended action",
            status.recommended_action,
            "PERF.RERUN1 lazy-analysis guard",
            "info",
        ),
    ]
    _render_dashboard_section("Project Status", cards, columns=4)
    st.caption(
        "Input edits are saved immediately. Analysis and report outputs are treated as stale until the relevant Analysis subpage is opened; inactive workspaces are not rendered on every rerun."
    )


def render_project_page() -> None:
    _apply_pending_project_load()
    _ensure_project_defaults()

    st.markdown(_DASHBOARD_CSS, unsafe_allow_html=True)
    st.markdown(_setup_page_hero_html(), unsafe_allow_html=True)

    success_message = st.session_state.pop("_project_load_success", None)
    error_message = st.session_state.pop("_project_load_error", None)
    if success_message:
        st.success(success_message)
    if error_message:
        st.error(f"Invalid project file: {error_message}")

    analysis_mode = _coerce_analysis_mode_settings(st.session_state.get("analysis_mode_settings", AnalysisModeSettings()))
    project = project_from_session_state(st.session_state)
    section_geometry = st.session_state.get("section_geometry")
    load_cases = st.session_state.get("load_cases", [])
    rebars = st.session_state.get("rebars", [])
    prestress_elements = st.session_state.get("prestress_elements", [])
    custom_points = st.session_state.get("custom_stress_check_points", [])
    include_default_stress_points = bool(st.session_state.get("include_default_stress_check_points", True))
    rebar_valid = st.session_state.get("rebars_valid_for_analysis")
    prestress_valid = st.session_state.get("prestress_valid_for_analysis")
    snapshot = build_result_traceability_snapshot(st.session_state)
    readiness = check_report_readiness(snapshot)

    _render_project_status_panel()

    analysis_mode = _render_analysis_mode_selector(analysis_mode)
    _render_project_setup_editor(analysis_mode)
    project = project_from_session_state(st.session_state)

    _render_dashboard_section(
        "Project Decision View",
        _next_action_cards(
            section_geometry=section_geometry,
            load_cases=load_cases,
            rebars=rebars,
            prestress_elements=prestress_elements,
            analysis_mode=analysis_mode,
            readiness=readiness,
        ),
        columns=4,
    )

    _render_summary_strip(
        "Project Summary",
        _project_overview_cards(project, section_geometry, load_cases, rebars, prestress_elements, rebar_valid, prestress_valid),
    )

    _render_compact_panel("Analysis Configuration", _analysis_configuration_cards(analysis_mode), columns=2)
    _render_compact_panel("Project Design Code / Capability Guard", _project_design_code_cards(project, analysis_mode), columns=2)

    project = project_from_session_state(st.session_state)
    # UI.COMMERCIAL4.3: Project file actions moved to the sidebar Project File panel.

    _render_dashboard_section("Pre-Report Readiness", _pre_report_readiness_cards(snapshot, readiness), columns=5)

    _render_compact_panel("SLS Stress Points", _sls_stress_point_cards(custom_points, include_default_stress_points), columns=1)

    manifest = st.session_state.get("report_manifest")
    _render_compact_panel("Report Foundation", _report_foundation_cards(manifest, snapshot), columns=2)

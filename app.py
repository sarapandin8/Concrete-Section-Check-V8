"""Concrete Section Pro Streamlit application."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.analysis_modes import analysis_mode_label, is_portal_frame_crossbeam_workflow
from concrete_pmm_pro.core.design_code import workflow_project_code_label_from_session
from concrete_pmm_pro.crossbeam.construction_stage import crossbeam_layout_navigation_label
from concrete_pmm_pro.state.dirty_state import current_project_dirty_status, update_dirty_state_from_session
from concrete_pmm_pro.io.project_io import (
    ProjectIOError,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_shear_decision_summary,
    _beam_uls_shear_utilization_display,
    _render_runtime_diagnostics_expander,
    render_analysis_page,
    render_analysis_report_qa,
    render_report_qa_page,
)
from concrete_pmm_pro.reporting.railway_u_girder_report import build_railway_u_girder_sls_report_package
from concrete_pmm_pro.ui.loads_page import render_loads_page
from concrete_pmm_pro.ui.materials_page import render_materials_page
from concrete_pmm_pro.ui.prestress_page import render_prestress_page
from concrete_pmm_pro.ui.project_page import render_project_page
from concrete_pmm_pro.ui.navigation import render_active_choice
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
from concrete_pmm_pro.ui.rebar_page import render_rebar_page
from concrete_pmm_pro.ui.section_builder import render_section_builder
from concrete_pmm_pro.ui.crossbeam_pages import (
    render_crossbeam_prestress_loss_page,
    render_crossbeam_segment_layout_page,
    render_crossbeam_tendon_profile_page,
    render_crossbeam_tendon_system_page,
)
from concrete_pmm_pro.ui.crossbeam_rebar_page import render_crossbeam_rebar_page
from concrete_pmm_pro.visualization.plot_readability import install_streamlit_plotly_readability_patch


WORKSPACE_NAVIGATION = {
    "Setup": ["Project", "Materials"],
    "Sections": ["Section Builder", "Rebar", "Prestress"],
    "Loads": ["Loads"],
    "Analysis": ["ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber"],
    "Result Summary": ["Overview", "ULS Summary", "SLS Summary", "Traceability"],
    "Report / QA": ["Report / QA"],
}

RESULTS_WORKSPACE_PLACEHOLDER = (
    "Future Result Summary workspace. Current detailed outputs remain available under Analysis. "
    "The Result Summary dashboard shows stored decision summaries only and does not rerun solvers."
)


def _sections_navigation_options() -> list[str]:
    """Return workflow-scoped Section subpages without changing other workflows."""

    mode = _analysis_mode_from_session_for_chrome()
    if is_portal_frame_crossbeam_workflow(mode):
        layout_label = crossbeam_layout_navigation_label(
            st.session_state.get("crossbeam_ptloss3b1_construction_method")
        )
        if layout_label == "Segment Layout":
            return ["Section Builder", "Segment Layout", "Rebar", "Tendon System", "Tendon Profile", "Prestress Loss"]
        return ["Section Builder", "Section / Zone Layout", "Rebar", "Tendon System", "Tendon Profile", "Prestress Loss"]
    return list(WORKSPACE_NAVIGATION["Sections"])


def _workspace_subpages(workspace: str) -> list[str]:
    if str(workspace) == "Sections":
        return _sections_navigation_options()
    return list(WORKSPACE_NAVIGATION.get(str(workspace), []))


_COMMERCIAL_TAB_CSS = """
<style>
/* UI.COMMERCIAL.TABS2 / UI.COMMERCIAL.TABS3 / UI.COMMERCIAL.TABS4 / UI.ACTIVE.TABS1 / UI.ACTIVE.TABS2 / UI.ACTIVE.TABS3 / UI.ACTION.BUTTONS1 / UI.ACTION.BUTTONS2:
   dark-blue bold typography plus compact deterministic active-tab highlight and state-aware highlighted primary action buttons. */
:root {
  --cpmm-ink-blue: #0b3a66;
  --cpmm-ink-blue-soft: #164f83;
  --cpmm-blue-border: #9fb9d4;
  --cpmm-blue-fill: #e8f1ff;
  --cpmm-blue-fill-strong: #d9eafe;
  --cpmm-action-fill: #1d6fe7;
  --cpmm-action-fill-hover: #175cd3;
  --cpmm-action-border: #1d6fe7;
  --cpmm-action-border-hover: #0f5ec2;
  --cpmm-action-disabled-fill: #f3f6f9;
  --cpmm-action-disabled-border: #c8d2dd;
  --cpmm-action-disabled-text: #6d7d8f;
  --cpmm-active-tab-fill: #e7f2ff;
  --cpmm-active-tab-border: #1d6fe7;
  --cpmm-active-tab-accent: #1d6fe7;
  --cpmm-active-tab-shadow: rgba(29, 111, 231, 0.14);
}

/* UI.ACTIVE.TABS3: make the app feel like a working engineering screen, not a landing page. */
.block-container {
  padding-top: 1.55rem !important;
}
div[data-testid="stVerticalBlock"] {
  gap: 0.48rem !important;
}
h1, div[data-testid="stMarkdownContainer"] h1 {
  color: var(--cpmm-ink-blue) !important;
  font-size: 1.95rem !important;
  line-height: 1.24 !important;
  margin: 0.12rem 0 0.18rem 0 !important;
  font-weight: 850 !important;
  overflow: visible !important;
}
div[data-testid="stCaptionContainer"] {
  margin-bottom: 0.15rem !important;
}

/* Existing app/workspace tabs: bolder, slightly larger, dark-blue text. */
div[data-testid="stSegmentedControl"],
div[data-testid="stButtonGroup"] {
  margin: 0.1rem 0 0.65rem 0;
}

/* Streamlit version compatibility:
   - older segmented controls can expose stSegmentedControl
   - current segmented_control/pills often render as stButtonGroup
   - radio fallback remains styled below */
div[data-testid="stSegmentedControl"] button,
div[data-testid="stButtonGroup"] button,
button[data-testid="stBaseButton-segmentedControl"],
button[data-testid="stBaseButton-segmentedControlActive"],
div[data-testid="stButtonGroup"] [role="button"],
div[data-testid="stButtonGroup"] [role="radio"] {
  border-radius: 0 !important;
  border: 1px solid var(--cpmm-blue-border) !important;
  border-right: 0 !important;
  background: #ffffff !important;
  color: var(--cpmm-ink-blue) !important;
  min-height: 2.24rem !important;
  padding: 0.38rem 1.0rem !important;
  font-size: 0.94rem !important;
  font-weight: 800 !important;
  letter-spacing: 0.004em !important;
  box-shadow: none !important;
}
div[data-testid="stSegmentedControl"] button:first-child,
div[data-testid="stButtonGroup"] button:first-child,
button[data-testid="stBaseButton-segmentedControl"]:first-child,
button[data-testid="stBaseButton-segmentedControlActive"]:first-child,
div[data-testid="stButtonGroup"] [role="button"]:first-child,
div[data-testid="stButtonGroup"] [role="radio"]:first-child {
  border-radius: 7px 0 0 7px !important;
}
div[data-testid="stSegmentedControl"] button:last-child,
div[data-testid="stButtonGroup"] button:last-child,
button[data-testid="stBaseButton-segmentedControl"]:last-child,
button[data-testid="stBaseButton-segmentedControlActive"]:last-child,
div[data-testid="stButtonGroup"] [role="button"]:last-child,
div[data-testid="stButtonGroup"] [role="radio"]:last-child {
  border-right: 1px solid var(--cpmm-blue-border) !important;
  border-radius: 0 7px 7px 0 !important;
}
div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
div[data-testid="stSegmentedControl"] button[data-selected="true"],
div[data-testid="stSegmentedControl"] button[data-testid="stBaseButton-segmentedControlActive"],
div[data-testid="stButtonGroup"] button[aria-pressed="true"],
div[data-testid="stButtonGroup"] button[data-selected="true"],
div[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmentedControlActive"],
button[data-testid="stBaseButton-segmentedControlActive"],
div[data-testid="stButtonGroup"] [role="radio"][aria-checked="true"],
div[data-testid="stButtonGroup"] [role="button"][aria-pressed="true"] {
  background: var(--cpmm-active-tab-fill) !important;
  color: var(--cpmm-ink-blue) !important;
  border-color: var(--cpmm-active-tab-border) !important;
  box-shadow: inset 0 -3px 0 var(--cpmm-active-tab-accent), 0 0 0 1px var(--cpmm-active-tab-shadow) !important;
}
div[data-testid="stSegmentedControl"] button p,
div[data-testid="stSegmentedControl"] button span,
div[data-testid="stButtonGroup"] button p,
div[data-testid="stButtonGroup"] button span,
button[data-testid="stBaseButton-segmentedControl"] p,
button[data-testid="stBaseButton-segmentedControl"] span,
button[data-testid="stBaseButton-segmentedControlActive"] p,
button[data-testid="stBaseButton-segmentedControlActive"] span,
div[data-testid="stButtonGroup"] [role="button"] p,
div[data-testid="stButtonGroup"] [role="button"] span,
div[data-testid="stButtonGroup"] [role="radio"] p,
div[data-testid="stButtonGroup"] [role="radio"] span {
  color: var(--cpmm-ink-blue) !important;
  font-size: 0.94rem !important;
  font-weight: 800 !important;
}

/* Active tab text should stay dark-blue and bold even when Streamlit theme tries to color it red. */
div[data-testid="stSegmentedControl"] button[data-testid="stBaseButton-segmentedControlActive"] p,
div[data-testid="stSegmentedControl"] button[data-testid="stBaseButton-segmentedControlActive"] span,
div[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmentedControlActive"] p,
div[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmentedControlActive"] span,
button[data-testid="stBaseButton-segmentedControlActive"] p,
button[data-testid="stBaseButton-segmentedControlActive"] span {
  color: var(--cpmm-ink-blue) !important;
  font-weight: 850 !important;
  overflow: visible !important;
}


/* Streamlit st.tabs used inside detail workspaces, e.g. Tendon Profile.
   Streamlit 1.5x renders React-Aria tabs as div[data-testid="stTab"], while
   older builds use buttons.  Role selectors keep both DOM variants on-theme. */
div[data-testid="stTabs"] [role="tablist"] {
  gap: 0.38rem !important;
  padding: 0.34rem 0.42rem !important;
  margin: 0.28rem 0 0.68rem 0 !important;
  border: 1px solid #c8d8e9 !important;
  border-radius: 9px !important;
  background: #eef4fb !important;
  overflow-x: auto !important;
}
div[data-testid="stTabs"] [role="tab"],
div[data-testid="stTabs"] div[data-testid="stTab"] {
  color: var(--cpmm-ink-blue) !important;
  font-size: 0.91rem !important;
  font-weight: 800 !important;
  min-height: 2.18rem !important;
  padding: 0.42rem 0.86rem !important;
  border-radius: 7px !important;
  border: 1px solid #b8cbe0 !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(11, 58, 102, 0.07) !important;
  white-space: nowrap !important;
}
div[data-testid="stTabs"] [role="tab"] p,
div[data-testid="stTabs"] [role="tab"] span {
  color: var(--cpmm-ink-blue) !important;
  font-size: 0.91rem !important;
  font-weight: 800 !important;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"],
div[data-testid="stTabs"] [role="tab"][data-selected="true"] {
  background: var(--cpmm-active-tab-fill) !important;
  border-color: var(--cpmm-active-tab-border) !important;
  box-shadow: inset 0 -3px 0 var(--cpmm-active-tab-accent), 0 1px 3px var(--cpmm-active-tab-shadow) !important;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] p,
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] span,
div[data-testid="stTabs"] [role="tab"][data-selected="true"] p,
div[data-testid="stTabs"] [role="tab"][data-selected="true"] span {
  color: var(--cpmm-ink-blue) !important;
  font-weight: 850 !important;
  overflow: visible !important;
}
div[data-testid="stTabs"] [role="tab"] .react-aria-SelectionIndicator {
  display: none !important;
}

/* Radio fallback navigation styled as app tabs, not as ordinary radio text. */
div[data-testid="stRadio"] > label {
  color: var(--cpmm-ink-blue) !important;
  font-size: 0.84rem !important;
  font-weight: 780 !important;
  margin-bottom: 0.24rem !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] {
  gap: 0 !important;
  margin: 0.1rem 0 0.65rem 0;
}
div[data-testid="stRadio"] div[role="radiogroup"] label {
  border: 1px solid var(--cpmm-blue-border);
  border-right: 0;
  border-radius: 0;
  background: #ffffff;
  min-height: 2.18rem;
  padding: 0.24rem 0.84rem;
  color: var(--cpmm-ink-blue);
  font-size: 0.9rem;
  font-weight: 760;
  display: inline-flex;
  align-items: center;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:first-child {
  border-radius: 7px 0 0 7px;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:last-child {
  border-right: 1px solid var(--cpmm-blue-border);
  border-radius: 0 7px 7px 0;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background: var(--cpmm-active-tab-fill);
  color: var(--cpmm-ink-blue);
  border-color: var(--cpmm-active-tab-border);
  box-shadow: inset 0 -3px 0 var(--cpmm-active-tab-accent), 0 0 0 1px var(--cpmm-active-tab-shadow);
}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) + label {
  border-left-color: var(--cpmm-ink-blue-soft);
}
div[data-testid="stRadio"] div[role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
div[data-testid="stRadio"] div[role="radiogroup"] label p,
div[data-testid="stRadio"] div[role="radiogroup"] label span {
  color: var(--cpmm-ink-blue) !important;
  font-size: 0.94rem !important;
  font-weight: 800 !important;
}

/* Deterministic app-owned navigation: active option is rendered from session_state,
   so the highlight does not depend on Streamlit selected-state DOM internals. */
.cpmm-nav-label {
  color: var(--cpmm-ink-blue);
  font-size: 0.88rem;
  font-weight: 800;
  margin: 0.10rem 0 0.08rem 0;
}
.cpmm-deterministic-nav-row,
.cpmm-deterministic-nav-row--compact {
  margin: 0.02rem 0 0.48rem 0; /* previous compact baseline: 0.01rem 0 0.34rem */
}
.cpmm-deterministic-nav-row--compact .stButton button,
.cpmm-deterministic-nav-row--compact .stButton button p,
.cpmm-deterministic-nav-row--compact .stButton button span {
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow-wrap: normal !important;
  min-width: 108px !important;
}
.cpmm-nav-tab-pill {
  width: 100%;
  min-height: 1.92rem; /* previous compact baseline: min-height: 1.64rem */
  border: 1px solid var(--cpmm-blue-border);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.24rem 0.72rem;
  color: var(--cpmm-ink-blue);
  font-size: 0.84rem;
  font-weight: 900;
  line-height: 1.08;
  white-space: nowrap;
  min-width: 108px;
}
.cpmm-nav-tab-active {
  background: var(--cpmm-active-tab-fill);
  border-color: var(--cpmm-active-tab-border);
  box-shadow: inset 0 -2px 0 var(--cpmm-active-tab-accent), 0 1px 1px var(--cpmm-active-tab-shadow);
}

/* Action buttons: commercial-style bold dark-blue text.
   UI.COMMERCIAL4.3.2 migrates primary/action buttons to the app blue accent
   so Run, Save, Upload/Load, Apply, Replace, Append, and confirm actions read
   as active controls in the same language as selected navigation. */
.stButton button,
.stDownloadButton button,
div[data-testid="stFormSubmitButton"] button {
  color: var(--cpmm-ink-blue) !important;
  font-weight: 800 !important;
  font-size: 0.86rem !important;
  min-height: 1.68rem !important;
  padding: 0.22rem 0.64rem !important;
  border-radius: 5px !important;
  border-color: var(--cpmm-blue-border) !important;
}
.stButton button[kind="primary"],
.stDownloadButton button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, var(--cpmm-action-fill), var(--cpmm-action-fill-hover)) !important;
  color: #ffffff !important;
  border-color: var(--cpmm-action-border) !important;
  font-weight: 850 !important;
  box-shadow: inset 0 -2px 0 rgba(7, 55, 99, 0.20) !important;
}
.stButton button[kind="primary"] p,
.stDownloadButton button[kind="primary"] p,
div[data-testid="stFormSubmitButton"] button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p,
.stButton button[kind="primary"] span,
.stDownloadButton button[kind="primary"] span,
div[data-testid="stFormSubmitButton"] button[kind="primary"] span,
button[data-testid="stBaseButton-primary"] span {
  color: #ffffff !important;
  font-weight: 850 !important;
}
.stButton button:hover,
.stDownloadButton button:hover,
div[data-testid="stFormSubmitButton"] button:hover {
  color: var(--cpmm-ink-blue) !important;
  border-color: var(--cpmm-ink-blue) !important;
  background: var(--cpmm-blue-fill-strong) !important;
}
.stButton button[kind="primary"]:hover,
.stDownloadButton button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
  color: #ffffff !important;
  border-color: var(--cpmm-action-border-hover) !important;
  background: linear-gradient(135deg, var(--cpmm-action-fill-hover), #0f5ec2) !important;
}
/* UI.ACTION.BUTTONS2: disabled action buttons must not look ready to run. */
.stButton button:disabled,
.stDownloadButton button:disabled,
div[data-testid="stFormSubmitButton"] button:disabled,
button[data-testid="stBaseButton-primary"]:disabled,
button[data-testid="stBaseButton-secondary"]:disabled {
  background: var(--cpmm-action-disabled-fill) !important;
  color: var(--cpmm-action-disabled-text) !important;
  border-color: var(--cpmm-action-disabled-border) !important;
  box-shadow: none !important;
  opacity: 1 !important;
  cursor: not-allowed !important;
}
.stButton button:disabled p,
.stDownloadButton button:disabled p,
div[data-testid="stFormSubmitButton"] button:disabled p,
button[data-testid="stBaseButton-primary"]:disabled p,
button[data-testid="stBaseButton-secondary"]:disabled p,
.stButton button:disabled span,
.stDownloadButton button:disabled span,
div[data-testid="stFormSubmitButton"] button:disabled span,
button[data-testid="stBaseButton-primary"]:disabled span,
button[data-testid="stBaseButton-secondary"]:disabled span {
  color: var(--cpmm-action-disabled-text) !important;
  font-weight: 800 !important;
}
/* Compact runtime status cards keep the PMM run area readable without large metrics. */
.cpmm-runtime-compact-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.45rem;
  margin-top: 0.42rem;
}
.cpmm-runtime-compact-card {
  border: 1px solid #d9e2ec;
  background: #fbfdff;
  border-radius: 6px;
  padding: 0.42rem 0.58rem;
  min-height: 2.9rem;
}
.cpmm-runtime-compact-card .cpmm-kicker {
  color: #55708b;
  font-size: 0.70rem;
  font-weight: 760;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.cpmm-runtime-compact-card .cpmm-value {
  color: var(--cpmm-ink-blue);
  font-size: 1.02rem;
  font-weight: 850;
  line-height: 1.25;
  margin-top: 0.14rem;
}
@media (max-width: 900px) {
  .cpmm-runtime-compact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
/* Upload controls have a built-in Browse button; keep only the dropzone
   Browse button in the soft action language. Do not style every button under
   stFileUploader: uploaded-file pills also contain remove (x) buttons, and
   broad button selectors can make those native controls hard to click. */
div[data-testid="stFileUploaderDropzone"] button {
  background: #e8f1ff !important;
  color: var(--cpmm-ink-blue) !important;
  border-color: #9fb9d4 !important;
  font-weight: 850 !important;
}
div[data-testid="stFileUploaderDropzone"] button:hover {
  background: #d9eafe !important;
  border-color: #1d6fe7 !important;
}

/* Labels for user input points and selectable/editable controls. */
div[data-testid="stWidgetLabel"] label,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stTextArea"] label,
div[data-testid="stDateInput"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stToggle"] label,
div[data-testid="stDataFrame"] label,
div[data-testid="stDataEditor"] label {
  color: var(--cpmm-ink-blue) !important;
  font-weight: 760 !important;
}

/* Field text and select display values should read as engineering inputs. */
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="select"] div,
div[data-baseweb="base-input"] input {
  color: var(--cpmm-ink-blue) !important;
  font-weight: 650 !important;
}

/* Section/card headings that tell the user where to act. */
h2, h3, h4,
div[data-testid="stMarkdownContainer"] h2,
div[data-testid="stMarkdownContainer"] h3,
div[data-testid="stMarkdownContainer"] h4 {
  color: var(--cpmm-ink-blue);
  font-weight: 760;
}

/* UI.THEME1: visual-only commercial engineering theme foundation.
   This layer intentionally changes color, spacing, cards, and table chrome only.
   It does not add, remove, move, or rename widgets and it does not affect session-state keys. */
:root {
  --cpmm-theme-navy: #071a33;
  --cpmm-theme-navy-2: #0b2545;
  --cpmm-theme-navy-3: #102f55;
  --cpmm-theme-bg: #f4f7fb;
  --cpmm-theme-panel: #ffffff;
  --cpmm-theme-panel-soft: #f8fbff;
  --cpmm-theme-line: #d7e2ee;
  --cpmm-theme-shadow: rgba(7, 26, 51, 0.08);
  --cpmm-theme-shadow-strong: rgba(7, 26, 51, 0.14);
  --cpmm-theme-cyan: #3aa0c4;
  --cpmm-theme-amber: #f6b84b;
}
html, body, [data-testid="stAppViewContainer"] {
  background: var(--cpmm-theme-bg) !important;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #071a33 0%, #0b2545 100%) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.10) !important;
}
section[data-testid="stSidebar"] *:not(input):not(textarea):not(option):not(svg):not(path) {
  color: #eef6ff !important;
}
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] label,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p {
  color: #d9e8f7 !important;
  font-weight: 750 !important;
}
section[data-testid="stSidebar"] div[data-baseweb="select"] *,
section[data-testid="stSidebar"] div[data-baseweb="input"] input,
section[data-testid="stSidebar"] div[data-baseweb="base-input"] input,
section[data-testid="stSidebar"] textarea {
  color: #071a33 !important;
}
section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stDownloadButton button {
  background: #0f335d !important;
  color: #f7fbff !important;
  border-color: #3a5f88 !important;
}
section[data-testid="stSidebar"] .stButton button[kind="primary"],
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
  background: #1f8fb3 !important;
  border-color: #58c3e3 !important;
  color: #ffffff !important;
  box-shadow: inset 0 -2px 0 rgba(255, 255, 255, 0.18) !important;
}
.block-container {
  background: transparent !important;
}
div[data-testid="stAppViewBlockContainer"] > div[data-testid="stVerticalBlock"] {
  background: transparent !important;
}
/* Top-level cards and Streamlit containers. */
div[data-testid="stMetric"],
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"],
div[data-testid="stPlotlyChart"],
div[data-testid="stPyplot"],
div[data-testid="stImage"] {
  border-radius: 9px !important;
}
/* UI.COMMERCIAL4.5: soften Streamlit metric cards.  Metrics are dashboard
   summaries, not primary actions; keep the blue accent in border/value only. */
div[data-testid="stMetric"] {
  background: linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%) !important;
  border: 1px solid #cfe0ff !important;
  border-left: 5px solid #1d6fe7 !important;
  box-shadow: 0 3px 10px rgba(29, 111, 231, 0.08) !important;
  padding: 0.50rem 0.66rem !important;
}
div[data-testid="stMetric"] label,
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
  color: #526f8d !important;
  font-weight: 900 !important;
  letter-spacing: 0.035em !important;
  text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
  color: #175cd3 !important;
  font-weight: 950 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  color: #166534 !important;
  font-weight: 800 !important;
}
/* UI.COMMERCIAL4.4: light-blue accordion system. Dark navy remains reserved for
   structural/brand emphasis; expanders now behave as lightweight group controls. */
div[data-testid="stExpander"] details {
  border: 1px solid #cfe0ff !important;
  border-radius: 9px !important;
  overflow: hidden !important;
  background: #ffffff !important;
  box-shadow: 0 2px 8px rgba(29, 111, 231, 0.08) !important;
}
div[data-testid="stExpander"] details > summary {
  background: linear-gradient(90deg, #f4f8ff 0%, #eef5ff 82%, #e7f1ff 100%) !important;
  border-bottom: 1px solid #cfe0ff !important;
  min-height: 2.0rem !important;
  padding: 0.44rem 0.75rem !important;
}
div[data-testid="stExpander"] details[open] > summary {
  background: linear-gradient(90deg, #eaf2ff 0%, #e0ecff 100%) !important;
  border-bottom-color: #b7d0ff !important;
}
div[data-testid="stExpander"] details > summary p,
div[data-testid="stExpander"] details > summary span,
div[data-testid="stExpander"] details > summary div {
  color: #123a6b !important;
  font-weight: 850 !important;
  letter-spacing: 0.006em !important;
}
div[data-testid="stExpander"] details > summary svg {
  color: #1d6fe7 !important;
  fill: #1d6fe7 !important;
}
div[data-testid="stExpander"] details > div[role="group"] {
  background: #ffffff !important;
  padding-top: 0.56rem !important;
}
/* Data tables/editors: stronger engineering grid chrome without touching editor behavior. */
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
  border: 1px solid var(--cpmm-theme-line) !important;
  background: var(--cpmm-theme-panel) !important;
  box-shadow: 0 2px 8px var(--cpmm-theme-shadow) !important;
  overflow: hidden !important;
}
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataEditor"] [role="columnheader"],
div[data-testid="stDataFrame"] [data-testid="stTableStyledCell"],
div[data-testid="stDataEditor"] [data-testid="stTableStyledCell"] {
  font-weight: 800 !important;
}
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataEditor"] [role="columnheader"] {
  color: var(--cpmm-theme-navy) !important;
}
/* Plots sit inside report-like panels. */
div[data-testid="stPlotlyChart"],
div[data-testid="stPyplot"] {
  border: 1px solid var(--cpmm-theme-line) !important;
  background: #ffffff !important;
  box-shadow: 0 2px 8px var(--cpmm-theme-shadow) !important;
  padding: 0.35rem !important;
}
/* Existing custom cards should pick up the darker professional result style. */
.cpmm-analysis-strip,
.cpmm-analysis-card,
.cpmm-governing-card,
.cpmm-prestress-chip,
.cpmm-prestress-kv-panel,
.cpmm-prestress-note-panel,
.cpmm-dashboard-card,
.cpmm-summary-strip,
.cpmm-compact-panel,
.cpmm-runtime-compact-card {
  border-color: var(--cpmm-theme-line) !important;
  box-shadow: 0 2px 8px var(--cpmm-theme-shadow) !important;
}
.cpmm-analysis-title,
.cpmm-card-title,
.cpmm-summary-title,
.cpmm-prestress-chip-label,
.cpmm-prestress-kv-label,
.cpmm-governing-label,
.cpmm-runtime-compact-card .cpmm-kicker {
  color: #526f8d !important;
  font-weight: 850 !important;
  letter-spacing: 0.025em !important;
  text-transform: uppercase !important;
}
.cpmm-analysis-value,
.cpmm-card-value,
.cpmm-summary-value,
.cpmm-prestress-chip-value,
.cpmm-prestress-kv-value,
.cpmm-governing-value,
.cpmm-runtime-compact-card .cpmm-value {
  color: var(--cpmm-theme-navy) !important;
  font-weight: 900 !important;
}
.cpmm-executive-header {
  background: linear-gradient(90deg, var(--cpmm-theme-navy) 0%, var(--cpmm-theme-navy-2) 74%, #123e6d 100%) !important;
  border-color: #183f6b !important;
  box-shadow: 0 4px 14px var(--cpmm-theme-shadow-strong) !important;
}
.cpmm-executive-eyebrow,
.cpmm-executive-title,
.cpmm-executive-subtitle {
  color: #f7fbff !important;
}
.cpmm-sls-action-panel,
.cpmm-prestress-mode-card {
  border-left: 5px solid var(--cpmm-theme-cyan) !important;
  border-color: var(--cpmm-theme-line) !important;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%) !important;
  box-shadow: 0 2px 8px var(--cpmm-theme-shadow) !important;
}
.cpmm-decision-banner,
.cpmm-prestress-table-note,
.cpmm-prestress-quiet-note {
  box-shadow: 0 2px 8px var(--cpmm-theme-shadow) !important;
}
/* Streamlit alerts and callouts: cleaner border and density. */
div[data-testid="stAlert"] {
  border-radius: 8px !important;
  border: 1px solid var(--cpmm-theme-line) !important;
  box-shadow: 0 2px 8px rgba(7, 26, 51, 0.05) !important;
}
/* Forms and inputs get a more deliberate engineering-software feel. */
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="select"],
div[data-baseweb="textarea"],
textarea,
input {
  border-radius: 6px !important;
}
/* Header text polish under the global brand. */
div[data-testid="stMarkdownContainer"] h2 {
  border-bottom: 2px solid #d7e2ee !important;
  padding-bottom: 0.18rem !important;
}
div[data-testid="stMarkdownContainer"] h3 {
  color: var(--cpmm-theme-navy) !important;
}


/* UI.COMMERCIAL4: premium app shell, sidebar rail, and centered commercial canvas. */
.stApp {
  background: linear-gradient(135deg, #f4f8fd 0%, #f7fbff 48%, #eef5ff 100%) !important;
}
.block-container {
  max-width: 1720px !important;
  padding-left: 1.45rem !important;
  padding-right: 1.45rem !important;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 44%, #e7f1ff 100%) !important;
  border-right: 1px solid rgba(11, 58, 102, 0.22) !important;
  box-shadow: 12px 0 30px rgba(7, 26, 51, 0.085) !important;
}
section[data-testid="stSidebar"] * {
  text-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton button {
  min-height: 2.10rem !important;
  border-radius: 10px !important;
  border-color: #a9c4df !important;
  background: #ffffff !important;
  color: #0b3a66 !important;
  font-weight: 900 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .stButton button p,
section[data-testid="stSidebar"] .stButton button span {
  color: #0b3a66 !important;
  font-weight: 900 !important;
}
section[data-testid="stSidebar"] > div {
  padding-top: 1.05rem !important;
}
.cpmm-sidebar-brand {
  border-bottom: 1px solid rgba(11, 58, 102, 0.12);
  padding: 0.20rem 0.20rem 0.92rem 0.20rem;
  margin-bottom: 0.72rem;
}
.cpmm-sidebar-brand-title {
  color: #061b35 !important;
  font-size: 1.22rem;
  line-height: 1.08;
  font-weight: 950;
  letter-spacing: -0.015em;
}
.cpmm-sidebar-brand-subtitle {
  margin-top: 0.42rem;
  color: #344054 !important;
  font-size: 0.80rem;
  line-height: 1.34;
  font-weight: 650;
}
.cpmm-sidebar-section-label {
  color: #0b3a66 !important;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 0.82rem 0 0.38rem 0.10rem;
}
.cpmm-sidebar-active-pill,
.cpmm-sidebar-sub-active-pill {
  display: flex;
  align-items: center;
  gap: 0.50rem;
  width: 100%;
  border-radius: 11px;
  padding: 0.55rem 0.66rem;
  background: linear-gradient(135deg, #175cd3, #2f80ed);
  color: #ffffff;
  font-size: 0.86rem;
  font-weight: 900;
  box-shadow: 0 9px 20px rgba(23, 92, 211, 0.22);
  margin: 0.22rem 0;
}
.cpmm-sidebar-sub-active-pill {
  background: linear-gradient(135deg, #175cd3, #2f80ed);
  font-size: 0.78rem;
  padding: 0.44rem 0.58rem;
  box-shadow: 0 7px 16px rgba(23, 92, 211, 0.20);
}
.cpmm-sidebar-status {
  border: 1px solid rgba(11, 58, 102, 0.20);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  padding: 0.78rem 0.78rem;
  box-shadow: 0 10px 24px rgba(7, 26, 51, 0.09);
  margin-top: 0.86rem;
}
.cpmm-sidebar-status-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.50rem;
  align-items: center;
  margin: 0.42rem 0;
}
.cpmm-sidebar-status-dot {
  width: 25px;
  height: 25px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 950;
  font-size: 0.74rem;
  background: #e8f1ff;
  color: #175cd3;
}
.cpmm-sidebar-status-dot.ready { background: #dcfce7; color: #16833a; }
.cpmm-sidebar-status-dot.warning { background: #fef3c7; color: #b45309; }
.cpmm-sidebar-status-title {
  color: #526f8d !important;
  font-size: 0.64rem;
  font-weight: 950;
  letter-spacing: 0.055em;
  text-transform: uppercase;
}
.cpmm-sidebar-status-value {
  color: #061b35 !important;
  font-size: 0.85rem;
  font-weight: 950;
  margin-top: 0.04rem;
  line-height: 1.22;
}

/* UI.COMMERCIAL4.1: sidebar contrast cleanup.  Older dark-sidebar
   selectors intentionally remain for backward compatibility, but the new
   premium light rail must keep readable ink colors. */
.cpmm-sidebar-brand-title,
.cpmm-sidebar-status-value { color: #061b35 !important; }
.cpmm-sidebar-brand-subtitle { color: #344054 !important; }
.cpmm-sidebar-section-label { color: #0b3a66 !important; }
.cpmm-sidebar-status-title { color: #526f8d !important; }
.cpmm-sidebar-active-pill, .cpmm-sidebar-active-pill *,
.cpmm-sidebar-sub-active-pill, .cpmm-sidebar-sub-active-pill * { color: #ffffff !important; }

/* UI.COMMERCIAL4.2: harden sidebar contrast and mini-status readability. */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #eef6ff 0%, #ffffff 44%, #eaf3ff 100%) !important;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] * {
  opacity: 1 !important;
  filter: none !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand {
  background: rgba(255, 255, 255, 0.72) !important;
  border: 1px solid rgba(11, 58, 102, 0.16) !important;
  border-radius: 14px !important;
  padding: 0.70rem 0.72rem 0.76rem 0.72rem !important;
  margin-bottom: 0.84rem !important;
  box-shadow: 0 8px 20px rgba(7, 26, 51, 0.07) !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand-title {
  color: #062348 !important;
  font-size: 1.18rem !important;
  font-weight: 950 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand-subtitle {
  color: #243b53 !important;
  font-size: 0.78rem !important;
  font-weight: 750 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-section-label,
section[data-testid="stSidebar"] .cpmm-sidebar-status .cpmm-sidebar-section-label {
  color: #073763 !important;
  font-weight: 950 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-status {
  background: linear-gradient(180deg, #ffffff 0%, #f2f8ff 100%) !important;
  border: 1px solid rgba(7, 55, 99, 0.30) !important;
  box-shadow: 0 12px 26px rgba(7, 26, 51, 0.12) !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-status-title {
  color: #34536f !important;
  font-weight: 950 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-status-value {
  color: #061b35 !important;
  font-weight: 950 !important;
  opacity: 1 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-status-dot {
  opacity: 1 !important;
  border: 1px solid rgba(23, 92, 211, 0.16) !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-active-pill,
section[data-testid="stSidebar"] .cpmm-sidebar-sub-active-pill {
  opacity: 1 !important;
  filter: none !important;
}

/* UI.COMMERCIAL4.3: sidebar project file actions and compact context. */
.cpmm-sidebar-context,
.cpmm-sidebar-file {
  border: 1px solid rgba(7, 55, 99, 0.22);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  padding: 0.74rem 0.76rem;
  box-shadow: 0 9px 22px rgba(7, 26, 51, 0.085);
  margin-top: 0.82rem;
}
.cpmm-sidebar-mini-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.12rem;
  padding: 0.28rem 0;
  border-bottom: 1px solid rgba(11, 58, 102, 0.09);
}
.cpmm-sidebar-mini-row:last-child { border-bottom: 0; }
.cpmm-sidebar-mini-label {
  color: #34536f !important;
  font-size: 0.62rem;
  font-weight: 950;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.cpmm-sidebar-mini-value {
  color: #061b35 !important;
  font-size: 0.78rem;
  font-weight: 900;
  line-height: 1.18;
  overflow-wrap: anywhere;
}
.cpmm-sidebar-file-note {
  color: #526f8d !important;
  font-size: 0.70rem;
  line-height: 1.25;
  margin: 0.18rem 0 0.42rem 0;
  font-weight: 650;
}
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button {
  background: linear-gradient(135deg, #1d6fe7, #175cd3) !important;
  border-color: #1d6fe7 !important;
  color: #ffffff !important;
}
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button p,
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button span {
  color: #ffffff !important;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] {
  border: 1px dashed rgba(11, 58, 102, 0.28) !important;
  border-radius: 12px !important;
  background: rgba(255,255,255,0.82) !important;
  padding: 0.28rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] label,
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] small {
  color: #0b3a66 !important;
  font-weight: 750 !important;
}


/* UI.COMMERCIAL4.3.1: sidebar text contrast hotfix.
   Override the older global sidebar ink rule with higher-specificity selectors
   for the new light commercial rail panels. */
section[data-testid="stSidebar"] .cpmm-sidebar-brand,
section[data-testid="stSidebar"] .cpmm-sidebar-status,
section[data-testid="stSidebar"] .cpmm-sidebar-context,
section[data-testid="stSidebar"] .cpmm-sidebar-file {
  opacity: 1 !important;
  filter: none !important;
  color: #061b35 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand *,
section[data-testid="stSidebar"] .cpmm-sidebar-status *,
section[data-testid="stSidebar"] .cpmm-sidebar-context *,
section[data-testid="stSidebar"] .cpmm-sidebar-file * {
  opacity: 1 !important;
  filter: none !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand-title,
section[data-testid="stSidebar"] .cpmm-sidebar-status-value,
section[data-testid="stSidebar"] .cpmm-sidebar-mini-value {
  color: #061b35 !important;
  font-weight: 950 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-brand-subtitle,
section[data-testid="stSidebar"] .cpmm-sidebar-file-note {
  color: #243b53 !important;
  font-weight: 750 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-section-label,
section[data-testid="stSidebar"] .cpmm-sidebar-status-title,
section[data-testid="stSidebar"] .cpmm-sidebar-mini-label {
  color: #0b3a66 !important;
  font-weight: 950 !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-context,
section[data-testid="stSidebar"] .cpmm-sidebar-file {
  background: linear-gradient(180deg, #ffffff 0%, #f2f8ff 100%) !important;
  border: 1px solid rgba(7, 55, 99, 0.34) !important;
  box-shadow: 0 12px 26px rgba(7, 26, 51, 0.12) !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-mini-row {
  border-bottom: 1px solid rgba(11, 58, 102, 0.18) !important;
}
section[data-testid="stSidebar"] .cpmm-sidebar-mini-row:last-child {
  border-bottom: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] {
  background: #ffffff !important;
  border: 1px dashed rgba(7, 55, 99, 0.46) !important;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] *,
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] p,
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] small,
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] label {
  color: #0b3a66 !important;
  opacity: 1 !important;
  font-weight: 800 !important;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploader"] button {
  color: #0b3a66 !important;
  background: #f8fbff !important;
  border-color: #a9c4df !important;
  font-weight: 900 !important;
}

.cpmm-top-brand-shell {
  border: 1px solid rgba(11, 58, 102, 0.11);
  border-radius: 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fbff 56%, #eef6ff 100%);
  padding: 0.82rem 1.02rem;
  margin: 0.20rem 0 0.82rem 0;
  box-shadow: 0 10px 30px rgba(7, 26, 51, 0.065);
}
.cpmm-top-brand-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.86rem;
}
.cpmm-top-brand-logo {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, #0b3a66, #1d6fe7);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  font-weight: 950;
  box-shadow: 0 8px 18px rgba(29, 111, 231, 0.20);
}
.cpmm-top-brand-title {
  color: #071a33;
  font-size: 1.36rem;
  font-weight: 950;
  line-height: 1.12;
}
.cpmm-top-brand-subtitle {
  color: #526f8d;
  font-size: 0.82rem;
  line-height: 1.30;
  margin-top: 0.18rem;
}
.cpmm-top-brand-badge {
  border: 1px solid rgba(29, 111, 231, 0.20);
  border-radius: 999px;
  background: #e8f1ff;
  color: #0b3a66;
  padding: 0.28rem 0.72rem;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.055em;
  text-transform: uppercase;
}
.cpmm-context-summary-shell {
  border: 1px solid rgba(11, 58, 102, 0.10);
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(7, 26, 51, 0.055);
  padding: 0.72rem 0.82rem;
  margin: 0.35rem 0 0.80rem 0;
}
.cpmm-context-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.50rem;
}
.cpmm-context-summary-item {
  border-right: 1px solid #e3eaf3;
  padding: 0.12rem 0.66rem;
  min-width: 0;
}
.cpmm-context-summary-item:last-child { border-right: 0; }
.cpmm-context-summary-label {
  color: #526f8d;
  font-size: 0.66rem;
  font-weight: 950;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 0.16rem;
}
.cpmm-context-summary-value {
  color: #071a33;
  font-size: 0.86rem;
  font-weight: 900;
  line-height: 1.22;
  overflow-wrap: anywhere;
}
@media (max-width: 1100px) {
  .cpmm-context-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cpmm-context-summary-item { border-right: 0; border-bottom: 1px solid #e3eaf3; padding-bottom: 0.42rem; }
}

</style>
"""


def _render_global_commercial_tab_styles() -> None:
    """Apply visual-only tab polish to existing navigation widgets.

    This does not add, move, or remove navigation controls; it only styles the
    existing segmented/radio controls so app tabs read closer to commercial
    engineering software.
    """

    st.markdown(_COMMERCIAL_TAB_CSS, unsafe_allow_html=True)


def _safe_choice(label: str, options: list[str], *, key: str, horizontal: bool = True) -> str:
    """Return one selected option without rendering inactive pages.

    Streamlit tabs execute every tab body on each rerun.  PERF.RERUN1 keeps
    navigation as a single-choice control so only the selected workspace/subpage
    runs.  UI.ACTIVE.TABS1 renders the active item from app state so the
    highlight is deterministic and does not depend on Streamlit's internal DOM.
    """

    return render_active_choice(label, options, key=key, horizontal=horizontal)



def _commercial_workspace_icon(workspace: str) -> str:
    return {
        "Setup": "⚙",
        "Sections": "▦",
        "Loads": "⇩",
        "Analysis": "⌁",
        "Result Summary": "RS",
        "Report / QA": "QA",
    }.get(str(workspace), "•")


def _commercial_subpage_icon(subpage: str) -> str:
    return {
        "Project": "▣",
        "Materials": "⚗",
        "Section Builder": "◇",
        "Rebar": "#",
        "Prestress": "PT",
        "Tendon System": "PT",
        "Segment Layout": "SG",
        "Section / Zone Layout": "ZN",
        "Tendon Profile": "3D",
        "ULS Strength": "ULS",
        "SLS / Stress & Cracking": "SLS",
        "SLS Deflection / Camber": "δ",
        "Report / QA": "QA",
    }.get(str(subpage), "•")


def _analysis_mode_from_session_for_chrome() -> AnalysisModeSettings:
    value = st.session_state.get("analysis_mode_settings")
    if isinstance(value, AnalysisModeSettings):
        return value
    if isinstance(value, dict):
        try:
            return AnalysisModeSettings.model_validate(value)
        except Exception:
            return AnalysisModeSettings()
    return AnalysisModeSettings()


def _current_section_label_for_chrome() -> str:
    return str(st.session_state.get("section_preset_name") or st.session_state.get("section_preset_selector_key") or "Not selected")


def _project_code_label_for_chrome() -> str:
    """Return workflow-compatible Design Code for the always-visible app chrome."""

    return workflow_project_code_label_from_session(st.session_state)


def _render_sidebar_active_context() -> None:
    """Render compact always-visible project context in the left rail."""
    mode = _analysis_mode_from_session_for_chrome()
    st.sidebar.markdown(
        f"""
<div class="cpmm-sidebar-context">
  <div class="cpmm-sidebar-section-label" style="margin-top:0;">Active Context</div>
  <div class="cpmm-sidebar-mini-row"><div class="cpmm-sidebar-mini-label">Workflow</div><div class="cpmm-sidebar-mini-value">{escape(analysis_mode_label(mode))}</div></div>
  <div class="cpmm-sidebar-mini-row"><div class="cpmm-sidebar-mini-label">Section</div><div class="cpmm-sidebar-mini-value">{escape(_current_section_label_for_chrome())}</div></div>
  <div class="cpmm-sidebar-mini-row"><div class="cpmm-sidebar-mini-label">Code</div><div class="cpmm-sidebar-mini-value">{escape(_project_code_label_for_chrome())}</div></div>
  <div class="cpmm-sidebar-mini-row"><div class="cpmm-sidebar-mini-label">Units</div><div class="cpmm-sidebar-mini-value">mm, MPa, N, N-mm</div></div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_sidebar_project_file_actions() -> None:
    """Move project-level save/load actions into the commercial sidebar.

    UI.COMMERCIAL4.3 keeps the existing JSON serialization/loading logic, but
    places file actions in the left rail where project-level actions belong.
    This is UI-only and does not change the project data model.
    """
    with st.sidebar.container(border=True):
        st.markdown('<div class="cpmm-sidebar-section-label" style="margin-top:0;">Project File</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="cpmm-sidebar-file-note">Save or load the complete project JSON before handoff or major edits.</div>',
            unsafe_allow_html=True,
        )
        project = project_from_session_state(st.session_state)
        st.download_button(
            "Save Project JSON",
            data=project_to_json(project),
            file_name="concrete_section_pro_project.json",
            mime="application/json",
            use_container_width=True,
            type="primary",
            key="ui_commercial4_3_sidebar_save_project_json",
        )
        uploaded_file = st.file_uploader(
            "Load Project JSON",
            type=["json"],
            key="ui_commercial4_3_sidebar_project_json_uploader",
        )
        if uploaded_file is not None and st.button(
            "Apply Loaded Project",
            use_container_width=True,
            type="primary",
            key="ui_commercial4_3_sidebar_apply_project_json",
        ):
            try:
                pending_json = uploaded_file.getvalue().decode("utf-8")
                project = project_from_json(pending_json)
                apply_project_to_session_state(project, st.session_state)
            except (UnicodeDecodeError, ProjectIOError) as exc:
                st.session_state["_project_load_error"] = str(exc)
            else:
                st.session_state["_project_load_success"] = (
                    "Project JSON loaded. Review Section Builder, Rebar, Prestress, and Loads tabs before future analysis."
                )
            rerun = getattr(st, "rerun", None)
            if callable(rerun):
                rerun()


def _render_commercial_sidebar(active_workspace: str | None = None) -> None:
    """Render a visual navigation rail without changing the existing page contracts.

    UI.COMMERCIAL4 keeps the top navigation available for backward
    compatibility, but adds a premium sidebar rail that writes to the same
    Streamlit session-state navigation keys when used.
    """
    if st.session_state.get("_nav_active_workspace") == "Results":
        st.session_state["_nav_active_workspace"] = "Result Summary"
    if st.session_state.get("_nav_active_workspace") not in WORKSPACE_NAVIGATION:
        st.session_state["_nav_active_workspace"] = "Setup"
    active = str(active_workspace or st.session_state.get("_nav_active_workspace", "Setup"))

    st.sidebar.markdown(
        """
<div class="cpmm-sidebar-brand">
  <div class="cpmm-sidebar-brand-title">Concrete Section Pro</div>
  <div class="cpmm-sidebar-brand-subtitle">Concrete section analysis and design-review workspace.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="cpmm-sidebar-section-label">Workspace</div>', unsafe_allow_html=True)
    for workspace in WORKSPACE_NAVIGATION:
        if workspace == active:
            st.sidebar.markdown(
                f'<div class="cpmm-sidebar-active-pill"><span>{_commercial_workspace_icon(workspace)}</span><span>{workspace}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            if st.sidebar.button(f"{_commercial_workspace_icon(workspace)}  {workspace}", key=f"_sidebar_workspace_{workspace}", use_container_width=True):
                st.session_state["_nav_active_workspace"] = workspace
                rerun = getattr(st, "rerun", None)
                if callable(rerun):
                    rerun()

    subpages = _workspace_subpages(active)
    if len(subpages) > 1:
        subpage_key = {
            "Setup": "_nav_setup_subpage",
            "Sections": "_nav_sections_subpage",
            "Analysis": "_nav_analysis_subpage",
        }.get(active)
        if subpage_key:
            if st.session_state.get(subpage_key) not in subpages:
                st.session_state[subpage_key] = subpages[0]
            active_subpage = str(st.session_state.get(subpage_key, subpages[0]))
            st.sidebar.markdown('<div class="cpmm-sidebar-section-label">Subpage</div>', unsafe_allow_html=True)
            for subpage in subpages:
                if subpage == active_subpage:
                    st.sidebar.markdown(
                        f'<div class="cpmm-sidebar-sub-active-pill"><span>{_commercial_subpage_icon(subpage)}</span><span>{subpage}</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.sidebar.button(f"{_commercial_subpage_icon(subpage)}  {subpage}", key=f"_sidebar_subpage_{active}_{subpage}", use_container_width=True):
                        st.session_state[subpage_key] = subpage
                        rerun = getattr(st, "rerun", None)
                        if callable(rerun):
                            rerun()

    dirty_status = current_project_dirty_status(st.session_state)
    model_dot = "warning" if dirty_status.model_status == "Modified" else "ready"
    analysis_dot = "warning" if dirty_status.analysis_status == "Out of date" else ("ready" if dirty_status.analysis_status == "Current" else "")
    affected_count = len(dirty_status.affected_checks)
    st.sidebar.markdown(
        f"""
<div class="cpmm-sidebar-status">
  <div class="cpmm-sidebar-section-label" style="margin-top:0;">Project Status</div>
  <div class="cpmm-sidebar-status-row">
    <span class="cpmm-sidebar-status-dot {model_dot}">●</span>
    <div><div class="cpmm-sidebar-status-title">Model</div><div class="cpmm-sidebar-status-value">{escape(dirty_status.model_status)}</div></div>
  </div>
  <div class="cpmm-sidebar-status-row">
    <span class="cpmm-sidebar-status-dot {analysis_dot}">●</span>
    <div><div class="cpmm-sidebar-status-title">Analysis</div><div class="cpmm-sidebar-status-value">{escape(dirty_status.analysis_status)}</div></div>
  </div>
  <div class="cpmm-sidebar-status-row">
    <span class="cpmm-sidebar-status-dot">{affected_count}</span>
    <div><div class="cpmm-sidebar-status-title">Affected Checks</div><div class="cpmm-sidebar-status-value">{escape(', '.join(dirty_status.affected_checks[:2]) if dirty_status.affected_checks else 'None')}</div></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    _render_sidebar_active_context()
    _render_sidebar_project_file_actions()


def _render_commercial_brand_header(active_workspace: str) -> None:
    st.markdown(
        f"""
<div class="cpmm-top-brand-shell">
  <div class="cpmm-top-brand-row">
    <div class="cpmm-top-brand-logo">CS</div>
    <div>
      <div class="cpmm-top-brand-title">Concrete Section Pro</div>
      <div class="cpmm-top-brand-subtitle">Professional concrete section analysis and design-review workspace · Internal units: mm, MPa, N, N-mm.</div>
    </div>
    <div class="cpmm-top-brand-badge">{escape(active_workspace)} Workspace</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_engineering_context_summary(active_workspace: str) -> None:
    mode = _analysis_mode_from_session_for_chrome()
    section_label = _current_section_label_for_chrome()
    code_label = _project_code_label_for_chrome()
    st.markdown(
        f"""
<div class="cpmm-context-summary-shell">
  <div class="cpmm-context-summary-grid">
    <div class="cpmm-context-summary-item"><div class="cpmm-context-summary-label">Workspace</div><div class="cpmm-context-summary-value">{escape(active_workspace)}</div></div>
    <div class="cpmm-context-summary-item"><div class="cpmm-context-summary-label">Active Workflow</div><div class="cpmm-context-summary-value">{escape(analysis_mode_label(mode))}</div></div>
    <div class="cpmm-context-summary-item"><div class="cpmm-context-summary-label">Section Type / Preset</div><div class="cpmm-context-summary-value">{escape(section_label)}</div></div>
    <div class="cpmm-context-summary-item"><div class="cpmm-context-summary-label">Design Code</div><div class="cpmm-context-summary-value">{escape(code_label)}</div></div>
    <div class="cpmm-context-summary-item"><div class="cpmm-context-summary-label">Units</div><div class="cpmm-context-summary-value">mm, MPa, N, N-mm</div></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_setup_workspace() -> None:
    active = _safe_choice("Setup workspace", WORKSPACE_NAVIGATION["Setup"], key="_nav_setup_subpage")
    if active == "Project":
        render_project_page()
    elif active == "Materials":
        render_materials_page()


def render_sections_workspace() -> None:
    options = _sections_navigation_options()
    active = _safe_choice("Sections workspace", options, key="_nav_sections_subpage")
    if active == "Section Builder":
        render_section_builder()
    elif active == "Rebar":
        mode = _analysis_mode_from_session_for_chrome()
        if is_portal_frame_crossbeam_workflow(mode):
            render_crossbeam_rebar_page()
        else:
            render_rebar_page()
    elif active == "Prestress":
        render_prestress_page()
    elif active == "Tendon System":
        render_crossbeam_tendon_system_page()
    elif active in {"Segment Layout", "Section / Zone Layout"}:
        # One shared route and one canonical layout source; only the visible label
        # changes with Construction Type.
        render_crossbeam_segment_layout_page()
    elif active == "Tendon Profile":
        render_crossbeam_tendon_profile_page()
    elif active == "Prestress Loss":
        render_crossbeam_prestress_loss_page()


def render_loads_workspace() -> None:
    render_loads_page()


def render_analysis_workspace() -> None:
    render_analysis_page()



_RESULTS_DASHBOARD_CSS = """
<style>
.cpmm-results-dashboard-grid {
  display: grid;
  grid-template-columns: 1.18fr 2.35fr;
  gap: 0.72rem;
  align-items: start;
  margin: 0.45rem 0 0.75rem 0;
}
.cpmm-results-executive-card {
  border: 1px solid #d7e2ee;
  border-left: 5px solid #1d6fe7;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  padding: 0.86rem 0.92rem;
  box-shadow: 0 5px 14px rgba(7, 26, 51, 0.045);
}
.cpmm-results-executive-card.ready { border-left-color: #22a447; background: linear-gradient(180deg, #ffffff 0%, #f5fff7 100%); }
.cpmm-results-executive-card.warning { border-left-color: #f59e0b; background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%); }
.cpmm-results-executive-card.danger { border-left-color: #d92d20; background: linear-gradient(180deg, #ffffff 0%, #fff6f5 100%); }
.cpmm-results-executive-card.neutral { border-left-color: #98a2b3; background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%); }
.cpmm-results-kicker {
  color: #526f8d;
  font-size: 0.66rem;
  font-weight: 950;
  letter-spacing: 0.075em;
  text-transform: uppercase;
  margin-bottom: 0.16rem;
}
.cpmm-results-title {
  color: #071a33;
  font-size: 1.04rem;
  font-weight: 950;
  line-height: 1.16;
}
.cpmm-results-detail {
  color: #667085;
  font-size: 0.76rem;
  line-height: 1.38;
  margin-top: 0.24rem;
}
.cpmm-results-status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.18rem 0.54rem;
  font-size: 0.70rem;
  font-weight: 900;
  line-height: 1;
  white-space: nowrap;
  border: 1px solid transparent;
}
.cpmm-results-status-pill.ready { color: #166534; background: #e9f9ef; border-color: rgba(34, 164, 71, 0.18); }
.cpmm-results-status-pill.warning { color: #92400e; background: #fff4d6; border-color: rgba(245, 158, 11, 0.20); }
.cpmm-results-status-pill.danger { color: #b42318; background: #fee4e2; border-color: rgba(217, 45, 32, 0.20); }
.cpmm-results-status-pill.info { color: #1849a9; background: #e8f1ff; border-color: rgba(29, 111, 231, 0.18); }
.cpmm-results-status-pill.neutral { color: #475467; background: #eef2f6; border-color: rgba(152, 162, 179, 0.18); }
.cpmm-results-table-shell {
  border: 1px solid #d7e2ee;
  border-radius: 14px;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 5px 14px rgba(7, 26, 51, 0.040);
}
.cpmm-results-table {
  width: 100%;
  border-collapse: collapse;
}
.cpmm-results-table thead th {
  background: linear-gradient(180deg, #f8fbff 0%, #f2f7ff 100%);
  color: #526f8d;
  font-size: 0.70rem;
  font-weight: 950;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  text-align: left;
  padding: 0.66rem 0.72rem;
  border-bottom: 1px solid #d7e2ee;
}
.cpmm-results-table tbody td {
  color: #071a33;
  font-size: 0.78rem;
  line-height: 1.40;
  padding: 0.68rem 0.72rem;
  border-bottom: 1px solid #e9eef5;
  vertical-align: top;
}
.cpmm-results-table tbody tr:last-child td { border-bottom: 0; }
.cpmm-results-table .module-name { font-weight: 850; color: #0b3a66; }
.cpmm-results-empty {
  border: 1px dashed #b8d0f5;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
  padding: 0.80rem 0.95rem;
  color: #0b3a66;
  font-size: 0.82rem;
  line-height: 1.42;
}
.cpmm-results-beam-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.62rem;
  margin: 0.50rem 0 0.78rem 0;
}
.cpmm-results-beam-card {
  border: 1px solid #d7e2ee;
  border-left: 4px solid #1d6fe7;
  border-radius: 13px;
  background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
  padding: 0.66rem 0.72rem;
  min-height: 134px;
  box-shadow: 0 4px 12px rgba(7, 26, 51, 0.040);
}
.cpmm-results-beam-card.ready { border-left-color: #22a447; background: linear-gradient(180deg, #ffffff 0%, #f5fff7 100%); }
.cpmm-results-beam-card.warning { border-left-color: #f59e0b; background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%); }
.cpmm-results-beam-card.danger { border-left-color: #d92d20; background: linear-gradient(180deg, #ffffff 0%, #fff6f5 100%); }
.cpmm-results-beam-card.neutral { border-left-color: #98a2b3; background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%); }
.cpmm-results-beam-kicker {
  color: #526f8d;
  font-size: 0.60rem;
  font-weight: 950;
  letter-spacing: 0.070em;
  text-transform: uppercase;
  margin-bottom: 0.12rem;
}
.cpmm-results-beam-title {
  color: #071a33;
  font-size: 0.94rem;
  font-weight: 950;
  line-height: 1.12;
  margin-bottom: 0.28rem;
}
.cpmm-results-beam-metric {
  color: #0b3a66;
  font-size: 0.80rem;
  line-height: 1.36;
  margin-top: 0.15rem;
}
.cpmm-results-beam-metric strong {
  color: #071a33;
  font-weight: 900;
}
.cpmm-results-beam-action {
  color: #667085;
  font-size: 0.70rem;
  line-height: 1.30;
  margin-top: 0.34rem;
  padding-top: 0.32rem;
  border-top: 1px solid #e9eef5;
}
@media (max-width: 1200px) {
  .cpmm-results-beam-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .cpmm-results-beam-grid { grid-template-columns: 1fr; }
}
@media (max-width: 1050px) {
  .cpmm-results-dashboard-grid { grid-template-columns: 1fr; }
}
</style>
"""


def _results_style_for_status(status: object) -> str:
    label = str(status or "").strip().upper()
    normalized = label.replace("_", " ").replace("-", " ")
    if "PREVIEW FAIL" in normalized:
        return "danger"
    if "PREVIEW PASS" in normalized:
        return "ready"
    if any(token in normalized for token in ["NOT READY", "NOT CALCULATED", "NOT RUN", "INCOMPLETE", "STALE", "PLANNED", "PLACEHOLDER", "DATA REQUIRED"]):
        return "warning"
    if any(token in normalized for token in ["FAIL", "ERROR", "DANGER", "EXCEED", "BLOCKED"]):
        return "danger"
    if any(token in normalized for token in ["REVIEW", "WARNING"]):
        return "warning"
    if any(token in normalized for token in ["N/A", "NOT ACTIVE", "NONE", "NO RESULT"]):
        return "neutral"
    if any(token in normalized for token in ["PASS", "READY", "AVAILABLE", "CURRENT", "CALCULATED", "BELOW THRESHOLD", "CLEAR"]):
        return "ready"
    return "info"


def _results_status_pill(status: object) -> str:
    label = escape(str(status or "-"))
    return f'<span class="cpmm-results-status-pill {_results_style_for_status(status)}">{label}</span>'


def _results_html_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return '<div class="cpmm-results-empty">No stored result rows are available yet. Run checks in Analysis, then return here to review the stored decision summary.</div>'
    header = "<thead><tr>" + "".join(f"<th>{escape(column)}</th>" for column in columns) + "</tr></thead>"
    body_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for column in columns:
            value = row.get(column, "-")
            if column == "Status":
                cells.append(f"<td>{_results_status_pill(value)}</td>")
            elif column in {"Module", "Check"}:
                cells.append(f'<td><div class="module-name">{escape(str(value))}</div></td>')
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<div class="cpmm-results-table-shell"><table class="cpmm-results-table">' + header + "<tbody>" + "".join(body_rows) + "</tbody></table></div>"


def _results_dataframe(value: object) -> pd.DataFrame | None:
    return value if isinstance(value, pd.DataFrame) else None


def _results_best_row(df: pd.DataFrame | None) -> dict[str, object] | None:
    if df is None or df.empty:
        return None
    work_df = df.copy()
    for col in ["Utilization value", "D/C value", "Overall D/C value", "Governing D/C value"]:
        if col in work_df.columns:
            numeric = pd.to_numeric(work_df[col], errors="coerce")
            if numeric.notna().any():
                return dict(work_df.loc[numeric.idxmax()].to_dict())
    return dict(work_df.iloc[0].to_dict())



def _results_design_code_label(state: object) -> str:
    """Return the workflow-compatible design code shown on Result Summary dashboards."""

    try:
        return workflow_project_code_label_from_session(state)
    except Exception:
        return "Project design code not resolved"


def _results_beam_sls_stage_summary_df(state: object) -> pd.DataFrame | None:
    """Return stored Beam/Girder full-length SLS stage rows from Analysis, if any.

    The Beam/Girder SLS workspace can show stage stress graphs without creating
    the legacy ``serviceability_summary`` object.  Result Summary must therefore
    read this normalized, read-only handoff package before declaring SLS as not
    calculated.
    """

    for key in (
        "result_summary_beam_girder_sls_stage_summary_df",
        "beam_girder_sls_stage_summary_df",
        "railway_u_girder_sls_stage_summary_df",
    ):
        df = _results_dataframe(state.get(key)) if hasattr(state, "get") else None
        if df is not None and not df.empty:
            return df.copy()
    raw_rows = state.get("result_summary_beam_girder_sls_stage_summary_rows") if hasattr(state, "get") else None
    if isinstance(raw_rows, list) and raw_rows:
        df = pd.DataFrame(raw_rows)
        return df if not df.empty else None
    return None


def _results_sls_stress_available(state: object) -> bool:
    serviceability = state.get("serviceability_summary") if hasattr(state, "get") else None
    if serviceability is not None and bool(getattr(serviceability, "stress_results", [object()])):
        return True
    if bool(state.get("railway_u_girder_sls_report_package_available")) if hasattr(state, "get") else False:
        return True
    try:
        if _results_railway_u_girder_sls_decision_dataframe(state) is not None:
            return True
    except NameError:
        pass
    return _results_beam_sls_stage_summary_df(state) is not None


def _results_sls_complete_for_report(state: object) -> bool:
    """Return whether SLS is complete enough for Report / QA handoff.

    Stage stress diagrams alone are useful stored results, but they remain a
    partial serviceability package until a formal SLS summary/report package is
    available.
    """

    if not hasattr(state, "get"):
        return False
    serviceability = state.get("serviceability_summary")
    if serviceability is not None and bool(getattr(serviceability, "stress_results", [object()])):
        return True
    if bool(state.get("railway_u_girder_sls_report_package_available")):
        return True
    try:
        return _results_railway_u_girder_sls_decision_dataframe(state) is not None
    except NameError:
        return False


def _results_sls_stage_governing_row(state: object) -> dict[str, object] | None:
    df = _results_beam_sls_stage_summary_df(state)
    if df is None or df.empty:
        return None
    work = df.copy()
    if "Utilization" in work.columns:
        numeric = pd.to_numeric(work["Utilization"], errors="coerce")
        if numeric.notna().any():
            return dict(work.loc[numeric.idxmax()].to_dict())
    return dict(work.iloc[0].to_dict())



def _results_railway_u_girder_sls_decision_dataframe(state: object) -> pd.DataFrame | None:
    """Return stored/normalized Railway U-Girder staged SLS decision rows.

    The Result Summary dashboard prefers data cached by the SLS preview page.  A
    guarded report-package fallback keeps the dashboard from incorrectly saying
    ``Not calculated`` when the Railway U-Girder staged SLS workflow has enough
    current model data to expose the same report-ready decision table.  This
    function does not add UI buttons and does not trigger PMM/ULS/SLS solver
    actions from Result Summary.
    """

    for key in (
        "railway_u_girder_sls_decision_summary_df",
        "railway_u_girder_sls_decision_summary",
        "railway_u_girder_sls_report_decision_summary",
    ):
        df = _results_dataframe(state.get(key) if hasattr(state, "get") else None)
        if df is not None and not df.empty:
            return df.copy()
    try:
        package = build_railway_u_girder_sls_report_package(state)
    except Exception:
        return None
    decision = _results_dataframe(getattr(package, "decision_summary", None))
    if bool(getattr(package, "available", False)) and decision is not None and not decision.empty:
        return decision.copy()
    return None


def _results_railway_sls_status(decision_df: pd.DataFrame | None) -> str:
    if decision_df is None or decision_df.empty or "Decision" not in decision_df.columns:
        return "NOT CALCULATED"
    statuses = {str(value).strip().upper() for value in decision_df["Decision"].tolist()}
    if any("FAIL" in status or "EXCEED" in status for status in statuses):
        return "FAIL"
    if any("REVIEW" in status or "WARNING" in status for status in statuses):
        return "REVIEW"
    if any("PASS" in status for status in statuses):
        return "PREVIEW PASS"
    return "AVAILABLE"


def _results_railway_sls_governing_row(decision_df: pd.DataFrame | None) -> dict[str, object] | None:
    if decision_df is None or decision_df.empty:
        return None
    work = decision_df.copy()
    if "Max utilization" in work.columns:
        util = pd.to_numeric(work["Max utilization"], errors="coerce")
        if util.notna().any():
            return dict(work.loc[util.idxmax()].to_dict())
    if "Decision" in work.columns:
        review_rows = work[work["Decision"].astype(str).str.upper().str.contains("REVIEW|FAIL|EXCEED", regex=True, na=False)]
        if not review_rows.empty:
            return dict(review_rows.iloc[0].to_dict())
    return dict(work.iloc[0].to_dict())


def _results_railway_sls_max_utilization(decision_df: pd.DataFrame | None) -> str:
    if decision_df is None or decision_df.empty or "Max utilization" not in decision_df.columns:
        return "-"
    values = pd.to_numeric(decision_df["Max utilization"], errors="coerce").dropna()
    if values.empty:
        return "-"
    return f"{float(values.max()):.3f}"


def _results_sls_stage_action(governing: Mapping[str, object] | None) -> str:
    """Return an engineering-specific action for a governing staged SLS row."""

    row = governing or {}
    stage = _results_scalar(row.get("Stage") or row.get("Check stage"))
    case = _results_scalar(row.get("Case Name") or row.get("Governing source"))
    station = _results_scalar(row.get("Station x (m)"))
    fiber = _results_scalar(row.get("Fiber"))
    controls = _results_scalar(row.get("Controls") or row.get("Control"))
    util = _results_scalar(row.get("Utilization") or row.get("Max utilization"))
    limit = _results_scalar(row.get("Limit profile") or row.get("Section basis"))

    location_parts = []
    if station != "-":
        location_parts.append(f"x = {station} m")
    if fiber != "-":
        location_parts.append(f"{fiber} fiber")
    location = " / ".join(location_parts) if location_parts else "governing location"
    case_label = f" ({case})" if case != "-" else ""

    if util != "-":
        return (
            f"Review {stage}{case_label} {controls.lower()} at {location}; utilization = {util}. "
            "Adjust lifting/support stage assumptions, release strength, prestress losses, temporary reinforcement, or section/stage geometry before Report / QA."
        )
    if limit != "-":
        return f"Review {stage}{case_label} at {location} against {limit} before Report / QA."
    return "Review governing staged SLS stress, stress-limit profile, load attribution, and project-specific limits."


def _results_railway_sls_review_action(decision_df: pd.DataFrame | None) -> str:
    governing = _results_railway_sls_governing_row(decision_df) or {}
    action = str(governing.get("Review action") or "").strip()
    if action:
        return action
    status = _results_railway_sls_status(decision_df)
    if "FAIL" in status or "EXCEED" in status:
        return _results_sls_stage_action(governing)
    if "REVIEW" in status:
        return _results_sls_stage_action(governing)
    if "PASS" in status:
        return "Review guarded SLS preview assumptions before final report issue."
    return "Run or refresh staged SLS stress checks before Report / QA."

def _results_sls_available(state: object) -> bool:
    return _results_sls_stress_available(state)


def _results_beam_uls_completion(state: object) -> tuple[int, int, list[str]]:
    rows = _results_beam_uls_summary_rows(state)
    calculated = sum(1 for row in rows if bool(row.get("__calculated")))
    missing = [str(row.get("Check")) for row in rows if not bool(row.get("__calculated"))]
    return calculated, len(rows), missing


def _results_has_stored_uls_rows(rows: list[dict[str, object]]) -> bool:
    return any(str(row.get("Module", "")).strip().upper().startswith("ULS") for row in rows)


def _results_report_handoff_state(state: object, rows: list[dict[str, object]] | None = None) -> dict[str, str]:
    """Return a read-only Report / QA readiness state for the summary dashboard.

    Result Summary is a downstream decision dashboard; it must never make Report
    / QA look ready when no ULS/SLS result has actually been stored by Analysis.
    """

    result_rows = rows if rows is not None else _results_governing_rows(state)
    if not result_rows:
        return {
            "status": "warning",
            "value": "Not ready",
            "detail": "No stored Analysis result set is available for Report / QA.",
        }
    styles = [_results_style_for_status(row.get("Status")) for row in result_rows]
    if "danger" in styles:
        return {
            "status": "danger",
            "value": "Review required",
            "detail": "Resolve failed checks or document engineering acceptance before report issue.",
        }
    if not _results_has_stored_uls_rows(result_rows):
        return {
            "status": "warning",
            "value": "Not ready",
            "detail": "Complete stored ULS summaries before Report / QA handoff.",
        }
    if not _results_sls_complete_for_report(state):
        detail = "Complete stored SLS summaries before Report / QA handoff."
        if _results_sls_stress_available(state):
            detail = "SLS stage stress results are stored, but formal SLS/report handoff summary is still partial."
        return {
            "status": "warning",
            "value": "Not ready",
            "detail": detail,
        }
    if "warning" in styles:
        return {
            "status": "warning",
            "value": "Review required",
            "detail": "Stored results contain review items or guarded scope notes.",
        }
    return {
        "status": "ready",
        "value": "Ready",
        "detail": "Stored ULS and SLS summaries are available for Report / QA review.",
    }


def _results_next_engineering_action(state: object, rows: list[dict[str, object]] | None = None) -> dict[str, str]:
    result_rows = rows if rows is not None else _results_governing_rows(state)
    styles = [_results_style_for_status(row.get("Status")) for row in result_rows]
    if "danger" in styles:
        return {
            "status": "danger",
            "value": "Resolve blocking check(s)",
            "detail": "At least one stored ULS/SLS result is FAIL, BLOCKED, or exceeds its limit.",
        }

    calculated, total, missing = _results_beam_uls_completion(state)
    if 0 < calculated < total:
        return {
            "status": "warning",
            "value": "Complete ULS checks",
            "detail": "Run missing Beam/Girder ULS checks in Analysis: " + ", ".join(missing),
        }
    if not _results_has_stored_uls_rows(result_rows):
        return {
            "status": "warning",
            "value": "Run ULS analysis",
            "detail": "No stored ULS result set is available for the active workflow.",
        }
    if not _results_sls_stress_available(state):
        return {
            "status": "warning",
            "value": "Run SLS Stress & Cracking",
            "detail": "ULS results may be available, but SLS serviceability is still not calculated.",
        }
    if not _results_sls_complete_for_report(state):
        return {
            "status": "warning",
            "value": "Complete SLS handoff",
            "detail": "SLS stage stress results are stored; complete formal SLS summary/report handoff before Report / QA.",
        }
    return {
        "status": "ready",
        "value": "Open Report / QA",
        "detail": "Stored ULS and SLS result summaries are available for traceability review.",
    }


def _results_required_action_rows(state: object, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for row in rows:
        style = _results_style_for_status(row.get("Status"))
        if style in {"danger", "warning"}:
            actions.append(
                {
                    "Priority": "High" if style == "danger" else "Medium",
                    "Module": row.get("Module", "-"),
                    "Issue": f"{row.get('Check', '-')} — {row.get('Status', '-')}",
                    "Required Action": row.get("Required Action", row.get("Source", "Review source Analysis check.")),
                }
            )
    if not _results_has_stored_uls_rows(rows):
        actions.append(
            {
                "Priority": "High",
                "Module": "ULS",
                "Issue": "ULS not calculated",
                "Required Action": "Run ULS Strength checks in Analysis before accepting this section or issuing Report / QA.",
            }
        )
    calculated, total, missing = _results_beam_uls_completion(state)
    if 0 < calculated < total:
        actions.append(
            {
                "Priority": "Medium",
                "Module": "ULS Beam/Girder",
                "Issue": "Partial ULS result set",
                "Required Action": "Run missing checks in Analysis: " + ", ".join(missing),
            }
        )
    if not _results_sls_stress_available(state):
        actions.append(
            {
                "Priority": "High" if actions == [] else "Medium",
                "Module": "SLS",
                "Issue": "SLS not calculated",
                "Required Action": "Run SLS Stress & Cracking before Report / QA.",
            }
        )
    elif not _results_sls_complete_for_report(state):
        actions.append(
            {
                "Priority": "Medium",
                "Module": "SLS",
                "Issue": "SLS stress stored; report summary partial",
                "Required Action": "Review stored SLS stage stress results and complete SLS report/cracking handoff before Report / QA.",
            }
        )
    if not actions:
        actions.append(
            {
                "Priority": "Review",
                "Module": "Report / QA",
                "Issue": "No blocking issue in stored summaries",
                "Required Action": "Open Report / QA and review traceability, assumptions, and limitations.",
            }
        )
    return actions


def _render_results_next_action_card(state: object, rows: list[dict[str, object]]) -> None:
    action = _results_next_engineering_action(state, rows)
    render_metric_cards(
        [
            {
                "title": "Next engineering action",
                "value": action["value"],
                "detail": action["detail"],
                "status": action["status"],
            }
        ]
    )


def _render_results_required_actions(state: object, rows: list[dict[str, object]]) -> None:
    action_rows = _results_required_action_rows(state, rows)
    st.markdown(
        _RESULTS_DASHBOARD_CSS
        + _results_html_table(
            action_rows,
            ["Priority", "Module", "Issue", "Required Action"],
        ),
        unsafe_allow_html=True,
    )


def _results_sls_summary_cards(state: object) -> list[dict[str, object]]:
    serviceability = state.get("serviceability_summary")
    stage_df = _results_beam_sls_stage_summary_df(state)
    stage_governing = _results_sls_stage_governing_row(state)
    railway_decision = _results_railway_u_girder_sls_decision_dataframe(state)
    code_label = _results_design_code_label(state)
    if serviceability is None and stage_df is None and railway_decision is None and not bool(state.get("railway_u_girder_sls_report_package_available")):
        return [
            {
                "title": "Design code",
                "value": code_label,
                "detail": "workflow-compatible project code basis",
                "status": "info",
            },
            {
                "title": "SLS status",
                "value": "Not calculated",
                "detail": "Run SLS Stress & Cracking in Analysis",
                "status": "warning",
            },
            {
                "title": "Governing stage",
                "value": "-",
                "detail": "no stored SLS stage result",
                "status": "neutral",
            },
            {
                "title": "Required action",
                "value": "Run SLS",
                "detail": "SLS is required before Report / QA readiness",
                "status": "warning",
            },
        ]
    if serviceability is None and railway_decision is not None:
        status = _results_railway_sls_status(railway_decision)
        governing = _results_railway_sls_governing_row(railway_decision) or {}
        if stage_governing is not None and _results_style_for_status(stage_governing.get("Status")) == "danger":
            status = _results_scalar(stage_governing.get("Status"))
            governing = stage_governing
            action_detail = _results_sls_stage_action(stage_governing)
            governing_value = _results_scalar(stage_governing.get("Stage"))
            governing_detail = f"{_results_scalar(stage_governing.get('Case Name'))} · {_results_scalar(stage_governing.get('Station x (m)'))} m / {_results_scalar(stage_governing.get('Fiber'))}"
            util_value = _results_scalar(stage_governing.get("Utilization"))
        else:
            action_detail = _results_railway_sls_review_action(railway_decision)
            governing_value = _results_scalar(governing.get("Check stage"))
            governing_detail = _results_scalar(governing.get("Governing x / case"))
            util_value = _results_railway_sls_max_utilization(railway_decision)
        return [
            {
                "title": "Design code",
                "value": code_label,
                "detail": "Railway U-Girder staged SLS preview basis",
                "status": "info",
            },
            {
                "title": "SLS status",
                "value": status,
                "detail": f"{len(railway_decision):,} Railway U-Girder staged SLS decision row(s)",
                "status": _results_style_for_status(status),
            },
            {
                "title": "Governing stage",
                "value": governing_value,
                "detail": governing_detail,
                "status": _results_style_for_status(status),
            },
            {
                "title": "Max utilization",
                "value": util_value,
                "detail": action_detail,
                "status": _results_style_for_status(status),
            },
        ]
    if serviceability is None and stage_df is not None:
        util = None if stage_governing is None else stage_governing.get("Utilization")
        try:
            util_text = "-" if util is None else f"{float(util):.3f}"
        except (TypeError, ValueError):
            util_text = "-"
        stage_status = str(stage_governing.get("Status", "PARTIAL") if stage_governing else "PARTIAL")
        return [
            {
                "title": "Design code",
                "value": code_label,
                "detail": str(stage_governing.get("Limit profile", "stage stress limit profile") if stage_governing else "stage stress limit profile"),
                "status": "info",
            },
            {
                "title": "SLS status",
                "value": stage_status if _results_style_for_status(stage_status) == "danger" else "Partial / stress stored",
                "detail": f"{len(stage_df):,} stored stage stress summary row(s); formal SLS/report handoff still pending",
                "status": "warning" if _results_style_for_status(stage_status) != "danger" else "danger",
            },
            {
                "title": "Governing stage",
                "value": str(stage_governing.get("Stage", "-") if stage_governing else "-"),
                "detail": str(stage_governing.get("Case Name", "stored full-length stage stress") if stage_governing else "stored full-length stage stress"),
                "status": _results_style_for_status(stage_status),
            },
            {
                "title": "Max utilization",
                "value": util_text,
                "detail": str(stage_governing.get("Controls", "stress utilization") if stage_governing else "stress utilization"),
                "status": _results_style_for_status(stage_status),
            },
        ]
    status = str(getattr(serviceability, "overall_status", "AVAILABLE")) if serviceability is not None else "AVAILABLE"
    util = getattr(serviceability, "max_utilization", None) if serviceability is not None else None
    return [
        {
            "title": "Design code",
            "value": code_label,
            "detail": "workflow-compatible project code basis",
            "status": "info",
        },
        {
            "title": "SLS status",
            "value": status,
            "detail": "stored serviceability summary",
            "status": _results_style_for_status(status),
        },
        {
            "title": "Governing case",
            "value": str(getattr(serviceability, "governing_combo", "-")) if serviceability is not None else "-",
            "detail": "critical stored SLS case",
            "status": "info",
        },
        {
            "title": "Max utilization",
            "value": "-" if util is None else f"{float(util):.3f}",
            "detail": "demand / applicable service limit",
            "status": "ready" if util is not None and float(util) <= 1.0 else ("danger" if util is not None else "neutral"),
        },
    ]


def _render_results_sls_dashboard(state: object) -> None:
    render_metric_cards(_results_sls_summary_cards(state))
    rows: list[dict[str, object]] = []
    _results_add_sls_rows(state, rows)
    if rows:
        st.markdown(
            _RESULTS_DASHBOARD_CSS
            + _results_html_table(
                rows,
                ["Module", "Check", "Status", "Code Basis", "Governing Case", "Station / Point", "Demand", "Capacity / Limit", "D/C / Util.", "Required Action", "Source"],
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            _RESULTS_DASHBOARD_CSS
            + '<div class="cpmm-results-empty">No stored SLS result rows are available yet. Run SLS Stress & Cracking in Analysis before Report / QA.</div>',
            unsafe_allow_html=True,
        )


def _results_utilization_values(value: object) -> list[float]:
    """Extract all numeric utilization ratios from compact summary text.

    Result Summary rows can contain multiple decision ratios, for example
    ``Strength D/C 0.422; Av/s min D/C 1.893``.  Critical-check ranking must
    consider the controlling detailing/source ratio, not only the first token or
    the nominal interaction ratio.
    """

    text = str(value or "")
    values: list[float] = []
    for match in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text.replace(",", "")):
        try:
            numeric = float(match)
        except ValueError:
            continue
        if pd.notna(numeric):
            values.append(numeric)
    return values


def _results_parse_utilization(value: object) -> float | None:
    values = _results_utilization_values(value)
    return max(values) if values else None


def _results_critical_label(row: Mapping[str, object] | None) -> str:
    if not row:
        return "-"
    module = str(row.get("Module") or "-").strip()
    check = str(row.get("Check") or "").strip()
    if module == "ULS Beam/Girder" and check:
        return f"ULS {check}"
    if module == "SLS Stress":
        return "SLS Stress"
    if check and check not in module:
        return f"{module} · {check}"
    return module or "-"


def _results_failing_check_summary(rows: list[dict[str, object]], *, limit: int = 3) -> str:
    failing = [row for row in rows if _results_style_for_status(row.get("Status")) == "danger"]
    if not failing:
        return ""
    ranked = sorted(
        failing,
        key=lambda row: (_results_parse_utilization(row.get("D/C / Util.")) or -1.0),
        reverse=True,
    )
    parts: list[str] = []
    for row in ranked[:limit]:
        util = str(row.get("D/C / Util.") or "-").strip()
        status = str(row.get("Status") or "-").strip()
        label = _results_critical_label(row)
        if util and util != "-":
            parts.append(f"{label} ({status}; {util})")
        else:
            parts.append(f"{label} ({status})")
    extra = len(ranked) - limit
    if extra > 0:
        parts.append(f"+{extra} more")
    return "; ".join(parts)


def _results_critical_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    if not rows:
        return None
    danger_rows = [row for row in rows if _results_style_for_status(row.get("Status")) == "danger"]
    warning_rows = [row for row in rows if _results_style_for_status(row.get("Status")) == "warning"]
    candidates = danger_rows or warning_rows or rows
    ranked: list[tuple[float, int, dict[str, object]]] = []
    for index, row in enumerate(candidates):
        util = _results_parse_utilization(row.get("D/C / Util."))
        ranked.append(((util if util is not None else -1.0), -index, row))
    return sorted(ranked, key=lambda item: (item[0], item[1]), reverse=True)[0][2]


def _results_availability_cards(state: object) -> list[dict[str, object]]:
    beam_cache = state.get("_beam_girder_uls_manual_calculation_cache") if isinstance(state.get("_beam_girder_uls_manual_calculation_cache"), dict) else {}
    pmm_available = state.get("rc_demand_capacity_result") is not None or state.get("rc_pmm_result") is not None
    code_label = _results_design_code_label(state)
    rows = _results_governing_rows(state)
    uls_rows = [row for row in rows if str(row.get("Module", "")).upper().startswith("ULS")]
    uls_count = sum(1 for entry in beam_cache.values() if isinstance(entry, dict))
    column_vt_available = _results_column_pier_vt_dataframe(state) is not None
    sls_available = _results_sls_stress_available(state)
    sls_complete = _results_sls_complete_for_report(state)
    executive = _results_executive_status(rows, state)
    critical = _results_critical_row(rows)
    handoff = _results_report_handoff_state(state, rows)
    has_blocking_result = any(_results_style_for_status(row.get("Status")) == "danger" for row in rows)
    has_review_result = any(_results_style_for_status(row.get("Status")) == "warning" for row in rows)
    completeness_detail = ("Column/Pier V+T stored; " if column_vt_available else "") + (
        f"Beam/Girder ULS checks: {uls_count}" if uls_count else ("PMM stored" if pmm_available else "Run ULS analysis")
    )
    if sls_complete and has_blocking_result:
        completeness_detail += "; SLS complete, but failing check exists"
        completeness_status = "info"
    elif sls_complete and has_review_result:
        completeness_detail += "; SLS complete, review item exists"
        completeness_status = "info"
    elif sls_complete:
        completeness_detail += "; SLS complete"
        completeness_status = "ready" if uls_rows else "warning"
    elif sls_available:
        completeness_detail += "; SLS stage stress stored"
        completeness_status = "warning"
    else:
        completeness_detail += "; SLS pending"
        completeness_status = "warning"

    return [
        {
            "title": "Overall status",
            "value": executive["title"].replace("Overall Status: ", ""),
            "detail": executive["detail"],
            "status": executive["status"],
        },
        {
            "title": "Design code",
            "value": code_label,
            "detail": "workflow-compatible project code basis used by stored Analysis results",
            "status": "info",
        },
        {
            "title": "Critical check",
            "value": "-" if critical is None else _results_critical_label(critical),
            "detail": "No stored governing row" if critical is None else f"{critical.get('Status', '-')} · {critical.get('D/C / Util.', '-')} · {critical.get('Governing Case', '-')}",
            "status": "warning" if critical is None else _results_style_for_status(critical.get("Status")),
        },
        {
            "title": "ULS/SLS completeness",
            "value": f"ULS {len(uls_rows)} · SLS {'complete' if sls_complete else ('partial' if sls_available else 'no')}",
            "detail": completeness_detail,
            "status": completeness_status,
        },
        {
            "title": "Report handoff",
            "value": handoff["value"],
            "detail": handoff["detail"],
            "status": handoff["status"],
        },
    ]


def _results_add_pmm_rows(state: object, rows: list[dict[str, object]]) -> None:
    dc_summary = state.get("rc_demand_capacity_result")
    if dc_summary is not None:
        rows.append(
            {
                "Module": "ULS PMM",
                "Check": "Column/Pier PMM",
                "Status": getattr(dc_summary, "overall_status", "REVIEW"),
                "Governing Case": getattr(dc_summary, "governing_combo", None) or "-",
                "Station / Point": "-",
                "Demand": "Pu, Mux, Muy",
                "Capacity / Limit": "PMM envelope",
                "D/C / Util.": "-" if getattr(dc_summary, "max_dcr", None) is None else f"{float(getattr(dc_summary, 'max_dcr')):.3f}",
                "Source": "Analysis → ULS Strength → Flexural (PMM)",
                "Code Basis": _results_design_code_label(state),
            }
        )
        return
    if state.get("rc_pmm_result") is not None:
        rows.append(
            {
                "Module": "ULS PMM",
                "Check": "PMM surface",
                "Status": "AVAILABLE",
                "Governing Case": "-",
                "Station / Point": "-",
                "Demand": "-",
                "Capacity / Limit": "PMM point cloud",
                "D/C / Util.": "-",
                "Source": "Analysis → ULS Strength → Flexural (PMM)",
                "Code Basis": _results_design_code_label(state),
            }
        )



_RESULTS_BEAM_ULS_CHECKS = ["Flexure", "Shear", "Torsion", "Shear + Torsion"]
_RESULTS_BEAM_ULS_DF_KEYS = {
    "Flexure": "flexure_preview_df",
    "Shear": "shear_check_df",
    "Torsion": "torsion_check_df",
    "Shear + Torsion": "combined_vt_df",
}


def _results_scalar(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return "-" if pd.isna(value) else f"{value:.3f}"
    return str(value) if str(value) else "-"


def _results_value_with_unit(value: object, unit: str) -> str:
    """Format a stored result value without duplicating an existing unit suffix."""

    text = _results_scalar(value).strip()
    if text == "-":
        return text
    if unit.lower() in text.lower():
        return text
    return f"{text} {unit}"


def _results_first_existing(row: Mapping[str, object], candidates: list[str], default: object = "-") -> object:
    for candidate in candidates:
        value = row.get(candidate)
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        if str(value) == "":
            continue
        return value
    return default


def _results_beam_uls_cache(state: object) -> dict[str, dict[str, object]]:
    cache = state.get("_beam_girder_uls_manual_calculation_cache") if hasattr(state, "get") else None
    return cache if isinstance(cache, dict) else {}


def _results_beam_uls_best_row(entry: dict[str, object] | None, check_name: str) -> dict[str, object]:
    if not isinstance(entry, dict):
        return {}
    df = _results_dataframe(entry.get(_RESULTS_BEAM_ULS_DF_KEYS.get(check_name, "")))
    if df is None or df.empty:
        return {}
    work_df = df.copy()
    if check_name == "Shear":
        # Keep Result Summary aligned with Analysis > ULS compact table.  The
        # compact Shear row is not simply the maximum strength D/C row: a
        # separate detailing/minimum-reinforcement gate can control and fail the
        # shear check even when strength D/C is below 1.0.
        decision = _beam_uls_shear_decision_summary(work_df)
        decision_row = decision.get("row") if isinstance(decision, dict) else None
        if isinstance(decision_row, Mapping):
            row = dict(decision_row)
            row["__decision_status"] = str(decision.get("status") or row.get("Status") or "REVIEW")
            row["__decision_reason"] = str(decision.get("reason") or "")
            return row
    preferred_columns = {
        "Flexure": ["Utilization value", "D/C value", "Overall D/C value"],
        "Shear": ["Strength D/C value", "D/C value", "Utilization value"],
        "Torsion": ["D/C value", "Utilization value"],
        "Shear + Torsion": ["Overall D/C value", "Transverse D/C value", "Stress D/C value", "Longitudinal D/C value"],
    }.get(check_name, ["Utilization value", "D/C value", "Overall D/C value"])
    for col in preferred_columns:
        if col in work_df.columns:
            numeric = pd.to_numeric(work_df[col], errors="coerce")
            if numeric.notna().any():
                return dict(work_df.loc[numeric.idxmax()].to_dict())
    return dict(work_df.iloc[0].to_dict())


def _results_beam_uls_row_status(check_name: str, row: Mapping[str, object], cache: dict[str, dict[str, object]]) -> str:
    status = str(row.get("__decision_status") or row.get("Status") or "").strip()
    if check_name == "Shear + Torsion":
        shear_row = _results_beam_uls_best_row(cache.get("Shear"), "Shear")
        torsion_row = _results_beam_uls_best_row(cache.get("Torsion"), "Torsion")
        shear_status = str(shear_row.get("__decision_status") or shear_row.get("Status") or "").upper()
        torsion_status = str(torsion_row.get("__decision_status") or torsion_row.get("Status") or "").upper()
        if "FAIL" in shear_status or "FAIL" in torsion_status:
            return "SOURCE BLOCKED"
        if status.upper() == "DATA REQUIRED":
            return "DATA REQUIRED"
    return status or ("CALCULATED" if row else "NOT CALCULATED")


def _results_beam_uls_utilization(check_name: str, row: Mapping[str, object]) -> str:
    if check_name == "Shear" and row:
        # Mirror the Analysis compact table wording so a detailing-controlled
        # shear failure does not appear as a PASS-looking strength D/C only.
        return _beam_uls_shear_utilization_display(row)
    value = _results_first_existing(
        row,
        {
            "Flexure": ["Utilization", "Utilization value", "D/C value"],
            "Shear": ["Strength D/C", "Strength D/C value", "D/C value"],
            "Torsion": ["D/C", "D/C value", "Utilization"],
            "Shear + Torsion": ["Overall D/C", "Overall D/C value", "Transverse D/C", "Transverse D/C value", "Stress D/C", "Stress D/C value"],
        }.get(check_name, ["Utilization", "D/C value", "Overall D/C value"]),
    )
    return _results_scalar(value)


def _results_beam_uls_demand(check_name: str, row: Mapping[str, object]) -> str:
    if check_name == "Flexure":
        return _results_scalar(_results_first_existing(row, ["Demand", "Mu", "Mux kN-m", "Muy kN-m"]))
    if check_name == "Shear":
        return _results_scalar(_results_first_existing(row, ["Demand", "Vu kN", "Vuy kN", "Vux kN"]))
    if check_name == "Torsion":
        tu = _results_first_existing(row, ["Tu kN-m", "Demand"])
        return "-" if tu == "-" else f"Tu = {_results_value_with_unit(tu, 'kN-m')}"
    if check_name == "Shear + Torsion":
        vu = _results_first_existing(row, ["Vu kN", "Vuy kN", "Vux kN"])
        tu = _results_first_existing(row, ["Tu kN-m"])
        if vu != "-" and tu != "-":
            return f"Vu = {_results_value_with_unit(vu, 'kN')}; Tu = {_results_value_with_unit(tu, 'kN-m')}"
        return _results_scalar(_results_first_existing(row, ["Demand", "Vu / Tu"]))
    return _results_scalar(_results_first_existing(row, ["Demand", "Vu / Tu", "Vu kN", "Tu kN-m"]))


def _results_beam_uls_capacity(check_name: str, row: Mapping[str, object]) -> str:
    if check_name == "Flexure":
        return _results_scalar(_results_first_existing(row, ["Capacity", "φMn kN-m", "phiMn kN-m"]))
    if check_name == "Shear":
        return _results_scalar(_results_first_existing(row, ["Capacity", "φVn kN", "phiVn kN"]))
    if check_name == "Torsion":
        return _results_scalar(_results_first_existing(row, ["Capacity", "φTn kN-m", "phiTn kN-m"]))
    return _results_scalar(_results_first_existing(row, ["Capacity", "Capacity / Limit", "Interaction limit", "limit"]))


def _results_beam_uls_action(check_name: str, status: str, row: Mapping[str, object] | None = None) -> str:
    label = status.upper()
    row_map: Mapping[str, object] = row or {}
    if check_name == "Shear + Torsion" and ("SOURCE BLOCKED" in label or "BLOCKED" in label):
        return "Resolve source Shear/Torsion FAIL before accepting V+T interaction. Interaction D/C is informational until source gates pass."
    if check_name == "Shear + Torsion" and "DATA REQUIRED" in label:
        return "Complete required V+T source data before accepting interaction."
    if check_name == "Shear" and "FAIL" in label:
        utilization = _beam_uls_shear_utilization_display(row_map) if row_map else ""
        if "Av/s min" in utilization or "Spacing" in utilization or "detailing" in utilization.lower():
            return f"Resolve minimum stirrup/detailing gate: {utilization}. Increase provided shear reinforcement or reduce stirrup spacing before accepting ULS shear."
        return "Resolve governing shear strength/detailing gate in Analysis → ULS Strength → Shear."
    if "FAIL" in label:
        return "Revise capacity/detailing in the source Analysis check."
    if "PASS" in label or "BELOW THRESHOLD" in label:
        return "Review audit output before final issue."
    if "LAYOUT REQUIRED" in label:
        return "Complete reinforcement layout before acceptance."
    if "NOT CALCULATED" in label:
        return f"Run {check_name} in Analysis."
    return "Review calculated gate and notes."


def _results_beam_uls_summary_rows(state: object) -> list[dict[str, object]]:
    cache = _results_beam_uls_cache(state)
    rows: list[dict[str, object]] = []
    for check_name in _RESULTS_BEAM_ULS_CHECKS:
        entry = cache.get(check_name)
        row = _results_beam_uls_best_row(entry, check_name)
        status = _results_beam_uls_row_status(check_name, row, cache)
        utilization = _results_beam_uls_utilization(check_name, row)
        if check_name == "Shear + Torsion" and str(status).upper() == "SOURCE BLOCKED" and utilization != "-":
            utilization = f"Interaction D/C {utilization}; source gate BLOCKED"
        rows.append(
            {
                "Module": "ULS Beam/Girder",
                "Check": check_name,
                "Status": status,
                "Governing Case": _results_scalar(_results_first_existing(row, ["Case", "Load case", "Case Name"])),
                "Station / Point": _results_scalar(_results_first_existing(row, ["Governing x", "Station x", "Station type"])),
                "Demand": _results_beam_uls_demand(check_name, row),
                "Capacity / Limit": _results_beam_uls_capacity(check_name, row),
                "D/C / Util.": utilization,
                "Required Action": _results_beam_uls_action(check_name, status, row),
                "Source": f"Analysis → ULS Strength → {check_name}",
                "Code Basis": _results_design_code_label(state),
                "__calculated": bool(row),
            }
        )
    return rows


def _render_results_beam_uls_dashboard(state: object) -> None:
    rows = _results_beam_uls_summary_rows(state)
    if not any(bool(row.get("__calculated")) for row in rows):
        st.markdown(
            _RESULTS_DASHBOARD_CSS
            + '<div class="cpmm-results-empty">No stored Beam/Girder ULS results are available yet. Run Flexure, Shear, Torsion, or Shear + Torsion in Analysis first.</div>',
            unsafe_allow_html=True,
        )
        return

    card_html: list[str] = []
    for row in rows:
        status = str(row.get("Status") or "-")
        style = _results_style_for_status(status)
        if status.upper() == "SOURCE BLOCKED":
            style = "danger"
        card_html.append(
            f'<div class="cpmm-results-beam-card {style}">'
            f'<div class="cpmm-results-beam-kicker">{escape(str(row.get("Check", "-")))}</div>'
            f'<div class="cpmm-results-beam-title">{_results_status_pill(status)}</div>'
            f'<div class="cpmm-results-beam-metric"><strong>Case</strong>: {escape(str(row.get("Governing Case", "-")))}</div>'
            f'<div class="cpmm-results-beam-metric"><strong>x</strong>: {escape(str(row.get("Station / Point", "-")))}</div>'
            f'<div class="cpmm-results-beam-metric"><strong>D/C</strong>: {escape(str(row.get("D/C / Util.", "-")))}</div>'
            f'<div class="cpmm-results-beam-action">{escape(str(row.get("Required Action", "-")))}</div>'
            '</div>'
        )
    st.markdown(_RESULTS_DASHBOARD_CSS + '<div class="cpmm-results-beam-grid">' + "".join(card_html) + '</div>', unsafe_allow_html=True)

    display_rows = [
        {
            "Check": row["Check"],
            "Status": row["Status"],
            "Governing Case": row["Governing Case"],
            "Station / Point": row["Station / Point"],
            "Demand": row["Demand"],
            "Capacity / Limit": row["Capacity / Limit"],
            "D/C / Util.": row["D/C / Util."],
            "Code Basis": row.get("Code Basis", _results_design_code_label(state)),
            "Required Action": row["Required Action"],
        }
        for row in rows
        if bool(row.get("__calculated"))
    ]
    st.markdown(
        _RESULTS_DASHBOARD_CSS
        + _results_html_table(
            display_rows,
            ["Check", "Status", "Code Basis", "Governing Case", "Station / Point", "Demand", "Capacity / Limit", "D/C / Util.", "Required Action"],
        ),
        unsafe_allow_html=True,
    )


def _results_add_beam_uls_rows(state: object, rows: list[dict[str, object]]) -> None:
    for row in _results_beam_uls_summary_rows(state):
        if bool(row.get("__calculated")):
            rows.append(
                {
                    "Module": row["Module"],
                    "Check": row["Check"],
                    "Status": row["Status"],
                    "Governing Case": row["Governing Case"],
                    "Station / Point": row["Station / Point"],
                    "Demand": row["Demand"],
                    "Capacity / Limit": row["Capacity / Limit"],
                    "D/C / Util.": row["D/C / Util."],
                    "Source": row["Source"],
                    "Code Basis": row.get("Code Basis", _results_design_code_label(state)),
                }
            )


def _results_column_pier_vt_dataframe(state: object) -> pd.DataFrame | None:
    for key in ("column_pier_combined_vt_result_df", "column_pier_combined_vt_df"):
        df = _results_dataframe(state.get(key))
        if df is not None and not df.empty:
            return df.copy()
    return None


def _results_column_pier_vt_governing_row(df: pd.DataFrame | None) -> dict[str, object] | None:
    if df is None or df.empty:
        return None
    work = df.copy()
    for column in ["Overall D/C value", "Stress D/C value", "Transverse D/C value", "Longitudinal D/C value"]:
        if column not in work.columns:
            work[column] = float("nan")
        work[f"__{column}"] = pd.to_numeric(work[column], errors="coerce")
    work["__Tu"] = pd.to_numeric(work.get("Tu kN-m"), errors="coerce").abs()
    work["__Vu"] = pd.to_numeric(work.get("Vu kN"), errors="coerce").abs()
    ranked = work[work["__Overall D/C value"].notna()].copy()
    if ranked.empty:
        return dict(work.iloc[0].to_dict())
    ranked = ranked.sort_values(
        ["__Overall D/C value", "__Tu", "__Vu"],
        ascending=[False, False, False],
        kind="stable",
    )
    return dict(ranked.iloc[0].to_dict())


def _results_column_pier_vt_overall_status(df: pd.DataFrame | None) -> str:
    if df is None or df.empty or "Status" not in df.columns:
        return "NOT READY"
    statuses = {str(value).strip().upper() for value in df["Status"].tolist()}
    if "FAIL" in statuses:
        return "FAIL"
    if "DATA REQUIRED" in statuses:
        return "DATA REQUIRED"
    if "REVIEW" in statuses:
        return "REVIEW"
    if statuses == {"NOT APPLICABLE"}:
        return "NOT APPLICABLE"
    if "PASS" in statuses:
        return "PASS"
    return "REVIEW"


def _results_column_pier_vt_max_dc(df: pd.DataFrame | None) -> str:
    if df is None or df.empty or "Overall D/C value" not in df.columns:
        return "-"
    values = pd.to_numeric(df["Overall D/C value"], errors="coerce").dropna()
    if values.empty:
        return "-"
    return f"{float(values.max()):.3f}"


def _results_column_pier_vt_action(status: str, cause: str) -> str:
    status_u = str(status or "").upper()
    cause_l = str(cause or "").lower()
    if "FAIL" in status_u:
        if "torsion" in cause_l:
            return "Review Tu demand, closed transverse torsion reinforcement, core geometry, and ordinary longitudinal torsion Al."
        if "shear" in cause_l:
            return "Review Vu demand, transverse reinforcement, effective shear area/core geometry, and source shear strength."
        return "Open Analysis → ULS Strength → Shear + Torsion and resolve the controlling V+T strength gate."
    if "DATA REQUIRED" in status_u or "NOT READY" in status_u:
        return "Complete active Vux/Vuy/Tu demand, closed transverse reinforcement, ordinary longitudinal Al, and section/core geometry."
    if "REVIEW" in status_u:
        return "Review guarded V+T scope, assumptions, and downstream detailing before report issue."
    return "Review seismic/detailing scope guard before Report / QA handoff."


def _results_add_column_pier_vt_rows(state: object, rows: list[dict[str, object]]) -> None:
    df = _results_column_pier_vt_dataframe(state)
    if df is None or df.empty:
        return
    governing = _results_column_pier_vt_governing_row(df) or {}
    status = _results_column_pier_vt_overall_status(df)
    cause = str(state.get("column_pier_combined_vt_controlling_cause") or "-")
    governing_label = str(state.get("column_pier_combined_vt_governing_label") or "").strip()
    if not governing_label:
        governing_label = f"{_results_scalar(governing.get('Case'))} / {_results_scalar(governing.get('Direction'))}"
    rows.append(
        {
            "Module": "ULS Shear + Torsion",
            "Check": "Column/Pier V+T",
            "Status": status,
            "Governing Case": governing_label,
            "Station / Point": "Control section",
            "Demand": f"Vu = {_results_scalar(governing.get('Vu kN'))} kN; Tu = {_results_scalar(governing.get('Tu kN-m'))} kN-m",
            "Capacity / Limit": str(state.get("column_pier_combined_vt_route_label") or "AASHTO/ACI V+T gates"),
            "D/C / Util.": _results_column_pier_vt_max_dc(df),
            "Required Action": _results_column_pier_vt_action(status, cause),
            "Source": "Analysis → ULS Strength → Shear + Torsion",
            "Code Basis": _results_design_code_label(state),
        }
    )


def _render_results_column_pier_vt_dashboard(state: object) -> bool:
    df = _results_column_pier_vt_dataframe(state)
    if df is None or df.empty:
        return False
    rows: list[dict[str, object]] = []
    _results_add_column_pier_vt_rows(state, rows)
    if not rows:
        return False
    render_metric_cards(
        [
            {
                "title": "Column/Pier V+T status",
                "value": rows[0]["Status"],
                "detail": str(state.get("column_pier_combined_vt_controlling_cause") or rows[0]["Required Action"]),
                "status": _results_style_for_status(rows[0]["Status"]),
            },
            {
                "title": "Max D/C",
                "value": rows[0]["D/C / Util."],
                "detail": str(rows[0]["Governing Case"]),
                "status": _results_style_for_status(rows[0]["Status"]),
            },
            {
                "title": "Scope guard",
                "value": "Review required",
                "detail": "Seismic confinement/detailing remains outside this strength gate.",
                "status": "warning",
            },
        ]
    )
    st.markdown(
        _RESULTS_DASHBOARD_CSS
        + _results_html_table(
            rows,
            ["Module", "Check", "Status", "Code Basis", "Governing Case", "Station / Point", "Demand", "Capacity / Limit", "D/C / Util.", "Required Action"],
        ),
        unsafe_allow_html=True,
    )
    screen_df = _results_dataframe(state.get("column_pier_combined_vt_screen_df"))
    if screen_df is not None and not screen_df.empty:
        with st.expander("Stored Column/Pier V+T compact result rows", expanded=False):
            st.dataframe(screen_df, use_container_width=True, hide_index=True)
    return True


def _results_add_sls_rows(state: object, rows: list[dict[str, object]]) -> None:
    serviceability = state.get("serviceability_summary")
    if serviceability is not None:
        rows.append(
            {
                "Module": "SLS Stress",
                "Check": "Elastic stress",
                "Status": getattr(serviceability, "overall_status", "AVAILABLE"),
                "Governing Case": getattr(serviceability, "governing_combo", None) or "-",
                "Station / Point": getattr(serviceability, "governing_point", None) or "-",
                "Demand": (
                    "N/A"
                    if getattr(serviceability, "max_tension_MPa", None) is None
                    else f"Max tension {float(getattr(serviceability, 'max_tension_MPa')):.3f} MPa"
                ),
                "Capacity / Limit": "Project SLS stress limits",
                "D/C / Util.": (
                    "-"
                    if getattr(serviceability, "max_utilization", None) is None
                    else f"{float(getattr(serviceability, 'max_utilization')):.3f}"
                ),
                "Source": "Analysis → SLS / Stress & Cracking",
                "Code Basis": _results_design_code_label(state),
            }
        )
        return

    stage_df = _results_beam_sls_stage_summary_df(state)
    if stage_df is not None and not stage_df.empty:
        governing = _results_sls_stage_governing_row(state) or {}
        rows.append(
            {
                "Module": "SLS Stress",
                "Check": "Beam/Girder stage stress",
                "Status": str(governing.get("Status", "PARTIAL")),
                "Governing Case": str(governing.get("Case Name", "-")),
                "Station / Point": "-" if governing.get("Station x (m)") is None else f"{float(governing.get('Station x (m)')):.3f} m / {governing.get('Fiber', '-')}",
                "Demand": "-" if governing.get("Actual stress (MPa)") is None else f"{governing.get('Controls', 'Stress')} {float(governing.get('Actual stress (MPa)')):.3f} MPa",
                "Capacity / Limit": str(governing.get("Limit profile", "Stored SLS stage stress limit")),
                "D/C / Util.": "-" if governing.get("Utilization") is None else f"{float(governing.get('Utilization')):.3f}",
                "Required Action": _results_sls_stage_action(governing),
                "Source": "Analysis → SLS / Stress & Cracking → staged stress diagram",
                "Code Basis": _results_design_code_label(state),
            }
        )
        return

    stage_df = _results_beam_sls_stage_summary_df(state)
    stage_governing = _results_sls_stage_governing_row(state)
    if serviceability is None and stage_df is not None and stage_governing is not None:
        rows.append(
            {
                "Module": "SLS Stress",
                "Check": "Beam/Girder stage stress",
                "Status": _results_scalar(stage_governing.get("Status")),
                "Governing Case": _results_scalar(stage_governing.get("Case Name")),
                "Station / Point": _results_scalar(stage_governing.get("Station x (m)")),
                "Demand": f"{_results_scalar(stage_governing.get('Actual stress (MPa)'))} MPa",
                "Capacity / Limit": _results_scalar(stage_governing.get("Limit stress (MPa)")),
                "D/C / Util.": _results_scalar(stage_governing.get("Utilization")),
                "Required Action": _results_sls_stage_action(stage_governing),
                "Source": "Analysis → SLS / Stress & Cracking → staged stress diagram",
                "Code Basis": _results_design_code_label(state),
            }
        )

    railway_decision = _results_railway_u_girder_sls_decision_dataframe(state)
    if railway_decision is None or railway_decision.empty:
        return
    for _, item in railway_decision.iterrows():
        status = str(item.get("Decision") or "REVIEW")
        compression = _results_scalar(item.get("Compression (MPa)"))
        tension = _results_scalar(item.get("Tension (MPa)"))
        rows.append(
            {
                "Module": "SLS Railway U-Girder",
                "Check": _results_scalar(item.get("Check stage")),
                "Status": status,
                "Governing Case": _results_scalar(item.get("Governing source")),
                "Station / Point": _results_scalar(item.get("Governing x / case")),
                "Demand": f"Compression {compression} MPa; tension {tension} MPa",
                "Capacity / Limit": _results_scalar(item.get("Section basis")),
                "D/C / Util.": _results_scalar(item.get("Max utilization")),
                "Required Action": _results_sls_stage_action(dict(item.to_dict())),
                "Source": "Analysis → Railway U-Girder staged SLS stress preview",
                "Code Basis": _results_design_code_label(state),
            }
        )


def _results_governing_rows(state: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    _results_add_pmm_rows(state, rows)
    _results_add_column_pier_vt_rows(state, rows)
    _results_add_beam_uls_rows(state, rows)
    _results_add_sls_rows(state, rows)
    return rows


def _results_executive_status(rows: list[dict[str, object]], state: object | None = None) -> dict[str, str]:
    if not rows:
        return {
            "status": "warning",
            "title": "Overall Status: INCOMPLETE",
            "detail": "No stored result set is available yet. Run ULS and SLS checks in Analysis first; Result Summary remains read-only and will not run solvers automatically.",
        }
    styles = [_results_style_for_status(row.get("Status")) for row in rows]
    if "danger" in styles:
        failing_summary = _results_failing_check_summary(rows)
        detail = "At least one stored result indicates FAIL, BLOCKED, or exceedance. Open the source Analysis check before report issue."
        if failing_summary:
            detail = f"Failing checks: {failing_summary}. Open the source Analysis check before report issue."
        return {
            "status": "danger",
            "title": "Overall Status: FAIL",
            "detail": detail,
        }

    beam_rows = _results_beam_uls_summary_rows(state) if state is not None else []
    beam_calculated = sum(1 for row in beam_rows if bool(row.get("__calculated")))
    beam_total = len(beam_rows)
    if 0 < beam_calculated < beam_total:
        missing = ", ".join(str(row.get("Check")) for row in beam_rows if not bool(row.get("__calculated")))
        return {
            "status": "warning",
            "title": "Overall Status: INCOMPLETE",
            "detail": f"{beam_calculated}/{beam_total} Beam/Girder ULS checks have stored results. Missing checks: {missing}.",
        }

    if "warning" in styles:
        return {
            "status": "warning",
            "title": "Overall Status: REVIEW",
            "detail": "Some checks are calculated but still require engineering review, detailing confirmation, or missing companion checks.",
        }
    if beam_total > 0 and beam_calculated == beam_total and state is not None and not _results_sls_stress_available(state):
        return {
            "status": "warning",
            "title": "Overall Status: INCOMPLETE",
            "detail": "All Beam/Girder ULS checks have stored results. SLS serviceability is not calculated yet.",
        }
    if state is not None and not _results_sls_stress_available(state):
        return {
            "status": "warning",
            "title": "Overall Status: INCOMPLETE",
            "detail": "Stored ULS summary is available, but SLS serviceability is not calculated yet.",
        }
    if state is not None and _results_sls_stress_available(state) and not _results_sls_complete_for_report(state):
        return {
            "status": "warning",
            "title": "Overall Status: INCOMPLETE",
            "detail": "Stored ULS summary and SLS stage stress results are available, but formal SLS/report readiness remains partial.",
        }
    return {
        "status": "ready",
        "title": "Overall Status: PASS",
        "detail": "Available stored results are ready for read-only review and downstream Report / QA traceability.",
    }


def _render_results_executive_summary(rows: list[dict[str, object]], state: object | None = None) -> None:
    status = _results_executive_status(rows, state)
    status_html = f"""
<div class="cpmm-results-executive-card {escape(status["status"])}">
  <div class="cpmm-results-kicker">Executive result state</div>
  <div class="cpmm-results-title">{escape(status["title"])}</div>
  <div class="cpmm-results-detail">{escape(status["detail"])}</div>
</div>
"""
    table_html = _results_html_table(
        rows,
        ["Module", "Check", "Status", "Code Basis", "Governing Case", "Station / Point", "Demand", "Capacity / Limit", "D/C / Util.", "Source"],
    )
    st.markdown(
        _RESULTS_DASHBOARD_CSS
        + '<div class="cpmm-results-dashboard-grid">'
        + status_html
        + table_html
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_results_module_tables(state: object) -> None:
    cache = state.get("_beam_girder_uls_manual_calculation_cache")
    if isinstance(cache, dict) and cache:
        with st.expander("ULS Beam/Girder stored result tables", expanded=False):
            for check_name, entry in cache.items():
                if not isinstance(entry, dict):
                    continue
                st.markdown(f"**{check_name}**")
                for key, value in entry.items():
                    if isinstance(value, pd.DataFrame) and not value.empty:
                        st.caption(key)
                        st.dataframe(value, use_container_width=True, hide_index=True)
    serviceability = state.get("serviceability_summary")
    if serviceability is not None:
        with st.expander("SLS stored stress summary", expanded=False):
            st.write(
                {
                    "overall_status": getattr(serviceability, "overall_status", "-"),
                    "governing_combo": getattr(serviceability, "governing_combo", "-"),
                    "governing_point": getattr(serviceability, "governing_point", "-"),
                    "max_utilization": getattr(serviceability, "max_utilization", "-"),
                    "warning_count": len(getattr(serviceability, "warnings", []) or []),
                }
            )
    stage_df = _results_beam_sls_stage_summary_df(state)
    if stage_df is not None and not stage_df.empty:
        with st.expander("Beam/Girder stored SLS stage stress summary", expanded=False):
            st.dataframe(stage_df, use_container_width=True, hide_index=True)
        demand_df = _results_dataframe(state.get("result_summary_beam_girder_sls_demand_detail_df"))
        if demand_df is not None and not demand_df.empty:
            with st.expander("Beam/Girder stored SLS compression/tension demand details", expanded=False):
                st.dataframe(demand_df, use_container_width=True, hide_index=True)



_RESULTS_STATIC_FIG_WIDTH = 980
_RESULTS_STATIC_FIG_HEIGHT = 460


def _results_numeric_plot_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for candidate in candidates:
        if candidate not in df.columns:
            continue
        series = df[candidate]
        if series.dtype == object:
            series = series.map(lambda value: str(value).replace(" m", "").replace("kN-m", "").replace("kN", "").strip())
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any():
            return numeric
    return None


def _results_beam_uls_cached_df(state: object, check_name: str) -> pd.DataFrame | None:
    cache = _results_beam_uls_cache(state)
    entry = cache.get(check_name)
    if not isinstance(entry, dict):
        return None
    return _results_dataframe(entry.get(_RESULTS_BEAM_ULS_DF_KEYS.get(check_name, "")))


def _results_add_line_if_available(fig: go.Figure, df: pd.DataFrame, x_values: pd.Series, *, columns: list[str], name: str, dash: str | None = None) -> bool:
    y_values = _results_numeric_plot_series(df, columns)
    if y_values is None:
        return False
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines+markers",
            name=name,
            line={"dash": dash} if dash else None,
        )
    )
    return True


def _results_beam_uls_cached_figure(state: object, check_name: str) -> go.Figure | None:
    df = _results_beam_uls_cached_df(state, check_name)
    if df is None or df.empty:
        return None
    plot_df = df.copy()
    x_values = _results_numeric_plot_series(plot_df, ["Governing x", "Station x (m)", "x (m)", "x_m"])
    if x_values is None:
        x_values = pd.Series(range(len(plot_df)), dtype="float64")
    fig = go.Figure()
    if check_name == "Flexure":
        y_label = "Moment, Mu (kN-m)"
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Demand kN-m", "Demand", "Mu kN-m"], name="Demand Mu")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Capacity kN-m", "Capacity", "φMn kN-m", "phiMn kN-m"], name="φMn", dash="dash")
    elif check_name == "Shear":
        y_label = "Shear, Vu (kN)"
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Vu kN", "Vuy kN", "Vux kN", "Demand"], name="Vu")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["φVn kN", "phiVn kN", "Capacity"], name="φVn", dash="dash")
    elif check_name == "Torsion":
        y_label = "Torsion, Tu (kN-m)"
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Tu kN-m", "Demand"], name="Tu")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["φTn kN-m", "phiTn kN-m", "Capacity"], name="φTn", dash="dash")
    else:
        y_label = "Demand / Capacity ratio"
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Stress D/C value", "Stress D/C"], name="Stress D/C")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Transverse D/C value", "Transverse D/C"], name="Transverse D/C")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Longitudinal D/C value", "Longitudinal D/C"], name="Long. Al D/C")
        _results_add_line_if_available(fig, plot_df, x_values, columns=["Overall D/C value", "Overall D/C"], name="Overall D/C")
        fig.add_hline(y=1.0, line_dash="dash", annotation_text="Limit = 1.0", annotation_position="top left")
    if not fig.data:
        return None
    fig.update_layout(
        title=f"Stored Beam/Girder ULS — {check_name}",
        xaxis_title="Distance from left end of member (m)",
        yaxis_title=y_label,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    )
    return fig


def _render_results_static_plotly_figure(fig: go.Figure, *, caption: str | None = None) -> None:
    try:
        apply_global_plot_readability(fig)
        fig.update_layout(
            autosize=False,
            width=_RESULTS_STATIC_FIG_WIDTH,
            height=_RESULTS_STATIC_FIG_HEIGHT,
            margin=dict(l=76, r=30, t=78, b=86),
            font=dict(size=11),
            title_font=dict(size=17),
            legend=dict(
                font=dict(size=10),
                orientation="h",
                yanchor="top",
                y=-0.18,
                xanchor="center",
                x=0.5,
                itemwidth=46,
                entrywidth=130,
                entrywidthmode="pixels",
            ),
            hoverlabel=dict(font=dict(size=11)),
        )
        fig.update_xaxes(tickfont=dict(size=10), title_font=dict(size=12))
        fig.update_yaxes(tickfont=dict(size=10), title_font=dict(size=12))
        image_bytes = fig.to_image(
            format="png",
            width=_RESULTS_STATIC_FIG_WIDTH,
            height=_RESULTS_STATIC_FIG_HEIGHT,
            scale=2,
        )
    except Exception as exc:
        st.warning("Static diagram rendering is not available in this environment. Stored result tables remain available below.")
        st.caption(f"Chart export detail: {type(exc).__name__}")
        return
    try:
        st.image(image_bytes, width=_RESULTS_STATIC_FIG_WIDTH, caption=caption)
    except TypeError:
        st.image(image_bytes, use_column_width=False, caption=caption)


def _results_available_diagram_figures(state: object) -> dict[str, go.Figure]:
    available: dict[str, go.Figure] = {}
    for check_name in _RESULTS_BEAM_ULS_CHECKS:
        fig = _results_beam_uls_cached_figure(state, check_name)
        if fig is not None:
            available[f"Beam/Girder ULS · {check_name}"] = fig
    for name, fig in {
        "PMM Mux-Muy slice": state.get("pmm_mux_muy_slice_figure"),
        "PMM 3D interaction": state.get("pmm_interaction_surface_figure"),
    }.items():
        if isinstance(fig, go.Figure):
            available[name] = fig
    return available


def _render_results_diagram_review(state: object) -> None:
    available = _results_available_diagram_figures(state)
    if not available:
        st.caption("No stored result diagrams are available yet. Run checks in Analysis, then return here for read-only diagram review.")
        return
    selected = st.selectbox("Stored result diagram", list(available.keys()), key="results_workspace_selected_diagram")
    _render_results_static_plotly_figure(
        available[selected],
        caption="Read-only stored result diagram. This view is generated from cached result data and does not rerun solvers.",
    )


def _render_results_traceability(state: object) -> None:
    beam_calculated, beam_total, _missing = _results_beam_uls_completion(state)
    railway_sls_available = _results_railway_u_girder_sls_decision_dataframe(state) is not None
    stored_available = bool(beam_calculated) or railway_sls_available or _results_column_pier_vt_dataframe(state) is not None or state.get("serviceability_summary") is not None
    runtime_status = str(state.get("analysis_runtime_last_status") or "").strip()
    if not runtime_status:
        runtime_status = "Read-only summary; stored analysis results available" if stored_available else "Read-only summary; no stored solver result"
    trace_rows = [
        {"Item": "Workflow", "Value": analysis_mode_label(_analysis_mode_from_session_for_chrome())},
        {"Item": "Design code", "Value": _results_design_code_label(state)},
        {"Item": "Project input hash", "Value": str(state.get("project_input_hash") or state.get("analysis_input_hash") or "-")},
        {"Item": "PMM cache hash", "Value": str(state.get("pmm_last_analysis_hash") or "-")},
        {"Item": "Beam/Girder ULS stored checks", "Value": f"{beam_calculated}/{beam_total}"},
        {"Item": "Column/Pier V+T stored", "Value": "Yes" if _results_column_pier_vt_dataframe(state) is not None else "No"},
        {"Item": "Elastic SLS cache hash", "Value": str(state.get("serviceability_summary_hash") or "-")},
        {"Item": "Railway U-Girder staged SLS stored", "Value": "Yes" if railway_sls_available else "No"},
        {"Item": "Result Summary runtime", "Value": runtime_status},
        {"Item": "Runtime last run", "Value": str(state.get("analysis_runtime_last_run_at") or "-")},
    ]
    st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)


def render_results_workspace() -> None:
    render_page_header(
        "Result Summary Dashboard",
        "Professional decision dashboard for stored analysis results. Opening Result Summary does not rerun PMM, ULS, or SLS.",
        icon="RS",
        badge="Summary workspace",
    )
    active_subpage = _safe_choice(
        "Result Summary subpage",
        WORKSPACE_NAVIGATION["Result Summary"],
        key="_results_active_subpage",
    )
    governing_rows = _results_governing_rows(st.session_state)

    if active_subpage == "Overview":
        render_metric_cards(_results_availability_cards(st.session_state))
        render_section_bar(
            "Executive Result Summary",
            "Decision-level status, critical check, result completeness, and next engineering action from stored Analysis outputs only.",
            mark="S",
        )
        _render_results_executive_summary(governing_rows, st.session_state)
        render_section_bar(
            "Required Actions",
            "Prioritized actions from stored results only. No calculation is triggered here.",
            mark="A",
        )
        _render_results_required_actions(st.session_state, governing_rows)
    elif active_subpage == "ULS Summary":
        render_section_bar(
            "ULS Summary Dashboard",
            "Read-only strength result summary from cached Analysis outputs.",
            mark="U",
        )
        has_column_vt = _render_results_column_pier_vt_dashboard(st.session_state)
        has_beam_uls = any(bool(row.get("__calculated")) for row in _results_beam_uls_summary_rows(st.session_state))
        if has_beam_uls:
            if has_column_vt:
                st.markdown("##### Beam/Girder stored ULS summaries")
            _render_results_beam_uls_dashboard(st.session_state)
        elif not has_column_vt:
            st.markdown(
                _RESULTS_DASHBOARD_CSS
                + '<div class="cpmm-results-empty">No stored ULS result rows are available yet. Run ULS Strength checks in Analysis, then return here for the read-only summary.</div>',
                unsafe_allow_html=True,
            )
    elif active_subpage == "SLS Summary":
        render_section_bar(
            "SLS Summary Dashboard",
            "Read-only serviceability result summary from cached Analysis outputs.",
            mark="L",
        )
        _render_results_sls_dashboard(st.session_state)
    elif active_subpage == "Traceability":
        render_section_bar(
            "Traceability / Cache State",
            "Stored result source, cache state, and raw stored module tables for audit review.",
            mark="T",
        )
        _render_results_traceability(st.session_state)
        _render_results_module_tables(st.session_state)


def _report_qa_dashboard_cards(state: object) -> list[dict[str, object]]:
    """Return Report / QA readiness cards aligned with Result Summary.

    Report / QA is a read-only downstream workspace.  These cards intentionally
    reuse the Result Summary decision helpers so a failed stored result cannot
    be described as ready for report issue simply because the report page can be
    opened.
    """

    rows = _results_governing_rows(state)
    executive = _results_executive_status(rows, state)
    handoff = _results_report_handoff_state(state, rows)
    critical = _results_critical_row(rows)
    critical_label = "-" if critical is None else _results_critical_label(critical)
    critical_detail = (
        "No stored governing row"
        if critical is None
        else f"{critical.get('Status', '-')} · {critical.get('D/C / Util.', '-')} · {critical.get('Governing Case', '-')}"
    )
    return [
        {
            "title": "Overall status",
            "value": executive["title"].replace("Overall Status: ", ""),
            "detail": executive["detail"],
            "status": executive["status"],
        },
        {
            "title": "Critical check",
            "value": critical_label,
            "detail": critical_detail,
            "status": "warning" if critical is None else _results_style_for_status(critical.get("Status")),
        },
        {
            "title": "Report readiness",
            "value": handoff["value"],
            "detail": handoff["detail"],
            "status": handoff["status"],
        },
        {
            "title": "Design code",
            "value": _results_design_code_label(state),
            "detail": "Workflow-compatible project code basis used by stored Analysis results",
            "status": "info",
        },
        {
            "title": "Runtime mode",
            "value": "Read-only",
            "detail": "Report / QA does not rerun PMM, ULS, SLS, or verification solvers.",
            "status": "neutral",
        },
    ]


def _render_report_qa_result_summary_alignment(state: object) -> None:
    """Render the same decision snapshot and required actions used by Result Summary.

    Report / QA is downstream of Analysis and Result Summary.  Keeping this
    review block on the report page prevents a dangerous split-brain state where
    Result Summary says REVIEW/FAIL but Report / QA only shows generic export
    readiness.  The helper only reads stored result rows and does not invoke
    solver actions.
    """

    rows = _results_governing_rows(state)
    render_section_bar(
        "Result Summary alignment",
        "Same stored status, critical check basis, and governing rows used by Result Summary Overview. No calculation is triggered here.",
        mark="R",
    )
    _render_results_executive_summary(rows, state)
    render_section_bar(
        "Required Actions",
        "Same prioritized actions as Result Summary Overview. Resolve or document these items before report issue.",
        mark="A",
    )
    _render_results_required_actions(state, rows)


def render_report_qa_workspace() -> None:
    render_page_header(
        "Report / QA",
        "Review stored analysis results, traceability, report readiness, limitations, and export QA without rerunning solvers.",
        icon="QA",
        kicker="Report workspace",
        badge="Report readiness",
        accent="blue",
    )
    render_metric_cards(_report_qa_dashboard_cards(st.session_state))
    _render_report_qa_result_summary_alignment(st.session_state)
    render_section_bar(
        "Traceability / report tools",
        "Report and QA tools summarize stored results only; PMM, SLS, ULS, and verification solvers are not rerun here.",
        mark="Q",
    )
    render_analysis_report_qa()
    _render_runtime_diagnostics_expander()


def main() -> None:
    st.set_page_config(page_title="Concrete Section Pro", layout="wide", initial_sidebar_state="expanded")
    _render_global_commercial_tab_styles()
    install_streamlit_plotly_readability_patch(st)
    # Keep the canonical Streamlit title call for brand continuity and tests;
    # the premium app shell below carries the visible commercial header.
    st.title("Concrete Section Pro")
    st.caption(
        "Concrete section analysis and design-review workspace. "
        "Internal units: mm, MPa, N, N-mm."
    )

    update_dirty_state_from_session(st.session_state)

    if st.session_state.get("_nav_active_workspace") == "Results":
        st.session_state["_nav_active_workspace"] = "Result Summary"
    if st.session_state.get("_nav_active_workspace") not in WORKSPACE_NAVIGATION:
        st.session_state["_nav_active_workspace"] = "Setup"
    _render_commercial_sidebar(str(st.session_state.get("_nav_active_workspace", "Setup")))
    _render_commercial_brand_header(str(st.session_state.get("_nav_active_workspace", "Setup")))

    active_workspace = _safe_choice(
        "Workspace",
        list(WORKSPACE_NAVIGATION.keys()),
        key="_nav_active_workspace",
    )
    _render_engineering_context_summary(active_workspace)
    if active_workspace == "Setup":
        render_setup_workspace()
    elif active_workspace == "Sections":
        render_sections_workspace()
    elif active_workspace == "Loads":
        render_loads_workspace()
    elif active_workspace == "Analysis":
        render_analysis_workspace()
    elif active_workspace == "Result Summary":
        render_results_workspace()
    elif active_workspace == "Report / QA":
        render_report_qa_workspace()


if __name__ == "__main__":
    main()

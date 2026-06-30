"""Rebar tab UI and parsing helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from concrete_pmm_pro.code_checks import (
    aashto_seismic_circular_spiral_required,
    aashto_seismic_column_spacing_limit_mm,
    aashto_seismic_confinement_length_mm,
    aashto_seismic_rectangular_ash_required_mm2,
)
from concrete_pmm_pro.core.aashto_units import inch_to_mm
from shapely.geometry import Point, Polygon

from concrete_pmm_pro.core.models import Rebar, SectionGeometry
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    REINFORCEMENT_FLAGS_PRESET_KEY,
    ordinary_rebar_enabled,
    prestressing_steel_enabled,
)
from concrete_pmm_pro.geometry.rebar_layout import PerimeterRebarLayoutResult, generate_perimeter_rebar_layout
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.serviceability.girder_sls_load_components import BEAM_GIRDER_SYSTEM_SETTINGS_KEY, system_settings_from_mapping
from concrete_pmm_pro.visualization import create_section_preview
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REBAR_DB_PATH = REPO_ROOT / "data" / "rebar_database.csv"
REBAR_DEFAULT_MATERIAL_BY_SIZE = {
    "DB10": "SD40",
    "DB12": "SD40",
    "DB16": "SD40",
    "DB20": "SD40",
    "DB25": "SD40",
    "DB28": "SD40",
    "DB32": "SD50",
}
REBAR_INPUT_MODE_MANUAL = "Manual table"
REBAR_INPUT_MODE_AUTO_PERIMETER = "Auto perimeter layout"
REBAR_INPUT_MODE_OPTIONS = [REBAR_INPUT_MODE_MANUAL, REBAR_INPUT_MODE_AUTO_PERIMETER]
DEFAULT_REBAR_INPUT_MODE = REBAR_INPUT_MODE_AUTO_PERIMETER

# Keep the editor column contract centralized.  The same ordered column list is
# used when creating the default table, normalizing data_editor output, comparing
# edited rows, and feeding the Rebar parser.  This avoids subtle Streamlit rerun
# bugs caused by missing columns or inconsistent column order.


# SHEAR.REINF1 — Beam/Girder transverse reinforcement layout used by future
# ULS shear design.  It is deliberately zone-based because commercial girder
# design is detailed by stirrup regions, not by per-station manual entries.
SHEAR_REINFORCEMENT_TABLE_KEY = "beam_girder_shear_reinforcement_table"
SHEAR_REINFORCEMENT_VALID_KEY = "beam_girder_shear_reinforcement_valid"
SHEAR_DEPTH_SETTINGS_KEY = "beam_girder_shear_depth_settings"
COLUMN_PIER_TRANSVERSE_TABLE_KEY = "column_pier_transverse_reinforcement_table"
COLUMN_PIER_TRANSVERSE_VALID_KEY = "column_pier_transverse_reinforcement_valid"
COLUMN_PIER_TRANSVERSE_SETTINGS_KEY = "column_pier_transverse_reinforcement_settings"
SHEAR_DEPTH_MODE_AUTO = "Auto from reinforcement centroid"
SHEAR_DEPTH_MODE_MANUAL = "Manual effective d / dv"
SHEAR_REINFORCEMENT_COLUMNS = [
    "Active",
    "Zone",
    "x_start_m",
    "x_end_m",
    "Bar Size",
    "Diameter_mm",
    "Legs",
    "Spacing_mm",
    "fy_MPa",
    "Note",
]
SHEAR_STIRRUP_BAR_OPTIONS = ["DB10", "DB12", "DB16", "DB20", "DB25"]
DEFAULT_SHEAR_STIRRUP_BAR = "DB12"
DEFAULT_SHEAR_STIRRUP_LEGS = 2
DEFAULT_SHEAR_STIRRUP_SPACING_MM = 150.0
DEFAULT_SHEAR_STIRRUP_FY_MPA = 390.0
COLUMN_PIER_WORKFLOW_MEMBER_TYPE = "column_pier_pmm"
COLUMN_PIER_CLOSED_TIE_OPTIONS = ["Closed ties / hoops", "Spiral reinforcement", "Open ties - shear only review"]
COLUMN_PIER_TORSION_CORE_OPTIONS = ["Auto from section and tie offset", "Manual core dimensions", "Not defined yet"]
COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL = "AASHTO LRFD seismic bridge-column advisor"
COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LEGACY_LABEL = COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL
COLUMN_PIER_SEISMIC_DETAILING_OPTIONS = [
    "Not selected / ordinary detailing",
    "ACI 318 special seismic confinement advisor",
    COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL,
    "Project-specific manual review",
]
COLUMN_PIER_SEISMIC_DETAILING_DEFAULT = COLUMN_PIER_SEISMIC_DETAILING_OPTIONS[0]
COLUMN_PIER_SEISMIC_HX_DEFAULT_MM = 300.0
COLUMN_PIER_SEISMIC_CLEAR_HEIGHT_DEFAULT_MM = 0.0
COLUMN_PIER_SEISMIC_SPACING_INCREMENT_MM = 25.0


def _normalize_column_pier_seismic_detailing_label(value: object) -> str:
    text = str(value or COLUMN_PIER_SEISMIC_DETAILING_DEFAULT).strip()
    if text == COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LEGACY_LABEL:
        return COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL
    return text if text in COLUMN_PIER_SEISMIC_DETAILING_OPTIONS else COLUMN_PIER_SEISMIC_DETAILING_DEFAULT


def _is_aashto_column_pier_seismic_advisor(value: object) -> bool:
    return _normalize_column_pier_seismic_detailing_label(value) == COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL

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

# Non-widget mirrors written by Section Builder.  Rebar reads these before
# deciding whether to show the disabled/stored branch so a checkbox selection in
# Section Builder opens the longitudinal rebar workspace immediately instead of
# requiring a second Enable click on this page.
SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY = "section_builder_ordinary_rebar_enabled"
SECTION_BUILDER_PRESTRESS_SYNC_KEY = "section_builder_prestressing_steel_enabled"
SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY = "section_builder_steel_systems_preset_key"




def _commercial_rebar_dashboard_cards(member_type: str) -> list[dict[str, object]]:
    """Return visual-only dashboard cards for the Rebar workspace."""

    table = pd.DataFrame(st.session_state.get("rebar_table", []))
    active_rows = int(pd.Series(table.get("Active", pd.Series(dtype=bool))).fillna(False).astype(bool).sum()) if not table.empty else 0
    try:
        total_area = sum(float(getattr(bar, "area", 0.0) or 0.0) for bar in st.session_state.get("rebars", []))
    except Exception:
        total_area = 0.0
    ordinary_status = "Enabled" if ordinary_rebar_enabled(st.session_state, default=True) else "Disabled"
    prestress_status = "Enabled" if prestressing_steel_enabled(st.session_state, default=True) else "Disabled"
    workflow = "Column/Pier" if member_type == COLUMN_PIER_WORKFLOW_MEMBER_TYPE else "Beam/Girder"
    return [
        {"title": "Workflow", "value": workflow, "detail": "Rebar interpretation follows active member type", "status": "info"},
        {"title": "Ordinary rebar", "value": ordinary_status, "detail": "Longitudinal Al / PMM participation", "status": "ready" if ordinary_status == "Enabled" else "warning"},
        {"title": "Active bars", "value": f"{active_rows:,}", "detail": f"Total As ≈ {total_area:,.0f} mm²", "status": "ready" if active_rows else "warning"},
        {"title": "Prestress", "value": prestress_status, "detail": "Prestress is managed on its own page", "status": "info" if prestress_status == "Enabled" else "neutral"},
    ]


def publish_ordinary_rebar_system_flag(session_state: Any, enabled: bool) -> None:
    """Publish ordinary-rebar participation consistently across UI pages.

    Section Builder owns the visible steel-system checkbox, but users can arrive
    at the Rebar page with a stale top-level flag after project load, preset
    switching, or a previous disabled preview.  This helper keeps the top-level
    Streamlit state and project metadata mirror aligned so Rebar, Analysis,
    Project save/load, and report builders read the same ordinary-rebar /
    longitudinal-Al decision.
    """

    enabled_bool = bool(enabled)
    session_state[ORDINARY_REBAR_FLAG_KEY] = enabled_bool
    metadata = dict(session_state.get("project_metadata", {}) or {})
    metadata[ORDINARY_REBAR_FLAG_KEY] = enabled_bool
    preset_key = session_state.get("section_preset_key")
    if preset_key is not None and str(preset_key).strip():
        metadata[REINFORCEMENT_FLAGS_PRESET_KEY] = str(preset_key)
        session_state[REINFORCEMENT_FLAGS_PRESET_KEY] = str(preset_key)
    session_state["project_metadata"] = metadata


def _to_optional_bool(value: Any) -> bool | None:
    """Return a bool for common UI/metadata values, or None when absent."""

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(value)


def _active_preset_key(session_state: Any) -> str:
    if hasattr(session_state, "get"):
        return str(session_state.get("section_preset_key") or "").strip()
    return str(getattr(session_state, "section_preset_key", "") or "").strip()


def _metadata_mapping(session_state: Any) -> dict[str, Any]:
    metadata = session_state.get("project_metadata", {}) if hasattr(session_state, "get") else getattr(session_state, "project_metadata", {})
    return dict(metadata or {}) if isinstance(metadata, dict) else {}


def _preset_matches_active(active_preset: str, source_preset: str) -> bool:
    # Empty source preset is tolerated for old sessions because the marker is
    # still a same-session Section Builder signal.  A non-empty mismatch is
    # ignored to avoid carrying a stale ON/OFF decision across preset changes.
    return not source_preset or not active_preset or source_preset == active_preset


def reconcile_ordinary_rebar_system_flag_for_rebar_page(session_state: Any, *, default: bool = True) -> bool:
    """Synchronize the Rebar page with the Section Builder steel-system switch.

    The Section Builder checkbox is the user-facing source of truth.  In some
    Streamlit navigation/rerun paths the top-level widget key can remain stale
    on the Rebar page even though Section Builder already shows ordinary rebar
    as enabled.  This reconciliation reads the non-widget Section Builder mirror
    and project metadata, updates the shared flags once, and returns the value
    that should drive the Longitudinal Rebar workspace.
    """

    active_preset = _active_preset_key(session_state)
    metadata = _metadata_mapping(session_state)

    builder_preset = str(
        session_state.get(SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY, "")
        if hasattr(session_state, "get")
        else getattr(session_state, SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY, "")
    ).strip()
    builder_value = (
        session_state.get(SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY, None)
        if hasattr(session_state, "get")
        else getattr(session_state, SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY, None)
    )
    builder_bool = _to_optional_bool(builder_value)
    if builder_bool is not None and _preset_matches_active(active_preset, builder_preset):
        publish_ordinary_rebar_system_flag(session_state, builder_bool)
        return builder_bool

    metadata_preset = str(metadata.get(REINFORCEMENT_FLAGS_PRESET_KEY, "") or "").strip()
    metadata_bool = _to_optional_bool(metadata.get(ORDINARY_REBAR_FLAG_KEY))
    if metadata_bool is True and _preset_matches_active(active_preset, metadata_preset):
        publish_ordinary_rebar_system_flag(session_state, True)
        return True

    return ordinary_rebar_enabled(session_state, default=default)


def _render_enable_ordinary_rebar_action() -> None:
    """Offer an in-page recovery path when ordinary rebar is disabled."""

    st.markdown(
        '<div class="cpmm-rebar-note">Need to define longitudinal bars or torsion Al for this girder? '
        'Enable the ordinary rebar system here, then the editable longitudinal rebar table will be shown on the next rerun.</div>',
        unsafe_allow_html=True,
    )
    if st.button(
        "Enable ordinary rebar / longitudinal Al",
        key="enable_ordinary_rebar_longitudinal_al_from_rebar_page",
        help="Synchronizes the Section Builder ordinary-rebar switch and opens the Longitudinal Rebar input table.",
    ):
        publish_ordinary_rebar_system_flag(st.session_state, True)
        st.rerun()

@dataclass(frozen=True)
class RebarParseResult:
    rebars: list[Rebar]
    errors: list[str]
    warnings: list[str]
    info: list[str]


@dataclass(frozen=True)
class RebarMetric:
    title: str
    value: str
    detail: str = ""
    status: str = "neutral"
    strong: bool = False


@dataclass(frozen=True)
class SeismicSpacingAdvisorResult:
    status: str
    code_basis: str
    s_max_mm: float | None
    suggested_spacing_mm: float | None
    governing_limit: str
    criteria: tuple[dict[str, object], ...]
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    clear_height_mm: float | None = None
    one_sixth_clear_height_mm: float | None = None
    max_member_dimension_mm: float | None = None
    confinement_min_length_mm: float | None = None
    confinement_length_mm: float | None = None
    confinement_length_governing: str = ""
    spacing_dc: float | None = None
    area_dc: float | None = None
    provided_transverse_area_mm2: float | None = None
    required_transverse_area_mm2: float | None = None
    required_transverse_area_y_mm2: float | None = None


_REBAR_PAGE_CSS = """
<style>
.cpmm-rebar-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}
.cpmm-rebar-panel-title {
  color: #101828;
  font-size: 0.94rem;
  font-weight: 760;
  line-height: 1.25;
  margin-bottom: 0.14rem;
}
.cpmm-rebar-panel-subtitle {
  color: #667085;
  font-size: 0.8rem;
  line-height: 1.35;
  margin-bottom: 0.5rem;
}
.cpmm-rebar-preview-title {
  color: #101828;
  font-size: 0.9rem;
  font-weight: 720;
  margin-bottom: 0.1rem;
}
.cpmm-rebar-preview-caption {
  color: #667085;
  font-size: 0.78rem;
  line-height: 1.35;
  margin-bottom: 0.32rem;
}
.cpmm-rebar-chip {
  border: 1px solid #d9dee7;
  border-left: 3px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.5rem 0.62rem;
  min-height: 68px;
}
.cpmm-rebar-chip.ready { border-left-color: #22a447; background: #fbfffc; }
.cpmm-rebar-chip.warning { border-left-color: #d99000; background: #fffdf7; }
.cpmm-rebar-chip.danger { border-left-color: #dc2626; background: #fffafa; }
.cpmm-rebar-chip.info { border-left-color: #175cd3; background: #fbfdff; }
.cpmm-rebar-chip.neutral { border-left-color: #98a2b3; }
.cpmm-rebar-chip-label {
  color: #667085;
  font-size: 0.74rem;
  font-weight: 650;
  letter-spacing: 0;
  margin-bottom: 0.18rem;
}
.cpmm-rebar-chip-value {
  color: #101828;
  font-size: 0.96rem;
  font-weight: 720;
  line-height: 1.22;
  overflow-wrap: anywhere;
}
.cpmm-rebar-chip-detail {
  color: #667085;
  font-size: 0.74rem;
  line-height: 1.25;
  margin-top: 0.16rem;
}
.cpmm-rebar-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.12rem 0.5rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0;
}
.cpmm-rebar-badge.ready { color: #1f5f2a; background: #e7f5e8; }
.cpmm-rebar-badge.warning { color: #7a4b00; background: #fff4d6; }
.cpmm-rebar-badge.danger { color: #9f1f17; background: #fde8e7; }
.cpmm-rebar-badge.info { color: #1849a9; background: #e8f1ff; }
.cpmm-rebar-badge.neutral { color: #475467; background: #eef1f5; }
.cpmm-rebar-kv-panel {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.64rem 0.84rem;
}
.cpmm-rebar-kv-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  gap: 0.8rem;
  border-bottom: 1px solid #edf0f5;
  padding: 0.32rem 0;
}
.cpmm-rebar-kv-row:last-child { border-bottom: 0; }
.cpmm-rebar-kv-label {
  color: #667085;
  font-size: 0.82rem;
  font-weight: 600;
}
.cpmm-rebar-kv-value {
  color: #101828;
  font-size: 0.88rem;
  font-weight: 650;
  text-align: right;
  overflow-wrap: anywhere;
}
.cpmm-rebar-note {
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.35;
}
.cpmm-rebar-action-callout {
  border: 1px solid #d0d5dd;
  border-left: 4px solid #98a2b3;
  border-radius: 8px;
  background: #ffffff;
  padding: 0.72rem 0.88rem;
  margin: 0.55rem 0 0.7rem 0;
  color: #344054;
  font-size: 0.84rem;
  line-height: 1.36;
}
.cpmm-rebar-action-callout.danger { border-left-color: #dc2626; background: #fff7f7; color: #9f1f17; }
.cpmm-rebar-action-callout.warning { border-left-color: #d99000; background: #fffaf0; color: #7a4b00; }
.cpmm-rebar-action-callout.ready { border-left-color: #22a447; background: #f5fff8; color: #1f5f2a; }
.cpmm-rebar-action-callout-title {
  font-size: 0.74rem;
  font-weight: 760;
  letter-spacing: 0.055em;
  text-transform: uppercase;
  margin-bottom: 0.22rem;
}
.cpmm-rebar-message-list {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fbfcfe;
  padding: 0.62rem 0.78rem;
  margin-top: 0.55rem;
}
.cpmm-rebar-message-item {
  color: #475467;
  font-size: 0.82rem;
  line-height: 1.35;
  padding: 0.18rem 0;
}
/* AASHTO.COL.SEISMIC3: Streamlit metric defaults are too large for the
   dense seismic-detailing advisor cards. Keep the commercial blue emphasis
   but reduce value size and allow long values to wrap cleanly on first render. */
div[data-testid="stMetric"] {
  border-radius: 10px;
}
div[data-testid="stMetricLabel"] {
  color: #344054;
  font-size: 0.64rem !important;
  font-weight: 760 !important;
  letter-spacing: 0.065em !important;
  text-transform: uppercase !important;
}
div[data-testid="stMetricValue"] {
  color: #175cd3 !important;
  font-size: 1.04rem !important;
  line-height: 1.12 !important;
  font-weight: 760 !important;
  letter-spacing: -0.01em !important;
  overflow-wrap: anywhere !important;
  white-space: normal !important;
}
div[data-testid="stMetricDelta"] {
  font-size: 0.68rem !important;
}

/* AASHTO.COL.SEISMIC5: visual status cards use semantic left-border colors,
   a prominent required-action callout, and a collapsed calculation trace so
   FAIL/PASS/REVIEW meaning is clear before the detailed table is opened. */
@media (max-width: 1250px) {
  .cpmm-rebar-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .cpmm-rebar-strip { grid-template-columns: minmax(0, 1fr); }
}
</style>
"""


def load_rebar_database(path: Path | str = DEFAULT_REBAR_DB_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def _default_rebar_table(rebar_db: pd.DataFrame) -> pd.DataFrame:
    default_size = "DB20" if "DB20" in set(rebar_db["name"]) else str(rebar_db.iloc[0]["name"])
    default_diameter = float(rebar_db.loc[rebar_db["name"] == default_size, "diameter_mm"].iloc[0])
    default_material = default_material_for_bar_size(default_size)
    return pd.DataFrame(
        [
            {"Active": True, "Label": "B1", "x_mm": -150.0, "y_mm": -250.0, "Bar Size": default_size, "Diameter_mm": default_diameter, "Material": default_material, "Count": 1, "Note": ""},
            {"Active": True, "Label": "B2", "x_mm": 150.0, "y_mm": -250.0, "Bar Size": default_size, "Diameter_mm": default_diameter, "Material": default_material, "Count": 1, "Note": ""},
            {"Active": True, "Label": "B3", "x_mm": 150.0, "y_mm": 250.0, "Bar Size": default_size, "Diameter_mm": default_diameter, "Material": default_material, "Count": 1, "Note": ""},
            {"Active": True, "Label": "B4", "x_mm": -150.0, "y_mm": 250.0, "Bar Size": default_size, "Diameter_mm": default_diameter, "Material": default_material, "Count": 1, "Note": ""},
        ]
    )


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _row_is_blank(row: pd.Series) -> bool:
    return all(_is_blank(row.get(column)) for column in ["Label", "x_mm", "y_mm", "Bar Size", "Diameter_mm", "Material", "Count", "Note"])


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


def _diameter_from_database(bar_size: str, rebar_db: pd.DataFrame) -> float | None:
    if _is_blank(bar_size):
        return None
    matches = rebar_db.loc[rebar_db["name"] == str(bar_size).strip(), "diameter_mm"]
    if matches.empty:
        return None
    return float(matches.iloc[0])


def default_material_for_bar_size(bar_size: str) -> str:
    return REBAR_DEFAULT_MATERIAL_BY_SIZE.get(str(bar_size).strip(), "SD40")


def bar_size_defaults(bar_size: str, rebar_db: pd.DataFrame) -> tuple[float, str] | None:
    diameter = _diameter_from_database(bar_size, rebar_db)
    if diameter is None:
        return None
    return diameter, default_material_for_bar_size(bar_size)


def is_standard_rebar_bar_size(bar_size: str) -> bool:
    return str(bar_size).strip() in REBAR_DEFAULT_MATERIAL_BY_SIZE


def enforced_material_for_standard_bar_size(bar_size: str) -> str | None:
    if not is_standard_rebar_bar_size(bar_size):
        return None
    return default_material_for_bar_size(bar_size)


def _normalized_bar_size(value: Any) -> str:
    return "" if _is_blank(value) else str(value).strip()


def _previous_bar_size(previous_df: pd.DataFrame | None, index: Any) -> str:
    if previous_df is None or index not in previous_df.index:
        return ""
    return _normalized_bar_size(previous_df.at[index, "Bar Size"] if "Bar Size" in previous_df.columns else "")


def _ensure_rebar_table_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with the full editor column contract and stable order."""
    table = df.copy()
    for column in REBAR_TABLE_COLUMNS:
        if column not in table.columns:
            table[column] = None
    return table[REBAR_TABLE_COLUMNS]


def apply_generated_perimeter_layout_state(session_state: Any, generated_table: pd.DataFrame) -> pd.DataFrame:
    """Commit an auto-generated perimeter layout into the longitudinal Rebar table.

    Streamlit data_editor keeps its own widget state by key.  A direct assignment
    to ``rebar_table`` is therefore not enough when the previous editor widget
    was already mounted with an empty table; the old widget payload can win on
    the next rerun and make the Apply button appear to do nothing.  This helper
    updates the source-of-truth table, bumps the editor key, clears stale editor
    widget states, and returns the UI to the manual table where the applied rows
    are immediately visible/editable.
    """
    applied_table = _ensure_rebar_table_columns(pd.DataFrame(generated_table)).reset_index(drop=True)
    session_state["rebar_table"] = applied_table
    session_state["rebar_editor_revision"] = int(session_state.get("rebar_editor_revision", 0) or 0) + 1
    session_state["rebar_input_mode"] = REBAR_INPUT_MODE_MANUAL
    session_state["rebar_apply_status"] = f"Applied {len(applied_table):,} generated bar row(s) to the Longitudinal Rebar table."

    for key in list(session_state.keys()):
        if str(key).startswith("rebar_data_editor_"):
            try:
                del session_state[key]
            except KeyError:
                pass
    return applied_table


def _apply_generated_perimeter_layout_to_rebar_table(generated_table: pd.DataFrame) -> None:
    apply_generated_perimeter_layout_state(st.session_state, generated_table)


def _data_editor_payload_to_dataframe(payload: Any, fallback_table: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a full dataframe from a Streamlit data_editor return value or patch.

    UI.DATAEDITOR.COMMIT1: keyed ``st.data_editor`` callbacks receive patch
    dictionaries in session state.  Reconstructing the full table from the
    previous source-of-truth table lets the first cell edit persist before the
    next rerun, instead of requiring the engineer to enter the same value twice.
    """

    if isinstance(payload, pd.DataFrame):
        return payload.reset_index(drop=True).copy()
    if payload is None:
        return pd.DataFrame(fallback_table).reset_index(drop=True).copy() if fallback_table is not None else pd.DataFrame()
    if isinstance(payload, list):
        return pd.DataFrame(payload).reset_index(drop=True)
    if not isinstance(payload, dict):
        return pd.DataFrame(payload).reset_index(drop=True)

    if {"edited_rows", "added_rows", "deleted_rows"}.intersection(payload.keys()):
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


def _clear_data_editor_widget_state(editor_key: str) -> None:
    try:
        del st.session_state[editor_key]
    except KeyError:
        pass


def _sync_beam_girder_shear_reinforcement_editor_to_table(editor_key: str, rebar_db: pd.DataFrame) -> None:
    """Commit the first transverse-rebar editor edit to the provided-zone table."""

    fallback = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state.get(SHEAR_REINFORCEMENT_TABLE_KEY)))
    edited = _data_editor_payload_to_dataframe(st.session_state.get(editor_key), fallback)
    normalized = _normalize_shear_reinforcement_table(edited, fallback, rebar_db)
    st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = normalized
    _store_shear_reinforcement_metadata(normalized)
    st.session_state["beam_girder_shear_reinforcement_editor_revision"] = int(st.session_state.get("beam_girder_shear_reinforcement_editor_revision", 0) or 0) + 1
    _clear_data_editor_widget_state(editor_key)


def _sync_column_pier_transverse_reinforcement_editor_to_table(editor_key: str, rebar_db: pd.DataFrame) -> None:
    """Commit the first Column/Pier transverse editor edit to the control table."""

    fallback = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state.get(COLUMN_PIER_TRANSVERSE_TABLE_KEY)))
    edited = _data_editor_payload_to_dataframe(st.session_state.get(editor_key), fallback)
    normalized = _normalize_shear_reinforcement_table(edited, fallback, rebar_db)
    st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = normalized
    _store_column_pier_transverse_metadata(normalized)
    st.session_state["column_pier_transverse_reinforcement_editor_revision"] = int(st.session_state.get("column_pier_transverse_reinforcement_editor_revision", 0) or 0) + 1
    _clear_data_editor_widget_state(editor_key)


def _editor_cell_equal(left: Any, right: Any, numeric: bool = False, boolean: bool = False) -> bool:
    """Compare data_editor cells without false mismatches from type coercion.

    Streamlit may round-trip ``32`` as ``32.0`` or preserve blank cells as
    ``None``/``NaN`` depending on the edit path.  This comparator keeps the
    immediate-sync guard from triggering an unnecessary rerun loop while still
    detecting real Bar Size → Diameter/Material updates.
    """
    if _is_blank(left) and _is_blank(right):
        return True
    if boolean:
        return _to_bool(left) == _to_bool(right)
    if numeric:
        left_number = _to_float(left)
        right_number = _to_float(right)
        if left_number is None or right_number is None:
            return left_number is right_number
        return abs(left_number - right_number) <= 1e-9
    return str(left).strip() == str(right).strip()


def rebar_editor_tables_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Return True when two editor tables are equivalent for the visible UI.

    This is intentionally stricter than object identity and looser than
    ``DataFrame.equals``.  It prevents rerun loops caused only by pandas/Streamlit
    dtype differences, while still detecting when the auto-sync has changed
    Diameter_mm or Material after a Bar Size edit.
    """
    left_table = _ensure_rebar_table_columns(left).reset_index(drop=True)
    right_table = _ensure_rebar_table_columns(right).reset_index(drop=True)
    if left_table.shape != right_table.shape:
        return False

    numeric_columns = {"x_mm", "y_mm", "Diameter_mm", "Count"}
    for row_index in range(len(left_table)):
        for column in REBAR_TABLE_COLUMNS:
            if not _editor_cell_equal(
                left_table.at[row_index, column],
                right_table.at[row_index, column],
                numeric=column in numeric_columns,
                boolean=column == "Active",
            ):
                return False
    return True


def normalize_rebar_table_for_bar_size_sync(edited_df: pd.DataFrame, previous_df: pd.DataFrame | None, rebar_db: pd.DataFrame) -> pd.DataFrame:
    """Apply database defaults only when Bar Size changes or dependent cells are blank.

    This keeps Streamlit data_editor manual Diameter_mm/Material overrides stable
    across reruns while still making size dropdown changes immediately consistent
    with the engineering database/default material rules.
    """
    normalized = _ensure_rebar_table_columns(edited_df)

    for index, row in normalized.iterrows():
        bar_size = _normalized_bar_size(row.get("Bar Size"))
        if not bar_size or bar_size == "Custom":
            continue
        defaults = bar_size_defaults(bar_size, rebar_db)
        if defaults is None:
            continue
        default_diameter, default_material = defaults
        previous_bar_size = _previous_bar_size(previous_df, index)
        bar_size_changed = bar_size != previous_bar_size

        if bar_size_changed or _is_blank(row.get("Diameter_mm")):
            normalized.at[index, "Diameter_mm"] = default_diameter
        # Standard DB sizes use bar size as the source of truth for material/fy.
        # This intentionally corrects legacy/imported rows such as DB32 + SD40.
        normalized.at[index, "Material"] = default_material

    return normalized


def _resolve_diameter(row: pd.Series, rebar_db: pd.DataFrame, row_number: int) -> tuple[float | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    bar_size = "" if _is_blank(row.get("Bar Size")) else str(row.get("Bar Size")).strip()
    manual_diameter = _to_float(row.get("Diameter_mm"))

    if bar_size and bar_size != "Custom":
        database_diameter = _diameter_from_database(bar_size, rebar_db)
        if database_diameter is not None:
            if manual_diameter is None:
                return database_diameter, errors, warnings
            if manual_diameter <= 0:
                errors.append(f"Row {row_number}: Diameter_mm must be positive.")
                return None, errors, warnings
            return manual_diameter, errors, warnings
        if manual_diameter is not None:
            warnings.append(f"Row {row_number}: Bar Size '{bar_size}' is not in the database; using manual Diameter_mm as custom.")
            if manual_diameter <= 0:
                errors.append(f"Row {row_number}: Diameter_mm must be positive.")
                return None, errors, warnings
            return manual_diameter, errors, warnings
        errors.append(f"Row {row_number}: Bar Size '{bar_size}' is not in the database and Diameter_mm is blank.")
        return None, errors, warnings

    if manual_diameter is None:
        if bar_size == "Custom":
            errors.append(f"Row {row_number}: Custom Bar Size requires Diameter_mm.")
        else:
            errors.append(f"Row {row_number}: Bar Size or Diameter_mm is required.")
        return None, errors, warnings
    if manual_diameter <= 0:
        errors.append(f"Row {row_number}: Diameter_mm must be positive.")
        return None, errors, warnings
    if bar_size == "Custom":
        warnings.append(f"Row {row_number}: Custom Bar Size is using manual Diameter_mm.")
    return manual_diameter, errors, warnings


def rebars_from_dataframe(df: pd.DataFrame, rebar_db: pd.DataFrame) -> RebarParseResult:
    errors: list[str] = []
    warnings: list[str] = []
    rebars: list[Rebar] = []

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

        diameter_mm, diameter_errors, diameter_warnings = _resolve_diameter(row, rebar_db, row_number)
        errors.extend(diameter_errors)
        warnings.extend(diameter_warnings)

        count = _to_count(row.get("Count"))
        if count is None:
            errors.append(f"Row {row_number}: Count must be an integer greater than or equal to 1.")
            count = 1

        if any(error.startswith(f"Row {row_number}:") for error in errors):
            continue

        base_label = str(row.get("Label")).strip() if not _is_blank(row.get("Label")) else f"R{len(rebars) + 1}"
        material_name = str(row.get("Material")).strip() if not _is_blank(row.get("Material")) else "SD40"
        enforced_material = enforced_material_for_standard_bar_size(str(row.get("Bar Size") or ""))
        if enforced_material is not None:
            if material_name and material_name != enforced_material:
                warnings.append(
                    f"Row {row_number}: Bar Size {str(row.get('Bar Size')).strip()} uses {enforced_material} by standard-size rule; "
                    f"entered Material '{material_name}' was ignored."
                )
            material_name = enforced_material
        for item in range(count):
            label = base_label if count == 1 else f"{base_label}-{item + 1}"
            rebars.append(Rebar(x_mm=float(x_mm), y_mm=float(y_mm), diameter_mm=float(diameter_mm), material_name=material_name, label=label))

    total_as = sum(rebar.area_mm2 for rebar in rebars)
    info = [f"{len(rebars)} active rebar object(s).", f"Total As = {total_as:,.1f} mm^2."]
    return RebarParseResult(rebars=rebars, errors=errors, warnings=warnings, info=info)


def validate_rebars_against_geometry(rebars: list[Rebar], geometry: SectionGeometry | None) -> list[str]:
    if geometry is None:
        return []
    section = to_shapely_polygon(geometry)
    hole_polygons = [Polygon([point.as_tuple() for point in hole]) for hole in geometry.holes]
    errors: list[str] = []
    for index, rebar in enumerate(rebars, start=1):
        label = rebar.label or f"Rebar {index}"
        point = Point(rebar.x_mm, rebar.y_mm)
        if any(hole.covers(point) for hole in hole_polygons):
            errors.append(f"{label}: rebar is inside a void/hole.")
        elif not section.covers(point):
            errors.append(f"{label}: rebar is outside concrete.")
    return errors


def rebars_valid_for_analysis(parse_result: RebarParseResult, geometry_errors: list[str]) -> bool:
    return not parse_result.errors and not geometry_errors


def rebar_summary_dataframe(rebars: list[Rebar]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Label": rebar.label,
                "x_mm": rebar.x_mm,
                "y_mm": rebar.y_mm,
                "diameter_mm": rebar.diameter_mm,
                "area_mm2": rebar.area_mm2,
                "material_name": rebar.material_name,
            }
            for rebar in rebars
        ]
    )


def _safe_status(status: str) -> str:
    return status if status in {"ready", "warning", "danger", "info", "neutral"} else "neutral"


def _strip_html(metrics: list[RebarMetric]) -> str:
    chips: list[str] = []
    for metric in metrics:
        status = _safe_status(metric.status)
        value_html = (
            f'<span class="cpmm-rebar-badge {status}">{escape(metric.value)}</span>'
            if metric.strong
            else escape(metric.value)
        )
        detail_html = f'<div class="cpmm-rebar-chip-detail">{escape(metric.detail)}</div>' if metric.detail else ""
        chips.append(
            f'<div class="cpmm-rebar-chip {status}">'
            f'<div class="cpmm-rebar-chip-label">{escape(metric.title)}</div>'
            f'<div class="cpmm-rebar-chip-value">{value_html}</div>'
            f"{detail_html}"
            "</div>"
        )
    return '<div class="cpmm-rebar-strip">' + "".join(chips) + "</div>"


def _kv_panel_html(rows: list[tuple[str, str]]) -> str:
    row_html = []
    for label, value in rows:
        row_html.append(
            '<div class="cpmm-rebar-kv-row">'
            f'<div class="cpmm-rebar-kv-label">{escape(label)}</div>'
            f'<div class="cpmm-rebar-kv-value">{escape(value)}</div>'
            "</div>"
        )
    return '<div class="cpmm-rebar-kv-panel">' + "".join(row_html) + "</div>"


def _message_list_html(messages: list[str]) -> str:
    items = "".join(f'<div class="cpmm-rebar-message-item">{escape(message)}</div>' for message in messages)
    return f'<div class="cpmm-rebar-message-list">{items}</div>'


def _fmt_detail_value(value: float | None, unit: str, digits: int = 0) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:,.{digits}f} {unit}"


def _aashto_seismic_governing_ash_requirement(
    result: SeismicSpacingAdvisorResult,
) -> tuple[float | None, str]:
    candidates: list[tuple[str, float]] = []
    if result.required_transverse_area_mm2 is not None and math.isfinite(float(result.required_transverse_area_mm2)):
        candidates.append(("x/core width", float(result.required_transverse_area_mm2)))
    if result.required_transverse_area_y_mm2 is not None and math.isfinite(float(result.required_transverse_area_y_mm2)):
        candidates.append(("y/core depth", float(result.required_transverse_area_y_mm2)))
    if not candidates:
        return None, "Unavailable"
    axis, value = max(candidates, key=lambda item: item[1])
    return value, axis


def _aashto_seismic_detailing_summary_metrics(
    result: SeismicSpacingAdvisorResult,
    *,
    current_spacing_mm: float | None,
) -> list[RebarMetric]:
    spacing_status = "Input required"
    spacing_detail = "Enter/provide the control-section hoop spacing"
    spacing_kind = "warning"
    if current_spacing_mm is not None and result.s_max_mm is not None:
        if result.spacing_dc is not None and result.spacing_dc <= 1.0 + 1.0e-9:
            spacing_status = "OK"
            spacing_detail = f"Current {_fmt_detail_value(current_spacing_mm, 'mm')} ≤ limit {_fmt_detail_value(result.s_max_mm, 'mm')}"
            spacing_kind = "ready"
        else:
            spacing_status = f"Reduce to ≤ {result.s_max_mm:.0f} mm"
            spacing_detail = f"Current {_fmt_detail_value(current_spacing_mm, 'mm')} exceeds the AASHTO spacing limit"
            spacing_kind = "danger"

    governing_required, governing_axis = _aashto_seismic_governing_ash_requirement(result)
    provided = result.provided_transverse_area_mm2
    area_status = "Input required"
    area_detail = "Define hoop/cross-tie bar size, effective legs, fyh, and spacing"
    area_kind = "warning"
    if provided is not None and governing_required is not None and result.area_dc is not None:
        if result.area_dc <= 1.0 + 1.0e-9:
            area_status = "OK"
            area_detail = f"Provided {_fmt_detail_value(provided, 'mm²', 1)} ≥ required {_fmt_detail_value(governing_required, 'mm²', 1)}"
            area_kind = "ready"
        else:
            area_status = f"Increase Ash ×{result.area_dc:.2f}"
            area_detail = f"Provided {_fmt_detail_value(provided, 'mm²', 1)} < required {_fmt_detail_value(governing_required, 'mm²', 1)} about {governing_axis}"
            area_kind = "danger"

    length_status = "Input required" if result.clear_height_mm is None else _fmt_detail_value(result.confinement_length_mm, "mm")
    length_detail = (
        "Enter clear height for the 1/6 clear-height criterion"
        if result.clear_height_mm is None
        else f"Governing: {result.confinement_length_governing or 'AASHTO 5.11.4.1.5'}"
    )

    action_value = "Review"
    action_detail = "Complete missing inputs before treating the seismic detail as final"
    action_kind = "warning"
    if result.status == "PASS":
        action_value = "Detailing OK"
        action_detail = "Spacing and confinement area checks pass; still verify hooks/splices/drawings"
        action_kind = "ready"
    elif result.area_dc is not None and result.area_dc > 1.0 + 1.0e-9:
        action_value = "Add confinement steel"
        action_detail = "Increase effective legs/cross-ties, bar size, or reduce spacing"
        action_kind = "danger"
    elif result.spacing_dc is not None and result.spacing_dc > 1.0 + 1.0e-9:
        action_value = "Reduce spacing"
        action_detail = "Use a spacing not greater than the AASHTO limit"
        action_kind = "danger"

    return [
        RebarMetric("Current spacing", _fmt_detail_value(current_spacing_mm, "mm"), "Provided control-section row", "neutral"),
        RebarMetric("Spacing action", spacing_status, spacing_detail, spacing_kind, strong=spacing_kind in {"danger", "warning"}),
        RebarMetric("Provided Ash", _fmt_detail_value(provided, "mm²", 1), "From selected hoop/cross-tie row", "neutral"),
        RebarMetric("Required Ash", _fmt_detail_value(governing_required, "mm²", 1), f"Governing {governing_axis}", "neutral"),
        RebarMetric("Confinement length", length_status, length_detail, "warning" if result.clear_height_mm is None else "info"),
        RebarMetric("Required action", action_value, action_detail, action_kind, strong=True),
    ]


def _aashto_seismic_fail_reason_messages(
    result: SeismicSpacingAdvisorResult,
    *,
    current_spacing_mm: float | None,
) -> list[str]:
    messages: list[str] = []
    if current_spacing_mm is not None and result.s_max_mm is not None and result.spacing_dc is not None and result.spacing_dc > 1.0 + 1.0e-9:
        messages.append(
            f"Spacing FAIL: current spacing = {_fmt_detail_value(current_spacing_mm, 'mm')} > AASHTO limit = {_fmt_detail_value(result.s_max_mm, 'mm')} (D/C = {result.spacing_dc:.2f})."
        )
    governing_required, governing_axis = _aashto_seismic_governing_ash_requirement(result)
    provided = result.provided_transverse_area_mm2
    if provided is not None and governing_required is not None and result.area_dc is not None and result.area_dc > 1.0 + 1.0e-9:
        messages.append(
            f"Ash/rho FAIL: provided Ash = {_fmt_detail_value(provided, 'mm²', 1)} < required Ash = {_fmt_detail_value(governing_required, 'mm²', 1)} about {governing_axis} (D/C = {result.area_dc:.2f}). Increase effective hoop/cross-tie legs, increase bar size, or reduce spacing."
        )
    return messages


def _status_kind_from_advisor_status(status: str) -> str:
    normalized = str(status or "").strip().upper()
    if normalized == "PASS":
        return "ready"
    if normalized == "FAIL":
        return "danger"
    if normalized in {"REVIEW", "NOT READY", "INPUT REQUIRED"}:
        return "warning"
    return "neutral"


def _status_kind_from_dc(dc: float | None) -> str:
    if dc is None:
        return "warning"
    return "ready" if dc <= 1.0 + 1.0e-9 else "danger"


def _aashto_seismic_advisor_status_metrics(
    result: SeismicSpacingAdvisorResult,
    *,
    spacing_status: str,
    area_status: str,
) -> tuple[list[RebarMetric], list[RebarMetric]]:
    overall_kind = _status_kind_from_advisor_status(result.status)
    spacing_kind = _status_kind_from_dc(result.spacing_dc)
    area_kind = _status_kind_from_dc(result.area_dc)
    headline = [
        RebarMetric("Advisor status", result.status, "Overall seismic detailing", overall_kind, strong=True),
        RebarMetric("Max spacing", "-" if result.s_max_mm is None else f"{result.s_max_mm:.1f} mm", result.governing_limit, "info"),
        RebarMetric("Suggested spacing", "-" if result.suggested_spacing_mm is None else f"{result.suggested_spacing_mm:.0f} mm", "Use for plastic-hinge region", "info"),
        RebarMetric("Confinement length", "-" if result.confinement_length_mm is None else f"{result.confinement_length_mm:.0f} mm", result.confinement_length_governing or "AASHTO 5.11.4.1.5", "info"),
        RebarMetric("Code basis", "AASHTO 5.11.4", "Bridge-column seismic advisor", "info"),
    ]
    checks = [
        RebarMetric("Seismic spacing check", spacing_status, "Current spacing versus AASHTO maximum", spacing_kind, strong=spacing_kind != "ready"),
        RebarMetric("Ash / rho check", area_status, "Confinement area requirement", area_kind, strong=area_kind != "ready"),
        RebarMetric("Overall seismic detailing", result.status, "Controls whether this detail is final", overall_kind, strong=True),
    ]
    return headline, checks


def _aashto_seismic_required_action_callout_html(
    result: SeismicSpacingAdvisorResult,
    *,
    current_spacing_mm: float | None,
) -> str:
    spacing_failed = result.spacing_dc is not None and result.spacing_dc > 1.0 + 1.0e-9
    area_failed = result.area_dc is not None and result.area_dc > 1.0 + 1.0e-9
    missing = result.status == "REVIEW"
    if result.status == "PASS":
        message = (
            "Spacing and confinement area checks pass for the current control-section row. "
            "Use the confinement length for expected plastic-hinge regions and verify hooks, cross-ties, splices, and drawings."
        )
        kind = "ready"
    elif spacing_failed or area_failed:
        parts: list[str] = []
        if spacing_failed and result.s_max_mm is not None:
            parts.append(f"reduce spacing to ≤ {result.s_max_mm:.0f} mm")
        governing_required, governing_axis = _aashto_seismic_governing_ash_requirement(result)
        provided = result.provided_transverse_area_mm2
        if area_failed and provided is not None and governing_required is not None:
            parts.append(
                f"increase confinement steel: provided Ash {_fmt_detail_value(provided, 'mm²', 1)} < required {_fmt_detail_value(governing_required, 'mm²', 1)} about {governing_axis}"
            )
        if not parts:
            parts.append("revise the selected control-section transverse reinforcement")
        message = "Required action: " + "; ".join(parts) + ". Use larger hoops/cross-ties, add effective legs, or reduce spacing as needed."
        kind = "danger"
    elif missing:
        message = "Required action: complete missing seismic advisor inputs before treating this transverse reinforcement as final."
        kind = "warning"
    else:
        message = "Required action: review the seismic detailing assumptions before finalizing this control-section row."
        kind = "warning"
    return (
        f'<div class="cpmm-rebar-action-callout {kind}">'
        '<div class="cpmm-rebar-action-callout-title">Required action summary</div>'
        f'{escape(message)}'
        '</div>'
    )


def _total_as_mm2(rebars: list[Rebar]) -> float:
    return sum(rebar.area_mm2 for rebar in rebars)


def _dominant_material_label(rebars: list[Rebar], fallback: str | None = None) -> str:
    if not rebars:
        return fallback or "N/A"
    materials = sorted({rebar.material_name for rebar in rebars if rebar.material_name})
    if not materials:
        return fallback or "N/A"
    if len(materials) == 1:
        return materials[0]
    return f"{len(materials)} materials"


def _reinforcement_ratio_label(total_as_mm2: float, geometry: SectionGeometry | None) -> str:
    if geometry is None:
        return "N/A"
    area_mm2 = float(to_shapely_polygon(geometry).area)
    if area_mm2 <= 0:
        return "N/A"
    return f"{100.0 * total_as_mm2 / area_mm2:.3f}%"


def _valid_status(valid_for_analysis: bool) -> str:
    return "ready" if valid_for_analysis else "danger"


def _render_summary_strip(
    result: RebarParseResult,
    geometry: SectionGeometry | None,
    input_mode: str,
    valid_for_analysis: bool,
    active_material_name: str | None,
) -> None:
    total_as = _total_as_mm2(result.rebars)
    st.markdown(
        _strip_html(
            [
                RebarMetric("Analysis Participation", "Included", "Ordinary rebar enabled", "ready", True),
                RebarMetric("Active Bars", f"{len(result.rebars):,}", "Expanded by Count"),
                RebarMetric("Total As", f"{total_as:,.1f} mm^2"),
                RebarMetric("Valid for Analysis", "Yes" if valid_for_analysis else "No", "", _valid_status(valid_for_analysis), True),
                RebarMetric("Rebar Ratio", _reinforcement_ratio_label(total_as, geometry), "As / concrete area"),
                RebarMetric("Input Mode", input_mode),
            ]
        ),
        unsafe_allow_html=True,
    )


def _render_validation(
    result: RebarParseResult,
    geometry_errors: list[str],
    geometry_available: bool,
    valid_for_analysis: bool,
    active_prestress_count: int = 0,
) -> None:
    st.markdown(
        '<div class="cpmm-rebar-panel-title">Rebar Status</div>'
        '<div class="cpmm-rebar-panel-subtitle">Active analysis participation and validation gate for the current longitudinal table.</div>',
        unsafe_allow_html=True,
    )
    all_errors = [*result.errors, *geometry_errors]
    warnings = list(result.warnings)
    contextual_notes: list[str] = []
    if not result.rebars and active_prestress_count > 0:
        contextual_notes.append(
            "No active ordinary rebar is defined. Analysis will rely on active bonded prestress elements; check minimum ordinary reinforcement and detailing requirements separately."
        )
    elif not result.rebars:
        warnings.append("No active longitudinal reinforcement is defined. Activate ordinary rebar or prestress before final analysis.")
    if not geometry_available:
        warnings.append("Section geometry is not available yet; geometry validation will run after a valid section is generated.")
    st.markdown(
        _kv_panel_html(
            [
                ("Validation", "OK" if not all_errors else "Error"),
                ("Warnings", f"{len(warnings):,}"),
                ("Active bars", f"{len(result.rebars):,}"),
                ("Total As", f"{_total_as_mm2(result.rebars):,.1f} mm^2"),
                ("Valid for analysis", "Yes" if valid_for_analysis else "No"),
                ("Material", _dominant_material_label(result.rebars)),
            ]
        ),
        unsafe_allow_html=True,
    )

    if all_errors:
        for error in all_errors:
            st.error(f"ERROR: {error}")

    if warnings:
        for warning in warnings:
            st.warning(f"WARNING: {warning}")

    for note in contextual_notes:
        st.info(f"INFO: {note}")

    if result.info and (all_errors or warnings or contextual_notes):
        st.markdown(_message_list_html([f"INFO: {info}" for info in result.info]), unsafe_allow_html=True)


def _rebar_column_config(bar_size_options: list[str]) -> dict[str, Any]:
    return {
        "Active": st.column_config.CheckboxColumn("Active", width="small"),
        "Label": st.column_config.TextColumn("Label", width="small"),
        "x_mm": st.column_config.NumberColumn("x_mm", help="x coordinate in section axes, mm", width="small"),
        "y_mm": st.column_config.NumberColumn("y_mm", help="y coordinate in section axes, mm", width="small"),
        "Bar Size": st.column_config.SelectboxColumn("Bar Size", options=bar_size_options, width="medium"),
        "Diameter_mm": st.column_config.NumberColumn("Diameter_mm", help="Used for Custom or blank Bar Size.", width="small"),
        "Material": st.column_config.TextColumn(
            "Material",
            width="small",
            help="Auto-resolved from standard DB bar size: DB10–DB28 = SD40, DB32 = SD50. Use Custom bar size for project-specific overrides.",
        ),
        "Count": st.column_config.NumberColumn("Count", min_value=1, step=1, width="small"),
        "Note": st.column_config.TextColumn("Note", width="medium"),
    }


def _rebar_bar_size_options(rebar_db: pd.DataFrame) -> list[str]:
    return [""] + [str(name) for name in rebar_db["name"].tolist()]


def _render_auto_perimeter_controls(rebar_db: pd.DataFrame, geometry: SectionGeometry | None) -> PerimeterRebarLayoutResult:
    """Render preview/apply controls for generated perimeter reinforcement.

    The generator is deliberately opt-in: it never overwrites the engineering
    rebar table until the user presses Apply.  This keeps manual layouts safe
    while making perimeter reinforcement fast for column/pier/wall/pylon PMM
    sections.
    """
    st.markdown("##### Auto perimeter layout")
    st.caption(
        "Preview ordinary bars offset from the current section perimeter, then apply the generated coordinates to the Rebar table. "
        "This does not silently overwrite manual bars."
    )
    control_cols = st.columns([1.05, 1.0, 1.0, 1.0, 0.9], gap="small")
    with control_cols[0]:
        bar_size = st.selectbox(
            "Bar size",
            _rebar_bar_size_options(rebar_db),
            index=max(0, _rebar_bar_size_options(rebar_db).index("DB20") if "DB20" in set(rebar_db["name"]) else 0),
            key="rebar_perimeter_bar_size",
        )
    defaults = bar_size_defaults(bar_size, rebar_db) if bar_size else None
    diameter_mm = defaults[0] if defaults else 20.0
    default_material = defaults[1] if defaults else "SD40"
    with control_cols[1]:
        material = st.text_input("Material", value=default_material, key="rebar_perimeter_material")
    with control_cols[2]:
        edge_offset_mm = st.number_input(
            "Bar center offset (mm)",
            min_value=1.0,
            value=50.0,
            step=5.0,
            key="rebar_perimeter_edge_offset_mm",
        )
    with control_cols[3]:
        target_spacing_mm = st.number_input(
            "Target spacing (mm)",
            min_value=1.0,
            value=150.0,
            step=10.0,
            key="rebar_perimeter_target_spacing_mm",
        )
    with control_cols[4]:
        min_bars = st.number_input(
            "Minimum bars",
            min_value=1,
            value=4,
            step=1,
            key="rebar_perimeter_min_bars",
        )

    prefix_cols = st.columns([0.35, 1.65], gap="small")
    with prefix_cols[0]:
        label_prefix = st.text_input("Label prefix", value="B", key="rebar_perimeter_label_prefix")
    with prefix_cols[1]:
        st.caption(
            "Default controls: 50 mm to bar center and 150 mm target spacing. Use the preview as an engineering starting layout, then adjust manually if needed."
        )

    result = generate_perimeter_rebar_layout(
        geometry,
        bar_size=bar_size or "DB20",
        diameter_mm=float(diameter_mm),
        material=material or default_material,
        edge_offset_mm=float(edge_offset_mm),
        target_spacing_mm=float(target_spacing_mm),
        min_bars=int(min_bars),
        label_prefix=label_prefix,
    )

    if result.errors:
        for error in result.errors:
            st.error(f"ERROR: {error}")
    if result.warnings:
        for warning in result.warnings:
            st.warning(f"WARNING: {warning}")
    if result.info:
        for info in result.info:
            st.info(f"INFO: {info}")

    if result.ok and not result.table.empty:
        metric_cols = st.columns(3)
        metric_cols[0].metric("Generated bars", f"{len(result.table):,}")
        metric_cols[1].metric("Actual spacing", f"{(result.actual_spacing_mm or 0.0):.1f} mm")
        metric_cols[2].metric("Offset", f"{edge_offset_mm:.1f} mm")
        st.dataframe(result.table, use_container_width=True, hide_index=True)
        st.button(
            "Apply generated perimeter layout to Rebar table",
            type="primary",
            key="rebar_apply_perimeter_layout",
            on_click=_apply_generated_perimeter_layout_to_rebar_table,
            args=(_ensure_rebar_table_columns(result.table),),
        )
    else:
        st.caption("No generated perimeter layout is available yet.")

    return result


def _render_rebar_editor(table: pd.DataFrame, bar_size_options: list[str], editor_key: str) -> pd.DataFrame:
    return st.data_editor(
        _ensure_rebar_table_columns(table),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=_rebar_column_config(bar_size_options),
        key=editor_key,
    )




def _beam_girder_span_length_for_shear_layout() -> float:
    settings = system_settings_from_mapping(st.session_state.get(BEAM_GIRDER_SYSTEM_SETTINGS_KEY))
    try:
        span = float(settings.span_length_m)
    except (TypeError, ValueError):
        span = 20.0
    return span if span > 0.0 else 20.0


def _default_shear_reinforcement_table(span_length_m: float | None = None) -> pd.DataFrame:
    span = float(span_length_m or 20.0)
    if span <= 0.0:
        span = 20.0
    # Keep the default compact and safe.  The rows are inactive until the
    # engineer confirms the provided layout.  DB12 is the default bar as
    # requested, with symmetric support/transition/midspan zones.
    left_support = min(0.15 * span, 3.0)
    left_transition = min(0.30 * span, max(left_support, 6.0))
    right_transition = span - left_transition
    right_support = span - left_support
    if right_transition < left_transition:
        left_transition = 0.40 * span
        right_transition = 0.60 * span
    rows = [
        ("Left support", 0.0, left_support, 100.0, "Template zone — verify support shear demand before activating."),
        ("Left transition", left_support, left_transition, 150.0, "Template zone — adjust spacing after shear design."),
        ("Midspan", left_transition, right_transition, 250.0, "Template zone — usually governed by minimum transverse reinforcement."),
        ("Right transition", right_transition, right_support, 150.0, "Template zone — adjust spacing after shear design."),
        ("Right support", right_support, span, 100.0, "Template zone — verify support shear demand before activating."),
    ]
    return pd.DataFrame(
        [
            {
                "Active": False,
                "Zone": zone,
                "x_start_m": round(float(x0), 3),
                "x_end_m": round(float(x1), 3),
                "Bar Size": DEFAULT_SHEAR_STIRRUP_BAR,
                "Diameter_mm": 12.0,
                "Legs": DEFAULT_SHEAR_STIRRUP_LEGS,
                "Spacing_mm": float(spacing),
                "fy_MPa": DEFAULT_SHEAR_STIRRUP_FY_MPA,
                "Note": note,
            }
            for zone, x0, x1, spacing, note in rows
        ],
        columns=SHEAR_REINFORCEMENT_COLUMNS,
    )


def _default_column_pier_transverse_reinforcement_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": False,
                "Zone": "Control section",
                "x_start_m": 0.0,
                "x_end_m": 0.0,
                "Bar Size": DEFAULT_SHEAR_STIRRUP_BAR,
                "Diameter_mm": 12.0,
                "Legs": DEFAULT_SHEAR_STIRRUP_LEGS,
                "Spacing_mm": DEFAULT_SHEAR_STIRRUP_SPACING_MM,
                "fy_MPa": DEFAULT_SHEAR_STIRRUP_FY_MPA,
                "Note": "Control section transverse reinforcement used by current Column/Pier shear and torsion preview checks.",
            }
        ],
        columns=SHEAR_REINFORCEMENT_COLUMNS,
    )


def _ensure_shear_reinforcement_columns(df: pd.DataFrame) -> pd.DataFrame:
    table = df.copy()
    for column in SHEAR_REINFORCEMENT_COLUMNS:
        if column not in table.columns:
            table[column] = None
    return table[SHEAR_REINFORCEMENT_COLUMNS]


def _collapse_legacy_column_pier_transverse_template(table: pd.DataFrame) -> pd.DataFrame:
    """Collapse the old three-region Column/Pier template into one control row.

    Current Column/Pier shear/torsion preview checks consume one governing
    transverse input.  Only the exact legacy template zone names are migrated so
    user-authored multi-row tables are preserved.
    """

    normalized = _ensure_shear_reinforcement_columns(table)
    legacy_zones = {"End confinement A", "Typical shaft/core", "End confinement B"}
    zones = {str(value or "").strip() for value in normalized["Zone"].tolist()}
    if len(normalized.index) != 3 or zones != legacy_zones:
        return normalized
    candidates = normalized.copy()
    active_candidates = candidates[candidates["Active"].map(_to_bool)].copy()
    if not active_candidates.empty:
        candidates = active_candidates

    def _avs_sort_key(row: pd.Series) -> tuple[float, float]:
        diameter = _to_float(row.get("Diameter_mm"))
        legs = _to_float(row.get("Legs"))
        spacing = _to_float(row.get("Spacing_mm"))
        if diameter is None or legs is None or spacing is None or spacing <= 0.0:
            return (float("inf"), float("inf"))
        area = math.pi * float(diameter) ** 2 / 4.0
        return (float(area) * float(legs) / float(spacing), -float(spacing))

    control = candidates.iloc[0].copy()
    control_key = _avs_sort_key(control)
    for _, row in candidates.iterrows():
        key = _avs_sort_key(row)
        if key < control_key:
            control = row.copy()
            control_key = key
    control["Active"] = bool(active_candidates.shape[0] > 0)
    control["Zone"] = "Control section"
    control["x_start_m"] = 0.0
    control["x_end_m"] = 0.0
    control["Note"] = "Migrated from legacy three-region template; current Column/Pier shear/torsion previews use this single control section input."
    return pd.DataFrame([control.to_dict()], columns=SHEAR_REINFORCEMENT_COLUMNS)


def _shear_stirrup_bar_area_mm2(bar_size: str, rebar_db: pd.DataFrame) -> float | None:
    matches = rebar_db.loc[rebar_db["name"] == str(bar_size).strip(), "area_mm2"]
    if matches.empty:
        return None
    try:
        return float(matches.iloc[0])
    except (TypeError, ValueError):
        return None


def _normalize_shear_reinforcement_table(edited_df: pd.DataFrame, previous_df: pd.DataFrame | None, rebar_db: pd.DataFrame) -> pd.DataFrame:
    table = _ensure_shear_reinforcement_columns(edited_df)
    previous = _ensure_shear_reinforcement_columns(previous_df) if previous_df is not None else pd.DataFrame(columns=SHEAR_REINFORCEMENT_COLUMNS)
    for index, row in table.iterrows():
        bar_size = _normalized_bar_size(row.get("Bar Size")) or DEFAULT_SHEAR_STIRRUP_BAR
        if bar_size not in SHEAR_STIRRUP_BAR_OPTIONS:
            bar_size = DEFAULT_SHEAR_STIRRUP_BAR
            table.at[index, "Bar Size"] = bar_size
        default_diameter = _diameter_from_database(bar_size, rebar_db) or 12.0
        previous_bar = _previous_bar_size(previous, index)
        if bar_size != previous_bar or _is_blank(row.get("Diameter_mm")):
            table.at[index, "Diameter_mm"] = default_diameter
        if _is_blank(row.get("Legs")):
            table.at[index, "Legs"] = DEFAULT_SHEAR_STIRRUP_LEGS
        if _is_blank(row.get("Spacing_mm")):
            table.at[index, "Spacing_mm"] = DEFAULT_SHEAR_STIRRUP_SPACING_MM
        if _is_blank(row.get("fy_MPa")):
            table.at[index, "fy_MPa"] = DEFAULT_SHEAR_STIRRUP_FY_MPA
        if _is_blank(row.get("Active")):
            table.at[index, "Active"] = False
    return table


def _shear_reinforcement_preview_dataframe(
    df: pd.DataFrame,
    rebar_db: pd.DataFrame,
    *,
    allow_zero_length_reference: bool = False,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    table = _ensure_shear_reinforcement_columns(df)
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    warnings: list[str] = []
    active_count = 0
    for index, row in table.iterrows():
        row_number = int(index) + 1
        if all(_is_blank(row.get(column)) for column in ["Zone", "x_start_m", "x_end_m", "Bar Size", "Legs", "Spacing_mm", "Note"]):
            continue
        active = _to_bool(row.get("Active"))
        if active:
            active_count += 1
        x0 = _to_float(row.get("x_start_m"))
        x1 = _to_float(row.get("x_end_m"))
        legs = _to_count(row.get("Legs"))
        spacing = _to_float(row.get("Spacing_mm"))
        fy = _to_float(row.get("fy_MPa"))
        bar_size = str(row.get("Bar Size") or DEFAULT_SHEAR_STIRRUP_BAR).strip()
        area = _shear_stirrup_bar_area_mm2(bar_size, rebar_db)
        row_errors: list[str] = []
        if x0 is None or x1 is None:
            row_errors.append("x start/end must be numeric")
        elif allow_zero_length_reference and x1 < x0:
            row_errors.append("reference end must be greater than or equal to reference start")
        elif not allow_zero_length_reference and x1 <= x0:
            row_errors.append("x end must be greater than x start")
        if bar_size not in SHEAR_STIRRUP_BAR_OPTIONS:
            row_errors.append("bar size must be DB10, DB12, DB16, DB20, or DB25")
        if area is None:
            row_errors.append("bar area not found")
        if legs is None or legs < 1:
            row_errors.append("legs must be an integer ≥ 1")
        if spacing is None or spacing <= 0:
            row_errors.append("spacing must be positive")
        if fy is None or fy <= 0:
            row_errors.append("fy must be positive")
        if row_errors:
            errors.append(f"Row {row_number}: " + "; ".join(row_errors) + ".")
            avs_mm2_per_mm = None
            avs_mm2_per_m = None
        else:
            avs_mm2_per_mm = float(area) * float(legs) / float(spacing)
            avs_mm2_per_m = avs_mm2_per_mm * 1000.0
        rows.append(
            {
                "Active": active,
                "Zone": str(row.get("Zone") or f"Zone {row_number}"),
                "x start (m)": x0 if x0 is not None else "-",
                "x end (m)": x1 if x1 is not None else "-",
                "Stirrup": f"{bar_size} × {legs or '-'} legs @ {spacing if spacing is not None else '-'} mm",
                "fy (MPa)": fy if fy is not None else "-",
                "Av/s (mm²/mm)": avs_mm2_per_mm if avs_mm2_per_mm is not None else "-",
                "Av/s (mm²/m)": avs_mm2_per_m if avs_mm2_per_m is not None else "-",
                "Note": str(row.get("Note") or ""),
            }
        )
    if active_count == 0:
        warnings.append("No active shear reinforcement zones are confirmed yet. Future φVn check will remain NOT READY until provided stirrup zones are activated.")
    return pd.DataFrame(rows), errors, warnings


def _section_outer_min_dimension_mm(geometry: SectionGeometry | None) -> float | None:
    if geometry is None:
        return None
    try:
        outer = Polygon([point.as_tuple() for point in geometry.outer_polygon])
        minx, miny, maxx, maxy = outer.bounds
    except Exception:
        return None
    width = float(maxx) - float(minx)
    depth = float(maxy) - float(miny)
    if width <= 0.0 or depth <= 0.0:
        return None
    return min(width, depth)


def _min_rebar_diameter_mm(rebars: list[Rebar] | tuple[Rebar, ...] | None) -> float | None:
    values = [
        float(getattr(rebar, "diameter_mm", 0.0))
        for rebar in (rebars or [])
        if getattr(rebar, "diameter_mm", None) is not None and float(getattr(rebar, "diameter_mm", 0.0)) > 0.0
    ]
    return min(values) if values else None


def _round_down_to_increment(value: float, increment: float = COLUMN_PIER_SEISMIC_SPACING_INCREMENT_MM) -> float:
    if not math.isfinite(value) or value <= 0.0:
        return value
    if increment <= 0.0:
        return value
    return max(increment, math.floor(value / increment) * increment)


def _aci_special_seismic_spacing_advisor(
    *,
    section_min_dimension_mm: float | None,
    min_longitudinal_bar_diameter_mm: float | None,
    hx_mm: float | None,
    spacing_increment_mm: float = COLUMN_PIER_SEISMIC_SPACING_INCREMENT_MM,
) -> SeismicSpacingAdvisorResult:
    """Return a guarded ACI 318 special-column confinement spacing advisor.

    This is an input advisor, not a final code certification gate.  It covers
    the common special seismic column spacing screen only; hoop configuration,
    hook anchorage, confinement length, shear demand, and project seismic
    system classification remain engineering review items.
    """

    criteria: list[dict[str, object]] = []
    warnings: list[str] = []
    notes: list[str] = [
        "Advisor only: verify seismic design category, frame/bridge system, confinement length, hook anchorage, and local code amendments before final design.",
    ]

    def _add(label: str, value: float | None, basis: str) -> None:
        criteria.append(
            {
                "Criterion": label,
                "Limit (mm)": round(float(value), 3) if value is not None and math.isfinite(float(value)) else "-",
                "Basis": basis,
            }
        )

    min_dim_limit = None
    if section_min_dimension_mm is not None and section_min_dimension_mm > 0.0:
        min_dim_limit = float(section_min_dimension_mm) / 4.0
    else:
        warnings.append("Section outside dimension is unavailable; cannot evaluate the one-quarter member-dimension limit.")
    _add("0.25 x minimum outside section dimension", min_dim_limit, "ACI 318 special seismic column spacing screen")

    db_limit = None
    if min_longitudinal_bar_diameter_mm is not None and min_longitudinal_bar_diameter_mm > 0.0:
        db_limit = 6.0 * float(min_longitudinal_bar_diameter_mm)
    else:
        warnings.append("Active ordinary longitudinal bar diameter is unavailable; cannot evaluate the 6db limit.")
    _add("6 x smallest active longitudinal bar diameter", db_limit, "ACI 318 special seismic column spacing screen")

    so_limit = None
    if hx_mm is not None and hx_mm > 0.0:
        so_raw = 100.0 + (350.0 - float(hx_mm)) / 3.0
        so_limit = min(150.0, max(100.0, so_raw))
        if float(hx_mm) > 350.0:
            warnings.append("hx exceeds 350 mm; lateral support spacing of longitudinal bars needs engineering review.")
    else:
        warnings.append("hx is unavailable; cannot evaluate the s0 confinement spacing limit.")
    _add("s0 from hx, bounded to 100-150 mm", so_limit, "ACI 318 special seismic column spacing screen")

    finite_limits = [
        (label, value)
        for label, value in [
            ("0.25 x minimum outside section dimension", min_dim_limit),
            ("6 x smallest active longitudinal bar diameter", db_limit),
            ("s0 from hx", so_limit),
        ]
        if value is not None and math.isfinite(float(value)) and float(value) > 0.0
    ]
    if not finite_limits:
        return SeismicSpacingAdvisorResult(
            status="REVIEW",
            code_basis="ACI 318 special seismic confinement advisor",
            s_max_mm=None,
            suggested_spacing_mm=None,
            governing_limit="Unavailable",
            criteria=tuple(criteria),
            warnings=tuple(warnings),
            notes=tuple(notes),
        )

    governing_limit, s_max = min(finite_limits, key=lambda item: float(item[1]))
    suggested = _round_down_to_increment(float(s_max), spacing_increment_mm)
    return SeismicSpacingAdvisorResult(
        status="Advisor ready" if not warnings else "REVIEW",
        code_basis="ACI 318 special seismic confinement advisor",
        s_max_mm=float(s_max),
        suggested_spacing_mm=float(suggested),
        governing_limit=governing_limit,
        criteria=tuple(criteria),
        warnings=tuple(warnings),
        notes=tuple(notes),
    )



def _section_outer_dimensions_area_mm(geometry: SectionGeometry | None) -> dict[str, float] | None:
    if geometry is None:
        return None
    try:
        outer = Polygon([point.as_tuple() for point in geometry.outer_polygon])
        section_poly = to_shapely_polygon(geometry)
        minx, miny, maxx, maxy = outer.bounds
    except Exception:
        return None
    width = float(maxx) - float(minx)
    depth = float(maxy) - float(miny)
    area = float(getattr(section_poly, "area", outer.area))
    if width <= 0.0 or depth <= 0.0 or area <= 0.0:
        return None
    return {"width_mm": width, "depth_mm": depth, "area_mm2": area, "min_dim_mm": min(width, depth), "max_dim_mm": max(width, depth)}


def _concrete_fc_mpa_from_state(default: float | None = None) -> float | None:
    concrete = st.session_state.get("concrete_material")
    value = getattr(concrete, "fc_MPa", None)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) and numeric > 0.0 else default


def _aashto_lrfd_seismic_bridge_column_advisor(
    *,
    section_geometry: SectionGeometry | None,
    settings: dict[str, Any],
    table: pd.DataFrame,
    rebar_db: pd.DataFrame,
    fc_MPa: float | None,
    spacing_increment_mm: float = COLUMN_PIER_SEISMIC_SPACING_INCREMENT_MM,
) -> SeismicSpacingAdvisorResult:
    """Return a bounded AASHTO LRFD bridge-column seismic detailing advisor.

    Scope is intentionally limited to the current control-section row: Article
    5.11.4.1.5 confinement spacing/length and Article 5.11.4.1.4 hoop or
    spiral confinement area.  The result remains an input/detailing advisor;
    it does not create overstrength shear demand, R-factor selection, splice
    qualification, or shop-drawing hook certification.
    """

    criteria: list[dict[str, object]] = []
    warnings: list[str] = []
    notes: list[str] = [
        "AASHTO LRFD seismic advisor: checks spacing, confinement length, and transverse confinement area for the current control-section row only.",
        "Verify seismic zone, R-factor/system classification, plastic-hinge locations, lap-splice restrictions, hook anchorage, and contract drawing details separately.",
    ]

    normalized = _ensure_shear_reinforcement_columns(pd.DataFrame(table))
    if normalized.empty:
        warnings.append("No Column/Pier transverse reinforcement row is available.")
        return SeismicSpacingAdvisorResult("REVIEW", "AASHTO LRFD 9th seismic bridge-column advisor", None, None, "Unavailable", tuple(criteria), tuple(warnings), tuple(notes))
    active = normalized[normalized["Active"].map(_to_bool)].copy()
    row = active.iloc[0] if not active.empty else normalized.iloc[0]

    dims = _section_outer_dimensions_area_mm(section_geometry)
    if dims is None:
        warnings.append("Section geometry is unavailable; cannot evaluate AASHTO seismic spacing or core confinement dimensions.")
        return SeismicSpacingAdvisorResult("REVIEW", "AASHTO LRFD 9th seismic bridge-column advisor", None, None, "Unavailable", tuple(criteria), tuple(warnings), tuple(notes))
    fc = float(fc_MPa or 0.0)
    if not math.isfinite(fc) or fc <= 0.0:
        warnings.append("Concrete f'c is unavailable; cannot evaluate AASHTO confinement area equations.")
    bar_size = str(row.get("Bar Size") or DEFAULT_SHEAR_STIRRUP_BAR).strip() or DEFAULT_SHEAR_STIRRUP_BAR
    tie_area = _shear_stirrup_bar_area_mm2(bar_size, rebar_db)
    tie_diameter = _to_float(row.get("Diameter_mm")) or None
    if tie_diameter is None or tie_diameter <= 0.0:
        match = rebar_db[rebar_db["name"].astype(str) == bar_size] if isinstance(rebar_db, pd.DataFrame) and not rebar_db.empty else pd.DataFrame()
        if not match.empty:
            tie_diameter = _to_float(match.iloc[0].get("diameter_mm"))
    legs = _to_count(row.get("Legs")) or DEFAULT_SHEAR_STIRRUP_LEGS
    spacing = _to_float(row.get("Spacing_mm"))
    fyh = _to_float(row.get("fy_MPa")) or DEFAULT_SHEAR_STIRRUP_FY_MPA
    if tie_area is None or tie_area <= 0.0:
        warnings.append("Tie/hoop bar area is unavailable from the reinforcement database.")
    if spacing is None or spacing <= 0.0:
        warnings.append("Control-section spacing is unavailable.")
    if fyh is None or fyh <= 0.0:
        warnings.append("Tie/hoop yield strength is unavailable.")
    if fyh is not None and fyh > 517.106797 + 1.0e-9:
        warnings.append("AASHTO seismic hooks are limited to fyh <= 75 ksi (≈517 MPa); verify reinforcement grade before final detailing.")

    try:
        s_max, governing = aashto_seismic_column_spacing_limit_mm(float(dims["min_dim_mm"]))
    except Exception as exc:
        warnings.append(str(exc))
        s_max, governing = None, "Unavailable"
    if s_max is not None:
        criteria.append({"Criterion": "0.25 x minimum member dimension", "Limit (mm)": 0.25 * float(dims["min_dim_mm"]), "Basis": "AASHTO 5.11.4.1.5"})
        criteria.append({"Criterion": "4.0 in maximum", "Limit (mm)": inch_to_mm(4.0), "Basis": "AASHTO 5.11.4.1.5"})
        criteria.append({"Criterion": "Governing maximum spacing", "Limit (mm)": s_max, "Basis": governing})

    clear_height = _to_float(settings.get("seismic_clear_height_mm"))
    one_sixth_clear_height = float(clear_height) / 6.0 if clear_height and clear_height > 0.0 else None
    confinement_min_length = inch_to_mm(18.0)
    confinement_length_governing = "Unavailable"
    try:
        confinement_length, length_criteria = aashto_seismic_confinement_length_mm(
            max_member_dimension_mm=float(dims["max_dim_mm"]),
            clear_height_mm=clear_height if clear_height and clear_height > 0.0 else None,
        )
        criteria.extend(length_criteria)
        length_options = {
            "Maximum cross-sectional dimension": float(dims["max_dim_mm"]),
            "18.0 in minimum": confinement_min_length,
        }
        if one_sixth_clear_height is not None:
            length_options["1/6 clear height"] = one_sixth_clear_height
        confinement_length_governing = max(length_options, key=length_options.get)
        criteria.append({"Criterion": "Governing plastic-hinge confinement length", "Limit (mm)": confinement_length, "Basis": "AASHTO 5.11.4.1.5"})
        if clear_height is None or clear_height <= 0.0:
            notes.append("Clear height was not entered; the advisor can only compute a preliminary confinement length from max member dimension and 18 in. Enter clear height to include the AASHTO 1/6 clear-height criterion.")
    except Exception as exc:
        confinement_length = None
        warnings.append(str(exc))

    edge_to_center = _to_float(settings.get("tie_center_offset_mm")) or 50.0
    tie_dia_for_core = tie_diameter if tie_diameter is not None and tie_diameter > 0.0 else 12.0
    edge_to_outside = max(0.0, float(edge_to_center) - 0.5 * float(tie_dia_for_core))
    core_width = max(0.0, float(dims["width_mm"]) - 2.0 * edge_to_outside)
    core_depth = max(0.0, float(dims["depth_mm"]) - 2.0 * edge_to_outside)
    core_area = core_width * core_depth
    if core_width <= 0.0 or core_depth <= 0.0 or core_area <= 0.0:
        warnings.append("Tie/hoop offset leaves no positive AASHTO core dimension; reduce offset or define the section correctly.")
    if len(getattr(section_geometry, "holes", []) or []) > 0:
        warnings.append("Section has holes/voids; seismic confinement advisor uses the outside tied core only and remains REVIEW for hollow/local wall behavior.")

    provided_area = float(tie_area or 0.0) * float(legs or 0.0)
    required_area = None
    required_area_y = None
    provided_rho = None
    required_rho = None
    area_dc = float("nan")
    layout = str(settings.get("closed_tie_layout") or COLUMN_PIER_CLOSED_TIE_OPTIONS[0])
    if fc > 0.0 and fyh and fyh > 0.0 and spacing and spacing > 0.0 and tie_area and tie_area > 0.0 and core_area > 0.0:
        if layout == "Spiral reinforcement":
            dc = min(core_width, core_depth)
            try:
                asp_req, rho_req, rho_511, rho_564 = aashto_seismic_circular_spiral_required(
                    fc_MPa=fc,
                    fyh_MPa=float(fyh),
                    Ag_mm2=float(dims["area_mm2"]),
                    Ac_mm2=float(math.pi * (dc**2) / 4.0),
                    dc_mm=float(dc),
                    s_mm=float(spacing),
                )
                required_area = asp_req
                required_rho = rho_req
                provided_rho = 4.0 * float(tie_area) / (float(dc) * float(spacing)) if dc > 0.0 else float("nan")
                area_dc = asp_req / float(tie_area) if float(tie_area) > 0.0 else float("inf")
                criteria.append({"Criterion": "Required spiral/hoop bar area Asp", "Limit (mm)": asp_req, "Basis": "AASHTO 5.11.4.1.4-1 and 5.6.4.6"})
                criteria.append({"Criterion": "Required volumetric ratio rho_s", "Limit (mm)": rho_req, "Basis": f"max(0.12fc/fyh={rho_511:.5f}, 0.45(Ag/Ac-1)fc/fyh={rho_564:.5f})"})
                criteria.append({"Criterion": "Provided spiral/hoop bar area Asp", "Limit (mm)": float(tie_area), "Basis": bar_size})
            except Exception as exc:
                warnings.append(str(exc))
        else:
            try:
                req_x, req_x_eq2, req_x_eq3 = aashto_seismic_rectangular_ash_required_mm2(
                    fc_MPa=fc,
                    fyh_MPa=float(fyh),
                    Ag_mm2=float(dims["area_mm2"]),
                    Ac_mm2=float(core_area),
                    s_mm=float(spacing),
                    hc_mm=float(core_width),
                )
                req_y, req_y_eq2, req_y_eq3 = aashto_seismic_rectangular_ash_required_mm2(
                    fc_MPa=fc,
                    fyh_MPa=float(fyh),
                    Ag_mm2=float(dims["area_mm2"]),
                    Ac_mm2=float(core_area),
                    s_mm=float(spacing),
                    hc_mm=float(core_depth),
                )
                required_area = req_x
                required_area_y = req_y
                req_control = max(req_x, req_y)
                area_dc = req_control / provided_area if provided_area > 0.0 else float("inf")
                criteria.append({"Criterion": "Required Ash about x/core width", "Limit (mm)": req_x, "Basis": "max(AASHTO 5.11.4.1.4-2, -3)"})
                criteria.append({"Criterion": "Required Ash about y/core depth", "Limit (mm)": req_y, "Basis": "max(AASHTO 5.11.4.1.4-2, -3)"})
                criteria.append({"Criterion": "Provided Ash from selected control row", "Limit (mm)": provided_area, "Basis": f"{bar_size} x {legs} effective legs"})
                notes.append("For rectangular hoops, the app uses the control-row effective legs for both axes; verify actual hoop/cross-tie leg distribution on shop drawings.")
            except Exception as exc:
                warnings.append(str(exc))
    elif fc > 0.0:
        warnings.append("AASHTO confinement area check needs fc, fyh, bar area, spacing, and positive tied-core dimensions.")

    hook_extension = None
    if tie_dia_for_core > 0.0:
        hook_extension = max(6.0 * float(tie_dia_for_core), inch_to_mm(3.0))
        criteria.append({"Criterion": "Seismic hook extension", "Limit (mm)": hook_extension, "Basis": "larger of 6db or 3.0 in"})

    spacing_dc = float(spacing) / float(s_max) if spacing and s_max and s_max > 0.0 else float("nan")
    if warnings:
        status = "REVIEW"
    elif math.isfinite(spacing_dc) and spacing_dc > 1.0 + 1.0e-9:
        status = "FAIL"
    elif math.isfinite(area_dc) and area_dc > 1.0 + 1.0e-9:
        status = "FAIL"
    else:
        status = "PASS"
    if s_max is not None:
        suggested = _round_down_to_increment(float(s_max), spacing_increment_mm)
    else:
        suggested = None
    return SeismicSpacingAdvisorResult(
        status=status,
        code_basis="AASHTO LRFD 9th seismic bridge-column advisor",
        s_max_mm=s_max,
        suggested_spacing_mm=suggested,
        governing_limit=governing,
        criteria=tuple(criteria),
        warnings=tuple(warnings),
        notes=tuple(notes),
        clear_height_mm=clear_height if clear_height and clear_height > 0.0 else None,
        one_sixth_clear_height_mm=one_sixth_clear_height,
        max_member_dimension_mm=float(dims["max_dim_mm"]),
        confinement_min_length_mm=confinement_min_length,
        confinement_length_mm=confinement_length,
        confinement_length_governing=confinement_length_governing,
        spacing_dc=spacing_dc if math.isfinite(spacing_dc) else None,
        area_dc=area_dc if math.isfinite(area_dc) else None,
        provided_transverse_area_mm2=provided_area if provided_area > 0.0 else None,
        required_transverse_area_mm2=required_area,
        required_transverse_area_y_mm2=required_area_y,
    )

def _minimum_active_rebar_diameter_from_state(rebar_db: pd.DataFrame) -> float | None:
    parsed = st.session_state.get("rebars")
    parsed_min = _min_rebar_diameter_mm(parsed if isinstance(parsed, list) else [])
    if parsed_min is not None:
        return parsed_min
    table = st.session_state.get("rebar_table")
    if table is None:
        return None
    diameters: list[float] = []
    for _, row in pd.DataFrame(table).iterrows():
        if not _to_bool(row.get("Active")):
            continue
        diameter = _to_float(row.get("Diameter_mm"))
        if diameter is None or diameter <= 0.0:
            bar_size = _normalized_bar_size(row.get("Bar Size"))
            diameter = _diameter_from_database(bar_size, rebar_db)
        count = _to_count(row.get("Count")) or 1
        if diameter is not None and diameter > 0.0 and count > 0:
            diameters.append(float(diameter))
    return min(diameters) if diameters else None


def _shear_reinforcement_column_config() -> dict[str, Any]:
    return {
        "Active": st.column_config.CheckboxColumn("Active", width="small", help="Activate only after the zone is verified as provided reinforcement."),
        "Zone": st.column_config.TextColumn("Zone", width="medium"),
        "x_start_m": st.column_config.NumberColumn("x start (m)", min_value=0.0, step=0.1, format="%.3f", width="small"),
        "x_end_m": st.column_config.NumberColumn("x end (m)", min_value=0.0, step=0.1, format="%.3f", width="small"),
        "Bar Size": st.column_config.SelectboxColumn("Bar Size", options=SHEAR_STIRRUP_BAR_OPTIONS, width="small"),
        "Diameter_mm": st.column_config.NumberColumn("Diameter (mm)", min_value=1.0, step=1.0, format="%.1f", width="small", help="Auto-filled from selected bar size."),
        "Legs": st.column_config.NumberColumn("Legs", min_value=1, step=1, width="small"),
        "Spacing_mm": st.column_config.NumberColumn("Spacing (mm)", min_value=1.0, step=25.0, format="%.1f", width="small"),
        "fy_MPa": st.column_config.NumberColumn("fy (MPa)", min_value=1.0, step=10.0, format="%.1f", width="small"),
        "Note": st.column_config.TextColumn("Note", width="large"),
    }


def _column_pier_transverse_column_config() -> dict[str, Any]:
    return {
        "Active": st.column_config.CheckboxColumn("Active", width="small", help="Activate only after the control-section transverse reinforcement is confirmed as provided reinforcement."),
        "Zone": st.column_config.TextColumn("Control section", width="medium"),
        "x_start_m": st.column_config.NumberColumn("Reference start (m)", min_value=0.0, step=0.1, format="%.3f", width="small"),
        "x_end_m": st.column_config.NumberColumn("Reference end (m)", min_value=0.0, step=0.1, format="%.3f", width="small"),
        "Bar Size": st.column_config.SelectboxColumn("Tie / hoop size", options=SHEAR_STIRRUP_BAR_OPTIONS, width="small"),
        "Diameter_mm": st.column_config.NumberColumn("Diameter (mm)", min_value=1.0, step=1.0, format="%.1f", width="small", help="Auto-filled from selected tie/hoop size."),
        "Legs": st.column_config.NumberColumn("Effective legs", min_value=1, step=1, width="small", help="Effective transverse legs for shear. Torsion At uses the closed hoop/tie bar area, not prestress."),
        "Spacing_mm": st.column_config.NumberColumn("Spacing (mm)", min_value=1.0, step=25.0, format="%.1f", width="small"),
        "fy_MPa": st.column_config.NumberColumn("fy (MPa)", min_value=1.0, step=10.0, format="%.1f", width="small"),
        "Note": st.column_config.TextColumn("Control-section note", width="large"),
    }


def _analysis_mode_member_type_from_session() -> str:
    settings = st.session_state.get("analysis_mode_settings")
    if hasattr(settings, "member_type"):
        return str(getattr(settings, "member_type") or COLUMN_PIER_WORKFLOW_MEMBER_TYPE)
    if isinstance(settings, dict):
        return str(settings.get("member_type") or COLUMN_PIER_WORKFLOW_MEMBER_TYPE)
    return COLUMN_PIER_WORKFLOW_MEMBER_TYPE


def _is_column_pier_workflow() -> bool:
    return _analysis_mode_member_type_from_session() in {COLUMN_PIER_WORKFLOW_MEMBER_TYPE, "general_section"}


def _column_pier_transverse_settings_from_state() -> dict[str, Any]:
    raw = st.session_state.get(COLUMN_PIER_TRANSVERSE_SETTINGS_KEY)
    if raw is None:
        raw = (st.session_state.get("project_metadata", {}) or {}).get(COLUMN_PIER_TRANSVERSE_SETTINGS_KEY)
    if not isinstance(raw, dict):
        raw = {}
    closed_tie_layout = str(raw.get("closed_tie_layout") or COLUMN_PIER_CLOSED_TIE_OPTIONS[0])
    if closed_tie_layout not in COLUMN_PIER_CLOSED_TIE_OPTIONS:
        closed_tie_layout = COLUMN_PIER_CLOSED_TIE_OPTIONS[0]
    torsion_core_basis = str(raw.get("torsion_core_basis") or COLUMN_PIER_TORSION_CORE_OPTIONS[0])
    if torsion_core_basis not in COLUMN_PIER_TORSION_CORE_OPTIONS:
        torsion_core_basis = COLUMN_PIER_TORSION_CORE_OPTIONS[0]
    seismic_detailing = _normalize_column_pier_seismic_detailing_label(raw.get("seismic_detailing"))

    def _num(value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if pd.notna(numeric) and numeric > 0.0 else None

    return {
        "closed_tie_layout": closed_tie_layout,
        "torsion_core_basis": torsion_core_basis,
        "tie_center_offset_mm": _num(raw.get("tie_center_offset_mm")) or 50.0,
        "manual_core_width_mm": _num(raw.get("manual_core_width_mm")),
        "manual_core_depth_mm": _num(raw.get("manual_core_depth_mm")),
        "seismic_detailing": seismic_detailing,
        "seismic_hx_mm": _num(raw.get("seismic_hx_mm")) or COLUMN_PIER_SEISMIC_HX_DEFAULT_MM,
        "seismic_clear_height_mm": _num(raw.get("seismic_clear_height_mm")) or COLUMN_PIER_SEISMIC_CLEAR_HEIGHT_DEFAULT_MM,
        "note": str(raw.get("note") or "").strip(),
    }


def _store_column_pier_transverse_settings_metadata(settings: dict[str, Any]) -> None:
    clean = {
        "closed_tie_layout": str(settings.get("closed_tie_layout") or COLUMN_PIER_CLOSED_TIE_OPTIONS[0]),
        "torsion_core_basis": str(settings.get("torsion_core_basis") or COLUMN_PIER_TORSION_CORE_OPTIONS[0]),
        "tie_center_offset_mm": settings.get("tie_center_offset_mm"),
        "manual_core_width_mm": settings.get("manual_core_width_mm"),
        "manual_core_depth_mm": settings.get("manual_core_depth_mm"),
        "seismic_detailing": str(settings.get("seismic_detailing") or COLUMN_PIER_SEISMIC_DETAILING_DEFAULT),
        "seismic_hx_mm": settings.get("seismic_hx_mm"),
        "seismic_clear_height_mm": settings.get("seismic_clear_height_mm"),
        "note": str(settings.get("note") or "").strip(),
    }
    st.session_state[COLUMN_PIER_TRANSVERSE_SETTINGS_KEY] = clean
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    metadata[COLUMN_PIER_TRANSVERSE_SETTINGS_KEY] = clean
    st.session_state["project_metadata"] = metadata


def _store_column_pier_transverse_metadata(table: pd.DataFrame) -> None:
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    metadata[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = _ensure_shear_reinforcement_columns(table).to_dict(orient="records")
    st.session_state["project_metadata"] = metadata


def _column_pier_transverse_readiness_cards(
    table: pd.DataFrame,
    settings: dict[str, Any],
    rebar_count: int,
    preview_errors: list[str],
) -> list[RebarMetric]:
    active_regions = int(sum(_to_bool(value) for value in table.get("Active", []))) if not table.empty else 0
    closed_layout = str(settings.get("closed_tie_layout") or "")
    closed_ready = closed_layout in {"Closed ties / hoops", "Spiral reinforcement"}
    torsion_basis = str(settings.get("torsion_core_basis") or "")
    torsion_ready = closed_ready and active_regions > 0 and torsion_basis != "Not defined yet" and not preview_errors
    shear_ready = active_regions > 0 and not preview_errors
    longitudinal_status = "Available" if rebar_count > 0 else "Missing"
    return [
        RebarMetric("Shear input", "Ready" if shear_ready else "REVIEW", f"{active_regions} active control section row(s)", "ready" if shear_ready else "warning", strong=not shear_ready),
        RebarMetric("Torsion input", "Ready" if torsion_ready else "REVIEW", "Needs closed ties/hoops or spiral plus torsion core basis", "ready" if torsion_ready else "warning", strong=not torsion_ready),
        RebarMetric("Closed transverse reinforcement", closed_layout or "Not defined", "Do not use open ties for torsion capacity", "ready" if closed_ready else "warning"),
        RebarMetric("Longitudinal torsion bars", longitudinal_status, "Ordinary active rebar only; prestress is not counted as Al", "ready" if rebar_count > 0 else "warning"),
        RebarMetric("Capability", "Input owner only", "Analysis issues scoped ACI RC shear/torsion/V+T status from this Control section row", "neutral"),
    ]


def _render_column_pier_transverse_settings() -> dict[str, Any]:
    current = _column_pier_transverse_settings_from_state()
    st.markdown("#### Column/Pier Shear and Torsion Reinforcement")
    st.caption(
        "Define the control-section transverse reinforcement used by the current Column/Pier shear, torsion, and V+T Analysis checks. "
        "Future station/height-specific region checks will be a separate milestone; capacity status is reported in Analysis, not from this input page."
    )
    col_a, col_b, col_c = st.columns([1.0, 1.0, 1.0], gap="small")
    with col_a:
        closed_tie_layout = st.selectbox(
            "Transverse reinforcement type",
            COLUMN_PIER_CLOSED_TIE_OPTIONS,
            index=COLUMN_PIER_CLOSED_TIE_OPTIONS.index(current["closed_tie_layout"]),
            key="column_pier_transverse_closed_tie_layout",
            help="Torsion capacity requires closed transverse reinforcement. Open ties are retained for shear-only review and are guarded for torsion.",
        )
    with col_b:
        torsion_core_basis = st.selectbox(
            "Torsion core basis",
            COLUMN_PIER_TORSION_CORE_OPTIONS,
            index=COLUMN_PIER_TORSION_CORE_OPTIONS.index(current["torsion_core_basis"]),
            key="column_pier_transverse_torsion_core_basis",
            help="Column/Pier torsion and V+T checks use Ao/Aoh or equivalent core geometry from this owner. Unsupported routes remain guarded in Analysis.",
        )
    with col_c:
        tie_center_offset_mm = st.number_input(
            "Tie/hoop center offset (mm)",
            min_value=1.0,
            value=float(current["tie_center_offset_mm"] or 50.0),
            step=5.0,
            format="%.1f",
            key="column_pier_transverse_tie_offset_mm",
        )
    manual_disabled = torsion_core_basis != "Manual core dimensions"
    col_w, col_d, col_note = st.columns([1.0, 1.0, 2.0], gap="small")
    with col_w:
        manual_core_width_mm = st.number_input(
            "Manual core width bo (mm)",
            min_value=0.0,
            value=float(current.get("manual_core_width_mm") or 0.0),
            step=10.0,
            format="%.1f",
            disabled=manual_disabled,
            key="column_pier_transverse_core_width_mm",
        )
    with col_d:
        manual_core_depth_mm = st.number_input(
            "Manual core depth ho (mm)",
            min_value=0.0,
            value=float(current.get("manual_core_depth_mm") or 0.0),
            step=10.0,
            format="%.1f",
            disabled=manual_disabled,
            key="column_pier_transverse_core_depth_mm",
        )
    with col_note:
        note = st.text_input(
            "Transverse reinforcement note",
            value=str(current.get("note") or ""),
            key="column_pier_transverse_note",
            placeholder="e.g. closed hoops with seismic confinement zone at member ends",
        )
    seismic_cols = st.columns([1.4, 0.8, 1.8], gap="small")
    with seismic_cols[0]:
        seismic_detailing = st.selectbox(
            "Seismic spacing advisor",
            COLUMN_PIER_SEISMIC_DETAILING_OPTIONS,
            index=COLUMN_PIER_SEISMIC_DETAILING_OPTIONS.index(current["seismic_detailing"]),
            key="column_pier_transverse_seismic_detailing",
            help="Input advisor only. It recommends a control-section tie/hoop spacing for seismic confinement review; it is not a final code certification.",
        )
    with seismic_cols[1]:
        if _is_aashto_column_pier_seismic_advisor(seismic_detailing):
            seismic_clear_height_mm = st.number_input(
                "Clear height for confinement length (mm)",
                min_value=0.0,
                value=float(current.get("seismic_clear_height_mm") or COLUMN_PIER_SEISMIC_CLEAR_HEIGHT_DEFAULT_MM),
                step=100.0,
                format="%.1f",
                key="column_pier_transverse_seismic_clear_height_mm",
                help="Optional AASHTO 5.11.4.1.5 clear height used for the 1/6 clear-height confinement-length criterion. Use 0.0 if not defined yet.",
            )
            seismic_hx_mm = float(current.get("seismic_hx_mm") or COLUMN_PIER_SEISMIC_HX_DEFAULT_MM)
        else:
            seismic_hx_mm = st.number_input(
                "hx for confinement (mm)",
                min_value=1.0,
                value=float(current.get("seismic_hx_mm") or COLUMN_PIER_SEISMIC_HX_DEFAULT_MM),
                step=25.0,
                format="%.1f",
                disabled=seismic_detailing != "ACI 318 special seismic confinement advisor",
                key="column_pier_transverse_seismic_hx_mm",
                help="Maximum horizontal spacing of supported longitudinal bars around the hoop/tie perimeter used by the ACI spacing advisor.",
            )
            seismic_clear_height_mm = float(current.get("seismic_clear_height_mm") or COLUMN_PIER_SEISMIC_CLEAR_HEIGHT_DEFAULT_MM)
    with seismic_cols[2]:
        if seismic_detailing == "ACI 318 special seismic confinement advisor":
            st.caption("Advisor will compare 0.25 section dimension, 6db, and s0 from hx; verify confinement length, hook anchorage, and seismic system separately.")
        elif _is_aashto_column_pier_seismic_advisor(seismic_detailing):
            st.caption("AASHTO advisor checks Section 5.11.4 spacing, plastic-hinge confinement length, and hoop/spiral confinement area from the current control-section row.")
        elif seismic_detailing == "Project-specific manual review":
            st.caption("Use project-specific seismic detailing rules manually; the app will not override the provided control-section spacing.")
        else:
            st.caption("No seismic confinement spacing advisor is applied.")
    settings = {
        "closed_tie_layout": closed_tie_layout,
        "torsion_core_basis": torsion_core_basis,
        "tie_center_offset_mm": float(tie_center_offset_mm) if float(tie_center_offset_mm) > 0.0 else None,
        "manual_core_width_mm": float(manual_core_width_mm) if not manual_disabled and float(manual_core_width_mm) > 0.0 else None,
        "manual_core_depth_mm": float(manual_core_depth_mm) if not manual_disabled and float(manual_core_depth_mm) > 0.0 else None,
        "seismic_detailing": seismic_detailing,
        "seismic_hx_mm": float(seismic_hx_mm) if float(seismic_hx_mm) > 0.0 else COLUMN_PIER_SEISMIC_HX_DEFAULT_MM,
        "seismic_clear_height_mm": float(seismic_clear_height_mm) if float(seismic_clear_height_mm) > 0.0 else COLUMN_PIER_SEISMIC_CLEAR_HEIGHT_DEFAULT_MM,
        "note": note,
    }
    _store_column_pier_transverse_settings_metadata(settings)
    if closed_tie_layout == "Open ties - shear only review":
        st.warning("Open ties are guarded for torsion. Future torsion capacity must remain REVIEW/NOT READY unless closed hoops/ties or spiral reinforcement are provided.")
    else:
        st.info("Closed transverse reinforcement is recorded as the torsion transverse source for the current control-section preview. Verify hooks, anchorage, spacing, and confinement requirements before final design.")
    return settings


def _render_column_pier_seismic_spacing_advisor(
    settings: dict[str, Any],
    table: pd.DataFrame,
    rebar_db: pd.DataFrame,
) -> None:
    seismic_detailing = _normalize_column_pier_seismic_detailing_label(settings.get("seismic_detailing"))
    if seismic_detailing == "Not selected / ordinary detailing":
        st.info("Seismic spacing advisor is not selected. Current control-section spacing remains user-provided.")
        return
    if _is_aashto_column_pier_seismic_advisor(seismic_detailing):
        geometry = st.session_state.get("section_geometry")
        fc_MPa = _concrete_fc_mpa_from_state()
        result = _aashto_lrfd_seismic_bridge_column_advisor(
            section_geometry=geometry if isinstance(geometry, SectionGeometry) else None,
            settings=settings,
            table=table,
            rebar_db=rebar_db,
            fc_MPa=fc_MPa,
        )
        with st.expander("AASHTO LRFD seismic bridge-column transverse advisor", expanded=True):
            st.caption(
                "Section 5.11.4 input advisor for expected plastic-hinge regions. "
                "It checks control-row spacing, confinement length, and hoop/spiral confinement area; final seismic system, splice, and hook detailing remain engineer review items."
            )
            spacing_status = "REVIEW"
            if result.spacing_dc is not None:
                spacing_status = "PASS" if result.spacing_dc <= 1.0 + 1.0e-9 else f"FAIL D/C {result.spacing_dc:.2f}"
            area_status = "REVIEW"
            if result.area_dc is not None:
                area_status = "PASS" if result.area_dc <= 1.0 + 1.0e-9 else f"FAIL D/C {result.area_dc:.2f}"
            headline_metrics, check_metrics = _aashto_seismic_advisor_status_metrics(
                result, spacing_status=spacing_status, area_status=area_status
            )
            st.markdown(_strip_html(headline_metrics), unsafe_allow_html=True)
            st.markdown(_strip_html(check_metrics), unsafe_allow_html=True)
            normalized = _ensure_shear_reinforcement_columns(pd.DataFrame(table))
            current_spacing = None
            if not normalized.empty:
                current_spacing = _to_float(normalized.iloc[0].get("Spacing_mm"))

            if result.status == "FAIL":
                st.error(
                    "Overall seismic transverse detailing is FAIL / REVIEW for the selected control-section row. "
                    "Shear strength may still pass, but seismic confinement must be revised before this transverse detail is treated as final."
                )
            elif result.status == "REVIEW":
                st.warning(
                    "Overall seismic transverse detailing remains REVIEW because one or more required inputs or detailing assumptions are missing."
                )
            else:
                st.success(
                    "AASHTO seismic advisor checks pass for the current control-section row. Final seismic zone, hooks, splices, and drawing details still require engineering review."
                )

            st.markdown("##### Recommended seismic detailing summary")
            st.markdown(
                _strip_html(_aashto_seismic_detailing_summary_metrics(result, current_spacing_mm=current_spacing)),
                unsafe_allow_html=True,
            )
            st.markdown(
                _aashto_seismic_required_action_callout_html(result, current_spacing_mm=current_spacing),
                unsafe_allow_html=True,
            )
            fail_reasons = _aashto_seismic_fail_reason_messages(result, current_spacing_mm=current_spacing)
            if fail_reasons:
                for message in fail_reasons:
                    st.error(message)
            elif result.status == "PASS":
                st.info(
                    "Spacing and Ash/rho area checks pass for the current control-section row. "
                    "Use the confinement length below for expected plastic-hinge regions and verify hooks, cross-ties, splices, and drawing details separately."
                )

            st.markdown("##### Plastic-hinge confinement length assistant")
            length_cols = st.columns(5)
            length_cols[0].metric(
                "Clear height input",
                "Input required" if result.clear_height_mm is None else f"{result.clear_height_mm:.0f} mm",
            )
            length_cols[1].metric(
                "1/6 clear height",
                "-" if result.one_sixth_clear_height_mm is None else f"{result.one_sixth_clear_height_mm:.0f} mm",
            )
            length_cols[2].metric(
                "Max section dim.",
                "-" if result.max_member_dimension_mm is None else f"{result.max_member_dimension_mm:.0f} mm",
            )
            length_cols[3].metric(
                "18 in minimum",
                "-" if result.confinement_min_length_mm is None else f"{result.confinement_min_length_mm:.0f} mm",
            )
            length_cols[4].metric(
                "Use length",
                "-" if result.confinement_length_mm is None else f"{result.confinement_length_mm:.0f} mm",
            )
            if result.clear_height_mm is None:
                st.warning(
                    "Input required: enter the column clear height above to include the AASHTO 1/6 clear-height criterion. "
                    "Until then, the displayed confinement length is preliminary and only uses max section dimension and 18 in."
                )
            else:
                st.info(
                    f"Use a special transverse confinement length not less than {float(result.confinement_length_mm or 0.0):.0f} mm "
                    f"at expected plastic-hinge regions; governing criterion: {result.confinement_length_governing or 'AASHTO 5.11.4.1.5'}."
                )
            if result.criteria:
                with st.expander("Detailed AASHTO 5.11.4 calculation trace", expanded=False):
                    criteria_df = pd.DataFrame(result.criteria)
                    if "Limit (mm)" in criteria_df.columns:
                        criteria_df = criteria_df.rename(columns={"Limit (mm)": "Value"})
                    st.dataframe(criteria_df, use_container_width=True, hide_index=True)
            for warning in result.warnings:
                st.warning(warning)
            for note in result.notes:
                st.info(note)
            normalized = _ensure_shear_reinforcement_columns(pd.DataFrame(table))
            apply_disabled = result.suggested_spacing_mm is None or normalized.empty
            if st.button(
                "Apply AASHTO suggested spacing to control section",
                use_container_width=True,
                disabled=apply_disabled,
                key="column_pier_apply_aashto_seismic_spacing_advisor",
            ):
                updated = normalized.copy()
                updated.at[0, "Active"] = True
                updated.at[0, "Spacing_mm"] = float(result.suggested_spacing_mm or 0.0)
                existing_note = str(updated.at[0, "Note"] or "").strip()
                advisor_note = f"AASHTO seismic advisor applied: s <= {float(result.suggested_spacing_mm or 0.0):.0f} mm; verify 5.11.4 confinement length, hooks, splices, and cross-ties."
                updated.at[0, "Note"] = advisor_note if not existing_note else f"{existing_note} {advisor_note}"
                st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = updated
                st.session_state["column_pier_transverse_reinforcement_editor_revision"] = int(st.session_state.get("column_pier_transverse_reinforcement_editor_revision", 0)) + 1
                _store_column_pier_transverse_metadata(updated)
                st.rerun()
        return
    if seismic_detailing == "Project-specific manual review":
        st.warning("Project-specific seismic detailing is selected. The app will not auto-recommend spacing; document the governing project clause in the transverse reinforcement note.")
        return

    geometry = st.session_state.get("section_geometry")
    section_min_dimension_mm = _section_outer_min_dimension_mm(geometry if isinstance(geometry, SectionGeometry) else None)
    min_bar_diameter_mm = _minimum_active_rebar_diameter_from_state(rebar_db)
    hx_mm = _to_float(settings.get("seismic_hx_mm")) or COLUMN_PIER_SEISMIC_HX_DEFAULT_MM
    result = _aci_special_seismic_spacing_advisor(
        section_min_dimension_mm=section_min_dimension_mm,
        min_longitudinal_bar_diameter_mm=min_bar_diameter_mm,
        hx_mm=hx_mm,
    )

    with st.expander("Seismic transverse spacing advisor", expanded=True):
        st.caption(
            "ACI 318 special seismic confinement spacing advisor for the control section. "
            "This is guidance for input selection, not final code certification."
        )
        metric_cols = st.columns(5)
        metric_cols[0].metric("Advisor status", result.status)
        metric_cols[1].metric("Max spacing", "-" if result.s_max_mm is None else f"{result.s_max_mm:.1f} mm")
        metric_cols[2].metric("Suggested spacing", "-" if result.suggested_spacing_mm is None else f"{result.suggested_spacing_mm:.0f} mm")
        metric_cols[3].metric("Governing", result.governing_limit)
        metric_cols[4].metric("hx", f"{hx_mm:.0f} mm")
        if result.criteria:
            st.dataframe(pd.DataFrame(result.criteria), use_container_width=True, hide_index=True)
        for warning in result.warnings:
            st.warning(warning)
        for note in result.notes:
            st.info(note)
        current_spacing = None
        normalized = _ensure_shear_reinforcement_columns(pd.DataFrame(table))
        if not normalized.empty:
            current_spacing = _to_float(normalized.iloc[0].get("Spacing_mm"))
        if result.suggested_spacing_mm is not None and current_spacing is not None:
            if current_spacing <= result.suggested_spacing_mm + 1.0e-9:
                st.success("Current control-section spacing is not greater than the advisor spacing.")
            else:
                st.warning("Current control-section spacing is greater than the advisor spacing; review seismic confinement before relying on this input.")
        apply_disabled = result.suggested_spacing_mm is None or normalized.empty
        if st.button(
            "Apply suggested spacing to control section",
            use_container_width=True,
            disabled=apply_disabled,
            key="column_pier_apply_seismic_spacing_advisor",
        ):
            updated = normalized.copy()
            updated.at[0, "Active"] = True
            updated.at[0, "Spacing_mm"] = float(result.suggested_spacing_mm or 0.0)
            existing_note = str(updated.at[0, "Note"] or "").strip()
            advisor_note = f"ACI seismic spacing advisor applied: s <= {float(result.suggested_spacing_mm or 0.0):.0f} mm; verify final detailing."
            updated.at[0, "Note"] = advisor_note if not existing_note else f"{existing_note} {advisor_note}"
            st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = updated
            st.session_state["column_pier_transverse_reinforcement_editor_revision"] = int(st.session_state.get("column_pier_transverse_reinforcement_editor_revision", 0)) + 1
            _store_column_pier_transverse_metadata(updated)
            st.rerun()


def _column_pier_transverse_preview_with_seismic_advisor(
    preview_df: pd.DataFrame,
    settings: dict[str, Any],
    table: pd.DataFrame,
    rebar_db: pd.DataFrame,
) -> pd.DataFrame:
    """Append a non-capacity seismic advisor row to the Column/Pier preview.

    The returned row is display-only.  It is not stored in the transverse
    reinforcement table and is not read by shear/torsion analysis unless the
    engineer explicitly applies or copies the suggested spacing into the
    Control section row.
    """

    seismic_detailing = _normalize_column_pier_seismic_detailing_label(settings.get("seismic_detailing"))
    if seismic_detailing not in {"ACI 318 special seismic confinement advisor", COLUMN_PIER_AASHTO_SEISMIC_ADVISOR_LABEL}:
        return preview_df

    normalized = _ensure_shear_reinforcement_columns(pd.DataFrame(table))
    base_row = normalized.iloc[0] if not normalized.empty else pd.Series(dtype=object)
    geometry = st.session_state.get("section_geometry")
    if _is_aashto_column_pier_seismic_advisor(seismic_detailing):
        advisor = _aashto_lrfd_seismic_bridge_column_advisor(
            section_geometry=geometry if isinstance(geometry, SectionGeometry) else None,
            settings=settings,
            table=table,
            rebar_db=rebar_db,
            fc_MPa=_concrete_fc_mpa_from_state(),
        )
    else:
        section_min_dimension_mm = _section_outer_min_dimension_mm(geometry if isinstance(geometry, SectionGeometry) else None)
        min_bar_diameter_mm = _minimum_active_rebar_diameter_from_state(rebar_db)
        hx_mm = _to_float(settings.get("seismic_hx_mm")) or COLUMN_PIER_SEISMIC_HX_DEFAULT_MM
        advisor = _aci_special_seismic_spacing_advisor(
            section_min_dimension_mm=section_min_dimension_mm,
            min_longitudinal_bar_diameter_mm=min_bar_diameter_mm,
            hx_mm=hx_mm,
        )

    spacing = advisor.suggested_spacing_mm
    bar_size = str(base_row.get("Bar Size") or DEFAULT_SHEAR_STIRRUP_BAR).strip()
    legs = _to_count(base_row.get("Legs")) or DEFAULT_SHEAR_STIRRUP_LEGS
    fy = _to_float(base_row.get("fy_MPa")) or DEFAULT_SHEAR_STIRRUP_FY_MPA
    area = _shear_stirrup_bar_area_mm2(bar_size, rebar_db)
    avs_mm2_per_mm = float(area) * float(legs) / float(spacing) if area is not None and spacing is not None and spacing > 0.0 else None
    advisor_row = {
        "Active": False,
        "Zone": "Recommended seismic spacing (AASHTO advisor)" if _is_aashto_column_pier_seismic_advisor(seismic_detailing) else "Recommended seismic spacing (ACI advisor)",
        "x start (m)": "-",
        "x end (m)": "-",
        "Stirrup": f"{bar_size} × {legs} legs @ {spacing:.0f} mm" if spacing is not None else f"{bar_size} × {legs} legs @ -",
        "fy (MPa)": fy,
        "Av/s (mm²/mm)": avs_mm2_per_mm if avs_mm2_per_mm is not None else "-",
        "Av/s (mm²/m)": avs_mm2_per_mm * 1000.0 if avs_mm2_per_mm is not None else "-",
        "Note": "Advisor only / REVIEW. Shear and torsion analysis uses the Control section row only unless this spacing is applied to Row 1.",
    }
    if preview_df.empty:
        return pd.DataFrame([advisor_row])
    return pd.concat([preview_df, pd.DataFrame([advisor_row])], ignore_index=True)


def _shear_depth_settings_from_state() -> dict[str, Any]:
    """Return Beam/Girder effective shear-depth settings stored in metadata.

    Analysis remains read-only.  These settings live with the section/rebar
    definition because d and dv are section/detailing design parameters, not ULS
    load inputs.
    """

    raw = st.session_state.get(SHEAR_DEPTH_SETTINGS_KEY)
    if raw is None:
        raw = (st.session_state.get("project_metadata", {}) or {}).get(SHEAR_DEPTH_SETTINGS_KEY)
    if not isinstance(raw, dict):
        raw = {}
    mode = str(raw.get("mode") or SHEAR_DEPTH_MODE_AUTO)
    if mode not in {SHEAR_DEPTH_MODE_AUTO, SHEAR_DEPTH_MODE_MANUAL}:
        mode = SHEAR_DEPTH_MODE_AUTO
    def _num(value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if pd.notna(numeric) and numeric > 0.0 else None
    return {
        "mode": mode,
        "d_mm": _num(raw.get("d_mm")),
        "dv_mm": _num(raw.get("dv_mm")),
        "note": str(raw.get("note") or "").strip(),
    }


def _store_shear_depth_settings_metadata(settings: dict[str, Any]) -> None:
    clean = {
        "mode": str(settings.get("mode") or SHEAR_DEPTH_MODE_AUTO),
        "d_mm": settings.get("d_mm"),
        "dv_mm": settings.get("dv_mm"),
        "note": str(settings.get("note") or "").strip(),
    }
    st.session_state[SHEAR_DEPTH_SETTINGS_KEY] = clean
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    metadata[SHEAR_DEPTH_SETTINGS_KEY] = clean
    st.session_state["project_metadata"] = metadata


def _render_effective_shear_depth_settings() -> None:
    st.markdown("#### Beam/Girder Effective Shear Depth Basis")
    st.caption(
        "Define the source of effective d / dv used by Analysis → ULS Shear. "
        "Auto mode derives d from the active reinforcement/strand centroid and derives dv for the AASHTO route; manual mode lets the engineer lock audited design-depth values."
    )
    current = _shear_depth_settings_from_state()
    mode_options = [SHEAR_DEPTH_MODE_AUTO, SHEAR_DEPTH_MODE_MANUAL]
    mode = st.radio(
        "Effective depth input mode",
        options=mode_options,
        index=mode_options.index(current["mode"]),
        horizontal=True,
        key="beam_girder_shear_depth_mode",
        help="Use manual mode only when d/dv has been checked from the section detailing. Analysis reads this setting but does not own the input.",
    )
    col_d, col_dv, col_note = st.columns([1.0, 1.0, 2.0], gap="small")
    with col_d:
        d_mm = st.number_input(
            "Manual d (mm)",
            min_value=0.0,
            value=float(current.get("d_mm") or 0.0),
            step=10.0,
            format="%.1f",
            disabled=mode != SHEAR_DEPTH_MODE_MANUAL,
            key="beam_girder_shear_depth_d_mm",
            help="Effective depth to tension reinforcement/strand centroid. Used directly for ACI shear and as the d basis for bridge dv derivation when dv is not manually supplied.",
        )
    with col_dv:
        dv_mm = st.number_input(
            "Manual dv (mm)",
            min_value=0.0,
            value=float(current.get("dv_mm") or 0.0),
            step=10.0,
            format="%.1f",
            disabled=mode != SHEAR_DEPTH_MODE_MANUAL,
            key="beam_girder_shear_depth_dv_mm",
            help="Effective shear depth for AASHTO/bridge shear. Leave as 0 to let the app derive dv from d and section depth in auto/bridge route.",
        )
    with col_note:
        note = st.text_input(
            "Depth basis note",
            value=str(current.get("note") or ""),
            disabled=mode != SHEAR_DEPTH_MODE_MANUAL,
            key="beam_girder_shear_depth_note",
            placeholder="e.g. d from centroid of bottom strand group; dv per project design basis",
        )
    settings = {
        "mode": mode,
        "d_mm": float(d_mm) if mode == SHEAR_DEPTH_MODE_MANUAL and float(d_mm) > 0.0 else None,
        "dv_mm": float(dv_mm) if mode == SHEAR_DEPTH_MODE_MANUAL and float(dv_mm) > 0.0 else None,
        "note": note if mode == SHEAR_DEPTH_MODE_MANUAL else "",
    }
    _store_shear_depth_settings_metadata(settings)
    if mode == SHEAR_DEPTH_MODE_AUTO:
        st.info("Auto mode: Analysis will calculate d from active longitudinal reinforcement/prestress centroid at the local tension face and derive dv for the bridge/AASHTO route. Review the d/dv values in the Shear audit table.")
    else:
        if not settings["d_mm"]:
            st.warning("Manual mode is selected but manual d is not defined. Analysis will fall back to the auto d basis until a positive d is entered.")
        elif settings["dv_mm"]:
            st.success(f"Manual effective depth basis stored: d = {settings['d_mm']:.1f} mm, dv = {settings['dv_mm']:.1f} mm.")
        else:
            st.warning(f"Manual d = {settings['d_mm']:.1f} mm is stored, but manual dv is blank. Bridge/AASHTO shear will derive dv from d and section depth.")


def _store_shear_reinforcement_metadata(table: pd.DataFrame) -> None:
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    metadata[SHEAR_REINFORCEMENT_TABLE_KEY] = _ensure_shear_reinforcement_columns(table).to_dict(orient="records")
    st.session_state["project_metadata"] = metadata


def _render_shear_reinforcement_layout(rebar_db: pd.DataFrame) -> None:
    st.markdown("#### Beam/Girder Shear Reinforcement Layout")
    st.caption(
        "Define provided stirrup zones along the member for the Analysis → ULS Shear tab. "
        "Analysis reads Active zones as the provided stirrup layout for φVn; inactive zones are shown here but are not used for capacity."
    )
    span_m = _beam_girder_span_length_for_shear_layout()
    if SHEAR_REINFORCEMENT_TABLE_KEY not in st.session_state:
        existing = (st.session_state.get("project_metadata", {}) or {}).get(SHEAR_REINFORCEMENT_TABLE_KEY)
        if isinstance(existing, list):
            st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = _ensure_shear_reinforcement_columns(pd.DataFrame(existing))
        else:
            st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = _default_shear_reinforcement_table(span_m)
    st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY]))
    if "beam_girder_shear_reinforcement_editor_revision" not in st.session_state:
        st.session_state["beam_girder_shear_reinforcement_editor_revision"] = 0

    cards = [
        RebarMetric("Input method", "Zone table", "Commercial girder detailing"),
        RebarMetric("Default stirrup", DEFAULT_SHEAR_STIRRUP_BAR, "Dropdown: DB10/DB12/DB16/DB20/DB25"),
        RebarMetric("Span basis", f"{span_m:.3f} m", "From Setup when available"),
        RebarMetric("Shear check", "Analysis ULS", "Active zones feed provided-stirrup φVn"),
        RebarMetric("Final use", "Provided layout", "Auto minimum will be a design aid only"),
    ]
    st.markdown(_strip_html(cards), unsafe_allow_html=True)

    _render_effective_shear_depth_settings()

    action_cols = st.columns([1.0, 1.0, 3.0], gap="small")
    with action_cols[0]:
        if st.button("Reset to DB12 zone template", use_container_width=True, key="shear_reinf_reset_template"):
            st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = _default_shear_reinforcement_table(span_m)
            st.session_state["beam_girder_shear_reinforcement_editor_revision"] += 1
            _store_shear_reinforcement_metadata(st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY])
            st.rerun()
    with action_cols[1]:
        if st.button("Activate all zones", use_container_width=True, key="shear_reinf_activate_all"):
            table = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY]))
            table["Active"] = True
            st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = table
            st.session_state["beam_girder_shear_reinforcement_editor_revision"] += 1
            _store_shear_reinforcement_metadata(table)
            st.rerun()
    with action_cols[2]:
        st.info(
            "Use Active only for reinforcement that is actually provided/accepted. "
            "Future shear analysis will read active zones as the provided stirrup layout; it will not silently assume minimum stirrups."
        )

    previous = st.session_state.get(SHEAR_REINFORCEMENT_TABLE_KEY)
    shear_editor_key = f"beam_girder_shear_reinforcement_editor_{st.session_state['beam_girder_shear_reinforcement_editor_revision']}"
    edited = st.data_editor(
        _ensure_shear_reinforcement_columns(pd.DataFrame(previous)),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=_shear_reinforcement_column_config(),
        key=shear_editor_key,
        on_change=_sync_beam_girder_shear_reinforcement_editor_to_table,
        args=(shear_editor_key, rebar_db),
    )
    edited = _data_editor_payload_to_dataframe(edited, pd.DataFrame(previous))
    normalized = _normalize_shear_reinforcement_table(edited, pd.DataFrame(previous), rebar_db)
    st.session_state[SHEAR_REINFORCEMENT_TABLE_KEY] = normalized
    _store_shear_reinforcement_metadata(normalized)

    preview_df, errors, warnings = _shear_reinforcement_preview_dataframe(normalized, rebar_db)
    st.session_state[SHEAR_REINFORCEMENT_VALID_KEY] = not errors and not warnings

    with st.expander("Shear reinforcement status", expanded=bool(errors or warnings)):
        active_rows = int(sum(_to_bool(value) for value in normalized.get("Active", []))) if not normalized.empty else 0
        cols = st.columns(4)
        cols[0].metric("Zones", f"{len(normalized):,}")
        cols[1].metric("Active zones", f"{active_rows:,}")
        cols[2].metric("Errors", f"{len(errors):,}")
        cols[3].metric("Default bar", DEFAULT_SHEAR_STIRRUP_BAR)
        for error in errors:
            st.error(error)
        for warning in warnings:
            st.warning(warning)
        if not errors and not warnings:
            st.success("Shear reinforcement layout is ready as provided-zone input for the future φVn engine.")

    st.markdown("##### Av/s provided preview")
    st.caption("Analysis ULS reads this table for SHEAR.CODE2 φVn, φVc, φVs, minimum Av/s, maximum spacing, and active-zone coverage gates.")
    if preview_df.empty:
        st.info("No shear reinforcement zones are defined yet.")
    else:
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

    with st.expander("Shear reinforcement workflow notes", expanded=False):
        st.write("- Provided stirrup layout is the source of truth for SHEAR.CODE2 φVn checks.")
        st.write("- DB12 is the default stirrup size; users can select DB10, DB12, DB16, DB20, or DB25 by zone.")
        st.write("- Auto required/minimum stirrup design should be a design assistant only; the final check must use the provided active layout.")
        st.write("- No shear strength formula is calculated in SHEAR.REINF1.")


def _render_column_pier_transverse_reinforcement_layout(rebar_db: pd.DataFrame) -> None:
    settings = _render_column_pier_transverse_settings()
    existing = st.session_state.get(COLUMN_PIER_TRANSVERSE_TABLE_KEY)
    if existing is None:
        existing = (st.session_state.get("project_metadata", {}) or {}).get(COLUMN_PIER_TRANSVERSE_TABLE_KEY)
    if isinstance(existing, list):
        st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = _ensure_shear_reinforcement_columns(pd.DataFrame(existing))
    elif COLUMN_PIER_TRANSVERSE_TABLE_KEY not in st.session_state:
        st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = _default_column_pier_transverse_reinforcement_table()
    st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY]))
    collapsed = _collapse_legacy_column_pier_transverse_template(st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY])
    if len(collapsed.index) != len(st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY].index):
        st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = collapsed
        _store_column_pier_transverse_metadata(collapsed)
    if "column_pier_transverse_reinforcement_editor_revision" not in st.session_state:
        st.session_state["column_pier_transverse_reinforcement_editor_revision"] = 0

    previous = st.session_state.get(COLUMN_PIER_TRANSVERSE_TABLE_KEY)
    preview_df, preview_errors, preview_warnings = _shear_reinforcement_preview_dataframe(
        pd.DataFrame(previous),
        rebar_db,
        allow_zero_length_reference=True,
    )
    active_rebars = list(st.session_state.get("rebars", []) or [])
    st.markdown(_strip_html(_column_pier_transverse_readiness_cards(pd.DataFrame(previous), settings, len(active_rebars), preview_errors)), unsafe_allow_html=True)
    st.info(
        "Longitudinal torsion reinforcement will be read from active ordinary rebar only. Prestress strands, tendons, and PT bars are not counted as Al in this guarded column/pier workflow."
    )
    _render_column_pier_seismic_spacing_advisor(settings, pd.DataFrame(previous), rebar_db)

    action_cols = st.columns([1.0, 1.0, 3.0], gap="small")
    with action_cols[0]:
        if st.button("Reset control section", use_container_width=True, key="column_pier_transverse_reset_template"):
            table = _default_column_pier_transverse_reinforcement_table()
            st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = table
            st.session_state["column_pier_transverse_reinforcement_editor_revision"] += 1
            _store_column_pier_transverse_metadata(table)
            st.rerun()
    with action_cols[1]:
        if st.button("Use control section", use_container_width=True, key="column_pier_transverse_activate_all"):
            table = _ensure_shear_reinforcement_columns(pd.DataFrame(st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY]))
            table["Active"] = True
            st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = table
            st.session_state["column_pier_transverse_reinforcement_editor_revision"] += 1
            _store_column_pier_transverse_metadata(table)
            st.rerun()
    with action_cols[2]:
        st.info(
            "Use the control section only for transverse reinforcement that is actually provided/accepted. Current column/pier shear and torsion previews use this single row; no minimum ties are silently assumed."
        )

    editor_key = f"column_pier_transverse_reinforcement_editor_{st.session_state['column_pier_transverse_reinforcement_editor_revision']}"
    edited = st.data_editor(
        _ensure_shear_reinforcement_columns(pd.DataFrame(previous)),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config=_column_pier_transverse_column_config(),
        key=editor_key,
        on_change=_sync_column_pier_transverse_reinforcement_editor_to_table,
        args=(editor_key, rebar_db),
    )
    edited = _data_editor_payload_to_dataframe(edited, pd.DataFrame(previous))
    normalized = _normalize_shear_reinforcement_table(edited, pd.DataFrame(previous), rebar_db)
    st.session_state[COLUMN_PIER_TRANSVERSE_TABLE_KEY] = normalized
    _store_column_pier_transverse_metadata(normalized)

    preview_df, errors, warnings = _shear_reinforcement_preview_dataframe(
        normalized,
        rebar_db,
        allow_zero_length_reference=True,
    )
    if settings.get("closed_tie_layout") == "Open ties - shear only review":
        warnings.append("Open ties are not accepted as torsion transverse reinforcement; torsion must remain REVIEW until closed ties/hoops or spiral reinforcement are defined.")
    if settings.get("torsion_core_basis") == "Manual core dimensions" and not (settings.get("manual_core_width_mm") and settings.get("manual_core_depth_mm")):
        warnings.append("Manual torsion core basis is selected, but bo/ho are not both defined.")
    st.session_state[COLUMN_PIER_TRANSVERSE_VALID_KEY] = not errors

    with st.expander("Column/Pier control-section transverse reinforcement status", expanded=bool(errors or warnings)):
        active_rows = int(sum(_to_bool(value) for value in normalized.get("Active", []))) if not normalized.empty else 0
        cols = st.columns(5)
        cols[0].metric("Control rows", f"{len(normalized):,}")
        cols[1].metric("Active control rows", f"{active_rows:,}")
        cols[2].metric("Errors", f"{len(errors):,}")
        cols[3].metric("Warnings", f"{len(warnings):,}")
        cols[4].metric("Default tie", DEFAULT_SHEAR_STIRRUP_BAR)
        for error in errors:
            st.error(error)
        for warning in warnings:
            st.warning(warning)
        if not errors and not warnings:
            st.success("Column/Pier control-section transverse reinforcement input is ready for the current shear/torsion preview milestones.")

    st.markdown("##### Control-section transverse reinforcement preview")
    st.caption("Row 1 is the provided Control section used by shear/torsion analysis. Any seismic advisor row is display-only until applied to Row 1.")
    display_preview_df = _column_pier_transverse_preview_with_seismic_advisor(preview_df, settings, normalized, rebar_db)
    if display_preview_df.empty:
        st.info("No transverse reinforcement control section is defined yet.")
    else:
        st.dataframe(display_preview_df, use_container_width=True, hide_index=True)
        if str(settings.get("seismic_detailing") or "") == "ACI 318 special seismic confinement advisor":
            st.warning("Seismic advisor row is not used by Analysis. Shear and torsion calculations use the Control section row only unless the suggested spacing is applied to Row 1.")

    with st.expander("Column/Pier shear and torsion workflow notes", expanded=False):
        st.write("- Current Column/Pier shear and torsion previews use the active control-section row as the provided transverse reinforcement source.")
        st.write("- Future station/height-specific confinement or end-region checks should be added as a named milestone, not inferred from this single row.")
        st.write("- Torsion requires closed ties/hoops or spiral reinforcement plus a defined torsion core basis before any future capacity result can be accepted.")
        st.write("- Longitudinal torsion Al comes from active ordinary rebar rows. Prestress strands, tendons, and PT bars are not counted as Al in this milestone.")
        st.write("- This UI milestone records and validates input ownership only; it does not certify ACI 318 or AASHTO LRFD shear/torsion capacity.")

def _render_longitudinal_rebar_tab(
    rebar_db: pd.DataFrame,
    bar_size_options: list[str],
    active_material_name: str | None,
    member_type: str,
) -> None:
    """Render ordinary longitudinal reinforcement inputs and preview.

    This tab owns the existing ordinary Rebar table.  Beam/Girder torsion Al
    review intentionally reads this same table so users do not maintain a
    duplicate longitudinal-torsion table that can drift away from the actual
    section reinforcement.
    """

    if member_type == COLUMN_PIER_WORKFLOW_MEMBER_TYPE:
        st.caption(
            "Ordinary longitudinal reinforcement used by Column/Pier PMM and future shear/torsion checks. "
            "Active ordinary bars are the future longitudinal torsion Al source; prestress strands, tendons, and PT bars are not counted as Al in this guarded workflow."
        )
    else:
        st.caption(
            "Ordinary longitudinal reinforcement used by PMM / SLS / flexure checks. "
            "For Beam/Girder torsion, active ordinary bars are also the review-only Al source; do not duplicate Al in a separate table."
        )
    ordinary_rebar_system_enabled = reconcile_ordinary_rebar_system_flag_for_rebar_page(st.session_state, default=True)
    # Legacy UI.COMPACT1 source marker retained after Section Builder sync hotfix:
    # if not ordinary_rebar_enabled(st.session_state, default=True):
    if not ordinary_rebar_system_enabled:
        table = st.session_state.get("rebar_table")
        stored_df = _ensure_rebar_table_columns(pd.DataFrame(table)) if table is not None else pd.DataFrame(columns=REBAR_TABLE_COLUMNS)
        result = rebars_from_dataframe(stored_df, rebar_db) if table is not None else RebarParseResult([], [], [], [])
        # Keep the editable table, but publish no active analysis rebars while
        # the section-level ordinary-rebar system is disabled.  This prevents
        # Project/Analysis/other pages from presenting stored rows as active
        # reinforcement if the Rebar page is visited before Section Builder is
        # rendered on the same rerun.
        st.session_state["rebars_stored_excluded"] = result.rebars
        st.session_state["rebars"] = []
        st.session_state["rebars_valid_for_analysis"] = False

        input_col, review_col = st.columns([1.22, 1.0], gap="large")
        with input_col:
            with st.container(border=True):
                st.markdown(
                    '<div class="cpmm-rebar-panel-title">Stored Longitudinal Rebar</div>'
                    '<div class="cpmm-rebar-panel-subtitle">Ordinary rebar is disabled in Section Builder. Stored Rebar table data is preserved for later use, but ordinary rebar and torsion Al are excluded from analysis until you enable it again.</div>',
                    unsafe_allow_html=True,
                )
                _render_enable_ordinary_rebar_action()
                st.markdown(
                    _strip_html(
                        [
                            RebarMetric("Stored Bars", f"{len(result.rebars):,}", "Preserved table rows"),
                            RebarMetric("Stored As", f"{_total_as_mm2(result.rebars):,.1f} mm^2"),
                            RebarMetric("Analysis Participation", "Excluded", "Disabled in Section Builder", "warning", True),
                            RebarMetric("Active Analysis Bars", "0", "Ordinary rebar ignored"),
                            RebarMetric("Active Analysis As", "0.0 mm^2"),
                            RebarMetric("Material", _dominant_material_label(result.rebars, active_material_name)),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                with st.expander("Stored Rebar table preview", expanded=False):
                    if table is None or stored_df.empty:
                        st.caption("No stored Rebar table is available yet.")
                    else:
                        st.caption("Stored rows are shown for review only. They are not included in PMM/SLS/shear/torsion assembly while ordinary rebar is disabled.")
                        st.dataframe(stored_df, use_container_width=True, hide_index=True)

        with review_col:
            with st.container(border=True):
                st.markdown(
                    '<div class="cpmm-rebar-panel-title">Analysis Participation</div>'
                    '<div class="cpmm-rebar-panel-subtitle">Stored but excluded from analysis. Active ordinary rebar is intentionally published as zero.</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _kv_panel_html(
                        [
                            ("Ordinary rebar system", "Disabled"),
                            ("Stored rows", f"{len(result.rebars):,}"),
                            ("Active analysis bars", "0"),
                            ("Active analysis As", "0.0 mm^2"),
                            ("Analysis state", "Preview only — excluded from analysis"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
            geometry = st.session_state.get("section_geometry")
            if geometry is not None and result.rebars:
                with st.container(border=True):
                    st.markdown(
                        '<div class="cpmm-rebar-preview-title">Stored Rebar Preview — Excluded from Analysis</div>'
                        '<div class="cpmm-rebar-preview-caption">Preview only — these stored bars are excluded from analysis. Dimension guides are intentionally hidden on the Rebar page; use Section Builder for section dimensions.</div>',
                        unsafe_allow_html=True,
                    )
                    preview_fig = create_section_preview(
                        geometry,
                        [],
                        "symbol_value",
                        result.rebars,
                        [],
                    )
                    preview_fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(
                        preview_fig,
                        use_container_width=True,
                        key="rebar_stored_excluded_section_preview",
                    )
        return

    if "rebar_table" not in st.session_state:
        st.session_state["rebar_table"] = _default_rebar_table(rebar_db)
    st.session_state["rebar_table"] = _ensure_rebar_table_columns(st.session_state["rebar_table"])
    if "rebar_editor_revision" not in st.session_state:
        st.session_state["rebar_editor_revision"] = 0

    input_mode = DEFAULT_REBAR_INPUT_MODE
    edited_df = st.session_state["rebar_table"]

    input_col, status_col = st.columns([1.28, 1.0], gap="large")
    summary_slot = None
    with input_col:
        with st.container(border=True):
            st.markdown(
                '<div class="cpmm-rebar-panel-title">Longitudinal Rebar Input</div>'
                '<div class="cpmm-rebar-panel-subtitle">Single source of truth for ordinary longitudinal bars used by PMM/SLS/flexure and review-only torsion Al workflows.</div>',
                unsafe_allow_html=True,
            )
            # Keep the summary visually above the editor. The placeholder is
            # filled after data_editor returns so the metrics still use the
            # normalized table from the current rerun instead of stale pre-edit
            # values.
            summary_slot = st.empty()
            apply_status = st.session_state.pop("rebar_apply_status", None)
            if apply_status:
                st.success(str(apply_status))
            if st.session_state.get("rebar_input_mode") not in REBAR_INPUT_MODE_OPTIONS:
                st.session_state["rebar_input_mode"] = DEFAULT_REBAR_INPUT_MODE
            input_mode = st.selectbox(
                "Rebar input mode",
                REBAR_INPUT_MODE_OPTIONS,
                index=REBAR_INPUT_MODE_OPTIONS.index(DEFAULT_REBAR_INPUT_MODE),
                key="rebar_input_mode",
            )
            st.markdown(
                '<div class="cpmm-rebar-note">Selecting a database bar size fills Diameter and enforces the standard material/fy rule: DB10–DB28 = SD40, DB32 = SD50. Use Custom bar size for project-specific overrides.</div>',
                unsafe_allow_html=True,
            )
            if input_mode == REBAR_INPUT_MODE_AUTO_PERIMETER:
                _render_auto_perimeter_controls(rebar_db, st.session_state.get("section_geometry"))

            # The editable table is always shown. Auto perimeter layout is a
            # preview/apply workflow, so the main table remains the single
            # source of truth for PMM/SLS/torsion-Al review after generated bars
            # are applied.
            editor_key = f"rebar_data_editor_{st.session_state['rebar_editor_revision']}"
            edited_df = _render_rebar_editor(st.session_state["rebar_table"], bar_size_options, editor_key)

    previous_table = st.session_state.get("rebar_table")
    normalized_df = normalize_rebar_table_for_bar_size_sync(edited_df, previous_table, rebar_db)

    if not rebar_editor_tables_equal(normalized_df, edited_df):
        # A database Bar Size edit changed dependent cells such as Diameter_mm
        # or Material. Updating only the backing dataframe after the widget has
        # rendered leaves the visible data_editor one rerun behind. Bump the
        # editor key and rerun once so the user sees DB25→25/SD40 or
        # DB32→32/SD50 immediately, while manual overrides remain stable when
        # Bar Size is unchanged.
        st.session_state["rebar_table"] = normalized_df
        st.session_state["rebar_editor_revision"] += 1
        st.rerun()

    st.session_state["rebar_table"] = normalized_df

    result = rebars_from_dataframe(normalized_df, rebar_db)
    geometry = st.session_state.get("section_geometry")
    geometry_errors = validate_rebars_against_geometry(result.rebars, geometry)
    valid_for_analysis = rebars_valid_for_analysis(result, geometry_errors)
    st.session_state["rebars"] = result.rebars
    st.session_state["rebars_valid_for_analysis"] = valid_for_analysis

    if summary_slot is not None:
        with summary_slot:
            _render_summary_strip(result, geometry, input_mode, valid_for_analysis, active_material_name)

    with status_col:
        with st.container(border=True):
            _render_validation(
                result,
                geometry_errors,
                geometry is not None,
                valid_for_analysis,
                active_prestress_count=(len(st.session_state.get("prestress_elements", []) or []) if prestressing_steel_enabled(st.session_state, default=True) else 0),
            )
            st.markdown(
                '<div class="cpmm-rebar-note">Coordinates are in mm. x is positive to the right; y is positive upward in the section preview.</div>',
                unsafe_allow_html=True,
            )

        if geometry is not None:
            with st.container(border=True):
                st.markdown(
                    '<div class="cpmm-rebar-preview-title">Section Preview with Rebar — Longitudinal</div>'
                    '<div class="cpmm-rebar-preview-caption">Default preview shows ordinary rebar only. Dimension guides are intentionally hidden here; use Section Builder for section dimensions.</div>',
                    unsafe_allow_html=True,
                )
                preview_fig = create_section_preview(
                    geometry,
                    [],
                    "symbol_value",
                    st.session_state["rebars"],
                    [],
                )
                preview_fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(
                    preview_fig,
                    use_container_width=True,
                    key="rebar_section_preview",
                )
            if prestressing_steel_enabled(st.session_state, default=True):
                prestress_elements = list(st.session_state.get("prestress_elements", []) or [])
                if prestress_elements:
                    with st.expander("Combined Reinforcement Preview", expanded=False):
                        st.caption(
                            "Coordination view only: ordinary rebar and prestressing steel are shown together. "
                            "Default page previews remain separated to avoid mixing rebar and prestress workflows."
                        )
                        combined_fig = create_section_preview(
                            geometry,
                            [],
                            "symbol_value",
                            st.session_state["rebars"],
                            prestress_elements,
                        )
                        combined_fig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10))
                        st.plotly_chart(
                            combined_fig,
                            use_container_width=True,
                            key="rebar_combined_reinforcement_preview",
                        )

    with st.expander("Longitudinal Rebar Summary", expanded=False):
        st.dataframe(rebar_summary_dataframe(st.session_state["rebars"]), use_container_width=True, hide_index=True)

    with st.expander("Longitudinal rebar / torsion Al workflow notes", expanded=False):
        st.write("- This ordinary Rebar table remains the single source of truth for longitudinal bars in PMM/SLS/flexure analysis.")
        if member_type == COLUMN_PIER_WORKFLOW_MEMBER_TYPE:
            st.write("- Column/Pier torsion will read active ordinary rebar from this same table as the longitudinal Al source.")
            st.write("- Prestress strands, tendons, and PT bars are not counted as longitudinal torsion Al in this milestone.")
        else:
            st.write("- Beam/Girder torsion reads active ordinary bars from this same table as the review-only Al provided source.")
        st.write("- Do not count flexural bars as torsion perimeter Al unless they are intentionally detailed around the closed-hoop perimeter.")


def _render_beam_girder_transverse_rebar_tab(rebar_db: pd.DataFrame) -> None:
    """Render Beam/Girder transverse reinforcement and effective d/dv inputs."""

    st.caption(
        "Transverse reinforcement and effective shear-depth inputs used by Analysis → ULS Shear and Torsion. "
        "Active stirrup zones are the provided layout for SHEAR.CODE2 φVn and the closed-hoop source for TORSION.CODE2 φTn."
    )
    _render_shear_reinforcement_layout(rebar_db)


def _render_transverse_rebar_tab(rebar_db: pd.DataFrame) -> None:
    """Render workflow-aware transverse reinforcement inputs."""

    if _is_column_pier_workflow():
        st.caption(
            "Transverse reinforcement for Column/Pier/Wall/Pylon shear, torsion, and confinement workflow. "
            "The current shear/torsion previews use one active control-section row; future checks must not count prestress as longitudinal torsion Al."
        )
        _render_column_pier_transverse_reinforcement_layout(rebar_db)
    else:
        st.caption(
            "Transverse reinforcement and effective shear-depth inputs used by Analysis -> ULS Shear and Torsion. "
            "Active stirrup zones are the provided layout for SHEAR.CODE2 phi Vn and the closed-hoop source for TORSION.CODE2 phi Tn."
        )
        _render_beam_girder_transverse_rebar_tab(rebar_db)


def render_rebar_page() -> None:
    st.markdown(_REBAR_PAGE_CSS, unsafe_allow_html=True)
    rebar_db = load_rebar_database()
    bar_size_options = ["", "Custom"] + [str(name) for name in rebar_db["name"].tolist()]
    active_material_name = st.session_state.get("active_rebar_material_name")
    member_type = _analysis_mode_member_type_from_session()

    render_page_header(
        "Rebar",
        "Define longitudinal bars, transverse reinforcement, torsion Al sources, and confinement inputs without duplicating analysis ownership.",
        icon="RB",
        kicker="Reinforcement workspace",
        badge="Steel input",
        accent="green",
    )
    render_metric_cards(_commercial_rebar_dashboard_cards(member_type))
    render_section_bar("Reinforcement input tabs", "Longitudinal and transverse reinforcement are separated for traceable PMM, shear, torsion, and confinement checks.", mark="R")

    longitudinal_tab, transverse_tab = st.tabs(["Longitudinal Rebar", "Transverse Rebar"])
    with longitudinal_tab:
        _render_longitudinal_rebar_tab(rebar_db, bar_size_options, active_material_name, member_type)
    with transverse_tab:
        _render_transverse_rebar_tab(rebar_db)

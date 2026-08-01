"""Navigation helpers for Concrete Section Pro UI.

These helpers render existing app navigation choices with deterministic active
state styling.  They intentionally do not change the available navigation
options or execute inactive workspaces.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from html import escape
import re
from typing import Any

import streamlit as st

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.analysis_modes import is_pmm_primary_workflow


ANALYSIS_SUBPAGES = ("ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber")
ANALYSIS_COLUMN_PIER_SUBPAGES = ("ULS Strength",)

_WORKFLOW_MEMBER_TYPES = {
    "column_pier_pmm",
    "beam_girder",
    "building_beam_girder",
    "portal_frame_crossbeam",
}
_WORKFLOW_LABEL_MEMBER_TYPES = {
    "Column / Pier / Wall / Pylon — RC / Prestressed Member": "column_pier_pmm",
    "Bridge Beam / Girder — RC / Prestressed Member": "beam_girder",
    "Building Beam / Girder — RC / Prestressed Member": "building_beam_girder",
    "Portal Frame Crossbeam — Prestressed Concrete": "portal_frame_crossbeam",
    # Legacy labels remain recovery-only so an interrupted rerun cannot erase
    # an otherwise unambiguous workflow selection.
    "Column / Pier / Wall / Pylon - PMM Mode": "column_pier_pmm",
    "Beam / Girder - Future Design Workflow": "beam_girder",
    "Beam / Girder - Flexure Mode Future": "beam_girder",
}


def _coerce_analysis_mode_settings(value: Any) -> AnalysisModeSettings | None:
    """Coerce the canonical object/dict workflow state without guessing."""

    if isinstance(value, AnalysisModeSettings):
        return value
    if isinstance(value, Mapping):
        try:
            return AnalysisModeSettings.model_validate(dict(value))
        except Exception:
            return None
    return None


def resolve_analysis_mode_settings(session_state: Mapping[str, Any]) -> AnalysisModeSettings:
    """Resolve workflow before any workflow-scoped navigation is validated.

    ``analysis_mode_settings`` is authoritative whenever it is valid.  The
    Project selector's synchronized member type/label is used only as a recovery
    source when that canonical value is temporarily absent or invalid during a
    Streamlit rerun.  Recovery is written back when the state is mutable so the
    remainder of the same rerun sees one stable workflow.
    """

    canonical = _coerce_analysis_mode_settings(session_state.get("analysis_mode_settings"))
    if canonical is not None:
        return canonical

    member_type = str(session_state.get("project_analysis_mode_member_type_sync") or "")
    if member_type not in _WORKFLOW_MEMBER_TYPES:
        label = str(session_state.get("project_analysis_mode_member_type_label") or "")
        member_type = _WORKFLOW_LABEL_MEMBER_TYPES.get(label, "column_pier_pmm")

    recovered = AnalysisModeSettings(member_type=member_type)
    if isinstance(session_state, MutableMapping):
        session_state["analysis_mode_settings"] = recovered
        session_state["project_analysis_mode_member_type_sync"] = recovered.member_type
    return recovered


def analysis_subpages_for_workflow(settings: AnalysisModeSettings) -> list[str]:
    """Return the single canonical Analysis subpage list for one workflow."""

    if is_pmm_primary_workflow(settings):
        return list(ANALYSIS_COLUMN_PIER_SUBPAGES)
    return list(ANALYSIS_SUBPAGES)


def analysis_subpages_for_session(session_state: Mapping[str, Any]) -> list[str]:
    """Resolve the active workflow, then return its allowed Analysis pages."""

    return analysis_subpages_for_workflow(resolve_analysis_mode_settings(session_state))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return slug or "option"


def render_active_choice(label: str, options: list[str], *, key: str, horizontal: bool = True) -> str:
    """Render a deterministic tab-like navigation choice.

    Streamlit segmented controls have version-dependent selected-state DOM.
    This renderer uses the app's own ``session_state`` value to draw the active
    option as a styled pill, while inactive options remain real buttons.  The
    result is predictable active-tab highlighting without relying on fragile CSS
    selectors for Streamlit internals.  The visual tab cluster is kept compact
    and left-aligned so it reads as navigation instead of full-width action
    buttons.
    """

    if not options:
        raise ValueError("Navigation options must not be empty.")

    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    active = str(st.session_state.get(key, options[0]))

    st.markdown(f'<div class="cpmm-nav-label">{escape(label)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="cpmm-deterministic-nav-row cpmm-deterministic-nav-row--compact">', unsafe_allow_html=True)

    if horizontal:
        # UI.ACTIVE.TABS2: keep the existing navigation location/choices, but
        # stop stretching each tab across the full viewport.  The trailing
        # spacer column leaves the tab cluster compact and left-aligned like a
        # commercial desktop tab bar, while each tab remains a real Streamlit
        # button for stable state handling.
        # UI.COMMERCIAL4.1: keep the deterministic nav compact, but do not
        # make each column so narrow that labels wrap into broken words on
        # wide dashboard layouts.  Each tab receives enough width for its
        # visible label, then the remaining width is assigned to a trailing
        # spacer so the cluster stays left-aligned.
        tab_widths = [max(1.28, min(1.78, 0.84 + len(option) / 16.0)) for option in options]
        trailing_spacer = max(3.8, 10.0 - sum(tab_widths))
        columns = st.columns([*tab_widths, trailing_spacer], gap="small")[: len(options)]
    else:
        columns = [st.container() for _ in options]

    for index, option in enumerate(options):
        option_text = str(option)
        widget_key = f"{key}__nav_button__{_slug(option_text)}"
        with columns[index]:
            if option_text == active:
                st.markdown(
                    f'<div class="cpmm-nav-tab-pill cpmm-nav-tab-active" aria-current="page">{escape(option_text)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                clicked = st.button(
                    option_text,
                    key=widget_key,
                    use_container_width=True,
                    help=f"Go to {option_text}",
                )
                if clicked:
                    st.session_state[key] = option_text
                    rerun = getattr(st, "rerun", None)
                    if callable(rerun):
                        rerun()
                    return option_text

    st.markdown('</div>', unsafe_allow_html=True)
    return active

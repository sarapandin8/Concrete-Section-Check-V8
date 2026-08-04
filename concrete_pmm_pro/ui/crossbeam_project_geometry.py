"""Decision-first Project-JSON geometry notice for Crossbeam workflows."""

from __future__ import annotations

from collections.abc import MutableMapping
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from concrete_pmm_pro.crossbeam.project_geometry import (
    CROSSBEAM_PROJECT_GEOMETRY_AUDIT_KEY,
    CROSSBEAM_SEGMENT_ROWS_KEY,
    crossbeam_project_geometry_audit,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    reset_crossbeam_rebar_zones_from_segment_layout,
)
from concrete_pmm_pro.state.dirty_state import ANALYSIS_STATUS_KEY, REPORT_STATUS_KEY


_RESET_SUCCESS_KEY = "crossbeam_project_json1_reset_success"


def render_crossbeam_project_geometry_notice(
    session_state: MutableMapping[str, Any],
    *,
    key_prefix: str,
) -> None:
    """Render exact restored-coordinate blockers and the guarded Rebar reset."""

    mode = session_state.get("analysis_mode_settings")
    member_type = (
        mode.get("member_type")
        if isinstance(mode, dict)
        else getattr(mode, "member_type", None)
    )
    if str(member_type or "") != "portal_frame_crossbeam":
        return

    audit = crossbeam_project_geometry_audit(session_state)
    session_state[CROSSBEAM_PROJECT_GEOMETRY_AUDIT_KEY] = audit
    success = session_state.pop(_RESET_SUCCESS_KEY, None)
    if success:
        st.success(str(success))
    if audit.get("status") != "INCONSISTENT":
        return

    issues = list(audit.get("issues") or [])
    rebar_issue = next(
        (issue for issue in issues if issue.get("Component") == "Rebar Zones"),
        None,
    )
    issue_detail = (
        str(rebar_issue.get("Detail") or "Rebar Zone geometry requires review.")
        if rebar_issue
        else "Review the listed project-coordinate inconsistencies before analysis."
    )
    where_to_fix = str(
        (rebar_issue or {}).get("Where to fix")
        or next((issue.get("Where to fix") for issue in issues if issue.get("Where to fix")), "Project inputs")
    )
    rebar = dict(audit.get("rebar") or {})
    if rebar_issue and bool(rebar.get("reset_supported")):
        action_text = "Use the reset button below, or review " + where_to_fix + "."
    elif rebar_issue:
        action_text = (
            "Open " + where_to_fix
            + ". Custom subdivisions are preserved and will not be replaced automatically."
        )
    else:
        action_text = "Review " + where_to_fix + " before analysis."

    if str(key_prefix).startswith("sidebar_"):
        st.markdown(
            (
                '<div class="cpmm-sidebar-blocked-notice" role="alert">'
                '<div class="cpmm-sidebar-blocked-title">PROJECT GEOMETRY INCONSISTENT — BLOCKED</div>'
                f'<div class="cpmm-sidebar-blocked-detail">{escape(issue_detail)}</div>'
                '<div class="cpmm-sidebar-blocked-action">'
                '<span class="cpmm-sidebar-blocked-action-label">ACTION</span>'
                f'{escape(action_text)}'
                "</div></div>"
            ),
            unsafe_allow_html=True,
        )
    else:
        st.error("PROJECT GEOMETRY INCONSISTENT — BLOCKED")
        st.markdown(f"**Reason:** {issue_detail}")
        st.warning(f"Action: {action_text}")

    if rebar_issue and bool(rebar.get("reset_supported")):
        if st.button(
            "Reset Rebar Zones from Segment Layout",
            key=f"{key_prefix}_reset_rebar_zones",
            use_container_width=True,
            type="primary",
        ):
            reset_crossbeam_rebar_zones_from_segment_layout(
                session_state,
                list(session_state.get(CROSSBEAM_SEGMENT_ROWS_KEY) or []),
            )
            session_state[ANALYSIS_STATUS_KEY] = "Out of date"
            session_state[REPORT_STATUS_KEY] = "Out of date"
            session_state[_RESET_SUCCESS_KEY] = (
                "PROJECT GEOMETRY CONSISTENT — READY. Rebar Zones were rebuilt "
                "from the saved Segment Layout; stored dependent results are STALE."
            )
            rerun = getattr(st, "rerun", None)
            if callable(rerun):
                rerun()
    elif rebar_issue and not str(key_prefix).startswith("sidebar_"):
        st.caption(
            "Custom Rebar subdivisions are preserved. Review the active assignment "
            "boundaries before analysis; the app will not replace them automatically."
        )

    if len(issues) > (1 if rebar_issue else 0):
        with st.expander("Other geometry checks", expanded=False):
            st.dataframe(
                pd.DataFrame(issues)[
                    ["Component", "Status", "Detail", "Where to fix"]
                ],
                use_container_width=True,
                hide_index=True,
            )

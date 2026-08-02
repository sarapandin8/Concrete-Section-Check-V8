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
    if str(key_prefix).startswith("sidebar_"):
        st.markdown(
            (
                '<div class="cpmm-sidebar-blocked-notice">'
                "PROJECT GEOMETRY INCONSISTENT — BLOCKED"
                f"<br>{escape(issue_detail)}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    else:
        st.error("PROJECT GEOMETRY INCONSISTENT — BLOCKED")
        if rebar_issue:
            st.caption(issue_detail)

    rebar = dict(audit.get("rebar") or {})
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
    elif rebar_issue:
        st.caption(
            "Custom Rebar subdivisions were detected. Open Sections → Rebar → "
            "Segment / Zone to review them; the app will not replace them automatically."
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

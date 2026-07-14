"""Project design-code source-of-truth helpers.

CODE.SETUP1 centralizes the design-code names used by the UI/project model.
It intentionally does not implement new ACI/AASHTO solver formulas.  Workflow
pages use these helpers to display capability status and to select existing
preview profiles without pretending that planned code-specific engines already
exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

PROJECT_CODE_ACI318 = "ACI 318"
PROJECT_CODE_AASHTO_LRFD = "AASHTO LRFD"
DEFAULT_PROJECT_DESIGN_CODE = PROJECT_CODE_ACI318
PROJECT_DESIGN_CODE_OPTIONS: tuple[str, ...] = (PROJECT_CODE_ACI318, PROJECT_CODE_AASHTO_LRFD)
PROJECT_DESIGN_CODE_STATE_KEY = "project_design_code"
PROJECT_CODE_EDITION_STATE_KEY = "project_code_edition"
LEGACY_DESIGN_CODE_WIDGET_KEY = "design_code"
LEGACY_CODE_EDITION_WIDGET_KEY = "code_edition"

DEFAULT_CODE_EDITION_BY_CODE: dict[str, str] = {
    PROJECT_CODE_ACI318: "ACI 318-19",
    PROJECT_CODE_AASHTO_LRFD: "AASHTO LRFD 9th Edition",
}
CODE_EDITION_OPTIONS_BY_CODE: dict[str, tuple[str, ...]] = {
    PROJECT_CODE_ACI318: ("ACI 318-19", "ACI 318-14", "Project-specified ACI 318 edition"),
    PROJECT_CODE_AASHTO_LRFD: (
        "AASHTO LRFD 9th Edition",
        "AASHTO LRFD 8th Edition",
        "Project-specified AASHTO LRFD edition",
    ),
}

GirderSLSProfileCode = Literal["AASHTO LRFD Bridge", "ACI 318"]


def normalize_project_design_code(value: object | None) -> str:
    """Return the canonical project design-code name used by Setup.

    Legacy UI labels are accepted so older project JSON and session state load
    safely.  Unknown labels fall back to ACI 318 rather than creating a third
    unsupported code path silently.
    """

    text = str(value or "").strip()
    compact = text.casefold().replace("-", " ").replace("_", " ")
    if not compact:
        return DEFAULT_PROJECT_DESIGN_CODE
    if "aashto" in compact or "lrfd" in compact or "bridge" in compact:
        return PROJECT_CODE_AASHTO_LRFD
    if "aci" in compact or "318" in compact:
        return PROJECT_CODE_ACI318
    return DEFAULT_PROJECT_DESIGN_CODE




def allowed_project_design_codes_for_workflow(member_type: object | None) -> tuple[str, ...]:
    """Return design-code options allowed by the active member workflow.

    WORKFLOW.TYPE2 makes code selection workflow-aware:
    Bridge Beam/Girder uses AASHTO LRFD only; Building Beam/Girder uses
    ACI 318 only; Column/Pier/Wall/Pylon can choose either code.
    """

    member = str(member_type or "column_pier_pmm")
    if member == "beam_girder":
        return (PROJECT_CODE_AASHTO_LRFD,)
    if member == "building_beam_girder":
        return (PROJECT_CODE_ACI318,)
    if member == "portal_frame_crossbeam":
        return (PROJECT_CODE_ACI318,)
    return PROJECT_DESIGN_CODE_OPTIONS


def default_project_design_code_for_workflow(member_type: object | None, current_code: object | None = None) -> str:
    """Return the workflow-compatible project design code.

    If ``current_code`` is allowed for the selected workflow it is preserved;
    otherwise the workflow's required/default code is returned.
    """

    allowed = allowed_project_design_codes_for_workflow(member_type)
    canonical = normalize_project_design_code(current_code)
    if canonical in allowed:
        return canonical
    return allowed[0]


def workflow_code_policy_message(member_type: object | None) -> str:
    member = str(member_type or "column_pier_pmm")
    if member == "beam_girder":
        return "Bridge Beam/Girder workflow uses AASHTO LRFD design basis only."
    if member == "building_beam_girder":
        return "Building Beam/Girder workflow uses ACI 318 design basis only."
    if member == "portal_frame_crossbeam":
        return "Portal Frame Crossbeam workflow uses ACI 318 design basis; prestress-loss basis is selected separately in future loss modules."
    return "Column / Pier / Wall / Pylon workflow may use ACI 318 or AASHTO LRFD, with capability guards where engines are not yet implemented."


def code_edition_options_for(code: object | None) -> tuple[str, ...]:
    canonical = normalize_project_design_code(code)
    return CODE_EDITION_OPTIONS_BY_CODE.get(canonical, CODE_EDITION_OPTIONS_BY_CODE[DEFAULT_PROJECT_DESIGN_CODE])


def default_code_edition_for(code: object | None) -> str:
    canonical = normalize_project_design_code(code)
    return DEFAULT_CODE_EDITION_BY_CODE.get(canonical, DEFAULT_CODE_EDITION_BY_CODE[DEFAULT_PROJECT_DESIGN_CODE])


def normalize_project_code_edition(code: object | None, edition: object | None) -> str:
    """Return a valid edition label for the canonical project code."""

    options = code_edition_options_for(code)
    text = str(edition or "").strip()
    if text in options:
        return text
    return default_code_edition_for(code)


def _state_getter(session_state: Mapping[str, Any] | Any):
    return session_state.get if hasattr(session_state, "get") else lambda key, default=None: getattr(session_state, key, default)


def _state_setter(session_state: Any):
    if hasattr(session_state, "__setitem__"):
        return lambda key, value: session_state.__setitem__(key, value)
    return lambda key, value: setattr(session_state, key, value)


def project_design_code_from_session(session_state: Mapping[str, Any] | Any) -> str:
    """Return the durable project design-code source of truth.

    Streamlit removes widget-owned keys when their widget is not rendered on the
    active workspace.  The Setup selector therefore mirrors its value into
    ``project_design_code``.  Analysis, Report, Prestress, save/load, and chrome
    must read the durable key first instead of falling back to the Setup-only
    selectbox key and accidentally returning ACI 318 after navigating away from
    Setup.
    """

    getter = _state_getter(session_state)
    return normalize_project_design_code(
        getter(
            PROJECT_DESIGN_CODE_STATE_KEY,
            getter(LEGACY_DESIGN_CODE_WIDGET_KEY, getter("code", DEFAULT_PROJECT_DESIGN_CODE)),
        )
    )


def project_code_edition_from_session(session_state: Mapping[str, Any] | Any) -> str:
    getter = _state_getter(session_state)
    code = project_design_code_from_session(session_state)
    return normalize_project_code_edition(
        code,
        getter(PROJECT_CODE_EDITION_STATE_KEY, getter(LEGACY_CODE_EDITION_WIDGET_KEY, getter("design_code_edition", None))),
    )


def sync_project_design_code_to_session(
    session_state: Any,
    *,
    member_type: object | None = None,
    selected_code: object | None = None,
    selected_edition: object | None = None,
    sync_legacy_widget_keys: bool = True,
) -> tuple[str, str]:
    """Persist the workflow-compatible project code outside Setup widgets.

    ``design_code`` and ``code_edition`` remain as legacy/widget keys for the
    Setup selectboxes and old project files.  ``project_design_code`` and
    ``project_code_edition`` are the durable keys that survive when Setup is not
    rendered.
    """

    getter = _state_getter(session_state)
    setter = _state_setter(session_state)
    workflow_member = member_type if member_type is not None else workflow_member_type_from_session(session_state)
    raw_code = selected_code if selected_code is not None else project_design_code_from_session(session_state)
    code = default_project_design_code_for_workflow(workflow_member, raw_code)
    raw_edition = selected_edition if selected_edition is not None else project_code_edition_from_session(session_state)
    edition = normalize_project_code_edition(code, raw_edition)
    setter(PROJECT_DESIGN_CODE_STATE_KEY, code)
    setter(PROJECT_CODE_EDITION_STATE_KEY, edition)
    # Keep legacy keys synchronized before Setup widgets are created or during
    # save/load.  Do not write widget-owned keys after the widgets have been
    # instantiated in the same Streamlit run.
    if sync_legacy_widget_keys:
        setter(LEGACY_DESIGN_CODE_WIDGET_KEY, code)
        setter(LEGACY_CODE_EDITION_WIDGET_KEY, edition)
    return code, edition


def workflow_member_type_from_session(session_state: Mapping[str, Any] | Any) -> str:
    """Return the active workflow member type from session state.

    Chrome/header widgets are rendered on every page and may execute before the
    Project page has normalized ``design_code`` for the current workflow.  Read
    the active AnalysisModeSettings directly so display and routing guards can
    still show the workflow-compatible design code.
    """

    getter = _state_getter(session_state)
    settings = getter("analysis_mode_settings", None)
    if isinstance(settings, Mapping):
        member = str(settings.get("member_type") or "").strip()
        if member:
            return member
    member = str(getattr(settings, "member_type", "") or "").strip()
    if member:
        return member
    return str(getter("member_type", "column_pier_pmm") or "column_pier_pmm")


def workflow_project_design_code_from_session(session_state: Mapping[str, Any] | Any) -> str:
    """Return the workflow-compatible project design code from session state.

    This read-side guard prevents stale project/session labels such as ACI 318
    from being displayed while the active workflow is Bridge Beam/Girder, where
    AASHTO LRFD is mandatory.
    """

    member = workflow_member_type_from_session(session_state)
    return default_project_design_code_for_workflow(member, project_design_code_from_session(session_state))


def workflow_project_code_edition_from_session(session_state: Mapping[str, Any] | Any) -> str:
    """Return a valid edition label for the workflow-compatible design code."""

    getter = _state_getter(session_state)
    code = workflow_project_design_code_from_session(session_state)
    return normalize_project_code_edition(code, getter(PROJECT_CODE_EDITION_STATE_KEY, getter(LEGACY_CODE_EDITION_WIDGET_KEY, None)))


def workflow_project_code_label_from_session(session_state: Mapping[str, Any] | Any) -> str:
    """Return a display label that cannot contradict the active workflow."""

    code = workflow_project_design_code_from_session(session_state)
    edition = workflow_project_code_edition_from_session(session_state)
    if edition and code.casefold() in edition.casefold():
        return edition
    return f"{code} {edition}".strip()


def girder_sls_code_for_project_code(code: object | None) -> GirderSLSProfileCode:
    """Map project code to the existing girder SLS preview profile namespace."""

    canonical = normalize_project_design_code(code)
    if canonical == PROJECT_CODE_AASHTO_LRFD:
        return "AASHTO LRFD Bridge"
    return "ACI 318"


def project_code_capability_cards(code: object | None, member_type: str | None = None) -> list[dict[str, str]]:
    """Return compact capability/status rows for project-level code routing.

    These are UI status guards only.  They do not authorize solver behavior.
    WORKFLOW.TYPE2 makes the project design-code selector workflow-aware.
    """

    member = str(member_type or "column_pier_pmm")
    canonical = default_project_design_code_for_workflow(member, code)
    if member == "beam_girder":
        workflow_note = "Active Bridge Beam/Girder workflow"
        pmm_status = "NOT APPLICABLE"
        pmm_note = "Column/Pier PMM is hidden in the Bridge Beam/Girder workflow."
        girder_status = "PREVIEW AVAILABLE"
        girder_note = "Bridge Beam/Girder uses AASHTO LRFD. Current flexure, SHEAR.CODE2, TORSION.CODE2, staged SLS, deflection/camber, and prestress tools remain guarded preview / engineering-review workflows until final code-certified bridge design milestones are completed."
    elif member == "building_beam_girder":
        workflow_note = "Active Building Beam/Girder workflow"
        pmm_status = "NOT APPLICABLE"
        pmm_note = "Column/Pier PMM is hidden in the Building Beam/Girder workflow."
        girder_status = "PREVIEW / REVIEW"
        girder_note = "Building Beam/Girder uses ACI 318. Current flexure, SHEAR.CODE2, TORSION.CODE2, staged SLS, deflection/camber, and prestress tools remain guarded preview / engineering-review workflows; bridge-specific tools are intentionally hidden."
    elif member == "portal_frame_crossbeam":
        workflow_note = "Active Portal Frame Crossbeam workflow"
        pmm_status = "NOT APPLICABLE"
        pmm_note = "Column/Pier PMM is hidden in the Portal Frame Crossbeam workflow."
        girder_status = "LAYOUT READY"
        girder_note = "Portal Frame Crossbeam uses ACI 318 for member-design routing. WF1 establishes segmented solid/hollow geometry and top-referenced tendon profile source-of-truth only; SLS, ULS, losses, anchorage, and D-region certification remain future guarded scope."
    elif canonical == PROJECT_CODE_AASHTO_LRFD:
        workflow_note = "Active Column/Pier/Wall/Pylon workflow"
        pmm_status = "AVAILABLE / REVIEW"
        pmm_note = "AASHTO LRFD 9th Column/Pier/Wall/Pylon PMM route is implemented for B-region axial-flexure, and AASHTO.COL.SHEAR1 provides simplified nonprestressed B-region shear; torsion, PSC/general-procedure shear, slenderness, final seismic certification, and hollow-wall local-buckling checks remain guarded; AASHTO.COL.SEISMIC1 provides a Section 5.11.4 transverse detailing advisor."
        girder_status = "NOT ACTIVE"
        girder_note = "Bridge/Building beam-girder checks are hidden because the active workflow is Column/Pier/Wall/Pylon."
    else:
        workflow_note = "Active Column/Pier/Wall/Pylon workflow"
        pmm_status = "AVAILABLE"
        pmm_note = "Current Column/Pier/Wall/Pylon PMM workflow is ACI-oriented."
        girder_status = "NOT ACTIVE"
        girder_note = "Bridge/Building beam-girder checks are hidden because the active workflow is Column/Pier/Wall/Pylon."
    return [
        {"title": "Project Design Code", "value": canonical, "detail": workflow_code_policy_message(member), "status": "info"},
        {"title": "Active Workflow", "value": workflow_note, "detail": "Tabs read this project basis; unsupported engines show REVIEW", "status": "info"},
        {"title": "Column/Pier PMM", "value": pmm_status, "detail": pmm_note, "status": "ready" if pmm_status in {"AVAILABLE", "AVAILABLE / REVIEW"} else ("neutral" if pmm_status in {"NOT APPLICABLE", "NOT ACTIVE"} else "warning")},
        {"title": "Beam/Girder Checks", "value": girder_status, "detail": girder_note, "status": "neutral" if girder_status in {"NOT APPLICABLE", "NOT ACTIVE"} else "warning"},
    ]

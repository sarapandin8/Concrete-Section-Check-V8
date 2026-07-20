"""Analysis mode/member type helper functions."""

from __future__ import annotations

from concrete_pmm_pro.core.analysis import AnalysisModeSettings

COLUMN_PIER_WORKFLOW = "column_pier_pmm"
BRIDGE_BEAM_GIRDER_WORKFLOW = "beam_girder"
BUILDING_BEAM_GIRDER_WORKFLOW = "building_beam_girder"
PORTAL_FRAME_CROSSBEAM_WORKFLOW = "portal_frame_crossbeam"


def analysis_mode_label(settings: AnalysisModeSettings) -> str:
    if settings.member_type == COLUMN_PIER_WORKFLOW:
        return "Column / Pier / Wall / Pylon — RC / Prestressed Member"
    if settings.member_type == BRIDGE_BEAM_GIRDER_WORKFLOW:
        return "Bridge Beam / Girder — RC / Prestressed Member"
    if settings.member_type == BUILDING_BEAM_GIRDER_WORKFLOW:
        return "Building Beam / Girder — RC / Prestressed Member"
    if settings.member_type == PORTAL_FRAME_CROSSBEAM_WORKFLOW:
        return "Portal Frame Crossbeam — Prestressed Concrete"
    if settings.member_type == "general_section":
        return "Column / Pier / Wall / Pylon — RC / Prestressed Member"
    return "Unknown Analysis Mode"


def analysis_mode_description(settings: AnalysisModeSettings) -> str:
    if settings.description:
        return settings.description
    if settings.member_type == COLUMN_PIER_WORKFLOW:
        return (
            "Workflow for column-type members primarily reviewed with Pu, Mux, and Muy. "
            "ACI 318 and AASHTO LRFD 9th PMM routes are available for B-region axial-flexure; shear/torsion and second-order/seismic checks remain capability-guarded."
        )
    if settings.member_type == BRIDGE_BEAM_GIRDER_WORKFLOW:
        return (
            "Bridge Beam/Girder workflow for RC/prestressed bridge members. AASHTO LRFD is the project code basis; "
            "implemented tools include guarded Beam/Girder ULS flexure/shear/torsion gates, staged SLS stress previews, deflection/camber previews, prestress, debonding, and bridge load components."
        )
    if settings.member_type == BUILDING_BEAM_GIRDER_WORKFLOW:
        return (
            "Building Beam/Girder workflow for RC/prestressed building members. ACI 318 is the project code basis; "
            "implemented tools include guarded Beam/Girder ULS flexure/shear/torsion gates and building-oriented SLS stress/deflection previews; bridge-specific tools remain hidden."
        )
    if settings.member_type == PORTAL_FRAME_CROSSBEAM_WORKFLOW:
        return (
            "Portal frame prestressed concrete crossbeam workflow for station-based solid/hollow member layout, "
            "top-referenced tendon profile definition, ACI design-code routing, and future prestress-loss FEA handoff. "
            "WF1 establishes geometry and tendon source-of-truth only; SLS, ULS, loss, anchorage, and D-region checks remain future guarded scope."
        )
    if settings.member_type == "general_section":
        return (
            "Legacy General Section mode is migrated to the explicit Column / Pier / Wall / Pylon "
            "PMM workflow to avoid ambiguous design interpretation."
        )
    return "Analysis mode is not recognized."


def is_pmm_primary_workflow(settings: AnalysisModeSettings) -> bool:
    return settings.member_type == COLUMN_PIER_WORKFLOW


def is_beam_girder_future_workflow(settings: AnalysisModeSettings) -> bool:
    """Return True for the active Bridge Beam/Girder workflow.

    The function name is preserved for backward compatibility with existing UI
    code; WORKFLOW.TYPE2 narrows this helper to bridge girders only, not building
    beam/girder workflows.
    """

    return settings.member_type == BRIDGE_BEAM_GIRDER_WORKFLOW


def is_bridge_beam_girder_workflow(settings: AnalysisModeSettings) -> bool:
    return settings.member_type == BRIDGE_BEAM_GIRDER_WORKFLOW


def is_building_beam_girder_workflow(settings: AnalysisModeSettings) -> bool:
    return settings.member_type == BUILDING_BEAM_GIRDER_WORKFLOW


def is_portal_frame_crossbeam_workflow(settings: AnalysisModeSettings) -> bool:
    return settings.member_type == PORTAL_FRAME_CROSSBEAM_WORKFLOW


def analysis_mode_warnings(settings: AnalysisModeSettings) -> list[str]:
    warnings: list[str] = []
    if settings.member_type == BRIDGE_BEAM_GIRDER_WORKFLOW:
        warnings.extend(
            [
                "Bridge Beam/Girder uses AASHTO LRFD project code basis. Implemented Beam/Girder ULS/SLS tools are guarded preview / engineering-review workflows; final code-certified bridge girder design remains outside current scope.",
                "Do not double-count prestress by entering Pe as Pu when prestress elements are defined.",
                "Bridge-specific inputs such as girder spacing, number of girders, barrier/parapet/sidewalk, wearing surface, and CSiBridge LL+IM are hidden outside this workflow.",
            ]
        )
    elif settings.member_type == BUILDING_BEAM_GIRDER_WORKFLOW:
        warnings.extend(
            [
                "Building Beam/Girder uses ACI 318 project code basis.",
                "Building Beam/Girder ULS/SLS tools are guarded preview / engineering-review workflows; bridge-specific staged girder assumptions are intentionally hidden.",
            ]
        )
    elif settings.member_type == PORTAL_FRAME_CROSSBEAM_WORKFLOW:
        warnings.extend(
            [
                "Portal Frame Crossbeam uses ACI 318 project design-code routing, while the Crossbeam Prestress Loss page uses an explicit AASHTO friction/wobble basis.",
                "Current Crossbeam tools do not certify SLS stress, final effective prestress, ULS strength, anchorage zones, solid/hollow transition zones, column joint regions, or local D-regions.",
            ]
        )
    elif settings.member_type == "general_section":
        warnings.append(
            "Legacy General Section mode has been removed from the active workflow list; use Column/Pier PMM, Bridge Beam/Girder, or Building Beam/Girder."
        )
    return warnings

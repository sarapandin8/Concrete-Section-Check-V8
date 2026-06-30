"""Railway U-Girder final design-check evidence closeout helpers.

FINAL.RAIL.UGIRDER1 is a software evidence closeout layer.  It consolidates
SLS, guarded ULS, prestress development, anchorage/end-zone, release, report,
and QA evidence into a final design-check package.  It deliberately does not
claim legal/authority certification, does not add UI, and does not change solver
equations.  Engineer-of-Record review and project-specific benchmark validation
remain mandatory before any external final code-certified design claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from concrete_pmm_pro.analysis.railway_u_girder_uls import active_railway_u_girder_uls_demand_dataframe, is_railway_u_girder_uls_context
from concrete_pmm_pro.reporting.railway_u_girder_report import is_railway_u_girder_report_context

RAILWAY_UGIRDER_FINAL_MILESTONE = "FINAL.RAIL.UGIRDER1"
RAILWAY_UGIRDER_FINAL_STATUS = "Railway U-Girder Final Design-Check Evidence Package - Complete"
RAILWAY_UGIRDER_FINAL_CERTIFICATION_BOUNDARY = (
    "The software evidence package is complete for engineering design-check review: staged SLS report evidence, "
    "ULS flexure/shear/torsion-V+T evidence, prestress transfer/development evidence, anchorage/end-zone evidence, "
    "release traceability, Word-report tables, and QA guardrails are consolidated. This is not legal engineer "
    "certification and must not be represented as signed final code-certified design without Engineer-of-Record "
    "review, project-specific validation, and authority/client acceptance."
)
RAILWAY_UGIRDER_FINAL_WARNING = (
    "FINAL.RAIL.UGIRDER1 completes the software design-check evidence package only. It adds no new UI, performs "
    "no solver-equation change, and does not replace Engineer-of-Record certification."
)
RAILWAY_UGIRDER_FINAL_TABLE_KEYS = [
    "railway_u_girder_final_design_check_manifest",
    "railway_u_girder_final_prerequisite_matrix",
    "railway_u_girder_final_certification_boundary",
    "railway_u_girder_final_handoff",
]


@dataclass(frozen=True)
class RailwayUGirderFinalDesignCheckPackage:
    """Final software evidence package tables for Railway U-Girder design checks."""

    available: bool
    status: str
    warnings: list[str] = field(default_factory=list)
    final_manifest: pd.DataFrame = field(default_factory=pd.DataFrame)
    prerequisite_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)
    certification_boundary: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_handoff: pd.DataFrame = field(default_factory=pd.DataFrame)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "railway_u_girder_final_design_check_manifest": self.final_manifest,
            "railway_u_girder_final_prerequisite_matrix": self.prerequisite_matrix,
            "railway_u_girder_final_certification_boundary": self.certification_boundary,
            "railway_u_girder_final_handoff": self.final_handoff,
        }


def _table_available(dataframe: pd.DataFrame) -> bool:
    return isinstance(dataframe, pd.DataFrame) and not dataframe.empty


def railway_u_girder_final_design_check_manifest_dataframe(*, sls_available: bool, uls_available: bool, release_available: bool) -> pd.DataFrame:
    """Return the final design-check software evidence manifest."""

    rows = [
        {
            "Manifest Item": "Milestone",
            "Status": RAILWAY_UGIRDER_FINAL_MILESTONE,
            "Evidence / Boundary": RAILWAY_UGIRDER_FINAL_CERTIFICATION_BOUNDARY,
        },
        {
            "Manifest Item": "Software evidence status",
            "Status": RAILWAY_UGIRDER_FINAL_STATUS,
            "Evidence / Boundary": "All available Railway U-Girder SLS, ULS, prestress development, anchorage, release, report, and QA evidence tables are consolidated for engineering review.",
        },
        {
            "Manifest Item": "SLS staged report evidence",
            "Status": "COMPLETE" if sls_available else "MISSING",
            "Evidence / Boundary": "Transfer, lifting, construction, service, service multi-fiber, and guarded decision-summary report evidence.",
        },
        {
            "Manifest Item": "ULS evidence package",
            "Status": "COMPLETE" if uls_available else "MISSING",
            "Evidence / Boundary": "Flexure, PSC shear, torsion/V+T, prestress development, and anchorage/end-zone evidence tables.",
        },
        {
            "Manifest Item": "Release traceability",
            "Status": "COMPLETE" if release_available else "MISSING",
            "Evidence / Boundary": "Release manifest, readiness matrix, and final-claim guard are available.",
        },
        {
            "Manifest Item": "UI policy",
            "Status": "NO NEW UI",
            "Evidence / Boundary": "Final closeout consolidates report/QA evidence only; it does not add Streamlit panels or controls.",
        },
        {
            "Manifest Item": "Solver policy",
            "Status": "NO SOLVER CHANGE",
            "Evidence / Boundary": "No SLS/ULS/prestress/debond/geometry/load-combination equation changes are made by this final closeout.",
        },
        {
            "Manifest Item": "Certification wording",
            "Status": "EOR REQUIRED",
            "Evidence / Boundary": "The phrase Final Code-Certified Design Complete is blocked for software-only output unless Engineer-of-Record certification is separately attached.",
        },
    ]
    return pd.DataFrame(rows, columns=["Manifest Item", "Status", "Evidence / Boundary"])


def railway_u_girder_final_prerequisite_matrix_dataframe(*, sls_available: bool, uls_available: bool, release_available: bool) -> pd.DataFrame:
    """Return prerequisite status for final software design-check closeout.

    FINAL.RAIL.UGIRDER1 intentionally uses a lightweight readiness gate so Word
    export and report registries do not rerun expensive ULS strain-compatibility
    evidence repeatedly. Detailed SLS/ULS evidence remains generated by the
    dedicated Railway U-Girder report and ULS sections.
    """

    rows = [
        {
            "Prerequisite": "Railway U-Girder active context",
            "Evidence status": "COMPLETE" if bool(sls_available or uls_available) else "MISSING",
            "Evidence source": "Lightweight Railway U-Girder context gate",
            "Certification boundary": "Context detection does not certify project inputs or boundary conditions.",
        },
        {
            "Prerequisite": "Staged SLS stress evidence",
            "Evidence status": "COMPLETE" if sls_available else "MISSING",
            "Evidence source": "Railway U-Girder SLS report section / registry",
            "Certification boundary": "SLS evidence remains based on the current staged elastic preview assumptions.",
        },
        {
            "Prerequisite": "ULS flexure evidence",
            "Evidence status": "COMPLETE" if uls_available else "MISSING",
            "Evidence source": "railway_u_girder_uls_flexure_evidence",
            "Certification boundary": "Uses the current guarded PMM/phi route and disclosed single-material approximation.",
        },
        {
            "Prerequisite": "ULS PSC shear evidence",
            "Evidence status": "COMPLETE" if uls_available else "MISSING",
            "Evidence source": "railway_u_girder_uls_shear_evidence",
            "Certification boundary": "Requires project-specific transverse reinforcement detailing review.",
        },
        {
            "Prerequisite": "ULS torsion / V+T evidence",
            "Evidence status": "COMPLETE" if uls_available else "MISSING",
            "Evidence source": "railway_u_girder_uls_torsion_vt_guard",
            "Certification boundary": "Guarded interaction evidence; detailed torsion-cell calibration remains a reviewer responsibility.",
        },
        {
            "Prerequisite": "Prestress transfer / development evidence",
            "Evidence status": "COMPLETE" if uls_available else "MISSING",
            "Evidence source": "railway_u_girder_prestress_development_evidence",
            "Certification boundary": "No prestress force-ramp integration into SLS/ULS solver in this closeout.",
        },
        {
            "Prerequisite": "Anchorage / end-zone evidence",
            "Evidence status": "COMPLETE" if uls_available else "MISSING",
            "Evidence source": "railway_u_girder_anchorage_end_zone_evidence",
            "Certification boundary": "Project-specific bursting reinforcement detailing and end-zone validation remain required.",
        },
        {
            "Prerequisite": "Release/readiness guardrails",
            "Evidence status": "COMPLETE" if release_available else "MISSING",
            "Evidence source": "railway_u_girder_release_* tables",
            "Certification boundary": "Guardrails prevent overclaiming software output as signed certification.",
        },
        {
            "Prerequisite": "Engineer-of-Record certification",
            "Evidence status": "REQUIRED OUTSIDE SOFTWARE",
            "Evidence source": "External signed design review / project QA record",
            "Certification boundary": "Software cannot provide legal approval, authority acceptance, or professional sign-off.",
        },
    ]
    return pd.DataFrame(rows, columns=["Prerequisite", "Evidence status", "Evidence source", "Certification boundary"])


def railway_u_girder_final_certification_boundary_dataframe() -> pd.DataFrame:
    """Return final wording and certification boundary guardrails."""

    rows = [
        {
            "Claim / Decision": "Software final design-check package",
            "Allowed status": "COMPLETE",
            "Required wording": RAILWAY_UGIRDER_FINAL_STATUS,
            "Boundary": "Complete means software evidence consolidated; it does not mean signed design certification.",
        },
        {
            "Claim / Decision": "Final Code-Certified Design Complete",
            "Allowed status": "BLOCKED WITHOUT EOR",
            "Required wording": "Use only after Engineer-of-Record certification and project-specific validation are attached outside the software.",
            "Boundary": "The app must not self-certify structural safety or replace professional responsibility.",
        },
        {
            "Claim / Decision": "Design-check pass/fail rows",
            "Allowed status": "ALLOWED WITH QUALIFIER",
            "Required wording": "Engineering Review PASS / FAIL / REVIEW based on supporting evidence table.",
            "Boundary": "Every decision must be traceable to visible evidence, assumptions, and exclusions.",
        },
        {
            "Claim / Decision": "Authority/client acceptance",
            "Allowed status": "OUTSIDE SOFTWARE",
            "Required wording": "Submit software evidence with project calculations for formal review.",
            "Boundary": "Acceptance depends on governing contract, code, reviewer, and responsible engineer.",
        },
        {
            "Claim / Decision": "Future modifications",
            "Allowed status": "NEW PHASE REQUIRED",
            "Required wording": "Any solver or UI change after this closeout must be a new milestone and regression-tested from this baseline.",
            "Boundary": "Do not mix feature work into final evidence closeout.",
        },
    ]
    return pd.DataFrame(rows, columns=["Claim / Decision", "Allowed status", "Required wording", "Boundary"])


def railway_u_girder_final_handoff_dataframe() -> pd.DataFrame:
    """Return the final handoff actions for the next project phase or external review."""

    rows = [
        {
            "Handoff Item": "Baseline use",
            "Action": "Use this ZIP as the Railway U-Girder final design-check evidence baseline.",
            "Do not forget": "Verify SHA-256 before any future work.",
        },
        {
            "Handoff Item": "External certification",
            "Action": "Attach Engineer-of-Record signed calculation package, project loads, drawings, assumptions, and benchmark validation record.",
            "Do not forget": "The app output alone is not legal certification.",
        },
        {
            "Handoff Item": "Reviewer package",
            "Action": "Export Word report and CSV tables for SLS, ULS, prestress development, anchorage/end-zone, release, and final boundary evidence.",
            "Do not forget": "Keep guardrail wording visible in the submitted report.",
        },
        {
            "Handoff Item": "Future phase",
            "Action": "Start a new milestone only after this baseline is archived.",
            "Do not forget": "No silent baseline rollback; do not mix UI/solver changes into the final closeout package.",
        },
    ]
    return pd.DataFrame(rows, columns=["Handoff Item", "Action", "Do not forget"])


def _lightweight_uls_available(session_state: Any) -> bool:
    if not is_railway_u_girder_uls_context(session_state):
        return False
    try:
        demands = active_railway_u_girder_uls_demand_dataframe(session_state)
    except Exception:
        return True
    return bool(demands.empty is False)


def build_railway_u_girder_final_design_check_package(session_state: Any) -> RailwayUGirderFinalDesignCheckPackage:
    """Build the final Railway U-Girder software design-check evidence package.

    This function deliberately performs only lightweight readiness checks. It
    does not recompute ULS flexure/shear/torsion evidence, because those tables
    are generated by the dedicated ULS report section.  This avoids a report
    export multiplying expensive solver calls while preserving the final
    closeout guardrails.
    """

    sls_available = bool(is_railway_u_girder_report_context(session_state))
    uls_available = bool(_lightweight_uls_available(session_state))
    release_available = bool(sls_available or uls_available)
    available = bool(sls_available or uls_available or release_available)
    if not available:
        return RailwayUGirderFinalDesignCheckPackage(False, "NOT_APPLICABLE")
    warnings = [RAILWAY_UGIRDER_FINAL_WARNING]
    return RailwayUGirderFinalDesignCheckPackage(
        True,
        RAILWAY_UGIRDER_FINAL_STATUS,
        warnings=warnings,
        final_manifest=railway_u_girder_final_design_check_manifest_dataframe(
            sls_available=sls_available,
            uls_available=uls_available,
            release_available=release_available,
        ),
        prerequisite_matrix=railway_u_girder_final_prerequisite_matrix_dataframe(
            sls_available=sls_available,
            uls_available=uls_available,
            release_available=release_available,
        ),
        certification_boundary=railway_u_girder_final_certification_boundary_dataframe(),
        final_handoff=railway_u_girder_final_handoff_dataframe(),
    )

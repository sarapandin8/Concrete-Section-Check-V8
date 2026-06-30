"""Railway U-Girder engineering-review release closeout helpers.

RELEASE.RAIL.UGIRDER1 is a delivery/traceability closeout layer only.  It
summarizes the current SLS + guarded ULS evidence package without adding UI,
changing solver equations, or promoting the application to final code-certified
structural design software.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from concrete_pmm_pro.analysis.railway_u_girder_uls import build_railway_u_girder_uls_framework_package
from concrete_pmm_pro.reporting.railway_u_girder_report import build_railway_u_girder_sls_report_package

RAILWAY_UGIRDER_RELEASE_MILESTONE = "RELEASE.RAIL.UGIRDER1"
RAILWAY_UGIRDER_RELEASE_STATUS = "Railway U-Girder Engineering Review Release Baseline - Closeout Ready"
RAILWAY_UGIRDER_RELEASE_BOUNDARY = (
    "Closeout-ready means SLS report evidence, guarded ULS flexure/shear/torsion-V+T evidence, "
    "prestress transfer/development evidence, anchorage/end-zone evidence, Word-report traceability, "
    "and QA guardrails are packaged as an engineering-review baseline. It is not final code-certified "
    "design and is not engineer certification."
)
RAILWAY_UGIRDER_RELEASE_WARNING = (
    "RELEASE.RAIL.UGIRDER1 is a final engineering-review release baseline only. It adds no new UI, "
    "no solver-equation change, and no certified approval wording."
)
RAILWAY_UGIRDER_RELEASE_TABLE_KEYS = [
    "railway_u_girder_release_manifest",
    "railway_u_girder_release_readiness",
    "railway_u_girder_final_claim_guard",
]


@dataclass(frozen=True)
class RailwayUGirderReleasePackage:
    """Report-ready release-closeout tables for Railway U-Girder."""

    available: bool
    status: str
    warnings: list[str] = field(default_factory=list)
    release_manifest: pd.DataFrame = field(default_factory=pd.DataFrame)
    release_readiness: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_claim_guard: pd.DataFrame = field(default_factory=pd.DataFrame)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "railway_u_girder_release_manifest": self.release_manifest,
            "railway_u_girder_release_readiness": self.release_readiness,
            "railway_u_girder_final_claim_guard": self.final_claim_guard,
        }


def railway_u_girder_release_manifest_dataframe() -> pd.DataFrame:
    """Return the release manifest table for the closeout baseline."""

    rows = [
        {
            "Release Item": "Milestone",
            "Status": RAILWAY_UGIRDER_RELEASE_MILESTONE,
            "Evidence / Boundary": RAILWAY_UGIRDER_RELEASE_BOUNDARY,
        },
        {
            "Release Item": "Release status",
            "Status": RAILWAY_UGIRDER_RELEASE_STATUS,
            "Evidence / Boundary": "Use this ZIP as the Railway U-Girder engineering-review release baseline after package verification.",
        },
        {
            "Release Item": "UI policy",
            "Status": "NO NEW UI",
            "Evidence / Boundary": "Closeout adds report/manifest traceability only; it does not add new tabs, panels, or Streamlit controls.",
        },
        {
            "Release Item": "Solver policy",
            "Status": "NO SOLVER CHANGE",
            "Evidence / Boundary": "No SLS stress, ULS strength, prestress/debond, geometry, section-property, load-combination, or project-schema equations are changed by release closeout.",
        },
        {
            "Release Item": "Allowed wording",
            "Status": "GUARDED",
            "Evidence / Boundary": "Use engineering-review, guarded evidence, review-ready, and closeout-ready wording only.",
        },
        {
            "Release Item": "Certification status",
            "Status": "NOT CERTIFIED",
            "Evidence / Boundary": "Engineer-of-Record review, project-specific validation, and authority requirements remain outside the software release closeout.",
        },
    ]
    return pd.DataFrame(rows, columns=["Release Item", "Status", "Evidence / Boundary"])


def railway_u_girder_release_readiness_dataframe(*, sls_available: bool, uls_available: bool) -> pd.DataFrame:
    """Return a compact readiness matrix for the release baseline."""

    rows = [
        {
            "Area": "SLS staged workflow",
            "Release status": "ENGINEERING REVIEW READY" if sls_available else "REVIEW",
            "Closeout evidence": "Geometry, material/stage settings, transfer/lifting/construction/service stress preview, multi-fiber service summary, and Word report tables.",
            "Remaining boundary": "Not a final code-certified SLS design certificate.",
        },
        {
            "Area": "ULS flexure evidence",
            "Release status": "ENGINEERING REVIEW READY" if uls_available else "REVIEW",
            "Closeout evidence": "Guarded Mux demand-vs-capacity evidence routed through the current PMM/phi layer.",
            "Remaining boundary": "Requires independent Railway U-Girder benchmarks before final certification wording.",
        },
        {
            "Area": "ULS PSC shear evidence",
            "Release status": "ENGINEERING REVIEW READY" if uls_available else "REVIEW",
            "Closeout evidence": "Guarded Vuy shear route with provided transverse reinforcement evidence.",
            "Remaining boundary": "Requires refined PSC/end-region calibration and project detailing validation.",
        },
        {
            "Area": "ULS torsion / V+T guard",
            "Release status": "ENGINEERING REVIEW READY" if uls_available else "REVIEW",
            "Closeout evidence": "Guarded Tu/Vuy torsion and linear interaction review index using closed-hoop/Al evidence.",
            "Remaining boundary": "Requires Railway U-Girder torsion-cell calibration before final certification wording.",
        },
        {
            "Area": "Prestress development",
            "Release status": "ENGINEERING REVIEW READY" if uls_available else "REVIEW",
            "Closeout evidence": "Transfer/development length evidence for active strand rows and debonding input.",
            "Remaining boundary": "No prestress force-ramp integration into SLS/ULS solvers in this release.",
        },
        {
            "Area": "Anchorage / end-zone",
            "Release status": "ENGINEERING REVIEW READY" if uls_available else "REVIEW",
            "Closeout evidence": "Bursting/spalling and sleeve-termination evidence screens from active strand rows.",
            "Remaining boundary": "Project-specific end-zone reinforcement detailing and benchmarks remain required.",
        },
        {
            "Area": "Final design certification",
            "Release status": "NOT CERTIFIED",
            "Closeout evidence": "Guardrails intentionally block certified approval wording.",
            "Remaining boundary": "Engineer-of-Record review and independent validation are mandatory before certified use.",
        },
    ]
    return pd.DataFrame(rows, columns=["Area", "Release status", "Closeout evidence", "Remaining boundary"])


def railway_u_girder_final_claim_guard_dataframe() -> pd.DataFrame:
    """Return release claim guardrails that prevent overclaiming."""

    rows = [
        {
            "Claim Area": "Permitted release claim",
            "Guard status": "ALLOWED",
            "Required wording": RAILWAY_UGIRDER_RELEASE_STATUS,
        },
        {
            "Claim Area": "Design-check outputs",
            "Guard status": "ALLOWED WITH QUALIFIER",
            "Required wording": "Engineering Review PASS / FAIL / REVIEW where an evidence table explicitly supports the result.",
        },
        {
            "Claim Area": "Certification claim",
            "Guard status": "BLOCKED",
            "Required wording": "Do not describe the Railway U-Girder workflow as final certified design software.",
        },
        {
            "Claim Area": "Authority / legal certification",
            "Guard status": "BLOCKED",
            "Required wording": "The software output supports engineering review; it does not replace the responsible engineer's signed review.",
        },
        {
            "Claim Area": "Future development",
            "Guard status": "DEFERRED",
            "Required wording": "Independent benchmark validation, refined calibration, and project-specific detailing remain future milestones.",
        },
    ]
    return pd.DataFrame(rows, columns=["Claim Area", "Guard status", "Required wording"])


def build_railway_u_girder_release_package(session_state: Any) -> RailwayUGirderReleasePackage:
    """Build the Railway U-Girder release closeout package from current state."""

    sls_package = build_railway_u_girder_sls_report_package(session_state)
    uls_package = build_railway_u_girder_uls_framework_package(session_state)
    available = bool(sls_package.available or uls_package.available)
    if not available:
        return RailwayUGirderReleasePackage(False, "NOT_APPLICABLE")
    warnings = [RAILWAY_UGIRDER_RELEASE_WARNING]
    warnings.extend(getattr(sls_package, "warnings", []) or [])
    warnings.extend(getattr(uls_package, "warnings", []) or [])
    return RailwayUGirderReleasePackage(
        True,
        RAILWAY_UGIRDER_RELEASE_STATUS,
        warnings=warnings,
        release_manifest=railway_u_girder_release_manifest_dataframe(),
        release_readiness=railway_u_girder_release_readiness_dataframe(
            sls_available=bool(sls_package.available),
            uls_available=bool(uls_package.available),
        ),
        final_claim_guard=railway_u_girder_final_claim_guard_dataframe(),
    )

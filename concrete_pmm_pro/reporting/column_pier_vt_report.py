"""Column/Pier V+T report-preview tables from stored Analysis results.

This module is intentionally read-only.  It consumes the DataFrame/results that
were stored by the Analysis > ULS Strength > Shear + Torsion workspace and does
not rerun PMM, SLS, shear, torsion, or V+T calculations from Report / QA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import pandas as pd

from concrete_pmm_pro.core.analysis import AnalysisModeSettings


COLUMN_PIER_VT_REPORT_STATUS = "COLUMN_PIER.VT.REPORT1"
COLUMN_PIER_VT_REPORT_WARNING = (
    "Column/Pier V+T report preview summarizes stored Analysis results only; "
    "seismic special detailing, hoop anchorage/hooks, lap splices, shop-drawing detailing, "
    "prestressed/general-procedure V+T, and final code certification remain outside this gate."
)
COLUMN_PIER_VT_SCOPE_GUARD = (
    "Seismic confinement/detailing review remains separate: this V+T gate uses the Control section "
    "transverse row only and does not certify plastic-hinge confinement, hoop anchorage, "
    "lap-splice confinement, or seismic detailing."
)
COLUMN_PIER_VT_TABLE_KEYS = (
    "column_pier_vt_report_summary",
    "column_pier_vt_report_results",
    "column_pier_vt_report_audit",
    "column_pier_vt_report_scope_guard",
)


@dataclass(frozen=True)
class ColumnPierVTReportPackage:
    available: bool
    summary: pd.DataFrame
    results: pd.DataFrame
    audit: pd.DataFrame
    scope_guard: pd.DataFrame
    warnings: list[str]
    status: str = COLUMN_PIER_VT_REPORT_STATUS

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "column_pier_vt_report_summary": self.summary,
            "column_pier_vt_report_results": self.results,
            "column_pier_vt_report_audit": self.audit,
            "column_pier_vt_report_scope_guard": self.scope_guard,
        }


def _get(mapping: Any, key: str, default: Any = None) -> Any:
    if mapping is None:
        return default
    if hasattr(mapping, "get"):
        try:
            return mapping.get(key, default)
        except (AttributeError, TypeError, ValueError):
            return default
    return getattr(mapping, key, default)


def _mode_from_state(session_state: Any) -> AnalysisModeSettings:
    value = _get(session_state, "analysis_mode_settings")
    if isinstance(value, AnalysisModeSettings):
        return value
    if isinstance(value, dict):
        try:
            return AnalysisModeSettings.model_validate(value)
        except Exception:
            return AnalysisModeSettings()
    return AnalysisModeSettings()


def _as_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if value is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame()


def _display_number(value: Any, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(numeric):
        return "-"
    return f"{numeric:.{digits}f}"


def _stored_vt_dataframe(session_state: Any) -> pd.DataFrame:
    for key in ("column_pier_combined_vt_result_df", "column_pier_combined_vt_df"):
        df = _as_dataframe(_get(session_state, key))
        if not df.empty:
            return df
    return pd.DataFrame()


def _stored_screen_dataframe(session_state: Any, audit_df: pd.DataFrame) -> pd.DataFrame:
    screen = _as_dataframe(_get(session_state, "column_pier_combined_vt_screen_df"))
    if not screen.empty:
        return screen
    columns = ["Status", "Case", "Dir", "Vu", "Tu", "Stress", "Transv.", "Long. Al", "Source", "D/C"]
    if audit_df.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for _, row in audit_df.iterrows():
        source_shear = str(row.get("Source shear status") or "-")
        source_torsion = str(row.get("Source torsion status") or "-")
        rows.append(
            {
                "Status": str(row.get("Status") or "-"),
                "Case": str(row.get("Case") or "-"),
                "Dir": str(row.get("Direction") or "-"),
                "Vu": f"{_display_number(row.get('Vu kN'), 2)} kN" if _display_number(row.get("Vu kN"), 2) != "-" else "-",
                "Tu": f"{_display_number(row.get('Tu kN-m'), 2)} kN-m" if _display_number(row.get("Tu kN-m"), 2) != "-" else "-",
                "Stress": str(row.get("Stress status") or "-"),
                "Transv.": str(row.get("Transverse status") or "-"),
                "Long. Al": str(row.get("Longitudinal status") or "-"),
                "Source": f"V {source_shear} / T {source_torsion}",
                "D/C": _display_number(row.get("Overall D/C value")),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _stored_cards(session_state: Any) -> list[dict[str, object]]:
    value = _get(session_state, "column_pier_combined_vt_summary_cards")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _overall_status(audit_df: pd.DataFrame) -> str:
    if audit_df.empty or "Status" not in audit_df.columns:
        return "NOT READY"
    statuses = {str(value) for value in audit_df["Status"].tolist()}
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


def _max_dc(audit_df: pd.DataFrame) -> str:
    if audit_df.empty or "Overall D/C value" not in audit_df.columns:
        return "-"
    values = pd.to_numeric(audit_df["Overall D/C value"], errors="coerce").dropna()
    if values.empty:
        return "-"
    return _display_number(values.max())


def _governing_label(audit_df: pd.DataFrame, session_state: Any) -> str:
    stored = str(_get(session_state, "column_pier_combined_vt_governing_label", "") or "").strip()
    if stored:
        return stored
    if audit_df.empty:
        return "No stored governing combined V+T row"
    work = audit_df.copy()
    work["__dc"] = pd.to_numeric(work.get("Overall D/C value"), errors="coerce")
    work["__tu"] = pd.to_numeric(work.get("Tu kN-m"), errors="coerce").abs()
    work["__vu"] = pd.to_numeric(work.get("Vu kN"), errors="coerce").abs()
    work = work[work["__dc"].notna()]
    if work.empty:
        return "No finite stored governing combined V+T D/C"
    row = work.sort_values(["__dc", "__tu", "__vu"], ascending=[False, False, False], kind="stable").iloc[0]
    return f"{row.get('Case', '-')} / {row.get('Direction', '-')}"


def _controlling_cause(audit_df: pd.DataFrame, session_state: Any) -> str:
    stored = str(_get(session_state, "column_pier_combined_vt_controlling_cause", "") or "").strip()
    if stored:
        return stored
    if _overall_status(audit_df) == "PASS":
        return "No failing governing cause"
    if audit_df.empty:
        return "No stored Column/Pier V+T result"
    return "Controlling cause must be reviewed in the stored audit table."


def _summary_dataframe(session_state: Any, audit_df: pd.DataFrame, results_df: pd.DataFrame) -> pd.DataFrame:
    cards = _stored_cards(session_state)
    if cards:
        return pd.DataFrame(
            [
                {
                    "Item": str(card.get("title") or "-"),
                    "Value": str(card.get("value") or "-"),
                    "Detail": str(card.get("detail") or ""),
                    "Status": str(card.get("status") or "info"),
                }
                for card in cards
            ],
            columns=["Item", "Value", "Detail", "Status"],
        )
    rows = [
        ("Strength gate", _overall_status(audit_df), _controlling_cause(audit_df, session_state), "danger" if _overall_status(audit_df) == "FAIL" else "info"),
        ("Governing row", f"D/C {_max_dc(audit_df)}", _governing_label(audit_df, session_state), "info"),
        ("Stored result rows", f"{len(results_df):,}", "Compact results stored from Analysis > ULS Strength > Shear + Torsion.", "info"),
        ("Seismic detailing", "REVIEW REQUIRED", "Confinement, hoop anchorage, lap-splice confinement, and plastic-hinge detailing are not certified by this gate.", "warning"),
    ]
    return pd.DataFrame(
        [{"Item": item, "Value": value, "Detail": detail, "Status": status} for item, value, detail, status in rows],
        columns=["Item", "Value", "Detail", "Status"],
    )


def _scope_guard_dataframe(session_state: Any) -> pd.DataFrame:
    scope_guard = str(_get(session_state, "column_pier_combined_vt_scope_guard", COLUMN_PIER_VT_SCOPE_GUARD) or COLUMN_PIER_VT_SCOPE_GUARD)
    route = str(_get(session_state, "column_pier_combined_vt_route_label", "Column/Pier V+T") or "Column/Pier V+T")
    return pd.DataFrame(
        [
            {
                "Guard Item": "Seismic/detailing scope",
                "Status": "REVIEW REQUIRED",
                "Message": scope_guard,
                "Report Color Semantics": "warning / amber, not strength failure",
            },
            {
                "Guard Item": "Prestress/general procedure",
                "Status": "NOT INCLUDED",
                "Message": f"{route} report preview uses the stored scoped nonprestressed route only; prestressed/general-procedure V+T remains guarded.",
                "Report Color Semantics": "neutral / guarded scope",
            },
        ],
        columns=["Guard Item", "Status", "Message", "Report Color Semantics"],
    )


def is_column_pier_vt_report_context(session_state: Any) -> bool:
    mode = _mode_from_state(session_state)
    if mode.member_type != "column_pier_pmm":
        return False
    return not _stored_vt_dataframe(session_state).empty


def build_column_pier_vt_report_package(session_state: Any) -> ColumnPierVTReportPackage:
    audit = _stored_vt_dataframe(session_state)
    results = _stored_screen_dataframe(session_state, audit)
    available = _mode_from_state(session_state).member_type == "column_pier_pmm" and not audit.empty
    summary = _summary_dataframe(session_state, audit, results) if available else pd.DataFrame(columns=["Item", "Value", "Detail", "Status"])
    scope_guard = _scope_guard_dataframe(session_state) if available else pd.DataFrame(columns=["Guard Item", "Status", "Message", "Report Color Semantics"])
    warnings = [COLUMN_PIER_VT_REPORT_WARNING] if available else ["No stored Column/Pier V+T result is available for Report / QA preview."]
    return ColumnPierVTReportPackage(
        available=available,
        summary=summary,
        results=results if available else pd.DataFrame(columns=["Status", "Case", "Dir", "Vu", "Tu", "Stress", "Transv.", "Long. Al", "Source", "D/C"]),
        audit=audit if available else pd.DataFrame(),
        scope_guard=scope_guard,
        warnings=warnings,
    )


def column_pier_vt_report_tables_to_dataframe(package: ColumnPierVTReportPackage) -> pd.DataFrame:
    rows = []
    for key, dataframe in package.tables().items():
        rows.append(
            {
                "Table Key": key,
                "Available": bool(package.available and not dataframe.empty),
                "Rows": int(len(dataframe)),
                "Status": package.status if package.available else "NOT_AVAILABLE",
            }
        )
    return pd.DataFrame(rows, columns=["Table Key", "Available", "Rows", "Status"])

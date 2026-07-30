"""Source-gated Effective Prestress handoff for external FEA workflows.

The handoff exports the currently reviewed tendon stress/force chain without
pretending to calculate portal-frame secondary prestress inside Concrete
Section Pro.  External FEA remains responsible for primary/secondary response,
and verified SLS resultants return through the main Loads workspace.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
from math import isfinite
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


EFFECTIVE_PRESTRESS_FEA_HANDOFF_SCHEMA = (
    "crossbeam-effective-prestress-fea-handoff-v1"
)
EFFECTIVE_PRESTRESS_FEA_HANDOFF_BASIS = (
    "Aps-weighted piecewise-trapezoidal integration over projected member station s"
)


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.to_dict(orient="records")]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _collapse_tendon_station_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate station faces once for one Tendon.

    Numeric values are averaged at a shared station.  Text labels are joined so
    the audit still records which point/face rows were represented.
    """

    grouped: dict[float, list[dict[str, Any]]] = {}
    for row in rows:
        station = round(_finite_float(row.get("Station s (m)")), 9)
        grouped.setdefault(station, []).append(row)

    numeric_fields = (
        "Aps (mm²)",
        "fpj (MPa)",
        "Friction (MPa)",
        "Anchorage (MPa)",
        "ES (MPa)",
        "Creep (MPa)",
        "Shrinkage (MPa)",
        "Relaxation (MPa)",
        "TD total (MPa)",
        "Total loss (MPa)",
        "Loss (% fpj)",
        "fpe preview (MPa)",
        "Pj (kN)",
        "Pe preview (kN)",
    )
    collapsed: list[dict[str, Any]] = []
    for station in sorted(grouped):
        station_rows = grouped[station]
        result: dict[str, Any] = {
            "Tendon": str(station_rows[0].get("Tendon") or ""),
            "Station s (m)": station,
            "Point": " / ".join(
                sorted(
                    {
                        str(row.get("Point") or "").strip()
                        for row in station_rows
                        if str(row.get("Point") or "").strip()
                    }
                )
            ),
            "Source rows collapsed": len(station_rows),
        }
        for field in numeric_fields:
            values = [_finite_float(row.get(field)) for row in station_rows]
            result[field] = sum(values) / len(values) if values else 0.0
        collapsed.append(result)
    return collapsed


def _trapezoidal_average(rows: list[dict[str, Any]], value_key: str) -> float | None:
    if not rows:
        return None
    points = sorted(
        (float(row["Station s (m)"]), _finite_float(row.get(value_key))) for row in rows
    )
    if len(points) == 1:
        return float(points[0][1])
    covered = float(points[-1][0]) - float(points[0][0])
    if covered <= 0.0:
        return float(points[0][1])
    integral = 0.0
    for (s0, v0), (s1, v1) in zip(points, points[1:]):
        integral += 0.5 * (float(v0) + float(v1)) * (float(s1) - float(s0))
    return integral / covered


def _nearest_station_row(rows: list[dict[str, Any]], station_m: float) -> dict[str, Any]:
    return min(
        rows,
        key=lambda row: (
            abs(_finite_float(row.get("Station s (m)")) - float(station_m)),
            _finite_float(row.get("Station s (m)")),
        ),
    )


def _canonical_fingerprint_payload(
    *,
    summary_payload: Mapping[str, Any],
    tendon_rows: list[dict[str, Any]],
    station_rows: list[dict[str, Any]],
    member_length_m: float,
) -> dict[str, Any]:
    return {
        "schema": EFFECTIVE_PRESTRESS_FEA_HANDOFF_SCHEMA,
        "member_length_m": round(float(member_length_m), 9),
        "averaging_basis": str(summary_payload.get("averaging_basis") or ""),
        "weighted_fpj_mpa": summary_payload.get("weighted_fpj_mpa"),
        "total_aps_mm2": summary_payload.get("total_aps_mm2"),
        "average_total_loss_mpa": summary_payload.get("average_total_loss_mpa"),
        "average_effective_stress_mpa": summary_payload.get(
            "average_effective_stress_mpa"
        ),
        "average_effective_force_kn": summary_payload.get(
            "average_effective_force_kn"
        ),
        "tendon_rows": tendon_rows,
        "station_rows": station_rows,
    }


def build_effective_prestress_fea_handoff(
    summary_payload: Mapping[str, Any],
    *,
    member_length_m: float,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, external-FEA-only Effective Prestress handoff."""

    issues: list[str] = []
    if not bool(summary_payload.get("effective_preview_ready")):
        issues.append(
            "Effective Prestress preview is not CURRENT/closed; refresh all loss components before export."
        )
    if not bool(summary_payload.get("projected_coverage_ready")):
        issues.append("Projected station coverage is incomplete for one or more Tendons.")

    effective_rows = _records(summary_payload.get("effective_station_rows"))
    if not effective_rows:
        issues.append("No Tendon/station Effective Prestress rows are available.")

    tendon_ids = sorted(
        {
            str(row.get("Tendon") or "").strip()
            for row in effective_rows
            if str(row.get("Tendon") or "").strip()
        }
    )
    tendon_handoff_rows: list[dict[str, Any]] = []
    station_handoff_rows: list[dict[str, Any]] = []
    tolerance = max(1.0e-7 * max(float(member_length_m), 1.0), 1.0e-9)

    for tendon_id in tendon_ids:
        tendon_source = [
            row for row in effective_rows if str(row.get("Tendon") or "") == tendon_id
        ]
        collapsed = _collapse_tendon_station_rows(tendon_source)
        if not collapsed:
            issues.append(f"{tendon_id}: no usable station rows.")
            continue
        if (
            abs(_finite_float(collapsed[0].get("Station s (m)"))) > tolerance
            or abs(
                _finite_float(collapsed[-1].get("Station s (m)"))
                - float(member_length_m)
            )
            > tolerance
        ):
            issues.append(
                f"{tendon_id}: station coverage must include s=0 and s={float(member_length_m):.3f} m."
            )

        average_fpe = _trapezoidal_average(collapsed, "fpe preview (MPa)")
        average_loss = _trapezoidal_average(collapsed, "Total loss (MPa)")
        average_fpj = _trapezoidal_average(collapsed, "fpj (MPa)")
        aps = _finite_float(collapsed[0].get("Aps (mm²)"))
        if average_fpe is None or average_loss is None or average_fpj is None or aps <= 0.0:
            issues.append(f"{tendon_id}: incomplete average stress/area source.")
            continue

        left = collapsed[0]
        mid = _nearest_station_row(collapsed, 0.5 * float(member_length_m))
        right = collapsed[-1]
        average_pe = aps * average_fpe / 1000.0
        average_pj = aps * average_fpj / 1000.0
        average_loss_percent = 100.0 * average_loss / average_fpj if average_fpj > 0 else 0.0
        remaining_percent = 100.0 * average_fpe / average_fpj if average_fpj > 0 else 0.0

        tendon_handoff_rows.append(
            {
                "Tendon": tendon_id,
                "Aps (mm²)": aps,
                "fpj (MPa)": average_fpj,
                "Pj (kN)": average_pj,
                "Left s (m)": _finite_float(left.get("Station s (m)")),
                "Left fpe (MPa)": _finite_float(left.get("fpe preview (MPa)")),
                "Left Pe (kN)": _finite_float(left.get("Pe preview (kN)")),
                "Mid s (m)": _finite_float(mid.get("Station s (m)")),
                "Mid fpe (MPa)": _finite_float(mid.get("fpe preview (MPa)")),
                "Mid Pe (kN)": _finite_float(mid.get("Pe preview (kN)")),
                "Right s (m)": _finite_float(right.get("Station s (m)")),
                "Right fpe (MPa)": _finite_float(right.get("fpe preview (MPa)")),
                "Right Pe (kN)": _finite_float(right.get("Pe preview (kN)")),
                "Average fpe (MPa)": average_fpe,
                "Average Pe (kN)": average_pe,
                "Average total loss (MPa)": average_loss,
                "Average loss (% fpj)": average_loss_percent,
                "Remaining prestress (%)": remaining_percent,
                "Recommended direct-input basis": (
                    "Use fpe/Pe once; disable duplicate FEA loss calculation"
                ),
            }
        )

        for row in collapsed:
            station_handoff_rows.append(
                {
                    "Tendon": tendon_id,
                    "Station s (m)": _finite_float(row.get("Station s (m)")),
                    "Point / face source": str(row.get("Point") or ""),
                    "Aps (mm²)": aps,
                    "fpj (MPa)": _finite_float(row.get("fpj (MPa)")),
                    "Pj (kN)": _finite_float(row.get("Pj (kN)")),
                    "Friction loss (MPa)": _finite_float(row.get("Friction (MPa)")),
                    "Anchorage loss (MPa)": _finite_float(row.get("Anchorage (MPa)")),
                    "Elastic-shortening loss (MPa)": _finite_float(row.get("ES (MPa)")),
                    "Creep loss (MPa)": _finite_float(row.get("Creep (MPa)")),
                    "Shrinkage loss (MPa)": _finite_float(row.get("Shrinkage (MPa)")),
                    "Relaxation loss (MPa)": _finite_float(row.get("Relaxation (MPa)")),
                    "Total loss (MPa)": _finite_float(row.get("Total loss (MPa)")),
                    "Loss (% fpj)": _finite_float(row.get("Loss (% fpj)")),
                    "fpe (MPa)": _finite_float(row.get("fpe preview (MPa)")),
                    "Pe (kN)": _finite_float(row.get("Pe preview (kN)")),
                    "Source rows collapsed": int(row.get("Source rows collapsed") or 1),
                }
            )

    fingerprint_payload = _canonical_fingerprint_payload(
        summary_payload=summary_payload,
        tendon_rows=tendon_handoff_rows,
        station_rows=station_handoff_rows,
        member_length_m=float(member_length_m),
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    ready = bool(not issues and tendon_handoff_rows and station_handoff_rows)
    status = "READY — EXTERNAL FEA APPLICATION ONLY" if ready else "SOURCE BLOCKED"

    for row in tendon_handoff_rows:
        row["Source fingerprint"] = fingerprint
    for row in station_handoff_rows:
        row["Source fingerprint"] = fingerprint

    summary_rows = [
        {"Field": "Schema version", "Value": EFFECTIVE_PRESTRESS_FEA_HANDOFF_SCHEMA},
        {"Field": "Handoff status", "Value": status},
        {"Field": "Generated at (UTC)", "Value": generated},
        {"Field": "Source fingerprint", "Value": fingerprint},
        {"Field": "Member length (m)", "Value": float(member_length_m)},
        {"Field": "Tendons represented", "Value": len(tendon_handoff_rows)},
        {"Field": "Station rows represented", "Value": len(station_handoff_rows)},
        {"Field": "Total Aps (mm²)", "Value": summary_payload.get("total_aps_mm2")},
        {"Field": "Average fpj (MPa)", "Value": summary_payload.get("weighted_fpj_mpa")},
        {"Field": "Average total loss (MPa)", "Value": summary_payload.get("average_total_loss_mpa")},
        {"Field": "Average total loss (% fpj)", "Value": summary_payload.get("average_total_loss_percent")},
        {"Field": "Average fpe (MPa)", "Value": summary_payload.get("average_effective_stress_mpa")},
        {"Field": "Initial total tendon force (kN)", "Value": summary_payload.get("initial_total_force_kn")},
        {"Field": "Average effective tendon force (kN)", "Value": summary_payload.get("average_effective_force_kn")},
        {"Field": "Averaging basis", "Value": EFFECTIVE_PRESTRESS_FEA_HANDOFF_BASIS},
        {"Field": "TD loss basis", "Value": "Representative event-stress scalar; not tendon/station dependent"},
        {"Field": "Secondary prestress", "Value": "Not included — calculate from structural restraint in external FEA"},
        {"Field": "SLS return route", "Value": "Import verified FEA SLS P/V2/M3 responses in the main Loads workspace"},
    ]

    instructions_rows = [
        {
            "Topic": "Purpose",
            "Instruction": "This handoff transfers tendon stress/force after accounted losses to external FEA. It is separate from ULS/SLS demand import.",
        },
        {
            "Topic": "Units and sign",
            "Instruction": "Station s is metres from the left member end. Strand stress is MPa tension-positive; Pe/Pj are positive tendon tension magnitudes in kN.",
        },
        {
            "Topic": "Preferred application",
            "Instruction": "When the FEA model accepts effective tendon force/stress directly, use fpe/Pe and disable any duplicate friction, anchorage, ES, creep, shrinkage, or relaxation loss calculation.",
        },
        {
            "Topic": "Alternative application",
            "Instruction": "When the FEA model must start from jacking force, use fpj/Pj and reproduce the same loss profile. Do not also input fpe/Pe; choose one application route only.",
        },
        {
            "Topic": "Force variation",
            "Instruction": "Use the Station Handoff profile when the FEA program supports tendon-force variation. Left/Mid/Right and Average values are a compact review summary, not replacements for the full station profile.",
        },
        {
            "Topic": "Secondary prestress",
            "Instruction": "Secondary prestress is not a tendon loss and must not be subtracted from Pe. Let the external portal-frame model calculate primary and secondary response from compatibility/restraint.",
        },
        {
            "Topic": "Time-dependent limitation",
            "Instruction": "Current creep, shrinkage, and relaxation are a representative TD scalar applied to each tendon/station. Adopt project-specific refined losses in FEA when the project requires greater detail.",
        },
        {
            "Topic": "SLS feedback",
            "Instruction": "After FEA calculates primary + secondary prestress and service actions, export verified SLS P/V2/M3 responses and import them through the main Loads workspace.",
        },
        {
            "Topic": "Traceability",
            "Instruction": "Record the source fingerprint in the FEA model note/report. Regenerate the handoff whenever tendon geometry, material, stressing, or loss inputs change.",
        },
    ]

    return {
        "ready": ready,
        "status": status,
        "issues": issues,
        "schema_version": EFFECTIVE_PRESTRESS_FEA_HANDOFF_SCHEMA,
        "source_fingerprint": fingerprint,
        "generated_at_utc": generated,
        "summary_rows": summary_rows,
        "tendon_rows": tendon_handoff_rows,
        "station_rows": station_handoff_rows,
        "system_station_rows": _records(summary_payload.get("system_station_rows")),
        "instructions_rows": instructions_rows,
        "scope_guard": (
            "External FEA must calculate portal-frame secondary prestress. Concrete Section Pro does not automatically feed this preview into SLS; verified FEA SLS responses must be imported back through Loads."
        ),
    }


def _style_export_sheet(worksheet) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="D9E2F3")
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=thin)
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(bottom=thin)
    for column_cells in worksheet.columns:
        values = [str(cell.value or "") for cell in column_cells]
        width = min(max(max((len(value) for value in values), default=0) + 2, 10), 42)
        worksheet.column_dimensions[column_cells[0].column_letter].width = width
    worksheet.row_dimensions[1].height = 30


def effective_prestress_handoff_excel_bytes(handoff: Mapping[str, Any]) -> bytes:
    """Return a formatted multi-sheet XLSX handoff workbook."""

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(_records(handoff.get("summary_rows"))).to_excel(
            writer, sheet_name="Handoff Summary", index=False
        )
        pd.DataFrame(_records(handoff.get("tendon_rows"))).to_excel(
            writer, sheet_name="Tendon Handoff", index=False
        )
        pd.DataFrame(_records(handoff.get("station_rows"))).to_excel(
            writer, sheet_name="Station Handoff", index=False
        )
        pd.DataFrame(_records(handoff.get("system_station_rows"))).to_excel(
            writer, sheet_name="System Station", index=False
        )
        pd.DataFrame(_records(handoff.get("instructions_rows"))).to_excel(
            writer, sheet_name="Instructions", index=False
        )
        for worksheet in writer.book.worksheets:
            _style_export_sheet(worksheet)
    return output.getvalue()


def effective_prestress_handoff_csv_bytes(
    handoff: Mapping[str, Any], *, table: str
) -> bytes:
    """Return UTF-8-SIG CSV bytes for the selected handoff table."""

    table_map = {
        "tendon": "tendon_rows",
        "station": "station_rows",
        "system": "system_station_rows",
    }
    key = table_map.get(str(table).casefold())
    if key is None:
        raise ValueError(f"Unsupported handoff CSV table: {table}")
    return pd.DataFrame(_records(handoff.get(key))).to_csv(index=False).encode("utf-8-sig")

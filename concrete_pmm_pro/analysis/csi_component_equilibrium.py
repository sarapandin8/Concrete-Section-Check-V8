"""Read-only CSI Girder/Beam/Slab equilibrium audit; not a strength solver.

Offsets are identified from P/M2/M3 in declared single-state exports. Torque
is an independent prediction, never a fitted target. The inferred offsets
are not CSI metadata and must never configure force origins or resistance.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import math
import re
import numpy as np
import pandas as pd

from concrete_pmm_pro.io.girder_csi_import import (
    FORCE_MAP, is_csi_table, prepare_csi_table, read_tables, source_info, split_member_tables,
)
from concrete_pmm_pro.io.csi_force_reference import transport

VERSION = "IGIRDER.EQUILIBRIUM27"
# Export reconciliation tolerance, in normalized kN / kN-m; not a design limit.
ROUNDING_TOLERANCE = 0.005


@dataclass
class ComponentAudit:
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    offsets: pd.DataFrame = field(default_factory=pd.DataFrame)
    trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    messages: list[str] = field(default_factory=list)


def _component(name):
    tokens = list(re.finditer(r"\b(girder|beam|slab)\b", str(name), re.I))
    if len(tokens) != 1:
        return None
    token = tokens[0]
    family = re.sub(r"\s+", " ", str(name)[:token.start()] + "{component}" + str(name)[token.end():]).strip()
    return token.group().casefold(), family.casefold(), family.replace("{component}", "Girder")


def _least_squares(matrix, values):
    matrix, values = np.asarray(matrix, float), np.asarray(values, float)
    scale = np.linalg.norm(matrix, axis=0)
    if not np.isfinite(matrix).all() or not np.isfinite(values).all() or np.any(scale <= 0):
        raise ValueError("Axial-force variation cannot identify both component offsets.")
    scaled = matrix / scale
    coef, _, rank, singular = np.linalg.lstsq(scaled, values, rcond=None)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else math.inf
    if rank != 2 or condition > 1e8:
        raise ValueError("Component origins are not independently identifiable from these axial forces.")
    return coef / scale, condition


def _row_key(row, info):
    return (str(info.get("case") or ""), str(info.get("case_type") or ""),
        str(info.get("step") or "").casefold(), str(info.get("step_number") or ""),
        str(info.get("control") or ""), str(info.get("location_type") or ""),
        str(info.get("section_cut") if info.get("section_cut") is not None else ""),
        round(float(row["Station x (m)"]), 10), int(info.get("occurrence", 1)))


def _fit_group(parts, common):
    stations = sorted({key[-2] for key in common})
    if len(stations) < 4 or len(common) < 6:
        raise ValueError("At least four distinct stations and six matched cuts are required for identification and holdout.")
    train_stations = set(stations[::2])
    train = [key for key in common if key[-2] in train_stations]
    holdout = [key for key in common if key[-2] not in train_stations]

    def matrix(keys):
        return [[-parts["beam"][k]["P"], -parts["slab"][k]["P"]] for k in keys]

    def delta(keys, action):
        return [parts["girder"][k][action] - parts["beam"][k][action] - parts["slab"][k][action] for k in keys]

    r2, condition = _least_squares(matrix(common), delta(common, "M3"))
    r3, _ = _least_squares(matrix(common), delta(common, "M2"))
    hold_r2, _ = _least_squares(matrix(train), delta(train, "M3"))
    hold_r3, _ = _least_squares(matrix(train), delta(train, "M2"))
    max_hold = 0.0
    for key in holdout:
        rebuilt = [transport(parts[kind][key], r2_m=float(hold_r2[i]), r3_m=float(hold_r3[i]))
            for i, kind in enumerate(("beam", "slab"))]
        for f in ("T", "M2", "M3"):
            max_hold = max(max_hold, abs(parts["girder"][key][f] - sum(v[f] for v in rebuilt)))
    return r2, r3, condition, max_hold, len(train), len(holdout)


def audit_tables(tables, *, source_name, source_mode="unverified", concurrency_confirmed=False, evidence=""):
    groups = {}
    for sheet, table in tables.items():
        if not is_csi_table(table):
            continue
        for member in split_member_tables(table, sheet_name=sheet):
            identity = _component(member.girder or sheet)
            if identity is None:
                continue
            kind, family, label = identity
            family_key = (member.bridge_object, family)
            group = groups.setdefault(family_key, {"label": label, "parts": {}, "errors": []})
            parsed = prepare_csi_table(member.frame, sheet_name=sheet,
                case_name=Path(source_name).stem, source_name=source_name,
                source_mode=source_mode, concurrency_confirmed=concurrency_confirmed, evidence=evidence)
            group["errors"].extend(parsed.errors)
            indexed = group["parts"].setdefault(kind, {})
            for _, row in parsed.frame.iterrows():
                info = source_info(row)
                key = _row_key(row, info)
                if key in indexed:
                    group["errors"].append(f"Duplicate {kind} cut identity across source sheets: {key}.")
                indexed[key] = {**{f: float(row[col]) for f, col in FORCE_MAP.items()},
                    "sheet": sheet, "row": info["row"],
                    "single_state": (info.get("source_mode") == "static"
                        and info.get("kind") == "CONCURRENT"
                        and key[2] not in {"max", "min"}
                        and (key[2] == "static" or bool(info.get("step_number"))))}
    summaries, offsets, traces = [], [], []
    for (bridge, _), group in groups.items():
        parts, label = group["parts"], group["label"]
        # Girder-only exports are normal; no speculative missing-component audit.
        if set(parts) == {"girder"} or "girder" not in parts:
            continue
        common_info = {"Source file": source_name, "Bridge": bridge, "Girder": label,
            "Audit version": VERSION, "Tolerance kN / kN-m": ROUNDING_TOLERANCE}
        if group["errors"] or set(parts) != {"girder", "beam", "slab"}:
            reason = "; ".join(group["errors"]) or "Matching Girder, Beam and Slab sheets are required."
            summaries.append({**common_info, "Audit status": "INPUT INCOMPLETE", "Reason": reason})
            continue
        keys = set(parts["girder"])
        if not keys or any(set(part) != keys for part in parts.values()):
            summaries.append({**common_info, "Audit status": "CUT MISMATCH",
                "Reason": "Component cases, steps, faces, occurrences or station grids differ; no force rows were paired."})
            continue
        by_case = {}
        for key in sorted(keys):
            # Keep every step, control identity and case separate in identification.
            by_case.setdefault(key[:5], []).append(key)
        for state_key, common in by_case.items():
            context = {**common_info, "Case": state_key[0], "Step": state_key[2],
                "Step number": state_key[3], "Matched cuts": len(common)}
            if not all(parts[kind][key]["single_state"] for kind in parts for key in common):
                envelope = state_key[2] in {"max", "min"}
                summaries.append({**context, "Audit status": "ENVELOPE — NO VECTOR SUM" if envelope else "STATE UNVERIFIED",
                    "Reason": "Component extrema/correspondence labels do not identify one shared loading state across all three components. No offsets were fitted."})
                continue
            try:
                r2, r3, condition, hold_error, ntrain, nhold = _fit_group(parts, common)
            except ValueError as exc:
                summaries.append({**context, "Audit status": "ORIGIN UNRESOLVED", "Reason": str(exc)})
                continue
            records = []
            for key in common:
                g, b, s = [parts[kind][key] for kind in ("girder", "beam", "slab")]
                shifted = [transport(v, r2_m=float(r2[i]), r3_m=float(r3[i])) for i, v in enumerate((b, s))]
                record = {**context, "Station x (m)": key[-2], "Occurrence": key[-1], "LocType": key[5],
                    "Section cut": key[6], "Girder Excel row": g["row"], "Beam Excel row": b["row"], "Slab Excel row": s["row"],
                    "Beam T at B kN-m": b["T"], "Slab T at S kN-m": s["T"],
                    "Beam r2V3 kN-m": float(r2[0])*b["V3"], "Slab r2V3 kN-m": float(r2[1])*s["V3"],
                    "Beam -r3V2 kN-m": -float(r3[0])*b["V2"], "Slab -r3V2 kN-m": -float(r3[1])*s["V2"]}
                for f in FORCE_MAP:
                    rebuilt = sum(v[f] for v in shifted)
                    record.update({f"Girder {f}": g[f], f"Rebuilt {f}": rebuilt, f"Residual {f}": g[f]-rebuilt})
                records.append(record)
            maxima = {f: max(abs(r[f"Residual {f}"]) for r in records) for f in FORCE_MAP}
            consistent = max(*maxima.values(), hold_error) <= ROUNDING_TOLERANCE + 1e-10
            status = "EQUILIBRIUM CONSISTENT" if consistent else "EQUILIBRIUM MISMATCH"
            summaries.append({**context, "Audit status": status,
                "Max force residual kN": max(maxima[f] for f in ("P", "V2", "V3")),
                "Max moment residual kN-m": max(maxima[f] for f in ("T", "M2", "M3")),
                "Holdout moment residual kN-m": hold_error, "Train cuts": ntrain, "Holdout cuts": nhold,
                "Scaled condition number": condition,
                "Reason": "Empirical moment-reference identification; torque independently predicted. Not a resistance or detailing check."})
            for i, kind in enumerate(("beam", "slab")):
                offsets.append({**context, "Component": kind.title(), "C_component-C_G local2 m": float(r2[i]),
                    "C_component-C_G local3 m": float(r3[i]), "Audit status": status,
                    "Origin basis": "Empirically inferred from P/M2/M3; not imported CSI metadata"})
            traces.extend({**r, "Audit status": status} for r in records)
    return ComponentAudit(pd.DataFrame(summaries), pd.DataFrame(offsets), pd.DataFrame(traces))


def audit_payload(payload, filename, **source_contract):
    return audit_tables(read_tables(payload, filename), source_name=filename, **source_contract)

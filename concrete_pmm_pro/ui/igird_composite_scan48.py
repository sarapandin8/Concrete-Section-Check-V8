"""Rank exact concurrent source vectors; never construct a force envelope.

Pure-action M=N=0 intercepts remain separate from the V-only/T-only diagnostic
intercepts holding the actual M3/N. The V–T governor is the maximum radial
utilization, not the largest imported torque. No design acceptance is inferred.
"""
from collections import Counter
import math

VERSION = "IGIRDER.FULLVT48.concurrent-source-scan"
SELECTION = ("Every eligible interior concurrent CSI source row is calculated; "
    "the maximum nominal V–T D/C governs each girder. Before/After and Max/Min "
    "vectors remain separate. Physical end rows are listed outside this model's scope.")


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def compact(entry):
    calc = entry.get("calculation") or {}
    return {**{k: entry.get(k) for k in ("Girder", "Case", "x (m)", "Source Excel row",
        "Source StepType", "Source location type", "Source input ordinal", "Status", "Reason")},
        "Model Vn (kN), M=N=0": calc.get("model_Vn_kN"),
        "Model Tn (kN-m), M=N=0": calc.get("model_Tn_kNm"),
        "V-only D/C, actual M/N": calc.get("model_V_only_actual_MN_DC"),
        "T-only D/C, actual M/N": calc.get("model_T_only_actual_MN_DC"),
        "Model nominal V–T D/C": calc.get("model_VT_DC"),
        "Nominal capacity exhausted": bool(calc.get("VT", {}).get("capacity_exhausted")),
        "CSI actions": entry.get("source_CSI"),
        "Actions used":entry.get("actions"),
        "Tu shift applied": (entry.get("torsion_reference") or {}).get("T shift applied"),
        "Baseline torsion threshold": (entry.get("baseline_code_check") or {}).get("Threshold status"),
        "Maximum numerical residual": max((v for action in ("V", "T", "VT", "V_fixed_MN", "T_fixed_MN")
            for v in calc.get(action, {}).get("checks", {}).values()), default=None)}


def _score(entry, action):
    calc = entry.get("calculation") or {}
    key = {"V": "model_V_only_actual_MN_DC", "T": "model_T_only_actual_MN_DC", "VT": "model_VT_DC"}[action]
    witness = calc.get({"V": "V_fixed_MN", "T": "T_fixed_MN", "VT": "VT"}[action], {})
    if witness.get("capacity_exhausted") and (not finite(calc.get(key)) or calc[key]>0):
        return math.inf
    value = calc.get(key)
    return float(value) if finite(value) else -math.inf


def summarize(entries, excluded):
    """Retain all compact row outcomes and only three full witnesses per girder."""
    members = list(dict.fromkeys(e["Girder"] for e in entries))
    primary, governing, coverage = [], [], []
    for member in members:
        rows = [e for e in entries if e["Girder"] == member]
        numeric = [e for e in rows if e.get("Status") == "MODEL REVIEW"]
        counts = Counter(e.get("Status") for e in rows)
        covered = {"Girder": member, "Interior source rows": len(rows), "Calculated rows": len(numeric),
            "Blocked / incomplete rows": len(rows)-len(numeric),
            "Physical end rows excluded": sum(e.get("Girder") == member for e in excluded),
            "Interior scan status": "COMPLETE" if len(rows) == len(numeric) else "INCOMPLETE",
            "Status counts": dict(counts)}
        coverage.append(covered)
        selected = max(numeric, key=lambda e: _score(e, "VT")) if numeric else rows[0]
        # Never hide a blocked row behind a numerically satisfactory governor.
        primary.append({**selected, "Row status": selected.get("Status"), "coverage": covered,
            "Status": selected.get("Status") if len(rows) == len(numeric) else "MODEL INCOMPLETE"})
        for action in ("V", "T", "VT"):
            candidates = [e for e in numeric if _score(e, action) > -math.inf]
            if candidates:
                governing.append({**max(candidates, key=lambda e: _score(e, action)), "Governing action": action})
    return {"rows": primary, "governing_rows": governing, "coverage": coverage,
        "station_rows": [compact(e) for e in entries], "excluded_rows": excluded, "selection": SELECTION}

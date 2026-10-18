"""Offline engineering QA. Never imported by Streamlit or saved to project JSON.

Run from the repository root:
    python tools/run_igird_reference42.py --output qa/evidence/igird_reference42
The generated JSON/CSV contain diagnostic reference evidence, not capacities.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from concrete_pmm_pro.analysis.igird_reference42 import (  # noqa: E402
    MATERIAL_PROFILE, VERSION, RCMaterial, RectangularRC,
    ReferenceConvergenceError, ReferenceScopeError, trace_postcracking,
)


def audit(*, steps: int = 160) -> tuple[dict, list[dict]]:
    fixture = ROOT / "qa/benchmarks/igird_reference42_2015.json"
    raw = fixture.read_bytes()
    data = json.loads(raw)
    results, curves = [], []
    tolerance = float(data["reproduction_relative_tolerance"])
    for values in data["cases"]:
        case = dict(zip(data["columns"], values))
        section = RectangularRC(case["b"], case["h"], case["hoop_b"], case["hoop_h"], case["Al"], case["At_s"])
        material = RCMaterial(case["fc"], case["eps0"], case["fly"], case["fty"])
        record = {
            "specimen": case["id"], "status": "NOT_CALCULATED",
            "torque_postcracking_peak_kNm": None, "twist_at_peak_deg_per_m": None,
            "published_theory_Tu_kNm": case["Tu_theory_kNm"],
            "published_theory_twist_deg_per_m": case["theta_u_theory_deg_per_m"],
            "measured_Tu_kNm": case["Tu_measured_kNm"],
            "torque_theory_relative_difference": None, "twist_theory_relative_difference": None,
            "computed_to_measured_torque_ratio": None,
            "maximum_equilibrium_relative_residual": None,
            "table2_fctm_MPa": case["fctm_table2"], "model_fcr_MPa": material.cracking_stress_MPa,
            "curve_branch_status": None, "production_accepted": False, "detail": "",
        }
        try:
            curve = trace_postcracking(section, material, steps=steps)
        except (ReferenceScopeError, ReferenceConvergenceError) as exc:
            record.update(status=type(exc).__name__, detail=str(exc))
        else:
            peak = curve.postcracking_peak
            torque = peak.torque_Nmm / 1e6
            twist = math.degrees(peak.twist_rad_per_mm) * 1000
            dt, da = torque / case["Tu_theory_kNm"] - 1, twist / case["theta_u_theory_deg_per_m"] - 1
            complete = curve.branch_status == "NUMERICALLY_COMPLETE"
            match = complete and abs(dt) <= tolerance and abs(da) <= tolerance
            record.update(
                status="PUBLISHED_POINTS_MATCH" if match else "REFERENCE_MISMATCH" if complete else "INCOMPLETE_BRANCH",
                torque_postcracking_peak_kNm=torque, twist_at_peak_deg_per_m=twist,
                torque_theory_relative_difference=dt, twist_theory_relative_difference=da,
                computed_to_measured_torque_ratio=torque / case["Tu_measured_kNm"],
                maximum_equilibrium_relative_residual=max(q.equilibrium_relative_residual for q in (*curve.states, peak)),
                curve_branch_status=curve.branch_status,
                detail="Post-cracking peak compared with the published Tu point; endpoint convention and material interpretation remain under audit.",
            )
            curves.append({"specimen": case["id"], "curve": asdict(curve)})
        results.append(record)
    matched = sum(q["status"] == "PUBLISHED_POINTS_MATCH" for q in results)
    solved = sum(q["torque_postcracking_peak_kNm"] is not None for q in results)
    summary = {
        "version": VERSION, "material_profile": MATERIAL_PROFILE,
        "fixture_sha256": hashlib.sha256(raw).hexdigest(), "source_doi": data["source_doi"],
        "selection": data["selection"], "reference_cases": len(results), "numerically_solved_cases": solved,
        "published_point_matches": matched, "reproduction_relative_tolerance": tolerance,
        "published_reproduction_status": "MATCHED_SELECTED_POINTS" if matched == len(results) else "NOT_REPRODUCED",
        "production_accepted": False,
        "excluded": ["initial elastic/cracking branch", "prestress", "open U with 90-degree hooks", "slab/girder construction joint",
                     "slip and anchorage", "combined N-M2-M3-V2-V3-T", "code nominal/design composite resistance"],
        "results": results,
    }
    return summary, curves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary, curves = audit()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "published_comparison.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output / "reference_curves.json").write_text(json.dumps(curves, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    with (args.output / "published_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary["results"][0]))
        writer.writeheader()
        writer.writerows(summary["results"])
    print(json.dumps({k: v for k, v in summary.items() if k not in ("results", "excluded")}, ensure_ascii=False))
    # Running an audit successfully is different from passing its engineering gate.
    # Shell/CI exit 2 keeps a failed published reproduction gate visible.
    return 0 if summary["published_reproduction_status"] == "MATCHED_SELECTED_POINTS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

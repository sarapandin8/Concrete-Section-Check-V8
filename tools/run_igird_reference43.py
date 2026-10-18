"""Source interpretation audit; offline evidence, never project capacities.

All material profiles use the same pre-existing 16 consecutive specimens and
the same 1% torque AND twist reproduction gate. A declared domain extension is
always distinguished from literal source reproduction. Exit 2 means that the
published reproduction/structural acceptance gates remain unmet.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from concrete_pmm_pro.analysis.igird_reference43 import (  # noqa: E402
    COMPARISON_WINDOW_START, VERSION, MaterialProfile, RCMaterial, RectangularRC,
    ReferenceConvergenceError, ReferenceScopeError, _equilibrium_residual,
    solve_state, steel_law_trace, trace_curve,
)


def _stage_residual(section, material, q):
    scale = material.concrete_strength_MPa * min(q.concrete_surface_strain / material.concrete_peak_strain, 1.)
    return float(max(abs(_equilibrium_residual(section, material, q))) / scale)


def audit(*, steps: int = 220) -> tuple[dict, list[dict]]:
    fixture = ROOT / "qa/benchmarks/igird_reference42_2015.json"
    raw = fixture.read_bytes()
    data = json.loads(raw)
    tolerance = float(data["reproduction_relative_tolerance"])
    profiles, curves = [], []
    for profile in MaterialProfile:
        results = []
        for values in data["cases"]:
            case = dict(zip(data["columns"], values))
            section = RectangularRC(case["b"], case["h"], case["hoop_b"], case["hoop_h"], case["Al"], case["At_s"])
            material = RCMaterial(case["fc"], case["eps0"], case["fly"], case["fty"])
            # The cap profile exposes both raw denominators even when the strict
            # profile must reject. It does not rescue a rejected strict result.
            laws = steel_law_trace(section, material,
                                   MaterialProfile.LEGACY42 if profile is MaterialProfile.LEGACY42
                                   else MaterialProfile.SOURCE2012_POSITIVE_CAP)
            raw_laws = [asdict(q) for q in laws]
            if profile is MaterialProfile.SOURCE2012_STRICT:
                for law in raw_laws:
                    if law["positive_cap_extension_used"]:
                        law["exponent"] = None
                    law["positive_cap_extension_used"] = False
            record = {
                "specimen": case["id"], "status": "NOT_CALCULATED", "profile": profile.value,
                "positive_cap_extension_required": any(q.exponent_denominator <= 0 for q in laws),
                "steel_laws": raw_laws,
                "concrete_tension_E_MPa": material.concrete_tension_E_MPa,
                "concrete_cracking_strain": material.cracking_strain,
                "concrete_cracking_stress_MPa": material.cracking_stress_MPa,
                "table2_fctm_MPa": case["fctm_table2"],
                "published_theory_Tu_kNm": case["Tu_theory_kNm"],
                "published_theory_twist_deg_per_m": case["theta_u_theory_deg_per_m"],
                "measured_Tu_kNm": case["Tu_measured_kNm"],
                "comparison_peak_kNm": None, "twist_at_comparison_peak_deg_per_m": None,
                "torque_theory_relative_difference": None, "twist_theory_relative_difference": None,
                "computed_to_measured_torque_ratio": None,
                "interval_peak_kNm": None, "termination": None, "branch_status": None,
                "maximum_stage_relative_equilibrium_residual": None,
                "minimum_twist_increment_rad_per_mm": None,
                "material_endpoint": None, "fixed_strain_states": [],
                "published_points_within_1_percent": False,
                "structural_validation_accepted": False, "production_accepted": False, "detail": "",
            }
            try:
                curve = trace_curve(section, material, profile=profile, steps=steps)
            except (ReferenceScopeError, ReferenceConvergenceError) as exc:
                record.update(status=type(exc).__name__, detail=str(exc))
            else:
                points = list(curve.states) + [curve.interval_peak]
                peak = curve.comparison_window_peak
                if peak:
                    points.append(peak)
                    torque = peak.torque_Nmm / 1e6
                    twist = math.degrees(peak.twist_rad_per_mm) * 1000
                    dt, da = torque / case["Tu_theory_kNm"] - 1, twist / case["theta_u_theory_deg_per_m"] - 1
                    match = abs(dt) <= tolerance and abs(da) <= tolerance
                    record.update(
                        status="PUBLISHED_POINTS_MATCH" if match else "REFERENCE_MISMATCH",
                        comparison_peak_kNm=torque, twist_at_comparison_peak_deg_per_m=twist,
                        torque_theory_relative_difference=dt, twist_theory_relative_difference=da,
                        computed_to_measured_torque_ratio=torque / case["Tu_measured_kNm"],
                        published_points_within_1_percent=match,
                    )
                else:
                    record["status"] = "MATERIAL_LIMIT_BEFORE_COMPARISON_WINDOW"
                for strain in (.0005, .001, .002, .0035):
                    if strain <= curve.states[-1].concrete_surface_strain:
                        record["fixed_strain_states"].append(asdict(solve_state(section, material, strain, profile=profile)))
                record.update(
                    interval_peak_kNm=curve.interval_peak.torque_Nmm / 1e6,
                    termination=curve.termination, branch_status=curve.branch_status,
                    maximum_stage_relative_equilibrium_residual=max(_stage_residual(section, material, q) for q in points),
                    minimum_twist_increment_rad_per_mm=min(b.twist_rad_per_mm-a.twist_rad_per_mm
                                                          for a,b in zip(curve.states,curve.states[1:])),
                    material_endpoint=asdict(curve.states[-1]),
                    detail="The e2s>=0.0005 comparison window is inherited from REFERENCE42, not a cracking definition. Numerical completeness is not structural validation.",
                )
                curves.append({"profile": profile.value, "specimen": case["id"], "curve": asdict(curve)})
            results.append(record)
        solved = [q for q in results if q["comparison_peak_kNm"] is not None]
        matched = sum(q["published_points_within_1_percent"] for q in results)
        ratios = [q["computed_to_measured_torque_ratio"] for q in solved]
        profiles.append({
            "profile": profile.value, "reference_cases": len(results), "numerically_solved_cases": len(solved),
            "unsupported_cases": sum(q["status"] == "ReferenceScopeError" for q in results),
            "declared_extension_cases": sum(q["positive_cap_extension_required"] for q in results)
                                        if profile is MaterialProfile.SOURCE2012_POSITIVE_CAP else 0,
            "published_point_matches": matched,
            "maximum_absolute_torque_theory_difference": max((abs(q["torque_theory_relative_difference"]) for q in solved), default=None),
            "maximum_absolute_twist_theory_difference": max((abs(q["twist_theory_relative_difference"]) for q in solved), default=None),
            "computed_to_measured_torque_statistics": {
                "sample_count": len(ratios), "mean": statistics.mean(ratios) if ratios else None,
                "minimum": min(ratios, default=None), "maximum": max(ratios, default=None),
                "sample_coefficient_of_variation": statistics.stdev(ratios)/statistics.mean(ratios) if len(ratios)>1 else None,
                "interpretation": "Descriptive reference statistics only; no structural acceptance band or strength factor is inferred.",
            },
            "published_reproduction_status": "MATCHED_SELECTED_POINTS" if matched == len(results) else "NOT_REPRODUCED",
            "production_accepted": False, "results": results,
        })
    summary = {
        "version": VERSION, "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "kernel_sha256": hashlib.sha256((ROOT / "concrete_pmm_pro/analysis/igird_reference43.py").read_bytes()).hexdigest(),
        "source_dois": [data["source_doi"], "10.1016/j.engstruct.2012.04.036"],
        "selection": data["selection"], "reproduction_relative_tolerance": tolerance,
        "comparison_window_start_surface_compression_strain": COMPARISON_WINDOW_START,
        "starting_surface_compression_strain": 1e-8, "continuation_steps": steps,
        "profiles": profiles,
        "published_reproduction_status": next(p["published_reproduction_status"] for p in profiles
                                             if p["profile"] == MaterialProfile.SOURCE2012_STRICT.value),
        "structural_validation_status": "NOT_ESTABLISHED_FOR_PROJECT_COMPOSITE_SYSTEM",
        "production_accepted": False,
        "excluded": ["source-defined cracking-torque reproduction", "prestressed girder/slab construction stages",
                     "nonrectangular composite shear-flow topology", "open U with 90-degree hooks and slab mesh",
                     "construction-joint slip/opening and anchorage", "simultaneous N-M2-M3-V2-V3-T resistance",
                     "code nominal/design composite resistance"],
    }
    return summary, curves


def write_evidence(output: Path, summary: dict, curves: list[dict]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    (output / "curves.json").write_text(json.dumps(curves, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n", encoding="utf-8")
    rows = [{k:v for k,v in result.items() if k not in {"steel_laws", "material_endpoint", "fixed_strain_states"}}
            for profile in summary["profiles"] for result in profile["results"]]
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    laws = [{"profile": p["profile"], "specimen": q["specimen"], **law}
            for p in summary["profiles"] for q in p["results"] for law in q["steel_laws"]]
    with (output / "steel_material_trace.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(laws[0]))
        writer.writeheader()
        writer.writerows(laws)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa/evidence/igird_reference43")
    parser.add_argument("--steps", type=int, default=220)
    args = parser.parse_args(argv)
    summary, curves = audit(steps=args.steps)
    write_evidence(args.output, summary, curves)
    print(json.dumps({"version": VERSION, "profiles": [
        {k:p[k] for k in ("profile", "reference_cases", "numerically_solved_cases", "unsupported_cases", "published_point_matches",
                         "maximum_absolute_torque_theory_difference", "maximum_absolute_twist_theory_difference")}
        for p in summary["profiles"]], "published_reproduction_status": summary["published_reproduction_status"],
        "production_accepted": False}, indent=2))
    return 0 if summary["production_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

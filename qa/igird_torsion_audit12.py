"""Read-only MAXMIN10 audit against direct US-unit AASHTO substitutions.

Hypothetical haunched I-girder: these forces are not the user's design data.
Run before and after a patch using --label, retaining both evidence sets.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import pandas as pd
from concrete_pmm_pro.core.models import Point2D, SectionGeometry
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls7_concurrent_vt import ready_state, check, physical
from test_igird_uls6_torsion_general_procedure import _route, _demand

INCH, KIP, KSI = 25.4, 4448.2216152605, 6.894757293168


def polygon_metrics(points):
    pairs = list(zip(points, points[1:]+points[:1]))
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in pairs))/2
    perimeter = sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in pairs)
    return area,perimeter


def independent_inset(points, offset):
    """Intersect parallel edge lines analytically; no geometry/code helpers.

    Valid for this single, counterclockwise, unsplit hypothetical I polygon.
    It is a benchmark, not a general-purpose geometry implementation.
    """
    lines = []
    for a,b in zip(points,points[1:]+points[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        lines.append(((a[0]-offset*dy/length,a[1]+offset*dx/length),(dx,dy)))
    def cross(a,b):
        return a[0]*b[1]-a[1]*b[0]
    vertices=[]
    for i,(q,s) in enumerate(lines):
        p,r=lines[i-1]
        den=cross(r,s)
        if abs(den)<1e-12:
            raise ValueError("Collinear edge outside this benchmark")
        t=cross((q[0]-p[0],q[1]-p[1]),s)/den
        vertices.append((p[0]+t*r[0],p[1]+t*r[1]))
    return vertices


def hypothetical_state():
    state = ready_state()
    points = [(-250, 0), (250, 0), (250, 200), (100, 300), (100, 1300),
              (400, 1400), (400, 1600), (-400, 1600), (-400, 1400),
              (-100, 1300), (-100, 300), (-250, 200)]
    state["section_geometry"] = SectionGeometry(name="Hypothetical haunched I",
        outer_polygon=[Point2D(x=x, y=y) for x, y in points])
    state["beam_girder_torsion_zone_settings"] = [{"Zone": "Full span",
        "Use for Torsion": True, "Closed Loop": True, "135° Hook": True}]
    return state


def reference(row, *, mu, vu, tu, nu=0):
    """Direct equations; source-owned geometry/steel terms held fixed.

    Mu floor uses actual Vu per printed pp. 5-71--5-72; only Vu in
    Eq. 5.7.3.4.2-4 becomes Veff. No application solver calls here.
    """
    dv = float(row["dv mm"])
    veff = float(row["Veff kN"]) * 1000
    denom = float(row["εs denominator N"])
    # All benchmark strands are fully transferred/developed at midspan.
    # Read the physical Aps/fpo source, not the application's epsilon result.
    aps_fpo = float(row["Aps raw tension mm2"]) * float(row["fpo full MPa"])
    mu_force = max(abs(mu) * 1e6 / dv, abs(vu) * 1000)
    eps = (mu_force - 0.5 * nu * 1000 + veff - aps_fpo) / denom
    eps_used = max(0.0, min(0.006, eps))
    theta = 29.0 + 3500 * eps_used
    beta = 4.8 / (1 + 750 * eps_used)
    cot = 1 / math.tan(math.radians(theta))
    ao_in2, ph_in = float(row["Ao mm2"]) / INCH**2, float(row["ph mm"]) / INCH
    fy_ksi, phi = float(row["fy MPa"]) / KSI, float(row["φ"])
    area = math.pi * 16**2 / 4
    ats_in = area / 100 / INCH
    tn_kipin = 2 * ao_in2 * ats_in * fy_ksi * cot
    return {"epsilon_s": eps, "theta_deg": theta, "beta": beta,
            "phiTn_kNm": phi * tn_kipin * KIP * INCH / 1e6,
            "Aps_fpo_N": aps_fpo, "Mu_min_kNm": abs(vu) * 1000 * dv / 1e6}


def run(label):
    out = ROOT / "qa" / "evidence" / "igird_torsion_audit12"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    comparisons = []
    for mu, vu, tu in [(500, 300, 300), (500, 300, 410), (500, 300, 500),
                       (2500, 300, 410), (2500, 300, 450), (2500, 300, 500),
                       (5000, 300, 410), (0, 300, 410)]:
        state = hypothetical_state()
        demand = _demand(x=10, mux=mu, vu=vu, tu=tu)
        # check() owns the calculated interface-shear gate for this QA model.
        combined = physical(check(state, x=10, mux=mu, vu=vu, tu=tu))
        torsion = ap._beam_uls_torsion_check_dataframe(state, demand, strength_route=_route()).iloc[0]
        expected = reference(torsion, mu=mu, vu=vu, tu=tu)
        fields = {"label": label, "scope": "hypothetical composite I; girder torsion cage",
            "Mu": mu, "Vu": vu, "Tu": tu, "Ao_mm2": torsion["Ao mm2"],
            "ph_mm": torsion["ph mm"], "dv_mm": torsion["dv mm"],
            "actual_phiTn_kNm": torsion["φTn kN-m"],
            "actual_theta_deg": torsion["θ deg"], "actual_eps": torsion["εs raw"],
            "combined_status": combined["Status"],
            "combined_stress_dc": combined.get("Stress D/C value"),
            "combined_transverse_dc": combined.get("Transverse D/C value"),
            "combined_longitudinal_dc": combined.get("Longitudinal D/C value"),
            "combined_overall_dc": combined.get("Overall D/C value"),
            **expected}
        fields["Tn_difference_pct"] = 100 * (fields["actual_phiTn_kNm"] / expected["phiTn_kNm"] - 1)
        points=[(p.x,p.y) for p in state["section_geometry"].outer_polygon]
        acp,pcp=polygon_metrics(points)
        ao,_=polygon_metrics(independent_inset(points,0.5*acp/pcp))
        _,ph=polygon_metrics(independent_inset(points,40+16/2))
        fields.update(independent_Acp_mm2=acp,independent_pc_mm=pcp,
            independent_Ao_mm2=ao,independent_ph_mm=ph)
        for name,actual,ref in [("Acp",torsion["Acp mm2"],acp),
            ("pc",torsion["Pcp mm"],pcp),("Ao",fields["Ao_mm2"],ao),("ph",fields["ph_mm"],ph)]:
            assert math.isclose(actual,ref,rel_tol=2e-9,abs_tol=1e-8),(name,actual,ref)
            comparisons.append({"Mu":mu,"Tu":tu,"quantity":name,"actual":actual,"reference":ref,
                "relative_error":abs(actual-ref)/max(abs(ref),1)})
        # Independent transverse and longitudinal equations at direct theta.
        fc, bv = float(combined["f'c MPa"]), float(combined["bw mm"])
        c_dv = float(combined["dv mm"])
        vc = 0.0316 * expected["beta"] * math.sqrt(fc / KSI) * (bv / INCH) * (c_dv / INCH) * KIP
        cot = 1 / math.tan(math.radians(expected["theta_deg"]))
        fy, phi = float(combined["fy MPa"]), float(combined["φ"])
        ats_req = abs(tu) * 1e6 / (phi * 2 * fields["Ao_mm2"] * fy * cot)
        avs = float(combined["Provided transverse mm2/mm"])
        shear_req = max(0, (abs(vu) * 1000 / phi - vc) / (fy * c_dv * cot))
        transverse = max(shear_req, float(combined["Minimum transverse req mm2/mm"])) + 2 * ats_req
        vs = min(max(0, avs - 2 * ats_req) * fy * c_dv * cot, abs(vu) * 1000 / phi)
        rhs = abs(mu) * 1e6 / (phi * c_dv) + cot * math.hypot(abs(vu) * 1000 / phi - 0.5 * vs,
            0.45 * fields["ph_mm"] * abs(tu) * 1e6 / (2 * fields["Ao_mm2"] * phi))
        fields.update(reference_transverse_dc=transverse / avs,
            reference_longitudinal_dc=rhs / (float(combined["Longitudinal resistance kN"]) * 1000),
            reference_shear_cap_dc=abs(vu) * 1000 / (phi * .25 * fc * bv * c_dv))
        if label=="corrected":
            for name,actual,ref in [("epsilon",torsion["εs raw"],expected["epsilon_s"]),
                ("theta",torsion["θ deg"],expected["theta_deg"]),
                ("phiTn",torsion["φTn kN-m"],expected["phiTn_kNm"]),
                ("transverse D/C",combined["Transverse D/C value"],fields["reference_transverse_dc"]),
                ("longitudinal D/C",combined["Longitudinal D/C value"],fields["reference_longitudinal_dc"]),
                ("shear cap D/C",combined["Stress D/C value"],fields["reference_shear_cap_dc"])]:
                assert math.isclose(actual,ref,rel_tol=2e-9,abs_tol=1e-8),(name,actual,ref)
                comparisons.append({"Mu":mu,"Tu":tu,"quantity":name,"actual":actual,"reference":ref,
                    "relative_error":abs(actual-ref)/max(abs(ref),1)})
        rows.append(fields)
        print(json.dumps({k: fields[k] for k in ("Mu", "Vu", "Tu", "actual_phiTn_kNm", "phiTn_kNm",
            "Tn_difference_pct", "combined_overall_dc", "reference_transverse_dc", "reference_longitudinal_dc",
            "combined_stress_dc", "reference_shear_cap_dc")}, default=float), flush=True)
    pd.DataFrame(rows).to_csv(out / f"{label}_benchmarks.csv", index=False)
    (out / f"{label}_benchmarks.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=float))
    pd.DataFrame(comparisons).to_csv(out / f"{label}_independent_substitution.csv",index=False)
    if label=="corrected":
        summary={"status":"PASS","scalar_comparisons":len(comparisons),
            "max_relative_error":max(r["relative_error"] for r in comparisons),
            "scope":"8 hypothetical midspan cases; analytic I/hoop inset; direct US-unit equations with developed dv and nominal fps held fixed"}
        (out/"independent_verification.json").write_text(json.dumps(summary,indent=2))
    state = hypothetical_state()
    from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json
    (out / "hypothetical_input_only.json").write_text(project_to_json(project_from_session_state(state)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    run(parser.parse_args().label)

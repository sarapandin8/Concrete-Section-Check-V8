"""Read-only reinforcement sizing from current station results (REBARADVISOR13).

This module never runs a solver, alters loads, or certifies a member. A spacing
estimate must be verified with the existing solver because a new diameter can
change ph, strain, theta, detailing and longitudinal force. All source vectors
and repeated occurrences remain eligible; a selected display case is irrelevant.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

import pandas as pd

TABLE_KEY = "beam_girder_shear_reinforcement_table"
VERSION = "IGIRDER.REBARADVISOR13"
FRAME_KINDS = {"combined_vt_df": "V+T", "torsion_check_df": "Torsion", "shear_check_df": "Shear"}
TOL = 1e-9


@dataclass(frozen=True)
class Options:
    # A user-selected trial constructibility screen, not a code minimum.
    minimum_spacing_mm: float = 50.0
    spacing_step_mm: float = 10.0
    larger_diameters_mm: tuple = (16.0, 20.0, 25.0, 32.0)

    def validate(self):
        if not all(math.isfinite(v) and v > 0 for v in
                   (self.minimum_spacing_mm, self.spacing_step_mm, *self.larger_diameters_mm)):
            raise ValueError("Trial spacing and diameters must be finite and positive.")


@dataclass
class Proposal:
    zones: pd.DataFrame
    layout: pd.DataFrame
    actions: pd.DataFrame
    issues: pd.DataFrame
    complete_combined: bool
    can_verify: bool


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def station(row):
    value = row.get("Governing x")
    numeric = number(value)
    if math.isfinite(numeric):
        return numeric
    match = re.fullmatch(r"\s*([-+\d.eE]+)\s*m\s*", str(value))
    return number(match.group(1)) if match else float("nan")


def _active(value):
    return str(value).strip().lower() in {"true", "yes", "1"}


def active_zones(layout):
    table = pd.DataFrame(layout).copy(deep=True)
    if "Active" not in table:
        return table.iloc[0:0]
    return table.loc[table["Active"].map(_active)]


def _diameter(zone):
    value = number(zone.get("Diameter_mm"))
    if math.isfinite(value) and value > 0:
        return value
    return number(str(zone.get("Bar Size", "")).upper().removeprefix("DB"))


def _provided(zone):
    diameter, legs, spacing = _diameter(zone), number(zone.get("Legs")), number(zone.get("Spacing_mm"))
    if not all(math.isfinite(v) and v > 0 for v in (diameter, legs, spacing)):
        return float("nan")
    return math.pi * diameter**2 / 4 * legs / spacing


def _label(diameter, spacing):
    return f"DB{diameter:g} @{spacing:g} mm"


def _zone_for(row, zones):
    x = station(row)
    if not math.isfinite(x):
        return None
    covered = zones.loc[(pd.to_numeric(zones["x_start_m"], errors="coerce") <= x + TOL)
                        & (pd.to_numeric(zones["x_end_m"], errors="coerce") >= x - TOL)]
    named = covered.loc[covered["Zone"].astype(str).eq(str(row.get("Zone", "")))]
    if len(named) == 1:
        return named.index[0]
    # Adjacent boundary stations use the accepted solver's stable earlier-zone
    # precedence. Unknown explicit zone names are never reassigned silently.
    if str(row.get("Zone", "-")) not in {"-", "", "nan", "None"}:
        return None
    return covered.sort_values(["x_start_m", "x_end_m"], kind="stable").index[0] if len(covered) else None


def records(results):
    for member, result in results.items():
        for key, kind in FRAME_KINDS.items():
            frame = result.get(key) if isinstance(result, dict) else None
            if not isinstance(frame, pd.DataFrame):
                continue
            for row in frame.to_dict("records"):
                if str(row.get("Station type", "")).upper() == "DIAGRAM BOUNDARY":
                    continue
                yield member, kind, row


def _requirement(kind, row, zone):
    """Physical Av/s equivalent and separately applicable spacing cap."""
    if kind == "V+T":
        q = number(row.get("Combined transverse req mm2/mm"))
        if not math.isfinite(q):
            q = number(row.get("Governing transverse req mm2/mm"))
        if row.get("Transverse status") == "NOT REQUIRED":
            q = 0.0
        dc = number(row.get("Transverse D/C value"))
        return q, number(row.get("s max mm")), dc
    if kind == "Torsion":
        if row.get("Threshold status") == "BELOW THRESHOLD":
            return 0.0, float("nan"), 0.0
        if row.get("Threshold status") != "DESIGN REQUIRED":
            return float("nan"), float("nan"), float("nan")
        # At is one hoop leg even when more shear-effective legs are present.
        q = number(row.get("Torsion At/s req mm2/mm")) * number(zone.get("Legs"))
        return q, number(row.get("s max torsion mm")), number(row.get("At D/C", row.get("D/C value")))
    provided = number(row.get("Av/s mm2/mm"))
    phi_vs, phi_vc = number(row.get("φVs kN")), number(row.get("φVc kN"))
    demand, phi, vp = number(row.get("Abs demand kN")), number(row.get("φ")), number(row.get("Vp kN"))
    # Algebra of the reported Vc+Vs+Vp capacities; Av/s required in the shear
    # table itself is the minimum steel requirement, not total force demand.
    if all(math.isfinite(v) for v in (provided, phi_vs, phi_vc, demand, phi, vp)):
        residual = max(0.0, demand - phi_vc - phi * vp)
        strength_q = provided * residual / phi_vs if phi_vs > 0 else (0.0 if residual == 0 else float("nan"))
    else:
        strength_q = float("nan")
    minimum = number(row.get("Av/s required mm2/mm"))
    q = max(strength_q, minimum) if all(math.isfinite(v) for v in (strength_q, minimum)) else float("nan")
    return q, number(row.get("s max mm")), number(row.get("Strength D/C value"))


def _candidate(zone, required, spacing_cap, options):
    diameter, spacing, legs = _diameter(zone), number(zone.get("Spacing_mm")), number(zone.get("Legs"))
    cap = min(spacing, spacing_cap) if math.isfinite(spacing_cap) else spacing
    if _provided(zone) + 1e-12 >= required and spacing <= cap + TOL:
        return diameter, spacing, "KEEP"
    for db in sorted({diameter, *(d for d in options.larger_diameters_mm if d > diameter)}):
        limit = min(cap, math.pi * db**2 / 4 * legs / required) if required > 0 else cap
        proposed = math.floor((limit + 1e-8) / options.spacing_step_mm) * options.spacing_step_mm
        if proposed + TOL >= options.minimum_spacing_mm:
            return db, proposed, "TRIAL — ลดระยะปลอก" if db == diameter else "TRIAL — เพิ่มขนาดปลอก"
    return float("nan"), float("nan"), "LAYOUT REVIEW"


def _issue(member, row, zone, issue, action, ratio=float("nan"), status="REVIEW"):
    return {"Girder": member, "Zone": zone, "Issue": issue, "Status": status,
            "x m": station(row), "Case": row.get("Case", "-"), "Source row": row.get("Source row", row.get("Source row set", "-")),
            "Tension face": row.get("Tension face", "-"), "D/C": ratio, "Required action": action}


def remaining_issues(results):
    """Actions that stirrup sizing alone cannot certify, with full row audit."""
    issues = []
    seen = set()
    for member, kind, row in records(results):
        zone = str(row.get("Zone", "-"))
        candidates = []
        if kind == "V+T":
            dc = number(row.get("Longitudinal D/C value"))
            dominance = row.get("Prestress dominance status") == "FAIL"
            if math.isfinite(dc) and dc > 1 + TOL:
                deficit = max(0.0, number(row.get("Longitudinal required kN")) - number(row.get("Longitudinal resistance kN")))
                candidates.append(("Longitudinal force", f"แรงตามยาวด้าน {row.get('Tension face', '-')} ขาด {deficit:.1f} kN; ปรับเหล็กตามยาวที่พัฒนากำลังได้/strand แล้วคำนวณ εs, fps และเงื่อนไข Aps·fps > As·fy พร้อมกัน", dc, "FAIL"))
            if dominance:
                candidates.append(("Pretensioned steel condition", "ตรวจด้านรับแรงดึง ตำแหน่ง strand และระยะ transfer/development/debonding ตามแบบ; ต้องมี Aps·fps > As·fy การเพิ่ม As ต้องตรวจเงื่อนไขนี้ใหม่", float("nan"), "FAIL"))
            stress = number(row.get("Stress D/C value"))
            if stress > 1 + TOL:
                candidates.append(("Concrete shear limit", "ปรับความกว้างเอว bw / effective depth dv / กำลังคอนกรีต หรือแรงที่กระทำ; การเพิ่มปลอกอย่างเดียวไม่แก้ขีดจำกัดคอนกรีต", stress, "FAIL"))
            if row.get("Conservative Veff guard status") == "REVIEW":
                candidates.append(("Additional Veff screen", "ตรวจ compression screen เพิ่มเติมตาม calculation trace; เป็นรายการ REVIEW แยกจาก code Stress D/C", number(row.get("Conservative Veff guard D/C")), "REVIEW"))
            for field, issue, action in (
                ("Development status", "Longitudinal development", "ระบุ/ตรวจระยะพัฒนากำลังและ anchorage ของเหล็กคานและ deck จากแบบจริง แล้วคำนวณใหม่"),
                ("Corner longitudinal status", "Hoop corner bars", "จัด/ตรวจเหล็กตามยาวหรือ tendon ที่ทุกมุมของปลอกปิดและยืนยันจากแบบจริง"),
                ("Perimeter longitudinal status", "Hoop perimeter bars", "จัด/ตรวจการกระจายเหล็กตามยาวรอบปลอกปิดและระยะตามข้อกำหนด แล้วตรวจแรงตามยาวใหม่"),
                ("Calculation status", "Incomplete calculation", "เติมข้อมูลที่ขาดตาม calculation trace ก่อนใช้ผลเป็นกำลังต้านทาน"),
            ):
                value = row.get(field)
                allowed = {"PASS", "CONFIRMED", "NOT REQUIRED", "COMPLETE"}
                if value and value not in allowed:
                    candidates.append((issue, action, float("nan"), "REVIEW"))
            if "negative composite flexure certification" in str(row.get("Review reason", "")):
                candidates.append(("Negative composite route", "ตรวจและยืนยันหน้าตัด composite ด้านแรงดึงบนและการพัฒนากำลัง deck; ผล force check อย่างเดียวไม่ยืนยัน negative composite flexure", float("nan"), "REVIEW"))
        if kind == "Shear":
            demand, limit = number(row.get("Abs demand kN")), number(row.get("φVn limit kN"))
            # Vn limit D/C reports uncapped *resistance* / concrete cap. A
            # capped resistance does not by itself mean the demand fails.
            if math.isfinite(demand) and limit > 0 and demand / limit > 1 + TOL:
                candidates.append(("Concrete shear limit", "ปรับ bw / dv / กำลังคอนกรีต หรือแรงที่กระทำ แล้วตรวจขีดจำกัด Vn ใหม่", demand / limit, "FAIL"))
        for field, issue, action, allowed in (
            ("Source coupling", "Force concurrency", "ตรวจชุด Mu, Nu, Vu, Tu ที่เกิดพร้อมกันจาก case/step/ตำแหน่งเดียวกัน และหลักฐาน CSI source; envelope ยังเป็น REVIEW", {"CONCURRENT — DECLARED", "CONCURRENT — PASS", "CONCURRENT", "PASS"}),
            ("Composite action status", "Girder–deck interface", "ตรวจ interface shear และข้อมูลการทำงานร่วมกันของ girder–deck ให้ครบ แล้ว Calculate สำหรับ inputs ปัจจุบัน", {"PASS", "NOT APPLICABLE"}),
            ("Depth source status", "Effective depth source", "ตรวจที่มาของ d/dv และข้อมูล composite/development ใน Depth note แล้วคำนวณใหม่", {"PASS", "NOT APPLICABLE"}),
            ("Coverage status", "Stirrup coverage", "จัดช่วงปลอกให้ครอบคลุมตำแหน่งที่ต้องออกแบบและตรวจปลอกปิด/135° hook จากแบบจริง", {"PASS", "COVERED", "NOT REQUIRED", "CONFIRMED"}),
            ("Hoop detailing status", "Closed hoop detailing", "ใช้ปลอกปิดและรายละเอียด anchorage/135° hook ที่ผ่านข้อกำหนด พร้อมข้อมูลกรงปลอกจริง", {"PASS", "NOT REQUIRED", "CONFIRMED"}),
        ):
            value = row.get(field)
            if value and str(value) not in {"-", "nan"} and value not in allowed:
                candidates.append((issue, action, float("nan"), "FAIL" if value == "FAIL" else "REVIEW"))
        for issue, action, ratio, status in candidates:
            # Duplicate representations of the same physical vector in shear,
            # torsion and V+T are grouped for action display, never for sizing.
            token = (member, zone, issue, str(row.get("Case")), str(row.get("Governing x")), str(row.get("Source row", row.get("Source row set"))), str(row.get("Tension face")))
            if token not in seen:
                issues.append(_issue(member, row, zone, issue, action, ratio, status))
                seen.add(token)
    return pd.DataFrame(issues)


def action_summary(issues):
    if issues.empty:
        return pd.DataFrame()
    rows = []
    for (member, zone, issue, status), group in issues.groupby(["Girder", "Zone", "Issue", "Status"], sort=False):
        finite = group.loc[pd.to_numeric(group["D/C"], errors="coerce").notna()]
        gov = finite.sort_values("D/C", ascending=False, kind="stable").iloc[0] if not finite.empty else group.iloc[0]
        rows.append({"Girder": member, "Zone": zone, "Issue": issue, "Status": status,
                     "Affected rows": len(group), "Governing x m": gov["x m"], "D/C": gov["D/C"],
                     "Case": gov["Case"], "Required action": gov["Required action"]})
    return pd.DataFrame(rows).sort_values("Status", kind="stable").reset_index(drop=True)


def recommend(layout, results, *, options=Options()):
    options.validate()
    proposed = pd.DataFrame(layout).copy(deep=True)
    zones = active_zones(proposed)
    complete = bool(results) and all(isinstance(r.get("combined_vt_df"), pd.DataFrame) and not r["combined_vt_df"].empty for r in results.values())
    issues = remaining_issues(results)
    if zones.empty or not {"Zone", "x_start_m", "x_end_m"}.issubset(zones):
        return Proposal(pd.DataFrame(), proposed, action_summary(issues), issues, complete, False)
    data = {i: [] for i in zones.index}
    missing = {i: [] for i in zones.index}
    unmapped = []
    for member, kind, row in records(results):
        i = _zone_for(row, zones)
        if i is None:
            unmapped.append(f"{member}: {row.get('Case', '-')} @ {row.get('Governing x', '-')}")
            continue
        q, cap, dc = _requirement(kind, row, zones.loc[i])
        if not math.isfinite(q) or q < 0:
            missing[i].append(f"{member} · {kind} · {row.get('Case', '-')} @ {row.get('Governing x', '-')}")
            continue
        data[i].append({"q": q, "cap": cap, "dc": dc, "kind": kind, "member": member, "row": row})
    summaries = []
    for i, zone in zones.iterrows():
        db, spacing = _diameter(zone), number(zone.get("Spacing_mm"))
        supplied = _provided(zone)
        start, end = number(zone.get("x_start_m")), number(zone.get("x_end_m"))
        invalid = not all(math.isfinite(v) and v > 0 for v in (db, spacing, supplied, number(zone.get("fy_MPa")))) or not all(math.isfinite(v) for v in (start, end)) or end <= start
        duplicate = zones["Zone"].astype(str).eq(str(zone["Zone"])).sum() > 1
        overlap = any(j != i and max(start, number(other["x_start_m"])) < min(end, number(other["x_end_m"])) - TOL for j, other in zones.iterrows())
        entries = data[i]
        gov = max(entries, key=lambda entry: entry["q"]) if entries else None
        required = gov["q"] if gov else float("nan")
        caps = [entry["cap"] for entry in entries if math.isfinite(entry["cap"]) and entry["cap"] > 0]
        cap = min(caps) if caps else float("nan")
        if invalid or duplicate or overlap or missing[i] or not entries:
            trial_db, trial_s, action = float("nan"), float("nan"), "DATA REQUIRED"
        else:
            trial_db, trial_s, action = _candidate(zone, required, cap, options)
        if math.isfinite(trial_s):
            proposed.loc[i, ["Bar Size", "Diameter_mm", "Spacing_mm"]] = [f"DB{trial_db:g}", trial_db, trial_s]
        failed = [e for e in entries if e["dc"] > 1 + TOL or number(e["row"].get("Spacing D/C")) > 1 + TOL or number(e["row"].get("Av/s min D/C")) > 1 + TOL]
        xs = sorted({station(e["row"]) for e in failed if math.isfinite(station(e["row"]))})
        maxima = {kind: max([e["dc"] for e in entries if e["kind"] == kind and math.isfinite(e["dc"])], default=float("nan")) for kind in FRAME_KINDS.values()}
        reason = ("Invalid/duplicate/overlapping zone" if invalid or duplicate or overlap else
                  (f"Missing transverse data: {len(missing[i])} rows" if missing[i] else
                   ("No calculated rows in this zone" if not entries else "All stored cases; apply trial to entire existing zone")))
        trial_q = math.pi * trial_db**2 / 4 * number(zone.get("Legs")) / trial_s if math.isfinite(trial_s) else float("nan")
        summaries.append({"Zone": zone["Zone"], "x start m": start, "x end m": end,
                          "Current": _label(db, spacing), "Proposed trial": _label(trial_db, trial_s) if math.isfinite(trial_s) else "—",
                          "Action": action, "Required transverse mm2/mm": required, "Current transverse mm2/mm": supplied,
                          "Estimated transverse D/C": required / trial_q if trial_q > 0 else float("nan"),
                          "Before φTn D/C": maxima["Torsion"], "Before V+T transverse D/C": maxima["V+T"],
                          "Governing girder": gov["member"] if gov else "—", "Governing x m": station(gov["row"]) if gov else float("nan"),
                          "Governing case": gov["row"].get("Case", "—") if gov else "—",
                          "Failed sampled x m": ", ".join(f"{x:g}" for x in xs) or "—",
                          "Sizing rows": len(entries), "Missing rows": len(missing[i]), "Scope": reason})
    summaries = pd.DataFrame(summaries)
    feasible = not summaries.empty and not summaries["Action"].isin(["DATA REQUIRED", "LAYOUT REVIEW"]).any() and not unmapped
    if unmapped:
        summaries["Scope"] = summaries["Scope"].astype(str) + f"; {len(unmapped)} unmapped station rows — check coverage"
    return Proposal(summaries, proposed, action_summary(issues), issues, complete, feasible)


def trial_summary(results):
    """Exact solver ratios; overall row status is retained independently."""
    rows = []
    for member, result in results.items():
        group = {}
        for key, columns in (
            ("torsion_check_df", (("φTn D/C", "At D/C"), ("Torsion spacing D/C", "Spacing D/C"))),
            ("combined_vt_df", (("V+T transverse D/C", "Transverse D/C value"), ("Longitudinal D/C", "Longitudinal D/C value"), ("Stress D/C", "Stress D/C value"), ("Spacing D/C", "Spacing D/C"))),
            ("shear_check_df", (("Shear strength D/C", "Strength D/C value"), ("Shear minimum D/C", "Av/s min D/C"))),
        ):
            frame = result.get(key)
            if not isinstance(frame, pd.DataFrame):
                continue
            for row in frame.to_dict("records"):
                if str(row.get("Station type", "")).upper() == "DIAGRAM BOUNDARY":
                    continue
                zone = str(row.get("Zone", "-"))
                if zone == "-" and key == "torsion_check_df" and row.get("Threshold status") == "BELOW THRESHOLD":
                    continue
                summary = group.setdefault(zone, {"Girder": member, "Zone": zone, "V+T rows": 0, "FAIL rows": 0, "REVIEW rows": 0, "Sizing data missing": False})
                if key == "combined_vt_df":
                    summary["V+T rows"] += 1
                    summary["FAIL rows"] += row.get("Status") == "FAIL"
                    summary["REVIEW rows"] += row.get("Status") != "PASS" and row.get("Status") != "FAIL"
                    if row.get("Transverse status") != "NOT REQUIRED" and not math.isfinite(number(row.get("Transverse D/C value"))):
                        summary["Sizing data missing"] = True
                for label, column in columns:
                    value = number(row.get(column))
                    if math.isfinite(value):
                        summary[label] = max(number(summary.get(label)) if label in summary else -math.inf, value)
            
        for summary in group.values():
            values = [number(summary.get(c)) for c in ("φTn D/C", "V+T transverse D/C", "Spacing D/C", "Torsion spacing D/C", "Shear strength D/C", "Shear minimum D/C")]
            finite = [v for v in values if math.isfinite(v)]
            summary["Transverse verification"] = ("DATA REQUIRED" if summary["Sizing data missing"] or not finite else
                ("MEETS NUMERIC CHECKS" if max(finite) <= 1 + TOL else "FAIL"))
            summary["Overall V+T"] = "FAIL" if summary["FAIL rows"] else ("REVIEW" if summary["REVIEW rows"] else ("PASS" if summary["V+T rows"] else "NOT AVAILABLE"))
            rows.append(summary)
    return pd.DataFrame(rows)

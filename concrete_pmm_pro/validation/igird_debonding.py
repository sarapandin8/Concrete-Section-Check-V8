"""AASHTO 9th Edition I-Girder debonding detailing screens, not certification.

Source: supplied Section 5 (2020), 5.9.4.3.3(A-I), printed pp. 5-144–145.
This module reads layout inputs only. It never changes strands or solver forces.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping

import pandas as pd

from concrete_pmm_pro.serviceability.girder_prestress_station import (
    DEBONDING_RULE_AUDIT_COLUMNS, active_girder_strand_rows,
    debonded_strand_numbers_for_row,
)

VERSION = "IGIRDER.DBQA1.aashto9-detailing-screen"
BASIS = "AASHTO LRFD 9th Edition · 5.9.4.3.3"


def _number(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def debonding_status(audit: pd.DataFrame, *, layout_errors=(), layout_warnings=()) -> str:
    statuses = set(audit.get("Status", []))
    if layout_errors or "ERROR" in statuses:
        return "ERROR"
    if "FAIL" in statuses:
        return "FAIL"
    if layout_warnings or "REVIEW" in statuses:
        return "REVIEW"
    return "OK"


def igird_debonding_audit(
    table, *, span_length_m: float, section_parameters: Mapping,
    points: pd.DataFrame,
) -> pd.DataFrame:
    """Read actual strand coordinates; separate bad inputs, FAIL, and REVIEW.

    Coordinates come from the existing production layout generator. The 45%
    limit applies to a physical horizontal row, so split groups at one y-level
    are counted together. Unknown geometry/diameter never receives an OK.
    Development and service-tension applicability are not inferred from Pe.
    """
    records = []

    def add(rule, status, demand, limit, note):
        records.append(dict(zip(DEBONDING_RULE_AUDIT_COLUMNS,
            (rule, status, demand, limit, f"{BASIS}: {note}"))))

    span = _number(span_length_m)
    if span is None or span <= 0:
        add("Span input", "ERROR", str(span_length_m), "finite L > 0", "Correct the span input.")
        return pd.DataFrame(records, columns=DEBONDING_RULE_AUDIT_COLUMNS)
    active = active_girder_strand_rows(table)
    groups = [str(row.get("Group ID") or "strand group") for row in active]
    if not active or len(set(groups)) != len(groups):
        add("Layout source", "ERROR", f"{len(active)} active groups", "active, unique Group IDs", "Define a unique ID for every active group.")
        return pd.DataFrame(records, columns=DEBONDING_RULE_AUDIT_COLUMNS)

    horizontal = defaultdict(lambda: [0, 0])
    terminations = defaultdict(list)
    position_rows = defaultdict(list)
    lengths = []
    invalid = []
    asymmetry = []
    diameter_missing = False
    for row, group in zip(active, groups):
        count = _number(row.get("No. Strands"))
        y = _number(row.get("y_mm_from_bottom"))
        left = _number(row.get("Left debond m"))
        right = _number(row.get("Right debond m"))
        if count is None or count <= 0 or count != int(count) or y is None or y < 0 or left is None or right is None or min(left, right) < 0 or left + right >= span:
            invalid.append(group)
            continue
        # A selection with zero sleeve length is not physically debonded.
        selected = set(debonded_strand_numbers_for_row(row)) if max(left, right) > 0 else set()
        key = round(y, 6)
        horizontal[key][0] += int(count)
        horizontal[key][1] += len(selected)
        group_points = points[points["Group ID"].astype(str) == group] if "Group ID" in points else pd.DataFrame()
        if len(group_points) != int(count):
            invalid.append(f"{group} coordinates")
            continue
        for p in group_points.to_dict("records"):
            x = _number(p.get("x_mm"))
            strand_no = int(p.get("Strand no.", 0))
            db = _number(p.get("Diameter mm"))
            if x is None or strand_no < 1 or strand_no > count:
                invalid.append(f"{group} coordinates")
                continue
            if db is None or db <= 0:
                diameter_missing = True
            position_rows[key].append((x, strand_no in selected, group, strand_no, db))
        if selected:
            lengths.append((group, left, right))
            if abs(left - right) > 1e-6:
                asymmetry.append(group)
            for distance in (left, span - right):
                if 0 < distance < span:
                    # A sleeve exists only at a nonzero-debonded end.
                    if (distance == left and left > 0) or (distance == span - right and right > 0):
                        terminations[round(distance, 6)].extend(
                            (group, n, max((p[4] or 0) for p in position_rows[key])) for n in selected
                        )
    add("Input layout", "ERROR" if invalid else "OK", ", ".join(invalid) or "finite inputs and strand coordinates", "valid span, counts, positions and bonded zone", "Input validity is separate from detailing compliance.")
    if invalid:
        return pd.DataFrame(records, columns=DEBONDING_RULE_AUDIT_COLUMNS)

    total = sum(v[0] for v in horizontal.values())
    debonded = sum(v[1] for v in horizontal.values())
    bad_rows = [f"y={y:g} mm: {n}/{count}={n/count:.1%}" for y, (count, n) in sorted(horizontal.items()) if n/count > .45 + 1e-9]
    add("Per-row debonded ratio — A", "FAIL" if bad_rows else "OK",
        "; ".join(f"y={y:g}: {n}/{count}={n/count:.1%}" for y, (count, n) in sorted(horizontal.items())),
        "≤ 45% per physical horizontal row unless Owner approves", "No Owner exception is assumed.")
    add("Total debonded ratio — I trigger", "INFO", f"{debonded}/{total} = {debonded/total:.1%}",
        "25% triggers web-strand bonding; not an overall rejection limit", "The former generic 25%/40% screens are not the 9th Edition I-Girder limits.")
    cap = 4 if debonded <= 10 else 6
    add("Strands terminating per section — B", "FAIL" if any(len(v) > cap for v in terminations.values()) else "OK",
        "; ".join(f"x={x:g} m: {len(v)} strands" for x, v in sorted(terminations.items())) or "no sleeves",
        f"≤ {cap} strands per termination section", "Count individual strands across all groups at the same station.")
    stations = sorted(terminations)
    gaps = [(b-a, max(p[2] for p in terminations[a] + terminations[b])) for a, b in zip(stations, stations[1:])]
    gap_fail = any(gap*1000 < 60*db-1e-6 for gap, db in gaps)
    add("Termination spacing — C", "REVIEW" if diameter_missing and gaps else ("FAIL" if gap_fail else "OK"),
        f"minimum spacing {min(g[0] for g in gaps):.3f} m" if gaps else "no adjacent termination sections",
        "≥ 60db; use larger adjacent strand diameter", "Strand diameter must be known to close this screen.")
    symmetry = []
    adjacent = []
    web_hits = []
    outer_hits = []
    web_top = _number(section_parameters.get("T1_mm"))
    web_bottom = _number(section_parameters.get("T2_mm"))
    web = max(web_top, web_bottom) if web_top and web_bottom else None
    bottom_width = _number(section_parameters.get("B2_mm"))
    bottom_flange = _number(section_parameters.get("D5_mm"))
    top_flange = _number(section_parameters.get("D2_mm"))
    depth = _number(section_parameters.get("D1_mm"))
    web_required = debonded/total > .25 + 1e-9 or (web and bottom_width and bottom_width/web > 4 + 1e-9)
    geometry_known = all(v is not None and v > 0 for v in (web, bottom_width, bottom_flange, top_flange, depth))
    for y, raw in sorted(position_rows.items()):
        ps = sorted(raw)
        for x, is_debonded, group, n, db in ps:
            if is_debonded and not any(abs(other[0]+x) < 1e-6 and other[1] for other in ps):
                symmetry.append(f"{group} #{n}")
            if is_debonded and web and abs(x) <= web/2 + 1e-6 and web_required:
                web_hits.append(f"{group} #{n} (x={x:g} mm)")
        for p, q in zip(ps, ps[1:]):
            if p[1] and q[1]:
                adjacent.append(f"horizontal y={y:g}: {p[2]} #{p[3]}/{q[2]} #{q[3]}")
        full_flange = geometry_known and (y <= bottom_flange+1e-6 or y >= depth-top_flange-1e-6)
        if full_flange:
            outer_hits.extend(f"{p[2]} #{p[3]}" for p in (ps[0], ps[-1]) if p[1])
    row_levels = sorted(position_rows)
    for y1, y2 in zip(row_levels, row_levels[1:]):
        for p in position_rows[y1]:
            for q in position_rows[y2]:
                if abs(p[0]-q[0]) < 1e-6 and p[1] and q[1]:
                    adjacent.append(f"vertical x={p[0]:g}: {p[2]} #{p[3]}/{q[2]} #{q[3]}")
    add("Symmetric distribution and termination — D", "FAIL" if symmetry or asymmetry else "OK", "; ".join(symmetry+asymmetry) or "symmetric about member centerline and at both ends", "symmetric strand pairs and terminations", "Individual paired strand coordinates are checked.")
    add("Alternating bonded/debonded positions — E", "FAIL" if adjacent else "REVIEW",
        "; ".join(adjacent) or "no adjacent debonded positions detected", "alternate horizontally and vertically", "Aligned adjacent rows are screened; staggered or irregular arrangements require drawing review.")
    add("Web projection strands fully bonded — I", "REVIEW" if not geometry_known else ("FAIL" if web_hits else "OK"),
        "; ".join(web_hits) or f"web width {web} mm; trigger {'active' if web_required else 'inactive'}", "all web-projection strands bonded if total >25% or bf/bw >4", "Uses actual x coordinates about the girder centerline.")
    add("Outer-most flange strands bonded — I", "REVIEW" if not geometry_known else ("FAIL" if outer_hits else "OK"),
        "; ".join(outer_hits) or "outer-most strands bonded in full-width flange rows", "bond outer-most strand at each side of each full-width flange row", "Rows in haunch/web regions are not misclassified as full-width flange rows.")
    max_length = max((max(left, right) for _, left, right in lengths), default=0)
    long_groups = ", ".join(group for group, left, right in lengths if max(left, right) > .20*span+1e-9)
    add("Debond length recommendation — G", "REVIEW" if debonded else "NOT REQUIRED",
        f"max L/R = {max_length:.3f} m; 0.20L = {span*.20:.3f} m; exceeding row(s): {long_groups or 'none'}", "recommended ≤ min(0.20L, 0.5L − ld)",
        "Exceeding the 20% recommendation requires engineering review, not an input ERROR. Verified strand ld is required for the second bound.")
    add("Development / strength handoff — F, I", "REVIEW" if debonded else "NOT REQUIRED",
        "verified strand development and service-tension applicability required" if debonded else "no sleeves",
        "review κ=2 where applicable; 5.7.3.5 longitudinal resistance; locate debonded strands furthest from centerline",
        "These requirements are not certified by this layout-only screen. Prestress, ULS and SLS calculations retain their existing force models.")
    return pd.DataFrame(records, columns=DEBONDING_RULE_AUDIT_COLUMNS)

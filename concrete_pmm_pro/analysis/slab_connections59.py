"""Engineer-selected connection-node exclusions, independent of action size.

Nodes on imported girder/diaphragm centre lines and the engineer-selected
deck-end-to-bearing zones are excluded. The 20 µm coordinate tolerance is
not an additional physical buffer. Retained source actions are unchanged.
The AASHTO deck negative-moment section is a separate location reference, not
an exemption for shell N/M/V or certification of a railway slab design.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from concrete_pmm_pro.analysis.igird_shear_support import support_settings

TOLERANCE = 2e-5  # m, original CSI coordinate export tolerance
INCLUDED = "Design included"
REASON = "Design exclusion"
END_REASON = "Bearing end-zone"
LINE_COLUMNS = ["Connection", "ID", "X1 (m)", "Y1 (m)", "X2 (m)", "Y2 (m)"]


def design_rows(result):
    rows = result["rows"]
    return rows.loc[rows[INCLUDED]] if INCLUDED in rows else rows


def bearing_end_zones(package, geometry, state, direction, *, is_i):
    """Project bearing offsets, measured from the imported single-span ends.

    The stored reference is respected: a centreline offset does not become
    an inside face when bearing length is unknown. Boundaries are inclusive.
    This is an engineer-selected review scope, not a code shear exemption.
    """
    settings = support_settings(state)
    result = {"active":False, "zones":[], "polygons":[], "reference":settings['offset_reference'],
              "source":"Existing project bearing settings", "notes":[]}
    if not is_i or not settings['locations_confirmed']:
        return result
    flags = package.tables['flags']
    slabs = flags.loc[flags['CompType'].astype(str).str.strip().str.casefold().eq('top slab')]
    if len(slabs[['BridgeObj','BOSpan']].drop_duplicates()) != 1:
        raise ValueError('Bearing end-zone offsets require one imported bridge/span; the project offsets cannot be applied to multiple spans')
    points = geometry.corners[['X (m)','Y (m)']].to_numpy(float)
    normal = np.array([-direction[1], direction[0]])
    station = points @ direction
    origin, last = float(station.min()), float(station.max())
    span = last-origin
    left, right = settings['left_offset_m'], settings['right_offset_m']
    reference = settings['offset_reference']
    if (reference not in ('centerline','inside_face') or left is None or right is None or
            span <= 0 or left+right >= span):
        raise ValueError('Existing project bearing offsets/reference are invalid for the imported slab length')
    low, high = float((points @ normal).min()), float((points @ normal).max())
    zones, polygons = [], []
    for side, start, end in [('Left',0.,left),('Right',span-right,span)]:
        zones.append({'Side':side,'From station (m)':start,'To station (m)':end,
                      'Bearing reference':reference})
        a, b = origin+start, origin+end
        polygon = np.array([a*direction+low*normal, b*direction+low*normal,
                            b*direction+high*normal, a*direction+high*normal])
        polygons.append(polygon.tolist())
    result.update(active=True, zones=zones, polygons=polygons,
                  origin_s_m=origin, longitudinal=direction.tolist(), span_m=span)
    return result


def _merged(lines, kind, longitudinal):
    """Merge contiguous native segments without filling gaps between supports."""
    direction = longitudinal if kind == "Girder" else np.array([-longitudinal[1], longitudinal[0]])
    normal = np.array([-direction[1], direction[0]])
    groups = []
    other = []
    for identifier, a, b in lines:
        if abs((b-a) @ normal) > TOLERANCE:
            other.append((identifier, a, b))
            continue
        offset = float((a+b) @ normal/2)
        group = next((g for g in groups if abs(g[0]-offset) <= TOLERANCE), None)
        if group is None:
            group = [offset, []]
            groups.append(group)
        start, end = sorted((float(a @ direction), float(b @ direction)))
        group[1].append((start, end, identifier))
    output = []
    for offset, intervals in groups:
        current = None
        for start, end, identifier in sorted(intervals):
            if current is None:
                current = [start, end, [identifier]]
            elif start <= current[1]+TOLERANCE:
                current[1] = max(end, current[1]); current[2].append(identifier)
            else:
                output.append((", ".join(current[2]), current[0]*direction+offset*normal,
                               current[1]*direction+offset*normal))
                current = [start, end, [identifier]]
        if current is not None:
            output.append((", ".join(current[2]), current[0]*direction+offset*normal,
                           current[1]*direction+offset*normal))
    output.extend(other)
    return [{"Connection": kind, "ID": identifier,
             **dict(zip(("X1 (m)", "Y1 (m)", "X2 (m)", "Y2 (m)"), (*a, *b)))}
            for identifier, a, b in output]


def layout(package, geometry, state):
    tables = package.tables
    notes = []
    coordinates = {str(r.Joint): np.array([r.GlobalX, r.GlobalY, r.GlobalZ], float)
                   for r in tables["joints"].itertuples()}
    coordinates.update({str(r.JointElem): np.array([r.GlobalX, r.GlobalY, r.GlobalZ], float)
                        for r in tables["nodes"].itertuples()})
    direction = np.array(next(iter(geometry.parent_axes.values()))["long"][:2])
    direction /= np.linalg.norm(direction)
    params = state.get("section_parameters") or {}
    # Frames in other workflows are not automatically assumed to be I-girders.
    is_i = (state.get("section_preset_key") == "parametric_i_girder" or
            "i-girder" in str(state.get("section_preset_name", "")).casefold())
    frames = tables.get("frames", pd.DataFrame())
    girder = []
    if is_i and frames.empty:
        notes.append("Girder connection geometry is unavailable in this stored import. Reimport the same complete Connectivity Data.xlsx export to read its Connectivity - Frame table.")
    if is_i:
        for row in frames.to_dict("records"):
            if str(row["IsCurved"]).strip().casefold() != "no":
                continue
            if row["JointI"] not in coordinates or row["JointJ"] not in coordinates:
                raise ValueError("Connectivity - Frame: endpoint coordinates missing")
            a, b = coordinates[row["JointI"]], coordinates[row["JointJ"]]
            delta = b[:2]-a[:2]; length = np.linalg.norm(delta)
            if length <= TOLERANCE or abs(delta @ direction)/length < 1-1e-8:
                continue
            girder.append((str(row["Frame"]), a[:2], b[:2]))
    diaphragm = []
    flags = tables["flags"]
    areas = flags.loc[flags["CompType"].astype(str).str.strip().str.casefold().eq("diaphragm"), "Area"]
    parents = tables["parents"].set_index("Area")
    for area in areas:
        if area not in parents.index:
            notes.append(f"Diaphragm {area}: original corner connectivity unavailable; no inferred exclusion.")
            continue
        parent = parents.loc[area]
        joints = [parent.get(f"Joint{i}", "") for i in range(1, int(parent["NumJoints"])+1)]
        if any(j not in coordinates for j in joints):
            raise ValueError(f"Diaphragm {area}: corner coordinates missing")
        points = np.array([coordinates[j][:2] for j in joints])
        distances = np.linalg.norm(points[:, None]-points[None, :], axis=2)
        i, j = np.unravel_index(distances.argmax(), distances.shape)
        a, b = points[i], points[j]; delta = b-a; length = np.linalg.norm(delta)
        if length <= TOLERANCE:
            continue
        normal = np.array([-delta[1], delta[0]])/length
        if np.max(abs((points-a) @ normal)) > TOLERANCE:
            notes.append(f"Diaphragm {area}: not a vertical line in plan; no inferred exclusion.")
            continue
        diaphragm.append((str(area), a, b))
    lines = pd.DataFrame([*_merged(girder, "Girder", direction),
                          *_merged(diaphragm, "Diaphragm", direction)], columns=LINE_COLUMNS)
    flange = float(params.get("B1_mm", 0) or 0)
    flange = flange if math.isfinite(flange) and flange > 0 and is_i else None
    return {"lines": lines, "notes": notes, "tolerance_m": TOLERANCE,
            "top_flange_mm": flange,
            "negative_moment_offset_mm": min(flange/3, 381.) if flange else None,
            "end_zones":bearing_end_zones(package,geometry,state,direction,is_i=is_i),
            "basis": "Engineer-selected exclusions of girder/diaphragm connection nodes and project bearing end zones; retained nodes are not averaged or clipped."}


def annotate(frame, connection_layout):
    """A geometry-only mask: no load level, sign, case or D/C threshold."""
    result = frame.copy()
    points = result[["X (m)", "Y (m)"]].to_numpy(float)
    masks = {kind: np.zeros(len(result), dtype=bool) for kind in ("Girder", "Diaphragm")}
    for line in connection_layout["lines"].to_dict("records"):
        a = np.array([line["X1 (m)"], line["Y1 (m)"]])
        b = np.array([line["X2 (m)"], line["Y2 (m)"]])
        delta = b-a; length = np.linalg.norm(delta); unit = delta/length
        along = (points-a) @ unit
        across = abs((points-a) @ np.array([-unit[1], unit[0]]))
        masks[line["Connection"]] |= ((along >= -TOLERANCE) &
            (along <= length+TOLERANCE) & (across <= TOLERANCE))
    g, d = masks["Girder"], masks["Diaphragm"]
    result[INCLUDED] = ~(g | d)
    result[REASON] = np.select([g & d, g, d],
        ["Girder + diaphragm connection", "Girder connection", "Diaphragm connection"], default="")
    result[END_REASON] = ''
    ends = connection_layout.get('end_zones', {})
    if ends.get('active'):
        station = points @ np.array(ends['longitudinal'])-ends['origin_s_m']
        for zone in ends['zones']:
            mask = ((station >= zone['From station (m)']-TOLERANCE) &
                    (station <= zone['To station (m)']+TOLERANCE))
            reason = zone['Side']+' end to bearing'
            previous = result.loc[mask,REASON]
            result.loc[mask,REASON] = np.where(previous.eq(''), reason, previous+'; '+reason)
            result.loc[mask,END_REASON] = reason
            result.loc[mask,INCLUDED] = False
    return result

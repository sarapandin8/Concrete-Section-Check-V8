"""CSIREF26: source-attached force origins and reversible sectional transport.

All dimensions of a source profile are metres. Analysis geometry is mm.
CSI local 2 is up; section x is local 3 (left-to-right in the CSI section view).
The physical moment vector is (T, -M2, M3). CSI P is tension-positive.
Source rows and units are never rewritten. A transient row can be transported
again to another origin using its retained original actions, without doubling.
This module establishes force equivalence, not composite torsional resistance.
"""
from __future__ import annotations
from collections.abc import Mapping
import csv
import hashlib
from io import BytesIO, StringIO
import json
import math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from concrete_pmm_pro.io.girder_csi_import import SOURCE_TAG, source_info
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.core.models import SectionGeometry

VERSION = "IGIRDER.CSIREF26"
SOURCE_TORSION_POLICY = "IGIRDER.CSITU46.reported-torque"
SETTINGS_KEY = "csi_girder_force_reference"
SNAPSHOT_KEY = "force_reference"
RUNTIME_KEY = "__csi_reference"
BOUNDS_KEY = "__csi_action_bounds"
FIELDS = ("P", "V2", "V3", "T", "M2", "M3")
ULS_MAP = dict(zip(FIELDS, ("Nu", "Vuy", "Vux", "Tu", "Muy", "Mux")))
SLS_MAP = dict(zip(FIELDS, ("N", "Vy", "Vx", "T", "My", "Mx")))


def _finite(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    return value


def canonical_profile(raw):
    if not isinstance(raw, Mapping):
        raise ValueError("CSI force-reference data must be an object.")
    if raw.get("axes", "CSI_GIRDER_LOCAL") != "CSI_GIRDER_LOCAL":
        raise ValueError("This adapter requires native CSI girder-local axes; global section cuts need an explicit rotation adapter.")
    if raw.get("schema") not in {None, VERSION}:
        raise ValueError("Unsupported CSI force-reference schema.")
    depth = _finite(raw.get("depth_below_deck_top_m"), "CSI reporting depth")
    if depth < 0:
        raise ValueError("CSI reporting depth below deck top must be nonnegative.")
    offset = _finite(raw.get("local3_offset_from_web_m", 0), "CSI local-3 offset")
    kind = str(raw.get("force_kind", "GIRDER_COMPOSITE"))
    if kind not in {"GIRDER_COMPOSITE", "BEAM_ONLY"}:
        raise ValueError("Force kind must be GIRDER_COMPOSITE or BEAM_ONLY.")
    result = {"schema": VERSION, "depth_below_deck_top_m": depth,
        "local3_offset_from_web_m": offset, "force_kind": kind,
        "vertical_location": str(raw.get("vertical_location", "CSI reported location")),
        "horizontal_location": "Center of Girder Web" if offset == 0 else "Declared local-3 offset",
        "axes": "CSI_GIRDER_LOCAL", "basis": str(raw.get("basis") or "Entered CSI output location"),
        "section_name": str(raw.get("section_name") or "")}
    for key in ("source_top_y_m", "source_cg_y_m", "reference_table_sha256",
                "bridge_section_area_m2", "structural_polygon_count"):
        if key in raw:
            result[key] = raw[key]
    # Overrides are keyed by the physical CSI member name, not by row order.
    overrides = raw.get("member_overrides") or {}
    if not isinstance(overrides, Mapping):
        raise ValueError("Member reference overrides must be keyed by Girder name.")
    if overrides:
        result["member_overrides"] = {
            str(name): canonical_profile({**result, **values, "member_overrides": {}})
            for name, values in overrides.items()}
    result["profile_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return result


def configured_profile(state):
    meta = state.get("project_metadata") or {}
    raw = meta.get(SETTINGS_KEY) if isinstance(meta, Mapping) else None
    return canonical_profile(raw) if raw is not None else None


def update_source_note(note, updates):
    text = str(note or "")
    if SOURCE_TAG not in text:
        return text
    prefix, encoded = text.split(SOURCE_TAG, 1)
    info, end = json.JSONDecoder().raw_decode(encoded)
    return prefix + SOURCE_TAG + json.dumps(
        {**info, **updates}, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + encoded[end:]


def bind_reference(frame, profile, *, replace=False):
    """Attach an immutable source-origin snapshot; numerical Loads stay raw."""
    result = pd.DataFrame(frame).copy(deep=True)
    if result.empty or profile is None:
        return result
    cfg = canonical_profile(profile)
    for index, row in result.iterrows():
        info = source_info(row)
        if not isinstance(info, Mapping) or "raw_fields" not in info:
            continue
        if SNAPSHOT_KEY in info and not replace:
            continue
        name = str(info.get("girder") or row.get("Girder") or info.get("sheet") or "")
        local = cfg.get("member_overrides", {}).get(name, cfg)
        snapshot = {k: v for k, v in local.items() if k != "member_overrides"}
        result.at[index, "Note"] = update_source_note(row.get("Note"), {SNAPSHOT_KEY: snapshot})
    return result


def actions(row, *, sls=False):
    trace = row.get(RUNTIME_KEY)
    if isinstance(trace, Mapping) and trace.get("mode") != "EXACT":
        return dict(trace["original_actions"])
    mapping = SLS_MAP if sls else ULS_MAP
    values = {f: _finite(row.get(col, 0), col) for f, col in mapping.items()}
    if sls:
        values["P"] *= -1  # N is already compression-positive in SLS.
    if isinstance(trace, Mapping):
        expected = trace.get("transported_actions", {})
        if all(f in expected and math.isclose(values[f], expected[f], rel_tol=1e-12, abs_tol=1e-10) for f in FIELDS):
            return dict(trace["original_actions"])
        # Some capacity readers intentionally alter the moment direction or N
        # at an analysis origin. Bring that edited vector back to its source
        # before transporting to another resistance origin.
        if trace.get("mode") == "EXACT":
            torque = trace.get("torsion_reference", trace)
            return {**values, "M3": values["M3"] + trace["r2_m"] * values["P"],
                "M2": values["M2"] + trace["r3_m"] * values["P"],
                "T": values["T"] - torque["r2_m"] * values["V3"] + torque["r3_m"] * values["V2"]}
        return dict(trace["original_actions"])
    return values


def transport(values, *, r2_m, r3_m):
    """M_O=M_C+(C-O)xF, then return CSI scalar output conventions."""
    f = np.array([values["P"], values["V2"], values["V3"]], dtype=float)
    m = np.array([values["T"], -values["M2"], values["M3"]], dtype=float)
    shifted = m + np.cross([0., r2_m, r3_m], f)
    return {**values, "T": float(shifted[0]), "M2": float(-shifted[1]),
            "M3": float(shifted[2])}


def transport_bounds(bounds, *, r2_m, r3_m):
    # Exact interval enclosure for the linear map; correlation is unknown.
    matrix = np.eye(6)
    matrix[3, 1] = -r3_m
    matrix[3, 2] = r2_m
    matrix[4, 0] = -r3_m
    matrix[5, 0] = -r2_m
    low = np.array([bounds[f][0] for f in FIELDS], dtype=float)
    high = np.array([bounds[f][1] for f in FIELDS], dtype=float)
    positive, negative = np.maximum(matrix, 0), np.minimum(matrix, 0)
    lower, upper = positive @ low + negative @ high, positive @ high + negative @ low
    return {f: (float(a), float(b)) for f, a, b in zip(FIELDS, lower, upper)}


def independent_envelope(info):
    return (str(info.get("step") or "").casefold() in {"max", "min"}
        and not (info.get("source_mode") == "correspondence"
                 and info.get("kind") == "CONCURRENT"
                 and info.get("concurrency_confirmed") is True
                 and bool(info.get("evidence"))))


def _pair_key(row, info):
    return (info.get("source_sha256") or info.get("source_file"), info.get("bridge_object"),
        info.get("girder") or row.get("Girder"), info.get("sheet"), info.get("case"),
        info.get("location_type"), info.get("section_cut"), info.get("occurrence"),
        float(row["Station x (m)"]))


def prepare_analysis_frame(frame, *, sls=False):
    result = pd.DataFrame(frame).copy(deep=True)
    pairs = {}
    for index, row in result.iterrows():
        info = source_info(row) or {}
        if SNAPSHOT_KEY in info and independent_envelope(info):
            pairs.setdefault(_pair_key(row, info), {}).setdefault(
                str(info["step"]).casefold(), []).append((index, actions(row, sls=sls)))
    for pair in pairs.values():
        if len(pair.get("max", [])) != 1 or len(pair.get("min", [])) != 1:
            continue
        endpoints = [pair["min"][0][1], pair["max"][0][1]]
        bounds = {f: [min(v[f] for v in endpoints), max(v[f] for v in endpoints)] for f in FIELDS}
        for index, _ in pair["max"] + pair["min"]:
            if BOUNDS_KEY not in result:
                result[BOUNDS_KEY] = pd.Series([None] * len(result), index=result.index, dtype=object)
            result.at[index, BOUNDS_KEY] = bounds
    return result


def geometry_origin(geometry, *, deck_thickness_mm=0, includes_deck=False):
    if isinstance(geometry, Mapping):
        geometry = SectionGeometry.model_validate(geometry)
    polygon = to_shapely_polygon(geometry)
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError("A valid resistance-section polygon is required for reference transport.")
    deck_top = float(polygon.bounds[3]) + (0 if includes_deck else float(deck_thickness_mm))
    return {"deck_top_y_mm": deck_top, "target_y_mm": float(polygon.centroid.y),
            "target_local3_mm": float(polygon.centroid.x)}


def translate_row(row, *, origin, sls=False):
    result = dict(row)
    info = source_info(row) or {}
    cfg = info.get(SNAPSHOT_KEY)
    if cfg is None:
        return result
    cfg = canonical_profile(cfg)
    raw = actions(row, sls=sls)
    cy = float(origin["deck_top_y_mm"]) / 1000 - cfg["depth_below_deck_top_m"]
    oy, o3 = float(origin["target_y_mm"]) / 1000, float(origin.get("target_local3_mm", 0)) / 1000
    r2, r3 = cy - oy, cfg["local3_offset_from_web_m"] - o3
    trace = {"schema": VERSION, "original_actions": raw, "source_y_mm": cy * 1000,
        "source_local3_mm": cfg["local3_offset_from_web_m"] * 1000,
        "target_y_mm": oy * 1000, "target_local3_mm": o3 * 1000,
        "r2_m": r2, "r3_m": r3, "force_kind": cfg["force_kind"],
        "profile_sha256": cfg["profile_sha256"], "mode": "EXACT",
        "concurrency_basis": "Declared correspondence" if str(info.get("step")).lower() in {"max", "min"} else "Single source state"}
    if independent_envelope(info):
        bounds = row.get(BOUNDS_KEY)
        previous = row.get(RUNTIME_KEY)
        if not isinstance(bounds, Mapping) and isinstance(previous, Mapping):
            bounds = previous.get("original_bounds")
        if not isinstance(bounds, Mapping):
            trace.update(mode="BLOCKED", error="Paired Max/Min actions at the same physical cut are required to transform envelope moments.")
            converted = {**raw, **{f: float("nan") for f in ("T", "M2", "M3")}}
        else:
            enclosed = transport_bounds(bounds, r2_m=r2, r3_m=r3)
            index = 1 if str(info["step"]).lower() == "max" else 0
            converted = {f: enclosed[f][index] for f in FIELDS}
            trace.update(mode="INTERVAL BOUND", original_bounds=dict(bounds),
                transformed_bounds={f: list(v) for f, v in enclosed.items()},
                concurrency_basis="Independent component bounds; no simultaneous state inferred")
    else:
        converted = transport(raw, r2_m=r2, r3_m=r3)
    trace["transported_actions"] = converted
    mapping = SLS_MAP if sls else ULS_MAP
    for f, col in mapping.items():
        result[col] = -converted[f] if sls and f == "P" else converted[f]
    result[RUNTIME_KEY] = trace
    return result


def retain_reported_torsion(row):
    """Keep native CSI Tu at its reporting point, independently of bending.

    CSITU46 is a demand policy, not a proof of reference-compatible resistance.
    General vector transport remains available to bending, SLS and equilibrium
    readers. Original source records and the input row are never modified.
    """
    result = dict(row)
    previous = row.get(RUNTIME_KEY)
    if not isinstance(previous, Mapping):
        return result
    trace = dict(previous)
    torque = float(trace["original_actions"]["T"])
    result[ULS_MAP["T"]] = torque
    trace["transported_actions"] = {**trace["transported_actions"], "T": torque}
    trace["torsion_reference"] = {
        "policy": SOURCE_TORSION_POLICY,
        "target_y_mm": trace["source_y_mm"],
        "target_local3_mm": trace["source_local3_mm"],
        "r2_m": 0.0, "r3_m": 0.0,
    }
    result[RUNTIME_KEY] = trace
    return result


def trace_columns(row):
    value = row.get(RUNTIME_KEY)
    if not isinstance(value, Mapping):
        return {}
    result = {"Reference version": VERSION, "Reference status": value["mode"],
        "CSI C y mm": value["source_y_mm"], "CSI C local3 mm": value["source_local3_mm"],
        "Resistance O y mm": value["target_y_mm"], "Resistance O local3 mm": value["target_local3_mm"],
        "C-O local2 m": value["r2_m"], "C-O local3 m": value["r3_m"],
        "CSI force kind": value["force_kind"], "CSI reference SHA256": value["profile_sha256"],
        "Reference action basis": value["concurrency_basis"],
        "Reference equation": "M_O=M_C+(C-O)xF; physical moments=(T,-M2,M3)",
        "Reference review": value.get("error", "")}
    for f, n in value["original_actions"].items():
        result[f"Original CSI {f} {'kN-m' if f in ('T','M2','M3') else 'kN'}"] = n
    torque = value.get("torsion_reference")
    if isinstance(torque, Mapping):
        result.update({"T resistance O y mm": torque["target_y_mm"],
            "T C-O local2 m": torque["r2_m"], "T C-O local3 m": torque["r3_m"],
            "Moment reference policy": "M2/M3 at composite centroid; T at I-section centroid; partial mechanism"})
        if torque.get("policy") == SOURCE_TORSION_POLICY:
            result.update({
                "T reference version": SOURCE_TORSION_POLICY,
                "T reference policy": "CSI reported Tu unchanged",
                "T reference y mm": torque["target_y_mm"],
                "T reference local3 mm": torque["target_local3_mm"],
                "T used kN-m": value["original_actions"]["T"],
                "T shift applied": False,
                "Moment reference policy": "T at CSI reporting point; M2/M3 at bending analysis origin; resistance screening",
                "Reference equation": "T_used=T_CSI; only M2/M3 use sectional moment transport",
            })
    return result


def qualify_result(result, demand_row, *, check_name):
    result = {**result, **trace_columns(demand_row)}
    trace = demand_row.get(RUNTIME_KEY)
    if not isinstance(trace, Mapping):
        return result
    reasons = []
    if trace["mode"] != "EXACT":
        reasons.append(trace.get("error") or "Transformed envelope bounds are screening only; concurrent actions are required.")
    if trace["force_kind"] == "GIRDER_COMPOSITE" and check_name in {"Torsion", "Shear + Torsion"}:
        reasons.append("Full Girder resultants include deck actions. This resistance route uses the I-girder hoop; composite torsion, slab and interface mechanisms are not certified by this check.")
    if ((trace.get("torsion_reference") or {}).get("policy") == SOURCE_TORSION_POLICY
            and check_name in {"Torsion", "Shear + Torsion"}):
        reasons.append("CSI Tu is used unchanged at its reporting point. Resistance at this reporting point and full coupled shear-center compatibility are not established; numerical ratios are screening results.")
    if trace["force_kind"] == "GIRDER_COMPOSITE" and check_name == "Shear" and abs(float(demand_row.get("Vux", 0))) > 1e-9:
        reasons.append("V2 sectional shear is checked; concurrent V3/deck transverse shear remains a separate required check.")
    if reasons:
        result["Reference review"] = " ".join(reasons)
        for key in ("Status", "Overall status", "Numerical status"):
            if result.get(key) in {"PASS", "Preview PASS", "NO DEMAND", "NOT REQUIRED", "BELOW THRESHOLD"}:
                result[key] = "REVIEW"
        result["Notes"] = " ".join(filter(None, [str(result.get("Notes") or ""), *reasons]))
    return result


def profile_from_payload(payload, filename):
    """Read a reference JSON or CSI Section Points table (m), independently of Loads."""
    digest = hashlib.sha256(payload).hexdigest()
    if filename.lower().endswith(".json"):
        data = json.loads(payload)
        if "metadata" in data:
            data = data["metadata"].get(SETTINGS_KEY, data)
        if "depth_below_deck_top_m" not in data:
            top, cg = _finite(data.get("source_top_y_m"), "Top Y"), _finite(data.get("source_cg_y_m"), "Ycg")
            data = {**data, "depth_below_deck_top_m": top - cg}
        return canonical_profile({**data, "reference_table_sha256": digest})
    grids = (pd.read_excel(BytesIO(payload), sheet_name=None, header=None).values()
        if filename.lower().endswith(".xlsx") else
        [pd.DataFrame(list(csv.reader(StringIO(payload.decode("utf-8-sig")))))])
    point_frames, properties = [], {}
    coordinate_factor = None
    key = lambda v: "".join(c for c in str(v).lower() if c.isalnum())
    for grid in grids:
        for _, row in grid.iterrows():
            cells = list(row)
            if len(cells) >= 2 and key(cells[0]) in {"ycg", "sourcecgym", "sourcetopym"}:
                properties[key(cells[0])] = _finite(cells[1], str(cells[0]))
        for i in range(min(25, len(grid))):
            names = [key(v) for v in grid.iloc[i]]
            if {"shape", "point", "x", "y"} <= set(names):
                frame = grid.iloc[i + 1:].copy()
                frame.columns = names
                first = frame.iloc[0] if not frame.empty else {}
                units = {"m": 1., "mm": .001, "cm": .01, "ft": .3048, "in": .0254}
                x_unit, y_unit = key(first.get("x", "")), key(first.get("y", ""))
                if x_unit in units or y_unit in units:
                    if x_unit != y_unit or x_unit not in units:
                        raise ValueError("CSI section coordinate units must be consistent.")
                    frame = frame.iloc[1:].copy()
                    for column in ("x", "y"):
                        frame[column] = pd.to_numeric(frame[column], errors="coerce") * units[x_unit]
                    if coordinate_factor is not None and coordinate_factor != units[x_unit]:
                        raise ValueError("Section tables with different coordinate units need separate reference files.")
                    coordinate_factor = units[x_unit]
                point_frames.append(frame)
                break
    if not point_frames:
        if {"sourcetopym", "ycg"} <= set(properties) or {"sourcetopym", "sourcecgym"} <= set(properties):
            top, cg = properties["sourcetopym"], properties.get("ycg", properties.get("sourcecgym"))
            return canonical_profile({"depth_below_deck_top_m": top - cg,
                "source_top_y_m": top, "source_cg_y_m": cg, "reference_table_sha256": digest,
                "vertical_location": "CG of Full Bridge Section", "basis": "Reported CSI properties"})
        raise ValueError("Reference file needs CSI Section Points columns Shape/Point/Material/X/Y, or source_top_y_m and Ycg.")
    points = pd.concat(point_frames, ignore_index=True)
    points["shape"] = points["shape"].replace(r"^\s*$", np.nan, regex=True).ffill()
    for col in ("x", "y"):
        points[col] = pd.to_numeric(points[col], errors="coerce")
    ref = points[points["shape"].map(key).eq("referencepoint")].dropna(subset=["y"])
    if len(ref) != 1:
        raise ValueError("Section Points must contain exactly one Reference Point.")
    top = float(ref.iloc[0]["y"])
    polygons, materials = [], set()
    for name, group in points.groupby("shape", sort=False):
        if not key(name).startswith("structuralpolygon"):
            continue
        group = group.dropna(subset=["x", "y"])
        poly = Polygon(group[["x", "y"]].to_numpy())
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f"Invalid CSI structural polygon: {name}.")
        polygons.append(poly)
        if "material" in group:
            materials.update(str(v).strip() for v in group["material"].dropna() if str(v).strip())
    if not polygons:
        raise ValueError("No structural polygons in the CSI reference table.")
    area = sum(p.area for p in polygons)
    for i, poly in enumerate(polygons):
        if any(poly.intersection(other).area > max(1e-10, area * 1e-9) for other in polygons[:i]):
            raise ValueError("CSI structural polygons overlap; resolve duplicate/overlapping component areas.")
    reported = properties.get("ycg", properties.get("sourcecgym"))
    if "ycg" in properties and coordinate_factor is not None:
        reported *= coordinate_factor
    if reported is None and len(materials) != 1:
        raise ValueError("Multiple or missing materials: include reported CSI Ycg; an area-only CG is not assumed.")
    cg = float(reported) if reported is not None else sum(p.area * p.centroid.y for p in polygons) / area
    if max(p.bounds[3] for p in polygons) > top + 1e-8:
        raise ValueError("Section Reference Point is not the common deck-top datum. Supply the actual CSI depth per Girder.")
    return canonical_profile({"depth_below_deck_top_m": top - cg,
        "source_top_y_m": top, "source_cg_y_m": cg, "bridge_section_area_m2": area,
        "structural_polygon_count": len(polygons), "reference_table_sha256": digest,
        "vertical_location": "CG of Full Bridge Section",
        "basis": "Reported CSI Ycg" if reported is not None else "CSI Section Points; single homogeneous material; area CG"})

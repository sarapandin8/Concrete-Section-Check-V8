"""Versioned hook geometry. No resistance, inferred slab closure or acceptance.

Legacy E remains a required cover. New E is the measured top-surface-to-outer-
hook depth. Only a saved B can establish a legacy hook position on migration.
"""
from copy import deepcopy
from collections.abc import Mapping
import math

SCHEMA = "IGIRDER.DETAIL35"


def value(v):
    try:
        n = float(v) if not isinstance(v, bool) else float("nan")
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def positive(v):
    n = value(v)
    return n is not None and n > 0


def migrate(cfg, params, *, girder_cover=None, slab_cover=None):
    """UI adoption only; preserve old measured values and their old meaning.

    Automatic 6db is a specified DESIGN bend, not proof of fabrication. Its
    required general-hook minimum is still checked independently by JOINT29.
    """
    out = deepcopy(dict(cfg))
    if out.get("detail_schema") == SCHEMA:
        return out
    legacy_keys = ("slab_ldh_available_mm", "hook_inside_bend_mm", "cover_required_mm")
    out["legacy_detail35"] = {k: out.get(k) for k in legacy_keys}
    ts, b = value(params.get("Tslab_mm")), value(out.get("slab_ldh_available_mm"))
    out["hook_top_depth_mm"] = ts-b if ts is not None and b is not None else None
    legacy_cover = out.get("cover_required_mm")
    out["girder_clear_cover_required_mm"] = girder_cover if positive(girder_cover) else legacy_cover
    out["slab_clear_cover_required_mm"] = slab_cover if positive(slab_cover) else legacy_cover
    out.update(detail_schema=SCHEMA, bend_mode="auto_6db")
    return out


def resolve(cfg, *, slab_thickness_mm, db_mm=None):
    """Resolve B and D from current thickness and the actual selected zone db.

    Old solver calls retain their old meaning; no heuristic on an E magnitude.
    Cached B/D in a new JSON are never authoritative over E/current db.
    """
    out = deepcopy(dict(cfg))
    if out.get("detail_schema") != SCHEMA:
        return out
    ts, e, db = map(value, (slab_thickness_mm, out.get("hook_top_depth_mm"), db_mm))
    out["slab_ldh_available_mm"] = ts-e if ts is not None and e is not None else None
    if out.get("bend_mode") == "auto_6db":
        out["hook_inside_bend_mm"] = 6*db if db is not None and db > 0 else None
    out["cover_required_mm"] = out.get("girder_clear_cover_required_mm")
    return out


def covers(cfg):
    if cfg.get("detail_schema") == SCHEMA:
        return value(cfg.get("girder_clear_cover_required_mm")), value(cfg.get("slab_clear_cover_required_mm"))
    old = value(cfg.get("cover_required_mm"))
    return old, old


def diameter_values(settings, girder_zones):
    """Match the selected connector source, never an unused dowel table."""
    from .igird_interface_connectors import INDEPENDENT_DOWELS, LINKED_DOWELS
    source = settings.get("connector_source")
    raw = settings.get("dowel_zones", []) if source == INDEPENDENT_DOWELS else girder_zones if source == LINKED_DOWELS else []
    return sorted({value(z.get("Diameter_mm")) for z in raw
        if isinstance(z, Mapping) and z.get("Active", True) and positive(z.get("Diameter_mm"))})


def mesh_rows(cfg, params):
    """Transverse mesh is independent of the existing longitudinal inputs.

    Reuse the named layer fy only as an explicit editable initial value. Unknown
    bar size, spacing and physical cover stay unknown; nothing becomes closure.
    """
    raw = cfg.get("slab_transverse_mesh", {})
    raw = raw if isinstance(raw, Mapping) else {}
    rows = []
    for layer in ("top", "bottom"):
        saved = raw.get(layer, {})
        saved = saved if isinstance(saved, Mapping) else {}
        fy = saved.get("fy_MPa") if "fy_MPa" in saved else params.get("deck_long_rebar_"+layer+"_fy_MPa", params.get("deck_long_rebar_fy_MPa"))
        rows.append({"Layer":layer.title(), "Diameter_mm":value(saved.get("Diameter_mm")),
            "Spacing_mm":value(saved.get("Spacing_mm")), "Clear_cover_mm":value(saved.get("Clear_cover_mm")), "fy_MPa":value(fy)})
    return rows


def mesh_inventory(cfg, params):
    from .igird_slab_layers import resolve
    params = resolve(params,cfg)['parameters']
    rows = []
    for layer in ("top", "bottom"):
        prefix = "deck_long_rebar_"+layer+"_"
        rows.append({"Layer":layer.title(), "Direction":"Along girder", "Diameter_mm":value(params.get(prefix+"diameter_mm")),
            "Spacing_mm":value(params.get(prefix+"spacing_mm")), "Clear_cover_mm":value(params.get(prefix+"cover_mm")),
            "fy_MPa":value(params.get(prefix+"fy_MPa",params.get("deck_long_rebar_fy_MPa"))), "Source":"Section Builder"})
    for row in mesh_rows(cfg, params):
        rows.append({**row, "Direction":"Across girder", "Source":"Slab mesh input; not a verified torsion closure"})
    for row in rows:
        complete = all(positive(row[k]) for k in ("Diameter_mm", "Spacing_mm", "fy_MPa"))
        row["As_mm2_per_m"] = math.pi*row["Diameter_mm"]**2/4*1000/row["Spacing_mm"] if complete else None
        row["Position"] = "Provided" if positive(row["Clear_cover_mm"]) else "Unknown"
        row["Scope"] = "Input inventory only — no additional resistance credit"
    return rows

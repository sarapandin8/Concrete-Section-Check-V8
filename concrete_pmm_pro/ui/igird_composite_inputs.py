"""Small input inventory for the composite workflow; no strength calculations."""
from collections.abc import Mapping
import math

import pandas as pd

from concrete_pmm_pro.analysis.igird_dowel_joint import ACTION_COLUMNS, DIMENSIONS, config, number
from concrete_pmm_pro.analysis.igird_interface_connectors import INDEPENDENT_DOWELS, LINKED_DOWELS
from concrete_pmm_pro.io import csi_component_sources as sources


SHORT_DIMENSIONS = {
    "row_spacing_mm": "U-leg centres a",
    "slab_ldh_available_mm": "Interface to outside of top hook",
    "hook_tail_mm": "Straight tail after 90° bend",
    "hook_inside_bend_mm": "Inside bend diameter",
    "girder_ld_available_mm": "Straight bonded leg below interface",
    "cover_required_mm": "Required clear cover",
}


def positive(value):
    value = number(value)
    return math.isfinite(value) and value > 0


def effective_config(current, params):
    """Reuse the existing cover value only; measured bar geometry stays unknown."""
    cfg = config(current)
    if cfg.get("cover_required_mm") is None:
        cover = params.get("deck_long_rebar_top_cover_mm")
        if positive(cover):
            cfg["cover_required_mm"] = cover
    return cfg


def input_plan(settings, *, params, state=None):
    """Presence checks only. A complete form is never design acceptance."""
    state = state or {}
    cfg = effective_config(settings, params)
    missing, pending = [], []
    from concrete_pmm_pro.analysis.igird_dowel_detail35 import SCHEMA
    current_detail = cfg.get("detail_schema") == SCHEMA
    names = {"row_spacing_mm":"U-leg centres A", "hook_tail_mm":"Hook tail C",
        "hook_top_depth_mm":"Top surface to outside hook E", "girder_ld_available_mm":"Straight bonded leg F",
        "girder_clear_cover_required_mm":"Girder minimum clear cover", "slab_clear_cover_required_mm":"Slab minimum clear cover"} if current_detail else SHORT_DIMENSIONS
    for name in names:
        if not positive(cfg.get(name)):
            missing.append({"Input": names[name], "Where": "Dowel detail",
                "Why": "Required measured bar geometry (mm)"})
    if current_detail and cfg.get("bend_mode") != "auto_6db" and not positive(cfg.get("hook_inside_bend_mm")):
        missing.append({"Input":"Provided bend D", "Where":"Dowel detail", "Why":"Enter provided D or use Automatic — 6.0db"})
    if cfg.get("coating") not in {"uncoated", "epoxy"}:
        pending.append({"Step":"Coating / development basis","Status":"UNVERIFIED MATERIAL BASIS",
            "Meaning":"Known coating may be taken from the specification. Unknown is retained; the model must establish a valid development bound before resistance acceptance."})
    if cfg.get("anchorage_region") != "interior":
        pending.append({"Step":"Anchorage-region evaluation","Status":"MODEL REVIEW REQUIRED",
            "Meaning":"The model must establish the applicable interior/end anchorage route. No user guess or manual interior selection can establish strength."})
    source = settings.get("connector_source")
    if source == INDEPENDENT_DOWELS:
        raw = settings.get("dowel_zones", [])
        zones = raw if isinstance(raw, list) else []
        if not zones or not any(isinstance(zone,Mapping) and zone.get("Active",True) for zone in zones):
            missing.append({"Input": "Dowel layout", "Where": "Dowel layout", "Why": "No independent layout saved"})
        intervals = []
        for index, zone in enumerate(zones):
            if not isinstance(zone, Mapping):
                missing.append({"Input": f"Zone {index+1}", "Where": "Dowel layout", "Why": "Invalid zone record"})
                continue
            if not zone.get("Active", True):
                continue
            a, b = number(zone.get("x_start_m")), number(zone.get("x_end_m"))
            if not math.isfinite(a+b) or a < 0 or b <= a:
                missing.append({"Input": str(zone.get("Zone") or f"Zone {index+1}") + " start / end",
                    "Where": "Dowel layout", "Why": "Section labels do not define the longitudinal extent"})
            else:
                intervals.append((a, b))
            for name in ("Diameter_mm", "Legs", "Spacing_mm", "fy_MPa"):
                if not positive(zone.get(name)):
                    missing.append({"Input": str(zone.get("Zone") or f"Zone {index+1}") + " / " + name,
                        "Where": "Dowel layout", "Why": "A positive supplied reinforcement value is needed"})
            legs = number(zone.get("Legs"))
            if positive(legs) and legs != 2:
                missing.append({"Input": str(zone.get("Zone") or f"Zone {index+1}") + " crossing legs",
                    "Where": "Dowel layout", "Why": "The current joint model supports one two-legged U per set"})
        intervals.sort()
        if any(b[0] < a[1]-1e-9 for a, b in zip(intervals, intervals[1:])):
            missing.append({"Input": "Overlapping dowel zones", "Where": "Dowel layout",
                "Why": "Separate zones must not overlap; supplies cannot be added"})
    elif source != LINKED_DOWELS:
        missing.append({"Input": "U-dowel source", "Where": "Interface reinforcement source",
            "Why": "Select an explicit U-dowel source for this joint model"})
    actions = cfg.get("action_rows", [])
    valid_actions = isinstance(actions, list) and bool(actions)
    if valid_actions:
        for row in actions:
            if not isinstance(row, Mapping):
                valid_actions = False
                break
            if any(not math.isfinite(number(row.get(k))) for k in ACTION_COLUMNS[1:6]):
                valid_actions = False
            if any(str(row.get(k) or "").strip().lower() in {"", "none", "nan"} for k in ("Case", "Source")):
                valid_actions = False
    if not valid_actions:
        pending.append({"Step": "Recover interface force state", "Status": "MODEL DEVELOPMENT",
            "Meaning": "Use paired component states, verified origins and external loading in a joint free-body; Girder Tu alone is insufficient. Manual forces are an optional advanced review."})
    pending.append({"Step": "Full composite Tn / V–T resistance", "Status": "COUPLED RESEARCH MODEL — PRODUCTION WITHHELD",
        "Meaning": "COUPLED34 adds a shared-resource closed-cell/interface model. Enable under Composite V–T research inputs and use Calculate Flexure. Compatible crack/slip behaviour and independent structural validation are still required for production acceptance."})
    if current_detail:
        pending.append({"Step":"Slab transverse top / bottom mesh", "Status":"INPUT INVENTORY ONLY",
            "Meaning":"Both directions are saved independently. Undefined transverse size/spacing/position stays unknown; a mesh does not establish a verified closed torsion path."})
    bank = state.get("igird_uls_member_bank")
    if bank is None:
        bank = state.get("beam_uls_loads_table", [])
    saved_sources = sources.saved(state)
    component_rows = sources.overview(saved_sources, active_loads=bank)
    reused = [
        {"Input": "I-girder depth / top flange / web", "Value": " / ".join(
            f"{number(params.get(k)):g}" if positive(params.get(k)) else "—" for k in ("D1_mm", "B1_mm", "T2_mm")) + " mm", "Source": "Section Builder"},
        {"Input": "Assigned slab width / thickness", "Value": " / ".join(
            f"{number(params.get(k)):g}" if positive(params.get(k)) else "—" for k in ("Be_mm", "Tslab_mm")) + " mm", "Source": "Section Builder"},
        {"Input": "Slab longitudinal top / bottom", "Value": " / ".join(
            f"DB{number(params.get('deck_long_rebar_'+side+'_diameter_mm')):g} @ {number(params.get('deck_long_rebar_'+side+'_spacing_mm')):g}"
            if positive(params.get('deck_long_rebar_'+side+'_diameter_mm')) and positive(params.get('deck_long_rebar_'+side+'_spacing_mm')) else "See existing slab inputs"
            for side in ("top", "bottom")), "Source": "Existing reinforcement; no new entry"},
        {"Input": "Dowel bars / fy / spacing", "Value": "Existing connector layout", "Source": "Independent dowel data" if source == INDEPENDENT_DOWELS else "Selected connector source"},
        {"Input": "ULS force rows", "Value": str(len(pd.DataFrame(bank if bank is not None else []))), "Source": "Loads; original values retained"},
        {"Input": "Beam / Slab source files", "Value": str(len(saved_sources.get("sources", []))), "Source": "Same CSiBridge uploader"},
    ]
    return {"reused": reused, "missing": missing, "pending": pending, "components": component_rows,
        "source_fingerprint": sources.fingerprint(saved_sources),
        "design_status": "REVIEW", "scope": "Input inventory only; full composite V–T resistance is not implemented or certified by this inventory."}

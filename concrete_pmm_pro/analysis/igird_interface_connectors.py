"""Explicit source of reinforcement crossing a girder/deck interface.

Only Avf and its material source are selected here. No dowel is credited to
the I-girder closed hoop, Ao/ph, or torsional longitudinal reinforcement.
"""
from __future__ import annotations
from copy import deepcopy
import math
from collections.abc import Mapping
from concrete_pmm_pro.analysis.igird_interface_shear import (
    INTERFACE_FY_CAP_MPA, provided_interface_reinforcement_mm2_per_m,
)

VERSION = "IGIRDER.DOWEL28"
STIRRUPS = "girder_stirrups"
LINKED_DOWELS = "dowels_same_zoning"
INDEPENDENT_DOWELS = "independent_dowels"
SOURCE_LABELS = {
    STIRRUPS: "Girder stirrups extended into slab",
    LINKED_DOWELS: "Dowel bars — use girder zoning, diameter and spacing",
    INDEPENDENT_DOWELS: "Dowel bars — separate layout",
}
DOWEL_COLUMNS = ["Zone", "x_start_m", "x_end_m", "Diameter_mm", "Legs", "Spacing_mm", "fy_MPa"]


def settings_fields(raw):
    raw = raw if isinstance(raw, Mapping) else {}
    fields = {"connector_source": str(raw.get("connector_source", STIRRUPS)),
        "dowel_crossing_legs": raw.get("dowel_crossing_legs", 2),
        "connectors_cross_and_anchored": bool(raw.get("connectors_cross_and_anchored",raw.get("stirrups_cross_and_anchored",False))),
        "dowel_zones": deepcopy(raw.get("dowel_zones", []))}
    if "dowel_connection" in raw:
        fields["dowel_connection"] = deepcopy(raw["dowel_connection"])
    return fields


def _number(v):
    try:
        return float(v) if not isinstance(v, bool) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _read_zone(raw):
    zone = dict(raw)
    diameter = _number(zone.get("Diameter_mm"))
    if not math.isfinite(diameter) or diameter <= 0:
        diameter = _number(str(zone.get("Bar Size", "")).upper().removeprefix("DB"))
    values = {"Diameter_mm": diameter, **{k:_number(zone.get(k)) for k in ("Legs","Spacing_mm","fy_MPa")}}
    if not all(math.isfinite(v) and v > 0 for v in values.values()) or not values["Legs"].is_integer():
        raise ValueError("Interface connector diameter, integer crossing-leg count, spacing and fy must be positive and finite.")
    zone.update(values)
    zone["Bar Size"] = f"DB{diameter:g}"
    zone["area_mm2"] = math.pi * diameter**2 / 4
    zone["Avf_mm2_per_m"] = provided_interface_reinforcement_mm2_per_m(
        bar_area_mm2=zone["area_mm2"],legs=zone["Legs"],spacing_mm=zone["Spacing_mm"])
    return zone


def copy_girder_zoning(zones, *, crossing_legs=2):
    """Explicit copy, not a live link; later stirrup edits cannot alter dowels."""
    return [{"Zone":"Dowel / "+str(z.get("Zone") or "zone"),
        "x_start_m":z.get("x_start_m"),"x_end_m":z.get("x_end_m"),
        "Diameter_mm":z.get("Diameter_mm"),"Legs":crossing_legs,
        "Spacing_mm":z.get("Spacing_mm"),"fy_MPa":z.get("fy_MPa")}
        for z in zones if z.get("Active",True)]


def at_station(settings, *, x_m, girder_zone=None):
    cfg = settings_fields(settings)
    source = cfg["connector_source"]
    base = {"source":source,"source_label":SOURCE_LABELS.get(source,"Unknown connector source"),
        "ready":False,"zone":None,"reason":""}
    try:
        x = _number(x_m)
        if not math.isfinite(x):
            raise ValueError("Interface connector station is unavailable.")
        if source in {STIRRUPS,LINKED_DOWELS}:
            if girder_zone is None:
                raise ValueError("No active girder zone covers the station for this linked connector source.")
            raw = dict(girder_zone)
            if source == LINKED_DOWELS:
                raw["Legs"] = cfg["dowel_crossing_legs"]
            chosen = _read_zone(raw)
        elif source == INDEPENDENT_DOWELS:
            if not isinstance(cfg["dowel_zones"],list):
                raise ValueError("Define the independent dowel layout.")
            zones = []
            for raw in cfg["dowel_zones"]:
                if not isinstance(raw,Mapping):
                    raise ValueError("Invalid dowel zone record.")
                if not raw.get("Active",True):
                    continue
                zone = _read_zone(raw)
                start,end = _number(raw.get("x_start_m")),_number(raw.get("x_end_m"))
                if not math.isfinite(start+end) or start < 0 or end <= start:
                    raise ValueError("Each dowel zone needs finite 0 ≤ start < end; section labels alone do not define longitudinal extents.")
                zone.update(x_start_m=start,x_end_m=end)
                zones.append(zone)
            zones.sort(key=lambda z:(z["x_start_m"],z["x_end_m"]))
            if any(b["x_start_m"] < a["x_end_m"]-1e-9 for a,b in zip(zones,zones[1:])):
                raise ValueError("Independent dowel zones overlap; do not sum mutually exclusive zones.")
            covered = [z for z in zones if z["x_start_m"]-1e-9 <= x <= z["x_end_m"]+1e-9]
            if not covered:
                raise ValueError("No independent dowel zone covers this station; no stirrup fallback is used.")
            # At an exact change of spacing, take the weaker adjoining supply.
            chosen = min(covered,key=lambda z:z["Avf_mm2_per_m"]*min(z["fy_MPa"],INTERFACE_FY_CAP_MPA))
        else:
            raise ValueError("Unknown interface connector source; choose an explicit reinforcement source.")
    except (ValueError, TypeError) as exc:
        return {**base,"reason":str(exc)}
    return {**base,"ready":True,"zone":chosen,
        "basis":"Avf/s = n_crossing × πdb²/4 / spacing; one selected connector source only"}

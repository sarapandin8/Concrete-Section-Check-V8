"""Input-only source-axis geometry for monolithic precast I-girder ends."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
import math
from shapely.geometry import Polygon, box
from concrete_pmm_pro.core.models import Point2D, SectionGeometry
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
SETTINGS_KEY = "igird_end_sections"
RESULT_VERSION = "IGIRDER.ENDSECTION18"

def enabled(state: Mapping) -> bool:
    params = state.get("section_parameters") or {}
    settings = params.get(SETTINGS_KEY) or {}
    mode = state.get("analysis_mode_settings")
    member = mode.get("member_type") if isinstance(mode, Mapping) else getattr(mode, "member_type", None)
    return (state.get("section_preset_key") == "parametric_i_girder" and member in (None, "beam_girder")
        and isinstance(settings, Mapping) and bool(settings.get("enabled")))

def cut_ends(params: Mapping, span_m: float) -> tuple[float, float]:
    raw = params.get(SETTINGS_KEY) or {}
    if not isinstance(raw, Mapping) or not raw.get("enabled"):
        return 0.0, float(span_m)
    mode = raw.get("coordinate_mode", "custom")
    if mode not in ("span", "custom"):
        raise ValueError("Girder end coordinates must use Loads span or custom coordinates.")
    if mode == "span":
        left, right = 0.0, float(span_m)
    else:
        left = float(raw.get("left_end_x_m", 0.0))
        right = float(raw.get("right_end_x_m", span_m))
    if not all(math.isfinite(v) for v in (left, right, span_m)) or not 0 <= left < right <= span_m:
        raise ValueError("Physical precast ends must satisfy 0 ≤ left x < right x ≤ Loads span.")
    return left, right

def development_coordinates(state: Mapping, x_m: float, span_m: float) -> tuple[float, float]:
    if not enabled(state): return x_m, span_m
    left, right = cut_ends(state.get("section_parameters") or {}, span_m)
    if not left - 1e-9 <= x_m <= right + 1e-9:
        raise ValueError("Imported station lies outside the physical precast girder; no section is assigned.")
    return min(max(x_m - left, 0.0), right - left), right - left

@dataclass(frozen=True)
class EndProfile:
    left_x_m: float
    right_x_m: float
    left_solid_m: float
    right_solid_m: float
    left_taper_m: float
    right_taper_m: float
    width_mm: float
    chamfer_mm: float
    hoop_confirmed: bool
    d_region_confirmed: bool
    load_reference_confirmed: bool
    @property
    def boundaries(self) -> tuple[float, ...]:
        return tuple(sorted(set((self.left_x_m, self.left_x_m + self.left_solid_m,
            self.left_x_m + self.left_solid_m + self.left_taper_m,
            self.right_x_m - self.right_solid_m - self.right_taper_m,
            self.right_x_m - self.right_solid_m, self.right_x_m))))
    def location(self, x_m: float) -> tuple[str, float]:
        if not math.isfinite(x_m) or not self.left_x_m - 1e-9 <= x_m <= self.right_x_m + 1e-9:
            raise ValueError("Imported station lies outside the physical precast girder; no section is assigned.")
        dl, dr = max(0.0, x_m - self.left_x_m), max(0.0, self.right_x_m - x_m)
        # An abrupt junction uses the narrower I-side section.
        for side, distance, solid, taper in (("LEFT", dl, self.left_solid_m, self.left_taper_m),
                ("RIGHT", dr, self.right_solid_m, self.right_taper_m)):
            if solid > 0 and (distance < solid - 1e-9 or (taper > 0 and distance <= solid + 1e-9)):
                return f"{side} SOLID END", 1.0
            if taper > 0 and solid <= distance < solid + taper - 1e-9:
                return f"{side} TAPER", min(1.0, max(0.0, 1.0 - (distance - solid) / taper))
        return "I SECTION", 0.0

def profile(state: Mapping, geometry: SectionGeometry, span_m: float) -> EndProfile:
    if not enabled(state): raise ValueError("Variable precast end sections are disabled.")
    if geometry.holes: raise ValueError("Filled end sections require a solid precast I profile without voids.")
    polygon = to_shapely_polygon(geometry)
    if polygon.is_empty or not polygon.is_valid or polygon.geom_type != "Polygon":
        raise ValueError("A valid precast I polygon is required.")
    minx, miny, maxx, maxy = polygon.bounds
    raw = (state.get("section_parameters") or {})[SETTINGS_KEY]
    left, right = cut_ends(state.get("section_parameters") or {}, span_m)
    def number(key, default):
        value = float(raw.get(key, default))
        if not math.isfinite(value) or value < 0: raise ValueError(f"{key} must be finite and nonnegative.")
        return value
    ls, rs = number("left_solid_m", 1.5), number("right_solid_m", 1.5)
    lt, rt = number("left_taper_m", .25), number("right_taper_m", .25)
    width, chamfer = number("width_mm", maxx-minx), number("chamfer_mm", 0.0)
    if ls + rs + lt + rt >= right - left - 1e-9:
        raise ValueError("Solid ends and tapers overlap or leave no central I-section length.")
    if width < maxx-minx-1e-6 or width <= 0:
        raise ValueError("Solid-end width must cover the widest flange of the supplied I profile.")
    if chamfer >= .5 * min(width, maxy-miny):
        raise ValueError("End chamfer must be smaller than half the section width and height.")
    return EndProfile(left,right,ls,rs,lt,rt,width,chamfer,bool(raw.get("hoop_confirmed")),
        bool(raw.get("d_region_confirmed")),bool(raw.get("load_reference_confirmed")))

def section_at(geometry: SectionGeometry, definition: EndProfile, x_m: float) -> tuple[SectionGeometry, dict]:
    region, fraction = definition.location(float(x_m))
    source = to_shapely_polygon(geometry)
    minx, miny, maxx, maxy = source.bounds
    if fraction == 0: local, polygon = geometry, source
    else:
        cx = .5 * (minx+maxx)
        if fraction == 1: polygon = box(cx-definition.width_mm/2,miny,cx+definition.width_mm/2,maxy)
        else:
            points=[]
            for point in geometry.outer_polygon:
                target=cx+math.copysign(definition.width_mm/2,float(point.x)-cx)
                points.append(((1-fraction)*point.x+fraction*target,point.y))
            polygon=Polygon(points)
        c=definition.chamfer_mm*fraction
        if c>0:
            a,b,d,e=polygon.bounds
            polygon=polygon.intersection(Polygon([(a+c,b),(d-c,b),(d,b+c),(d,e-c),(d-c,e),(a+c,e),(a,e-c),(a,b+c)]))
        if polygon.is_empty or polygon.geom_type!="Polygon" or not polygon.is_valid:
            raise ValueError("The selected end/taper definition produces an invalid polygon.")
        polygon=polygon.simplify(1e-8,preserve_topology=True)
        local=geometry.model_copy(update={"name":f"{geometry.name} · {region}",
            "outer_polygon":[Point2D(x=x,y=y) for x,y in list(polygon.exterior.coords)[:-1]],
            "metadata":{**geometry.metadata,"end_section_fraction":fraction,"end_section_region":region}})
    return local,{"Section region":region,"Solid fill fraction":fraction,
        "Physical girder x (m)":float(x_m)-definition.left_x_m,
        "Physical girder length (m)":definition.right_x_m-definition.left_x_m,
        "Section Acp mm2":float(polygon.area),"Section Pcp mm":float(polygon.length),
        "Section boundaries (m)":",".join(f"{v:.9g}" for v in definition.boundaries[1:-1]),
        "Section geometry version":RESULT_VERSION}

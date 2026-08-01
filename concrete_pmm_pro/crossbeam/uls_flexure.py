"""ACI 318-19 Crossbeam ULS axial-flexure (P-M3) interaction review.

CROSSBEAM.ULS1A consumes validated, row-coupled ``ULS Final Stage`` demands.
``P`` is compression-positive and ``M3`` is sagging-positive.  Capacity is
calculated by the existing ACI strain-compatibility PMM engine using the
station Section ID and adopted longitudinal-rebar template.  Bonded internal
prestress is included only when an adopted effective-prestress handoff exists;
external/unbonded tendon effects remain a guarded REVIEW limitation.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from typing import Any

from shapely.geometry import Point

from concrete_pmm_pro.analysis.pmm_solver import run_rc_pmm_solver
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.concrete_materials import concrete_materials_by_name, ensure_concrete_material_library
from concrete_pmm_pro.core.models import LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.crossbeam.analysis_foundation import DATASET_ULS_FINAL
from concrete_pmm_pro.crossbeam.rebar import canonical_rebar_templates, rebar_diameter_mm, template_map
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    canonical_section_definitions,
    definition_map,
)
from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_system_rows, tendon_positions_at_station
from concrete_pmm_pro.geometry.rebar_layout import generate_inner_face_rebar_layout, generate_perimeter_rebar_layout
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


CROSSBEAM_ULS_FLEXURE_SCHEMA = "crossbeam-uls-flexure-pm3-v1"
CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY = "crossbeam_analysis_uls1a_flexure_result"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
            return [dict(row) for row in rows if isinstance(row, Mapping)]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def flexure_input_fingerprint(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    rebar_template_rows: Any,
    tendon_system_rows: Any = None,
    tendon_profile_rows: Any = None,
    effective_prestress_link: Any = None,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    prestress_ep_mpa: float = 195000.0,
) -> str:
    try:
        library = ensure_concrete_material_library(
            concrete_material=concrete_material,
            concrete_materials=concrete_materials,
            active_concrete_material_name=active_concrete_material_name,
            deck_topping_material_name=deck_topping_material_name,
        )
        materials = [_jsonable(item) for item in library.materials]
    except Exception:
        materials = _records(concrete_materials)
    return _fingerprint(
        {
            "schema": CROSSBEAM_ULS_FLEXURE_SCHEMA,
            "foundation": _text(foundation.get("fingerprint")),
            "definitions": canonical_section_definitions(section_definitions),
            "rebar_templates": canonical_rebar_templates(_records(rebar_template_rows)),
            "tendon_system": canonical_tendon_system_rows(tendon_system_rows),
            "tendon_profile": _records(tendon_profile_rows),
            "effective_prestress_link": dict(effective_prestress_link) if isinstance(effective_prestress_link, Mapping) else {},
            "materials": materials,
            "prestress_ep_mpa": _float(prestress_ep_mpa, 195000.0),
        }
    )



def _uniaxial_pm3_check(pmm: Any, *, pu_n: float, m3_nmm: float) -> dict[str, Any]:
    """Interpolate the exact uniaxial M3 slice from the PMM sweep.

    With the app axis convention, theta = pi/2 produces positive Mnx (positive
    M3) and theta = 3pi/2 produces negative Mnx.  This avoids the generic
    biaxial directional-envelope prototype for the Crossbeam uniaxial check.
    """

    points = list(getattr(pmm, "points", []) or [])
    if not points:
        return {"status": "INCOMPLETE", "dcr": None, "capacity_phiMn_Nmm": None, "method": "empty_pmm"}
    if abs(m3_nmm) <= 1.0e-9:
        axial_values = [
            float(point.phiPn_capped_N if point.phiPn_capped_N is not None else point.phiPn_N)
            for point in points
        ]
        capacity = max(axial_values) if pu_n >= 0.0 else abs(min(axial_values))
        demand = pu_n if pu_n >= 0.0 else abs(pu_n)
        if capacity <= 0.0:
            return {"status": "INCOMPLETE", "dcr": None, "capacity_phiMn_Nmm": None, "method": "axial_only"}
        dcr = demand / capacity
        return {"status": "FAIL" if dcr > 1.0 + 1.0e-12 else "PASS", "dcr": dcr, "capacity_phiMn_Nmm": 0.0, "method": "axial_only_capped_phiPn"}

    target_theta = 0.5 * math.pi if m3_nmm > 0.0 else 1.5 * math.pi
    selected = [point for point in points if abs(float(point.theta_rad) - target_theta) <= 1.0e-8]
    if len(selected) < 2:
        return {"status": "INCOMPLETE", "dcr": None, "capacity_phiMn_Nmm": None, "method": "missing_uniaxial_theta"}

    grouped: dict[float, float] = {}
    for point in selected:
        p_value = float(point.phiPn_capped_N if point.phiPn_capped_N is not None else point.phiPn_N)
        m_value = float(point.phiMnx_Nmm)
        directional = m_value if m3_nmm > 0.0 else -m_value
        if directional <= 0.0:
            continue
        key = round(p_value, 6)
        grouped[key] = max(grouped.get(key, 0.0), directional)
    curve = sorted((p_value, m_value) for p_value, m_value in grouped.items())
    if len(curve) < 2 or pu_n < curve[0][0] - 1.0e-6 or pu_n > curve[-1][0] + 1.0e-6:
        return {"status": "INCOMPLETE", "dcr": None, "capacity_phiMn_Nmm": None, "method": "uniaxial_pm3_out_of_range"}

    candidates: list[float] = []
    for (p1, m1), (p2, m2) in zip(curve[:-1], curve[1:]):
        if p1 <= pu_n <= p2:
            if abs(p2 - p1) <= 1.0e-12:
                candidates.append(max(m1, m2))
            else:
                ratio = (pu_n - p1) / (p2 - p1)
                candidates.append(m1 + ratio * (m2 - m1))
    if not candidates:
        nearest = min(curve, key=lambda item: abs(item[0] - pu_n))
        candidates.append(nearest[1])
    capacity = max(candidates)
    if capacity <= 0.0:
        return {"status": "INCOMPLETE", "dcr": None, "capacity_phiMn_Nmm": None, "method": "uniaxial_pm3_zero_capacity"}
    dcr = abs(m3_nmm) / capacity
    return {
        "status": "FAIL" if dcr > 1.0 + 1.0e-12 else "PASS",
        "dcr": dcr,
        "capacity_phiMn_Nmm": capacity,
        "method": "uniaxial_pm3_theta_slice",
    }

def _generated_rebars(geometry: Any, template: Mapping[str, Any]) -> tuple[list[Rebar], RebarMaterial, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    template_id = _text(template.get("Template ID")) or "Rebar template"
    if not bool(template.get("Active", True)):
        return [], RebarMaterial(), [f"{template_id}: longitudinal template is inactive."], []
    if not bool(template.get("Credit inside segment", True)):
        return [], RebarMaterial(), [f"{template_id}: template is not credited for global section strength."], []

    material_name = _text(template.get("Rebar material")) or "SD40"
    material = RebarMaterial(name=material_name, fy_MPa=_float(template.get("fy MPa"), 390.0), Es_MPa=200000.0)
    tables: list[Any] = []

    if bool(template.get("Outer face bars", True)):
        size = _text(template.get("Outer bar size")) or "DB25"
        method = _text(template.get("Outer layout method"))
        result = generate_perimeter_rebar_layout(
            geometry,
            bar_size=size,
            diameter_mm=rebar_diameter_mm(size),
            material=material_name,
            edge_offset_mm=_float(template.get("Outer center offset mm"), 75.0),
            target_spacing_mm=_float(template.get("Outer target spacing mm"), 150.0),
            exact_bar_count=int(_float(template.get("Outer exact bar count"), 4.0)) if method == "By exact bar count" else None,
            label_prefix=f"{template_id}-O",
        )
        errors.extend(result.errors)
        warnings.extend(result.warnings)
        if result.ok:
            tables.append(result.table)

    if bool(template.get("Inner face bars", False)):
        size = _text(template.get("Inner bar size")) or "DB20"
        method = _text(template.get("Inner layout method"))
        result = generate_inner_face_rebar_layout(
            geometry,
            hole_index=0,
            bar_size=size,
            diameter_mm=rebar_diameter_mm(size),
            material=material_name,
            edge_offset_mm=_float(template.get("Inner center offset mm"), 50.0),
            target_spacing_mm=_float(template.get("Inner target spacing mm"), 150.0),
            exact_bar_count=int(_float(template.get("Inner exact bar count"), 4.0)) if method == "By exact bar count" else None,
            label_prefix=f"{template_id}-I",
        )
        errors.extend(result.errors)
        warnings.extend(result.warnings)
        if result.ok:
            tables.append(result.table)

    rebars: list[Rebar] = []
    seen: set[tuple[float, float, float]] = set()
    for table in tables:
        for row in table.to_dict(orient="records"):
            if not bool(row.get("Active", True)):
                continue
            diameter = _float(row.get("Diameter_mm"), rebar_diameter_mm(row.get("Bar Size")))
            key = (round(_float(row.get("x_mm")), 6), round(_float(row.get("y_mm")), 6), round(diameter, 6))
            if key in seen:
                continue
            seen.add(key)
            rebars.append(
                Rebar(
                    x_mm=key[0],
                    y_mm=key[1],
                    diameter_mm=diameter,
                    material_name=material_name,
                    label=_text(row.get("Label")) or None,
                )
            )
    if not rebars and not errors:
        errors.append(f"{template_id}: no credited longitudinal bars were generated.")
    return rebars, material, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _prestress_elements_at_station(
    *,
    geometry: Any,
    section_height_mm: float,
    station_m: float,
    member_length_m: float,
    tendon_system_rows: Any,
    tendon_profile_rows: Any,
    effective_prestress_link: Any,
    prestress_ep_mpa: float,
) -> tuple[list[PrestressElement], list[str], list[str], bool]:
    """Return bonded internal tendon elements and guarded source messages."""

    errors: list[str] = []
    warnings: list[str] = []
    review_required = False
    systems = [row for row in canonical_tendon_system_rows(tendon_system_rows) if bool(row.get("Active"))]
    if not systems:
        return [], errors, ["No active tendon rows were available; PMM capacity uses concrete and any credited ordinary reinforcement only."], True

    link = dict(effective_prestress_link) if isinstance(effective_prestress_link, Mapping) else {}
    fpe = _float(link.get("average_effective_stress_mpa"), 0.0)
    link_ready = bool(link.get("ready")) and fpe > 0.0
    if not link_ready:
        warnings.append("Adopted effective-prestress handoff is not ready; active prestress is omitted from PMM capacity.")
        review_required = True

    system_by_id = {_text(row.get("Tendon ID")): row for row in systems}
    positions = tendon_positions_at_station(
        tendon_profile_rows,
        tendon_system_rows,
        station_m=station_m,
        length_m=member_length_m,
        active_only=True,
    )
    concrete_polygon = to_shapely_polygon(geometry)
    elements: list[PrestressElement] = []
    for position in positions:
        tendon_id = _text(position.get("Tendon ID"))
        system = system_by_id.get(tendon_id)
        if not system:
            continue
        tendon_type = _text(system.get("Type"))
        bond_state = _text(system.get("Bond state"))
        if tendon_type != "Internal" or bond_state != "Bonded after grouting":
            warnings.append(f"{tendon_id}: {tendon_type} / {bond_state} tendon is not included in bonded strain compatibility.")
            review_required = True
            continue
        if not link_ready:
            continue
        x = _float(position.get("x lateral (mm)"))
        y = section_height_mm - _float(position.get("dtop (mm)"))
        if not concrete_polygon.buffer(1.0e-6).covers(Point(x, y)):
            errors.append(f"{tendon_id}: interpolated tendon point at s={station_m:.6f} m is outside concrete.")
            continue
        strands = int(_float(system.get("Strands"), 0.0))
        aps = _float(system.get("Aps/strand mm²"), 0.0)
        fpu = _float(system.get("fpu MPa"), 1860.0)
        if strands <= 0 or aps <= 0.0:
            errors.append(f"{tendon_id}: strand count and Aps/strand must be positive.")
            continue
        total_area = strands * aps
        elements.append(
            PrestressElement(
                id=tendon_id,
                x_mm=x,
                y_mm=y,
                area_mm2=total_area,
                steel_type="tendon_group",
                material_name="ASTM A416 Gr.270 LR",
                fpy_mpa=0.9 * fpu,
                fpu_mpa=fpu,
                ep_mpa=max(_float(prestress_ep_mpa, 195000.0), 1.0),
                pe_eff_n=fpe * total_area,
                bonded=True,
                count=1,
                initial_stress_mpa=fpe,
                label=tendon_id,
            )
        )
    if elements:
        # ACI 22.4.2.3 requires duct/sheathing area in the pure-compression cap;
        # the shared PMM engine currently uses gross geometry, so a non-failing
        # result remains REVIEW rather than certified PASS.
        warnings.append("Bonded internal prestress uses adopted system-average fpe; station/tendon-specific fpe and duct-void Apd are not modeled in the axial cap.")
        review_required = True
    return elements, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings)), review_required


def calculate_crossbeam_uls_flexure(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    rebar_template_rows: Any,
    tendon_system_rows: Any = None,
    tendon_profile_rows: Any = None,
    effective_prestress_link: Any = None,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    prestress_ep_mpa: float = 195000.0,
) -> dict[str, Any]:
    """Calculate station-by-station ACI P-M3 utilization for ULS Final Stage."""

    input_fingerprint = flexure_input_fingerprint(
        foundation=foundation,
        section_definitions=section_definitions,
        rebar_template_rows=rebar_template_rows,
        tendon_system_rows=tendon_system_rows,
        tendon_profile_rows=tendon_profile_rows,
        effective_prestress_link=effective_prestress_link,
        concrete_material=concrete_material,
        concrete_materials=concrete_materials,
        active_concrete_material_name=active_concrete_material_name,
        deck_topping_material_name=deck_topping_material_name,
        prestress_ep_mpa=prestress_ep_mpa,
    )
    mapped_rows = [
        dict(row)
        for row in _records(foundation.get("mapped_rows"))
        if _text(row.get("Dataset")) == DATASET_ULS_FINAL and _text(row.get("Context status")) == "READY"
    ]
    errors: list[str] = []
    warnings: list[str] = []
    if not mapped_rows:
        errors.append("No READY ULS Final Stage station contexts are available.")

    definitions = canonical_section_definitions(section_definitions)
    definitions_by_id = definition_map(definitions)
    templates_by_id = template_map(canonical_rebar_templates(_records(rebar_template_rows)))
    try:
        library = ensure_concrete_material_library(
            concrete_material=concrete_material,
            concrete_materials=concrete_materials,
            active_concrete_material_name=active_concrete_material_name,
            deck_topping_material_name=deck_topping_material_name,
        )
        materials_by_name = concrete_materials_by_name(library.materials)
    except Exception as exc:
        materials_by_name = {}
        errors.append(f"Concrete material library is invalid: {exc}")

    member_length = max(_float(foundation.get("member_length_m"), 0.0), 0.1)
    rows: list[dict[str, Any]] = []
    capacity_cache: dict[str, tuple[Any, list[Rebar], list[PrestressElement], list[str], bool]] = {}

    for source in mapped_rows:
        context_id = _text(source.get("Context ID")) or _text(source.get("Source row"))
        section_id = _text(source.get("Section ID"))
        template_id = _text(source.get("Longitudinal template"))
        definition = definitions_by_id.get(section_id)
        template = templates_by_id.get(template_id)
        if definition is None:
            errors.append(f"{context_id}: Section ID {section_id or 'blank'} is not defined.")
            continue
        if template is None:
            errors.append(f"{context_id}: Longitudinal template {template_id or 'blank'} is not defined/active.")
            continue
        material_name = _text(definition.get("Material"))
        concrete = materials_by_name.get(material_name)
        if concrete is None:
            errors.append(f"{context_id}: concrete material {material_name or 'blank'} is not available.")
            continue

        station = _float(source.get("Station s (m)"))
        params = definition.get("Parameters") if isinstance(definition.get("Parameters"), Mapping) else {}
        height = _float(params.get("height_mm"), 0.0)
        physical_joint = (
            _text(foundation.get("construction_method")).casefold() == "precast segmental"
            and _text(source.get("Boundary type")) == "Physical segment joint"
        )
        cache_key = _fingerprint(
            {
                "section": definition,
                "template": template,
                "station": station,
                "physical_joint_no_ordinary_rebar": physical_joint,
                "tendon_system": canonical_tendon_system_rows(tendon_system_rows),
                "tendon_profile": _records(tendon_profile_rows),
                "effective_link": dict(effective_prestress_link) if isinstance(effective_prestress_link, Mapping) else {},
                "ep": prestress_ep_mpa,
            }
        )
        cached = capacity_cache.get(cache_key)
        if cached is None:
            try:
                geometry = build_geometry_for_definition(definition)
                if physical_joint:
                    rebars = []
                    rebar_material = RebarMaterial(
                        name=_text(template.get("Rebar material")) or "SD40",
                        fy_MPa=_float(template.get("fy MPa"), 390.0),
                        Es_MPa=200000.0,
                    )
                    rebar_errors = []
                    rebar_warnings = [
                        "Ordinary longitudinal rebar is not credited across a Precast Segmental physical joint; tendon continuity governs the interface."
                    ]
                else:
                    rebars, rebar_material, rebar_errors, rebar_warnings = _generated_rebars(geometry, template)
                errors.extend(f"{context_id}: {item}" for item in rebar_errors)
                warnings.extend(f"{context_id}: {item}" for item in rebar_warnings)
                pt_elements, pt_errors, pt_warnings, review_required = _prestress_elements_at_station(
                    geometry=geometry,
                    section_height_mm=height,
                    station_m=station,
                    member_length_m=member_length,
                    tendon_system_rows=tendon_system_rows,
                    tendon_profile_rows=tendon_profile_rows,
                    effective_prestress_link=effective_prestress_link,
                    prestress_ep_mpa=prestress_ep_mpa,
                )
                errors.extend(f"{context_id}: {item}" for item in pt_errors)
                warnings.extend(f"{context_id}: {item}" for item in pt_warnings)
                if rebar_errors or pt_errors:
                    continue
                capacity_cache[cache_key] = (geometry, rebars, pt_elements, [rebar_material], review_required)
                cached = capacity_cache[cache_key]
            except Exception as exc:
                errors.append(f"{context_id}: failed to assemble PMM section input: {exc}")
                continue

        geometry, rebars, pt_elements, rebar_materials, review_required = cached
        pu_n = _float(source.get("P (kN; compression +)")) * 1000.0
        m3_nmm = _float(source.get("M3 (kN-m; sagging +)")) * 1_000_000.0
        load = LoadCase(
            name=_text(source.get("Case / Combination")) or context_id or "ULS",
            Pu_N=pu_n,
            Mux_Nmm=m3_nmm,
            Muy_Nmm=0.0,
            load_type="ULS",
            active=True,
            note="Row-coupled Crossbeam ULS Final Stage P and M3.",
        )
        try:
            analysis_input = AnalysisInput(
                section_geometry=geometry,
                concrete_material=concrete,
                rebar_materials=rebar_materials,
                prestress_materials=[],
                rebars=rebars,
                prestress_elements=pt_elements,
                load_cases=[load],
                settings=AnalysisSettings(
                    code="ACI 318-19",
                    analysis_type="PMM Surface",
                    strength_load_type="ULS",
                    include_rebars=True,
                    include_prestress=bool(pt_elements),
                    use_phi_factor=True,
                    transverse_reinforcement="tied",
                    prestress_stress_model="bilinear",
                    subtract_rebar_displaced_concrete=True,
                    neutral_axis_angle_steps=12,
                    neutral_axis_depth_steps=80,
                    compression_positive=True,
                    note="Crossbeam ULS1A P-M3 B-region sectional check.",
                ),
            )
            pmm = run_rc_pmm_solver(analysis_input)
            check = _uniaxial_pm3_check(pmm, pu_n=pu_n, m3_nmm=m3_nmm)
        except Exception as exc:
            errors.append(f"{context_id}: PMM calculation failed: {exc}")
            continue

        dcr = check.get("dcr")
        phi_mn = check.get("capacity_phiMn_Nmm")
        method = _text(check.get("method"))
        if check.get("status") == "FAIL":
            row_status = "FAIL"
        elif check.get("status") != "PASS" or dcr is None:
            row_status = "INCOMPLETE"
        elif review_required:
            row_status = "REVIEW"
        else:
            row_status = "PASS"
        warnings.extend(f"{context_id}: {item}" for item in getattr(pmm, "warnings", []) or [])

        rows.append(
            {
                "Context ID": context_id,
                "Source row": _text(source.get("Source row")),
                "Case / Combination": _text(source.get("Case / Combination")),
                "Station s (m)": station,
                "Check Point": _text(source.get("Check Point")),
                "Station face": _text(source.get("Station face")),
                "Boundary type": _text(source.get("Boundary type")),
                "Segment / Zone": _text(source.get("Segment / Zone")),
                "Section ID": section_id,
                "Material": material_name,
                "Longitudinal template": template_id,
                "P (kN; compression +)": pu_n / 1000.0,
                "M3 (kN-m; sagging +)": m3_nmm / 1_000_000.0,
                "|M3| demand (kN-m)": abs(m3_nmm) / 1_000_000.0,
                "phiMn at Pu (kN-m)": (phi_mn / 1_000_000.0) if phi_mn is not None else None,
                "P-M3 D/C": dcr,
                "Status": row_status,
                "Capacity method": method,
                "Rebar count": len(rebars),
                "As total (mm²)": sum(bar.area_mm2 for bar in rebars),
                "Bonded tendon groups": len(pt_elements),
                "Aps total (mm²)": sum(item.total_area_mm2 for item in pt_elements),
                "Review required": bool(review_required),
                "Ordinary rebar credited": not physical_joint,
            }
        )

    # One user-facing result per physical joint.  Adjacent Section contexts are
    # evaluated internally and the largest D/C governs; values are not averaged.
    collapsed_rows: list[dict[str, Any]] = []
    joint_groups: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for row in rows:
        if _text(row.get("Boundary type")) == "Physical segment joint":
            key = (_text(row.get("Case / Combination")), round(_float(row.get("Station s (m)")), 9))
            joint_groups.setdefault(key, []).append(row)
        else:
            collapsed_rows.append(row)
    for group in joint_groups.values():
        def _joint_rank(item: Mapping[str, Any]) -> tuple[int, float]:
            status_text = _text(item.get("Status"))
            status_rank = 3 if status_text == "FAIL" else 2 if status_text == "INCOMPLETE" else 1
            dc = _float(item.get("P-M3 D/C"), -math.inf) if item.get("P-M3 D/C") is not None else math.inf
            return status_rank, dc
        governing_joint = dict(max(group, key=_joint_rank))
        governing_joint["Station face"] = ""
        governing_joint["Segment / Zone"] = " / ".join(dict.fromkeys(_text(item.get("Segment / Zone")) for item in group if _text(item.get("Segment / Zone"))))
        governing_joint["Section ID"] = " / ".join(dict.fromkeys(_text(item.get("Section ID")) for item in group if _text(item.get("Section ID"))))
        governing_joint["Internal section contexts"] = len(group)
        governing_joint["Capacity basis"] = "Governing adjacent interface context; ordinary longitudinal rebar not credited across joint"
        collapsed_rows.append(governing_joint)
    rows = sorted(
        collapsed_rows,
        key=lambda row: (_text(row.get("Case / Combination")), _float(row.get("Station s (m)")), _text(row.get("Context ID"))),
    )

    finite_rows = [row for row in rows if row.get("P-M3 D/C") is not None and math.isfinite(_float(row.get("P-M3 D/C"), math.inf))]
    governing = max(finite_rows, key=lambda row: _float(row.get("P-M3 D/C"))) if finite_rows else None
    if errors and not rows:
        status = "SOURCE BLOCKED"
    elif any(_text(row.get("Status")) == "FAIL" for row in rows):
        status = "FAIL"
    elif errors or any(_text(row.get("Status")) == "INCOMPLETE" for row in rows):
        status = "INCOMPLETE"
    elif any(_text(row.get("Status")) == "REVIEW" for row in rows):
        status = "REVIEW"
    elif rows:
        status = "PASS"
    else:
        status = "SOURCE BLOCKED"

    limitations = [
        "ACI 318-19 strain-compatibility B-region sectional interaction check; beam-column joints, anchorage zones, deviators, concentrated-load regions, abrupt section transitions, and other D-regions remain separate checks.",
        "Imported P and M3 are used together from the same ULS Final Stage source row; prestress and secondary prestress are not added to demand again.",
        "Member/global second-order effects, frame stability, development length, tendon anchorage, seismic detailing, shear, and torsion are outside this milestone.",
        "Lines on the result chart connect imported stations for visualization only; no compliance is inferred between unverified stations.",
    ]
    return {
        "schema": CROSSBEAM_ULS_FLEXURE_SCHEMA,
        "input_fingerprint": input_fingerprint,
        "status": status,
        "rows": rows,
        "cases": sorted({_text(row.get("Case / Combination")) for row in rows if _text(row.get("Case / Combination"))}),
        "governing": dict(governing) if governing else None,
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
        "limitations": limitations,
        "sign_convention": "P compression positive; M3 sagging positive.",
        "code_basis": "ACI 318-19 Chapters 21 and 22; strain compatibility with phi-reduced P-M3 capacity.",
        "solver_run": True,
    }

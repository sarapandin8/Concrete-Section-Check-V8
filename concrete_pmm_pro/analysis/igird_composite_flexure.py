"""AASHTO composite positive-flexure preparation for Bridge Precast I-Girders.

IGIRDER.ULS3 deliberately keeps the generic section polygon as the precast
member source of truth.  For Final Composite ULS flexure it builds a temporary
analysis-only concrete polygon consisting of the precast I-girder plus the
*effective* CIP deck rectangle.

AASHTO LRFD 9th Edition Article 5.6.3.2.6 permits nominal flexural resistance of
composite prestressed girder sections with the neutral axis below the deck to be
determined using the deck concrete compressive strength.  Commentary to
Articles 5.6.2.2 / 5.6.3.2.6 describes the lower concrete strength as a
conservative uniform-strength approximation when the compression block spans
both deck and girder concretes.  This module therefore uses the lower of deck
and girder f'c as the temporary uniform strength whenever the two strengths
differ.  It does not mutate the project concrete materials.

The girder-deck interface shear check remains a separate validity gate; this
module prepares section flexural resistance only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from shapely.geometry import box

from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, Rebar, RebarMaterial, SectionGeometry
from concrete_pmm_pro.geometry.summary import summarize_geometry, to_shapely_polygon


DECK_REBAR_MATERIAL_NAME = "Composite deck longitudinal rebar"


@dataclass(frozen=True)
class CompositeFlexurePreparation:
    geometry: SectionGeometry | None
    concrete_material: ConcreteMaterial | None
    deck_rebars: tuple[Rebar, ...]
    deck_rebar_material: RebarMaterial | None
    deck_fc_MPa: float
    girder_fc_MPa: float
    design_fc_MPa: float
    effective_width_mm: float
    deck_thickness_mm: float
    deck_rebar_credit_enabled: bool
    ready: bool
    warnings: tuple[str, ...]
    info: tuple[str, ...]


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def _float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _composite_geometry(precast: SectionGeometry, *, be_mm: float, tslab_mm: float) -> SectionGeometry:
    precast_polygon = to_shapely_polygon(precast)
    if precast_polygon.is_empty or not precast_polygon.is_valid:
        raise ValueError("Precast I-Girder polygon is invalid.")
    y_top = float(precast_polygon.bounds[3])
    deck = box(-0.5 * be_mm, y_top, 0.5 * be_mm, y_top + tslab_mm)
    merged = precast_polygon.union(deck)
    if merged.geom_type != "Polygon" or merged.is_empty or not merged.is_valid:
        raise ValueError("Precast I-Girder plus effective CIP deck did not form one valid composite polygon.")
    outer = [Point2D(x=float(x), y=float(y)) for x, y in list(merged.exterior.coords)[:-1]]
    holes = [
        [Point2D(x=float(x), y=float(y)) for x, y in list(ring.coords)[:-1]]
        for ring in merged.interiors
    ]
    return SectionGeometry(
        name=f"{precast.name} + effective CIP deck",
        outer_polygon=outer,
        holes=holes,
        metadata={
            "preset": "parametric_i_girder_composite_uls",
            "source_section": precast.name,
            "Be_mm": float(be_mm),
            "Tslab_mm": float(tslab_mm),
            "analysis_only": True,
            "code_basis": "AASHTO LRFD 9th 5.6.3.2.6 conservative composite strength section",
        },
    )


def _equivalent_layer_rebar(
    *,
    be_mm: float,
    bar_diameter_mm: float,
    spacing_mm: float,
    y_mm: float,
    label: str,
) -> Rebar | None:
    if not (_finite_positive(be_mm) and _finite_positive(bar_diameter_mm) and _finite_positive(spacing_mm)):
        return None
    bar_area = math.pi * float(bar_diameter_mm) ** 2 / 4.0
    total_area = bar_area * float(be_mm) / float(spacing_mm)
    if total_area <= 0.0:
        return None
    equivalent_diameter = math.sqrt(4.0 * total_area / math.pi)
    return Rebar(
        x_mm=0.0,
        y_mm=float(y_mm),
        diameter_mm=float(equivalent_diameter),
        material_name=DECK_REBAR_MATERIAL_NAME,
        label=label,
    )


def deck_longitudinal_rebars_from_parameters(
    params: Mapping[str, object],
    *,
    precast_geometry: SectionGeometry,
    be_mm: float,
    tslab_mm: float,
) -> tuple[tuple[Rebar, ...], RebarMaterial | None, list[str], list[str]]:
    """Return optional smeared longitudinal deck-rebar layers for +M composite flexure.

    The equivalent bar area is ``Ab * Be / spacing`` at the entered layer depth.
    For uniaxial girder flexure the transverse x-location of individual bars does
    not affect Mx, so a single equivalent bar at x=0 preserves total layer area
    without fabricating edge-bar placement.
    """

    warnings: list[str] = []
    info: list[str] = []
    credit = bool(params.get("deck_long_rebar_credit_positive_mn", False))
    if not credit:
        info.append("Deck longitudinal reinforcement is excluded from positive composite Mn by project selection (conservative default).")
        return (), None, warnings, info

    fy = _float(params.get("deck_long_rebar_fy_MPa"), 0.0)
    es = _float(params.get("deck_long_rebar_Es_MPa"), 200000.0)
    if not (_finite_positive(fy) and _finite_positive(es)):
        warnings.append("Deck longitudinal rebar credit is enabled but fy/Es is not valid; deck rebar is not credited.")
        return (), None, warnings, info

    summary = summarize_geometry(precast_geometry)
    if summary.y_max_mm is None:
        warnings.append("Precast top elevation is unavailable; deck longitudinal rebar cannot be positioned.")
        return (), None, warnings, info
    deck_bottom = float(summary.y_max_mm)
    deck_top = deck_bottom + float(tslab_mm)

    layers: list[Rebar] = []
    for prefix, face in (("top", "Top"), ("bottom", "Bottom")):
        dia = _float(params.get(f"deck_long_rebar_{prefix}_diameter_mm"), 0.0)
        spacing = _float(params.get(f"deck_long_rebar_{prefix}_spacing_mm"), 0.0)
        cover = _float(params.get(f"deck_long_rebar_{prefix}_cover_mm"), 0.0)
        if dia <= 0.0 or spacing <= 0.0:
            continue
        if cover < 0.0:
            warnings.append(f"{face} deck longitudinal rebar cover is negative; layer is not credited.")
            continue
        if prefix == "top":
            y = deck_top - cover - 0.5 * dia
        else:
            y = deck_bottom + cover + 0.5 * dia
        if not (deck_bottom < y < deck_top):
            warnings.append(f"{face} deck longitudinal rebar centroid lies outside the CIP deck; layer is not credited.")
            continue
        layer = _equivalent_layer_rebar(
            be_mm=be_mm,
            bar_diameter_mm=dia,
            spacing_mm=spacing,
            y_mm=y,
            label=f"{face} deck longitudinal rebar · equivalent As over Be",
        )
        if layer is not None:
            layers.append(layer)
            info.append(
                f"{face} deck longitudinal rebar credited as equivalent As={layer.area_mm2:,.1f} mm² over Be={be_mm:,.1f} mm at y={y:,.1f} mm."
            )
    if not layers:
        warnings.append("Deck longitudinal rebar credit is enabled but no valid top/bottom layer is defined; no deck rebar is credited.")
        return (), None, warnings, info
    return (
        tuple(layers),
        RebarMaterial(name=DECK_REBAR_MATERIAL_NAME, fy_MPa=float(fy), Es_MPa=float(es), note="IGIRDER.ULS3 equivalent deck longitudinal layer"),
        warnings,
        info,
    )


def prepare_aashto_composite_positive_flexure(
    *,
    precast_geometry: SectionGeometry | None,
    girder_concrete: ConcreteMaterial | None,
    section_parameters: Mapping[str, object] | None,
) -> CompositeFlexurePreparation:
    """Prepare the analysis-only composite section used for final +Mux strength."""

    params: Mapping[str, object] = section_parameters if isinstance(section_parameters, Mapping) else {}
    warnings: list[str] = []
    info: list[str] = []
    be = _float(params.get("Be_mm"), 0.0)
    tslab = _float(params.get("Tslab_mm"), 0.0)
    deck_fc = _float(params.get("deck_fc_MPa"), 0.0)
    girder_fc = _float(getattr(girder_concrete, "fc_MPa", 0.0), 0.0) if girder_concrete is not None else 0.0
    credit = bool(params.get("deck_long_rebar_credit_positive_mn", False))

    if not isinstance(precast_geometry, SectionGeometry):
        warnings.append("Precast I-Girder geometry is missing.")
    if not isinstance(girder_concrete, ConcreteMaterial):
        warnings.append("Precast I-Girder concrete material is missing.")
    if not _finite_positive(be):
        warnings.append("Effective deck width Be must be positive for Final Composite flexure.")
    if not _finite_positive(tslab):
        warnings.append("CIP deck thickness Tslab must be positive for Final Composite flexure.")
    if not _finite_positive(deck_fc):
        warnings.append("Deck concrete f'c is missing; assign the Deck / topping concrete material in Section Builder.")
    if not _finite_positive(girder_fc):
        warnings.append("Girder concrete f'c is missing.")
    if warnings:
        return CompositeFlexurePreparation(
            geometry=None,
            concrete_material=None,
            deck_rebars=(),
            deck_rebar_material=None,
            deck_fc_MPa=deck_fc,
            girder_fc_MPa=girder_fc,
            design_fc_MPa=0.0,
            effective_width_mm=be,
            deck_thickness_mm=tslab,
            deck_rebar_credit_enabled=credit,
            ready=False,
            warnings=tuple(warnings),
            info=tuple(info),
        )

    assert precast_geometry is not None
    assert girder_concrete is not None
    try:
        geometry = _composite_geometry(precast_geometry, be_mm=be, tslab_mm=tslab)
    except ValueError as exc:
        warnings.append(str(exc))
        geometry = None

    design_fc = min(float(girder_fc), float(deck_fc))
    if deck_fc <= girder_fc + 1.0e-9:
        info.append(
            f"AASHTO LRFD 5.6.3.2.6 composite flexure basis: deck f'c={deck_fc:g} MPa is used for the composite compression section."
        )
    else:
        info.append(
            f"Deck f'c={deck_fc:g} MPa exceeds girder f'c={girder_fc:g} MPa; the lower girder strength {design_fc:g} MPa is used uniformly as the conservative C5.6.2.2 basis."
        )

    composite_concrete = girder_concrete.model_copy(
        update={
            "name": f"Composite strength concrete · conservative f'c={design_fc:g} MPa",
            "fc_MPa": float(design_fc),
            "beta1": None,
            "note": "IGIRDER.ULS3 analysis-only uniform conservative composite strength material; project materials are unchanged.",
        }
    )

    deck_rebars, deck_mat, rebar_warnings, rebar_info = deck_longitudinal_rebars_from_parameters(
        params,
        precast_geometry=precast_geometry,
        be_mm=be,
        tslab_mm=tslab,
    )
    warnings.extend(rebar_warnings)
    info.extend(rebar_info)
    info.append("Girder–deck interface shear remains a separate composite-action acceptance gate and is not included in Mn.")

    return CompositeFlexurePreparation(
        geometry=geometry,
        concrete_material=composite_concrete if geometry is not None else None,
        deck_rebars=deck_rebars,
        deck_rebar_material=deck_mat,
        deck_fc_MPa=float(deck_fc),
        girder_fc_MPa=float(girder_fc),
        design_fc_MPa=float(design_fc),
        effective_width_mm=float(be),
        deck_thickness_mm=float(tslab),
        deck_rebar_credit_enabled=credit,
        ready=geometry is not None,
        warnings=tuple(warnings),
        info=tuple(info),
    )

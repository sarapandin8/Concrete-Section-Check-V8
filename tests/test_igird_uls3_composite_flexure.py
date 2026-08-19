import math
from pathlib import Path

import pytest

from concrete_pmm_pro.analysis.igird_composite_flexure import (
    DECK_REBAR_MATERIAL_NAME,
    deck_longitudinal_rebars_from_parameters,
    prepare_aashto_composite_positive_flexure,
)
from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, SectionGeometry
from concrete_pmm_pro.geometry.summary import summarize_geometry


def _rect_section(width=800.0, depth=1600.0):
    return SectionGeometry(
        name="QA precast girder",
        outer_polygon=[
            Point2D(x=-width / 2, y=0.0),
            Point2D(x=width / 2, y=0.0),
            Point2D(x=width / 2, y=depth),
            Point2D(x=-width / 2, y=depth),
        ],
    )


def _concrete(fc=45.0):
    return ConcreteMaterial(name=f"Girder {fc:g}", fc_MPa=fc)


def test_composite_preparation_builds_effective_deck_and_uses_lower_fc():
    prep = prepare_aashto_composite_positive_flexure(
        precast_geometry=_rect_section(),
        girder_concrete=_concrete(45.0),
        section_parameters={
            "Be_mm": 2400.0,
            "Tslab_mm": 220.0,
            "deck_fc_MPa": 35.0,
        },
    )

    assert prep.ready
    assert prep.design_fc_MPa == pytest.approx(35.0)
    assert prep.deck_fc_MPa == pytest.approx(35.0)
    assert prep.girder_fc_MPa == pytest.approx(45.0)
    assert prep.geometry is not None
    summary = summarize_geometry(prep.geometry)
    assert summary.y_min_mm == pytest.approx(0.0)
    assert summary.y_max_mm == pytest.approx(1820.0)
    assert summary.x_min_mm == pytest.approx(-1200.0)
    assert summary.x_max_mm == pytest.approx(1200.0)
    assert prep.concrete_material is not None
    assert prep.concrete_material.fc_MPa == pytest.approx(35.0)


def test_composite_preparation_uses_lower_girder_fc_when_deck_is_stronger():
    prep = prepare_aashto_composite_positive_flexure(
        precast_geometry=_rect_section(),
        girder_concrete=_concrete(40.0),
        section_parameters={
            "Be_mm": 2400.0,
            "Tslab_mm": 220.0,
            "deck_fc_MPa": 50.0,
        },
    )

    assert prep.ready
    assert prep.design_fc_MPa == pytest.approx(40.0)
    assert any("lower girder strength" in note for note in prep.info)


def test_deck_longitudinal_rebar_is_excluded_by_default():
    rebars, material, warnings, info = deck_longitudinal_rebars_from_parameters(
        {},
        precast_geometry=_rect_section(),
        be_mm=2400.0,
        tslab_mm=220.0,
    )
    assert rebars == ()
    assert material is None
    assert not warnings
    assert any("excluded" in note for note in info)


def test_deck_longitudinal_rebar_credit_builds_equivalent_layer_area_and_depth():
    be = 2400.0
    dia = 16.0
    spacing = 200.0
    cover = 50.0
    rebars, material, warnings, info = deck_longitudinal_rebars_from_parameters(
        {
            "deck_long_rebar_credit_positive_mn": True,
            "deck_long_rebar_fy_MPa": 400.0,
            "deck_long_rebar_Es_MPa": 200000.0,
            "deck_long_rebar_top_diameter_mm": dia,
            "deck_long_rebar_top_spacing_mm": spacing,
            "deck_long_rebar_top_cover_mm": cover,
            "deck_long_rebar_bottom_diameter_mm": 0.0,
            "deck_long_rebar_bottom_spacing_mm": spacing,
            "deck_long_rebar_bottom_cover_mm": cover,
        },
        precast_geometry=_rect_section(),
        be_mm=be,
        tslab_mm=220.0,
    )

    assert not warnings
    assert material is not None
    assert material.name == DECK_REBAR_MATERIAL_NAME
    assert material.fy_MPa == pytest.approx(400.0)
    assert len(rebars) == 1
    expected_as = math.pi * dia**2 / 4.0 * be / spacing
    assert rebars[0].area_mm2 == pytest.approx(expected_as)
    assert rebars[0].y_mm == pytest.approx(1600.0 + 220.0 - cover - dia / 2.0)
    assert any("equivalent As" in note for note in info)


def test_uls3_ui_source_contains_final_composite_calculation_and_guards():
    root = Path(__file__).resolve().parents[1]
    analysis_source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    section_source = (root / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")

    assert "IGIRDER.ULS3A.composite-flexure-audit-closeout" in analysis_source
    assert "Calculate Final Composite Flexure" in analysis_source
    assert "use_aashto_solver=True" in analysis_source
    assert "INTERFACE SHEAR PENDING" in analysis_source
    assert "AASHTO 5.6.3.2.6 applicability" in analysis_source
    assert "Deck longitudinal rebar credit" in analysis_source
    assert "final_command_slot = st.empty()" in analysis_source
    assert "construction_command_slot = st.empty()" in analysis_source
    assert "negative composite flexure" in analysis_source
    assert "Composite Deck Longitudinal Reinforcement" in section_source
    assert "Credit deck longitudinal reinforcement in positive composite Mn" in section_source
    assert "preliminary helper Be remains REVIEW for Final Composite ULS" in section_source


def test_uls3_final_composite_preview_returns_finite_positive_capacity_with_final_prestress():
    import pandas as pd

    from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
    from concrete_pmm_pro.ui.analysis_page import (
        _beam_uls_final_composite_preparation,
        _beam_uls_flexure_preview_dataframe,
    )

    strand_table = pd.DataFrame(
        [
            {
                "Active": True,
                "Group ID": "Bottom strands",
                "No. Strands": 20,
                "Area/Strand_mm2": 140.0,
                "Total Aps_mm2": 2800.0,
                "y_mm_from_bottom": 120.0,
                "Pe_transfer/strand_kN": 150.0,
                "Pe_construction/strand_kN": 140.0,
                "Pe_eff_final/strand_kN": 120.0,
                "Left debond m": 0.0,
                "Right debond m": 0.0,
            }
        ]
    )
    state = {
        "section_geometry": _rect_section(),
        "concrete_material": _concrete(45.0),
        "section_parameters": {
            "composite_enabled": True,
            "Be_mm": 2400.0,
            "Tslab_mm": 220.0,
            "deck_fc_MPa": 35.0,
            "Be_mode": "Manual",
            "Be_strength_verified": True,
        },
        "girder_strand_layout_table": strand_table,
        "rebars": [],
        "rebar_materials": [],
        "prestress_elements": [],
        "prestress_materials": [],
    }
    prep, composite_state, messages = _beam_uls_final_composite_preparation(state)
    assert prep.ready
    assert composite_state is not None
    assert not any("missing" in message.casefold() for message in messages)

    demand = pd.DataFrame(
        [
            {"Active": True, "Station x (m)": 0.0, "Case Name": "ULS", "Mux": 0.0, "Vuy": 0.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
            {"Active": True, "Station x (m)": 10.0, "Case Name": "ULS", "Mux": 3000.0, "Vuy": 0.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
            {"Active": True, "Station x (m)": 20.0, "Case Name": "ULS", "Mux": 0.0, "Vuy": 0.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
        ]
    )
    route = beam_girder_uls_strength_route(
        is_bridge=True,
        is_building=False,
        project_design_code="AASHTO LRFD",
        code_edition="AASHTO LRFD 9th Edition",
    )
    preview, notes = _beam_uls_flexure_preview_dataframe(
        composite_state,
        demand,
        strength_route=route,
        prestress_force_stage="final",
        full_span_capacity=True,
        use_aashto_solver=True,
    )

    governing = preview[pd.to_numeric(preview["Utilization value"], errors="coerce").notna()].copy()
    assert len(governing) == 1
    row = governing.iloc[0]
    assert row["Status"] in {"PASS", "FAIL"}
    assert float(row["Capacity kN-m"]) > 0.0
    assert float(row["Mn nominal kN-m"]) > 0.0
    assert float(row["φ value"]) == pytest.approx(1.0)
    assert math.isfinite(float(row["Neutral axis c mm"]))
    assert float(row["Neutral axis c mm"]) > 0.0
    assert float(row["Neutral axis θ deg"]) == pytest.approx(90.0, abs=1.0e-6)
    assert any("final effective prestress force" in note.casefold() for note in notes)

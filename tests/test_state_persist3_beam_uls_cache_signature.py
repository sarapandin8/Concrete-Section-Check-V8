from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.ui.analysis_page import _BEAM_ULS_INPUT_HASH_KIND, _beam_uls_cache_input_hash


def _bridge_girder_state() -> dict[str, object]:
    return {
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "section_preset_key": "railway_u_girder",
        "section_category": "Precast Composite Girder",
        "girder_section_family": "precast_composite_girder",
        "section_parameters": {"B_mm": 5500.0, "H_mm": 1600.0},
        "beam_girder_shear_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Support",
                "x_start_m": 0.0,
                "x_end_m": 10.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 2,
                "Spacing_mm": 200.0,
                "fy_MPa": 400.0,
            }
        ],
    }


def _active_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": True,
                "Station x (m)": 5.0,
                "Case Name": "Strength I",
                "Mux": 3805.24,
                "Vuy": 1075.99,
                "Tu": 100.0,
            }
        ]
    )


def test_beam_uls_cache_signature_ignores_section_builder_navigation_keys() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD 9th Edition")
    before = _bridge_girder_state()
    after = dict(before)
    after.update(
        {
            "section_has_ordinary_rebar": True,
            "section_has_prestressing_steel": True,
            "reinforcement_flags_preset_key": "railway_u_girder",
            "section_builder_ordinary_rebar_enabled": True,
            "section_builder_prestressing_steel_enabled": True,
            "section_builder_steel_systems_preset_key": "railway_u_girder",
            "section_builder_steel_systems_user_overridden": False,
            "project_metadata": {
                "section_has_ordinary_rebar": True,
                "section_has_prestressing_steel": True,
                "reinforcement_flags_preset_key": "railway_u_girder",
            },
        }
    )

    assert _beam_uls_cache_input_hash(before, _active_df(), strength_route=route) == _beam_uls_cache_input_hash(
        after,
        _active_df(),
        strength_route=route,
    )


def test_beam_uls_cache_signature_changes_when_actual_load_changes() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD 9th Edition")
    base_loads = _active_df()
    changed_loads = _active_df()
    changed_loads.loc[0, "Mux"] = 4000.0

    assert _beam_uls_cache_input_hash(_bridge_girder_state(), base_loads, strength_route=route) != _beam_uls_cache_input_hash(
        _bridge_girder_state(),
        changed_loads,
        strength_route=route,
    )


def test_beam_uls_store_records_cache_signature_kind() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()

    assert '_BEAM_ULS_INPUT_HASH_KIND = "beam_girder_uls_v2"' in source
    assert 'entry["input_hash_kind"] = _BEAM_ULS_INPUT_HASH_KIND' in source
    assert "project_input_hash(st.session_state)" not in source[source.index("def _render_beam_girder_uls_workspace") :]


def test_beam_uls_cache_signature_does_not_hash_raw_section_geometry() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    start = source.index("def _beam_uls_cache_input_hash")
    end = source.index("\n\ndef _beam_uls_manual_cache", start)
    body = source[start:end]

    assert '"section_geometry"' not in body
    assert '"section_properties"' not in body
    assert "_depth > 8" in source


def test_beam_uls_cache_signature_ignores_all_section_subpage_derived_outputs() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD 9th Edition")
    source_table = [
        {
            "Active": True,
            "Label": "B1",
            "x_mm": 0.0,
            "y_mm": -500.0,
            "Bar Size": "DB20",
            "Diameter_mm": 20.0,
            "Material": "SD40",
            "Count": 1,
        }
    ]
    source_prestress = [
        {
            "Active": True,
            "Label": "PS1",
            "Product": "12.7mm strand",
            "x_mm": 0.0,
            "y_mm": -600.0,
            "Area_mm2": 98.7,
            "Pe_eff_kN": 120.0,
        }
    ]
    before = _bridge_girder_state()
    before.update({"rebar_table": source_table, "prestress_table": source_prestress})

    after = dict(before)
    after.update(
        {
            # Section Builder derived/generated state
            "section_geometry": {"heavy": "generated object placeholder"},
            "section_properties": {"A_mm2": 100000.0, "Ix_mm4": 1.0},
            "section_dimensions": [{"label": "B", "value": 5500.0}],
            # Rebar page parser outputs
            "rebars": [{"label": "B1", "area_mm2": 314.159}],
            "rebars_valid_for_analysis": True,
            "rebar_input_mode": "Manual table",
            # Prestress page parser outputs
            "prestress_elements": [{"label": "PS1", "pe_eff_n": 120000.0}],
            "prestress_valid_for_analysis": True,
            "girder_strand_layout_preview_df": [{"not": "source"}],
        }
    )

    assert _beam_uls_cache_input_hash(before, _active_df(), strength_route=route) == _beam_uls_cache_input_hash(
        after,
        _active_df(),
        strength_route=route,
    )


def test_beam_uls_cache_signature_changes_when_source_rebar_table_changes() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD 9th Edition")
    before = _bridge_girder_state()
    before["rebar_table"] = [{"Active": True, "Label": "B1", "x_mm": 0.0, "y_mm": -500.0, "Bar Size": "DB20", "Count": 1}]
    after = dict(before)
    after["rebar_table"] = [{"Active": True, "Label": "B1", "x_mm": 0.0, "y_mm": -500.0, "Bar Size": "DB25", "Count": 1}]

    assert _beam_uls_cache_input_hash(before, _active_df(), strength_route=route) != _beam_uls_cache_input_hash(
        after,
        _active_df(),
        strength_route=route,
    )


def test_beam_uls_cache_signature_uses_source_tables_not_parser_outputs() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    start = source.index("def _beam_uls_cache_input_hash")
    end = source.index("\n\ndef _beam_uls_manual_cache", start)
    body = source[start:end]

    assert '"rebar_table"' in body
    assert '"prestress_table"' in body
    assert '"rebars",' not in body
    assert '"prestress_elements"' not in body
    assert '"rebars_valid_for_analysis"' not in body
    assert '"prestress_valid_for_analysis"' not in body

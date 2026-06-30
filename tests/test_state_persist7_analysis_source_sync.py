from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.state.dirty_state import INPUT_GROUP_KEYS
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_cache_input_hash,
    _beam_uls_sync_source_tables_for_analysis,
)


def test_dirty_state_rebar_prestress_groups_use_source_tables_not_parser_outputs() -> None:
    assert "rebar_table" in INPUT_GROUP_KEYS["Rebar"]
    assert "rebars" not in INPUT_GROUP_KEYS["Rebar"]
    assert "rebars_valid_for_analysis" not in INPUT_GROUP_KEYS["Rebar"]
    assert "prestress_table" in INPUT_GROUP_KEYS["Prestress"]
    assert "prestress_elements" not in INPUT_GROUP_KEYS["Prestress"]
    assert "prestress_valid_for_analysis" not in INPUT_GROUP_KEYS["Prestress"]


def test_beam_uls_analysis_syncs_source_tables_before_hashing() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    workspace_start = source.index("def _render_beam_girder_uls_workspace")
    workspace_body = source[workspace_start:]

    assert "def _beam_uls_sync_source_tables_for_analysis" in source
    assert "_beam_uls_sync_source_tables_for_analysis(st.session_state)" in workspace_body
    assert "Rebar source-table sync skipped" in source
    assert "Prestress source-table sync skipped" in source


def test_beam_uls_source_sync_materializes_rebar_parser_outputs_from_source_table() -> None:
    state: dict[str, object] = {
        "section_has_ordinary_rebar": True,
        "section_has_prestressing_steel": False,
        "rebar_table": pd.DataFrame(
            [
                {
                    "Active": True,
                    "Label": "B1",
                    "x_mm": 0.0,
                    "y_mm": -250.0,
                    "Bar Size": "DB20",
                    "Diameter_mm": 20.0,
                    "Material": "SD40",
                    "Count": 1,
                    "Note": "",
                }
            ]
        ),
    }

    _beam_uls_sync_source_tables_for_analysis(state)

    assert "rebars" in state
    assert len(state["rebars"]) == 1
    assert state["rebars_valid_for_analysis"] is True


def test_beam_uls_hash_is_stable_before_and_after_source_sync_for_same_source_table() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD 9th Edition")
    active_df = pd.DataFrame(
        [
            {
                "Active": True,
                "Station x (m)": 5.0,
                "Case Name": "Strength I",
                "Mux": 100.0,
                "Vuy": 10.0,
                "Tu": 1.0,
            }
        ]
    )
    state: dict[str, object] = {
        "section_preset_key": "railway_u_girder",
        "section_category": "Precast Composite Girder",
        "girder_section_family": "precast_composite_girder",
        "section_parameters": {"B_mm": 5500.0, "H_mm": 1600.0},
        "section_has_ordinary_rebar": True,
        "section_has_prestressing_steel": False,
        "rebar_table": pd.DataFrame(
            [
                {
                    "Active": True,
                    "Label": "B1",
                    "x_mm": 0.0,
                    "y_mm": -250.0,
                    "Bar Size": "DB20",
                    "Diameter_mm": 20.0,
                    "Material": "SD40",
                    "Count": 1,
                    "Note": "",
                }
            ]
        ),
    }

    before = _beam_uls_cache_input_hash(state, active_df, strength_route=route)
    _beam_uls_sync_source_tables_for_analysis(state)
    after = _beam_uls_cache_input_hash(state, active_df, strength_route=route)

    assert before == after

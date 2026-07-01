from pathlib import Path

import streamlit as st

from concrete_pmm_pro.ui import analysis_page as ap

SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text()


def test_qa4_adds_all_stage_limit_profile_control_matrix_before_summary() -> None:
    assert "SLS.STAGE.STRESS.QA4" in SOURCE
    assert "_render_girder_sls4d_all_stage_profile_control_matrix" in SOURCE
    assert "All-stage tensile limit basis control" in SOURCE
    table_block = SOURCE[SOURCE.find("def _render_girder_sls4b_combined_stage_result_table"):SOURCE.find("def _girder_sls_graph_stage_title")]
    assert "_render_girder_sls4d_all_stage_profile_control_matrix()" in table_block
    assert table_block.find("_render_girder_sls4d_all_stage_profile_control_matrix()") < table_block.find("summary_rows")


def test_qa4_apply_engineer_confirmed_sets_temporary_stage_guide_state() -> None:
    st.session_state.clear()
    st.session_state["section_preset_key"] = "railway_u_girder"
    ap._girder_sls_apply_engineer_confirmed_to_temporary_stages()

    for _stage_key, stage_label, _stage_note in ap._beam_sls_stage_tab_specs():
        keys = ap._girder_sls_stage_profile_keys_from_guide_state(stage_label)
        if ap._beam_sls_stage_default_code_limit_stage(stage_label) == ap.STAGE_FINAL_SERVICE:
            assert st.session_state.get(keys["guide_method"]) is None
            continue
        assert st.session_state[keys["guide_enabled"]] is True
        assert st.session_state[keys["guide_method"]] == "Engineer-confirmed bonded auxiliary reinforcement"
        assert st.session_state[keys["bonded_confirm"]] is True
        assert st.session_state[keys["bonded_source"]] == "engineer_confirmed_drawings"


def test_qa4_control_row_reports_current_profile_source() -> None:
    st.session_state.clear()
    st.session_state["analysis_mode_settings"] = {"member_type": "beam_girder"}
    st.session_state["girder_code_loss_fci_mpa"] = 36.0
    stage_label = "Transfer stage"
    ap._girder_sls_apply_stage_profile_control_state(
        stage_label,
        method="Engineer-confirmed bonded auxiliary reinforcement",
        engineer_confirmed=True,
    )

    row = ap._girder_sls_current_stage_profile_control_row(stage_label)

    assert row["Stage"] == stage_label
    assert row["Tension reinforcement condition"] == "Engineer-confirmed bonded auxiliary reinforcement"
    assert row["Confirm drawing source"] is True
    assert row["Current limit"] == "3.480 MPa"
    assert "bonded auxiliary" in row["Current profile"]
    assert row["Source"] == "Engineer-confirmed from drawings"

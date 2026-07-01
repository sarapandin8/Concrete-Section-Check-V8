from pathlib import Path

import streamlit as st

from concrete_pmm_pro.ui import analysis_page as ap

SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text()


def test_qa3_adds_summary_detail_profile_sync_source_of_truth() -> None:
    assert "SLS.STAGE.STRESS.QA3" in SOURCE
    assert "_girder_sls_sync_stage_profile_from_guide_state" in SOURCE
    assert "top Overall SLS table" in SOURCE
    assert "conservative/default profile" in SOURCE
    profile_block = SOURCE[SOURCE.find("def _girder_stage_limit_profile_for_diagram"):SOURCE.find("def _girder_sls_diagram_stress_limit_rows")]
    assert "_girder_sls_sync_stage_profile_from_guide_state" in profile_block
    assert "stage summary" in profile_block
    assert "detail cards" in profile_block
    assert "graph limit lines" in profile_block


def test_qa3_syncs_engineer_confirmed_transfer_profile_before_summary_render() -> None:
    st.session_state.clear()
    st.session_state["analysis_mode_settings"] = {"member_type": "beam_girder"}
    stage_label = "Transfer stage"
    title = ap._girder_sls_full_length_guide_title(stage_label)
    profile_key = ap._girder_sls_diagram_profile_key(stage_label)
    st.session_state[profile_key] = "aashto_transfer_no_aux"
    st.session_state[f"girder_tension_limit_guide_enabled_{title}"] = True
    st.session_state[f"girder_tension_limit_guide_method_{title}"] = "Engineer-confirmed bonded auxiliary reinforcement"
    st.session_state[ap._girder_sls_bonded_confirmation_key(stage_label)] = True

    selected = ap._girder_sls_sync_stage_profile_from_guide_state(
        stage_label,
        code="AASHTO LRFD Bridge",
        limit_stage="Transfer / Release",
    )

    assert selected == "aashto_transfer_bonded_aux"
    assert st.session_state[profile_key] == "aashto_transfer_bonded_aux"
    assert st.session_state[ap._girder_sls_bonded_confirmation_source_key(stage_label)] == "engineer_confirmed_drawings"


def test_qa3_keeps_unconfirmed_bonded_route_conservative_for_summary() -> None:
    st.session_state.clear()
    st.session_state["analysis_mode_settings"] = {"member_type": "beam_girder"}
    stage_label = "Transfer stage"
    title = ap._girder_sls_full_length_guide_title(stage_label)
    profile_key = ap._girder_sls_diagram_profile_key(stage_label)
    st.session_state[profile_key] = "aashto_transfer_bonded_aux"
    st.session_state[f"girder_tension_limit_guide_enabled_{title}"] = True
    st.session_state[f"girder_tension_limit_guide_method_{title}"] = "Engineer-confirmed bonded auxiliary reinforcement"
    st.session_state[ap._girder_sls_bonded_confirmation_key(stage_label)] = False

    selected = ap._girder_sls_sync_stage_profile_from_guide_state(
        stage_label,
        code="AASHTO LRFD Bridge",
        limit_stage="Transfer / Release",
    )

    assert selected == "aashto_transfer_no_aux"
    assert st.session_state[profile_key] == "aashto_transfer_no_aux"
    assert st.session_state[ap._girder_sls_bonded_confirmation_source_key(stage_label)] == "engineer_confirmation_missing"


def test_qa3_stage_decision_row_uses_synced_profile_not_stale_conservative_key() -> None:
    import pandas as pd

    st.session_state.clear()
    st.session_state["analysis_mode_settings"] = {"member_type": "beam_girder"}
    stage_label = "Transfer stage"
    title = ap._girder_sls_full_length_guide_title(stage_label)
    profile_key = ap._girder_sls_diagram_profile_key(stage_label)
    st.session_state[profile_key] = "aashto_transfer_no_aux"
    st.session_state[f"girder_tension_limit_guide_enabled_{title}"] = True
    st.session_state[f"girder_tension_limit_guide_method_{title}"] = "Engineer-confirmed bonded auxiliary reinforcement"
    st.session_state[ap._girder_sls_bonded_confirmation_key(stage_label)] = True
    st.session_state["girder_code_loss_fci_mpa"] = 36.0

    df = pd.DataFrame(
        [
            {
                "Station x (m)": 2.0,
                "Case Name": "SLS-TR",
                "Basis": "Precast gross section",
                "Top total (MPa)": 3.1144,
                "Bottom total (MPa)": -5.145,
                "Max compression (MPa)": -5.145,
                "Max tension (MPa)": 3.1144,
            }
        ]
    )

    row = ap._girder_sls4b_stage_decision_row(df, stage_label, "SLS-TR")

    assert row["Status"] == "Preview PASS"
    assert row["Limit profile key"] == "aashto_transfer_bonded_aux"
    assert row["Limit profile source"] == "Engineer-confirmed from drawings"
    assert 0.89 < float(row["Utilization"]) < 0.90

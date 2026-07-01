from pathlib import Path

from concrete_pmm_pro.ui import analysis_page as ap

SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text()


def test_qa5_adds_governing_lifting_action_review_after_summary_table() -> None:
    assert "SLS.STAGE.STRESS.QA5" in SOURCE
    assert "Governing lifting-stage action review" in SOURCE
    assert "_render_girder_sls5_lifting_action_review" in SOURCE
    table_block = SOURCE[SOURCE.find("def _render_girder_sls4b_combined_stage_result_table"):SOURCE.find("def _girder_sls_graph_stage_title")]
    assert "_render_girder_sls5_lifting_action_review(summary_df)" in table_block
    assert table_block.find("st.dataframe(_clean_girder_sls4b_decision_dataframe(summary_df)") < table_block.find("_render_girder_sls5_lifting_action_review(summary_df)")


def test_qa5_lifting_action_rows_prioritize_design_review_levers() -> None:
    lifting_row = {
        "Status": "Preview FAIL",
        "Controls": "Tension",
        "Station x (m)": 2.0,
        "Fiber": "Top",
        "Actual stress (MPa)": 4.2463,
        "Limit stress (MPa)": 3.48,
        "Utilization": 1.220,
        "Limit profile": "Temporary release — bonded auxiliary reinforcement condition",
        "Limit profile source": "Engineer-confirmed from drawings",
    }

    rows = ap._girder_sls5_lifting_action_review_rows(lifting_row)

    assert len(rows) >= 5
    actions = "\n".join(row["Required action"] for row in rows)
    review_items = "\n".join(row["Review item"] for row in rows)
    why = "\n".join(row["Why it matters"] for row in rows)
    assert "lifting a/L" in actions
    assert "impact factor" in actions
    assert "anchorage/development" in actions
    assert "debonded lengths" in actions
    assert "lifting insert" in actions
    assert "Tension controls at x=2.000 m" in why
    assert "D/C 1.220" in why
    assert "Top auxiliary reinforcement" in review_items

from pathlib import Path

SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text()


def _guide_block() -> str:
    return SOURCE[SOURCE.find("def _render_girder_tension_limit_guidance"):SOURCE.find("def _render_girder_code_limit_preview")]


def test_qa2_exposes_practical_engineer_confirmed_and_model_detected_routes() -> None:
    block = _guide_block()
    assert "SLS.STAGE.STRESS.QA2" in block
    assert "Engineer-confirmed bonded auxiliary reinforcement" in block
    assert "Model-detected active ordinary rebar at tensile face" in block
    assert "Use engineer-confirmed bonded auxiliary reinforcement from design/detailing drawings" in block
    assert "model_detected" in block
    assert "engineer_confirmed_drawings" in block


def test_qa2_does_not_present_external_drawing_confirmation_as_model_verification() -> None:
    block = _guide_block()
    assert "The active ordinary rebar model is not used as the proof source for this stage limit" in block
    assert "Reinforcement basis source" in block
    assert "not model-certified" in block
    assert "final detailing, development, anchorage, and end-zone checks remain separate" in block


def test_qa2_stage_summary_records_bonded_auxiliary_source_label() -> None:
    assert "_girder_sls_bonded_confirmation_source_key" in SOURCE
    assert "_girder_sls_bonded_source_label" in SOURCE
    assert "Engineer-confirmed from drawings" in SOURCE
    assert "Model-detected active rebar at tensile face" in SOURCE

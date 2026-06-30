from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.analysis_modes import analysis_mode_description, analysis_mode_warnings
from concrete_pmm_pro.core.design_code import project_code_capability_cards

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
PROJECT_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "project_page.py").read_text(encoding="utf-8")
LIMITATIONS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "reporting" / "limitations.py").read_text(encoding="utf-8")
WORD_EXPORT_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "reporting" / "word_export.py").read_text(encoding="utf-8")
WORKFLOW_STATUS_DOC = (REPO_ROOT / "docs" / "design" / "workflow_status1.md").read_text(encoding="utf-8")


def test_current_app_caption_uses_product_workspace_wording() -> None:
    assert "Concrete Section Pro" in APP_SOURCE
    assert "Concrete section analysis and design-review workspace" in APP_SOURCE
    assert "Internal units: mm, MPa, N, N-mm" in APP_SOURCE


def test_bridge_beam_girder_mode_describes_guarded_preview_scope_not_placeholder() -> None:
    description = analysis_mode_description(AnalysisModeSettings(member_type="beam_girder"))
    warnings = analysis_mode_warnings(AnalysisModeSettings(member_type="beam_girder"))

    assert "guarded Beam/Girder ULS flexure/shear/torsion gates" in description
    assert any("guarded preview / engineering-review" in warning for warning in warnings)
    assert not any("future workflow placeholder" in warning for warning in warnings)


def test_building_beam_girder_code_capability_is_preview_review_not_planned_placeholder() -> None:
    cards = project_code_capability_cards("ACI 318", "building_beam_girder")
    by_title = {card["title"]: card for card in cards}

    assert by_title["Beam/Girder Checks"]["value"] == "PREVIEW / REVIEW"
    assert "SHEAR.CODE2" in by_title["Beam/Girder Checks"]["detail"]
    assert "guarded preview / engineering-review" in by_title["Beam/Girder Checks"]["detail"]


def test_current_ui_and_report_sources_do_not_call_beam_girder_a_future_placeholder() -> None:
    combined = "\n".join([ANALYSIS_SOURCE, PROJECT_SOURCE, LIMITATIONS_SOURCE, WORD_EXPORT_SOURCE])

    stale_phrases = [
        "Bridge girder ULS flexure/shear/torsion engines are planned",
        "Building ULS design engines remain planned",
        "Beam/Girder design checks are future work and are not implemented in this report",
        "Beam/Girder mode is a future workflow placeholder",
    ]
    for phrase in stale_phrases:
        assert phrase not in combined

    assert "Beam/Girder ULS/SLS preview checks are guarded engineering-review outputs" in WORD_EXPORT_SOURCE
    assert "Beam/Girder flexure, SHEAR.CODE2, TORSION.CODE2, staged SLS stress" in LIMITATIONS_SOURCE


def test_workflow_status1_document_records_no_solver_formula_changes() -> None:
    assert "Do not change PMM, prestress, shear, torsion, SLS stress, deflection/camber, load, or report calculation formulas." in WORKFLOW_STATUS_DOC
    assert "not final code-certified design outputs" in WORKFLOW_STATUS_DOC

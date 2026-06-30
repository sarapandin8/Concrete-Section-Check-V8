from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.ui.rebar_page import (
    SeismicSpacingAdvisorResult,
    _aashto_seismic_advisor_status_metrics,
    _aashto_seismic_required_action_callout_html,
    _strip_html,
)


def _failed_spacing_and_area_result() -> SeismicSpacingAdvisorResult:
    return SeismicSpacingAdvisorResult(
        status="FAIL",
        code_basis="AASHTO LRFD 9th seismic bridge-column advisor",
        s_max_mm=100.0,
        suggested_spacing_mm=100.0,
        governing_limit="0.25 x minimum member dimension",
        criteria=(
            {"Criterion": "0.25 x minimum member dimension", "Value": 100.0, "Basis": "AASHTO 5.11.4.1.5"},
        ),
        spacing_dc=1.50,
        area_dc=5.90,
        provided_transverse_area_mm2=226.2,
        required_transverse_area_mm2=813.9,
        required_transverse_area_y_mm2=1335.6,
        clear_height_mm=4000.0,
        one_sixth_clear_height_mm=666.7,
        max_member_dimension_mm=600.0,
        confinement_min_length_mm=457.2,
        confinement_length_mm=666.7,
        confinement_length_governing="1/6 clear height",
    )


def test_seismic5_fail_status_cards_use_danger_card_class() -> None:
    result = _failed_spacing_and_area_result()
    headline, checks = _aashto_seismic_advisor_status_metrics(
        result,
        spacing_status="FAIL D/C 1.50",
        area_status="FAIL D/C 5.90",
    )
    html = _strip_html(headline + checks)
    assert 'cpmm-rebar-chip danger' in html
    assert "FAIL D/C 1.50" in html
    assert "FAIL D/C 5.90" in html


def test_seismic5_required_action_callout_names_spacing_and_ash_actions() -> None:
    result = _failed_spacing_and_area_result()
    html = _aashto_seismic_required_action_callout_html(result, current_spacing_mm=150.0)
    assert 'cpmm-rebar-action-callout danger' in html
    assert "reduce spacing to ≤ 100 mm" in html
    assert "increase confinement steel" in html
    assert "provided Ash 226.2 mm²" in html
    assert "required 1,335.6 mm²" in html


def test_seismic5_trace_table_is_collapsed_and_status_cards_are_custom_html() -> None:
    source = Path("concrete_pmm_pro/ui/rebar_page.py").read_text(encoding="utf-8")
    assert "AASHTO.COL.SEISMIC5" in source
    assert "Detailed AASHTO 5.11.4 calculation trace" in source
    assert "expanded=False" in source
    assert "_aashto_seismic_advisor_status_metrics" in source
    assert "cpmm-rebar-action-callout" in source

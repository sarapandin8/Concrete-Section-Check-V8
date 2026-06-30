from concrete_pmm_pro.ui.rebar_page import (
    RebarMetric,
    SeismicSpacingAdvisorResult,
    _aashto_seismic_detailing_summary_metrics,
    _aashto_seismic_fail_reason_messages,
    _aashto_seismic_governing_ash_requirement,
)


def _failed_area_result() -> SeismicSpacingAdvisorResult:
    return SeismicSpacingAdvisorResult(
        status="FAIL",
        code_basis="AASHTO LRFD 9th seismic bridge-column advisor",
        s_max_mm=100.0,
        suggested_spacing_mm=100.0,
        governing_limit="0.25 x minimum member dimension",
        criteria=(),
        spacing_dc=1.0,
        area_dc=2.10,
        provided_transverse_area_mm2=402.2,
        required_transverse_area_mm2=516.2,
        required_transverse_area_y_mm2=842.9,
        clear_height_mm=5000.0,
        one_sixth_clear_height_mm=833.333,
        max_member_dimension_mm=600.0,
        confinement_min_length_mm=457.2,
        confinement_length_mm=833.333,
        confinement_length_governing="1/6 clear height",
    )


def test_aashto_seismic_governing_ash_requirement_reports_control_axis() -> None:
    value, axis = _aashto_seismic_governing_ash_requirement(_failed_area_result())
    assert value == 842.9
    assert axis == "y/core depth"


def test_aashto_seismic_fail_reason_explains_provided_less_than_required() -> None:
    messages = _aashto_seismic_fail_reason_messages(_failed_area_result(), current_spacing_mm=100.0)
    assert len(messages) == 1
    assert "provided Ash" in messages[0]
    assert "402.2 mm²" in messages[0]
    assert "842.9 mm²" in messages[0]
    assert "D/C = 2.10" in messages[0]
    assert "Increase effective hoop/cross-tie legs" in messages[0]


def test_aashto_seismic_detailing_summary_calls_for_added_confinement_steel() -> None:
    metrics = _aashto_seismic_detailing_summary_metrics(_failed_area_result(), current_spacing_mm=100.0)
    assert all(isinstance(metric, RebarMetric) for metric in metrics)
    values = {metric.title: metric.value for metric in metrics}
    details = {metric.title: metric.detail for metric in metrics}
    assert values["Spacing action"] == "OK"
    assert values["Required Ash"] == "842.9 mm²"
    assert values["Required action"] == "Add confinement steel"
    assert "Increase effective legs" in details["Required action"]

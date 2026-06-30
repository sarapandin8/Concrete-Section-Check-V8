from __future__ import annotations

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.reporting import (
    build_column_pier_vt_report_package,
    build_report_manifest,
    column_pier_vt_report_tables_to_dataframe,
)
from concrete_pmm_pro.reporting.report_sections import report_sections_to_dataframe
from concrete_pmm_pro.reporting.report_tables import report_tables_to_dataframe
from concrete_pmm_pro.reporting.word_export import build_draft_word_report
from concrete_pmm_pro.ui.analysis_page import (
    _column_pier_combined_vt_check_dataframe,
    _column_pier_combined_vt_controlling_cause,
    _column_pier_combined_vt_governing_tie_info,
    _column_pier_combined_vt_screen_dataframe,
)

from tests.test_aashto_col_vt1 import _analysis_input, _state


def _stored_vt_state() -> dict[str, object]:
    state = _state(spacing_mm=300.0, tu_kNm=80.0)
    state["analysis_mode_settings"] = AnalysisModeSettings(member_type="column_pier_pmm")
    vt_df = _column_pier_combined_vt_check_dataframe(state, _analysis_input())
    state["column_pier_combined_vt_result_df"] = vt_df
    state["column_pier_combined_vt_screen_df"] = _column_pier_combined_vt_screen_dataframe(vt_df)
    state["column_pier_combined_vt_controlling_cause"] = _column_pier_combined_vt_controlling_cause(vt_df)
    state["column_pier_combined_vt_governing_label"] = str(_column_pier_combined_vt_governing_tie_info(vt_df)["label"])
    state["column_pier_combined_vt_scope_guard"] = (
        "Seismic confinement/detailing review remains separate: this V+T gate uses the Control section transverse row only "
        "and does not certify plastic-hinge confinement, hoop anchorage, lap-splice confinement, or seismic detailing."
    )
    state["column_pier_combined_vt_route_label"] = "AASHTO LRFD V+T"
    return state


def test_column_pier_vt_report_package_mirrors_stored_analysis_results() -> None:
    package = build_column_pier_vt_report_package(_stored_vt_state())

    assert package.available is True
    assert set(package.tables()) == {
        "column_pier_vt_report_summary",
        "column_pier_vt_report_results",
        "column_pier_vt_report_audit",
        "column_pier_vt_report_scope_guard",
    }
    assert not package.summary.empty
    assert not package.results.empty
    assert not package.audit.empty
    assert not package.scope_guard.empty
    assert package.results.columns.tolist() == ["Status", "Case", "Dir", "Vu", "Tu", "Stress", "Transv.", "Long. Al", "Source", "D/C"]
    assert package.scope_guard["Status"].str.contains("REVIEW REQUIRED").any()
    assert package.scope_guard["Report Color Semantics"].str.contains("warning / amber", regex=False).any()


def test_column_pier_vt_report_registry_and_manifest_include_tables_and_section() -> None:
    state = _stored_vt_state()
    package = build_column_pier_vt_report_package(state)
    registry = column_pier_vt_report_tables_to_dataframe(package)
    manifest = build_report_manifest(state)
    tables_df = report_tables_to_dataframe(manifest.tables)
    sections_df = report_sections_to_dataframe(manifest.sections)

    assert registry["Table Key"].str.contains("column_pier_vt_report_summary").any()
    assert tables_df["Table Key"].str.contains("column_pier_vt_report_results").any()
    assert bool(tables_df.loc[tables_df["Table Key"] == "column_pier_vt_report_scope_guard", "Available"].iloc[0]) is True
    assert sections_df["Section ID"].str.contains("column_pier_vt_strength_gate").any()
    section = sections_df.loc[sections_df["Section ID"] == "column_pier_vt_strength_gate"].iloc[0]
    assert "column_pier_vt_report_summary" in section["Tables"]
    assert "column_pier_vt_scope" in section["Limitations"]


def test_column_pier_vt_draft_word_report_includes_vt_section_and_scope_guard() -> None:
    state = _stored_vt_state()
    manifest = build_report_manifest(state)
    docx_bytes = build_draft_word_report(manifest, session_state=state)

    assert b"word/document.xml" in docx_bytes
    # The OOXML is compressed, so use the project QA text extractor rather than raw-byte text search.
    from concrete_pmm_pro.reporting.report_qa import extract_docx_text

    text = extract_docx_text(docx_bytes)
    assert "Column/Pier Shear + Torsion Strength Gate" in text
    assert "Column/Pier V+T Summary" in text
    assert "Seismic confinement/detailing" in text
    assert "warning / amber" in text

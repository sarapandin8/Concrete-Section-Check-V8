from __future__ import annotations

import inspect
from io import BytesIO

from docx import Document

import app
from concrete_pmm_pro.reporting.crossbeam_report_qa import build_crossbeam_draft_design_report
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state
from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state
from tests.test_crossbeam_analysis4c7d13_result_summary_integration import _store_all_crossbeam_uls


def test_segmental_report_qa_context_matches_result_summary_and_preserves_joint_scope() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)

    context = app._report_qa_crossbeam_context(state)
    assert context["Construction type"] == "Precast Segmental"
    assert context["Overall status"] == "FAIL"
    assert context["Critical check"] == "ULS Shear + Torsion"
    assert context["Report readiness"] == "Review required"
    assert context["ULS completeness"].startswith("4/4 current")
    assert context["SLS status"] == "PENDING"

    rows = {row["Check"]: row for row in context["ULS rows"]}
    assert rows["Flexure"]["Status"] == "PASS"
    assert "tendon-only" in rows["Flexure"]["Scope"].lower()
    assert rows["Shear"]["Status"] == "REVIEW"
    assert rows["Torsion"]["Status"] == "FAIL"
    assert rows["Shear + Torsion"]["Status"] == "FAIL"
    assert "NOT EVALUATED" in rows["Shear + Torsion"]["Scope"]

    limits = {row["Item"]: row for row in context["Limitation rows"]}
    assert limits["Physical-joint V+T transfer"]["Status"] == "NOT EVALUATED"
    assert limits["SLS report package"]["Status"] == "PENDING"


def test_cip_report_qa_context_marks_physical_segment_joint_not_applicable() -> None:
    state = _store_all_crossbeam_uls(_cip_ready_state())
    context = app._report_qa_crossbeam_context(state)

    assert context["Construction type"] == "Cast-in-Place"
    rows = {row["Check"]: row for row in context["ULS rows"]}
    assert all("physical Segment-joint" in row["Scope"] or row["Check"] == "Flexure" for row in rows.values())
    limits = {row["Item"]: row for row in context["Limitation rows"]}
    assert limits["Physical Segment-joint transfer"]["Status"] == "NOT APPLICABLE"


def test_crossbeam_report_qa_traceability_uses_stored_package_hashes() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)
    trace = app._report_qa_crossbeam_traceability_rows(state)
    assert len(trace) == 4
    assert {row["Check"] for row in trace} == {"Flexure", "Shear", "Torsion", "Shear + Torsion"}
    assert all(row["Result fingerprint"] != "-" for row in trace)
    assert all("Analysis → ULS Strength" in row["Source"] for row in trace)


def test_report_qa_crossbeam_context_and_render_route_do_not_prepare_or_run_solvers() -> None:
    source = "\n".join(
        [
            inspect.getsource(app._report_qa_crossbeam_context),
            inspect.getsource(app._report_qa_crossbeam_traceability_rows),
            inspect.getsource(app._render_report_qa_crossbeam_workspace),
        ]
    )
    assert "run_crossbeam_uls" not in source
    assert "build_crossbeam_uls" not in source
    assert "Calculate" not in source


def test_crossbeam_draft_design_report_is_docx_and_contains_review_sections() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)
    context = app._report_qa_crossbeam_context(state)
    report_bytes = build_crossbeam_draft_design_report(context)

    assert report_bytes[:2] == b"PK"
    document = Document(BytesIO(report_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "DRAFT — NOT FOR ISSUE" in text
    assert "Report Readiness" in text
    assert "Design Basis and Analysis Scope" in text
    assert "Stored ULS Result Evidence" in text
    assert "QA Scope Guards and Limitations" in text
    assert "Stored Result Traceability" in text
    assert "Final Design Report export remains disabled" in text

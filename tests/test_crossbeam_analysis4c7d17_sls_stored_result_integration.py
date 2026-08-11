from __future__ import annotations

import inspect
from io import BytesIO

from docx import Document

import app
from concrete_pmm_pro.analysis.crossbeam_sls_transfer import (
    CROSSBEAM_SERVICE_RESULT_HASH_KEY,
    CROSSBEAM_SERVICE_RESULT_KEY,
    CROSSBEAM_TRANSFER_RESULT_HASH_KEY,
    CROSSBEAM_TRANSFER_RESULT_KEY,
    build_crossbeam_service_stress_preparation,
    build_crossbeam_transfer_stress_preparation,
    run_crossbeam_service_stress,
    run_crossbeam_transfer_stress,
)
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.reporting.crossbeam_report_qa import build_crossbeam_draft_design_report
from tests.test_crossbeam_sls1a_transfer_stress import (
    _base_state,
    _complete_joint_rows,
    _service_row,
)


def _store_crossbeam_sls(*, construction_method: str = "Precast Segmental") -> dict[str, object]:
    state = _base_state(construction_method=construction_method)
    state["analysis_mode_settings"] = AnalysisModeSettings(member_type="portal_frame_crossbeam")
    if construction_method == "Precast Segmental":
        transfer_rows = _complete_joint_rows()
        service_rows = [
            _service_row(station, m3=500.0 if station == 10.0 else 0.0)
            for station in (0.0, 3.0, 7.0, 10.0, 13.0, 17.0, 20.0)
        ]
    else:
        transfer_rows = [
            {
                "Active": True,
                "Station s (m)": float(station),
                "Check Point": "",
                "Case Name": "TR-CIP",
                "Stage": "Transfer stage",
                "P": 5000.0,
                "V2": 0.0,
                "T": 0.0,
                "M3": 250.0 if station == 10 else 0.0,
                "Note": "CIP Transfer total response",
            }
            for station in range(0, 21, 2)
        ]
        service_rows = [
            _service_row(float(station), case="SERV-CIP", p=5000.0, m3=500.0 if station == 10 else 0.0)
            for station in range(0, 21, 2)
        ]
    state["crossbeam_sls_loads_table"] = transfer_rows + service_rows

    transfer_prep = build_crossbeam_transfer_stress_preparation(state)
    assert transfer_prep.ready, transfer_prep.errors
    transfer = run_crossbeam_transfer_stress(transfer_prep)
    state[CROSSBEAM_TRANSFER_RESULT_KEY] = transfer
    state[CROSSBEAM_TRANSFER_RESULT_HASH_KEY] = transfer_prep.fingerprint

    service_prep = build_crossbeam_service_stress_preparation(state)
    assert service_prep.ready, service_prep.errors
    service = run_crossbeam_service_stress(service_prep)
    state[CROSSBEAM_SERVICE_RESULT_KEY] = service
    state[CROSSBEAM_SERVICE_RESULT_HASH_KEY] = service_prep.fingerprint
    return state


def test_crossbeam_sls_results_store_explicit_construction_ownership() -> None:
    state = _store_crossbeam_sls(construction_method="Precast Segmental")
    assert state[CROSSBEAM_TRANSFER_RESULT_KEY]["construction_method"] == "Precast Segmental"
    assert state[CROSSBEAM_SERVICE_RESULT_KEY]["construction_method"] == "Precast Segmental"


def test_crossbeam_sls_summary_reads_transfer_and_final_service_stored_packages() -> None:
    state = _store_crossbeam_sls()
    rows = app._results_crossbeam_sls_summary_rows(state)

    assert [row["Check"] for row in rows] == ["At Transfer", "At Final Service"]
    assert all(row["Module"] == "SLS Crossbeam" for row in rows)
    assert all(row["__calculated"] for row in rows)
    assert all(row["__stored"] for row in rows)
    assert all("Analysis → SLS / Stress & Cracking" in row["Source"] for row in rows)
    assert rows[0]["Governing Check"] != "-"
    assert rows[0]["D/C / Util."] != "-"
    assert rows[1]["Governing Check"] != "-"
    assert rows[1]["D/C / Util."] != "-"

    assert app._results_crossbeam_sls_completion(state) == (2, 2, [])
    assert app._results_sls_stress_available(state) is True
    # Deflection / Camber remains the intentional final Crossbeam SLS report gate.
    assert app._results_sls_complete_for_report(state) is False


def test_crossbeam_sls_construction_switch_marks_stored_stages_stale() -> None:
    state = _store_crossbeam_sls(construction_method="Cast-in-Place")
    state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = "Precast Segmental"

    rows = app._results_crossbeam_sls_summary_rows(state)
    assert {row["Status"] for row in rows} == {"STALE"}
    assert all(not row["__calculated"] for row in rows)
    assert all(row["__stored"] for row in rows)
    assert app._results_crossbeam_sls_completion(state) == (0, 2, ["At Transfer", "At Final Service"])


def test_report_qa_context_exposes_current_sls_stress_and_keeps_deflection_pending() -> None:
    state = _store_crossbeam_sls()
    context = app._report_qa_crossbeam_context(state)

    assert "Stress & Cracking 2/2 current" in context["SLS status"]
    assert "Deflection/Camber PENDING" in context["SLS status"]
    sls_rows = {row["Check"]: row for row in context["SLS rows"]}
    assert set(sls_rows) == {"At Transfer", "At Final Service"}
    assert all(row["Status"] != "NOT CALCULATED" for row in sls_rows.values())

    limitations = {row["Item"]: row for row in context["Limitation rows"]}
    assert limitations["SLS Stress & Cracking"]["Status"] == "CURRENT"
    assert limitations["SLS Deflection / Camber"]["Status"] == "PENDING"

    trace = app._report_qa_crossbeam_traceability_rows(state)
    sls_trace = [row for row in trace if str(row["Check"]).startswith("SLS ")]
    assert len(sls_trace) == 2
    assert all(row["Result fingerprint"] != "-" for row in sls_trace)


def test_report_source_fingerprint_includes_crossbeam_sls_packages() -> None:
    state = _store_crossbeam_sls()
    before = app._report_qa_crossbeam_source_fingerprint(state)
    state[CROSSBEAM_SERVICE_RESULT_HASH_KEY] = "changed-service-fingerprint"
    after = app._report_qa_crossbeam_source_fingerprint(state)
    assert before != after


def test_draft_design_report_contains_stored_sls_evidence_and_pending_deflection_scope() -> None:
    state = _store_crossbeam_sls()
    context = app._report_qa_crossbeam_context(state)
    report_bytes = build_crossbeam_draft_design_report(context)
    document = Document(BytesIO(report_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert "Stored SLS Stress & Cracking Evidence" in text
    assert "Crossbeam SLS Deflection / Camber remains a separate pending serviceability route" in text


def test_crossbeam_sls_downstream_routes_are_read_only() -> None:
    source = "\n".join(
        [
            inspect.getsource(app._results_crossbeam_sls_summary_rows),
            inspect.getsource(app._results_crossbeam_sls_summary_row),
            inspect.getsource(app._report_qa_crossbeam_context),
            inspect.getsource(app._render_report_qa_crossbeam_sls_evidence),
        ]
    )
    assert "run_crossbeam_transfer_stress" not in source
    assert "run_crossbeam_service_stress" not in source
    assert "build_crossbeam_transfer_stress_preparation" not in source
    assert "build_crossbeam_service_stress_preparation" not in source

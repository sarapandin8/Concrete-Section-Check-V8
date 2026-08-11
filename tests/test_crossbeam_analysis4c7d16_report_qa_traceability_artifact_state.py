from __future__ import annotations

import app


def _synthetic_crossbeam_state() -> dict[str, object]:
    state: dict[str, object] = {
        "analysis_mode_settings": app.AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        app.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
    }
    for check_name, hash_key in app._RESULTS_CROSSBEAM_ULS_HASH_KEYS.items():
        state[hash_key] = f"stored-{check_name}"
    return state


def test_report_artifact_state_distinguishes_not_generated_current_and_stale() -> None:
    state = _synthetic_crossbeam_state()

    artifact = app._report_qa_crossbeam_artifact_state(state)
    assert artifact["state"] == "NOT GENERATED"

    state[app._CROSSBEAM_REPORT_QA_DRAFT_DOCX_KEY] = b"PK-draft"
    assert app._report_qa_crossbeam_artifact_state(state)["state"] == "OUT OF DATE"

    source_fingerprint = app._report_qa_crossbeam_source_fingerprint(state)
    state[app._CROSSBEAM_REPORT_QA_DRAFT_SOURCE_FINGERPRINT_KEY] = source_fingerprint
    assert app._report_qa_crossbeam_artifact_state(state)["state"] == "CURRENT"

    state[app._RESULTS_CROSSBEAM_ULS_HASH_KEYS["Flexure"]] = "changed-result-package"
    assert app._report_qa_crossbeam_artifact_state(state)["state"] == "OUT OF DATE"


def test_report_qa_sls_scope_mentions_both_serviceability_report_routes() -> None:
    state = _synthetic_crossbeam_state()
    limits = {row["Item"]: row for row in app._report_qa_crossbeam_limitation_rows(state)}
    sls = limits["SLS report package"]["Engineering meaning"]
    assert "SLS Stress & Cracking" in sls
    assert "SLS Deflection / Camber" in sls
    assert "final Design Report issue remains unavailable" in sls


def test_traceability_renderer_uses_artifact_state_not_legacy_report_status() -> None:
    import inspect

    source = inspect.getsource(app._render_report_qa_crossbeam_traceability)
    assert "Report artifact state" in source
    assert "Current report-source fingerprint" in source
    assert "Last built report-source fingerprint" in source
    assert "dirty.report_status" not in source


def test_export_requires_current_source_fingerprint_before_download() -> None:
    import inspect

    source = inspect.getsource(app._render_report_qa_crossbeam_export)
    assert "OUT OF DATE" in source
    assert "Rebuild it before export" in source
    assert "_CROSSBEAM_REPORT_QA_DRAFT_SOURCE_FINGERPRINT_KEY" in source
    assert 'artifact["state"] == "CURRENT"' in source

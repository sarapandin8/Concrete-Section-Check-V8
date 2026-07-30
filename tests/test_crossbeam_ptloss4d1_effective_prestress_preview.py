from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.ui import crossbeam_pages


def _source_rows() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    friction_rows: list[dict[str, object]] = []
    anchorage_rows: list[dict[str, object]] = []
    after_es_rows: list[dict[str, object]] = []
    for tendon_id, aps in (("T1", 1000.0), ("T2", 2000.0)):
        for station, friction, anchor in ((0.0, 10.0, 2.0), (20.0, 20.0, 4.0)):
            base = {
                "Tendon ID": tendon_id,
                "Active": True,
                "s (m)": station,
                "Point": "P0" if station == 0.0 else "P1",
                "Aps total (mm²)": aps,
                "fpj (MPa)": 1400.0,
                "Friction loss (MPa)": friction,
            }
            friction_rows.append(dict(base))
            anchorage_rows.append({**base, "Anchorage-set loss (MPa)": anchor})
            after_es_rows.append(
                {
                    **base,
                    "Anchorage-set loss (MPa)": anchor,
                    "Elastic-shortening loss (MPa)": 5.0,
                    "Stress after ES (MPa)": 1400.0 - friction - anchor - 5.0,
                }
            )
    return friction_rows, anchorage_rows, after_es_rows


def test_ptloss4d1_separates_average_system_loss_from_maximum_local_loss() -> None:
    friction_rows, anchorage_rows, after_es_rows = _source_rows()
    payload = crossbeam_pages._crossbeam_loss_summary_payload(
        length_m=20.0,
        friction_rows=friction_rows,
        anchorage_station_rows=anchorage_rows,
        lightweight_result={"after_es_station_rows": after_es_rows},
        lightweight_status="CURRENT",
        td_result={
            "ready": True,
            "creep_loss_mpa": 30.0,
            "shrinkage_loss_mpa": 10.0,
            "relaxation_loss_mpa": 5.0,
        },
        td_status="CURRENT",
    )

    assert payload["average_total_loss_mpa"] == pytest.approx(68.0)
    assert payload["average_total_loss_percent"] == pytest.approx(100.0 * 68.0 / 1400.0)
    assert payload["max_local_loss_mpa"] == pytest.approx(74.0)
    assert payload["max_local_loss_percent"] == pytest.approx(100.0 * 74.0 / 1400.0)
    assert len(payload["max_local_rows"]) == 2
    assert all(row["Station s (m)"] == pytest.approx(20.0) for row in payload["max_local_rows"])


def test_ptloss4d1_effective_prestress_preview_closes_stress_and_force_chain() -> None:
    friction_rows, anchorage_rows, after_es_rows = _source_rows()
    payload = crossbeam_pages._crossbeam_loss_summary_payload(
        length_m=20.0,
        friction_rows=friction_rows,
        anchorage_station_rows=anchorage_rows,
        lightweight_result={"after_es_station_rows": after_es_rows},
        lightweight_status="CURRENT",
        td_result={
            "ready": True,
            "creep_loss_mpa": 30.0,
            "shrinkage_loss_mpa": 10.0,
            "relaxation_loss_mpa": 5.0,
        },
        td_status="CURRENT",
    )

    assert payload["effective_preview_ready"] is True
    assert payload["average_effective_stress_mpa"] == pytest.approx(1332.0)
    assert payload["initial_total_force_kn"] == pytest.approx(4200.0)
    assert payload["average_effective_force_kn"] == pytest.approx(3996.0)
    assert payload["average_force_loss_kn"] == pytest.approx(204.0)
    assert payload["min_local_fpe_mpa"] == pytest.approx(1326.0)
    assert payload["max_stress_closure_mpa"] == pytest.approx(0.0, abs=1.0e-12)
    assert payload["max_force_closure_kn"] == pytest.approx(0.0, abs=1.0e-12)
    assert len(payload["effective_station_rows"]) == 4
    assert len(payload["system_station_rows"]) == 2
    assert all(abs(row["Force closure (kN)"]) <= 1.0e-12 for row in payload["system_station_rows"])


def test_ptloss4d1_tab_order_and_final_handoff_guard_are_explicit() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    tab_block = source.split(") = st.tabs(", 1)[1].split("]\n    )", 1)[0]
    labels = [
        '"Friction & Wobble"',
        '"Anchorage Set / Draw-in"',
        '"Elastic Shortening"',
        '"Time-Dependent"',
        '"Loss Summary"',
        '"Effective Prestress"',
        '"Audit"',
    ]
    positions = [tab_block.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "Effective Prestress & External-FEA Handoff" in source
    assert "HANDOFF AVAILABLE · SLS PENDING" in source
    assert "External FEA / SLS" in source
    assert "import verified FEA SLS P/V2/M3 through Loads" in source
    assert "Average total accounted loss — QA" in source
    assert "Maximum local accounted loss" in source


def test_ptloss4d1_no_event_scope_guard_does_not_claim_an_imported_later_load() -> None:
    source = Path("concrete_pmm_pro/crossbeam/event_stage_stress.py").read_text(encoding="utf-8")
    assert "No later permanent-load response is adopted; Δf_cd = 0.0000 MPa" in source

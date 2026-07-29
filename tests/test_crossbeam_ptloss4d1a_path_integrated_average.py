from __future__ import annotations

import pytest

from concrete_pmm_pro.ui import crossbeam_pages


def test_projected_station_average_uses_nonuniform_trapezoids_and_collapses_duplicates() -> None:
    rows = [
        {"Station s (m)": 0.0, "fpe preview (MPa)": 1000.0},
        {"Station s (m)": 5.0, "fpe preview (MPa)": 1090.0},
        {"Station s (m)": 5.0, "fpe preview (MPa)": 1110.0},
        {"Station s (m)": 20.0, "fpe preview (MPa)": 1300.0},
    ]

    trace = crossbeam_pages._projected_station_path_average_trace(
        rows,
        "fpe preview (MPa)",
        length_m=20.0,
        station_keys=("Station s (m)",),
    )

    # Duplicate rows at s=5 m collapse to 1100 MPa before integration.
    expected = (
        0.5 * (1000.0 + 1100.0) * 5.0
        + 0.5 * (1100.0 + 1300.0) * 15.0
    ) / 20.0
    assert trace["average"] == pytest.approx(expected)
    assert trace["point_count"] == 3
    assert trace["duplicate_row_count"] == 1
    assert trace["covered_length_m"] == pytest.approx(20.0)
    assert trace["complete_projected_coverage"] is True


def test_projected_station_average_is_invariant_to_inserted_linear_points() -> None:
    original = [
        {"Station s (m)": 0.0, "value": 1000.0},
        {"Station s (m)": 20.0, "value": 1400.0},
    ]
    refined = [
        {"Station s (m)": 0.0, "value": 1000.0},
        {"Station s (m)": 3.0, "value": 1060.0},
        {"Station s (m)": 13.0, "value": 1260.0},
        {"Station s (m)": 20.0, "value": 1400.0},
    ]

    original_avg = crossbeam_pages._tendon_path_average_mpa(
        original,
        "value",
        length_m=20.0,
        station_keys=("Station s (m)",),
    )
    refined_avg = crossbeam_pages._tendon_path_average_mpa(
        refined,
        "value",
        length_m=20.0,
        station_keys=("Station s (m)",),
    )

    assert original_avg == pytest.approx(1200.0)
    assert refined_avg == pytest.approx(original_avg)


def test_effective_prestress_system_average_closes_against_component_average() -> None:
    friction_rows: list[dict[str, object]] = []
    anchorage_rows: list[dict[str, object]] = []
    after_es_rows: list[dict[str, object]] = []
    for station, friction in ((0.0, 0.0), (10.0, 10.0), (20.0, 0.0)):
        base = {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": station,
            "Point": f"P{int(station)}",
            "Aps total (mm²)": 1000.0,
            "fpj (MPa)": 1400.0,
            "Friction loss (MPa)": friction,
        }
        friction_rows.append(dict(base))
        anchorage_rows.append({**base, "Anchorage-set loss (MPa)": 2.0})
        after_es_rows.append(
            {
                **base,
                "Anchorage-set loss (MPa)": 2.0,
                "Elastic-shortening loss (MPa)": 3.0,
                "Stress after ES (MPa)": 1400.0 - friction - 2.0 - 3.0,
            }
        )

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

    # Trapezoidal friction average = 5 MPa, so total average loss = 5+2+3+45 = 55 MPa.
    assert payload["average_total_loss_mpa"] == pytest.approx(55.0)
    assert payload["average_effective_stress_mpa"] == pytest.approx(1345.0)
    assert payload["average_effective_stress_mpa"] != pytest.approx(
        sum(row["fpe preview (MPa)"] for row in payload["effective_station_rows"]) / 3.0
    )
    assert payload["average_effective_force_kn"] == pytest.approx(1345.0)
    assert payload["average_force_loss_kn"] == pytest.approx(55.0)
    assert payload["average_stress_closure_mpa"] == pytest.approx(0.0, abs=1.0e-12)
    assert payload["average_force_closure_kn"] == pytest.approx(0.0, abs=1.0e-12)
    assert payload["projected_coverage_ready"] is True
    assert payload["effective_preview_ready"] is True
    assert payload["effective_path_average_rows"][0]["Coverage status"] == "COMPLETE"


def test_effective_preview_blocks_incomplete_projected_station_coverage() -> None:
    friction_rows = [
        {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": station,
            "Point": "P",
            "Aps total (mm²)": 1000.0,
            "fpj (MPa)": 1400.0,
            "Friction loss (MPa)": 0.0,
        }
        for station in (2.0, 18.0)
    ]
    anchorage_rows = [
        {**row, "Anchorage-set loss (MPa)": 0.0} for row in friction_rows
    ]
    after_es_rows = [
        {
            **row,
            "Anchorage-set loss (MPa)": 0.0,
            "Elastic-shortening loss (MPa)": 0.0,
            "Stress after ES (MPa)": 1400.0,
        }
        for row in friction_rows
    ]

    payload = crossbeam_pages._crossbeam_loss_summary_payload(
        length_m=20.0,
        friction_rows=friction_rows,
        anchorage_station_rows=anchorage_rows,
        lightweight_result={"after_es_station_rows": after_es_rows},
        lightweight_status="CURRENT",
        td_result={
            "ready": True,
            "creep_loss_mpa": 1.0,
            "shrinkage_loss_mpa": 1.0,
            "relaxation_loss_mpa": 1.0,
        },
        td_status="CURRENT",
    )

    assert payload["projected_coverage_ready"] is False
    assert payload["effective_preview_ready"] is False
    assert payload["effective_status"] == "SOURCE BLOCKED"

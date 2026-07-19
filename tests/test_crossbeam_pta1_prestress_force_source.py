from __future__ import annotations

import inspect

import pytest

from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_analysis import (
    tendon_force_source_rows,
    tendon_force_source_summary,
    tendon_force_trace_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    render_crossbeam_tendon_profile_page,
    render_crossbeam_tendon_system_page,
)


def _geometry_context():
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    return definitions, segments


def test_pta1_default_force_source_derives_pj_without_doubling_both_end_jacking() -> None:
    rows = tendon_force_source_rows(default_tendon_system_rows())

    assert len(rows) == 8
    assert {row["Force source status"] for row in rows} == {"SOURCE READY"}
    assert {row["Area source"] for row in rows} == {"Strands x Aps/strand"}
    assert {row["Jacking end"] for row in rows} == {"Both"}
    assert rows[0]["Aps total (mm²)"] == pytest.approx(19 * 140.0)
    assert rows[0]["fpj (MPa)"] == pytest.approx(1860.0 * 0.75)
    assert rows[0]["Pj (kN)"] == pytest.approx(19 * 140.0 * 1860.0 * 0.75 / 1000.0)
    assert rows[0]["Active Pj credit (kN)"] == pytest.approx(rows[0]["Pj (kN)"])


def test_pta1_force_summary_counts_only_ready_active_tendon_credit() -> None:
    system = default_tendon_system_rows(4)
    system[1]["Active"] = False
    system[2]["fpj/fpu"] = 1.10

    rows = tendon_force_source_rows(system)
    summary = tendon_force_source_summary(rows)

    assert rows[1]["Force source status"] == "STORED ONLY"
    assert rows[1]["Active Pj credit (kN)"] == 0.0
    assert rows[2]["Force source status"] == "REVIEW REQUIRED"
    assert "fpj/fpu" in rows[2]["Issue"]
    assert summary["value"] == "REVIEW REQUIRED"
    assert summary["review_count"] == 1
    assert summary["active_count"] == 3
    assert summary["active_pj_total_kN"] == pytest.approx(
        rows[0]["Pj (kN)"] + rows[3]["Pj (kN)"]
    )


def test_pta1_duplicate_tendon_id_blocks_force_source_credit() -> None:
    system = default_tendon_system_rows(3)
    system[1]["Tendon ID"] = "T1"

    rows = tendon_force_source_rows(system)
    duplicate_rows = [row for row in rows if row["Tendon ID"] == "T1"]

    assert len(duplicate_rows) == 2
    assert {row["Force source status"] for row in duplicate_rows} == {
        "REVIEW REQUIRED"
    }
    assert all("Duplicate Tendon ID" in row["Issue"] for row in duplicate_rows)


def test_pta1_force_trace_joins_pj_to_profile_station_rows() -> None:
    definitions, segments = _geometry_context()
    system = default_tendon_system_rows(3)
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )

    trace = tendon_force_trace_rows(
        profile,
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )
    t1_rows = [row for row in trace if row["Tendon ID"] == "T1"]

    assert t1_rows
    assert {row["Force source status"] for row in t1_rows} == {"SOURCE READY"}
    assert {round(row["Pj (kN)"], 6) for row in t1_rows} == {
        round(19 * 140.0 * 1860.0 * 0.75 / 1000.0, 6)
    }
    assert any(row["Point"] == "P2" and row["Station face"] for row in t1_rows)


def test_pta1_ui_exposes_force_source_without_claiming_losses_or_solver_results() -> None:
    system_source = inspect.getsource(render_crossbeam_tendon_system_page)
    profile_source = inspect.getsource(render_crossbeam_tendon_profile_page)

    assert "Prestress force source audit" in system_source
    assert "Pj = Aps total x fpj / 1000" in system_source
    assert "tendon_force_source_rows" in system_source
    assert "Prestress force station trace" in profile_source
    assert "tendon_force_trace_rows" in profile_source
    assert "Both-end jacking does not double Pj" in profile_source
    assert "loss calculations" in system_source
    assert "SLS/ULS checks" in system_source

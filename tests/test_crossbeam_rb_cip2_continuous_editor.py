from __future__ import annotations

from concrete_pmm_pro.crossbeam.cip_rebar import (
    canonical_cip_longitudinal_bar_runs,
    cip_bar_run_zone_intersections,
    cip_longitudinal_runs_at_station,
    cip_rebar_topology_status,
    new_cip_longitudinal_bar_run,
    validate_cip_longitudinal_bar_runs,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    crossbeam_layout_navigation_label,
)
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _cip_editor_select_options,
    _cip_run_rows_from_editor_rows,
)


def _run(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Active": True,
        "Run ID": "TOP-01",
        "s_start_m": 0.0,
        "s_end_m": 20.0,
        "Bar group": "Top continuous bars",
        "Layer / face": "Top",
        "Bar size": "DB32",
        "Material": "SD50",
        "Definition basis": "By exact bar count",
        "Bar count": 8,
        "Target spacing mm": 0.0,
        "Start intent": "Member end / anchorage region",
        "End intent": "Member end / anchorage region",
        "Notes": "",
    }
    row.update(overrides)
    return row


def _zones() -> list[dict[str, object]]:
    return [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 4.0, "Section ID": "CB-S01"},
        {"Segment": "Z2", "x_start_m": 4.0, "x_end_m": 16.0, "Section ID": "CB-S02"},
        {"Segment": "Z3", "x_start_m": 16.0, "x_end_m": 20.0, "Section ID": "CB-S01"},
    ]


def test_layout_navigation_label_changes_semantics_not_route_model() -> None:
    assert crossbeam_layout_navigation_label(CONSTRUCTION_METHOD_PRECAST) == "Segment Layout"
    assert crossbeam_layout_navigation_label(CONSTRUCTION_METHOD_CIP) == "Section / Zone Layout"
    assert crossbeam_layout_navigation_label("unknown") == "Segment Layout"


def test_add_draft_run_is_explicit_and_not_solver_ready() -> None:
    draft1 = new_cip_longitudinal_bar_run([], length_m=20.0)
    draft2 = new_cip_longitudinal_bar_run([draft1], length_m=20.0)

    assert draft1["Run ID"] == "CIP-R1"
    assert draft2["Run ID"] == "CIP-R2"
    assert draft1["s_start_m"] == 0.0
    assert draft1["s_end_m"] == 20.0
    assert draft1["Bar size"] == ""
    assert draft1["Material"] == ""
    assert draft1["Bar count"] == 0

    status = cip_rebar_topology_status([draft1], length_m=20.0)
    assert status["status"] == "REVIEW REQUIRED"
    assert status["solver_handoff"] == "LOCKED"


def test_continuous_run_crosses_zone_boundaries_without_being_split() -> None:
    run = canonical_cip_longitudinal_bar_runs([_run()])[0]
    assert cip_bar_run_zone_intersections(run, _zones()) == ["Z1", "Z2", "Z3"]

    # A run ending exactly at the Z1/Z2 boundary occupies Z1 only; touching the
    # adjacent zone is not treated as a second occupied zone.
    end_at_boundary = canonical_cip_longitudinal_bar_runs(
        [_run(**{"Run ID": "TOP-END", "s_end_m": 4.0})]
    )[0]
    assert cip_bar_run_zone_intersections(end_at_boundary, _zones()) == ["Z1"]


def test_station_participation_reads_continuous_runs_independently_of_zones() -> None:
    rows = [
        _run(**{"Run ID": "FULL", "s_start_m": 0.0, "s_end_m": 20.0}),
        _run(**{"Run ID": "SUPPORT", "s_start_m": 0.0, "s_end_m": 5.0}),
        _run(**{"Run ID": "INACTIVE", "Active": False, "s_start_m": 0.0, "s_end_m": 20.0}),
    ]

    assert [row["Run ID"] for row in cip_longitudinal_runs_at_station(rows, station_m=2.0)] == ["FULL", "SUPPORT"]
    assert [row["Run ID"] for row in cip_longitudinal_runs_at_station(rows, station_m=10.0)] == ["FULL"]


def test_editor_derives_bar_diameter_and_fy_instead_of_duplicating_editable_state() -> None:
    rows = _cip_run_rows_from_editor_rows(
        [
            {
                "Active": True,
                "Run ID": "TOP-01",
                "s_start (m)": 0.0,
                "s_end (m)": 20.0,
                "Bar group": "Top continuous bars",
                "Layer / face": "Top",
                "Bar size": "DB32",
                "Material": "SD50",
                "Definition basis": "By exact bar count",
                "Bar count": 8,
                "Target spacing (mm)": 0.0,
                "Start intent": "Member end / anchorage region",
                "End intent": "Member end / anchorage region",
                "Notes": "QA",
            }
        ]
    )

    assert rows[0]["Bar diameter mm"] == 32.0
    assert rows[0]["fy MPa"] == 490.0
    assert rows[0]["s_start_m"] == 0.0
    assert rows[0]["s_end_m"] == 20.0


def test_standard_bar_grade_mismatch_is_review_required_not_silently_rewritten() -> None:
    rows, errors, _warnings = validate_cip_longitudinal_bar_runs(
        [_run(**{"Bar size": "DB32", "Material": "SD40", "fy MPa": 390.0})],
        length_m=20.0,
    )
    assert rows[0]["Material"] == "SD40"
    assert any("DB32 must use SD50" in message for message in errors)


def test_editor_preserves_unknown_loaded_labels_and_numeric_metadata_for_review() -> None:
    editor_rows = [
        {
            "Active": True,
            "Run ID": "CUSTOM-01",
            "s_start (m)": 1.0,
            "s_end (m)": 19.0,
            "Bar group": "Imported custom run",
            "Layer / face": "CUSTOM-FACE",
            "Bar size": "DB40-CUSTOM",
            "Diameter (mm)": 40.0,
            "Material": "CUSTOM-GRADE",
            "fy (MPa)": 500.0,
            "Definition basis": "By exact bar count",
            "Bar count": 4,
            "Target spacing (mm)": 0.0,
            "Start intent": "Not yet defined",
            "End intent": "Not yet defined",
            "Notes": "Preserve on edit",
        }
    ]
    rows = _cip_run_rows_from_editor_rows(editor_rows)
    assert rows[0]["Bar size"] == "DB40-CUSTOM"
    assert rows[0]["Bar diameter mm"] == 40.0
    assert rows[0]["Material"] == "CUSTOM-GRADE"
    assert rows[0]["fy MPa"] == 500.0

    options = _cip_editor_select_options(
        editor_rows, field="Bar size", supported=("DB25", "DB32")
    )
    assert "DB40-CUSTOM" in options

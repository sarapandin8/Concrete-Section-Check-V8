from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_COLUMN,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_joint_audit_rows,
    station_rebar_audit_rows,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_rebar_page import _rebar_elevation_figure


def test_rb1_default_templates_match_precast_hollow_and_cip_solid_intent():
    templates = default_crossbeam_rebar_templates()
    by_id = {row["Template ID"]: row for row in templates}
    assert by_id[RB_HOLLOW_MIN]["Applicable role"] == "Hollow"
    assert by_id[RB_HOLLOW_MIN]["Construction"] == "Factory precast"
    assert by_id[RB_HOLLOW_MIN]["Longitudinal basis"] == "Segment-local"
    assert by_id[RB_SOLID_COLUMN]["Applicable role"] == "Solid"
    assert by_id[RB_SOLID_COLUMN]["Construction"] == "Cast in place"
    assert by_id[RB_SOLID_COLUMN]["Longitudinal basis"] == "Zone-local"


def test_rb1_default_zone_assignment_follows_segment_role_and_covers_each_segment():
    segments = default_crossbeam_segment_rows(20.0)
    templates = default_crossbeam_rebar_templates()
    zones = default_crossbeam_rebar_zones(segments)
    normalized, errors, warnings = validate_rebar_zones(zones, segments, templates)
    assert not errors
    assert warnings  # quantities intentionally start undefined
    assert len(normalized) == len(segments)
    for segment, zone in zip(segments, normalized):
        assert zone["Segment"] == segment["Segment"]
        assert zone["s_start_m"] == segment["x_start_m"]
        assert zone["s_end_m"] == segment["x_end_m"]
        expected = RB_HOLLOW_MIN if segment["Section role"] == "Hollow" else RB_SOLID_COLUMN
        assert zone["Rebar template"] == expected


def test_rb1_joint_rule_is_locked_to_zero_ordinary_rebar_and_tendons_only():
    segments = default_crossbeam_segment_rows(20.0)
    joints = segment_joint_audit_rows(segments)
    assert len(joints) == len(segments) - 1
    assert {row["Ordinary rebar crossing joint"] for row in joints} == {"0 mm² (LOCKED)"}
    assert {row["Ordinary rebar strength credit"] for row in joints} == {"None"}
    assert {row["Global continuity system"] for row in joints} == {"Post-tensioning tendons only"}
    assert {row["Status"] for row in joints} == {"LOCKED"}


def test_rb1_station_audit_distinguishes_interior_from_joint_planes():
    segments = default_crossbeam_segment_rows(20.0)
    templates = default_crossbeam_rebar_templates()
    zones = default_crossbeam_rebar_zones(segments)
    audit = station_rebar_audit_rows(segments, zones, templates)
    joint_rows = [row for row in audit if row["Location type"] == "Segment joint"]
    interior_rows = [row for row in audit if row["Location type"] != "Segment joint"]
    assert len(joint_rows) == len(segments) - 1
    assert len(interior_rows) == len(segments)
    assert all(row["Ordinary rebar across joints"] == "0 mm² (LOCKED)" for row in joint_rows)
    assert all(row["Status"] == "TENDONS ONLY" for row in joint_rows)


def test_rb1_elevation_stops_rebar_traces_at_zone_boundaries_and_marks_joints():
    segments = default_crossbeam_segment_rows(20.0)
    templates = default_crossbeam_rebar_templates()
    zones = default_crossbeam_rebar_zones(segments)
    fig = _rebar_elevation_figure(segments, zones, templates, 20.0)
    annotations = [str(item.text) for item in fig.layout.annotations]
    assert annotations.count("<b>Ord. rebar = 0</b><br>Tendons only") == len(segments) - 1
    zone_traces = [trace for trace in fig.data if str(trace.name).endswith(" rebar") and trace.showlegend is False]
    assert zone_traces
    joint_stations = {float(row["x_end_m"]) for row in segments[:-1]}
    for trace in zone_traces:
        x_values = [float(value) for value in trace.x]
        assert not joint_stations.intersection(x_values)


def test_rb1_rebar_page_is_workflow_scoped_and_solver_free():
    app_source = Path("app.py").read_text()
    page_source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert "render_crossbeam_rebar_page" in app_source
    assert "if is_portal_frame_crossbeam_workflow(mode):" in app_source
    assert "else:\n            render_rebar_page()" in app_source
    assert "crossbeam_rb1_template_rows" in page_source
    assert "crossbeam_rb1_zone_assignment_rows" in page_source
    assert "Ordinary rebar crossing every segment joint = 0 mm²" in page_source
    assert "calculate_pmm" not in page_source
    assert "calculate_flexure" not in page_source
    assert "calculate_shear" not in page_source
    assert "project_from_session_state" not in page_source

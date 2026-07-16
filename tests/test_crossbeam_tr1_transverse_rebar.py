from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    default_section_definitions,
    definition_map,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_HOLLOW_MIN,
    TR_SOLID_COLUMN,
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    transverse_avs_record,
    transverse_set_stations,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_transverse_page import (
    transverse_cross_section_figure,
    transverse_elevation_figure,
)


def test_tr1_default_templates_separate_hollow_webs_and_solid_multileg_ties():
    rows = canonical_transverse_templates(default_crossbeam_transverse_templates())
    by_id = {row["Template ID"]: row for row in rows}
    assert by_id[TR_HOLLOW_MIN]["Applicable role"] == "Hollow"
    assert by_id[TR_HOLLOW_MIN]["Left web legs"] == 2
    assert by_id[TR_HOLLOW_MIN]["Right web legs"] == 2
    assert by_id[TR_SOLID_COLUMN]["Applicable role"] == "Solid"
    assert by_id[TR_SOLID_COLUMN]["Effective legs"] >= 4
    assert by_id[TR_SOLID_COLUMN]["Closed cage"] is True


def test_tr1_avs_preview_uses_independent_hollow_web_legs():
    hollow = next(row for row in default_crossbeam_transverse_templates() if row["Template ID"] == TR_HOLLOW_MIN)
    record = transverse_avs_record(hollow)
    assert record["Av,left/s mm²/mm"] > 0.0
    assert record["Av,right/s mm²/mm"] > 0.0
    assert abs(record["Av,total/s mm²/mm"] - record["Av,left/s mm²/mm"] - record["Av,right/s mm²/mm"]) < 1e-12


def test_tr1_default_zone_assignment_contains_longitudinal_and_transverse_templates():
    segments = default_crossbeam_segment_rows(20.0)
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    normalized, errors, _warnings = validate_rebar_zones(zones, segments, longitudinal, transverse)
    assert not errors
    assert len(normalized) == len(segments)
    for segment, zone in zip(segments, normalized):
        assert zone["Rebar template"] == zone["Longitudinal template"]
        if segment["Section role"] == "Hollow":
            assert zone["Transverse template"] == TR_HOLLOW_MIN
        else:
            assert zone["Transverse template"] == TR_SOLID_COLUMN


def test_tr1_validation_rejects_hollow_transverse_template_on_solid_segment():
    segments = default_crossbeam_segment_rows(20.0)
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    solid_zone = next(zone for segment, zone in zip(segments, zones) if segment["Section role"] == "Solid")
    solid_zone["Transverse template"] = TR_HOLLOW_MIN
    _normalized, errors, _warnings = validate_rebar_zones(zones, segments, longitudinal, transverse)
    assert any("transverse template" in message and "Hollow" in message and "Solid" in message for message in errors)


def test_tr1_transverse_set_stations_respect_first_and_last_offsets():
    template = next(row for row in default_crossbeam_transverse_templates() if row["Template ID"] == TR_HOLLOW_MIN)
    stations = transverse_set_stations(template, 0.0, 3.0)
    assert stations
    assert stations[0] >= template["First bar offset mm"] / 1000.0
    assert stations[-1] <= 3.0 - template["Last bar offset mm"] / 1000.0 + 1e-12
    assert all(b > a for a, b in zip(stations, stations[1:]))


def test_tr1_cross_section_and_elevation_figures_render_for_hollow_and_solid():
    definitions = definition_map(default_section_definitions())
    templates = {row["Template ID"]: row for row in default_crossbeam_transverse_templates()}
    for section_id, template_id in (("CB-H01", TR_HOLLOW_MIN), ("CB-S01", TR_SOLID_COLUMN)):
        definition = definitions[section_id]
        geometry = build_geometry_for_definition(definition)
        cross = transverse_cross_section_figure(geometry, definition, templates[template_id], title="TR1")
        elevation = transverse_elevation_figure(templates[template_id], start_m=0.0, end_m=3.0, segment_id="S1", zone_id="Z-S1")
        assert cross.layout.title.text == "TR1"
        assert any(str(trace.name) in {"Closed tie", "Left web closed loop"} for trace in cross.data)
        assert elevation.layout.title.text.startswith("Transverse Reinforcement Elevation")
        assert len(elevation.data) > 1


def test_tr1_ui_is_workflow_scoped_compact_and_solver_free():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    transverse_source = Path("concrete_pmm_pro/ui/crossbeam_transverse_page.py").read_text()
    assert '("Transverse / Shear", "Transverse / Shear")' in source
    assert '("Section Rebar Preview", "Preview")' in source
    assert "Longitudinal template" in source
    assert "Transverse template" in source
    assert "Hollow web-leg credit and detailing topology" in transverse_source
    assert "4 flange U-bars" in transverse_source
    assert "4 straight bars" in transverse_source
    assert "Solid multi-leg ties" in transverse_source
    assert "Joint shear credit" in source
    assert "calculate_shear" not in transverse_source
    assert "calculate_torsion" not in transverse_source
    assert "project_from_session_state" not in transverse_source

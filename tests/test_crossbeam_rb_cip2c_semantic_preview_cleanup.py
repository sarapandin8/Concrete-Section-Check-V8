from pathlib import Path

from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.ui.crossbeam_rebar_page import _cip_template_elevation_figure
from concrete_pmm_pro.ui.crossbeam_transverse_page import transverse_full_elevation_figure


def _segments():
    return [
        {
            "Segment": "Z1",
            "x_start_m": 0.0,
            "x_end_m": 10.0,
            "Section role": "Solid",
            "Section ID": "CB-S01",
            "Section name": "Support zone",
        },
        {
            "Segment": "Z2",
            "x_start_m": 10.0,
            "x_end_m": 20.0,
            "Section role": "Solid",
            "Section ID": "CB-S02",
            "Section name": "Typical zone",
        },
    ]


def _transverse_inputs():
    templates = default_crossbeam_transverse_templates()
    solid = next(row for row in templates if row.get("Applicable role") == "Solid")
    zones = [
        {
            "Zone ID": "Z1",
            "Segment": "Z1",
            "s_start_m": 0.0,
            "s_end_m": 10.0,
            "Transverse template": solid["Template ID"],
        },
        {
            "Zone ID": "Z2",
            "Segment": "Z2",
            "s_start_m": 10.0,
            "s_end_m": 20.0,
            "Transverse template": solid["Template ID"],
        },
    ]
    return templates, zones


def test_cip_assignment_figure_has_explicit_production_title():
    zones = [
        {"Zone ID": "Z1", "Segment": "Z1", "s_start_m": 0.0, "s_end_m": 10.0, "Longitudinal template": "RB-SOLID-COLUMN"},
        {"Zone ID": "Z2", "Segment": "Z2", "s_start_m": 10.0, "s_end_m": 20.0, "Longitudinal template": "RB-SOLID-COLUMN"},
    ]
    fig = _cip_template_elevation_figure(_segments(), zones, 20.0)
    assert fig.layout.title.text == "Cast-in-Place Reinforcement Template Assignment"
    assert "undefined" not in str(fig.layout.title.text).lower()


def test_cip_transverse_elevation_uses_zone_only_legend_semantics():
    templates, zones = _transverse_inputs()
    fig = transverse_full_elevation_figure(
        _segments(), zones, templates, selected_zone_id="Z1", cip_mode=True
    )
    names = [trace.name for trace in fig.data if trace.name]
    assert "Solid zone" in names
    assert "Solid segment" not in names
    assert "Hollow segment" not in names
    assert "Hidden void boundary" not in names
    assert fig.layout.meta["construction_semantics"] == "Cast-in-Place Section/Zone"


def test_precast_transverse_elevation_legend_is_preserved():
    templates, zones = _transverse_inputs()
    fig = transverse_full_elevation_figure(
        _segments(), zones, templates, selected_zone_id="Z1", cip_mode=False
    )
    names = [trace.name for trace in fig.data if trace.name]
    assert "Solid segment" in names
    assert "Hollow segment" in names
    assert "Hidden void boundary" in names
    assert fig.layout.meta["construction_semantics"] == "Precast Segmental"


def test_cip_ui_removes_developer_plural_and_uses_specific_cleanup_copy():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    assert "assigned CIP reinforcement item(s)" not in source
    assert "assigned reinforcement {noun} additional input" in source
    assert "Actual spacing and first/last offsets remain Zone-local" in source
    assert "splice/termination" in source

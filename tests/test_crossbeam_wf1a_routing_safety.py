from __future__ import annotations

from types import SimpleNamespace

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.ui import section_builder


CROSSBEAM_PRESET = {
    "key": "crossbeam_rectangular_solid_bottom_fillets",
    "category": "Portal Frame Crossbeam",
    "display_name": "PC Crossbeam — Rectangular Solid with Bottom Fillets",
    "allowed_workflows": ["portal_frame_crossbeam"],
}

COLUMN_PRESET = {
    "key": "rectangular_solid",
    "category": "Basic Solid",
    "display_name": "Rectangular Solid",
}


def test_crossbeam_family_and_coordinate_labels_are_workflow_scoped() -> None:
    crossbeam = AnalysisModeSettings(member_type="portal_frame_crossbeam")
    column = AnalysisModeSettings(member_type="column_pier_pmm")

    assert section_builder._section_family_label_for_workflow(CROSSBEAM_PRESET, crossbeam) == "Portal Frame Crossbeam"
    assert section_builder._section_axis_status_for_workflow(crossbeam) == (
        "s/u/v",
        "s longitudinal left→right; u horizontal in section/plan; v vertical",
    )

    # Existing Column/Pier wording remains unchanged.
    assert section_builder._section_family_label_for_workflow(COLUMN_PRESET, column) == "Column/Pier/Wall/Pylon section"
    assert section_builder._section_axis_status_for_workflow(column) == (
        "x/y/z",
        "x horizontal, y vertical, z longitudinal",
    )


def test_crossbeam_entry_does_not_inherit_old_preset_steel_override(monkeypatch) -> None:
    fake_state = {
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        section_builder.ORDINARY_REBAR_FLAG_KEY: False,
        section_builder.PRESTRESSING_STEEL_FLAG_KEY: False,
        section_builder.SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY: True,
        section_builder.SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY: "rectangular_solid",
        "project_metadata": {
            section_builder.SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY: True,
            section_builder.SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY: "rectangular_solid",
        },
    }
    monkeypatch.setattr(section_builder, "st", SimpleNamespace(session_state=fake_state))

    section_builder._ensure_reinforcement_flags_for_preset(CROSSBEAM_PRESET)

    assert fake_state[section_builder.ORDINARY_REBAR_FLAG_KEY] is True
    assert fake_state[section_builder.PRESTRESSING_STEEL_FLAG_KEY] is True
    assert fake_state[section_builder.REINFORCEMENT_FLAGS_PRESET_KEY] == CROSSBEAM_PRESET["key"]


def test_same_crossbeam_preset_explicit_steel_override_is_preserved(monkeypatch) -> None:
    preset_key = CROSSBEAM_PRESET["key"]
    fake_state = {
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        section_builder.ORDINARY_REBAR_FLAG_KEY: False,
        section_builder.PRESTRESSING_STEEL_FLAG_KEY: True,
        section_builder.SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY: True,
        section_builder.SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY: preset_key,
        "project_metadata": {
            section_builder.SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY: True,
            section_builder.SECTION_BUILDER_STEEL_SYSTEMS_OVERRIDE_PRESET_KEY: preset_key,
        },
    }
    monkeypatch.setattr(section_builder, "st", SimpleNamespace(session_state=fake_state))

    section_builder._ensure_reinforcement_flags_for_preset(CROSSBEAM_PRESET)

    assert fake_state[section_builder.ORDINARY_REBAR_FLAG_KEY] is False
    assert fake_state[section_builder.PRESTRESSING_STEEL_FLAG_KEY] is True


def test_wf1a_keeps_existing_sections_navigation_unchanged() -> None:
    source = open("app.py", encoding="utf-8").read()
    assert '"Sections": ["Section Builder", "Rebar", "Prestress"]' in source
    assert 'elif active == "Prestress":' in source

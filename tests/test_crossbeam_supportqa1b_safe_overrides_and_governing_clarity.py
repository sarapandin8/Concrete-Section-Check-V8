from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
    CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
    CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY,
    CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY,
)
from concrete_pmm_pro.ui.crossbeam_pages import (
    _annotate_governing_fcgp_rows,
    _sync_es_override_preview_value,
)


def test_supportqa1b_disabled_override_tracks_source_and_first_enable_is_seeded() -> None:
    state: dict[str, object] = {
        CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY: False,
        CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY: 1000.0,
    }

    enabled = _sync_es_override_preview_value(
        state,
        enabled_key=CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
        value_key=CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
        source_value=28200.0,
    )
    assert enabled is False
    assert state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] == 28200.0

    state[CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY] = True
    state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] = 1000.0
    enabled = _sync_es_override_preview_value(
        state,
        enabled_key=CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
        value_key=CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
        source_value=28200.0,
    )
    assert enabled is True
    assert state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] == 28200.0

    state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] = 30000.0
    _sync_es_override_preview_value(
        state,
        enabled_key=CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
        value_key=CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
        source_value=28200.0,
    )
    assert state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] == 30000.0


def test_supportqa1b_existing_enabled_project_override_is_preserved_on_first_load() -> None:
    state: dict[str, object] = {
        CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY: True,
        CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY: 14.5,
    }

    enabled = _sync_es_override_preview_value(
        state,
        enabled_key=CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY,
        value_key=CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY,
        source_value=12.215,
    )
    assert enabled is True
    assert state[CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY] == 14.5


def test_supportqa1b_governing_fcgp_rows_are_marked_without_changing_values() -> None:
    rows = [
        {
            "Evaluation role": "Column C1 centerline — LEFT LIMIT (s−)",
            "s (m)": 1.5,
            "f_cgp (MPa; compression +)": 7.871,
        },
        {
            "Evaluation role": "Bay C2–C3 governing f_cgp",
            "s (m)": 15.0,
            "f_cgp (MPa; compression +)": 12.215,
        },
        {
            "Evaluation role": "Bay C2–C3 midpoint",
            "s (m)": 15.0,
            "f_cgp (MPa; compression +)": 12.2150000004,
        },
    ]

    annotated, governing = _annotate_governing_fcgp_rows(
        rows,
        governing_fcgp_mpa=12.215,
    )

    assert [row["Governing source"] for row in annotated] == [
        "",
        "GOVERNING",
        "GOVERNING",
    ]
    assert len(governing) == 2
    assert rows[1].get("Governing source") is None
    assert annotated[1]["f_cgp (MPa; compression +)"] == 12.215


def test_supportqa1b_ui_explains_safe_override_seed_and_governing_source() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]

    assert "Governing f_cgp source —" in elastic
    assert '"Governing source"' in elastic
    assert "the field displays the current source-derived f_cgp" in elastic
    assert "the field displays the current stage-derived Eci" in elastic
    assert "Enabling it starts from that source value" in elastic

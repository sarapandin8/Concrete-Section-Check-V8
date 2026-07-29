from __future__ import annotations

import pytest

from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    normalize_crossbeam_prestress_loss_settings,
    normalize_stressing_strength_ratio,
)
from concrete_pmm_pro.ui import crossbeam_pages


def test_legacy_widget_fallback_ratio_is_repaired_to_established_default() -> None:
    value, migrated = normalize_stressing_strength_ratio(0.10)
    assert migrated is True
    assert value == pytest.approx(DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO)

    settings = normalize_crossbeam_prestress_loss_settings(
        {"es_stressing_strength_ratio": 0.10}
    )
    assert settings["es_stressing_strength_ratio"] == pytest.approx(0.80)
    assert settings["es_stressing_strength_ratio_migrated"] is True


def test_session_guard_repairs_existing_legacy_state_before_widget_render() -> None:
    state = {CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY: 0.10}
    migrated = crossbeam_pages._guard_crossbeam_stressing_strength_ratio_state(state)
    assert migrated is True
    assert state[CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY] == pytest.approx(0.80)
    assert state[crossbeam_pages.CB_LOSS_ES_STRENGTH_RATIO_GUARD_NOTICE_KEY] is True


def test_loss_summary_reports_component_mpa_percent_and_total_accounted_loss() -> None:
    friction_rows = []
    anchorage_rows = []
    after_es_rows = []
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

    assert payload["weighted_fpj_mpa"] == pytest.approx(1400.0)
    assert payload["instantaneous_loss_mpa"] == pytest.approx(15.0 + 3.0 + 5.0)
    assert payload["time_dependent_loss_mpa"] == pytest.approx(45.0)
    assert payload["total_loss_mpa"] == pytest.approx(68.0)
    assert payload["total_loss_percent"] == pytest.approx(100.0 * 68.0 / 1400.0)
    assert payload["ready"] is True
    assert len(payload["governing_rows"]) == 2
    assert all(row["Governing station s (m)"] == pytest.approx(20.0) for row in payload["governing_rows"])


def test_project_metadata_with_legacy_point_one_ratio_restores_as_point_eight() -> None:
    from concrete_pmm_pro.crossbeam.prestress_loss import (
        CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
        restore_crossbeam_prestress_loss_project_state,
    )

    restored_state: dict[str, object] = {}
    restored = restore_crossbeam_prestress_loss_project_state(
        {
            CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: {
                "es_stressing_strength_ratio": 0.10,
            }
        },
        restored_state,
    )
    assert restored is not None
    assert restored["es_stressing_strength_ratio"] == pytest.approx(0.80)
    assert restored_state[CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY] == pytest.approx(0.80)

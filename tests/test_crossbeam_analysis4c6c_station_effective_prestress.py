from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    build_crossbeam_uls_shear_preparation,
)
from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    canonical_effective_prestress_link,
)
from concrete_pmm_pro.crossbeam.uls_effective_prestress import (
    PROFILE_MODE_STATION_DEPENDENT,
    PROFILE_MODE_UNIFORM_OVERRIDE,
    canonical_effective_prestress_profile_rows,
    resolve_tendon_effective_prestress,
    validate_effective_prestress_profiles,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


_FIXTURE = Path(__file__).with_name("data") / "crossbeam_analysis4_direct_solver_benchmark.json"


def _benchmark_state() -> dict[str, object]:
    state: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(_FIXTURE.read_text(encoding="utf-8")), state)
    return state


def _vary_profile(state: dict[str, object]) -> None:
    link = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    updated = []
    for row in link.get("tendon_station_profiles", []):
        station = float(row["Station s (m)"])
        if station <= 15.0:
            fpe = 1000.0 + station * (200.0 / 15.0)
        else:
            fpe = 1200.0 - (station - 15.0) * (100.0 / 15.0)
        updated.append({**row, "fpe (MPa)": fpe})
    link["tendon_station_profiles"] = updated
    link["average_effective_stress_mpa"] = 1125.0
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = link


def test_profile_rows_collapse_duplicates_and_interpolate() -> None:
    rows = [
        {"Tendon": "T1", "Station s (m)": 0.0, "fpe (MPa)": 1000.0},
        {"Tendon": "T1", "Station s (m)": 10.0, "fpe (MPa)": 1190.0},
        {"Tendon": "T1", "Station s (m)": 10.0, "fpe (MPa)": 1210.0},
        {"Tendon": "T1", "Station s (m)": 20.0, "fpe (MPa)": 1000.0},
    ]
    canonical = canonical_effective_prestress_profile_rows(rows)
    assert len(canonical) == 3
    middle = next(row for row in canonical if row["Station s (m)"] == 10.0)
    assert middle["fpe (MPa)"] == pytest.approx(1200.0)
    assert middle["Duplicate fpe spread (MPa)"] == pytest.approx(20.0)

    validation = validate_effective_prestress_profiles(
        canonical,
        tendon_ids=["T1"],
        member_length_m=20.0,
    )
    assert validation.ready
    assert validation.warnings

    resolved = resolve_tendon_effective_prestress(
        canonical,
        tendon_id="T1",
        station_m=5.0,
        member_length_m=20.0,
    )
    assert resolved.ready
    assert resolved.mode == PROFILE_MODE_STATION_DEPENDENT
    assert not resolved.exact
    assert resolved.source_station_1_m == pytest.approx(0.0)
    assert resolved.source_station_2_m == pytest.approx(10.0)
    assert resolved.interpolation_ratio == pytest.approx(0.5)
    assert resolved.fpe_mpa == pytest.approx(1100.0)


def test_flexure_uses_local_tendon_fpe_at_each_station() -> None:
    state = _benchmark_state()
    _vary_profile(state)
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors

    end_row = next(row for row in preparation.rows if abs(row.station_m - 0.0) <= 1.0e-9)
    face_row = next(row for row in preparation.rows if abs(row.station_m - 14.0) <= 1.0e-9)
    assert end_row.effective_prestress_mode == PROFILE_MODE_STATION_DEPENDENT
    assert end_row.effective_prestress_min_mpa == pytest.approx(1000.0)
    assert face_row.effective_prestress_min_mpa == pytest.approx(1186.6666667)
    assert face_row.effective_prestress_max_mpa == pytest.approx(1186.6666667)

    result = run_crossbeam_uls_flexure(preparation)
    result_face = next(row for row in result["rows"] if abs(float(row["Station s (m)"]) - 14.0) <= 1.0e-9)
    assert result_face["Effective prestress mode"] == PROFILE_MODE_STATION_DEPENDENT
    assert float(result_face["Local fpe min MPa"]) == pytest.approx(1186.6666667)
    result_end = next(row for row in result["rows"] if abs(float(row["Station s (m)"]) - 0.0) <= 1.0e-9)
    assert float(result_face["φMn kN-m"]) > float(result_end["φMn kN-m"])


def test_shear_and_torsion_source_groups_use_local_fse() -> None:
    state = _benchmark_state()
    _vary_profile(state)
    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors

    end_row = next(row for row in preparation.rows if abs(row.station_m - 0.0) <= 1.0e-9)
    face_row = next(row for row in preparation.rows if abs(row.station_m - 14.0) <= 1.0e-9)
    assert {group.effective_prestress_mode for group in end_row.prestress_groups} == {
        PROFILE_MODE_STATION_DEPENDENT
    }
    assert sorted({group.fse_mpa for group in end_row.prestress_groups}) == pytest.approx([1000.0])
    assert sorted({group.fse_mpa for group in face_row.prestress_groups}) == pytest.approx(
        [1186.6666667]
    )

    torsion_preparation = build_crossbeam_uls_torsion_preparation(state)
    assert torsion_preparation.ready, torsion_preparation.errors
    torsion_result = run_crossbeam_uls_torsion(torsion_preparation)
    torsion_end = next(row for row in torsion_result["rows"] if abs(float(row["Station s (m)"]) - 0.0) <= 1.0e-9)
    torsion_face = next(row for row in torsion_result["rows"] if abs(float(row["Station s (m)"]) - 14.0) <= 1.0e-9)
    assert float(torsion_face["phiTth kN-m"]) > float(torsion_end["phiTth kN-m"])
    assert float(torsion_face["fpc MPa"]) > float(torsion_end["fpc MPa"])


def test_legacy_average_link_blocks_without_explicit_override() -> None:
    state = _benchmark_state()
    source = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    source.pop("tendon_station_profiles", None)
    source["schema"] = "crossbeam-effective-prestress-loads-link-v1"
    source["profile_ready"] = False
    source["allow_uniform_average_uls_override"] = False
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = canonical_effective_prestress_link(source)

    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert not preparation.ready
    assert any("Station-dependent Effective Prestress is required" in message for message in preparation.errors)


def test_explicit_uniform_average_override_is_review_not_pass() -> None:
    state = _benchmark_state()
    source = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    source.pop("tendon_station_profiles", None)
    source["schema"] = "crossbeam-effective-prestress-loads-link-v2"
    source["profile_ready"] = False
    source["allow_uniform_average_uls_override"] = True
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = canonical_effective_prestress_link(source)

    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    assert {row.effective_prestress_mode for row in preparation.rows} == {
        PROFILE_MODE_UNIFORM_OVERRIDE
    }
    result = run_crossbeam_uls_flexure(preparation)
    assert result["status"] == "REVIEW"
    assert all(row["Status"] != "PASS" for row in result["rows"])

    combined_preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert combined_preparation.ready, combined_preparation.errors
    combined_result = run_crossbeam_uls_combined_vt(combined_preparation)
    assert combined_result["status"] == "REVIEW"
    assert all(row["Status"] != "PASS" for row in combined_result["rows"] if row.get("Station type") != "PHYSICAL JOINT SIDE")


def test_station_profiles_round_trip_through_project_json() -> None:
    state = _benchmark_state()
    _vary_profile(state)
    original = canonical_effective_prestress_link(
        state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]
    )

    project = project_from_session_state(state)
    restored: dict[str, object] = {}
    apply_project_to_session_state(
        project_from_json(project_to_json(project)),
        restored,
    )
    restored_link = canonical_effective_prestress_link(
        restored[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]
    )

    assert restored_link["schema"] == "crossbeam-effective-prestress-loads-link-v2"
    assert restored_link["profile_ready"] is True
    assert restored_link["profile_fingerprint"] == original["profile_fingerprint"]
    assert restored_link["tendon_station_profiles"] == original["tendon_station_profiles"]
    assert restored_link["allow_uniform_average_uls_override"] is False

from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_equivalent_average_summary,
    anchorage_set_station_rows,
    anchorage_set_summary,
)
from concrete_pmm_pro.crossbeam.anchorage_set_validation import (
    independent_both_end_dense_grid_validation,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ANCHORAGE_SET_MM_KEY,
    CB_LOSS_EP_MPA_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    DEFAULT_ANCHORAGE_SET_MM,
    aashto_friction_wobble_station_rows,
    crossbeam_prestress_loss_settings_from_session_state,
    default_crossbeam_prestress_loss_settings,
    restore_crossbeam_prestress_loss_project_state,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)

KSI_TO_MPA = 6.894757293168361
FT_TO_M = 0.3048
IN_TO_MM = 25.4


def _linear_left_friction_rows() -> list[dict[str, object]]:
    # Accepted post-friction diagram: f(x) = 1400 - 10x MPa over 20 m.
    rows: list[dict[str, object]] = []
    for point, x_m, stress_mpa in (
        ("P1", 0.0, 1400.0),
        ("P2", 10.0, 1300.0),
        ("P3", 20.0, 1200.0),
    ):
        rows.append(
            {
                "Tendon ID": "T1",
                "Active": True,
                "Type": "Internal",
                "Jacking end": "Left",
                "Source end": "Left",
                "Point": point,
                "s (m)": x_m,
                "x from jack (m)": x_m,
                "K (/m)": 0.0,
                "Aps total (mm²)": 1000.0,
                "fpj (MPa)": 1400.0,
                "Pj (kN)": 1400.0,
                "Stress after friction (MPa)": stress_mpa,
                "P after friction (kN)": stress_mpa,
                "Status": "LOSS READY",
                "Blocking issue": "",
                "Review note": "",
            }
        )
    return rows


def _linear_both_end_friction_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for station_m in (0.0, 5.0, 10.0, 15.0, 20.0):
        left_stress = 1400.0 - 10.0 * station_m
        right_stress = 1400.0 - 10.0 * (20.0 - station_m)
        use_left = station_m <= 10.0
        accepted = left_stress if use_left else right_stress
        rows.append(
            {
                "Tendon ID": "T1",
                "Active": True,
                "Type": "Internal",
                "Jacking end": "Both",
                "Source end": "Left (nearest)" if use_left else "Right (nearest)",
                "Point": f"P{int(station_m)}",
                "s (m)": station_m,
                "x from jack (m)": station_m if use_left else 20.0 - station_m,
                "K (/m)": 0.0,
                "Aps total (mm²)": 1000.0,
                "fpj (MPa)": 1400.0,
                "Pj (kN)": 1400.0,
                "Stress after friction (MPa)": accepted,
                "P after friction (kN)": accepted,
                "Stress from left jack (MPa)": left_stress,
                "Stress from right jack (MPa)": right_stress,
                "Status": "LOSS READY",
                "Blocking issue": "",
                "Review note": "",
            }
        )
    return rows



def _linear_asymmetric_both_end_friction_rows(
    *, left_gradient_mpa_per_m: float, right_gradient_mpa_per_m: float
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    length_m = 20.0
    fpj = 1400.0
    for station_m in (0.0, 4.0, 8.0, 12.0, 16.0, 20.0):
        left_stress = fpj - left_gradient_mpa_per_m * station_m
        right_stress = fpj - right_gradient_mpa_per_m * (length_m - station_m)
        accepted = max(left_stress, right_stress)
        source = "Left (controlling)" if left_stress >= right_stress else "Right (controlling)"
        rows.append(
            {
                "Tendon ID": "T1",
                "Active": True,
                "Type": "Internal",
                "Jacking end": "Both",
                "Source end": source,
                "Point": f"P{int(station_m)}",
                "s (m)": station_m,
                "x from jack (m)": station_m if left_stress >= right_stress else length_m - station_m,
                "K (/m)": 0.0,
                "Aps total (mm²)": 1000.0,
                "fpj (MPa)": fpj,
                "Pj (kN)": fpj,
                "Stress after friction (MPa)": accepted,
                "P after friction (kN)": accepted,
                "Stress from left jack (MPa)": left_stress,
                "Stress from right jack (MPa)": right_stress,
                "Status": "LOSS READY",
                "Blocking issue": "",
                "Review note": "",
            }
        )
    return rows

def _caltrans_linear_rows(*, length_ft: float, fjack_ksi: float, end_loss_ksi: float) -> list[dict[str, object]]:
    length_m = length_ft * FT_TO_M
    fjack_mpa = fjack_ksi * KSI_TO_MPA
    dead_mpa = (fjack_ksi - end_loss_ksi) * KSI_TO_MPA
    return [
        {
            "Tendon ID": "CALTRANS",
            "Active": True,
            "Type": "Internal",
            "Jacking end": "Left",
            "Source end": "Left",
            "Point": "JACK",
            "s (m)": 0.0,
            "x from jack (m)": 0.0,
            "K (/m)": 0.0,
            "Aps total (mm²)": 1000.0,
            "fpj (MPa)": fjack_mpa,
            "Pj (kN)": fjack_mpa,
            "Stress after friction (MPa)": fjack_mpa,
            "P after friction (kN)": fjack_mpa,
            "Status": "LOSS READY",
            "Blocking issue": "",
            "Review note": "",
        },
        {
            "Tendon ID": "CALTRANS",
            "Active": True,
            "Type": "Internal",
            "Jacking end": "Left",
            "Source end": "Left",
            "Point": "DEAD",
            "s (m)": length_m,
            "x from jack (m)": length_m,
            "K (/m)": 0.0,
            "Aps total (mm²)": 1000.0,
            "fpj (MPa)": fjack_mpa,
            "Pj (kN)": fjack_mpa,
            "Stress after friction (MPa)": dead_mpa,
            "P after friction (kN)": dead_mpa,
            "Status": "LOSS READY",
            "Blocking issue": "",
            "Review note": "",
        },
    ]



def _independent_simultaneous_both_end_grid_solution(
    *,
    length_m: float,
    fpj_mpa: float,
    left_gradient_mpa_per_m: float,
    right_gradient_mpa_per_m: float,
    anchor_set_mm: float,
    ep_mpa: float,
    n_steps: int = 4000,
) -> tuple[float, float, float, float]:
    """Independent discretized check of the PTLOSS2R2 coupled equations.

    This test helper intentionally does not call any production interpolation,
    area, or coupled-solver helper.  It numerically integrates the physical
    branch equations on a dense grid and solves the two seating-compatibility
    equations by bisection.
    """

    def f_left(s: float) -> float:
        return fpj_mpa - left_gradient_mpa_per_m * s

    def f_right(s: float) -> float:
        return fpj_mpa - right_gradient_mpa_per_m * (length_m - s)

    def f_initial(s: float) -> float:
        return max(f_left(s), f_right(s))

    def integrate(a: float, b: float, fn) -> float:
        if b <= a:
            return 0.0
        steps = max(20, int(n_steps * (b - a) / length_m))
        h = (b - a) / steps
        total = 0.5 * (fn(a) + fn(b))
        for i in range(1, steps):
            total += fn(a + i * h)
        return total * h

    target_area = anchor_set_mm * ep_mpa / 1000.0

    def solve_meeting_from_left(sn: float) -> float:
        numerator = integrate(
            0.0,
            sn,
            lambda s: f_initial(s) - f_left(sn) + f_left(s),
        ) - target_area
        return numerator / sn

    def right_residual(sn: float) -> tuple[float, float]:
        meeting = solve_meeting_from_left(sn)
        area = integrate(
            sn,
            length_m,
            lambda s: f_initial(s) - (meeting + f_right(sn) - f_right(s)),
        )
        return area - target_area, meeting

    lo = 1.0e-6
    hi = length_m - 1.0e-6
    r_lo, _ = right_residual(lo)
    r_hi, _ = right_residual(hi)
    assert r_lo * r_hi <= 0.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        residual, _ = right_residual(mid)
        if residual == 0.0:
            lo = hi = mid
            break
        if r_lo * residual <= 0.0:
            hi = mid
            r_hi = residual
        else:
            lo = mid
            r_lo = residual
    sn = 0.5 * (lo + hi)
    _, meeting = right_residual(sn)
    final_left_anchor = meeting + f_left(sn) - f_left(0.0)
    final_right_anchor = meeting + f_right(sn) - f_right(length_m)
    left_loss = f_initial(0.0) - final_left_anchor
    right_loss = f_initial(length_m) - final_right_anchor
    return sn, meeting, left_loss, right_loss

def test_ptloss2r1_linear_force_diagram_matches_closed_form_area_compatibility() -> None:
    end_rows = anchorage_set_end_rows(
        _linear_left_friction_rows(), length_m=20.0, anchor_set_mm=5.0, ep_mpa=200000.0
    )
    row = end_rows[0]
    assert row["Status"] == "PREVIEW READY + NOTE"
    assert row["Interaction mode"] == "SINGLE-END FRICTION-COUPLED"
    assert row["Affected length (m)"] == pytest.approx(10.0, abs=1.0e-6)
    assert row["Full tendon affected"] is False
    assert row["Zero movement stress (MPa)"] == pytest.approx(1300.0)
    assert row["Lock-off stress at anchorage (MPa)"] == pytest.approx(1200.0)
    assert row["Anchorage-set loss at anchorage (MPa)"] == pytest.approx(200.0)
    assert row["Dead-end anchorage-set loss (MPa)"] == pytest.approx(0.0)
    assert row["Compatibility set check (mm)"] == pytest.approx(5.0)
    assert abs(float(row["Compatibility residual (mm)"])) < 1.0e-8


def test_ptloss2r1_station_trace_applies_reverse_slip_loss_only_inside_partial_affected_length() -> None:
    friction_rows = _linear_left_friction_rows()
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=5.0, ep_mpa=200000.0
    )
    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    by_point = {row["Point"]: row for row in station_rows}
    assert by_point["P1"]["P after anchorage set (kN)"] == pytest.approx(1200.0)
    assert by_point["P2"]["P after anchorage set (kN)"] == pytest.approx(1300.0)
    assert by_point["P3"]["P after anchorage set (kN)"] == pytest.approx(1200.0)
    assert by_point["P1"]["Anchorage-set loss (kN)"] == pytest.approx(200.0)
    assert by_point["P2"]["Anchorage-set loss (kN)"] == pytest.approx(0.0)
    assert by_point["P3"]["Anchorage-set loss (kN)"] == pytest.approx(0.0)


def test_ptloss2r1_large_single_end_drawin_can_affect_full_tendon_without_false_capacity_failure() -> None:
    friction_rows = _linear_left_friction_rows()
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=25.0, ep_mpa=200000.0
    )
    row = end_rows[0]
    assert row["Status"] == "PREVIEW READY + NOTE"
    assert row["Affected length (m)"] == pytest.approx(20.0)
    assert row["Full tendon affected"] is True
    assert row["Anchorage-set loss at anchorage (MPa)"] == pytest.approx(450.0)
    assert row["Dead-end anchorage-set loss (MPa)"] == pytest.approx(50.0)
    assert row["Compatibility set check (mm)"] == pytest.approx(25.0)

    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    by_point = {row["Point"]: row for row in station_rows}
    assert by_point["P1"]["P after anchorage set (kN)"] == pytest.approx(950.0)
    assert by_point["P2"]["P after anchorage set (kN)"] == pytest.approx(1050.0)
    assert by_point["P3"]["P after anchorage set (kN)"] == pytest.approx(1150.0)


def test_ptloss2r1_reproduces_caltrans_example_2_anchor_set() -> None:
    # Caltrans Prestress Manual Appendix E Example 2:
    # E=28,000 ksi, Δa=0.375 in, L=144 ft, friction loss d=10.5 ksi.
    rows = _caltrans_linear_rows(length_ft=144.0, fjack_ksi=202.5, end_loss_ksi=10.5)
    result = anchorage_set_end_rows(
        rows,
        length_m=144.0 * FT_TO_M,
        anchor_set_mm=0.375 * IN_TO_MM,
        ep_mpa=28000.0 * KSI_TO_MPA,
    )[0]
    assert result["Status"] == "PREVIEW READY + NOTE"
    assert float(result["Affected length (m)"]) / FT_TO_M == pytest.approx(109.5, abs=0.08)
    assert float(result["Anchorage-set loss at anchorage (MPa)"]) / KSI_TO_MPA == pytest.approx(15.97, abs=0.02)


def test_ptloss2r1_reproduces_caltrans_example_3_single_end() -> None:
    # Caltrans Prestress Manual Appendix E Example 3:
    # L=140 ft, E=28,000 ksi, Δa=0.375 in, total friction loss d=9.77 ksi.
    rows = _caltrans_linear_rows(length_ft=140.0, fjack_ksi=202.5, end_loss_ksi=9.77)
    result = anchorage_set_end_rows(
        rows,
        length_m=140.0 * FT_TO_M,
        anchor_set_mm=0.375 * IN_TO_MM,
        ep_mpa=28000.0 * KSI_TO_MPA,
    )[0]
    assert result["Status"] == "PREVIEW READY + NOTE"
    assert float(result["Affected length (m)"]) / FT_TO_M == pytest.approx(112.0, abs=0.08)
    assert float(result["Anchorage-set loss at anchorage (MPa)"]) / KSI_TO_MPA == pytest.approx(15.63, abs=0.02)


def test_ptloss2r1_si_implementation_round_trips_caltrans_native_units() -> None:
    rows = _caltrans_linear_rows(length_ft=144.0, fjack_ksi=202.5, end_loss_ksi=10.5)
    result = anchorage_set_end_rows(
        rows,
        length_m=144.0 * FT_TO_M,
        anchor_set_mm=0.375 * IN_TO_MM,
        ep_mpa=28000.0 * KSI_TO_MPA,
    )[0]
    xp_ft = float(result["Affected length (m)"]) / FT_TO_M
    loss_ksi = float(result["Anchorage-set loss at anchorage (MPa)"]) / KSI_TO_MPA
    assert xp_ft == pytest.approx(109.5445, rel=1.0e-5)
    assert loss_ksi == pytest.approx(15.97524, rel=1.0e-5)


def test_ptloss2r2_symmetric_simultaneous_both_end_overlap_matches_closed_form() -> None:
    # Symmetric linear friction: f=1400-10x MPa from each end, L=20 m, Ep=200 GPa.
    # Half-length local capacity corresponds to Δa=5 mm. At Δa=6 mm the seating
    # zones interact. Closed form gives s_n=10 m, meeting stress=1280 MPa,
    # anchorage loss=220 MPa, and lock-off stress=1180 MPa.
    rows = anchorage_set_end_rows(
        _linear_both_end_friction_rows(), length_m=20.0, anchor_set_mm=6.0, ep_mpa=200000.0
    )
    assert len(rows) == 2
    assert {row["Seating end"] for row in rows} == {"Left", "Right"}
    assert all(row["Status"] == "PREVIEW READY + NOTE" for row in rows)
    assert all(row["Interaction mode"] == "BOTH-END SIMULTANEOUS COUPLED" for row in rows)
    assert all(row["Pre-seat no-movement s (m)"] == pytest.approx(10.0) for row in rows)
    assert all(row["Neutral point s (m)"] == pytest.approx(10.0) for row in rows)
    assert all(row["Meeting stress after seating (MPa)"] == pytest.approx(1280.0) for row in rows)
    assert all(row["Anchorage-set loss at anchorage (MPa)"] == pytest.approx(220.0) for row in rows)
    assert all(row["Lock-off stress at anchorage (MPa)"] == pytest.approx(1180.0) for row in rows)
    assert all(row["Compatibility set check (mm)"] == pytest.approx(6.0) for row in rows)
    assert all(abs(float(row["Compatibility residual (mm)"])) < 1.0e-8 for row in rows)

    station_rows = anchorage_set_station_rows(_linear_both_end_friction_rows(), rows, length_m=20.0)
    by_s = {float(row["s (m)"]): row for row in station_rows}
    assert by_s[0.0]["P after anchorage set (kN)"] == pytest.approx(1180.0)
    assert by_s[5.0]["P after anchorage set (kN)"] == pytest.approx(1230.0)
    assert by_s[10.0]["P after anchorage set (kN)"] == pytest.approx(1280.0)
    assert by_s[15.0]["P after anchorage set (kN)"] == pytest.approx(1230.0)
    assert by_s[20.0]["P after anchorage set (kN)"] == pytest.approx(1180.0)


def test_ptloss2r2_symmetric_small_drawin_keeps_separated_local_zones() -> None:
    rows = anchorage_set_end_rows(
        _linear_both_end_friction_rows(), length_m=20.0, anchor_set_mm=2.0, ep_mpa=200000.0
    )
    assert all(row["Interaction mode"] == "BOTH-END SIMULTANEOUS LOCAL" for row in rows)
    expected_sa = (200000.0 * 2.0 / (1000.0 * 10.0)) ** 0.5
    assert all(float(row["Affected length (m)"]) == pytest.approx(expected_sa) for row in rows)
    assert all(row["Neutral point s (m)"] is None for row in rows)


def test_ptloss2r2_zero_friction_both_end_reduces_to_uniform_elastic_shortening() -> None:
    rows = _linear_both_end_friction_rows()
    for row in rows:
        row["Stress after friction (MPa)"] = 1400.0
        row["P after friction (kN)"] = 1400.0
        row["Stress from left jack (MPa)"] = 1400.0
        row["Stress from right jack (MPa)"] = 1400.0
    end_rows = anchorage_set_end_rows(rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=200000.0)
    # Total tendon shortening is 2Δa = 12 mm, so uniform loss = Ep*(12/20000)=120 MPa.
    assert all(row["Interaction mode"] == "BOTH-END SIMULTANEOUS COUPLED" for row in end_rows)
    assert all(row["Neutral point s (m)"] == pytest.approx(10.0) for row in end_rows)
    assert all(row["Anchorage-set loss at anchorage (MPa)"] == pytest.approx(120.0) for row in end_rows)
    station_rows = anchorage_set_station_rows(rows, end_rows, length_m=20.0)
    assert all(row["Stress after anchorage set (MPa)"] == pytest.approx(1280.0) for row in station_rows)


def test_ptloss2r2_asymmetric_simultaneous_both_end_is_not_hardcoded_to_midspan() -> None:
    original = anchorage_set_end_rows(
        _linear_asymmetric_both_end_friction_rows(
            left_gradient_mpa_per_m=8.0, right_gradient_mpa_per_m=12.0
        ),
        length_m=20.0,
        anchor_set_mm=6.0,
        ep_mpa=200000.0,
    )
    mirrored = anchorage_set_end_rows(
        _linear_asymmetric_both_end_friction_rows(
            left_gradient_mpa_per_m=12.0, right_gradient_mpa_per_m=8.0
        ),
        length_m=20.0,
        anchor_set_mm=6.0,
        ep_mpa=200000.0,
    )
    assert original[0]["Pre-seat no-movement s (m)"] == pytest.approx(12.0)
    assert mirrored[0]["Pre-seat no-movement s (m)"] == pytest.approx(8.0)
    n1 = float(original[0]["Neutral point s (m)"])
    n2 = float(mirrored[0]["Neutral point s (m)"])
    assert n1 != pytest.approx(10.0)
    assert n2 == pytest.approx(20.0 - n1, abs=1.0e-7)
    assert all(row["Compatibility set check (mm)"] == pytest.approx(6.0) for row in original + mirrored)



def test_ptloss2r1_default_crossbeam_t1_left_six_mm_solves_full_path_without_false_capacity_limit() -> None:
    system = default_tendon_system_rows()
    for row in system:
        if row["Tendon ID"] == "T1":
            row["Jacking end"] = "Left"
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    friction_rows = aashto_friction_wobble_station_rows(profile, system, length_m=20.0)
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=195000.0
    )
    t1 = next(row for row in end_rows if row["Tendon ID"] == "T1")
    assert t1["Status"] == "PREVIEW READY + NOTE"
    assert t1["Interaction mode"] == "SINGLE-END FRICTION-COUPLED"
    assert t1["Affected length (m)"] == pytest.approx(20.0)
    assert t1["Full tendon affected"] is True
    assert float(t1["Dead-end anchorage-set loss (MPa)"]) > 0.0
    assert t1["Compatibility set check (mm)"] == pytest.approx(6.0, abs=1.0e-7)

    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    t1_rows = [row for row in station_rows if row["Tendon ID"] == "T1"]
    assert t1_rows
    assert all(row["P after anchorage set (kN)"] is not None for row in t1_rows)
    assert all(
        float(row["P after anchorage set (kN)"]) <= float(row["P after friction (kN)"]) + 1.0e-8
        for row in t1_rows
    )

def test_ptloss2r3_equivalent_average_single_end_integrates_actual_station_distribution() -> None:
    friction_rows = _linear_left_friction_rows()
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=5.0, ep_mpa=200000.0
    )
    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    summary = anchorage_set_equivalent_average_summary(
        station_rows, end_rows, length_m=20.0
    )
    assert summary["status"] == "PASS"
    assert summary["equivalent_average_loss_mpa"] == pytest.approx(50.0)
    assert summary["expected_average_loss_mpa"] == pytest.approx(50.0)
    assert summary["max_compatibility_residual_mpa"] == pytest.approx(0.0, abs=1.0e-9)
    tendon = summary["tendon_rows"][0]
    assert tendon["Equivalent average loss (MPa)"] == pytest.approx(50.0)
    assert tendon["Equivalent average loss (%)"] == pytest.approx(100.0 * 50.0 / 1400.0)


def test_ptloss2r3_equivalent_average_both_end_is_double_end_compatibility_average() -> None:
    friction_rows = _linear_both_end_friction_rows()
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=200000.0
    )
    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    summary = anchorage_set_equivalent_average_summary(
        station_rows, end_rows, length_m=20.0
    )
    # Two simultaneous 6 mm seating movements over 20 m: Ep*(12/20000)=120 MPa.
    assert summary["status"] == "PASS"
    assert summary["equivalent_average_loss_mpa"] == pytest.approx(120.0)
    assert summary["expected_average_loss_mpa"] == pytest.approx(120.0)
    assert summary["equivalent_average_loss_percent"] == pytest.approx(100.0 * 120.0 / 1400.0)


def test_ptloss2r3_independent_dense_grid_matches_asymmetric_simultaneous_both_end_solver() -> None:
    left_gradient = 8.0
    right_gradient = 12.0
    friction_rows = _linear_asymmetric_both_end_friction_rows(
        left_gradient_mpa_per_m=left_gradient,
        right_gradient_mpa_per_m=right_gradient,
    )
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=200000.0
    )
    independent = _independent_simultaneous_both_end_grid_solution(
        length_m=20.0,
        fpj_mpa=1400.0,
        left_gradient_mpa_per_m=left_gradient,
        right_gradient_mpa_per_m=right_gradient,
        anchor_set_mm=6.0,
        ep_mpa=200000.0,
    )
    sn, meeting, left_loss, right_loss = independent
    by_end = {row["Seating end"]: row for row in end_rows}
    assert by_end["Left"]["Interaction mode"] == "BOTH-END SIMULTANEOUS COUPLED"
    assert float(by_end["Left"]["Neutral point s (m)"]) == pytest.approx(sn, abs=2.0e-4)
    assert float(by_end["Left"]["Meeting stress after seating (MPa)"]) == pytest.approx(meeting, abs=2.0e-3)
    assert float(by_end["Left"]["Anchorage-set loss at anchorage (MPa)"]) == pytest.approx(left_loss, abs=2.0e-3)
    assert float(by_end["Right"]["Anchorage-set loss at anchorage (MPa)"]) == pytest.approx(right_loss, abs=2.0e-3)



def test_ptloss2r3a_independent_verifier_exposes_numeric_difference_evidence() -> None:
    friction_rows = _linear_asymmetric_both_end_friction_rows(
        left_gradient_mpa_per_m=8.0,
        right_gradient_mpa_per_m=12.0,
    )
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=200000.0
    )
    qa = independent_both_end_dense_grid_validation(
        friction_rows,
        end_rows,
        length_m=20.0,
        anchor_set_mm=6.0,
        ep_mpa=200000.0,
        n_steps=6000,
    )
    assert qa["status"] == "PASS"
    assert qa["max_neutral_station_diff_m"] <= qa["station_tolerance_m"]
    assert qa["max_meeting_stress_diff_mpa"] <= qa["stress_tolerance_mpa"]
    assert qa["max_left_anchor_loss_diff_mpa"] <= qa["stress_tolerance_mpa"]
    assert qa["max_right_anchor_loss_diff_mpa"] <= qa["stress_tolerance_mpa"]
    assert qa["tendon_rows"][0]["Status"] == "PASS"


def test_ptloss2r2_default_crossbeam_both_end_tendons_solve_simultaneous_preview() -> None:
    system = default_tendon_system_rows()
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    friction_rows = aashto_friction_wobble_station_rows(profile, system, length_m=20.0)
    end_rows = anchorage_set_end_rows(
        friction_rows, length_m=20.0, anchor_set_mm=6.0, ep_mpa=195000.0
    )
    summary = anchorage_set_summary(end_rows)
    assert len(end_rows) == 16
    assert summary["calculated_end_count"] == 16
    assert summary["review_end_count"] == 0
    assert all(row["Interaction mode"] == "BOTH-END SIMULTANEOUS COUPLED" for row in end_rows)
    assert all(row["Pre-seat no-movement s (m)"] == pytest.approx(10.0) for row in end_rows)
    assert all(row["Neutral point s (m)"] == pytest.approx(10.0) for row in end_rows)


def test_ptloss2b_new_project_default_anchorage_set_is_six_mm_design_assumption() -> None:
    defaults = default_crossbeam_prestress_loss_settings()
    assert DEFAULT_ANCHORAGE_SET_MM == pytest.approx(6.0)
    assert defaults["anchorage_set_mm"] == pytest.approx(6.0)


def test_ptloss2_zero_set_keeps_component_input_required() -> None:
    end_rows = anchorage_set_end_rows(
        _linear_left_friction_rows(), length_m=20.0, anchor_set_mm=0.0, ep_mpa=200000.0
    )
    summary = anchorage_set_summary(end_rows)
    assert end_rows[0]["Status"] == "INPUT REQUIRED"
    assert end_rows[0]["Affected length (m)"] is None
    assert summary["value"] == "INPUT REQUIRED"
    assert summary["calculated_end_count"] == 0


def test_ptloss2_settings_persist_with_existing_crossbeam_loss_metadata() -> None:
    state = {CB_LOSS_ANCHORAGE_SET_MM_KEY: 7.0, CB_LOSS_EP_MPA_KEY: 197000.0}
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    restored_state: dict[str, object] = {}
    restored = restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata}, restored_state
    )
    assert metadata["schema_version"] == 2
    assert metadata["anchorage_set_mm"] == pytest.approx(7.0)
    assert metadata["ep_mpa"] == pytest.approx(197000.0)
    assert restored is not None
    assert restored_state[CB_LOSS_ANCHORAGE_SET_MM_KEY] == pytest.approx(7.0)
    assert restored_state[CB_LOSS_EP_MPA_KEY] == pytest.approx(197000.0)


def test_ptloss2r2_ui_exposes_single_and_simultaneous_both_end_methods_without_releasing_pe_eff() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    anchorage_block = source.split("with anchorage_set_tab:", maxsplit=1)[1].split(
        "with elastic_shortening_tab:", maxsplit=1
    )[0]
    assert "Anchorage Set / Draw-in — validated preview + on-demand independent QA" in anchorage_block
    assert "SINGLE-END FRICTION-COUPLED" in source
    assert "Simultaneous both-end stressing / seating — PTLOSS2R2" in source
    assert "Jack = Both means simultaneous equal left/right stressing" in source
    assert "Tendon force profile — before / after anchorage seating" in anchorage_block
    assert "After Anchorage Set" in source
    assert "Affected length sₐ" in source
    assert "Equivalent average anchor-set loss" in anchorage_block
    assert "Selected tendon —" in anchorage_block
    assert "Three-point force-profile QA" in anchorage_block
    assert "Independent simultaneous-both-end numerical verification" in source
    assert "fig.update_yaxes(range=[y_min - margin, y_max + margin])" in source
    assert "Pe and Pe_eff remain locked" in anchorage_block




def test_ptloss2r3b_heavy_independent_validation_is_explicit_button_gated_and_fingerprint_scoped() -> None:
    import ast

    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    render_page = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_crossbeam_prestress_loss_page"
    )
    render_source = ast.get_source_segment(source, render_page) or ""
    assert "independent_both_end_dense_grid_validation(" not in render_source

    audit = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_anchorage_formula_unit_audit"
    )
    audit_source = ast.get_source_segment(source, audit) or ""
    assert audit_source.count("independent_both_end_dense_grid_validation(") == 1
    assert "Run / Refresh Independent Both-End Validation" in audit_source
    assert "if st.button(" in audit_source
    assert audit_source.index("if st.button(") < audit_source.index(
        "independent_both_end_dense_grid_validation("
    )
    assert "QA validation requires refresh" in audit_source
    assert "normal Streamlit reruns" in audit_source
    assert "CB_PTLoss_INDEPENDENT_QA_FINGERPRINT_KEY" in source
    assert "stored_fingerprint != str(fingerprint)" in source
    assert 'return None, "STALE"' in source

def test_ptloss2_ui_loss_defaults_use_valid_session_state_get_arity_and_include_new_fields() -> None:
    import ast

    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_loss_setting_defaults_from_state"
    )
    get_calls = []
    dict_keys: set[str] = set()
    for node in ast.walk(target):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    dict_keys.add(key.value)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "get":
            continue
        owner = node.func.value
        if not (
            isinstance(owner, ast.Attribute)
            and owner.attr == "session_state"
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "st"
        ):
            continue
        get_calls.append(node)
    assert get_calls
    assert all(len(call.args) == 2 and not call.keywords for call in get_calls)
    assert {
        "internal_mu",
        "internal_k_per_m",
        "external_deviator_mu",
        "external_inadvertent_angle_rad",
        "anchorage_set_mm",
        "ep_mpa",
    }.issubset(dict_keys)

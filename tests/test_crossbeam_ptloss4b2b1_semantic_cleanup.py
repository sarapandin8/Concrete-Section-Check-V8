from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
)
from concrete_pmm_pro.crossbeam.event_stage_stress import (
    run_crossbeam_event_stage_stress_sources,
)
from concrete_pmm_pro.crossbeam.time_dependent_loss import (
    LOW_RELAXATION_STEEL,
    run_crossbeam_lightweight_time_dependent_loss,
)
from concrete_pmm_pro.ui.crossbeam_pages import _crossbeam_td_loss_basis_detail
from tests.test_crossbeam_ptloss4a_time_dependent import _sources


def test_time_dependent_code_trace_is_construction_route_specific() -> None:
    segmental = _crossbeam_td_loss_basis_detail(CONSTRUCTION_METHOD_PRECAST)
    nonsegmental = _crossbeam_td_loss_basis_detail(CONSTRUCTION_METHOD_CIP)

    assert "§5.9.3.4 refined framework" in segmental
    assert "Precast Segmental" in segmental
    assert "§5.9.3.4.5" not in segmental
    assert "§5.9.3.4.5" in nonsegmental
    assert "nonsegmental" in nonsegmental.lower()


def test_event_audit_exposes_raw_forces_and_unambiguous_stage_change_labels() -> None:
    (
        _length_m,
        _definitions,
        _segments,
        system,
        _settings,
        es,
        model,
        profile,
    ) = _sources()

    result = run_crossbeam_event_stage_stress_sources(
        model=model,
        lightweight_es_result=es,
        profile_rows=profile,
        system_rows=system,
        later_permanent_load_delta_fcgp_mpa=0.0,
    )

    assert result["ready"] is True
    stress_rows = result["stress_audit_rows"]
    assert len(stress_rows) == 3
    assert stress_rows[0]["N (kN; compression +)"] == pytest.approx(26999.999, rel=1e-3)
    assert "M (kN-m; sagging +)" in stress_rows[0]
    assert stress_rows[0]["f_cgp (MPa; compression +)"] == pytest.approx(
        stress_rows[0]["N/A (MPa; compression +)"]
        + stress_rows[0]["-M*y/I (MPa; compression +)"],
        abs=1.0e-9,
    )

    summary = {
        row["Quantity"]: row
        for row in result["response_verification"]["summary_rows"]
    }
    assert "Stage max |M| (kN-m)" in summary
    assert "Stage max |V| (kN)" in summary
    assert "Stage max |v| (mm)" in summary
    assert "f_cgp at max-change row (MPa)" in summary
    assert "max stationwise |ΔM|" in summary["Stage max |M| (kN-m)"]["Basis"]
    assert "max stationwise |Δf_cgp|" in summary[
        "f_cgp at max-change row (MPa)"
    ]["Basis"]


def test_ptloss4b2b1_keeps_accepted_loss_result_and_updates_scope_wording() -> None:
    (
        length_m,
        definitions,
        segments,
        system,
        settings,
        es,
        model,
        profile,
    ) = _sources()

    result = run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        system_rows=system,
        construction_method=CONSTRUCTION_METHOD_PRECAST,
        rh_percent=75.0,
        load_age_days=28.0,
        curing_end_age_days=7.0,
        final_age_days=18250.0,
        grout_age_days=28.0,
        falsework_removal_age_days=35.0,
        permanent_load_age_days=90.0,
        linear_stage_model=model,
        profile_rows=profile,
        later_permanent_load_delta_fcgp_mpa=0.0,
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )

    assert result["time_dependent_loss_mpa"] == pytest.approx(127.149115, abs=1.0e-5)
    assert result["scope_guard"].startswith("PTLOSS4B2B1 uses one event solve")


def test_ptloss4b2b1_ui_print_tables_show_raw_n_m_and_current_milestone() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split("with time_dependent_tab:", 1)[1].split("with audit_tab:", 1)[0]

    assert "PTLOSS4B2B1 keeps the route event-based and lightweight" in block
    assert '"detail": td_loss_basis_detail' in block
    assert "N (kN; comp. +)" in block
    assert "M (kN·m; sag. +)" in block
    assert "Event Δ / max stationwise |Δ|" in block
    assert "PTLOSS4B2B1 does not assemble Pe/Pe_eff" in block

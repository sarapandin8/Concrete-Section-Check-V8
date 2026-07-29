from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_station_rows,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    default_column_stage_rows,
)
from concrete_pmm_pro.crossbeam.elastic_shortening import symmetric_stressing_group_rows
from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    run_crossbeam_lightweight_elastic_shortening,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_TD_CURING_END_AGE_DAYS_KEY,
    CB_LOSS_TD_FINAL_AGE_DAYS_KEY,
    CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY,
    CB_LOSS_TD_GROUT_AGE_DAYS_KEY,
    CB_LOSS_TD_INNER_PERIMETER_FACTOR_KEY,
    CB_LOSS_TD_LATER_LOAD_DELTA_FCGP_MPA_KEY,
    CB_LOSS_TD_LOAD_AGE_DAYS_KEY,
    CB_LOSS_TD_PERMANENT_LOAD_AGE_DAYS_KEY,
    CB_LOSS_TD_RELAXATION_STEEL_CLASS_KEY,
    CB_LOSS_TD_RH_PERCENT_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION,
    aashto_friction_wobble_station_rows,
    crossbeam_prestress_loss_settings_from_session_state,
    default_crossbeam_prestress_loss_settings,
    restore_crossbeam_prestress_loss_project_state,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    build_crossbeam_linear_stage_model,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    TENDON_BOND_STATE_UNBONDED,
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.time_dependent_loss import (
    LOW_RELAXATION_STEEL,
    aashto_creep_coefficient,
    aashto_incremental_shrinkage_strain,
    crossbeam_drying_geometry,
    run_crossbeam_lightweight_time_dependent_loss,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.ui import crossbeam_pages


def _sources(bond_state: str = TENDON_BOND_STATE_BONDED):
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    system = default_tendon_system_rows(8)
    for row in system:
        row["Bond state"] = bond_state
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=[f"T{i}" for i in range(1, 9)],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    settings = default_crossbeam_prestress_loss_settings()
    friction = aashto_friction_wobble_station_rows(
        profile,
        system,
        length_m=length_m,
        internal_mu=settings["internal_mu"],
        internal_k_per_m=settings["internal_k_per_m"],
        external_deviator_mu=settings["external_deviator_mu"],
        external_inadvertent_angle_rad=settings[
            "external_inadvertent_angle_rad"
        ],
    )
    ends = anchorage_set_end_rows(
        friction,
        length_m=length_m,
        anchor_set_mm=settings["anchorage_set_mm"],
        ep_mpa=settings["ep_mpa"],
    )
    post_anchor = anchorage_set_station_rows(
        friction, ends, length_m=length_m
    )
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(length_m),
        profile_rows=profile,
    )
    groups = symmetric_stressing_group_rows(
        profile, system, length_m=length_m
    )
    es = run_crossbeam_lightweight_elastic_shortening(
        model=model,
        profile_rows=profile,
        system_rows=system,
        anchorage_station_rows=post_anchor,
        ordered_group_rows=groups,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
    )
    assert es["ready"] is True
    return length_m, definitions, segments, system, settings, es, model, profile


def _run_td(construction_method: str = CONSTRUCTION_METHOD_PRECAST):
    length_m, definitions, segments, system, settings, es, model, profile = _sources()
    return run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        system_rows=system,
        construction_method=construction_method,
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


def test_drying_geometry_is_length_weighted_and_conservative() -> None:
    length_m, definitions, segments, _system, _settings, _es, _model, _profile = _sources()
    result_0 = crossbeam_drying_geometry(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        inner_perimeter_factor=0.0,
    )
    result_50 = crossbeam_drying_geometry(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        inner_perimeter_factor=0.5,
    )
    result_100 = crossbeam_drying_geometry(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        inner_perimeter_factor=1.0,
    )
    assert result_50["ready"] is True
    assert result_50["covered_length_m"] == pytest.approx(20.0)
    assert sum(row["Concrete volume (m³)"] for row in result_50["rows"]) == pytest.approx(
        result_50["total_volume_m3"]
    )
    assert sum(row["Drying surface (m²)"] for row in result_50["rows"]) == pytest.approx(
        result_50["total_drying_surface_m2"]
    )
    assert result_0["total_drying_surface_m2"] < result_50["total_drying_surface_m2"] < result_100["total_drying_surface_m2"]
    assert result_0["v_over_s_mm"] > result_50["v_over_s_mm"] > result_100["v_over_s_mm"]
    assert result_50["h0_m"] == pytest.approx(2.0 * result_50["v_over_s_m"])
    assert result_50["formula"] == "Σ(AiLi) / Σ(udry,iLi)"
    assert len(result_50["section_summary_rows"]) == 2
    local_by_role = {
        row["Section role"]: row for row in result_50["section_summary_rows"]
    }
    assert local_by_role["Solid"]["Local V/S (in.)"] == pytest.approx(18.77320756535903, rel=1.0e-8)
    assert local_by_role["Hollow"]["Local V/S (in.)"] == pytest.approx(8.185366751370205, rel=1.0e-8)
    arithmetic_mean = 0.5 * (
        local_by_role["Solid"]["Local V/S (in.)"]
        + local_by_role["Hollow"]["Local V/S (in.)"]
    )
    assert result_50["v_over_s_in"] == pytest.approx(12.73174724, rel=1.0e-8)
    assert result_50["v_over_s_in"] != pytest.approx(arithmetic_mean)
    assert result_50["local_v_over_s_min_in"] == pytest.approx(
        local_by_role["Hollow"]["Local V/S (in.)"]
    )
    assert result_50["local_v_over_s_max_in"] == pytest.approx(
        local_by_role["Solid"]["Local V/S (in.)"]
    )


def test_time_factor_routes_use_elapsed_creep_and_incremental_shrinkage_maturity() -> None:
    creep = aashto_creep_coefficient(
        rh_percent=75.0,
        v_over_s_mm=150.0,
        fci_mpa=36.0,
        load_age_days=28.0,
        final_age_days=3650.0,
    )
    shrinkage = aashto_incremental_shrinkage_strain(
        rh_percent=75.0,
        v_over_s_mm=150.0,
        fci_mpa=36.0,
        curing_end_age_days=7.0,
        interval_start_age_days=28.0,
        final_age_days=3650.0,
    )
    assert creep["elapsed_days"] == pytest.approx(3622.0)
    assert 0.0 < creep["ktd_creep"] < 1.0
    assert creep["psi"] > 0.0
    assert shrinkage["start_maturity_days"] == pytest.approx(21.0)
    assert shrinkage["final_maturity_days"] == pytest.approx(3643.0)
    assert shrinkage["delta_ktd_shrinkage"] > 0.0
    assert shrinkage["shrinkage_strain"] > 0.0


def test_precast_segmental_route_uses_one_event_solve_and_interval_stress_sources() -> None:
    result = _run_td(CONSTRUCTION_METHOD_PRECAST)
    assert result["ready"] is True
    assert result["adoptable"] is False
    assert result["status"] == "EVENT-BASED TIME-STEP QA READY — FINAL ADOPTION BLOCKED"
    assert result["solve_count"] == 1
    assert result["creep_loss_mpa"] > 0.0
    assert result["shrinkage_loss_mpa"] == pytest.approx(40.8905895965, rel=1.0e-9)
    assert result["relaxation_loss_mpa"] == pytest.approx(7.8886818546, rel=1.0e-9)
    assert result["time_dependent_loss_mpa"] == pytest.approx(
        result["creep_loss_mpa"] + result["shrinkage_loss_mpa"] + result["relaxation_loss_mpa"]
    )
    assert result["interaction"]["Kdf"] == pytest.approx(0.8942766001, rel=1.0e-9)
    assert result["route"] == "PRECAST SEGMENTAL — EVENT-BASED TIME-STEP QA"
    assert result["schedule_source"]["ready"] is True
    assert result["schedule_source"]["immediate_grout"] is True
    assert result["schedule_time_step"]["interval_count"] == 3
    assert sum(
        row["Creep increment (MPa)"]
        for row in result["schedule_time_step"]["rows"]
    ) == pytest.approx(result["creep_loss_mpa"], rel=1.0e-12)
    assert sum(
        row["Shrinkage increment (MPa)"]
        for row in result["schedule_time_step"]["rows"]
    ) == pytest.approx(result["shrinkage_loss_mpa"], rel=1.0e-12)
    assert sum(
        row["Relaxation increment (MPa)"]
        for row in result["schedule_time_step"]["rows"]
    ) == pytest.approx(result["relaxation_loss_mpa"], rel=1.0e-12)
    assert result["schedule_time_step"]["closure"]["total_residual_mpa"] == pytest.approx(
        0.0, abs=1.0e-12
    )
    assert any("Falsework-removal stress redistribution" in note for note in result["review_notes"])
    assert result["event_stress_source"]["ready"] is True
    assert all(row["f_cgp interval (MPa)"] >= 0.0 for row in result["schedule_time_step"]["rows"])
    assert result["v_over_s_commentary_advisory"] is True
    assert any("Specification lower bound ks = 1.0 is applied" in note for note in result["calibration_advisories"])


def test_cip_route_keeps_commentary_range_as_advisory_not_hard_code_block() -> None:
    result = _run_td(CONSTRUCTION_METHOD_CIP)
    assert result["ready"] is True
    assert result["construction_method"] == CONSTRUCTION_METHOD_CIP
    assert result["route"].startswith("CAST-IN-PLACE NONSEGMENTAL")
    assert result["adoptable"] is True
    assert result["status"] == "DESIGN ESTIMATE READY"
    assert result["blocking_review_notes"] == []
    assert result["v_over_s_commentary_advisory"] is True
    assert any("6.0-in. range considered" in note for note in result["calibration_advisories"])
    assert any("engineering review" in note for note in result["calibration_advisories"])


def test_unbonded_route_is_source_blocked_in_ptloss4a() -> None:
    length_m, definitions, segments, system, settings, es, model, profile = _sources(
        TENDON_BOND_STATE_UNBONDED
    )
    result = run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        system_rows=system,
        construction_method=CONSTRUCTION_METHOD_CIP,
        rh_percent=75.0,
        load_age_days=28.0,
        curing_end_age_days=7.0,
        final_age_days=18250.0,
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    assert result["ready"] is False
    assert result["status"] == "SOURCE BLOCKED"
    assert result["solve_count"] == 0
    assert any("bonded after grouting" in issue for issue in result["issues"])


def test_ptloss4a_inputs_round_trip_in_project_metadata_without_results() -> None:
    state = {
        CB_LOSS_TD_RH_PERCENT_KEY: 68.0,
        CB_LOSS_TD_LOAD_AGE_DAYS_KEY: 35.0,
        CB_LOSS_TD_CURING_END_AGE_DAYS_KEY: 5.0,
        CB_LOSS_TD_FINAL_AGE_DAYS_KEY: 36500.0,
        CB_LOSS_TD_INNER_PERIMETER_FACTOR_KEY: 1.0,
        CB_LOSS_TD_RELAXATION_STEEL_CLASS_KEY: LOW_RELAXATION_STEEL,
        CB_LOSS_TD_GROUT_AGE_DAYS_KEY: 35.0,
        CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY: 42.0,
        CB_LOSS_TD_PERMANENT_LOAD_AGE_DAYS_KEY: 120.0,
    }
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    restored_state: dict[str, object] = {}
    restored = restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata}, restored_state
    )
    assert metadata["schema_version"] == CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION == 8
    assert metadata["td_rh_percent"] == pytest.approx(68.0)
    assert metadata["td_load_age_days"] == pytest.approx(35.0)
    assert metadata["td_curing_end_age_days"] == pytest.approx(5.0)
    assert metadata["td_final_age_days"] == pytest.approx(36500.0)
    assert metadata["td_inner_perimeter_factor"] == pytest.approx(1.0)
    assert metadata["td_grout_age_days"] == pytest.approx(35.0)
    assert metadata["td_falsework_removal_age_days"] == pytest.approx(42.0)
    assert metadata["td_permanent_load_age_days"] == pytest.approx(120.0)
    assert "time_dependent_result" not in metadata
    assert restored is not None
    assert restored_state[CB_LOSS_TD_RH_PERCENT_KEY] == pytest.approx(68.0)
    assert restored_state[CB_LOSS_TD_FINAL_AGE_DAYS_KEY] == pytest.approx(36500.0)
    assert restored_state[CB_LOSS_TD_GROUT_AGE_DAYS_KEY] == pytest.approx(35.0)
    assert restored_state[CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY] == pytest.approx(42.0)
    assert restored_state[CB_LOSS_TD_PERMANENT_LOAD_AGE_DAYS_KEY] == pytest.approx(120.0)



def test_ptloss4b2_time_dependent_widget_defaults_include_later_load_delta_without_unpack_error() -> None:
    settings = default_crossbeam_prestress_loss_settings()
    state: dict[str, object] = {CB_LOSS_TD_RH_PERCENT_KEY: 68.0}

    crossbeam_pages._initialize_crossbeam_td_session_defaults(state, settings)

    assert state[CB_LOSS_TD_RH_PERCENT_KEY] == pytest.approx(68.0)
    assert state[CB_LOSS_TD_PERMANENT_LOAD_AGE_DAYS_KEY] == pytest.approx(
        settings["td_permanent_load_age_days"]
    )
    assert state[CB_LOSS_TD_LATER_LOAD_DELTA_FCGP_MPA_KEY] == pytest.approx(
        settings["td_later_load_delta_fcgp_mpa"]
    )
    assert len(state) == 10

def test_time_dependent_ui_is_on_demand_and_contains_no_structural_solver_call() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split("with time_dependent_tab:", 1)[1].split("with audit_tab:", 1)[0]
    assert "Lightweight Time-Dependent Losses — event-based schedule preview" in block
    assert "Run Event-Based Time-Step Preview" in block
    assert "0 solves on open" in block
    assert "one no-contact frame solve" in block
    assert "BG40 relaxation interaction cap are not reused" in block
    assert "Member-equivalent V/S" in block
    assert "Local V/S range" in block
    assert "Loss geometry source" in block
    assert "MIXED SOLID + HOLLOW" in block
    assert "Segment Layout ·" in block
    assert "Σ(AᵢLᵢ) / Σ(u_dry,ᵢLᵢ)" in block
    assert "Drying geometry — station and section source" in block
    assert "Drying geometry — volume and drying-surface contributions" in block
    assert "Volume share (%)" in block
    assert "Drying-surface share (%)" in block
    assert "Representative section / interaction source" in block
    assert "Prestressing-steel properties by Tendon" in block
    assert "ptloss4a-print-table-heading" in block
    assert "st.json(current_td.get(\"section_source\")" not in block
    assert "εsh increment" in block and "με" in block
    assert block.index("run_crossbeam_lightweight_time_dependent_loss") > block.index("if run_td:")
    assert "run_crossbeam_linear_stage_response" not in block
    assert "run_crossbeam_incremental_contact_qa" not in block
    assert "run_crossbeam_incremental_contact_mesh_sensitivity" not in block
    assert "Effective Prestress assembly remains locked" in block
    assert "Precast Segmental construction schedule" in block
    assert "Incremental construction-schedule loss audit" in block
    assert "Time-step component closure" in block
    assert "tg → tr → tf · no permanent-load events" in block
    assert "tg → tr → tp… → tf · event stress by interval" in block


def test_ptloss4a1a1_print_audit_uses_static_compact_tables_and_one_equation_block() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split("with time_dependent_tab:", 1)[1].split("with audit_tab:", 1)[0]
    assert "ptloss4a-audit-table-shell" in block
    assert "ptloss4a-audit-table" in block
    assert block.count("_render_ptloss4a_static_table(") >= 10
    assert "Avg stress after ES (MPa)" in block
    assert "fpy = 0.90fpu (MPa)" in block
    assert "S share (%)" in block
    assert "Section-type contribution shares" in block
    assert "st.dataframe(" not in block
    assert r"\begin{aligned}" in block
    assert block.count("st.latex(") == 1


def test_ptloss4a_static_table_keeps_right_side_audit_values_in_print_dom(monkeypatch) -> None:
    rendered: list[str] = []

    def _capture(body: str, **_kwargs) -> None:
        rendered.append(body)

    monkeypatch.setattr(crossbeam_pages.st, "markdown", _capture)
    crossbeam_pages._render_ptloss4a_static_table(
        pd.DataFrame(
            [
                {
                    "Tendon": "T1",
                    "Aps (mm²)": 2660.0,
                    "Length-average stress after ES (MPa)": 1206.8655,
                    "Stations": 41,
                }
            ]
        ),
        columns=[
            ("Tendon", "Tendon"),
            ("Aps (mm²)", "Aps (mm²)"),
            ("Length-average stress after ES (MPa)", "Avg stress after ES (MPa)"),
            ("Stations", "Stations"),
        ],
        formats={
            "Aps (mm²)": "{:.1f}",
            "Length-average stress after ES (MPa)": "{:.4f}",
            "Stations": "{:.0f}",
        },
        widths=[18, 22, 42, 18],
    )
    html = "".join(rendered)
    assert "Avg stress after ES (MPa)" in html
    assert "1206.8655" in html
    assert "2660.0" in html
    assert "41" in html
    assert "<colgroup>" in html
    assert "ptloss4a-audit-table-shell" in html


def test_segmental_schedule_delayed_grouting_is_explicitly_partial() -> None:
    length_m, definitions, segments, system, settings, es, model, profile = _sources()
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
        grout_age_days=35.0,
        falsework_removal_age_days=42.0,
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
    baseline = _run_td(CONSTRUCTION_METHOD_PRECAST)
    assert result["ready"] is True
    assert result["schedule_source"]["immediate_grout"] is False
    assert result["schedule_time_step"]["pre_grouting_interval_days"] == pytest.approx(7.0)
    assert result["creep_loss_mpa"] < baseline["creep_loss_mpa"]
    assert result["shrinkage_loss_mpa"] < baseline["shrinkage_loss_mpa"]
    assert any("pre-grouting interval" in note for note in result["blocking_review_notes"])


def test_segmental_schedule_rejects_nonchronological_ages() -> None:
    length_m, definitions, segments, system, settings, es, model, profile = _sources()
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
        grout_age_days=35.0,
        falsework_removal_age_days=30.0,
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
    assert result["ready"] is False
    assert result["status"] == "SOURCE BLOCKED"
    assert any("Falsework removal age" in issue for issue in result["issues"])

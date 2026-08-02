from pathlib import Path

from concrete_pmm_pro.crossbeam.station_force_contract import (
    canonical_storage_contract,
    default_station_force_contract,
    validate_station_force_contract,
)


def test_blank_fea_metadata_is_not_a_load_or_analysis_warning() -> None:
    contract = default_station_force_contract()
    contract["fea_program"] = ""
    contract["model_revision"] = ""
    contract["adopted_total_loss_percent"] = 15.0
    errors, warnings = validate_station_force_contract(contract, response_type="ULS")
    assert not errors
    assert not any("FEA Program" in item for item in warnings)
    assert not any("model / revision" in item for item in warnings)


def test_crossbeam_storage_contract_forces_fixed_canonical_units_and_signs() -> None:
    contract = default_station_force_contract()
    contract.update(
        {
            "source_force_unit": "N",
            "source_moment_unit": "N-mm",
            "p_sign": "TENSION_POSITIVE",
            "v2_sign": "DOWNWARD_POSITIVE",
            "t_sign": "OPPOSITE_RIGHT_HAND_ABOUT_INCREASING_S",
            "m3_sign": "HOGGING_POSITIVE",
        }
    )
    canonical = canonical_storage_contract(contract)
    assert canonical["source_force_unit"] == "kN"
    assert canonical["source_moment_unit"] == "kN-m"
    assert canonical["p_sign"] == "COMPRESSION_POSITIVE"
    assert canonical["v2_sign"] == "UPWARD_POSITIVE"
    assert canonical["t_sign"] == "RIGHT_HAND_ABOUT_INCREASING_S"
    assert canonical["m3_sign"] == "SAGGING_POSITIVE"


def test_crossbeam_loads_ui_hides_source_unit_axis_and_stage_declaration_controls() -> None:
    source = Path("concrete_pmm_pro/ui/loads_page.py").read_text(encoding="utf-8")
    assert "FEA source, units, axes, and Transfer / Service declarations" not in source
    assert "Source-axis and sign mapping" not in source
    assert "crossbeam_loads1b_fea_program" not in source
    assert "crossbeam_loads1b_model_revision" not in source
    assert "crossbeam_loads1b_source_force_unit" not in source
    assert "crossbeam_loads1b_source_moment_unit" not in source
    assert 'if settings.member_type != "portal_frame_crossbeam":' in source
    assert "Axis convention for load input" in source
    assert "rows_are_canonical=True" in source


def test_crossbeam_shear_removes_redundant_amber_scope_warning_and_metadata_noise() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    start = source.index("def _render_crossbeam_uls_shear_workspace")
    end = source.index("def _crossbeam_transfer_demand_dataframe")
    shear = source[start:end]
    assert "FEA Program is blank" not in shear
    assert "FEA model / revision is blank" not in shear
    assert 'st.warning(str(governing.get("Notes")' not in shear
    assert 'with st.expander("Calculation limitations"' in shear
    assert 'with st.expander("Source notes"' in shear
    assert 'st.markdown(f"- {message}")' in shear
    assert "imported station-force row" in shear


def test_crossbeam_uls_dashboard_uses_on_demand_result_mode_not_runtime_pass() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    start = source.index("def _commercial_analysis_dashboard_cards")
    end = source.index("def _analysis_subtabs_for_workflow")
    dashboard = source[start:end]
    assert 'status_title = "Result mode"' in dashboard
    assert 'readiness = "ON-DEMAND"' in dashboard
    assert "The selected ULS check reports its engineering status below" in dashboard

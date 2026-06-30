from __future__ import annotations

import pandas as pd
import pytest

from concrete_pmm_pro.ui import materials_page, section_builder
from concrete_pmm_pro.ui.rebar_page import load_rebar_database, normalize_rebar_table_for_bar_size_sync, rebars_from_dataframe


def test_materials_page_is_library_only() -> None:
    source = open(materials_page.__file__, encoding="utf-8").read()

    assert "Active / primary section concrete material" not in source
    assert "Default deck / topping concrete material" not in source
    assert "Active rebar material" not in source
    assert "Active prestress material" not in source
    assert "library only" in source
    assert "Section Builder" in source


def test_section_builder_has_railway_u_girder_stage_material_assignment() -> None:
    source = open(section_builder.__file__, encoding="utf-8").read()

    assert "Precast web concrete material" in source
    assert "CIP slab concrete material" in source
    assert "Precast web f'ci at transfer" in source
    assert "railway_u_girder_stage_settings" in source
    assert "web-only; service = full U-girder" in source


def test_standard_rebar_material_is_forced_from_bar_size_even_for_legacy_rows() -> None:
    rebar_db = load_rebar_database()
    previous = pd.DataFrame(
        [{"Active": True, "Label": "B1", "x_mm": 0, "y_mm": 0, "Bar Size": "DB32", "Diameter_mm": 32, "Material": "SD40", "Count": 1, "Note": ""}]
    )

    normalized = normalize_rebar_table_for_bar_size_sync(previous, previous, rebar_db)
    result = rebars_from_dataframe(normalized, rebar_db)

    assert normalized.loc[0, "Material"] == "SD50"
    assert not result.errors
    assert result.rebars[0].material_name == "SD50"


def test_rebar_parser_corrects_imported_standard_bar_material_mismatch() -> None:
    rebar_db = load_rebar_database()
    imported = pd.DataFrame(
        [{"Active": True, "Label": "B1", "x_mm": 0, "y_mm": 0, "Bar Size": "DB32", "Diameter_mm": 32, "Material": "SD40", "Count": 1, "Note": ""}]
    )

    result = rebars_from_dataframe(imported, rebar_db)

    assert not result.errors
    assert result.rebars[0].material_name == "SD50"
    assert any("entered Material 'SD40' was ignored" in warning for warning in result.warnings)


def test_prestress_product_is_source_of_truth_for_strength_properties() -> None:
    from concrete_pmm_pro.ui.prestress_page import normalize_prestress_table_for_effective_input_sync, load_prestress_steel_database

    prestress_db = load_prestress_steel_database()
    product = "12.7mm strand" if "12.7mm strand" in set(prestress_db["name"]) else str(prestress_db.iloc[0]["name"])
    db_row = prestress_db.loc[prestress_db["name"] == product].iloc[0]
    table = pd.DataFrame(
        [
            {
                "Active": True,
                "Label": "PS1",
                "Steel Type": "custom",
                "Product": product,
                "x_mm": 0.0,
                "y_mm": -500.0,
                "Area_mm2": 1.0,
                "Diameter_mm": 1.0,
                "Eq Steel Dia_mm": None,
                "fpy_MPa": 1.0,
                "fpu_MPa": 1.0,
                "Ep_MPa": 1.0,
                "Input Mode": "Passive",
                "Pe_eff_kN": 0.0,
                "fpe_MPa": 0.0,
                "fpj_ratio": 0.75,
                "loss_percent": 15.0,
                "Bonded": True,
                "Count": 1,
                "Strand Count": None,
                "Breaking Load_kN": None,
                "Duct Type": "",
                "Duct ID_mm": None,
                "Note": "",
            }
        ]
    )

    normalized = normalize_prestress_table_for_effective_input_sync(table, prestress_db)

    assert normalized.loc[0, "Area_mm2"] == pytest.approx(float(db_row["area_mm2"]))
    assert normalized.loc[0, "fpu_MPa"] == pytest.approx(float(db_row["fpu_MPa"]))
    assert normalized.loc[0, "Ep_MPa"] == pytest.approx(float(db_row["Ep_MPa"]))

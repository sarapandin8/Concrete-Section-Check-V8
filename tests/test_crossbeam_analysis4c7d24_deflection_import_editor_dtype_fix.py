from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import CROSSBEAM_SLS_DISPLACEMENT_COLUMNS
from concrete_pmm_pro.crossbeam.station_force_contract import canonical_sls_stage


def _load_production_normalizer():
    """Load only the production normalizer without importing Streamlit locally."""

    root = Path(__file__).resolve().parents[1]
    source_path = root / "concrete_pmm_pro" / "ui" / "analysis_page.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {
        "_analysis_value_is_blank",
        "_analysis_to_bool",
        "_normalize_crossbeam_sls_displacement_source_table",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in nodes} == wanted
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Any": object,
        "pd": pd,
        "canonical_sls_stage": canonical_sls_stage,
        "CROSSBEAM_SLS_DISPLACEMENT_COLUMNS": CROSSBEAM_SLS_DISPLACEMENT_COLUMNS,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_normalize_crossbeam_sls_displacement_source_table"]


def test_d24_imported_blank_text_columns_are_pinned_to_text_and_numeric_editor_dtypes() -> None:
    normalize = _load_production_normalizer()
    # Mirrors the failure mode from a CSV where optional text columns are blank,
    # so pandas infers them as float64/NaN, while stations look integer-like.
    imported = pd.DataFrame(
        {
            "Active": [True, True, True],
            "Station s (m)": [0, 1, 2],
            "Case Name": ["SLS-SERV", "SLS-SERV", "SLS-SERV"],
            "Stage": ["Final service stage"] * 3,
            "Vertical displacement (mm)": [0, -1, -2],
            "Source point": [float("nan")] * 3,
            "Note": [float("nan")] * 3,
        }
    )
    assert str(imported["Source point"].dtype) == "float64"

    normalized = normalize(imported)

    assert str(normalized["Active"].dtype) == "bool"
    assert str(normalized["Station s (m)"].dtype) == "float64"
    assert str(normalized["Vertical displacement (mm)"].dtype) == "float64"
    for column in ("Case Name", "Stage", "Source point", "Note"):
        assert normalized[column].dtype == object
    assert normalized["Source point"].tolist() == ["", "", ""]
    assert normalized["Note"].tolist() == ["", "", ""]


def test_d24_empty_editor_source_has_explicit_streamlit_compatible_schema() -> None:
    normalize = _load_production_normalizer()
    normalized = normalize(None)
    assert list(normalized.columns) == list(CROSSBEAM_SLS_DISPLACEMENT_COLUMNS)
    assert str(normalized["Active"].dtype) == "bool"
    assert str(normalized["Station s (m)"].dtype) == "float64"
    assert str(normalized["Vertical displacement (mm)"].dtype) == "float64"
    for column in ("Case Name", "Stage", "Source point", "Note"):
        assert normalized[column].dtype == object

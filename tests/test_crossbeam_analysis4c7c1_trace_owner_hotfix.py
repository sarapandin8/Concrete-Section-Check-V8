import ast
from pathlib import Path

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    normalize_construction_method,
)


ANALYSIS_PAGE = (
    Path(__file__).resolve().parents[1]
    / "concrete_pmm_pro"
    / "ui"
    / "analysis_page.py"
)


def test_analysis_page_uses_local_trace_owner_helper() -> None:
    source = ANALYSIS_PAGE.read_text(encoding="utf-8")

    assert "def _trace_owner_label(construction_method: str) -> str:" in source
    assert "from concrete_pmm_pro.crossbeam.uls_station_geometry import (\n    trace_owner_label," not in source
    assert "owner = trace_owner_label(" not in source
    assert "owner_label = trace_owner_label(" not in source
    assert source.count("_trace_owner_label(") >= 9
    assert '"Zone-owned"' in source
    assert '"Segment-owned"' in source


def test_local_trace_owner_helper_executes_for_both_construction_modes() -> None:
    tree = ast.parse(ANALYSIS_PAGE.read_text(encoding="utf-8"))
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_trace_owner_label"
    )
    namespace = {
        "CONSTRUCTION_METHOD_CIP": CONSTRUCTION_METHOD_CIP,
        "normalize_construction_method": normalize_construction_method,
    }
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(ANALYSIS_PAGE), "exec"), namespace)

    label = namespace["_trace_owner_label"]
    assert label("Cast-in-Place") == "Zone-owned"
    assert label("Precast Segmental") == "Segment-owned"

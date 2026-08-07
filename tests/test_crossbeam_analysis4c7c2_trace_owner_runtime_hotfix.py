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


def _owner_expression_nodes() -> list[ast.IfExp]:
    tree = ast.parse(ANALYSIS_PAGE.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.IfExp)
        and isinstance(node.body, ast.Constant)
        and node.body.value == "Zone-owned"
        and isinstance(node.orelse, ast.Constant)
        and node.orelse.value == "Segment-owned"
    ]


def test_analysis_page_has_no_late_bound_trace_owner_symbol() -> None:
    source = ANALYSIS_PAGE.read_text(encoding="utf-8")

    assert "_trace_owner_label" not in source
    assert "trace_owner_label(" not in source
    assert source.count('"Zone-owned" if normalize_construction_method(') >= 8
    assert source.count('else "Segment-owned"') >= 8


def test_inline_trace_owner_expression_executes_for_both_modes() -> None:
    nodes = _owner_expression_nodes()
    assert len(nodes) >= 8

    expression = nodes[0]
    code = compile(ast.Expression(body=expression), str(ANALYSIS_PAGE), "eval")
    namespace = {
        "CONSTRUCTION_METHOD_CIP": CONSTRUCTION_METHOD_CIP,
        "normalize_construction_method": normalize_construction_method,
    }

    namespace["construction_method"] = "Cast-in-Place"
    assert eval(code, namespace) == "Zone-owned"

    namespace["construction_method"] = "Precast Segmental"
    assert eval(code, namespace) == "Segment-owned"

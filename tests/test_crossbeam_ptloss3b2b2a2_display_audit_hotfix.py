from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.ui.crossbeam_pages import _ptloss3b2a_response_figure


def test_lightweight_display_audit_uses_current_shared_response_figure_contract() -> None:
    rows = [
        {
            "Element": "B1",
            "s (m)": 0.0,
            "M sagging-positive (kN-m)": -10.0,
            "N compression-positive (kN)": 1000.0,
        },
        {
            "Element": "B1",
            "s (m)": 1.0,
            "M sagging-positive (kN-m)": 20.0,
            "N compression-positive (kN)": 990.0,
        },
    ]
    figure = _ptloss3b2a_response_figure(
        rows,
        title="Crossbeam Moment — LIGHTWEIGHT CUMULATIVE ES STAGE",
        field="M sagging-positive (kN-m)",
        y_title="Moment M (kN-m; sagging +)",
        trace_name="Moment M",
    )
    assert list(figure.data[0].x) == [0.0, 1.0]
    assert list(figure.data[0].y) == [-10.0, 20.0]
    assert figure.layout.title.text == "Crossbeam Moment — LIGHTWEIGHT CUMULATIVE ES STAGE"
    assert figure.layout.yaxis.title.text == "Moment M (kN-m; sagging +)"


def test_lightweight_display_only_block_has_no_stale_helper_keywords() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split(
        '"Cumulative structural-response audit — display only", expanded=False', 1
    )[1].split("advanced_fingerprint =", 1)[0]
    assert "case_label=" not in block
    assert "response=" not in block
    assert 'field="M sagging-positive (kN-m)"' in block
    assert 'field="N compression-positive (kN)"' in block
    assert block.count("caption=") == 2

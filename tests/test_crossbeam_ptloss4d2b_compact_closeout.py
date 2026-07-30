from __future__ import annotations

from pathlib import Path


def test_ptloss4d2b_effective_prestress_main_view_is_compact_and_qa_is_collapsed() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")

    assert "Effective Prestress & External-FEA Handoff" in source
    assert "Average total loss — QA" in source
    assert "Average effective prestress" in source
    assert "Maximum local loss" in source
    assert "External FEA / SLS" in source
    assert 'with st.expander("QA formulas, closure, and averaging audit", expanded=False)' in source
    assert 'with st.expander("Station and tendon Effective Prestress preview", expanded=False)' in source
    assert 'with st.expander("Detailed sequential source rows", expanded=False)' in source
    assert 'with st.expander("FEA instructions, limitations, and traceability", expanded=False)' in source
    assert 'with st.expander("Formula and sequential stress-chain trace", expanded=True)' not in source
    assert '"Source readiness"' not in source


def test_ptloss4d2b_keeps_download_gating_and_external_fea_boundary() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")

    assert "disabled=not download_ready" in source
    assert "Do not apply the same losses twice; use exactly one FEA route" in source
    assert "External FEA calculates secondary prestress; import verified FEA SLS P/V2/M3 through Loads" in source
    assert "Download FEA workbook" in source
    assert "Download Tendon CSV" in source
    assert "Download Three-Point CSV" in source

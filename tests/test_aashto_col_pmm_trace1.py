from __future__ import annotations

import plotly.graph_objects as go

from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.ui.analysis_page import (
    _append_pmm_traceability_to_figure_title,
    _apply_pmm_traceability_to_summary,
    _pmm_traceability_context_for_code,
    _pmm_traceability_summary_cards,
)


def test_aashto_col_pmm_trace1_context_identifies_aashto_route_and_units() -> None:
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC PMM",
        prestress_included=False,
        bonded_prestress_included=False,
    )

    assert context["code_basis"] == PROJECT_CODE_AASHTO_LRFD
    assert context["code_edition"] == "AASHTO LRFD 9th Edition"
    assert context["pmm_route"] == "AASHTO LRFD Column/Pier PMM"
    assert "Section 5" in context["flexural_basis"]
    assert "AASHTO strain-controlled" in context["phi_basis"]
    assert "ksi/kips constants converted" in context["units_basis"]
    assert context["prestress_branch"] == "Ordinary rebar only"


def test_aashto_col_pmm_trace1_prestress_branch_is_not_confused_with_aci() -> None:
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC + Active Bonded Prestress PMM",
        prestress_included=True,
        bonded_prestress_included=True,
        unbonded_ignored_count=2,
    )

    assert context["pmm_route"] == "AASHTO LRFD Column/Pier PMM"
    assert "Bonded prestress included" in context["prestress_branch"]
    assert "unbonded ignored 2" in context["prestress_branch"]
    assert "ACI" not in context["pmm_route"]


def test_aashto_col_pmm_trace2_summary_cards_are_compact() -> None:
    cards = _pmm_traceability_summary_cards(
        _pmm_traceability_context_for_code(
            "AASHTO LRFD",
            "AASHTO LRFD 9th Edition",
            mode_label="RC PMM",
            prestress_included=False,
            bonded_prestress_included=False,
        )
    )
    by_title = {card["title"]: card for card in cards}

    assert by_title["Code Basis"]["value"] == "AASHTO LRFD 9th"
    assert by_title["PMM Route"]["value"] == "Column/Pier PMM"
    assert by_title["Prestress"]["value"] == "Ordinary rebar only"
    assert "φ / Units Trace" not in by_title


def test_aashto_col_pmm_trace1_selected_case_detail_fields_are_enriched() -> None:
    base_summary = {
        "selected_combo": "ULS-1",
        "analysis_mode": "RC PMM",
        "prestress_included": False,
    }
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC PMM",
        prestress_included=False,
        bonded_prestress_included=False,
    )
    enriched = _apply_pmm_traceability_to_summary(base_summary, context)

    assert enriched["code_basis"] == "AASHTO LRFD"
    assert enriched["code_edition"] == "AASHTO LRFD 9th Edition"
    assert enriched["pmm_route"] == "AASHTO LRFD Column/Pier PMM"
    assert enriched["pmm_route_short"] == "Column/Pier PMM"
    assert enriched["phi_basis"] == "AASHTO strain-controlled φ transition"
    assert enriched["units_basis"].startswith("SI solver units")
    assert enriched["compact_trace"] == "AASHTO LRFD 9th · Column/Pier PMM · SI-safe"
    assert base_summary.get("code_basis") is None


def test_aashto_col_pmm_trace1_plotly_title_gets_code_basis_subtitle_and_meta() -> None:
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC PMM",
        prestress_included=False,
        bonded_prestress_included=False,
    )
    fig = go.Figure()
    fig.update_layout(title="PMM Mux-Muy Slice")

    traced = _append_pmm_traceability_to_figure_title(fig, context)

    assert "AASHTO LRFD 9th · Column/Pier PMM · SI-safe" in traced.layout.title.text
    assert "Code basis:" not in traced.layout.title.text
    assert "Route:" not in traced.layout.title.text
    assert traced.layout.legend.y < 0
    assert traced.layout.margin.b >= 154
    assert traced.layout.meta["pmm_code_trace"]["code_basis"] == "AASHTO LRFD"


def test_aashto_col_pmm_trace2_plotly_title_replaces_verbose_trace_line() -> None:
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC PMM",
        prestress_included=False,
        bonded_prestress_included=False,
    )
    fig = go.Figure()
    fig.update_layout(
        title=(
            "PMM Mux-Muy Slice at Pu = 1,200.0 kN (Interpolated Slice)"
            "<br><sup>Demand ray intersects the cleaned slice envelope to obtain available φMn.</sup>"
            "<br><sup>Code basis: AASHTO LRFD 9th Edition · Route: AASHTO LRFD Column/Pier PMM · "
            "φ: AASHTO strain-controlled φ transition</sup>"
        ),
        margin=dict(l=20, r=20, t=86, b=20),
    )

    traced = _append_pmm_traceability_to_figure_title(fig, context)

    assert traced.layout.title.text.count("<br><sup>") == 1
    assert "Demand ray intersects" not in traced.layout.title.text
    assert "Code basis:" not in traced.layout.title.text
    assert "AASHTO LRFD 9th · Column/Pier PMM · SI-safe" in traced.layout.title.text
    assert traced.layout.margin.b >= 154


def test_aashto_col_pmm_trace3_plot_layout_keeps_legend_below_axis() -> None:
    context = _pmm_traceability_context_for_code(
        "AASHTO LRFD",
        "AASHTO LRFD 9th Edition",
        mode_label="RC PMM",
        prestress_included=False,
        bonded_prestress_included=False,
    )
    fig = go.Figure()
    fig.update_layout(title="PMM Mux-Muy Slice", margin=dict(l=20, r=20, t=86, b=20))

    traced = _append_pmm_traceability_to_figure_title(fig, context)

    assert traced.layout.height >= 580
    assert traced.layout.legend.y <= -0.34
    assert traced.layout.margin.b >= 154
    assert traced.layout.xaxis.automargin is True
    assert traced.layout.xaxis.title.standoff >= 24

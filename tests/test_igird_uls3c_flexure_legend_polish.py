from __future__ import annotations

from pathlib import Path

import pandas as pd

import concrete_pmm_pro.ui.analysis_page as analysis_page


def _demand_df(case_name: str = "AUTO-CONSTRUCTION-ULS") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Station x (m)": 0.0, "Case Name": case_name, "Mux": 0.0},
            {"Station x (m)": 10.0, "Case Name": case_name, "Mux": 891.0},
            {"Station x (m)": 20.0, "Case Name": case_name, "Mux": 0.0},
        ]
    )


def _preview_df(case_name: str = "AUTO-CONSTRUCTION-ULS") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Governing x": "0.000 m",
                "Demand kN-m": 0.0,
                "Capacity kN-m": 6094.78,
                "Utilization value": None,
                "Case": case_name,
                "Status": "SECTION",
                "Capacity plot sign": 1.0,
            },
            {
                "Governing x": "10.000 m",
                "Demand kN-m": 891.0,
                "Capacity kN-m": 6094.78,
                "Utilization value": 891.0 / 6094.78,
                "Case": case_name,
                "Status": "PASS",
                "Capacity plot sign": 1.0,
            },
            {
                "Governing x": "20.000 m",
                "Demand kN-m": 0.0,
                "Capacity kN-m": 6094.78,
                "Utilization value": None,
                "Case": case_name,
                "Status": "SECTION",
                "Capacity plot sign": 1.0,
            },
        ]
    )


def test_uls3c_igird_flexure_legend_uses_compact_labels_without_duplicate_governing_demand() -> None:
    fig = analysis_page._make_beam_uls_flexure_preview_figure(
        _demand_df(),
        _preview_df(),
        code_label="AASHTO LRFD 9th Edition · Construction noncomposite",
    )
    polished = analysis_page._polish_igird_uls_flexure_legend(fig)

    names = [str(getattr(trace, "name", "") or "") for trace in polished.data]
    assert "Demand Mux" in names
    assert "φMn" in names
    assert "Gov. flexure" in names
    assert "Governing flexure check" not in names
    assert not any(name.startswith("Demand Mux — AUTO-CONSTRUCTION-ULS") for name in names)

    governing_demand = next(trace for trace in polished.data if str(getattr(trace, "name", "")) == "Gov. demand")
    assert governing_demand.showlegend is False
    assert list(governing_demand.text) == ["Governing demand"]


def test_uls3c_igird_flexure_legend_reserves_fixed_entry_width_and_bottom_margin() -> None:
    fig = analysis_page._polish_igird_uls_flexure_legend(
        analysis_page._make_beam_uls_flexure_preview_figure(
            _demand_df("Strength I"),
            _preview_df("Strength I"),
            code_label="AASHTO LRFD 9th Edition · Final composite +M",
        )
    )

    legend = fig.layout.legend
    assert legend.orientation == "h"
    assert legend.entrywidth == 145
    assert legend.entrywidthmode == "pixels"
    assert legend.font.size == 10
    assert fig.layout.margin.b == 126


def test_uls3c_polish_is_scoped_to_igird_stage_render_calls() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")

    assert "def _polish_igird_uls_flexure_legend" in source
    assert source.count("_polish_igird_uls_flexure_legend(") >= 4  # helper + 3 stage render sites
    # Generic Beam/Girder chart factory retains its established trace names;
    # compacting is applied only by the Precast Composite I-Girder stage route.
    assert 'name=f"Demand {column} — {case_name}"' in source
    assert 'name="Governing flexure check"' in source

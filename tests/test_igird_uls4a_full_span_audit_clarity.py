import pandas as pd

from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_full_member_plot_range,
    _igird_interface_figure,
    _igird_interface_reinforcement_card_detail,
    _igird_interface_source_dataframe,
    _make_beam_uls_flexure_preview_figure,
)


def _active_demand():
    return pd.DataFrame(
        [
            {"Station x (m)": 0.0, "Case Name": "Strength I", "Mux": 0.0},
            {"Station x (m)": 10.0, "Case Name": "Strength I", "Mux": 1000.0},
            # Negative +M-scope row must remain visible/source-owned for full-span QA.
            {"Station x (m)": 20.0, "Case Name": "Strength I", "Mux": -100.0},
        ]
    )


def _preview():
    return pd.DataFrame(
        [
            {
                "Governing x": "0.000 m",
                "Case": "Strength I",
                "Demand kN-m": 0.0,
                "Capacity kN-m": 7000.0,
                "Utilization value": float("nan"),
                "Capacity plot sign": 1.0,
                "Status": "PASS",
            },
            {
                "Governing x": "10.000 m",
                "Case": "Strength I",
                "Demand kN-m": 1000.0,
                "Capacity kN-m": 7000.0,
                "Utilization value": 1.0 / 7.0,
                "Capacity plot sign": 1.0,
                "Status": "PASS",
            },
        ]
    )


def test_full_member_plot_range_keeps_configured_span_visible_even_if_last_result_station_is_shorter():
    short = pd.DataFrame({"Station x (m)": [0.0, 5.0, 10.0, 14.0]})
    assert _beam_uls_full_member_plot_range(short, 20.0) == (0.0, 20.0)


def test_final_flexure_display_keeps_full_demand_span_but_positive_governing_scope():
    active = _active_demand()
    supported = active[active["Mux"] >= 0.0].copy()
    fig = _make_beam_uls_flexure_preview_figure(
        active,
        _preview(),
        code_label="AASHTO LRFD 9th Edition · Final composite +M",
        governing_df=supported,
        member_length_m=20.0,
    )
    demand = next(trace for trace in fig.data if str(trace.name).startswith("Demand Mux"))
    assert list(demand.x) == [0.0, 10.0, 20.0]
    assert tuple(fig.layout.xaxis.range) == (0.0, 20.0)
    gov = next(trace for trace in fig.data if trace.name == "Governing demand")
    assert list(gov.x) == [10.0]


def test_interface_source_is_not_truncated_by_positive_mux_scope():
    active = _active_demand()
    source = _igird_interface_source_dataframe(active)
    assert list(source["Station x (m)"]) == [0.0, 10.0, 20.0]
    assert source.iloc[-1]["Mux"] < 0.0


def test_interface_figure_exposes_full_member_domain():
    result = pd.DataFrame(
        [
            {"Station x (m)": 0.0, "Case": "Strength I", "vui (MPa)": 0.5, "phi vni (MPa)": 2.7, "Strength D/C": 0.185, "Minimum Avf D/C": 0.0, "Status": "PASS"},
            {"Station x (m)": 14.0, "Case": "Strength I", "vui (MPa)": 0.2, "phi vni (MPa)": 2.2, "Strength D/C": 0.091, "Minimum Avf D/C": 0.0, "Status": "PASS"},
        ]
    )
    fig = _igird_interface_figure(result, code_label="AASHTO LRFD 9th Edition", member_length_m=20.0)
    assert tuple(fig.layout.xaxis.range) == (0.0, 20.0)


def test_interface_reinforcement_card_states_actual_fy_cap_and_zero_minimum_basis():
    detail = _igird_interface_reinforcement_card_detail(
        {
            "Stirrup": "DB12 × 2 @ 100 mm",
            "fy used <=60 ksi (MPa)": 390.0,
            "Avf min required (mm2/m)": 0.0,
            "Minimum basis": "1.33Vui/phi cap satisfied by cohesion",
        }
    )
    assert "fy used = 390.0 MPa" in detail
    assert "AASHTO cap = 413.7 MPa" in detail
    assert "Min = 0" in detail
    assert "cohesion satisfies 1.33Vui/φ" in detail
    assert "waiver not needed" in detail

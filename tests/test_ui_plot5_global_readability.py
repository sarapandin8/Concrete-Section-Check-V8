from __future__ import annotations

import plotly.graph_objects as go

from concrete_pmm_pro.visualization.plot_readability import (
    apply_global_plot_readability,
    install_streamlit_plotly_readability_patch,
)


def test_ui_plot5_strengthens_basic_plot_text_without_changing_data() -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1, 2], y=[1.0, 2.0, 3.0], name="Demand"))
    before_x = list(fig.data[0].x)
    before_y = list(fig.data[0].y)

    apply_global_plot_readability(fig)

    assert list(fig.data[0].x) == before_x
    assert list(fig.data[0].y) == before_y
    assert fig.layout.font.color == "#0f172a"
    assert fig.layout.xaxis.tickfont.color == "#1f2937"
    assert fig.layout.yaxis.title.font.size >= 15
    assert fig.layout.legend.font.size >= 13


def test_ui_plot5_strengthens_annotations() -> None:
    fig = go.Figure()
    fig.add_annotation(text="Gov. Tension", x=1, y=2, font={"size": 9, "color": "#888888"})

    apply_global_plot_readability(fig)

    assert fig.layout.annotations[0].font.size >= 12
    assert fig.layout.annotations[0].font.color == "#888888" or fig.layout.annotations[0].font.color == "#0f172a"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.received = None

    def plotly_chart(self, figure_or_data=None, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        self.received = figure_or_data
        return "ok"


def test_ui_plot5_installs_streamlit_plotly_patch_once() -> None:
    fake = _FakeStreamlit()
    install_streamlit_plotly_readability_patch(fake)
    first_wrapper = fake.plotly_chart
    install_streamlit_plotly_readability_patch(fake)
    assert fake.plotly_chart is first_wrapper

    fig = go.Figure(go.Scatter(x=[0], y=[0]))
    assert fake.plotly_chart(fig) == "ok"
    assert fake.received is fig
    assert fig.layout.font.color == "#0f172a"


def test_ui_plot7_extends_legend_swatch_for_dashed_engineering_lines() -> None:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0.0, 10.0],
            y=[100.0, 100.0],
            name="φVn",
            mode="lines",
            line={"dash": "dash", "width": 1.5},
        )
    )
    before_x = list(fig.data[0].x)
    before_y = list(fig.data[0].y)

    apply_global_plot_readability(fig)

    assert list(fig.data[0].x) == before_x
    assert list(fig.data[0].y) == before_y
    assert fig.layout.legend.itemwidth >= 70
    assert fig.layout.legend.entrywidth >= 140
    assert fig.layout.legend.entrywidthmode == "pixels"
    assert fig.data[0].line.dash == "dash"
    assert fig.data[0].line.width >= 3.0


def test_ui_plot7_solid_trace_data_and_line_width_are_not_changed() -> None:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0.0, 5.0, 10.0],
            y=[1.0, 2.0, 3.0],
            name="Demand",
            mode="lines+markers",
            line={"width": 1.25},
        )
    )

    apply_global_plot_readability(fig)

    assert list(fig.data[0].x) == [0.0, 5.0, 10.0]
    assert list(fig.data[0].y) == [1.0, 2.0, 3.0]
    assert fig.data[0].line.width == 1.25

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, Rebar, RebarMaterial, SectionGeometry
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_flexure_preview_dataframe,
    _make_beam_uls_flexure_preview_figure,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")


def _simple_rc_state() -> dict[str, object]:
    geometry = SectionGeometry(
        outer_polygon=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=300.0, y=0.0),
            Point2D(x=300.0, y=600.0),
            Point2D(x=0.0, y=600.0),
        ]
    )
    return {
        "section_geometry": geometry,
        "concrete_material": ConcreteMaterial(name="C30", fc_MPa=30.0),
        "rebars": [
            Rebar(x_mm=75.0, y_mm=50.0, diameter_mm=25.0, material_name="SD40"),
            Rebar(x_mm=225.0, y_mm=50.0, diameter_mm=25.0, material_name="SD40"),
        ],
        "rebar_materials": [RebarMaterial(name="SD40", fy_MPa=400.0, Es_MPa=200000.0)],
        "prestress_elements": [],
    }


def _full_span_rows(*, length_m: float = 20.0, divisions: int = 40) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index in range(divisions + 1):
        x = length_m * index / divisions
        # Positive simple-span demand, zero only at supports.
        mu = x * (length_m - x)
        rows.append(
            {
                "Active": True,
                "Station x (m)": x,
                "Case Name": "AUTO-CONSTRUCTION-ULS",
                "Mux": mu,
                "Vuy": 0.0,
                "Tu": 0.0,
                "Muy": 0.0,
                "Vux": 0.0,
                "Nu": 0.0,
                "Note": "",
            }
        )
    return pd.DataFrame(rows)


def test_igird_uls2_construction_route_requests_full_span_capacity() -> None:
    assert 'full_span_capacity=True' in ANALYSIS_SOURCE
    assert 'IGIRDER.ULS2.full-span-physical-phiMn' in ANALYSIS_SOURCE


def test_igird_uls2_full_span_capacity_keeps_physical_phi_mn_at_zero_demand_supports() -> None:
    preview, messages = _beam_uls_flexure_preview_dataframe(
        _simple_rc_state(),
        _full_span_rows(divisions=4),
        code_label="ACI 318",
        is_building=True,
        full_span_capacity=True,
    )

    assert len(preview) == 5
    endpoints = preview[preview["Governing x"].isin(["0.000 m", "20.000 m"])]
    assert len(endpoints) == 2
    assert set(endpoints["Status"]) == {"SECTION PREVIEW"}
    assert (pd.to_numeric(endpoints["Capacity kN-m"]) > 0.0).all()
    assert endpoints["Utilization value"].isna().all()
    assert all("physical section φMn" in str(note) for note in endpoints["Notes"])
    assert any("Full-span φMn capacity evaluated" in message for message in messages)
    assert not any("φMn = 0 section-boundary" in message for message in messages)


def test_igird_uls2_full_span_capacity_is_not_truncated_after_24_nonzero_rows() -> None:
    active = _full_span_rows(divisions=40)
    preview, messages = _beam_uls_flexure_preview_dataframe(
        _simple_rc_state(),
        active,
        code_label="ACI 318",
        is_building=True,
        full_span_capacity=True,
    )

    assert len(preview) == 41
    assert preview.iloc[-1]["Governing x"] == "20.000 m"
    assert float(preview.iloc[-1]["Capacity kN-m"]) > 0.0
    assert not any("limited to the first 24" in message for message in messages)

    # Uniform section/reinforcement gives one physical capacity state throughout
    # the member. The full-span curve must therefore remain horizontal instead
    # of falling artificially from the 24-row cutoff to a fabricated zero end.
    capacities = pd.to_numeric(preview["Capacity kN-m"], errors="coerce")
    assert capacities.notna().all()
    assert capacities.max() == pytest.approx(capacities.min(), rel=1e-9, abs=1e-9)

    fig = _make_beam_uls_flexure_preview_figure(active, preview, code_label="Construction noncomposite")
    capacity_trace = next(trace for trace in fig.data if trace.name == "φMn")
    assert len(capacity_trace.x) == 41
    assert list(capacity_trace.x)[0] == pytest.approx(0.0)
    assert list(capacity_trace.x)[-1] == pytest.approx(20.0)
    assert float(list(capacity_trace.y)[0]) > 0.0
    assert float(list(capacity_trace.y)[-1]) > 0.0
    assert max(capacity_trace.y) == pytest.approx(min(capacity_trace.y), rel=1e-9, abs=1e-9)

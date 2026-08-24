import math

from concrete_pmm_pro.geometry.generators import parametric_i_girder
from concrete_pmm_pro.geometry.torsion_hoop import derive_closed_hoop_centerline


def _geometry():
    return parametric_i_girder(
        B1_mm=800.0,
        B2_mm=500.0,
        D1_mm=1400.0,
        D2_mm=150.0,
        D3_mm=200.0,
        D5_mm=200.0,
        D6_mm=200.0,
        T1_mm=200.0,
        T2_mm=200.0,
        C1_mm=0.0,
    )


def test_auto_ph_uses_clear_cover_plus_half_bar_diameter():
    result = derive_closed_hoop_centerline(_geometry(), clear_cover_mm=40.0, bar_diameter_mm=12.0)
    assert result.ready is True
    assert result.centerline_offset_mm == 46.0
    assert result.ph_mm is not None and result.ph_mm > 0.0
    assert len(result.coordinates) >= 8
    assert "clear cover 40.0 mm + db/2 = 6.0 mm" in result.note


def test_auto_ph_is_independent_of_spacing_and_changes_only_with_geometry_or_db():
    # Spacing is deliberately absent from the geometry API: changing @100 to
    # @250 changes At/s but not the closed-hoop centerline perimeter.
    db12 = derive_closed_hoop_centerline(_geometry(), clear_cover_mm=40.0, bar_diameter_mm=12.0)
    db16 = derive_closed_hoop_centerline(_geometry(), clear_cover_mm=40.0, bar_diameter_mm=16.0)
    assert db12.ready and db16.ready
    assert math.isclose(db12.centerline_offset_mm or 0.0, 46.0)
    assert math.isclose(db16.centerline_offset_mm or 0.0, 48.0)
    assert (db16.ph_mm or 0.0) < (db12.ph_mm or 0.0)


def test_audited_centerline_offset_override_keeps_ph_automatic():
    result = derive_closed_hoop_centerline(
        _geometry(),
        clear_cover_mm=40.0,
        bar_diameter_mm=12.0,
        centerline_offset_override_mm=55.0,
    )
    assert result.ready is True
    assert result.centerline_offset_mm == 55.0
    assert result.ph_mm is not None and result.ph_mm > 0.0
    assert "audited centerline offset = 55.0 mm" in result.note


def test_auto_ph_refuses_offset_that_collapses_section():
    result = derive_closed_hoop_centerline(_geometry(), clear_cover_mm=1000.0, bar_diameter_mm=12.0)
    assert result.ready is False
    assert result.ph_mm is None


def test_rebar_workspace_header_total_as_comes_from_source_table_before_parser_materialization():
    import pandas as pd
    from concrete_pmm_pro.ui import rebar_page

    rebar_page.st.session_state.clear()
    rows = []
    for i in range(34):
        rows.append({
            "Active": True,
            "Label": f"B{i+1}",
            "Diameter_mm": 20.0,
            "Count": 1,
        })
    rebar_page.st.session_state["rebar_table"] = pd.DataFrame(rows)
    rebar_page.st.session_state["rebars"] = []  # reproduces the header-before-parser condition
    cards = rebar_page._commercial_rebar_dashboard_cards("beam_girder")
    active = next(card for card in cards if card["title"] == "Active bars")
    assert active["value"] == "34"
    assert "10,681" in active["detail"]

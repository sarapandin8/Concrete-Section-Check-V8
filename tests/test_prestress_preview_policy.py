from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESTRESS_SOURCE = (ROOT / "concrete_pmm_pro" / "ui" / "prestress_page.py").read_text()
REBAR_SOURCE = (ROOT / "concrete_pmm_pro" / "ui" / "rebar_page.py").read_text()


def test_prestress_page_default_preview_hides_ordinary_rebar_and_dimensions():
    assert "Section Preview with Prestress" in PRESTRESS_SOURCE
    assert "Default preview shows prestressing steel only" in PRESTRESS_SOURCE
    assert "dimension guides are intentionally hidden" in PRESTRESS_SOURCE
    assert "prestress_only_section_preview" in PRESTRESS_SOURCE
    preview_label_index = PRESTRESS_SOURCE.index("Section Preview with Prestress")
    preview_call_start = PRESTRESS_SOURCE.index("fig = create_section_preview(", preview_label_index)
    preview_call_end = PRESTRESS_SOURCE.index("fig.update_layout", preview_call_start)
    preview_call = PRESTRESS_SOURCE[preview_call_start:preview_call_end]
    assert "geometry" in preview_call
    assert "preview_dimensions" in preview_call
    assert "active_prestress" in preview_call
    assert 'st.session_state.get("section_dimensions", [])' not in preview_call
    assert "preview_dimensions: list[Any] = []" in PRESTRESS_SOURCE


def test_rebar_page_default_preview_hides_prestressing_steel_and_dimensions():
    assert "Section Preview with Rebar" in REBAR_SOURCE
    assert "Default preview shows ordinary rebar only" in REBAR_SOURCE
    assert "Dimension guides are intentionally hidden here" in REBAR_SOURCE
    assert "rebar_section_preview" in REBAR_SOURCE
    preview_label_index = REBAR_SOURCE.index("Section Preview with Rebar")
    preview_call_start = REBAR_SOURCE.index("preview_fig = create_section_preview(", preview_label_index)
    preview_call_end = REBAR_SOURCE.index("preview_fig.update_layout", preview_call_start)
    preview_call = REBAR_SOURCE[preview_call_start:preview_call_end]
    assert "geometry" in preview_call
    assert "[]" in preview_call
    assert 'st.session_state["rebars"]' in preview_call
    assert 'st.session_state.get("section_dimensions", [])' not in preview_call



def test_rebar_page_disabled_ordinary_rebar_is_marked_stored_excluded():
    assert "Analysis Participation" in REBAR_SOURCE
    assert "Excluded" in REBAR_SOURCE
    assert "Active Analysis Bars" in REBAR_SOURCE
    assert "st.session_state[\"rebars_stored_excluded\"] = result.rebars" in REBAR_SOURCE
    assert "st.session_state[\"rebars\"] = []" in REBAR_SOURCE
    assert "Stored Rebar Preview — Excluded from Analysis" in REBAR_SOURCE
    assert "stored_excluded_section_preview" in REBAR_SOURCE


def test_combined_reinforcement_preview_is_explicit_and_collapsed():
    assert "Combined Reinforcement Preview" in PRESTRESS_SOURCE
    assert "Combined Reinforcement Preview" in REBAR_SOURCE
    assert "Coordination view only" in PRESTRESS_SOURCE
    assert "Coordination view only" in REBAR_SOURCE
    assert "prestress_combined_reinforcement_preview" in PRESTRESS_SOURCE
    assert "rebar_combined_reinforcement_preview" in REBAR_SOURCE
    combined_index = PRESTRESS_SOURCE.index("prestress_combined_reinforcement_preview")
    combined_call_start = PRESTRESS_SOURCE.rindex("combined_fig = create_section_preview(", 0, combined_index)
    combined_call = PRESTRESS_SOURCE[combined_call_start:combined_index]
    assert "preview_dimensions" in combined_call
    assert 'st.session_state.get("section_dimensions", [])' not in combined_call


def test_prestress_page_hides_section_level_table_for_precast_girder_workflow():
    assert "Section-level tendon/prestress table is hidden and ignored" in PRESTRESS_SOURCE
    assert "The legacy section-level tendon/prestress table is hidden and ignored" in PRESTRESS_SOURCE
    assert "Girder Strand Preview" in PRESTRESS_SOURCE
    assert "Legacy PS1/PS2 section-level previews are hidden" in PRESTRESS_SOURCE
    assert "Tendon Product Creation / product database" in PRESTRESS_SOURCE
    assert "_render_tendon_product_tools()" in PRESTRESS_SOURCE


def test_prestress_force_status_distinguishes_reference_only_rows():
    assert "Force status" in PRESTRESS_SOURCE
    assert "Reference only" in PRESTRESS_SOURCE
    assert "no active Pe assigned" in PRESTRESS_SOURCE
    assert "Active prestress rows are reference/passive only" in PRESTRESS_SOURCE


def test_prestress_preview_is_visible_for_passive_reference_rows() -> None:
    assert "Preview shows active prestress/reference rows immediately" in PRESTRESS_SOURCE
    assert "Passive prestress/reference steel preview" not in PRESTRESS_SOURCE
    assert "prestress_passive_section_preview" not in PRESTRESS_SOURCE
    assert "prestress_geometry_only_section_preview" in PRESTRESS_SOURCE

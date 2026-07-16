from pathlib import Path


def test_crossbeam_ui1_module_exists_and_is_solver_free():
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text()
    assert "render_crossbeam_segment_layout_page" in source
    assert "render_crossbeam_tendon_system_page" in source
    assert "render_crossbeam_tendon_profile_page" in source
    assert "Tendon Plan" in source
    assert "Tendon Elevation" in source
    assert "Tendon Cross Section" in source
    assert "Crossbeam Tendon 3D Orthographic Review" in source
    assert 'projection": {"type": "orthographic"}' in source
    assert "loss" in source.lower()
    assert "calculate_prestress" not in source


def test_crossbeam_navigation_is_workflow_scoped():
    source = Path("app.py").read_text()
    assert 'return ["Section Builder", "Segment Layout", "Rebar", "Tendon System", "Tendon Profile"]' in source
    assert 'return list(WORKSPACE_NAVIGATION["Sections"])' in source
    assert '"Sections": ["Section Builder", "Rebar", "Prestress"]' in source


def test_section_builder_no_longer_renders_combined_crossbeam_foundation():
    source = Path("concrete_pmm_pro/ui/section_builder.py").read_text()
    render_body = source.split("def render_section_builder() -> None:", 1)[1]
    assert "_render_crossbeam_layout_tendon_foundation(" not in render_body


def test_crossbeam_ui1_uses_section_x_and_longitudinal_s_conventions():
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text()
    assert "Lateral position x (mm)" in source
    assert "Station s (m)" in source
    assert "Depth from top dtop (mm)" in source
    assert "Cross-section axes remain x–y" in source


def test_crossbeam_section_status_keeps_xy_and_adds_longitudinal_s():
    source = Path("concrete_pmm_pro/ui/section_builder.py").read_text()
    assert '"x/y + s"' in source
    assert '"s/u/v"' not in source
    assert '("x-axis", "Horizontal local coordinate in the cross-section' in source

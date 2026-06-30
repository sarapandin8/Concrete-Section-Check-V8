from __future__ import annotations

from pathlib import Path


def test_app_uses_visual_only_commercial_tab_styles_without_new_navigation() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "_COMMERCIAL_TAB_CSS" in source
    assert "_render_global_commercial_tab_styles()" in source
    assert "div[data-testid=\"stSegmentedControl\"]" in source
    assert "div[data-testid=\"stRadio\"] div[role=\"radiogroup\"]" in source
    assert "This does not add, move, or remove navigation controls" in source
    assert source.count('"Analysis": ["ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber"]') == 1
    assert source.count('"Report / QA": ["Report / QA"]') == 1


def test_app_commercial_tabs2_applies_dark_blue_bold_typography_to_existing_controls() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL.TABS2" in source
    assert "--cpmm-ink-blue: #0b3a66" in source
    assert "font-weight: 760" in source
    assert "font-weight: 780" in source
    assert "font-size: 0.9rem" in source
    assert ".stButton button" in source
    assert ".stDownloadButton button" in source
    assert "div[data-testid=\"stWidgetLabel\"]" in source
    assert "div[data-testid=\"stNumberInput\"] label" in source
    assert "div[data-baseweb=\"input\"] input" in source


def test_ui_commercial_tabs3_styles_actual_streamlit_button_group_tabs() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'div[data-testid="stButtonGroup"]' in source
    assert 'div[data-testid="stButtonGroup"] button p' in source
    assert 'div[data-testid="stButtonGroup"] [role="radio"][aria-checked="true"]' in source
    assert 'font-weight: 800' in source
    assert '--cpmm-ink-blue' in source


def test_ui_commercial_tabs4_highlights_active_segmented_tabs() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL.TABS4" in source
    assert "--cpmm-active-tab-fill" in source
    assert "--cpmm-active-tab-border" in source
    assert 'button[data-testid="stBaseButton-segmentedControlActive"]' in source
    assert 'box-shadow: inset 0 -3px 0 var(--cpmm-active-tab-accent)' in source
    assert 'label:has(input:checked)' in source


def test_ui_active_tabs1_adds_deterministic_active_tab_css() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.ACTIVE.TABS1" in source
    assert ".cpmm-nav-tab-active" in source
    assert "background: var(--cpmm-active-tab-fill)" in source
    assert "render_active_choice" in source


def test_ui_active_tabs2_uses_compact_commercial_nav_and_styles_streamlit_tabs() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.ACTIVE.TABS2" in source
    assert ".cpmm-deterministic-nav-row--compact" in source
    assert "min-height: 1.64rem" in source
    assert "0 1px 1px var(--cpmm-active-tab-shadow)" in source
    assert 'div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]' in source
    assert "--cpmm-active-tab-accent" in source


def test_ui_active_tabs3_applies_working_screen_density_polish() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.ACTIVE.TABS3" in source
    assert ".block-container" in source
    assert "padding-top: 1.55rem" in source
    assert "font-size: 1.95rem" in source
    assert "min-height: 1.64rem" in source
    assert "0.01rem 0 0.34rem" in source
    assert "inset 0 -2px 0 var(--cpmm-active-tab-accent)" in source


def test_app_brand1_renames_visible_app_and_prevents_header_crop() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'page_title="Concrete Section Pro"' in source
    assert 'st.title("Concrete Section Pro")' in source
    assert "Concrete section analysis and design-review workspace." in source
    assert "line-height: 1.24rem" not in source
    assert "line-height: 1.24" in source
    assert "padding-top: 1.55rem" in source
    assert "overflow: visible" in source


def test_ui_pmm_compact1_collapses_flexural_diagnostics_and_prioritizes_visual_review() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert "Decision-first axial-biaxial PMM strength workspace" in source
    assert 'with st.expander("Analysis setup / readiness", expanded=False)' in source
    assert 'with st.expander("Analysis input overview / diagnostics", expanded=False)' in source
    assert 'with st.expander("Run / cache controls", expanded=True)' in source
    assert 'with st.expander("Stored calculation snapshot / D/C trace", expanded=False)' in source
    assert "Decision graphics use the stored PMM result and cached D/C summary" in source
    assert "show_summary_cards=False" in source
    assert source.index('st.subheader("PMM Visual Review")') < source.index('with st.expander("Stored calculation snapshot / D/C trace", expanded=False)')




def test_ui_pmm_nav3_moves_result_view_tabs_immediately_under_flexural() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert "def _render_pmm_result_views_first_screen" in source
    assert "Primary Flexural PMM result views are shown immediately after the Flexural workspace header" in source
    assert "_pmm_result_views_rendered_upstream" in source
    assert source.index("_render_pmm_result_views_first_screen()") < source.index('with st.expander("Analysis setup / readiness", expanded=False)')
    call_index = source.index("    _render_pmm_result_views_first_screen()")
    assert call_index < source.index('with st.expander("Analysis setup / readiness", expanded=False)')
    assert call_index < source.index('    _render_input_summary()')
    assert 'with st.expander("Stored calculation snapshot / D/C trace", expanded=False)' in source



def test_ui_analysis_nav2_promotes_uls_strength_summary_to_top_level_check_tab() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert 'COLUMN_PIER_ULS_CHECK_SUBTABS = ["Summary", "Flexural (PMM)", "Shear", "Torsion", "Shear + Torsion"]' in source
    assert "def _render_column_pier_uls_summary_workspace" in source
    assert 'if active_check == "Summary":' in source
    assert 'render_metric_cards(_project_design_code_status_cards(workflow="pmm"))' in source
    assert 'render_metric_cards(_column_pier_analysis_scope_cards())' in source
    assert '_render_column_pier_uls_decision_summary()' in source
    render_start = source.index("def render_analysis_uls_pmm() -> None:")
    render_end = source.index("def render_analysis_sls_stress() -> None:", render_start)
    body = source[render_start:render_end]
    assert "decision_view_slot = st.container()" not in body

def test_ui_action_buttons1_highlights_primary_actions_with_blue_accent() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    analysis_source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    project_source = Path("concrete_pmm_pro/ui/project_page.py").read_text(encoding="utf-8")

    assert "UI.ACTION.BUTTONS1" in app_source
    assert "--cpmm-action-fill: #1d6fe7" in app_source
    assert "--cpmm-action-fill-hover: #175cd3" in app_source
    assert "button[kind=\"primary\"]" in app_source
    assert 'button[data-testid="stBaseButton-primary"]' in app_source
    assert 'div[data-testid="stFileUploaderDropzone"] button' in app_source
    assert 'div[data-testid="stFileUploader"] button,' not in app_source
    assert "uploaded-file pills also contain remove (x) buttons" in app_source
    assert "UI.COMMERCIAL4.3.2 migrates primary/action buttons to the app blue accent" in app_source
    assert "font-weight: 850" in app_source
    assert 'type="primary"' in analysis_source and 'ui_keys1_analysis_page_button_1983' in analysis_source
    assert '"Save Project"' in project_source and 'type="primary"' in project_source
    assert '"Load Project JSON"' in project_source and 'type="primary"' in project_source


def test_ui_action_buttons2_mutes_disabled_run_and_compacts_runtime_control() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    analysis_source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert "UI.ACTION.BUTTONS2" in app_source
    assert "--cpmm-action-disabled-fill" in app_source
    assert ".stButton button:disabled" in app_source
    assert ".cpmm-runtime-compact-grid" in app_source
    assert ".cpmm-runtime-compact-card" in app_source
    assert "run_enabled = analysis_input is not None" in analysis_source
    assert 'type="primary" if run_enabled else "secondary"' in analysis_source
    assert "Run blocked: Analysis readiness errors must be corrected" in analysis_source
    assert "Solver guard" in analysis_source

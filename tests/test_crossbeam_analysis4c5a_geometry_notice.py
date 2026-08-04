from pathlib import Path


APP = Path("app.py").read_text(encoding="utf-8")
NOTICE = Path("concrete_pmm_pro/ui/crossbeam_project_geometry.py").read_text(
    encoding="utf-8"
)
AUDIT = Path("concrete_pmm_pro/crossbeam/project_geometry.py").read_text(
    encoding="utf-8"
)


def test_sidebar_blocker_overrides_global_sidebar_white_ink_rule() -> None:
    assert (
        'section[data-testid="stSidebar"] .cpmm-sidebar-blocked-notice,'
        in APP
    )
    assert (
        'section[data-testid="stSidebar"] .cpmm-sidebar-blocked-notice * {'
        in APP
    )
    assert "-webkit-text-fill-color: #81172a !important;" in APP
    assert ".cpmm-sidebar-blocked-title" in APP
    assert ".cpmm-sidebar-blocked-detail" in APP
    assert ".cpmm-sidebar-blocked-action" in APP


def test_geometry_blocker_shows_reason_and_direct_action() -> None:
    assert "cpmm-sidebar-blocked-title" in NOTICE
    assert "cpmm-sidebar-blocked-detail" in NOTICE
    assert "cpmm-sidebar-blocked-action-label" in NOTICE
    assert "ACTION" in NOTICE
    assert "Where to fix" in NOTICE
    assert "Custom subdivisions are preserved" in NOTICE


def test_geometry_audit_selects_the_active_construction_mode_rebar_source() -> None:
    assert 'CROSSBEAM_CIP_REBAR_ZONE_ROWS_KEY = "crossbeam_rb_cip2a_zone_assignment_rows"' in AUDIT
    assert 'CROSSBEAM_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"' in AUDIT
    assert "active_rebar_zone_key" in AUDIT
    assert "dormant assignments must never create a false geometry blocker" in AUDIT

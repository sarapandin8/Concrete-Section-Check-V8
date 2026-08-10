from __future__ import annotations

import inspect

from concrete_pmm_pro.analysis.crossbeam_uls import build_crossbeam_uls_flexure_preparation
from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.ui.analysis_page import (
    _render_crossbeam_uls_combined_vt_workspace,
    _render_crossbeam_uls_flexure_workspace,
)
from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state


def test_cip_flexure_source_count_contract_distinguishes_imported_from_retained_rows() -> None:
    preparation = build_crossbeam_uls_flexure_preparation(_cip_ready_state())
    assert preparation.ready, preparation.errors

    imported = len(preparation.demand_rows)
    support = len(preparation.derived_support_rows)
    generated_aux = max(0, len(preparation.rows) - imported - support)
    retained = max(0, len(preparation.rows) - support - generated_aux)

    assert imported > retained
    assert retained + support + generated_aux == len(preparation.rows)
    assert support > 0
    assert generated_aux == 0

    source = inspect.getsource(_render_crossbeam_uls_flexure_workspace)
    assert "imported source rows →" in source
    assert "retained_source_count" in source
    assert "Column Face checks" in source


def test_cip_shear_scope_marks_physical_segment_joint_transfer_not_applicable() -> None:
    preparation = build_crossbeam_uls_shear_preparation(_cip_ready_state())
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_shear(preparation)
    scope = str(result.get("scope") or "")

    assert "Cast-in-Place Zone boundaries are monolithic property boundaries" in scope
    assert "physical segment-joint shear transfer is NOT APPLICABLE" in scope
    assert "separate REVIEW item" not in scope


def test_cip_torsion_scope_has_no_segmental_completion_gate() -> None:
    preparation = build_crossbeam_uls_torsion_preparation(_cip_ready_state())
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_torsion(preparation)
    scope = str(result.get("scope") or "")

    assert "physical segment-joint torsion transfer is NOT APPLICABLE" in scope
    assert "overall Crossbeam ULS adoption remains REVIEW/INCOMPLETE" not in scope
    assert "physical-joint transfer reviews close" not in scope


def test_cip_combined_scope_and_workspace_do_not_claim_joint_audit_evidence_applies() -> None:
    preparation = build_crossbeam_uls_combined_vt_preparation(_cip_ready_state())
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)
    scope = str(result.get("scope") or "")

    assert result["joint_transfer_status"] == "NOT APPLICABLE"
    assert result["joint_side_checks"] == 0
    assert "physical Segment-joint transfer is NOT APPLICABLE" in scope
    assert "no one-sided joint rows are generated" in scope
    assert "Physical-joint transfer is NOT EVALUATED" not in scope

    source = inspect.getsource(_render_crossbeam_uls_combined_vt_workspace)
    assert "Cast-in-Place Zones are monolithic property regions" in source
    assert "no physical Segment-joint transfer review or one-sided joint audit rows apply" in source
    assert "Physical Segment-joint rows are not generated" in source

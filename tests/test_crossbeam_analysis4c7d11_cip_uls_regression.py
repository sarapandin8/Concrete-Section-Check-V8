from __future__ import annotations

from copy import deepcopy

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
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
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from tests.test_crossbeam_analysis2_uls_shear import _ready_state
from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state


def _location_types(rows: pd.DataFrame) -> set[str]:
    return set(rows["Location type"].astype(str))


def test_cip_flexure_retains_rebar_credit_and_has_no_segmental_joint_rows() -> None:
    state = _cip_ready_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors

    result = run_crossbeam_uls_flexure(preparation)
    rows = pd.DataFrame(result["rows"])

    assert result["flexure_credit_basis"] == "SECTION REBAR + TENDONS"
    assert result["physical_joint_side_checks"] == 0
    assert set(rows["Ordinary rebar credit"].astype(str)) == {"FULL CREDIT"}
    assert pd.to_numeric(rows["Ordinary bars credited"], errors="coerce").min() > 0
    assert pd.to_numeric(rows["Ordinary As credited mm²"], errors="coerce").min() > 0.0
    assert _location_types(rows) == {"ZONE INTERIOR", "COLUMN FACE"}
    assert not rows["Check Point"].astype(str).str.contains("near 100 mm|J[0-9]", regex=True).any()


def test_cip_shear_torsion_and_combined_have_no_physical_joint_semantics() -> None:
    state = _cip_ready_state()

    shear_preparation = build_crossbeam_uls_shear_preparation(state)
    assert shear_preparation.ready, shear_preparation.errors
    shear = run_crossbeam_uls_shear(shear_preparation)
    shear_rows = pd.DataFrame(shear["rows"])
    assert shear["status"] == "PASS"
    assert not shear_rows["Location type"].astype(str).str.contains("JOINT", case=False).any()
    assert {"ZONE INTERIOR", "COLUMN FACE", "ACI h/2 CRITICAL SECTION"} <= _location_types(shear_rows)

    torsion_preparation = build_crossbeam_uls_torsion_preparation(state)
    assert torsion_preparation.ready, torsion_preparation.errors
    torsion = run_crossbeam_uls_torsion(torsion_preparation)
    torsion_rows = pd.DataFrame(torsion["rows"])
    assert torsion["joint_review_count"] == 0
    assert not torsion_rows["Location type"].astype(str).str.contains("JOINT", case=False).any()
    assert {"ZONE INTERIOR", "COLUMN FACE", "ACI h/2 CRITICAL SECTION"} <= _location_types(torsion_rows)

    combined_preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert combined_preparation.ready, combined_preparation.errors
    combined = run_crossbeam_uls_combined_vt(combined_preparation)
    combined_rows = pd.DataFrame(combined["rows"])
    assert combined["status"] == "PASS"
    assert combined["joint_side_checks"] == 0
    assert combined["joint_review_count"] == 0
    assert combined["joint_transfer_status"] == "NOT APPLICABLE"
    assert combined["sectional_checks"] == combined["total_checks"]
    assert not combined_rows["Location type"].astype(str).str.contains("JOINT", case=False).any()


def test_segmental_cip_segmental_switch_preserves_isolated_flexure_semantics_and_dormant_data() -> None:
    state = _ready_state(include_guard_rows=False)
    layout = state["crossbeam_ui1_segment_layout_rows"]
    cip_longitudinal = default_cip_longitudinal_templates()
    cip_transverse = default_cip_transverse_templates()
    cip_zones = default_cip_zone_assignments(layout, cip_longitudinal, cip_transverse)
    state[CIP_RB_TEMPLATE_ROWS_KEY] = deepcopy(cip_longitudinal)
    state[CIP_TR_TEMPLATE_ROWS_KEY] = deepcopy(cip_transverse)
    state[CIP_RB_ZONE_ROWS_KEY] = deepcopy(cip_zones)

    precast_snapshot = (
        deepcopy(state[CB_RB_TEMPLATE_ROWS_KEY]),
        deepcopy(state[CB_RB_ZONE_ROWS_KEY]),
        deepcopy(state[CB_TR_TEMPLATE_ROWS_KEY]),
    )
    cip_snapshot = (
        deepcopy(state[CIP_RB_TEMPLATE_ROWS_KEY]),
        deepcopy(state[CIP_RB_ZONE_ROWS_KEY]),
        deepcopy(state[CIP_TR_TEMPLATE_ROWS_KEY]),
    )

    observed: list[tuple[str, int, set[str], set[str]]] = []
    for mode in ("Precast Segmental", "Cast-in-Place", "Precast Segmental"):
        state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = mode
        preparation = build_crossbeam_uls_flexure_preparation(state)
        assert preparation.ready, preparation.errors
        result = run_crossbeam_uls_flexure(preparation)
        rows = pd.DataFrame(result["rows"])
        observed.append(
            (
                str(result["flexure_credit_basis"]),
                int(result["physical_joint_side_checks"]),
                set(rows["Ordinary rebar credit"].astype(str)),
                _location_types(rows),
            )
        )

    assert observed[0][0] == observed[2][0] == "TENDON-ONLY"
    assert observed[0][1] == observed[2][1] == 10
    assert observed[0][2] == observed[2][2] == {"TENDON-ONLY"}
    assert "PHYSICAL SEGMENT JOINT" in observed[0][3]
    assert "NEAR JOINT SECTION" in observed[0][3]

    assert observed[1][0] == "SECTION REBAR + TENDONS"
    assert observed[1][1] == 0
    assert observed[1][2] == {"FULL CREDIT"}
    assert observed[1][3] == {"ZONE INTERIOR", "COLUMN FACE"}

    assert precast_snapshot == (
        state[CB_RB_TEMPLATE_ROWS_KEY],
        state[CB_RB_ZONE_ROWS_KEY],
        state[CB_TR_TEMPLATE_ROWS_KEY],
    )
    assert cip_snapshot == (
        state[CIP_RB_TEMPLATE_ROWS_KEY],
        state[CIP_RB_ZONE_ROWS_KEY],
        state[CIP_TR_TEMPLATE_ROWS_KEY],
    )

"""Compact Crossbeam Analysis workspaces.

Crossbeam Analysis follows the same decision-first language as the accepted
Beam/Girder ULS and SLS pages, while keeping Crossbeam solver/state ownership
isolated.  ANALYSIS.UI1 established the compact shell; CROSSBEAM.SLS1A now evaluates
ACI 318-19 transfer/final-service stress and the first isolated ULS P–M3 interaction solver.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
import streamlit as st

from concrete_pmm_pro.crossbeam.analysis_foundation import (
    CROSSBEAM_ANALYSIS_FOUNDATION_KEY,
    DATASET_ORDER,
    DATASET_SLS_SERVICE,
    DATASET_SLS_TRANSFER,
    DATASET_ULS_FINAL,
    build_crossbeam_analysis_foundation,
)
from concrete_pmm_pro.crossbeam.analysis_charts import (
    make_crossbeam_flexure_pm3_figure,
    make_crossbeam_service_stress_figure,
    make_crossbeam_station_coverage_figure,
    make_crossbeam_transfer_stress_figure,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_EP_MPA_KEY,
    CB_LOSS_ES_COLUMN_ROWS_KEY,
    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import CB_SECLIB_DEFINITIONS_KEY
from concrete_pmm_pro.crossbeam.sls_transfer import (
    CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY,
    calculate_crossbeam_transfer_stress,
    transfer_stress_input_fingerprint,
)
from concrete_pmm_pro.crossbeam.sls_service import (
    CB_ANALYSIS_SLS_SERVICE_RESULT_KEY,
    CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY,
    calculate_crossbeam_service_stress,
    canonical_sustained_case_names,
    service_stress_input_fingerprint,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_VALIDATION_KEY,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import CB_PROFILE_ROWS_KEY, CB_TENDON_SYSTEM_ROWS_KEY
from concrete_pmm_pro.crossbeam.uls_flexure import (
    CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY,
    calculate_crossbeam_uls_flexure,
    flexure_input_fingerprint,
)
from concrete_pmm_pro.ui.commercial import render_metric_cards
from concrete_pmm_pro.ui.crossbeam_section_library import CB_SEGMENT_ROWS_KEY
from concrete_pmm_pro.ui.navigation import render_active_choice


CB_LENGTH_KEY = "crossbeam_ui1_length_m"
CB_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"
CB_ANALYSIS_UI1_ULS_CHECK_KEY = "crossbeam_analysis_ui1_uls_check"
CB_ANALYSIS_UI1_SLS_STAGE_KEY = "crossbeam_analysis_ui1_sls_stage"
CB_ANALYSIS_SLS1A_CASE_KEY = "crossbeam_analysis_sls1a_diagram_case"
CB_ANALYSIS_SLS1B_CASE_KEY = "crossbeam_analysis_sls1b_diagram_case"
CB_ANALYSIS_ULS1A_CASE_KEY = "crossbeam_analysis_uls1a_diagram_case"

ULS_CHECKS = ("Flexure", "Shear", "Torsion", "Shear + Torsion")
SLS_STAGE_TRANSFER = "At Transfer"
SLS_STAGE_SERVICE = "At Service"
SLS_STAGES = (SLS_STAGE_TRANSFER, SLS_STAGE_SERVICE)


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _foundation_from_session() -> dict[str, Any]:
    foundation = build_crossbeam_analysis_foundation(
        handoff=st.session_state.get(CB_STATION_FORCE_VALIDATION_KEY),
        member_length_m=float(st.session_state.get(CB_LENGTH_KEY, 20.0) or 20.0),
        construction_method=str(
            st.session_state.get(CB_CONSTRUCTION_METHOD_KEY, "Precast Segmental")
            or "Precast Segmental"
        ),
        segment_rows=_records(st.session_state.get(CB_SEGMENT_ROWS_KEY)),
        section_definitions=_records(st.session_state.get(CB_SECLIB_DEFINITIONS_KEY)),
        rebar_zone_rows=_records(st.session_state.get(CB_RB_ZONE_ROWS_KEY)),
        rebar_template_rows=_records(st.session_state.get(CB_RB_TEMPLATE_ROWS_KEY)),
        transverse_template_rows=_records(st.session_state.get(CB_TR_TEMPLATE_ROWS_KEY)),
        column_rows=_records(st.session_state.get(CB_LOSS_ES_COLUMN_ROWS_KEY)),
    )
    # Input assembly is session-only.  ANALYSIS.UI1 does not add result-cache
    # persistence or write diagnostic output into production results.
    st.session_state[CROSSBEAM_ANALYSIS_FOUNDATION_KEY] = foundation
    return foundation


def _summary_by_dataset(foundation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("Dataset") or ""): dict(row)
        for row in foundation.get("dataset_summaries", [])
        if isinstance(row, Mapping)
    }


def _dataset_summary(foundation: Mapping[str, Any], dataset: str) -> dict[str, Any]:
    return _summary_by_dataset(foundation).get(dataset, {})


def _dataset_ready(summary: Mapping[str, Any]) -> bool:
    return bool(
        summary.get("Source ready")
        and int(summary.get("Mapped check contexts") or 0) > 0
        and int(summary.get("Mapping errors") or 0) == 0
    )


def _source_detail(summary: Mapping[str, Any]) -> str:
    return (
        f"{int(summary.get('Active source rows') or 0)} rows · "
        f"{int(summary.get('Cases') or 0)} cases · "
        f"{int(summary.get('Stations') or 0)} stations"
    )


def _display_rows(foundation: Mapping[str, Any], dataset: str) -> pd.DataFrame:
    rows = [
        dict(row)
        for row in foundation.get("mapped_rows", [])
        if isinstance(row, Mapping) and str(row.get("Dataset") or "") == dataset
    ]
    columns = [
        "Source row",
        "Case / Combination",
        "Station s (m)",
        "Check Point",
        "Station face",
        "Column ID",
        "Column side",
        "Boundary type",
        "Segment / Zone",
        "Section ID",
        "Section role",
        "Rebar Zone",
        "Longitudinal template",
        "Transverse template",
        "P (kN; compression +)",
        "V2 (kN; upward +)",
        "T (kN-m; RH +s)",
        "M3 (kN-m; sagging +)",
        "Joint compression gate",
        "Context status",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).reindex(columns=columns)


def _source_summary_table(foundation: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dataset in DATASET_ORDER:
        summary = _dataset_summary(foundation, dataset)
        rows.append(
            {
                "Dataset": dataset,
                "Status": "READY" if _dataset_ready(summary) else "SOURCE BLOCKED",
                "Rows": int(summary.get("Active source rows") or 0),
                "Cases": int(summary.get("Cases") or 0),
                "Stations": int(summary.get("Stations") or 0),
                "Mapped contexts": int(summary.get("Mapped check contexts") or 0),
            }
        )
    return pd.DataFrame(rows)


def _render_source_audit(
    foundation: Mapping[str, Any],
    *,
    datasets: Sequence[str] = DATASET_ORDER,
) -> None:
    """Keep source mapping available without letting it dominate Analysis."""

    with st.expander("Input source / station coverage audit", expanded=False):
        st.dataframe(
            _source_summary_table(foundation),
            use_container_width=True,
            hide_index=True,
        )
        figure = make_crossbeam_station_coverage_figure(foundation)
        st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})
        st.caption(
            "This is an input-coverage diagram, not a ULS/SLS result graph. Column bands show actual footprints; "
            "dashed lines show Column centerlines. No result or compliance is interpolated between imported stations."
        )

        dataset_list = list(datasets)
        containers = st.tabs(dataset_list) if len(dataset_list) > 1 else [st.container()]
        for container, dataset in zip(containers, dataset_list):
            with container:
                frame = _display_rows(foundation, dataset)
                if frame.empty:
                    st.caption(f"{dataset}: no mapped station-force contexts.")
                else:
                    st.dataframe(
                        frame,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                            "P (kN; compression +)": st.column_config.NumberColumn(format="%.3f"),
                            "V2 (kN; upward +)": st.column_config.NumberColumn(format="%.3f"),
                            "T (kN-m; RH +s)": st.column_config.NumberColumn(format="%.3f"),
                            "M3 (kN-m; sagging +)": st.column_config.NumberColumn(format="%.3f"),
                        },
                    )

        errors = [str(item) for item in foundation.get("errors", [])]
        warnings = [str(item) for item in foundation.get("warnings", [])]
        if errors:
            st.markdown("**Blocking source issues**")
            for error in errors:
                st.error(error)
        if warnings:
            st.markdown("**Source warnings**")
            for warning in warnings:
                st.warning(warning)
        st.caption(
            f"Analysis input fingerprint: {str(foundation.get('fingerprint') or '')[:16] or 'missing'} · "
            f"Loads handoff: {str(foundation.get('loads_handoff_fingerprint') or '')[:16] or 'missing'} · "
            "Input audit only; result state is shown in the decision cards above."
        )


def _not_calculated_graph_note(label: str) -> None:
    st.info(
        f"{label} has not been calculated. The full-length engineering result graph will appear here after the selected solver is implemented and run."
    )


def _uls_governing_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "—"
    return (
        f"{str(value.get('Case / Combination') or '—')} @ "
        f"s={float(value.get('Station s (m)') or 0.0):.3f} m"
    )


def _uls_cards(
    *,
    selected_check: str,
    summary: Mapping[str, Any],
    result: Mapping[str, Any] | None = None,
    result_state: str = "NOT CALCULATED",
) -> list[dict[str, object]]:
    ready = _dataset_ready(summary)
    flexure_active = selected_check == "Flexure"
    displayed_state = result_state if flexure_active else "NOT CALCULATED"
    governing = result.get("governing") if isinstance(result, Mapping) and flexure_active else None
    governing_dc = (
        float(governing.get("P-M3 D/C") or 0.0)
        if isinstance(governing, Mapping)
        else None
    )
    return [
        {
            "title": "Selected check",
            "value": selected_check,
            "detail": "One check workspace at a time",
            "status": "info",
        },
        {
            "title": "Input source",
            "value": "READY" if ready else "SOURCE BLOCKED",
            "detail": _source_detail(summary),
            "status": "ready" if ready else "warning",
        },
        {
            "title": "Result status",
            "value": displayed_state,
            "detail": "ACI 318-19 P–M3 interaction" if flexure_active else "Solver not yet connected",
            "status": _metric_status(displayed_state),
        },
        {
            "title": "Governing P–M3",
            "value": f"D/C {governing_dc:.3f}" if governing_dc is not None else "—",
            "detail": _uls_governing_text(governing),
            "status": _metric_status(displayed_state) if governing_dc is not None else "neutral",
        },
    ]


def _uls_check_table(
    *,
    selected_check: str,
    source_ready: bool,
    flexure_result: Mapping[str, Any] | None = None,
    flexure_state: str = "NOT CALCULATED",
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    governing = flexure_result.get("governing") if isinstance(flexure_result, Mapping) else None
    for check in ULS_CHECKS:
        if not source_ready:
            status = "SOURCE BLOCKED"
            location = "—"
            demand_capacity = "—"
            action = "Complete the ULS source and Section/Rebar mapping."
        elif check == "Flexure":
            status = flexure_state
            location = _uls_governing_text(governing)
            if isinstance(governing, Mapping) and governing.get("P-M3 D/C") is not None:
                demand = abs(float(governing.get("M3 (kN-m; sagging +)") or 0.0))
                capacity = float(governing.get("phiMn at Pu (kN-m)") or 0.0)
                dc = float(governing.get("P-M3 D/C") or 0.0)
                demand_capacity = f"|M3| {demand:,.2f} / φMn@Pu {capacity:,.2f} kN-m · D/C {dc:.3f}"
            else:
                demand_capacity = "—"
            action = (
                "Review P–M3 audit and guarded limitations."
                if status in {"PASS", "REVIEW"}
                else "Revise section/rebar/prestress or ULS demand basis."
                if status == "FAIL"
                else "Calculate Flexure."
            )
        else:
            status = "NOT CALCULATED"
            location = "—"
            demand_capacity = "—"
            action = "Select this check after the Crossbeam solver is implemented."
        rows.append(
            {
                "Check": check,
                "Status": status,
                "Governing station / case": location,
                "Demand / capacity": demand_capacity,
                "Required action": action,
            }
        )
    return pd.DataFrame(rows)


def _render_uls_flexure_result(*, foundation: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    cases = [str(item) for item in result.get("cases", []) if str(item).strip()]
    if not cases:
        st.warning("No calculated ULS Flexure case is available for the result graph.")
        return
    governing = result.get("governing") if isinstance(result.get("governing"), Mapping) else {}
    default_case = str(governing.get("Case / Combination") or cases[0])
    if st.session_state.get(CB_ANALYSIS_ULS1A_CASE_KEY) not in cases:
        st.session_state[CB_ANALYSIS_ULS1A_CASE_KEY] = default_case if default_case in cases else cases[0]
    if len(cases) > 1:
        selected_case = st.selectbox(
            "Diagram case",
            options=cases,
            key=CB_ANALYSIS_ULS1A_CASE_KEY,
            help="The decision summary checks every imported ULS case; the graph displays one case at a time.",
        )
    else:
        selected_case = cases[0]
        st.caption(f"Diagram case: {selected_case}")
    figure = make_crossbeam_flexure_pm3_figure(foundation, result, case_name=selected_case)
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})
    st.caption(
        "Lines connect imported station checks for visualization only. Column bands show actual footprints; dotted lines show Column centerlines; orange dash-dot lines show physical segment joints. No compliance is inferred between unverified stations."
    )
    with st.expander("Flexure P–M3 calculation audit", expanded=False):
        columns = [
            "Case / Combination", "Station s (m)", "Check Point", "Station face",
            "Segment / Zone", "Section ID", "Material", "Longitudinal template",
            "P (kN; compression +)", "M3 (kN-m; sagging +)", "|M3| demand (kN-m)",
            "phiMn at Pu (kN-m)", "P-M3 D/C", "Status", "Capacity method",
            "Rebar count", "As total (mm²)", "Ordinary rebar credited",
            "Bonded tendon groups", "Aps total (mm²)", "Internal section contexts", "Capacity basis",
        ]
        st.dataframe(
            pd.DataFrame(_records(result.get("rows"))).reindex(columns=columns),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                "P (kN; compression +)": st.column_config.NumberColumn(format="%.3f"),
                "M3 (kN-m; sagging +)": st.column_config.NumberColumn(format="%.3f"),
                "|M3| demand (kN-m)": st.column_config.NumberColumn(format="%.3f"),
                "phiMn at Pu (kN-m)": st.column_config.NumberColumn(format="%.3f"),
                "P-M3 D/C": st.column_config.NumberColumn(format="%.3f"),
                "As total (mm²)": st.column_config.NumberColumn(format="%.1f"),
                "Aps total (mm²)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.markdown(
            "**ACI 318-19 axial-flexure basis**  \n"
            "- Strain compatibility with φ-reduced P–M3 sectional capacity.  \n"
            "- P is compression-positive; M3 is sagging-positive.  \n"
            "- P and M3 are taken from the same imported ULS Final Stage row."
        )
        for issue in result.get("errors", []):
            st.error(str(issue))
        for warning in result.get("warnings", []):
            st.warning(str(warning))
        for note in result.get("limitations", []):
            st.caption(f"• {note}")


def render_crossbeam_uls_workspace() -> None:
    """Render compact Crossbeam ULS with ULS1A Flexure connected."""

    foundation = _foundation_from_session()
    summary = _dataset_summary(foundation, DATASET_ULS_FINAL)
    source_ready = _dataset_ready(summary)

    st.subheader("ULS Strength")
    st.caption(
        "Crossbeam-specific ACI 318-19 workspace. External FEA station rows remain the demand source; Section/Rebar capacity is evaluated in the isolated Crossbeam route."
    )
    selected_check = render_active_choice(
        "ULS check to calculate",
        list(ULS_CHECKS),
        key=CB_ANALYSIS_UI1_ULS_CHECK_KEY,
    )

    current_fingerprint = flexure_input_fingerprint(
        foundation=foundation,
        section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
        rebar_template_rows=st.session_state.get(CB_RB_TEMPLATE_ROWS_KEY),
        tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
        tendon_profile_rows=st.session_state.get(CB_PROFILE_ROWS_KEY),
        effective_prestress_link=st.session_state.get(CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY),
        concrete_material=st.session_state.get("concrete_material"),
        concrete_materials=st.session_state.get("concrete_materials"),
        active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
        deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
        prestress_ep_mpa=st.session_state.get(CB_LOSS_EP_MPA_KEY, 195000.0),
    )
    candidate = st.session_state.get(CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY)
    flexure_result = candidate if isinstance(candidate, Mapping) else None
    flexure_state = _result_state(flexure_result, current_fingerprint=current_fingerprint)

    action_col, note_col = st.columns([1, 3])
    with action_col:
        calculate_clicked = st.button(
            f"Calculate {selected_check}",
            type="primary",
            disabled=(not source_ready or selected_check != "Flexure"),
            use_container_width=True,
            help=(
                "Calculate ACI 318-19 P–M3 interaction at every READY ULS station."
                if selected_check == "Flexure"
                else "This Crossbeam strength solver is not connected yet."
            ),
        )
    with note_col:
        st.caption(
            "Uses row-coupled ULS Final Stage P and M3 exactly once; P is compression positive and M3 is sagging positive."
            if selected_check == "Flexure"
            else "Shear and torsion remain isolated future milestones."
        )

    st.info(
        "**ULS sign convention:** P = compression positive (+); M3 = sagging positive (+).  \n"
        "**Flexure check:** simultaneous P and M3 from each imported row are checked against the φ-reduced interaction capacity; D/C ≤ 1.00."
    )

    if calculate_clicked:
        calculated = calculate_crossbeam_uls_flexure(
            foundation=foundation,
            section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
            rebar_template_rows=st.session_state.get(CB_RB_TEMPLATE_ROWS_KEY),
            tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
            tendon_profile_rows=st.session_state.get(CB_PROFILE_ROWS_KEY),
            effective_prestress_link=st.session_state.get(CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY),
            concrete_material=st.session_state.get("concrete_material"),
            concrete_materials=st.session_state.get("concrete_materials"),
            active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
            deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
            prestress_ep_mpa=st.session_state.get(CB_LOSS_EP_MPA_KEY, 195000.0),
        )
        st.session_state[CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY] = calculated
        flexure_result = calculated
        flexure_state = str(calculated.get("status") or "NOT CALCULATED")

    active_result = flexure_result if selected_check == "Flexure" else None
    active_state = flexure_state if selected_check == "Flexure" else "NOT CALCULATED"
    render_metric_cards(
        _uls_cards(
            selected_check=selected_check,
            summary=summary,
            result=active_result,
            result_state=active_state,
        )
    )
    if not source_ready:
        st.error("ULS SOURCE BLOCKED — complete the ULS dataset and Section/Rebar mapping before calculation.")
    if selected_check == "Flexure" and flexure_state == "STALE":
        st.warning("Flexure result is STALE — inputs changed after the last calculation. Recalculate before use.")

    st.markdown("#### Compact ULS check table")
    st.dataframe(
        _uls_check_table(
            selected_check=selected_check,
            source_ready=source_ready,
            flexure_result=flexure_result,
            flexure_state=flexure_state,
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(f"#### {selected_check} result workspace")
    if selected_check == "Flexure" and isinstance(flexure_result, Mapping) and flexure_state != "STALE":
        _render_uls_flexure_result(foundation=foundation, result=flexure_result)
    else:
        _not_calculated_graph_note(f"Crossbeam {selected_check}")
    _render_source_audit(foundation, datasets=(DATASET_ULS_FINAL,))

def _sls_dataset_for_stage(stage: str) -> str:
    return DATASET_SLS_TRANSFER if stage == SLS_STAGE_TRANSFER else DATASET_SLS_SERVICE


def _result_state(result: Mapping[str, Any] | None, *, current_fingerprint: str) -> str:
    if not isinstance(result, Mapping):
        return "NOT CALCULATED"
    if str(result.get("input_fingerprint") or "") != str(current_fingerprint or ""):
        return "STALE"
    return str(result.get("status") or "NOT CALCULATED")


def _metric_status(value: str) -> str:
    text = str(value or "").upper()
    if text == "PASS":
        return "ready"
    if text in {"FAIL", "SOURCE BLOCKED"}:
        return "danger"
    if text in {"STALE", "NOT CALCULATED", "REQUIRED", "INCOMPLETE", "REVIEW"}:
        return "warning"
    return "neutral"


def _governing_location_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "—"
    station = float(value.get("Station s (m)") or 0.0)
    face = str(value.get("Station face") or "").strip()
    case = str(value.get("Case / Combination") or "—").strip()
    fiber = str(value.get("Fiber") or "").strip()
    suffix = " · ".join(item for item in (face, fiber) if item)
    return f"{case} @ s={station:.3f} m" + (f" · {suffix}" if suffix else "")


def _governing_joint_location_text(value: Any) -> str:
    """Format one displayed physical-joint result without left/right faces."""

    if not isinstance(value, Mapping):
        return "—"
    station = float(value.get("Station s (m)") or 0.0)
    case = str(value.get("Case / Combination") or "—").strip()
    fiber = str(value.get("Fiber") or "").strip()
    boundary = str(value.get("Boundary ID") or "").strip()
    suffix = " · ".join(item for item in (boundary, fiber) if item)
    return f"{case} @ s={station:.3f} m" + (f" · {suffix}" if suffix else "")


def _signed_stress_text(value: float, *, decimals: int = 3) -> str:
    """Format signed stress so tension is visibly positive and compression negative."""

    number = float(value)
    tolerance = 0.5 * 10.0 ** (-decimals)
    if abs(number) < tolerance:
        number = 0.0
    text = f"{number:+.{decimals}f}" if number != 0.0 else f"{number:.{decimals}f}"
    return text.replace("-", "−")


def _governing_actual_limit_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "—"
    actual = float(value.get("Stress (MPa)") or 0.0)
    limit = float(value.get("Limit (MPa)") or 0.0)
    utilization = float(value.get("Utilization") or 0.0)
    return (
        f"{_signed_stress_text(actual)} / {_signed_stress_text(limit)} MPa · "
        f"D/C {utilization:.3f}"
    )


def _sls_cards(
    *,
    stage: str,
    summary: Mapping[str, Any],
    construction_method: str,
    result: Mapping[str, Any] | None = None,
    result_state: str = "NOT CALCULATED",
) -> list[dict[str, object]]:
    ready = _dataset_ready(summary)
    joint_required = construction_method == "Precast Segmental"
    stress_status = (
        str(result.get("stress_status") or result_state)
        if isinstance(result, Mapping) and result_state not in {"STALE", "NOT CALCULATED"}
        else result_state
    )
    joint_status = (
        str(result.get("joint_status") or result_state)
        if isinstance(result, Mapping) and result_state not in {"STALE", "NOT CALCULATED"}
        else result_state
    )
    if not joint_required:
        joint_status = "NOT REQUIRED"
    governing = result.get("governing") if isinstance(result, Mapping) else None
    governing_joint = result.get("governing_joint") if isinstance(result, Mapping) else None
    return [
        {
            "title": "Active stage",
            "value": stage,
            "detail": "One service stage at a time",
            "status": "info",
        },
        {
            "title": "Input source",
            "value": "READY" if ready else "SOURCE BLOCKED",
            "detail": _source_detail(summary),
            "status": "ready" if ready else "warning",
        },
        {
            "title": "Stress check",
            "value": stress_status,
            "detail": _governing_location_text(governing) if result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"} else "Top / bottom concrete stress",
            "status": _metric_status(stress_status),
        },
        {
            "title": "Segment joint gate",
            "value": joint_status if joint_required else "NOT REQUIRED",
            "detail": (
                _governing_joint_location_text(governing_joint)
                if joint_required and result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"} and governing_joint
                else "Top and Bottom: fjoint ≤ −0.70 MPa"
                if joint_required
                else "Cast-in-Place — no physical segment joints"
            ),
            "status": _metric_status(joint_status) if joint_required else "neutral",
        },
    ]


def _sls_check_table(
    *,
    stage: str,
    source_ready: bool,
    construction_method: str,
    result: Mapping[str, Any] | None = None,
    result_state: str = "NOT CALCULATED",
) -> pd.DataFrame:
    joint_required = construction_method == "Precast Segmental"
    if not source_ready:
        stress_status = "SOURCE BLOCKED"
    elif result_state == "STALE":
        stress_status = "STALE"
    elif result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW", "SOURCE BLOCKED"} and isinstance(result, Mapping):
        stress_status = str(result.get("stress_status") or result_state)
    else:
        stress_status = "NOT CALCULATED"

    governing = result.get("governing") if isinstance(result, Mapping) else None
    governing_joint = result.get("governing_joint") if isinstance(result, Mapping) else None
    if joint_required:
        if not source_ready:
            joint_status = "SOURCE BLOCKED"
        elif result_state == "STALE":
            joint_status = "STALE"
        elif result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW", "SOURCE BLOCKED"} and isinstance(result, Mapping):
            joint_status = str(result.get("joint_status") or result_state)
        else:
            joint_status = "NOT CALCULATED"
    else:
        joint_status = "NOT REQUIRED"

    joint_actual_limit = "fjoint ≤ −0.700 MPa" if joint_required else "—"
    if joint_required and isinstance(governing_joint, Mapping) and result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"}:
        joint_actual_limit = (
            f"{_signed_stress_text(float(governing_joint.get('Stress (MPa)') or 0.0))} / "
            f"≤ {_signed_stress_text(-float(result.get('joint_min_compression_mpa') or 0.70))} MPa"
        )
    return pd.DataFrame(
        [
            {
                "Check": "Concrete stress — top / bottom",
                "Status": stress_status,
                "Governing station / case": _governing_location_text(governing) if result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"} else "—",
                "Actual / limit": _governing_actual_limit_text(governing) if result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"} else "—",
                "Required action": (
                    f"Review the governing {stage.lower()} stress and source audit."
                    if stress_status == "PASS"
                    else (
                        "Revise the transfer-stage prestress/load/section basis."
                        if stage == SLS_STAGE_TRANSFER
                        else "Revise the final-service prestress/load/section basis."
                    )
                    if stress_status == "FAIL"
                    else (
                        "Adopt transfer-stage duct-void/net-section properties before final PASS."
                        if stage == SLS_STAGE_TRANSFER
                        else "Complete sustained/total service basis and adopted duct-void/net-section review."
                    )
                    if stress_status == "REVIEW"
                    else "Recalculate for the current inputs."
                    if stress_status == "STALE"
                    else "Complete the selected SLS dataset and mapping."
                    if not source_ready
                    else f"Run Calculate {stage}."
                ),
            },
            {
                "Check": "Physical segment-joint compression — Top / Bottom",
                "Status": joint_status,
                "Governing station / case": _governing_joint_location_text(governing_joint) if joint_required and result_state in {"PASS", "FAIL", "INCOMPLETE", "REVIEW"} else "—",
                "Actual / limit": joint_actual_limit,
                "Required action": (
                    "Review the governing Top and Bottom joint compression reserve."
                    if joint_status == "PASS"
                    else "Increase compression reserve; joint opening is not permitted."
                    if joint_status == "FAIL"
                    else "Recalculate for the current inputs."
                    if joint_status == "STALE"
                    else "Provide one result at every physical joint; both Top and Bottom fibers are checked."
                    if joint_required
                    else "Cast-in-Place boundaries are not physical joints."
                ),
            },
        ]
    )


def _transfer_result_audit_table(result: Mapping[str, Any]) -> pd.DataFrame:
    columns = [
        "Case / Combination",
        "Station s (m)",
        "Station face",
        "Segment / Zone",
        "Section ID",
        "Material",
        "f'ci (MPa)",
        "P (kN; compression +)",
        "M3 (kN-m; sagging +)",
        "Axial stress (MPa)",
        "Top bending stress (MPa)",
        "Top stress (MPa)",
        "Top applicable limit (MPa)",
        "Top utilization",
        "Top status",
        "Bottom bending stress (MPa)",
        "Bottom stress (MPa)",
        "Bottom applicable limit (MPa)",
        "Bottom utilization",
        "Bottom status",
        "Joint status",
    ]
    return pd.DataFrame(_records(result.get("rows"))).reindex(columns=columns)


def _joint_result_audit_table(result: Mapping[str, Any]) -> pd.DataFrame:
    columns = [
        "Case / Combination",
        "Boundary ID",
        "Station s (m)",
        "Top stress (MPa)",
        "Top status",
        "Bottom stress (MPa)",
        "Bottom status",
        "Joint minimum signed stress (MPa)",
        "Joint status",
        "Section IDs evaluated",
    ]
    return pd.DataFrame(_records(result.get("joint_rows"))).reindex(columns=columns)


def _render_transfer_result(
    *,
    foundation: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    cases = [str(item) for item in result.get("cases", []) if str(item).strip()]
    if not cases:
        st.warning("No calculated Transfer case is available for the result graph.")
        return
    governing = result.get("governing") if isinstance(result.get("governing"), Mapping) else {}
    default_case = str(governing.get("Case / Combination") or cases[0])
    if st.session_state.get(CB_ANALYSIS_SLS1A_CASE_KEY) not in cases:
        st.session_state[CB_ANALYSIS_SLS1A_CASE_KEY] = default_case if default_case in cases else cases[0]
    if len(cases) > 1:
        selected_case = st.selectbox(
            "Diagram case",
            options=cases,
            key=CB_ANALYSIS_SLS1A_CASE_KEY,
            help="The decision summary checks every imported Transfer case; the graph displays one case at a time.",
        )
    else:
        selected_case = cases[0]
        st.caption(f"Diagram case: {selected_case}")
    figure = make_crossbeam_transfer_stress_figure(
        foundation,
        result,
        case_name=selected_case,
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})
    st.caption(
        "Lines connect imported station checks for visualization only. Column bands show actual footprints; dotted lines show Column centerlines; orange dash-dot lines show physical segment joints. No compliance is inferred between unverified stations."
    )
    with st.expander("Transfer stress calculation audit", expanded=False):
        joint_table = _joint_result_audit_table(result)
        if not joint_table.empty:
            st.markdown("**Physical segment-joint check — one governing value per fiber**")
            st.caption(
                "Both Top and Bottom must satisfy fjoint ≤ −0.70 MPa. Adjacent Section IDs are evaluated internally; the displayed values are the least-compressive / most-tensile results and are not averaged."
            )
            st.dataframe(
                joint_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                    "Top stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                    "Bottom stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                    "Joint minimum signed stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                },
            )
            st.markdown("**Station stress calculation rows**")
        st.dataframe(
            _transfer_result_audit_table(result),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                "f'ci (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "P (kN; compression +)": st.column_config.NumberColumn(format="%.3f"),
                "M3 (kN-m; sagging +)": st.column_config.NumberColumn(format="%.3f"),
                "Axial stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top bending stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top applicable limit (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top utilization": st.column_config.NumberColumn(format="%.3f"),
                "Bottom bending stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom applicable limit (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom utilization": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        limit_basis = result.get("limit_basis") if isinstance(result.get("limit_basis"), Mapping) else {}
        st.markdown(
            "**ACI 318-19 transfer basis**  \n"
            f"- Compression: {limit_basis.get('compression', '0.60 f\'ci')}  \n"
            f"- Tension: {limit_basis.get('tension', '0.25 sqrt(f\'ci)')}  \n"
            f"- Joint: {limit_basis.get('joint', 'Project criterion')}  \n"
            f"- Sign convention: {result.get('sign_convention', 'Compression negative / tension positive')}"
        )
        coverage_issues = [str(item) for item in result.get("joint_coverage_issues", [])]
        if coverage_issues:
            st.markdown("**Joint coverage issues**")
            for issue in coverage_issues:
                st.warning(issue)
        for note in result.get("limitations", []):
            st.caption(f"• {note}")



def _service_result_audit_table(result: Mapping[str, Any]) -> pd.DataFrame:
    columns = [
        "Case / Combination",
        "Service load condition",
        "Station s (m)",
        "Station face",
        "Segment / Zone",
        "Section ID",
        "Material",
        "f'c (MPa)",
        "P (kN; compression +)",
        "M3 (kN-m; sagging +)",
        "Axial stress (MPa)",
        "Top bending stress (MPa)",
        "Top stress (MPa)",
        "Top applicable limit (MPa)",
        "Top utilization",
        "Top status",
        "Bottom bending stress (MPa)",
        "Bottom stress (MPa)",
        "Bottom applicable limit (MPa)",
        "Bottom utilization",
        "Bottom status",
        "Joint status",
    ]
    return pd.DataFrame(_records(result.get("rows"))).reindex(columns=columns)


def _service_cases_from_foundation(foundation: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("Case / Combination") or "").strip()
            for row in foundation.get("mapped_rows", [])
            if isinstance(row, Mapping)
            and str(row.get("Dataset") or "") == DATASET_SLS_SERVICE
            and str(row.get("Case / Combination") or "").strip()
        }
    )


def _render_service_result(
    *,
    foundation: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    cases = [str(item) for item in result.get("cases", []) if str(item).strip()]
    if not cases:
        st.warning("No calculated At Service case is available for the result graph.")
        return
    governing = result.get("governing") if isinstance(result.get("governing"), Mapping) else {}
    default_case = str(governing.get("Case / Combination") or cases[0])
    if st.session_state.get(CB_ANALYSIS_SLS1B_CASE_KEY) not in cases:
        st.session_state[CB_ANALYSIS_SLS1B_CASE_KEY] = default_case if default_case in cases else cases[0]
    if len(cases) > 1:
        selected_case = st.selectbox(
            "Diagram case",
            options=cases,
            key=CB_ANALYSIS_SLS1B_CASE_KEY,
            help="The decision summary checks every imported service case; the graph displays one case at a time.",
        )
    else:
        selected_case = cases[0]
        st.caption(f"Diagram case: {selected_case}")
    figure = make_crossbeam_service_stress_figure(
        foundation,
        result,
        case_name=selected_case,
    )
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})
    st.caption(
        "Lines connect imported station checks for visualization only. Column bands show actual footprints; dotted lines show Column centerlines; orange dash-dot lines show physical segment joints. No compliance is inferred between unverified stations."
    )
    with st.expander("At Service stress calculation audit", expanded=False):
        joint_table = _joint_result_audit_table(result)
        if not joint_table.empty:
            st.markdown("**Physical segment-joint check — one governing value per fiber**")
            st.caption(
                "Both Top and Bottom must satisfy fjoint ≤ −0.70 MPa. Adjacent Section IDs are evaluated internally; the displayed values are the least-compressive / most-tensile results and are not averaged."
            )
            st.dataframe(
                joint_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                    "Top stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                    "Bottom stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                    "Joint minimum signed stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                },
            )
            st.markdown("**Station stress calculation rows**")
        st.dataframe(
            _service_result_audit_table(result),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                "f'c (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "P (kN; compression +)": st.column_config.NumberColumn(format="%.3f"),
                "M3 (kN-m; sagging +)": st.column_config.NumberColumn(format="%.3f"),
                "Axial stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top bending stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top applicable limit (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Top utilization": st.column_config.NumberColumn(format="%.3f"),
                "Bottom bending stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom stress (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom applicable limit (MPa)": st.column_config.NumberColumn(format="%.3f"),
                "Bottom utilization": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        limit_basis = result.get("limit_basis") if isinstance(result.get("limit_basis"), Mapping) else {}
        st.markdown(
            "**ACI 318-19 final-service basis**  \n"
            f"- Sustained compression: {limit_basis.get('compression_sustained', '0.45 f\'c')}  \n"
            f"- Total-load compression: {limit_basis.get('compression_total', '0.60 f\'c')}  \n"
            f"- Tension: {limit_basis.get('tension', 'Class U: 0.62 sqrt(f\'c)')}  \n"
            f"- Joint: {limit_basis.get('joint', 'Project criterion')}  \n"
            f"- Sign convention: {result.get('sign_convention', 'Compression negative / tension positive')}"
        )
        basis_issues = [str(item) for item in result.get("basis_coverage_issues", [])]
        if basis_issues:
            st.markdown("**Service load-basis review**")
            for issue in basis_issues:
                st.warning(issue)
        coverage_issues = [str(item) for item in result.get("joint_coverage_issues", [])]
        if coverage_issues:
            st.markdown("**Joint coverage issues**")
            for issue in coverage_issues:
                st.warning(issue)
        for note in result.get("limitations", []):
            st.caption(f"• {note}")

def render_crossbeam_sls_workspace() -> None:
    """Render compact Crossbeam SLS for Transfer and final Service stages."""

    foundation = _foundation_from_session()
    construction_method = str(foundation.get("construction_method") or "Precast Segmental")

    st.subheader("SLS / Stress & Joint Compression")
    st.caption(
        "Full-length top/bottom stress review follows the accepted Beam/Girder chart language, with Crossbeam Columns and physical segment joints added."
    )
    stage = render_active_choice(
        "SLS stage",
        list(SLS_STAGES),
        key=CB_ANALYSIS_UI1_SLS_STAGE_KEY,
    )
    dataset = _sls_dataset_for_stage(stage)
    summary = _dataset_summary(foundation, dataset)
    source_ready = _dataset_ready(summary)

    sustained_cases: list[str] = []
    if stage == SLS_STAGE_SERVICE:
        available_cases = _service_cases_from_foundation(foundation)
        saved_cases = canonical_sustained_case_names(
            st.session_state.get(CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY, [])
        )
        valid_saved = [name for name in saved_cases if name in available_cases]
        if st.session_state.get(CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY) != valid_saved:
            st.session_state[CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY] = valid_saved
        with st.expander("Service stress basis", expanded=False):
            if available_cases:
                st.multiselect(
                    "Prestress + sustained load cases",
                    options=available_cases,
                    key=CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY,
                    help=(
                        "Selected cases use the ACI 318-19 compression limit 0.45f'c. "
                        "Unselected service cases use the total-load limit 0.60f'c."
                    ),
                )
                st.caption(
                    "Tension is checked on a conservative Class U basis: ft ≤ 0.62√f'c. "
                    + (
                        "For Precast Segmental, physical joints retain the separate Top/Bottom gate fjoint ≤ −0.70 MPa."
                        if construction_method == "Precast Segmental"
                        else "For Cast-in-Place, the physical segment-joint gate is not required."
                    )
                )
            else:
                st.caption("No SLS At Service cases are available for basis assignment.")
        sustained_cases = canonical_sustained_case_names(
            st.session_state.get(CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY, [])
        )

    current_fingerprint = ""
    stored_result: Mapping[str, Any] | None = None
    result_state = "NOT CALCULATED"
    if stage == SLS_STAGE_TRANSFER:
        current_fingerprint = transfer_stress_input_fingerprint(
            foundation=foundation,
            section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
            concrete_material=st.session_state.get("concrete_material"),
            concrete_materials=st.session_state.get("concrete_materials"),
            active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
            deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
            tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
            stressing_strength_ratio=st.session_state.get(
                CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
                DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
            ),
        )
        candidate = st.session_state.get(CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY)
        stored_result = candidate if isinstance(candidate, Mapping) else None
        result_state = _result_state(stored_result, current_fingerprint=current_fingerprint)
    else:
        current_fingerprint = service_stress_input_fingerprint(
            foundation=foundation,
            section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
            concrete_material=st.session_state.get("concrete_material"),
            concrete_materials=st.session_state.get("concrete_materials"),
            active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
            deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
            tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
            sustained_case_names=sustained_cases,
        )
        candidate = st.session_state.get(CB_ANALYSIS_SLS_SERVICE_RESULT_KEY)
        stored_result = candidate if isinstance(candidate, Mapping) else None
        result_state = _result_state(stored_result, current_fingerprint=current_fingerprint)

    action_col, note_col = st.columns([1, 3])
    with action_col:
        calculate_clicked = st.button(
            f"Calculate {stage}",
            type="primary",
            disabled=not source_ready,
            use_container_width=True,
            help=(
                "Calculate ACI 318-19 transfer-stage top/bottom concrete stress"
                + (" and the project physical-joint compression gate." if construction_method == "Precast Segmental" else ".")
                if stage == SLS_STAGE_TRANSFER
                else "Calculate ACI 318-19 Class U final-service stress and sustained/total compression limits"
                + (", including the project physical-joint compression gate." if construction_method == "Precast Segmental" else ".")
            ),
        )

    with note_col:
        st.caption(
            "Uses imported Transfer P and M3 exactly once; compression is negative and tension is positive."
            if stage == SLS_STAGE_TRANSFER
            else (
                f"Class U · {len(sustained_cases)} sustained case(s); unselected cases use total-load limits. "
                "Imported final-service P and M3 are used exactly once."
            )
        )

    if construction_method == "Precast Segmental":
        st.info(
            "**Stress sign convention:** Compression = negative (−); Tension = positive (+).  \n"
            "**Physical segment-joint gate:** one result is shown per joint. Both Top and Bottom must satisfy "
            "`fjoint ≤ −0.70 MPa` (compression magnitude ≥ 0.70 MPa)."
        )
    else:
        st.info(
            "**Stress sign convention:** Compression = negative (−); Tension = positive (+).  \n"
            "**Segment-joint gate:** NOT REQUIRED — Cast-in-Place Section/Zone boundaries are monolithic, not physical segment joints."
        )

    if calculate_clicked:
        if stage == SLS_STAGE_TRANSFER:
            calculated = calculate_crossbeam_transfer_stress(
                foundation=foundation,
                section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
                concrete_material=st.session_state.get("concrete_material"),
                concrete_materials=st.session_state.get("concrete_materials"),
                active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
                deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
                tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
                stressing_strength_ratio=st.session_state.get(
                    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
                    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
                ),
            )
            st.session_state[CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY] = calculated
        else:
            calculated = calculate_crossbeam_service_stress(
                foundation=foundation,
                section_definitions=st.session_state.get(CB_SECLIB_DEFINITIONS_KEY),
                concrete_material=st.session_state.get("concrete_material"),
                concrete_materials=st.session_state.get("concrete_materials"),
                active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
                deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
                tendon_system_rows=st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY),
                sustained_case_names=sustained_cases,
            )
            st.session_state[CB_ANALYSIS_SLS_SERVICE_RESULT_KEY] = calculated
        rerun = getattr(st, "rerun", None)
        if callable(rerun):
            rerun()
        stored_result = calculated
        result_state = str(calculated.get("status") or "NOT CALCULATED")

    render_metric_cards(
        _sls_cards(
            stage=stage,
            summary=summary,
            construction_method=construction_method,
            result=stored_result,
            result_state=result_state,
        )
    )
    if not source_ready:
        st.error(f"{dataset.upper()} SOURCE BLOCKED — complete this dataset and Section mapping before calculation.")
    elif result_state == "STALE":
        st.warning(f"{stage.upper()} STRESS RESULT STALE — inputs changed after the last calculation. Run Calculate {stage} again.")
    elif result_state == "INCOMPLETE" and isinstance(stored_result, Mapping):
        issues = [str(item) for item in stored_result.get("joint_coverage_issues", [])]
        st.warning(
            issues[0]
            if issues
            else f"{stage.upper()} JOINT CHECK INCOMPLETE — provide one result at every physical joint for every case; both Top and Bottom fibers are checked."
        )
    elif result_state == "REVIEW" and isinstance(stored_result, Mapping):
        basis_issues = [str(item) for item in stored_result.get("basis_coverage_issues", [])]
        internal_ids = [str(item) for item in stored_result.get("active_internal_tendon_ids", [])]
        if basis_issues:
            st.warning(basis_issues[0])
        elif internal_ids:
            st.warning(
                f"{stage.upper()} SECTION BASIS REVIEW — gross Section ID properties are used, but active Internal Tendon duct voids are not yet deducted ({', '.join(internal_ids)})."
            )
        else:
            st.warning(f"{stage.upper()} ENGINEERING REVIEW REQUIRED — see the calculation audit.")
    elif result_state == "SOURCE BLOCKED" and isinstance(stored_result, Mapping):
        errors = [str(item) for item in stored_result.get("errors", [])]
        st.error(errors[0] if errors else f"{stage} stress calculation is source-blocked.")

    st.markdown("#### Compact SLS check table")
    st.dataframe(
        _sls_check_table(
            stage=stage,
            source_ready=source_ready,
            construction_method=construction_method,
            result=stored_result,
            result_state=result_state,
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(f"#### Concrete stress — {stage}")
    visible_states = {"PASS", "FAIL", "INCOMPLETE", "REVIEW"}
    if isinstance(stored_result, Mapping) and result_state in visible_states and stored_result.get("solver_run"):
        if stage == SLS_STAGE_TRANSFER:
            _render_transfer_result(foundation=foundation, result=stored_result)
        else:
            _render_service_result(foundation=foundation, result=stored_result)
    elif result_state == "SOURCE BLOCKED" and isinstance(stored_result, Mapping):
        with st.expander(f"{stage} stress blocking issues", expanded=False):
            for error in stored_result.get("errors", []):
                st.error(str(error))
    else:
        _not_calculated_graph_note(f"Crossbeam concrete stress {stage}")
    _render_source_audit(foundation, datasets=(dataset,))

def render_crossbeam_analysis_foundation() -> None:
    """Legacy entry retained for compatibility; the audit is no longer a main page."""

    foundation = _foundation_from_session()
    st.subheader("Analysis Input Audit")
    st.caption(
        "The former Station Check Foundation has been consolidated into the ULS/SLS source-audit expander so input diagnostics do not dominate the engineering result workspace."
    )
    _render_source_audit(foundation)

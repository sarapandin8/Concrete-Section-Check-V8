"""Compact Crossbeam Analysis workspaces.

Crossbeam Analysis follows the same decision-first language as the accepted
Beam/Girder ULS and SLS pages, while keeping Crossbeam solver/state ownership
isolated.  ANALYSIS.UI1 is a UI shell only: it does not evaluate ACI 318
strength or service-stress equations.
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
from concrete_pmm_pro.crossbeam.analysis_charts import make_crossbeam_station_coverage_figure
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import CB_SECLIB_DEFINITIONS_KEY
from concrete_pmm_pro.crossbeam.station_force_contract import CB_STATION_FORCE_VALIDATION_KEY
from concrete_pmm_pro.ui.commercial import render_metric_cards
from concrete_pmm_pro.ui.crossbeam_section_library import CB_SEGMENT_ROWS_KEY
from concrete_pmm_pro.ui.navigation import render_active_choice


CB_LENGTH_KEY = "crossbeam_ui1_length_m"
CB_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"
CB_ANALYSIS_UI1_ULS_CHECK_KEY = "crossbeam_analysis_ui1_uls_check"
CB_ANALYSIS_UI1_SLS_STAGE_KEY = "crossbeam_analysis_ui1_sls_stage"

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
            "Solver run: No"
        )


def _not_calculated_graph_note(label: str) -> None:
    st.info(
        f"{label} has not been calculated. The full-length engineering result graph will appear here after the selected solver is implemented and run."
    )


def _uls_cards(
    *,
    selected_check: str,
    summary: Mapping[str, Any],
) -> list[dict[str, object]]:
    ready = _dataset_ready(summary)
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
            "value": "NOT CALCULATED",
            "detail": "No ACI 318-19 strength equation evaluated",
            "status": "warning",
        },
        {
            "title": "Governing",
            "value": "—",
            "detail": "Station / case available after calculation",
            "status": "neutral",
        },
    ]


def _uls_check_table(*, selected_check: str, source_ready: bool) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for check in ULS_CHECKS:
        status = "NOT CALCULATED" if source_ready else "SOURCE BLOCKED"
        action = (
            "Run the selected Crossbeam solver when available."
            if check == selected_check and source_ready
            else "Complete the ULS source and mapping."
            if not source_ready
            else "Select this check when review is required."
        )
        rows.append(
            {
                "Check": check,
                "Status": status,
                "Governing station / case": "—",
                "Demand / capacity": "—",
                "Required action": action,
            }
        )
    return pd.DataFrame(rows)


def render_crossbeam_uls_workspace() -> None:
    """Render compact Crossbeam ULS shell without using generic member solvers."""

    foundation = _foundation_from_session()
    summary = _dataset_summary(foundation, DATASET_ULS_FINAL)
    source_ready = _dataset_ready(summary)

    st.subheader("ULS Strength")
    st.caption(
        "Crossbeam-specific ACI 318-19 workspace. External FEA station rows remain the demand source; no generic Beam/Girder solver is reused."
    )
    selected_check = render_active_choice(
        "ULS check to calculate",
        list(ULS_CHECKS),
        key=CB_ANALYSIS_UI1_ULS_CHECK_KEY,
    )
    action_col, note_col = st.columns([1, 3])
    with action_col:
        st.button(
            f"Calculate {selected_check}",
            type="primary",
            disabled=True,
            use_container_width=True,
            help="ANALYSIS.UI1 establishes the compact workspace only; the engineering solver is a later milestone.",
        )
    with note_col:
        st.caption(
            "Solver not yet connected. The disabled action prevents a UI shell from being mistaken for a completed strength check."
        )

    render_metric_cards(_uls_cards(selected_check=selected_check, summary=summary))
    if not source_ready:
        st.error("ULS SOURCE BLOCKED — complete the ULS dataset and Section/Rebar mapping before calculation.")

    st.markdown("#### Compact ULS check table")
    st.dataframe(
        _uls_check_table(selected_check=selected_check, source_ready=source_ready),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(f"#### {selected_check} result workspace")
    _not_calculated_graph_note(f"Crossbeam {selected_check}")
    _render_source_audit(foundation, datasets=(DATASET_ULS_FINAL,))


def _sls_dataset_for_stage(stage: str) -> str:
    return DATASET_SLS_TRANSFER if stage == SLS_STAGE_TRANSFER else DATASET_SLS_SERVICE


def _sls_cards(
    *,
    stage: str,
    summary: Mapping[str, Any],
    construction_method: str,
) -> list[dict[str, object]]:
    ready = _dataset_ready(summary)
    joint_required = construction_method == "Precast Segmental"
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
            "value": "NOT CALCULATED",
            "detail": "Top / bottom concrete stress",
            "status": "warning",
        },
        {
            "title": "Segment joint gate",
            "value": "REQUIRED" if joint_required else "NOT REQUIRED",
            "detail": "Top and bottom compression ≥ 0.70 MPa" if joint_required else "Cast-in-Place zone boundaries",
            "status": "warning" if joint_required else "neutral",
        },
    ]


def _sls_check_table(
    *,
    source_ready: bool,
    construction_method: str,
) -> pd.DataFrame:
    stress_status = "NOT CALCULATED" if source_ready else "SOURCE BLOCKED"
    joint_required = construction_method == "Precast Segmental"
    return pd.DataFrame(
        [
            {
                "Check": "Concrete stress — top / bottom",
                "Status": stress_status,
                "Governing station / case": "—",
                "Actual / limit": "—",
                "Required action": (
                    "Run the selected SLS stage when available."
                    if source_ready
                    else "Complete the selected SLS dataset and mapping."
                ),
            },
            {
                "Check": "Physical segment-joint compression",
                "Status": (
                    "NOT CALCULATED"
                    if joint_required and source_ready
                    else "SOURCE BLOCKED"
                    if joint_required
                    else "NOT REQUIRED"
                ),
                "Governing station / case": "—",
                "Actual / limit": "≥ 0.70 MPa compression" if joint_required else "—",
                "Required action": (
                    "Check s− / s+ top and bottom fibers for every imported case."
                    if joint_required
                    else "Cast-in-Place boundaries are not physical joints."
                ),
            },
        ]
    )


def render_crossbeam_sls_workspace() -> None:
    """Render compact staged SLS shell with the project joint-compression gate."""

    foundation = _foundation_from_session()
    construction_method = str(foundation.get("construction_method") or "Precast Segmental")

    st.subheader("SLS / Stress & Joint Compression")
    st.caption(
        "Full-length top/bottom stress review will follow the accepted Beam/Girder chart language, with Crossbeam Columns and physical segment joints added."
    )
    stage = render_active_choice(
        "SLS stage",
        list(SLS_STAGES),
        key=CB_ANALYSIS_UI1_SLS_STAGE_KEY,
    )
    dataset = _sls_dataset_for_stage(stage)
    summary = _dataset_summary(foundation, dataset)
    source_ready = _dataset_ready(summary)

    action_col, note_col = st.columns([1, 3])
    with action_col:
        st.button(
            f"Calculate {stage}",
            type="primary",
            disabled=True,
            use_container_width=True,
            help="ANALYSIS.UI1 establishes the compact workspace only; the SLS solver is a later milestone.",
        )
    with note_col:
        st.caption(
            "Solver not yet connected. Stress limits, governing fibers, and joint compression are not evaluated by this milestone."
        )

    render_metric_cards(
        _sls_cards(
            stage=stage,
            summary=summary,
            construction_method=construction_method,
        )
    )
    if not source_ready:
        st.error(f"{dataset.upper()} SOURCE BLOCKED — complete this dataset and Section mapping before calculation.")

    st.markdown("#### Compact SLS check table")
    st.dataframe(
        _sls_check_table(
            source_ready=source_ready,
            construction_method=construction_method,
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(f"#### Concrete stress — {stage}")
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

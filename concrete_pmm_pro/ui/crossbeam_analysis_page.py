"""Crossbeam-specific Analysis workspace.

The first milestone is a read-only, three-stage station-check input foundation.
It deliberately does not reuse the generic Beam/Girder or Column/Pier solvers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import streamlit as st

from concrete_pmm_pro.crossbeam.analysis_foundation import (
    CROSSBEAM_ANALYSIS_FOUNDATION_KEY,
    DATASET_ORDER,
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
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_section_bar
from concrete_pmm_pro.ui.crossbeam_section_library import CB_SEGMENT_ROWS_KEY


CB_LENGTH_KEY = "crossbeam_ui1_length_m"
CB_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"


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
    # Session-only source assembly for later Crossbeam Analysis milestones.
    # Project JSON result persistence is intentionally not introduced here.
    st.session_state[CROSSBEAM_ANALYSIS_FOUNDATION_KEY] = foundation
    return foundation


def _summary_by_dataset(foundation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("Dataset") or ""): dict(row)
        for row in foundation.get("dataset_summaries", [])
        if isinstance(row, Mapping)
    }


def _analysis1_cards(foundation: Mapping[str, Any]) -> list[dict[str, object]]:
    summaries = _summary_by_dataset(foundation)
    cards: list[dict[str, object]] = [
        {
            "title": "Source assembly",
            "value": str(foundation.get("status") or "SOURCE BLOCKED"),
            "detail": "No structural solver run",
            "status": "ready" if foundation.get("ready") else "warning",
        }
    ]
    for dataset in DATASET_ORDER:
        summary = summaries.get(dataset, {})
        cards.append(
            {
                "title": dataset,
                "value": str(summary.get("Mapped check contexts", 0)),
                "detail": (
                    f"{summary.get('Active source rows', 0)} source rows · "
                    f"{summary.get('Cases', 0)} cases · {summary.get('Stations', 0)} stations"
                ),
                "status": "ready" if summary.get("Source ready") and not summary.get("Mapping errors") else "warning",
            }
        )
    coverage = foundation.get("station_coverage") if isinstance(foundation.get("station_coverage"), Mapping) else {}
    cards.append(
        {
            "title": "Station coverage",
            "value": str(coverage.get("status") or "REVIEW REQUIRED"),
            "detail": (
                f"{coverage.get('covered_requirements', 0)} / "
                f"{coverage.get('required_requirements', 0)} structural requirements"
            ),
            "status": "ready" if coverage.get("ready") else "warning",
        }
    )
    return cards


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


def render_crossbeam_analysis_foundation() -> None:
    """Render ``CROSSBEAM.ANALYSIS1`` without executing any design equation."""

    foundation = _foundation_from_session()
    render_section_bar(
        "Three-Stage Station-Check Foundation",
        "Read-only assembly of validated ULS Final, SLS At Transfer, and SLS At Service station forces with Section ID and reinforcement source mapping.",
        mark="A1",
    )
    render_metric_cards(_analysis1_cards(foundation))

    st.caption(
        "Member design basis: ACI 318-19. Prestress-loss basis: AASHTO LRFD 2020 Section 5.9.3. "
        "This milestone maps sources only; it does not calculate stress, flexure, shear, torsion, or capacity."
    )
    if foundation.get("ready"):
        st.success(
            "THREE-STAGE INPUT ASSEMBLY READY · "
            f"Foundation {str(foundation.get('fingerprint') or '')[:12]} · no solver run"
        )
    else:
        st.error(
            "SOURCE BLOCKED — Crossbeam Analysis checks cannot start until Loads, Section/Zone, Section ID, and reinforcement mappings are complete."
        )

    if str(foundation.get("construction_method")) == "Precast Segmental":
        st.info(
            "Precast Segmental physical joints are mapped as one-sided s- / s+ faces. Future SLS checks must verify both top and bottom fibers remain at least 0.70 MPa in compression for every imported Transfer and Service case."
        )
    else:
        st.info(
            "Cast-in-Place boundaries are Section / analysis zones within one monolithic member; the 0.70 MPa physical segment-joint gate does not apply."
        )

    render_section_bar(
        "Full-Length Source Coverage",
        "Shared Crossbeam Analysis chart foundation showing imported station contexts, Segment/Zone bands, physical or analysis boundaries, and actual Column footprints/centerlines.",
        mark="A1A",
    )
    coverage_figure = make_crossbeam_station_coverage_figure(foundation)
    st.plotly_chart(
        coverage_figure,
        use_container_width=True,
        config={"displaylogo": False},
    )
    st.caption(
        "Markers are validated imported station-check contexts. Column bands show the actual footprint along s; dashed lines show Column centerlines. "
        "No production stress/capacity envelope is interpolated between unverified stations."
    )

    tabs = st.tabs(list(DATASET_ORDER))
    for tab, dataset in zip(tabs, DATASET_ORDER):
        with tab:
            dataframe = _display_rows(foundation, dataset)
            if dataframe.empty:
                st.warning(f"{dataset}: no mapped active station-force contexts are available.")
            else:
                st.dataframe(
                    dataframe,
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
            st.caption(
                "Each displayed context retains one source-row identity and one row-coupled P, V2, T, M3 state. "
                "Two faces at a boundary are section mappings of the same source row, not a synthetic force envelope."
            )

    errors = [str(item) for item in foundation.get("errors", [])]
    warnings = [str(item) for item in foundation.get("warnings", [])]
    with st.expander("Source readiness, traceability, and limitations", expanded=bool(errors)):
        st.markdown(
            f"**Loads handoff:** `{str(foundation.get('loads_handoff_fingerprint') or '')[:16] or 'missing'}`  "
            f"\n**Analysis foundation:** `{str(foundation.get('fingerprint') or '')[:16]}`  "
            f"\n**Construction:** `{foundation.get('construction_method')}`  "
            f"\n**Solver run:** `No`"
        )
        for error in errors:
            st.error(error)
        for warning in warnings:
            st.warning(warning)
        coverage = foundation.get("station_coverage") if isinstance(foundation.get("station_coverage"), Mapping) else {}
        missing_rows = [
            dict(row)
            for row in coverage.get("missing_rows", [])
            if isinstance(row, Mapping)
        ]
        if missing_rows:
            st.warning(
                "STATION COVERAGE REVIEW REQUIRED — required member ends, one-sided Column contexts, or Segment/Zone boundaries are missing from one or more datasets."
            )
            st.dataframe(
                pd.DataFrame(missing_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Station s (m)": st.column_config.NumberColumn(format="%.6f"),
                },
            )
        for limitation in foundation.get("limitations", []):
            st.caption(f"• {limitation}")

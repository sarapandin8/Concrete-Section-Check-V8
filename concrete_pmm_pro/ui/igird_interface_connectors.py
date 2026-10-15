"""Source-specific interface inputs; reuses the existing anchorage declaration."""
import hashlib
import json
import math
import pandas as pd
import streamlit as st
from concrete_pmm_pro.analysis.igird_interface_connectors import (
    DOWEL_COLUMNS, SOURCE_LABELS, LINKED_DOWELS, INDEPENDENT_DOWELS, copy_girder_zoning, settings_fields,
)


def render_source(current, girder_zones):
    cfg = settings_fields(current)
    options = list(SOURCE_LABELS)
    if cfg["connector_source"] not in options:
        options.append(cfg["connector_source"])
    source = st.selectbox("Interface reinforcement source",options,
        index=options.index(cfg["connector_source"]),
        format_func=lambda s:SOURCE_LABELS.get(s,"Unknown source — choose a supported source"))
    cfg["connector_source"] = source
    if source == LINKED_DOWELS:
        try:
            legs = float(cfg["dowel_crossing_legs"])
            if not math.isfinite(legs): legs = 0.
        except (TypeError,ValueError): legs = 0.
        cfg["dowel_crossing_legs"] = st.number_input("Dowel legs crossing the interface per set",min_value=0.,
            value=max(0.,legs),step=1.,format="%.0f")
        st.caption("Diameter, spacing, fy and longitudinal zoning follow the girder table by this explicit selection. "
            "The dowel crossing-leg count is separate from the I-girder stirrup leg count.")
    elif source == INDEPENDENT_DOWELS:
        with st.expander("Dowel layout",expanded=True):
            rows = cfg["dowel_zones"] if isinstance(cfg["dowel_zones"],list) else []
            if st.button("Copy current girder zoning into separate dowel layout"):
                rows = copy_girder_zoning(girder_zones.to_dict("records"),crossing_legs=2)
            frame = pd.DataFrame(rows,columns=DOWEL_COLUMNS)
            for col in DOWEL_COLUMNS[1:]: frame[col] = pd.to_numeric(frame[col],errors="coerce")
            signature = hashlib.sha256(frame.to_json(orient="records").encode()).hexdigest()[:12]
            edited = st.data_editor(frame,hide_index=True,num_rows="dynamic",use_container_width=True,
                key="igird_interface_dowel_layout_"+signature,
                column_config={"Zone":st.column_config.TextColumn("Dowel zone"),
                    "x_start_m":st.column_config.NumberColumn("Start x (m)"),
                    "x_end_m":st.column_config.NumberColumn("End x (m)"),
                    "Diameter_mm":st.column_config.NumberColumn("db (mm)"),
                    "Legs":st.column_config.NumberColumn("Crossing legs",step=1),
                    "Spacing_mm":st.column_config.NumberColumn("Spacing (mm)"),
                    "fy_MPa":st.column_config.NumberColumn("fy (MPa)")})
            cfg["dowel_zones"] = json.loads(edited.to_json(orient="records",double_precision=15))
            st.caption("Copying creates independent inputs. Enter actual dowel spacings and start/end stations from the longitudinal detail; "
                "section labels C–C / D–D / E–E do not determine the zone lengths.")
    st.caption("This input supplies interface Avf only. It does not enlarge the I-girder torsion hoop or add dowel steel to Ao/ph or longitudinal Al.")
    return cfg

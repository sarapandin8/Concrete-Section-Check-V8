"""Compact input inventory. No steel is inferred to close a torsion cage."""
import json
import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis.igird_dowel_detail35 import mesh_rows, mesh_inventory, value


def render(cfg, params):
    with st.expander("Slab mesh — top / bottom, both directions", expanded=False, key="igird_detail35_mesh_panel"):
        inventory = mesh_inventory(cfg, params)
        st.caption("Along girder = existing Section Builder reinforcement; no re-entry. Across girder = the other direction in each mesh. Bar intersections are tied in the concrete; they do not automatically establish a closed torsion path.")
        st.dataframe(pd.DataFrame(inventory[:2])[["Layer", "Direction", "Diameter_mm", "Spacing_mm", "Clear_cover_mm", "fy_MPa"]], hide_index=True, use_container_width=True)
        st.markdown("**Across girder — enter only the missing direction**")
        st.caption("Clear cover is measured to the actual transverse bar surface, not automatically copied from the longitudinal layer. fy starts from the existing slab layer grade and remains editable.")
        from .igird_input_editor import input_editor
        frame = pd.DataFrame(mesh_rows(cfg, params))
        for column in ("Diameter_mm", "Spacing_mm", "Clear_cover_mm", "fy_MPa"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        edited = input_editor(frame, prefix="igird_detail35_mesh_", disabled=["Layer"], num_rows="fixed", hide_index=True, use_container_width=True,
            column_config={"Diameter_mm":st.column_config.NumberColumn("Bar diameter (mm)", min_value=0.),
                "Spacing_mm":st.column_config.NumberColumn("Spacing (mm)", min_value=0.),
                "Clear_cover_mm":st.column_config.NumberColumn("Actual clear cover (mm)", min_value=0.),
                "fy_MPa":st.column_config.NumberColumn("fy (MPa)", min_value=0.)})
        records = json.loads(edited.to_json(orient="records", double_precision=15))
        cfg["slab_transverse_mesh"] = {layer:{k:value(row.get(k)) for k in ("Diameter_mm", "Spacing_mm", "Clear_cover_mm", "fy_MPa")}
            for layer,row in zip(("top", "bottom"), records)}
        if any(row["As_mm2_per_m"] is not None for row in mesh_inventory(cfg, params)[2:]):
            with st.expander("Mesh inventory / area per metre", expanded=False):
                st.dataframe(pd.DataFrame(mesh_inventory(cfg, params)), hide_index=True, use_container_width=True)
        st.caption("Saved input inventory only. Transverse bars are not added to longitudinal Mn, substituted for research closing bars, or credited to full composite Tn / V–T by this release. Anchorage and force transfer remain separate checks.")
    return cfg

"""Section Builder inputs and geometry-only station preview."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from concrete_pmm_pro.analysis import igird_end_sections as ends
from concrete_pmm_pro.visualization import create_section_preview
PREFIX="igird_end18_"

def render_inputs(params,geometry):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.section_builder import _commercial_panel_title_html
    raw=dict((st.session_state.get("section_parameters") or {}).get(ends.SETTINGS_KEY) or {})
    span=ap._beam_uls_span_length_from_state(st.session_state,is_building=False)
    bounds=ap._beam_uls_section_bounds(geometry)
    defaults={"enabled":False,"left_solid_m":1.5,"right_solid_m":1.5,"left_taper_m":.25,"right_taper_m":.25,
        "width_mm":bounds[2]-bounds[0],"chamfer_mm":0.0,"left_end_x_m":0.0,"right_end_x_m":span,
        "hoop_confirmed":False,"d_region_confirmed":False,"load_reference_confirmed":False}
    if raw!=st.session_state.get(PREFIX+"source"):
        for key,value in defaults.items(): st.session_state[PREFIX+key]=raw.get(key,value)
    for key,value in defaults.items(): st.session_state.setdefault(PREFIX+key,raw.get(key,value))
    with st.container(border=True):
        st.markdown(_commercial_panel_title_html("Solid End Sections","ENDSECTION18","Along Girder","ULS"),unsafe_allow_html=True)
        enabled=st.checkbox("Enable solid precast end sections",key=PREFIX+"enabled")
        config={**defaults,**raw,"enabled":enabled}
        if enabled:
            inputs,preview=st.columns([1,1],gap="medium")
            with inputs:
                left,right=st.columns(2)
                for col,side in ((left,"left"),(right,"right")):
                    with col:
                        config[side+"_solid_m"]=st.number_input(side.title()+" solid length (m)",min_value=0.0,step=.1,format="%.3f",key=PREFIX+side+"_solid_m")
                        config[side+"_taper_m"]=st.number_input(side.title()+" taper length (m)",min_value=0.0,step=.05,format="%.3f",key=PREFIX+side+"_taper_m")
                config["width_mm"]=st.number_input("Solid-end width (mm)",min_value=1.0,step=10.0,key=PREFIX+"width_mm")
                st.caption(f"Solid-end height = {bounds[3]-bounds[1]:,.0f} mm, from the precast section. Taper linearly fills the I-profile sides toward this rectangle.")
                with st.expander("Coordinates and drawing confirmations"):
                    config["left_end_x_m"]=st.number_input("Left physical end x in Loads (m)",min_value=0.0,step=.025,format="%.3f",key=PREFIX+"left_end_x_m")
                    config["right_end_x_m"]=st.number_input("Right physical end x in Loads (m)",min_value=0.0,step=.025,format="%.3f",key=PREFIX+"right_end_x_m")
                    config["chamfer_mm"]=st.number_input("Solid-end corner chamfer (mm)",min_value=0.0,step=5.0,key=PREFIX+"chamfer_mm")
                    config["load_reference_confirmed"]=st.checkbox("CSI Mux/Nu reference matches each local section centroid",key=PREFIX+"load_reference_confirmed")
                    config["hoop_confirmed"]=st.checkbox("End/taper closed hoops and perimeter bars verified from drawing",key=PREFIX+"hoop_confirmed")
                    config["d_region_confirmed"]=st.checkbox("End/taper D-region, bearing and anchorage checked separately",key=PREFIX+"d_region_confirmed")
                    st.caption("Physical ends use the existing Loads x-axis. Strand sleeves/development remain measured from the physical cut ends; deck bar limits keep their Loads coordinates. Forces are never shifted or re-signed here.")
            params[ends.SETTINGS_KEY]=config
            candidate={**dict(st.session_state),"section_preset_key":"parametric_i_girder","section_parameters":params}
            with preview:
                try:
                    profile=ends.profile(candidate,geometry,span)
                    key=PREFIX+"preview_x"
                    if not profile.left_x_m<=st.session_state.get(key,profile.left_x_m)<=profile.right_x_m: st.session_state[key]=profile.left_x_m
                    st.session_state.setdefault(key,profile.left_x_m)
                    x=st.slider("Preview section at Loads x (m)",profile.left_x_m,profile.right_x_m,step=.025,format="%.3f",key=key)
                    local,trace=ends.section_at(geometry,profile,x)
                    bv=ap._beam_uls_web_width_mm(local)[0]
                    st.caption(f"{trace['Section region']} · bv ≈ {bv:,.0f} mm · Acp = {trace['Section Acp mm2']/1e6:.4f} m²")
                    fig=create_section_preview(local,[],dimension_label_mode="symbol_value");fig.update_layout(height=340)
                    st.plotly_chart(fig,use_container_width=True,key=PREFIX+"preview")
                    regions=[]
                    for a,b in zip(profile.boundaries,profile.boundaries[1:]):
                        if b>a: regions.append({"Loads x start (m)":a,"Loads x end (m)":b,"Section":profile.location((a+b)/2)[0]})
                    st.dataframe(pd.DataFrame(regions),hide_index=True,use_container_width=True)
                except (ValueError,TypeError,KeyError) as exc:
                    st.error(str(exc));st.caption("ULS section capacities remain unavailable until the end-section inputs are valid.")
            st.info("Calculate ULS again after editing. Local precast geometry feeds Flexure, Shear, Torsion and Shear + Torsion. Final-composite flexural/depth checks include the existing deck; torsion uses the precast polygon and closed hoop. Diaphragms are separate. SLS stresses/deflection and FE stiffness/self-weight still use the existing uniform-section model.")
        else:
            params[ends.SETTINGS_KEY]=config
            st.caption("Uniform I-section along the girder. Enable to enter the solid ends and taper lengths from the drawing.")
    st.session_state[PREFIX+"source"]=dict(config)

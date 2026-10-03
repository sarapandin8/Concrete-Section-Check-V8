"""Reproducible QA fixture using the real app styles and production renderers.

Run: streamlit run qa/igird_uls7_runtime.py
This fixture supplies QA inputs; it does not alter the production model/solvers.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import pandas as pd
import streamlit as st
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6d_torsion_auto_ph import _geometry
from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.analysis.igird_combined_vt import DEVELOPMENT_KEY
from concrete_pmm_pro.ui.analysis_page import _render_beam_girder_uls_workspace
from concrete_pmm_pro.ui.igird_combined_vt import render_development_inputs
from app import (_render_global_commercial_tab_styles, install_streamlit_plotly_readability_patch,
    _render_report_qa_igird_combined_vt_equation_trace, _results_beam_uls_summary_rows)

st.set_page_config(page_title='Concrete Section Pro — ULS7 QA',layout='wide')
_render_global_commercial_tab_styles();install_streamlit_plotly_readability_patch(st)
if 'qa_uls7_seeded' not in st.session_state:
    state=ready_state();state['section_geometry']=_geometry()
    ymin=min(p.y for p in state['section_geometry'].outer_polygon)
    ymax=max(p.y for p in state['section_geometry'].outer_polygon)
    state['rebars']=[Rebar(x_mm=x,y_mm=y,diameter_mm=20,material_name='SD40')
        for y in [ymin+100,ymax-100] for x in [-150.,150.]]
    state['beam_girder_torsion_settings']['clear_cover_mm']=44.0
    zones=[]
    for i,(a,b,s) in enumerate([(0,3,100),(3,6,150),(6,14,100),(14,17,150),(17,20,100)]):
        zones.append(dict(state['beam_girder_shear_reinforcement_table'].iloc[0],Zone=f'Z{i+1}',x_start_m=a,x_end_m=b,Spacing_mm=s))
    state['beam_girder_shear_reinforcement_table']=pd.DataFrame(zones)
    state['beam_girder_torsion_zone_settings']=[{'Zone':f'Z{i+1}','Use for Torsion':True,'Closed Loop':True,'135° Hook':True} for i in range(5)]
    state['beam_girder_uls_lazy_check']='Shear + Torsion'
    st.session_state.update(state);st.session_state['qa_uls7_seeded']=True

st.title('Concrete Section Pro')
st.caption('QA fixture — actual parametric I-Girder · AASHTO LRFD 9th Edition · span 20 m')
scenario=st.radio('QA scenario',['Ready sources','Transverse FAIL','Development REVIEW','Missing zone'],horizontal=True)
view=st.radio('QA view',['Analysis','Stored Summary / Report','Longitudinal inputs'],horizontal=True)
st.session_state[DEVELOPMENT_KEY]['continuous_full_span_confirmed']=scenario!='Development REVIEW'
for z in st.session_state['beam_girder_torsion_zone_settings']:
    z['Use for Torsion']=scenario!='Missing zone' if z['Zone']=='Z3' else True
st.session_state['beam_uls_loads_table']=pd.DataFrame([{'Active':True,'Station x (m)':float(x),
    'Case Name':'Strength I — concurrent QA','Mux':1000.0,'Vuy':200.0,
    'Tu':500.0 if scenario=='Transverse FAIL' else 50.0,'Muy':0.0,'Vux':0.0,'Nu':0.0,
    'Note':'QA physical imported row'} for x in [3,6,10,14,17]])
if view=='Analysis':
    _render_beam_girder_uls_workspace(AnalysisModeSettings(member_type='beam_girder'))
elif view=='Stored Summary / Report':
    st.dataframe(pd.DataFrame(_results_beam_uls_summary_rows(st.session_state)),hide_index=True,use_container_width=True)
    _render_report_qa_igird_combined_vt_equation_trace(st.session_state)
else:
    render_development_inputs()

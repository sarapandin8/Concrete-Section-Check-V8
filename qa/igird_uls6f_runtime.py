import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import streamlit as st
import pandas as pd
from test_igird_uls6_torsion_general_procedure import _state
from test_igird_uls6d_torsion_auto_ph import _geometry
from concrete_pmm_pro.core.models import Rebar,RebarMaterial
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.ui.analysis_page import _render_beam_girder_uls_workspace
from app import _render_global_commercial_tab_styles, install_streamlit_plotly_readability_patch
st.set_page_config(page_title='Concrete Section Pro — ULS6F QA',layout='wide')
_render_global_commercial_tab_styles()
install_streamlit_plotly_readability_patch(st)
if 'qa_seeded' not in st.session_state:
 state=_state()
 state['section_geometry']=_geometry()
 state['beam_girder_torsion_settings']['clear_cover_mm']=44.0
 state['analysis_mode_settings']=AnalysisModeSettings(member_type='beam_girder')
 state['project_design_code']='AASHTO LRFD'
 state['code_edition']='AASHTO LRFD 9th Edition'
 ymin=min(p.y for p in state['section_geometry'].outer_polygon); ymax=max(p.y for p in state['section_geometry'].outer_polygon)
 state['rebars']=[Rebar(x_mm=x,y_mm=y,diameter_mm=20,material_name='SD40',label=f'B{x}-{y}') for y in [ymin+100.,ymax-100.] for x in [-150.,150.]]
 state['rebar_materials']=[RebarMaterial(name='SD40',fy_MPa=390)]
 state['rebars_valid_for_analysis']=True
 state['section_has_ordinary_rebar']=True
 state['section_has_prestressing_steel']=True
 state['section_steel_systems']={'include_rebars':True,'include_prestress':True}
 zones=[]
 for i,(a,b,s) in enumerate([(0,3,100),(3,6,150),(6,14,250),(14,17,150),(17,20,100)]):
  zones.append(dict(state['beam_girder_shear_reinforcement_table'].iloc[0],Zone=f'Z{i+1}',x_start_m=a,x_end_m=b,Spacing_mm=s))
 state['beam_girder_shear_reinforcement_table']=pd.DataFrame(zones)
 state['beam_girder_torsion_zone_settings']=[{'Zone':f'Z{i+1}','Use for Torsion':True,'Closed Loop':True,'135° Hook':True} for i in range(5)]
 state['beam_uls_loads_table']=pd.DataFrame([{'Active':True,'Station x (m)':float(x),'Case Name':'Strength I — QA','Mux':500.0,'Vuy':400.-40*x,'Tu':500.0,'Muy':0.,'Vux':0.,'Nu':0.,'Note':'QA constant Tu; concurrent row'} for x in range(21)])
 state['beam_girder_uls_lazy_check']='Torsion'
 st.session_state.update(state)
 st.session_state['qa_seeded']=True
st.title('Concrete Section Pro')
st.caption('QA fixture — Precast I-Girder · AASHTO LRFD 9th Edition · 20 m')
gap=st.checkbox('QA: make Z3 not-ready',key='qa_gap')
for z in st.session_state['beam_girder_torsion_zone_settings']:
 z['Use for Torsion']=not gap if z['Zone']=='Z3' else True
_render_beam_girder_uls_workspace(AnalysisModeSettings(member_type='beam_girder'))
